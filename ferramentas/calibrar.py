"""
calibrar.py - Escolhe os limiares de interacao com base no SEU audio.

Le os turnos ja gravados no .json do pipeline.py e reprocessa a analise com varios
limiares, instantaneamente e sem tocar o audio. Assim voce compara numeros em
vez de aceitar o chute de quem escreveu o codigo (inclusive o meu).

Uso:
    python ferramentas/calibrar.py audios/reuniao_08.json
    python ferramentas/calibrar.py audios/*.json --detalhe

O que olhar:

  A distribuicao de sobreposicoes diz onde esta o ruido. Numa reuniao normal a
  mediana fica em torno de 0.6s, e isso e TRANSICAO DE TURNO - a pessoa emenda
  no fim da fala da outra. Nao e interrupcao. Se o limiar deixar isso passar, a
  contagem de interrupcao infla varias vezes.

  A varredura mostra como cada contagem reage ao limiar. Escolha o ponto onde a
  contagem para de cair rapido: abaixo dele voce esta contando ruido de
  fronteira da diarizacao, acima esta descartando evento real.

Depois de escolher:
    echo 'export MIN_SOBREPOSICAO=0.80' >> ~/.zshrc
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trama import interacao as I  # noqa: E402


def carregar_turnos(caminho):
    """Turnos vem do .json. Sem eles, avisa como regerar."""
    d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if "turnos" in d:
        return [(a, b, q) for a, b, q in d["turnos"]], d
    raise SystemExit(
        f"{caminho} nao tem 'turnos'.\n"
        "Foi gerado por uma versao antiga do pipeline.py. Rode o pipeline.py de novo\n"
        "nesse audio para gravar os turnos e poder calibrar sem reprocessar."
    )


def percentis(valores, ps=(10, 25, 50, 75, 90, 95, 99)):
    if not valores:
        return {}
    return {p: float(np.percentile(valores, p)) for p in ps}


def distribuicao(turnos):
    """Distribuicao bruta das sobreposicoes, sem nenhum limiar aplicado."""
    brutas = I.sobreposicoes(turnos, min_dur=0.0)
    duracoes = [b - a for a, b, _ in brutas]

    print(f"\n  Sobreposicoes brutas: {len(duracoes)}")
    if duracoes:
        pc = percentis(duracoes)
        print("    " + "  ".join(f"p{p}={v:.2f}s" for p, v in pc.items()))
        print(f"    total em sobreposicao: {sum(duracoes):.0f}s")

    pausas = []
    por_falante = {}
    for ini, fim, quem in turnos:
        por_falante.setdefault(quem, []).append((ini, fim))
    for segs in por_falante.values():
        segs.sort()
        for (_, fim), (ini, _) in zip(segs, segs[1:]):
            if 0 <= ini - fim < 10:
                pausas.append(ini - fim)

    if pausas:
        pc = percentis(pausas)
        print(f"\n  Pausas internas do mesmo falante: {len(pausas)}")
        print("    " + "  ".join(f"p{p}={v:.2f}s" for p, v in pc.items()))
        print("    -> GAP_MESCLAGEM acima da mediana junta fala fragmentada;")
        print("       alto demais funde falas realmente separadas.")


def varredura(turnos, valores=(0.2, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0)):
    print(f"\n  Varredura de MIN_SOBREPOSICAO (atual: {I.MIN_SOBREPOSICAO:.2f}s)")
    print(
        f"    {'LIMIAR':>8}{'APOIO':>8}{'INTERR.':>9}{'DISPUTA':>9}{'REGIOES':>9}{'SEG.SOBREP':>12}"
    )
    for v in valores:
        ev = I.eventos_de_fala(turnos, min_sobrep=v)
        reg = I.sobreposicoes(turnos, min_dur=v)
        tipos = [e["tipo"] for e in ev]
        seg = sum(b - a for a, b, _ in reg)
        marca = "  <- atual" if abs(v - I.MIN_SOBREPOSICAO) < 1e-6 else ""
        print(
            f"    {v:>7.2f}s{tipos.count('apoio'):>8}"
            f"{tipos.count('interrupcao'):>9}{tipos.count('disputa'):>9}"
            f"{len(reg):>9}{seg:>11.0f}s{marca}"
        )


def distribuicao_confianca(falas):
    """
    Distribuicao de confianca_media por fala - o que decide
    LIMIAR_CONFIANCA_FALA (pipeline.py), do mesmo jeito que a distribuicao de
    sobreposicoes decidiu MIN_SOBREPOSICAO: olhar os numeros reais antes
    de cravar o limiar.

    Ausente (reuniao de antes deste campo existir) so avisa e sai - nao ha
    o que medir sem reprocessar.
    """
    medias = [f["confianca_media"] for f in falas if "confianca_media" in f]
    if not medias:
        print(
            "\n  Nenhuma fala com 'confianca_media' - reprocesse com o "
            "pipeline.py atual para medir isto."
        )
        return

    pc = percentis(medias)
    print(f"\n  Confianca media por fala: {len(medias)} falas")
    print("    " + "  ".join(f"p{p}={v:.3f}" for p, v in pc.items()))

    buckets = [0] * 10
    for m in medias:
        buckets[min(int(m * 10), 9)] += 1
    maior = max(buckets) or 1
    print("\n    Histograma (0.0 a 1.0, passo 0.1):")
    for i, n in enumerate(buckets):
        barra = "#" * round(40 * n / maior)
        print(f"    [{i / 10:.1f}-{(i + 1) / 10:.1f}) {n:>4}  {barra}")


def varredura_gap(turnos_brutos, valores=(0.0, 0.3, 0.5, 0.8, 1.2, 2.0)):
    print("\n  Varredura de GAP_MESCLAGEM (efeito na contagem de turnos)")
    print(f"    {'GAP':>7}{'TURNOS':>9}{'MEDIA':>9}{'INTERR.':>9}{'DISPUTA':>9}")
    for v in valores:
        t = I.mesclar_turnos(turnos_brutos, gap_max=v)
        dur = sum(b - a for a, b, _ in t)
        ev = I.eventos_de_fala(t)
        tipos = [e["tipo"] for e in ev]
        marca = "  <- atual" if abs(v - I.GAP_MESCLAGEM) < 1e-6 else ""
        print(
            f"    {v:>6.2f}s{len(t):>9}{dur / max(len(t), 1):>8.1f}s"
            f"{tipos.count('interrupcao'):>9}{tipos.count('disputa'):>9}{marca}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsons", nargs="+")
    ap.add_argument(
        "--detalhe",
        action="store_true",
        help="Lista as disputas mais longas, para conferir no audio",
    )
    args = ap.parse_args()

    for caminho in args.jsons:
        turnos, dados = carregar_turnos(caminho)
        # Os turnos crus gravados no JSON usam SPEAKER_XX, porque sao
        # anteriores a identificacao. Traduz para os nomes reais usando o mapa
        # de clusters do mesmo JSON, senao o --detalhe imprime rotulos que nao
        # dizem nada a quem for conferir o audio.
        nomes = {k: v.get("nome", k) for k, v in dados.get("clusters", {}).items()}
        if nomes:
            turnos = [(a, b, nomes.get(q, q)) for a, b, q in turnos]
        print("\n" + "=" * 66)
        print(
            f"  {Path(caminho).name}   "
            f"{len(turnos)} turnos   {len(dados.get('clusters', {}))} falantes"
        )
        print("=" * 66)

        distribuicao(turnos)
        varredura(turnos)
        varredura_gap(turnos)
        distribuicao_confianca(dados.get("falas", []))

        if args.detalhe:
            ev = I.eventos_de_fala(turnos)
            disputas = sorted(
                (e for e in ev if e["tipo"] == "disputa"), key=lambda e: -e["sobreposicao_s"]
            )[:10]
            if disputas:
                print("\n  Disputas mais longas - ouca estes trechos no audio:")
                for e in disputas:
                    m, s = divmod(int(e["tempo"]), 60)
                    print(
                        f"    {m // 60:02d}:{m % 60:02d}:{s:02d}  "
                        f"{e['entrante']} x {e['falava']}  "
                        f"({e['sobreposicao_s']:.1f}s)"
                    )

    print("\n  Escolha o limiar onde a contagem PARA de cair rapido.")
    print("  Abaixo dele voce conta ruido de fronteira; acima, descarta evento real.\n")


if __name__ == "__main__":
    main()
