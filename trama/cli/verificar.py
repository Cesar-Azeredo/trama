"""
trama/cli/verificar.py - Verifica o ambiente antes da primeira execucao
(antigo cli/verificar.py).

Roda em segundos. Serve para voce nao descobrir que falta acesso a um modelo
depois de 20 minutos de diarizacao.

Uso:
    trama-verificar
"""

import importlib
import os
import shutil
import sys

REPOS = [
    ("pyannote/speaker-diarization-community-1", "pipeline de diarizacao"),
    ("pyannote/wespeaker-voxceleb-resnet34-LM", "modelo de embedding de voz"),
]

PACOTES = [
    ("pyannote.audio", "pyannote.audio"),
    ("torch", "torch"),
    ("numpy", "numpy"),
    ("soundfile", "soundfile"),
    ("huggingface_hub", "huggingface_hub"),
]

ok_geral = True


def ok(msg):
    print(f"  \033[92mOK\033[0m      {msg}")


def falha(msg, dica=""):
    global ok_geral
    ok_geral = False
    print(f"  \033[91mFALHOU\033[0m  {msg}")
    if dica:
        for linha in dica.strip().splitlines():
            print(f"          {linha}")


def aviso(msg):
    print(f"  \033[93mAVISO\033[0m   {msg}")


def _sistema():
    print("\n--- Sistema ---")
    versao = f"Python {sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info < (3, 12):
        falha(versao, "O trama precisa de Python 3.12 ou mais novo.")
    else:
        ok(versao)

    if shutil.which("ffmpeg"):
        ok("ffmpeg encontrado")
    else:
        falha("ffmpeg não encontrado", "brew install ffmpeg")

    if shutil.which("ffprobe"):
        ok("ffprobe encontrado")
    else:
        aviso("ffprobe ausente (o fase0 só perde a checagem de qualidade do áudio)")

    if sys.prefix == sys.base_prefix:
        aviso(
            "Você não está num virtualenv. Recomendado: "
            "python -m venv .venv && source .venv/bin/activate"
        )


def _pacotes():
    print("\n--- Pacotes Python ---")
    for modulo, nome in PACOTES:
        try:
            m = importlib.import_module(modulo)
            ok(f"{nome} {getattr(m, '__version__', '?')}")
        except ImportError:
            falha(f"{nome} não instalado", 'pip install -e ".[dev]"')

    try:
        import pyannote.audio as pa

        v = getattr(pa, "__version__", "0")
        if v != "?" and int(str(v).split(".")[0]) < 4:
            falha(
                f"pyannote.audio {v} é antigo",
                "O community-1 exige a versão 4 ou superior.\npip install -U 'pyannote.audio>=4.0'",
            )
    except Exception:
        pass

    # Transcricao: qualquer um dos dois serve
    tem_asr = False
    for mod, flag in [("mlx_whisper", "--asr mlx"), ("faster_whisper", "--asr faster")]:
        try:
            importlib.import_module(mod)
            ok(f"{mod} disponível  (use {flag})")
            tem_asr = True
        except ImportError:
            pass
    if not tem_asr:
        aviso(
            "Nenhum motor de transcrição instalado. "
            "O fase0 funciona sem ele; o trama-processar não."
        )


def _apple_silicon():
    print("\n--- Apple Silicon ---")
    try:
        import torch

        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            ok("MPS disponível (mas teste contra --device cpu antes de confiar)")
        else:
            aviso("MPS indisponível - vai rodar em CPU, o que costuma ser aceitável")
    except Exception:
        pass


def _token_do_cache():
    try:
        from huggingface_hub import get_token

        return get_token()
    except Exception:
        try:
            from huggingface_hub import HfFolder

            return HfFolder.get_token()
        except Exception:
            return None


def _token():
    """Devolve o token do Hugging Face (ou None) e checa se ele autentica."""
    print("\n--- Token Hugging Face ---")
    token, origem = os.environ.get("HF_TOKEN"), "variável HF_TOKEN"
    if not token:
        token, origem = _token_do_cache(), "cache do hf auth login"

    if not token:
        falha("Nenhum token encontrado", "export HF_TOKEN=hf_xxxxx     (ou rode: hf auth login)")
        return None
    if not token.startswith("hf_"):
        aviso("O token não começa com 'hf_'. Confirme se copiou o valor certo.")
    ok(f"Token presente ({origem}, termina em ...{token[-4:]})")

    try:
        from huggingface_hub import HfApi

        me = HfApi().whoami(token=token)
        ok(f"Autenticado como '{me.get('name', '?')}'")
    except Exception as e:
        falha(
            f"Token inválido ou revogado ({type(e).__name__})",
            "Crie outro em huggingface.co/settings/tokens",
        )
    return token


def _acesso_aos_modelos(token):
    print("\n--- Acesso aos modelos ---")
    if not token:
        aviso("Sem token, não dá para checar acesso aos modelos.")
        return
    from huggingface_hub import HfApi

    api = HfApi()
    for repo, desc in REPOS:
        try:
            api.model_info(repo, token=token)
            ok(f"{repo}\n          ({desc})")
        except Exception as e:
            nome_erro = type(e).__name__
            if "Gated" in nome_erro or "403" in str(e):
                falha(
                    f"{repo} - acesso não liberado",
                    f"Abra https://huggingface.co/{repo}\n"
                    "logado na MESMA conta do token, e aceite os termos.",
                )
            else:
                falha(f"{repo} - {nome_erro}", str(e)[:160])


def main():
    _sistema()
    _pacotes()
    _apple_silicon()
    _acesso_aos_modelos(_token())

    print("\n" + "=" * 64)
    if ok_geral:
        print("Ambiente pronto. Próximo passo:\n")
        print("  ffmpeg -ss 600 -t 300 -i reuniao.m4a teste5min.m4a")
        print("  python ferramentas/fase0.py teste5min.m4a --esperado 4")
    else:
        print("Resolva os itens marcados como FALHOU antes de continuar.")
    print()
    sys.exit(0 if ok_geral else 1)


if __name__ == "__main__":
    main()
