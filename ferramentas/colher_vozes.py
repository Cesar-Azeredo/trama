"""
colher_vozes.py - Constroi a galeria de vozes A PARTIR das reunioes que voce ja tem.

Isto substitui o cadastro previo. Voce nao precisa juntar as pessoas para
gravar amostra: o audio das reunioes antigas JA E a amostra, e na condicao
acustica exata que importa (sua sala, seu microfone, a cadeira de cada um).

Uso:
    python ferramentas/colher_vozes.py reuniao_fase0/fase0.json SPEAKER_00=Joao SPEAKER_02=Maria

Clusters nao mencionados sao ignorados - e assim que deve ser. Se voce nao tem
certeza de quem e um cluster, nao o inclua. Perfil contaminado e pior do que
perfil ausente, porque o erro fica escondido e se propaga para as proximas
reunioes.

Repita em 3 ou 4 reunioes. Cada uma empurra o perfil da pessoa um pouco mais.
"""

import argparse
import json
from pathlib import Path

from trama import nucleo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file", help="fase0.json gerado pelo fase0.py")
    ap.add_argument("mapa", nargs="+", help="SPEAKER_00=Joao SPEAKER_01=Maria")
    ap.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    ap.add_argument(
        "--peso",
        type=float,
        default=1.0,
        help="Multiplicador de confianca (use 0.5 se tiver duvida)",
    )
    ap.add_argument(
        "--min-fala",
        type=float,
        default=40.0,
        help="Segundos minimos de fala para aceitar o cluster",
    )
    ap.add_argument(
        "--simular", action="store_true", help="Mostra o que faria, sem gravar no banco"
    )
    args = ap.parse_args()

    dados = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    wav = dados["wav16k"]
    clusters = dados["clusters"]

    if not Path(wav).exists():
        raise SystemExit(
            f"WAV nao encontrado: {wav}\n"
            "Rode o fase0.py de novo (ele grava o wav16k dentro da pasta de saida)."
        )

    pares = []
    for item in args.mapa:
        if "=" not in item:
            raise SystemExit(f"Formato invalido: '{item}'. Use SPEAKER_00=Joao")
        label, nome = item.split("=", 1)
        label, nome = label.strip(), nome.strip()
        if label not in clusters:
            raise SystemExit(
                f"Cluster '{label}' nao existe. Disponiveis: " + ", ".join(sorted(clusters))
            )
        pares.append((label, nome))

    print()
    for label, nome in pares:
        info = clusters[label]
        fala = info["fala_s"]

        if fala < args.min_fala:
            print(
                f"  PULADO  {label} -> {nome}: so {fala:.0f}s de fala "
                f"(minimo {args.min_fala:.0f}s). Embedding seria instavel."
            )
            continue

        emb, usados = nucleo.embed_segments(wav, info["segmentos"], device=args.device)

        if emb is None:
            print(f"  FALHOU  {label} -> {nome}: nenhum trecho utilizavel.")
            continue

        if args.simular:
            print(f"  (simulado) {label} -> {nome}: {usados:.0f}s de fala usados")
            continue

        total = nucleo.upsert_pessoa(nome, emb, peso=usados * args.peso)
        print(
            f"  OK      {label} -> {nome:<16} "
            f"({usados:.0f}s desta reuniao, {total:.0f}s acumulados)"
        )

    if not args.simular:
        print("\nGaleria atual:")
        for nome, peso, quando in nucleo.listar_pessoas():
            print(f"  {nome:<18}{peso:>7.0f}s   {quando}")
        print("\nRepita em outras reunioes para reforcar os perfis.")
        print("Depois: trama-processar reuniao.m4a --pessoas Joao,Maria,Pedro")


if __name__ == "__main__":
    main()
