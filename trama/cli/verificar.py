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

from trama.idioma import t

REPOS = [
    ("pyannote/speaker-diarization-community-1", "modelo_diarizacao"),
    ("pyannote/wespeaker-voxceleb-resnet34-LM", "modelo_embedding"),
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
    print(f"  \033[92m{t('rotulo_ok'):<7}\033[0m {msg}")


def falha(msg, dica=""):
    global ok_geral
    ok_geral = False
    print(f"  \033[91m{t('rotulo_falhou'):<7}\033[0m {msg}")
    if dica:
        for linha in dica.strip().splitlines():
            print(f"          {linha}")


def aviso(msg):
    print(f"  \033[93m{t('rotulo_aviso'):<7}\033[0m {msg}")


def _sistema():
    print(t("secao_sistema"))
    versao = f"Python {sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info < (3, 12):
        falha(versao, t("python_antigo"))
    else:
        ok(versao)

    if shutil.which("ffmpeg"):
        ok(t("ffmpeg_ok"))
    else:
        falha(t("ffmpeg_falta"), "brew install ffmpeg")

    if shutil.which("ffprobe"):
        ok(t("ffprobe_ok"))
    else:
        aviso(t("ffprobe_falta"))

    if sys.prefix == sys.base_prefix:
        aviso(t("sem_venv"))


def _pacotes():
    print(t("secao_pacotes"))
    for modulo, nome in PACOTES:
        try:
            m = importlib.import_module(modulo)
            ok(f"{nome} {getattr(m, '__version__', '?')}")
        except ImportError:
            falha(t("nao_instalado", nome=nome), 'pip install -e ".[dev]"')

    try:
        import pyannote.audio as pa

        v = getattr(pa, "__version__", "0")
        if v != "?" and int(str(v).split(".")[0]) < 4:
            falha(t("pyannote_antigo", versao=v), t("pyannote_dica"))
    except Exception:
        pass

    # Transcricao: qualquer um dos dois serve
    tem_asr = False
    for mod, flag in [("mlx_whisper", "--asr mlx"), ("faster_whisper", "--asr faster")]:
        try:
            importlib.import_module(mod)
            ok(t("asr_ok", modulo=mod, flag=flag))
            tem_asr = True
        except ImportError:
            pass
    if not tem_asr:
        aviso(t("sem_asr"))


def _apple_silicon():
    print(t("secao_apple"))
    try:
        import torch

        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            ok(t("mps_ok"))
        else:
            aviso(t("mps_falta"))
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
    print(t("secao_token"))
    token, origem = os.environ.get("HF_TOKEN"), t("token_da_variavel")
    if not token:
        token, origem = _token_do_cache(), t("token_do_cache")

    if not token:
        falha(t("sem_token"), t("sem_token_dica"))
        return None
    if not token.startswith("hf_"):
        aviso(t("token_formato"))
    ok(t("token_presente", origem=origem, fim=token[-4:]))

    try:
        from huggingface_hub import HfApi

        me = HfApi().whoami(token=token)
        ok(t("autenticado", nome=me.get("name", "?")))
    except Exception as e:
        falha(t("token_invalido", erro=type(e).__name__), t("token_novo"))
    return token


def _acesso_aos_modelos(token):
    print(t("secao_modelos"))
    if not token:
        aviso(t("sem_token_modelos"))
        return
    from huggingface_hub import HfApi

    api = HfApi()
    for repo, desc in REPOS:
        try:
            api.model_info(repo, token=token)
            ok(f"{repo}\n          ({t(desc)})")
        except Exception as e:
            nome_erro = type(e).__name__
            if "Gated" in nome_erro or "403" in str(e):
                falha(t("acesso_negado", repo=repo), t("acesso_dica", repo=repo))
            else:
                falha(f"{repo} - {nome_erro}", str(e)[:160])


def main():
    _sistema()
    _pacotes()
    _apple_silicon()
    _acesso_aos_modelos(_token())

    print("\n" + "=" * 64)
    if ok_geral:
        print(t("ambiente_pronto"))
        print("  ffmpeg -ss 600 -t 300 -i reuniao.m4a teste5min.m4a")
        print("  python ferramentas/fase0.py teste5min.m4a --esperado 4")
    else:
        print(t("resolva"))
    print()
    sys.exit(0 if ok_geral else 1)


if __name__ == "__main__":
    main()
