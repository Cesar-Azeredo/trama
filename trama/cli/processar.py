"""
trama/cli/processar.py - Processa uma reuniao: diarizacao, identificacao
pela voz, analise de interacao, transcricao (antigo main do run.py).

Uso:
    trama-processar audios/reuniao_NN/reuniao_NN.m4a \\
        --pessoas Nome1,Nome2 --device mps --asr mlx

O servidor roda este modulo como subprocess (python -m trama.cli.processar)
e le o progresso das linhas "N/5  texto..." do stdout.
"""

import argparse

from trama import pipeline, termos


def _argumentos():
    ap = argparse.ArgumentParser(prog="trama-processar")
    ap.add_argument("audio")
    ap.add_argument("--pessoas", help="Quem estava na sala: Joao,Maria,Pedro")
    ap.add_argument("--falantes", type=int, help="Numero exato de falantes")
    ap.add_argument("--min-falantes", type=int)
    ap.add_argument("--max-falantes", type=int)
    ap.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "mps"],
        help="No Mac, teste os dois: MPS nem sempre e mais rapido",
    )
    ap.add_argument("--asr", default="mlx", choices=["mlx", "faster"])
    ap.add_argument("--modelo", default=pipeline.MODELO_PADRAO)
    ap.add_argument("--idioma", default="pt")
    ap.add_argument(
        "--termos",
        default=termos.ARQUIVO_PADRAO,
        help="Arquivo de vocabulario do dominio (errado => certo)",
    )
    ap.add_argument("--sem-termos", action="store_true", help="Desliga a correcao de vocabulario")
    ap.add_argument("--out", help="Prefixo dos arquivos de saida")
    return ap.parse_args()


def main():
    args = _argumentos()
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
    print(f"\nPronto:\n  {saida}.txt\n  {saida}.json")
    print(f"\nAgora rode:  trama-revisar {saida}.json")


if __name__ == "__main__":
    main()
