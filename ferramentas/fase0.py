"""
fase0.py - Valida SO a diarizacao. Sem Whisper, sem galeria, sem identificacao.

Responde uma unica pergunta: o pyannote consegue separar as pessoas no MEU audio?

Uso:
    python ferramentas/fase0.py reuniao.m4a --max-falantes 6
    python ferramentas/fase0.py reuniao.m4a --falantes 4        # se voce sabe quantos eram

Saidas:
    reuniao_fase0/SPEAKER_00/*.wav   <- amostras para voce OUVIR
    reuniao_fase0/fase0.json         <- segmentos (usado pelo colher_vozes.py)

Depois de rodar, ouca as amostras de cada pasta e conte quantas sao a mesma
pessoa. 9 ou 10 em 10 = otimo. 6 em 10 = o microfone e o problema, nao o modelo.
"""

import argparse
import json
import subprocess
from pathlib import Path

import torch

from trama import nucleo

DIAR_MODEL_DEFAULT = "pyannote/speaker-diarization-community-1"


def iter_turns(annotation):
    if hasattr(annotation, "itertracks"):
        for turn, _, label in annotation.itertracks(yield_label=True):
            yield turn, label
    else:
        for turn, label in annotation:
            yield turn, label


def info_audio(caminho):
    """Checagem rapida de qualidade da gravacao original."""
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=sample_rate,channels,codec_name",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(caminho),
            ],
            # ffprobe NAO aceita -nostdin (falha com "Option not found");
            # stdin=DEVNULL tira o terminal dele do mesmo jeito.
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=True,
        )
        d = json.loads(r.stdout)
        s = d["stream" + "s"][0]
        return {
            "sample_rate": int(s.get("sample_rate", 0)),
            "canais": int(s.get("channels", 0)),
            "codec": s.get("codec_name", "?"),
            "duracao": float(d["format"]["duration"]),
        }
    except Exception:
        return None


def amostras_espalhadas(segs, n, min_dur=2.0):
    """
    Pega n trechos ESPALHADOS ao longo da reuniao, nao os n mais longos.

    Isso e proposital: se a pessoa mudou de posicao no meio da reuniao, ou se
    o cluster misturou duas pessoas, o problema aparece na dispersao temporal.
    Pegar so os trechos mais longos esconde exatamente esse defeito.
    """
    bons = sorted([s for s in segs if (s.end - s.start) >= min_dur], key=lambda s: s.start)
    if not bons:
        bons = sorted(segs, key=lambda s: s.start)
    if len(bons) <= n:
        return bons
    # Inclui explicitamente o primeiro E o ultimo trecho. O fim da reuniao e
    # onde a voz mais deriva (cansaco, pessoa recostada, mudanca de posicao).
    idx = [round(i * (len(bons) - 1) / (n - 1)) for i in range(n)]
    return [bons[i] for i in sorted(set(idx))]


def cortar(wav, seg, destino, margem=0.25):
    ini = max(0.0, seg.start - margem)
    dur = (seg.end - seg.start) + 2 * margem
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{ini:.3f}",
            "-t",
            f"{dur:.3f}",
            "-i",
            wav,
            "-c:a",
            "pcm_s16le",
            str(destino),
        ],
        # ffmpeg le o terminal por padrao e come a entrada de quem chamou
        # (ver nucleo.to_wav16k).
        stdin=subprocess.DEVNULL,
        check=True,
    )


def _argumentos():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--falantes", type=int)
    ap.add_argument("--min-falantes", type=int)
    ap.add_argument("--max-falantes", type=int)
    ap.add_argument("--esperado", type=int, help="Quantas pessoas voce LEMBRA que estavam na sala")
    ap.add_argument("--amostras", type=int, default=8)
    ap.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    ap.add_argument("--modelo", default=DIAR_MODEL_DEFAULT)
    ap.add_argument("--out")
    return ap.parse_args()


def _avisar_qualidade(origem):
    meta = info_audio(origem)
    if not meta:
        return
    print(
        f"Original: {meta['codec']}  {meta['sample_rate']} Hz  "
        f"{meta['canais']} canal(is)  {meta['duracao'] / 60:.1f} min"
    )
    if meta["sample_rate"] < 16000:
        print("  ! Abaixo de 16 kHz. A diarizacao vai sofrer.")


