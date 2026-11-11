"""
experimental/cadastro_avulso.py - Cadastro de voz de uma pessoa por
gravacao avulsa (antigo cadastro_avulso.py).

EXPERIMENTAL, FORA DO PRODUTO: o caminho descartado pelo ADR 0011
(docs/adr/0011-sem-cadastro-por-gravacao-avulsa.md). O jeito que o
produto usa e colher a voz da propria reuniao - ferramentas/colher_vozes.py
e a revisao (trama-revisar). Fica aqui como registro e para comparacao.

Uso:
    python experimental/cadastro_avulso.py Joao amostras/joao/*.wav
    python experimental/cadastro_avulso.py --listar

REGRA DE OURO DO CADASTRO:
grave as amostras NA MESMA SALA, COM O MESMO MICROFONE E NA MESMA POSICAO
das reunioes reais. Um cadastro feito no headset e comparado depois contra
o mic da mesa vira erro de identificacao garantido - o embedding captura o
canal acustico junto com a voz.

Peca ~90 segundos de fala espontanea (nao leitura), em 2 ou 3 arquivos.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

from trama import nucleo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nome", nargs="?", help="Nome da pessoa")
    ap.add_argument("arquivos", nargs="*", help="Arquivos de audio de amostra")
    ap.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    ap.add_argument("--listar", action="store_true")
    ap.add_argument(
        "--reset", action="store_true", help="Apaga o perfil existente antes de cadastrar"
    )
    args = ap.parse_args()

    if args.listar:
        rows = nucleo.listar_pessoas()
        if not rows:
            print("Nenhuma pessoa cadastrada.")
            return
        print(f"{'NOME':<20} {'FALA ACUM.':>12}   ATUALIZADO")
        for nome, peso, quando in rows:
            print(f"{nome:<20} {peso:>9.0f} s   {quando}")
        return

    if not args.nome or not args.arquivos:
        ap.error("informe o nome e pelo menos um arquivo de audio")

    if args.reset:
        con = nucleo.connect()
        # Apaga tambem a base legada e o ledger de contribuicoes desta
        # pessoa - senao a proxima revisao de reuniao recalcula o perfil a
        # partir do que sobrou e o "reset" parece nao ter feito nada.
        con.execute("DELETE FROM pessoas WHERE nome = ?", (args.nome,))
        con.execute("DELETE FROM pessoas_legado WHERE nome = ?", (args.nome,))
        con.execute("DELETE FROM contribuicoes WHERE pessoa = ?", (args.nome,))
        con.commit()
        con.close()

    vecs, pesos = [], []
    for f in args.arquivos:
        p = Path(f)
        if not p.exists():
            print(f"  ! nao encontrado: {f}", file=sys.stderr)
            continue
        wav = nucleo.to_wav16k(p)
        emb = nucleo.embed_file(wav, device=args.device)
        import soundfile as sf

        dur = sf.info(wav).duration
        vecs.append(emb)
        pesos.append(dur)
        print(f"  + {p.name}  ({dur:.1f}s)")

    if not vecs:
        raise SystemExit("Nenhuma amostra valida.")

    total = sum(pesos)
    if total < 45:
        print(f"\n  AVISO: so {total:.0f}s de amostra. O ideal sao 90s ou mais.")

    media = nucleo.l2(np.average(np.stack(vecs), axis=0, weights=np.asarray(pesos)))
    peso_final = nucleo.upsert_pessoa(args.nome, media, peso=total)
    print(f"\nOK: '{args.nome}' cadastrado. Fala acumulada no perfil: {peso_final:.0f}s")


if __name__ == "__main__":
    main()
