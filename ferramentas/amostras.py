"""
amostras.py - Exporta trechos de UM cluster para escuta manual, espalhados
pela reuniao inteira, SEM o piso de duracao da revisao (DURACAO_MIN_TRECHO
= 4.0s em revisao.py).

A amostragem da revisao existe para decidir em 20 segundos - por isso
descarta trecho curto. Mas contaminacao de cluster (uma pessoa aparecendo
por poucas palavras dentro do cluster de outra) e exatamente o que um
trecho curto capturaria e a revisao descarta por construcao (ver
ARCHITECTURE.md, "Verificacao de pureza de cluster por embedding medio tem
ponto cego"). Este script existe para OUVIR fora dessa amostra, nao para
decidir sozinho - a decisao continua sendo escuta humana.

Le os turnos crus (label -> intervalos) do .json ja gravado pelo pipeline.py -
nao roda diarizacao de novo, so recorta o audio original.

Uso:
    python ferramentas/amostras.py audios/reuniao_06/reuniao_06.json SPEAKER_02
    python ferramentas/amostras.py audios/reuniao_06/reuniao_06.json SPEAKER_02 -n 15 --min-dur 1.0
"""

import argparse
import json
import subprocess
from pathlib import Path


def amostras_espalhadas(segs, n):
    """
    [(inicio, fim), ...] -> n trechos espalhados no TEMPO, nao os n mais
    longos - mesma logica de fase0.py:amostras_espalhadas. Inclui sempre o
    primeiro e o ultimo segmento.
    """
    segs = sorted(segs)
    if len(segs) <= n:
        return segs
    idx = [round(i * (len(segs) - 1) / (n - 1)) for i in range(n)]
    return [segs[i] for i in sorted(set(idx))]


def cortar(audio_origem, ini, fim, destino, margem=0.25):
    ini_c = max(0.0, ini - margem)
    dur = (fim - ini) + 2 * margem
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{ini_c:.3f}",
            "-t",
            f"{dur:.3f}",
            "-i",
            str(audio_origem),
            "-c:a",
            "pcm_s16le",
            str(destino),
        ],
        # ffmpeg le o terminal por padrao e come a entrada de quem chamou
        # (ver nucleo.to_wav16k).
        stdin=subprocess.DEVNULL,
        check=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file")
    ap.add_argument("cluster", help="Rotulo cru do turno, ex.: SPEAKER_02")
    ap.add_argument("-n", type=int, default=10)
    ap.add_argument(
        "--min-dur",
        type=float,
        default=0.0,
        help="Duracao minima do trecho em segundos "
        "(0 = sem piso, inclui os curtos que a revisao descarta)",
    )
    ap.add_argument("--out", help="Pasta de saida (padrao: ao lado do .json)")
    args = ap.parse_args()

    caminho = Path(args.json_file)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if "turnos" not in dados:
        raise SystemExit(
            f"{caminho} nao tem 'turnos' - rode o pipeline.py atual nesse audio "
            "antes (versoes antigas nao gravam os turnos crus)."
        )

    segs = [(a, b) for a, b, q in dados["turnos"] if q == args.cluster and (b - a) >= args.min_dur]
    if not segs:
        raise SystemExit(
            f"nenhum turno de {args.cluster} com duracao >= {args.min_dur}s "
            f"(clusters disponiveis: {sorted({q for _, _, q in dados['turnos']})})"
        )

    escolhidos = amostras_espalhadas(segs, args.n)

    audio_origem = dados.get("audio")
    if not audio_origem or not Path(audio_origem).exists():
        raise SystemExit(
            f"audio original nao encontrado em {audio_origem!r} - o "
            "arquivo pode ter sido movido desde o processamento."
        )

    saida = Path(args.out or caminho.parent / f"amostras_{args.cluster}")
    saida.mkdir(parents=True, exist_ok=True)

    print(
        f"Exportando {len(escolhidos)} de {len(segs)} trechos de "
        f"{args.cluster} (duracao >= {args.min_dur}s) para {saida}/\n"
    )
    for i, (ini, fim) in enumerate(escolhidos, 1):
        dur = fim - ini
        nome = f"{i:02d}_{int(ini) // 60:02d}m{int(ini) % 60:02d}s_{dur:.1f}s.wav"
        cortar(audio_origem, ini, fim, saida / nome)
        print(f"  {nome}")

    print(f"\nOuca em: {saida}/")


if __name__ == "__main__":
    main()
