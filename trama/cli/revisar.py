"""
trama/cli/revisar.py - Revisao dos nomes pelo terminal (antigo main do
review.py): uma pergunta por cluster, confirmacao do que muda na voz
aprendida, gravacao. A logica e a de trama/revisao.py - a mesma que a tela
de Revisao usa pelo servidor.

Uso:
    trama-revisar audios/reuniao_NN/reuniao_NN.json
    trama-revisar audios/reuniao_NN/reuniao_NN.json --sem-aprender
"""

import argparse
import json
import sys
from pathlib import Path

from trama import nucleo, revisao


def formatar_trechos_cli(trechos):
    """So a apresentacao no terminal - a selecao mora em
    revisao.selecionar_trechos(), separada para ser testavel sem strings."""
    out = []
    for f in trechos:
        t = f["texto"]
        out.append(f"      [{nucleo.hhmmss(f['inicio'])}] {t[:90]}{'...' if len(t) > 90 else ''}")
    return out


def _mostrar_cluster(label, info, falas):
    print("-" * 62)
    print(
        f"  {label}   sugerido: {info['nome']}   "
        f"sim={info['sim']:.3f}  margem={info['margem']:.3f}  "
        f"fala={info['fala_s']:.0f}s"
    )
    if info.get("scores"):
        top = sorted(info["scores"].items(), key=lambda kv: -kv[1])[:3]
        print("    candidatos: " + "  ".join(f"{n}={s:.3f}" for n, s in top))
    for linha in formatar_trechos_cli(revisao.selecionar_trechos(falas, label)):
        print(linha)


def _perguntar(clusters, falas, sem_aprender):
    """Uma pergunta por cluster. Devolve (renomear, aprender, retirar)."""
    renomear, aprender, retirar = {}, [], []
    for label in sorted(clusters):
        info = clusters[label]
        _mostrar_cluster(label, info, falas)
        resp = input(f"    Quem e? [{info['nome']}] ").strip()
        nome = info["nome"] if resp == "" else resp

        # Mesma regra da tela (servidor/revisao.planejar): ignorar ou so
        # nomear tira do ledger o que este cluster ja tinha ensinado.
        if nome == "-":
            renomear[label] = f"IGNORADO_{label}"
            retirar.append(label)
            continue
        renomear[label] = nome
        contrib = None if sem_aprender else revisao.decidir_contribuicao(label, nome, info)
        if contrib:
            aprender.append(contrib)
        else:
            retirar.append(label)
    return renomear, aprender, retirar


def _frase_do_efeito(e):
    if e["tipo"] == "ensinar":
        frase = f"ensina {e['peso_s']:.0f} s da voz de {e['pessoa']}"
    elif e["tipo"] == "mover":
        frase = f"move {e['peso_s']:.0f} s da voz de {e['pessoa']} para {e['para']}"
    else:
        frase = f"remove {e['peso_s']:.0f} s da voz de {e['pessoa']}"
    fim = " - o perfil deixa de existir" if e["perfil_some"] else ""
    return f"  {e['cluster']}: {frase}{fim}"


def _confirmar_efeitos(reuniao_id, aprender, retirar):
    """Mostra o que muda na voz aprendida e pede confirmacao; sai sem
    gravar nada se a pessoa nao confirmar."""
    efeitos = revisao.efeitos_no_ledger(reuniao_id, aprender, retirar)
    if not efeitos:
        return
    print("\nIsto muda a voz aprendida:")
    for e in efeitos:
        print(_frase_do_efeito(e))
    if input("Confirmar? [s/N] ").strip().lower() != "s":
        sys.exit("Nada foi gravado.")


def main():
    ap = argparse.ArgumentParser(prog="trama-revisar")
    ap.add_argument("json_file")
    ap.add_argument(
        "--sem-aprender",
        action="store_true",
        help="Corrige o texto mas nao atualiza os perfis de voz",
    )
    args = ap.parse_args()

    caminho = Path(args.json_file)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    reuniao_id = revisao.garantir_reuniao_id(caminho, dados)

    conhecidos = sorted(n for n, _, _ in nucleo.listar_pessoas())
    print(f"\nPessoas ja cadastradas: {', '.join(conhecidos) or '(nenhuma)'}")
    print("\nEnter = aceitar   |   digitar nome = corrigir   |   '-' = ignorar cluster\n")

    renomear, aprender, retirar = _perguntar(dados["clusters"], dados["falas"], args.sem_aprender)
    _confirmar_efeitos(dados.get("reuniao_id"), aprender, retirar)

    so_nomear = (
        [label for label, n in renomear.items() if not n.startswith("IGNORADO")]
        if args.sem_aprender
        else ()
    )
    try:
        totais = revisao.aplicar_e_gravar(
            caminho, dados, reuniao_id, renomear, aprender, retirar, so_nomear=so_nomear
        )
    except Exception as exc:
        sys.exit(
            f"\nFalha ao atualizar os perfis de voz: {type(exc).__name__}: {exc}\n"
            "Nada foi gravado (nem o TXT/JSON corrigidos). O arquivo "
            "continua como antes - rode trama-revisar de novo com as mesmas "
            "respostas quando o problema for resolvido."
        )

    if aprender:
        print("\nAtualizando perfis de voz:")
        for _, nome, _, _ in aprender:
            print(f"  {nome:<18} fala acumulada: {totais.get(nome, 0.0):.0f}s")

    if not dados.get("turnos"):
        print(
            "\n  ! arquivo antigo sem 'turnos' brutos - dinamica/eventos/"
            "matriz/regioes nao foram recalculados (ver dados['avisos'])."
        )

    print(f"\nCorrigido: {caminho.with_suffix('.txt')}")


if __name__ == "__main__":
    main()
