"""
tests/servidor_apoio.py - Infraestrutura comum das suites do servidor
(tests/test_servidor_*.py): isola o ambiente, instala os stubs de
torch/pyannote ANTES de qualquer import do projeto e cria reunioes de
teste. NUNCA toca em audios/ nem vozes.db reais - reunioes.PASTA_AUDIOS e
nucleo.DB_PATH sao sempre redirecionados para pastas temporarias.

Importe este modulo PRIMEIRO em cada suite.
"""

import json
import subprocess
import sys
import tempfile
import types
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import _ambiente  # noqa: E402

_ambiente.isolar()

warnings.filterwarnings("ignore")


def _instalar_stubs():
    for nome in ["torch", "pyannote", "pyannote.audio", "pyannote.core", "soundfile"]:
        sys.modules.setdefault(nome, types.ModuleType(nome))
    sys.modules["torch"].device = lambda x: x
    sys.modules["pyannote.audio"].Model = object
    sys.modules["pyannote.audio"].Inference = object
    sys.modules["pyannote.core"].Segment = object


_instalar_stubs()

from fastapi.testclient import TestClient  # noqa: E402

import trama.servidor.app as app_mod  # noqa: E402
from trama import (
    nucleo,  # noqa: E402
)
from trama.servidor import glossario, reunioes  # noqa: E402

# --------------------------------------------------------------------------
# infraestrutura de teste
# --------------------------------------------------------------------------


def _ambiente_temporario():
    """
    Redireciona reunioes.PASTA_AUDIOS e nucleo.DB_PATH para uma pasta
    descartavel, e devolve (pasta, cliente) para o teste usar. NUNCA toca
    audios/ nem vozes.db reais - e o bug que aconteceu num smoke test manual
    antes desta suite existir (a rota /api/pessoas migrou o vozes.db real
    porque nucleo.DB_PATH nao tinha sido isolado).
    """
    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-servidor-"))
    reunioes.PASTA_AUDIOS = pasta / "audios"
    reunioes.PASTA_AUDIOS.mkdir()
    nucleo.DB_PATH = pasta / "vozes_teste.db"
    # termos.txt tambem: o PUT /api/termos escreve de verdade, e o real e o
    # que o pipeline.py le em toda transcricao.
    glossario.CAMINHO = pasta / "termos.txt"
    cliente = TestClient(app_mod.app)
    return pasta, cliente


def _criar_reuniao_completa(pasta_audios, id, pessoas=("Ramiro", "Amanda")):
    pasta = pasta_audios / id
    pasta.mkdir()
    clusters = {
        f"S{i}": {
            "nome": nome,
            "sim": 0.9,
            "margem": 0.5,
            "fala_s": 30.0,
            "embedding": [0.1, 0.2, 0.3],
            "scores": {},
        }
        for i, nome in enumerate(pessoas)
    }
    dados = {
        "reuniao_id": f"uuid-{id}",
        "clusters": clusters,
        "falas": [
            {"falante": pessoas[0], "cluster": "S0", "inicio": 0.0, "fim": 42.0, "texto": "Ola."}
        ],
        "turnos": [[0.0, 42.0, "S0"]],
        "dinamica": {
            pessoas[0]: {"fala_s": 42.0, "fala_pct": 70.0},
            pessoas[1]: {"fala_s": 18.0, "fala_pct": 30.0},
        },
        "matriz_interrupcoes": {},
        "eventos": [],
        "regioes_sobrepostas": [],
    }
    (pasta / f"{id}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return pasta


def _criar_audio_real(caminho, duracao_s=2):
    """Gera um .m4a curto de verdade (tom senoidal) via ffmpeg lavfi -
    para testar recortar_audio() com o binario real, nao um mock, do mesmo
    jeito que o resto da suite testa as funcoes reais."""
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duracao_s}",
            "-c:a",
            "aac",
            str(caminho),
        ],
        stdin=subprocess.DEVNULL,
        check=True,
        timeout=30,
    )


def _criar_reuniao_incompleta(pasta_audios, id):
    """Schema antigo: so audio/wav16k/clusters/falas, como reuniao_01/03/05
    de producao - sem turnos nem dinamica."""
    pasta = pasta_audios / id
    pasta.mkdir()
    dados = {
        "audio": str(pasta / f"{id}.m4a"),
        "clusters": {
            "S0": {
                "nome": "DESCONHECIDO_S0",
                "sim": 0.1,
                "margem": 0.0,
                "fala_s": 10.0,
                "embedding": [0.0],
                "scores": {},
            }
        },
        "falas": [
            {
                "falante": "DESCONHECIDO_S0",
                "cluster": "S0",
                "inicio": 0.0,
                "fim": 10.0,
                "texto": "Oi.",
            }
        ],
    }
    (pasta / f"{id}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return pasta


def _criar_reuniao_nao_processada(pasta_audios, id, tamanho_bytes=1000):
    pasta = pasta_audios / id
    pasta.mkdir()
    (pasta / f"{id}.m4a").write_bytes(b"\x00" * tamanho_bytes)
    return pasta


def rodar_suite(escopo):
    """Runner das suites sem pytest: roda cada test_* de `escopo`."""
    testes = [(n, f) for n, f in sorted(escopo.items()) if n.startswith("test_") and callable(f)]
    falhas = []
    for nome, fn in testes:
        try:
            fn()
            print(f"  \033[92mPASSOU\033[0m  {nome}")
        except AssertionError as e:
            falhas.append(nome)
            print(f"  \033[91mFALHOU\033[0m  {nome}\n            {e}")
        except Exception as e:
            falhas.append(nome)
            print(f"  \033[91mERRO\033[0m    {nome}\n            {type(e).__name__}: {e}")
    print(f"\n{len(testes) - len(falhas)}/{len(testes)} passaram")
    return 1 if falhas else 0
