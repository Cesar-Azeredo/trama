"""
trama/cli/processar.py - Processa uma reuniao: diarizacao, identificacao
pela voz, analise de interacao, transcricao (antigo main do run.py).

Uso:
    trama-processar audios/reuniao_NN/reuniao_NN.m4a \\
        --pessoas Nome1,Nome2 --device mps --asr mlx

O servidor roda este modulo como subprocess (python -m trama.cli.processar)
com --progresso-json, e le o progresso das linhas "@progresso {json}" do
stdout (pipeline._progresso) - nunca da frase "N/5  texto...", que e para
quem le o terminal.
"""

import argparse
import signal
import sys

from trama import pipeline, termos
from trama.idioma import t


def _sigterm_vira_saida(*_):
    # "Cancelar" na tela manda SIGTERM. O padrao do Python e morrer na hora,
    # sem rodar nenhum finally - e o finally de pipeline.processar e o que
    # apaga a copia WAV do audio (trama/temporarios.py).
    sys.exit(143)


def _argumentos():
    ap = argparse.ArgumentParser(prog="trama-processar")
    ap.add_argument("audio")
    ap.add_argument("--pessoas", help=t("ajuda_pessoas"))
    # Para o servidor: progresso tambem em linhas "@progresso {json}"
    # (pipeline._progresso). Quem roda no terminal nao precisa.
    ap.add_argument("--progresso-json", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--falantes", type=int, help=t("ajuda_falantes"))
    ap.add_argument("--min-falantes", type=int)
    ap.add_argument("--max-falantes", type=int)
    ap.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "mps"],
        help=t("ajuda_device"),
    )
    ap.add_argument("--asr", default="mlx", choices=["mlx", "faster"])
    ap.add_argument("--modelo", default=pipeline.MODELO_PADRAO)
    ap.add_argument("--idioma", default="pt", help=t("ajuda_idioma_fala"))
    ap.add_argument(
        "--termos",
        default=termos.ARQUIVO_PADRAO,
        help=t("ajuda_termos"),
    )
    ap.add_argument("--sem-termos", action="store_true", help=t("ajuda_sem_termos"))
    ap.add_argument("--out", help=t("ajuda_out"))
    return ap.parse_args()


def main():
    signal.signal(signal.SIGTERM, _sigterm_vira_saida)
    args = _argumentos()
    pipeline.PROGRESSO_MAQUINA = args.progresso_json
    pessoas = [p.strip() for p in args.pessoas.split(",")] if args.pessoas else None
    saida = pipeline.processar(
        args.audio,
        pessoas=pessoas,
        falantes=args.falantes,
        min_falantes=args.min_falantes,
        max_falantes=args.max_falantes,
        device=args.device,
        asr=args.asr,
        modelo=args.modelo,
        idioma=args.idioma,
        arquivo_termos=args.termos,
        sem_termos=args.sem_termos,
        out=args.out,
    )
    print(t("pronto", txt=f"{saida}.txt", json=f"{saida}.json"))
    print(t("agora_rode", json=f"{saida}.json"))


if __name__ == "__main__":
    main()