def _faixa(args):
    if args.falantes:
        return {"num_speakers": args.falantes}
    kwargs = {}
    if args.min_falantes:
        kwargs["min_speakers"] = args.min_falantes
    if args.max_falantes:
        kwargs["max_speakers"] = args.max_falantes
    return kwargs


def _diarizar(wav, args):
    from pyannote.audio import Pipeline
    from pyannote.audio.pipelines.utils.hook import ProgressHook

    pipeline = Pipeline.from_pretrained(args.modelo, token=nucleo.HF_TOKEN)
    pipeline.to(torch.device(args.device))
    with ProgressHook() as hook:
        out = pipeline(wav, hook=hook, **_faixa(args))
    clusters = {}
    for turn, label in iter_turns(out.speaker_diarization):
        clusters.setdefault(label, []).append(turn)
    return clusters


def _exportar_cluster(label, segs, wav, saida, n_amostras):
    """Imprime a linha do cluster, corta as amostras e devolve o resumo."""
    total = sum(s.end - s.start for s in segs)
    maior = max(s.end - s.start for s in segs)
    ini = min(s.start for s in segs)
    fim = max(s.end for s in segs)
    print(
        f"{label:<12}{total:>7.0f}s{len(segs):>8}"
        f"{nucleo.hhmmss(ini):>10}{nucleo.hhmmss(fim):>10}{maior:>7.0f}s"
    )
    pasta = saida / label
    pasta.mkdir(exist_ok=True)
    for i, s in enumerate(amostras_espalhadas(segs, n_amostras), 1):
        cortar(wav, s, pasta / f"{i:02d}_{nucleo.hhmmss(s.start).replace(':', '')}.wav")
    return {
        "fala_s": round(total, 1),
        "turnos": len(segs),
        "segmentos": [[round(s.start, 3), round(s.end, 3)] for s in segs],
    }


def _diagnostico(dados, esperado):
    n = len(dados)
    print(f"\n{'=' * 62}")
    print(f"Clusters encontrados: {n}")
    if esperado:
        if n > esperado * 1.5:
            print(f"  ! OVER-SPLITTING. Voce esperava {esperado}.")
            print("    Causa tipica: reverberacao, distancia do mic, pessoa que")
            print(f"    mudou de posicao. Tente rodar com --falantes {esperado} e compare.")
        elif n < esperado:
            print(
                f"  ! Menos clusters que pessoas ({esperado}). Alguem"
                " falou pouco, ou duas vozes foram fundidas."
            )
        else:
            print("  OK: bateu com o esperado.")

    curtos = [label for label, d in dados.items() if d["fala_s"] < 30]
    if curtos:
        print(f"  Clusters com pouca fala (<30s): {', '.join(sorted(curtos))}")
        print("    Nao dao embedding confiavel. Podem ser ruido ou fala cruzada.")


def main():
    args = _argumentos()
    origem = Path(args.audio)
    saida = Path(args.out or f"{origem.with_suffix('')}_fase0")
    saida.mkdir(parents=True, exist_ok=True)
    _avisar_qualidade(origem)

    print("\n1/3  Convertendo para 16 kHz mono...")
    wav = nucleo.to_wav16k(origem, str(saida / "audio16k.wav"))

    print("2/3  Diarizando (so isso, sem transcricao)...")
    clusters = _diarizar(wav, args)

    print("\n3/3  Exportando amostras para escuta...\n")
    print(f"{'CLUSTER':<12}{'FALA':>9}{'TURNOS':>8}{'1a VEZ':>10}{'ULT VEZ':>10}{'MAIOR':>8}")
    dados = {
        label: _exportar_cluster(label, clusters[label], wav, saida, args.amostras)
        for label in sorted(clusters)
    }
    with open(saida / "fase0.json", "w", encoding="utf-8") as f:
        json.dump(
            {"audio": str(origem.resolve()), "wav16k": wav, "clusters": dados},
            f,
            ensure_ascii=False,
            indent=1,
        )

    _diagnostico(dados, args.esperado)
    print(f"\nAgora ouca:  {saida}/SPEAKER_XX/*.wav")
    print("Conte quantas amostras de cada pasta sao a MESMA pessoa.")
    print("\nQuando souber quem e quem:")
    print(
        f"  python ferramentas/colher_vozes.py {saida}/fase0.json SPEAKER_00=Joao SPEAKER_01=Maria"
    )


if __name__ == "__main__":
    main()
