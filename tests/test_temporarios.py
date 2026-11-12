"""
tests/test_temporarios.py - A varredura das copias WAV orfas
(trama/temporarios.py): o que ela apaga e o que ela nunca toca. Roda na
pasta temporaria propria desta execucao (_ambiente.isolar), nunca na do
sistema.

Uso:
    python tests/test_temporarios.py
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ambiente  # noqa: E402

_ambiente.isolar()

from servidor_apoio import rodar_suite  # noqa: E402

from trama import temporarios  # noqa: E402


def _pid_morto():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _copia(pasta, nome="reuniao_01_16k.wav", tamanho=1000):
    (pasta / nome).write_bytes(b"\0" * tamanho)


def test_criar_e_apagar_a_propria_pasta():
    pasta = temporarios.criar_pasta()
    assert pasta.parent.resolve() == Path(tempfile.gettempdir()).resolve()
    assert (pasta / temporarios.ARQUIVO_DONO).read_text() == str(os.getpid())
    _copia(pasta)
    assert temporarios.apagar(pasta) > 1000 - 1
    assert not pasta.exists()


def test_apagar_nunca_toca_pasta_que_nao_e_nossa():
    alheia = Path(tempfile.mkdtemp(prefix="outra-"))
    _copia(alheia)
    assert temporarios.apagar(alheia) == 0 and alheia.exists()
    assert temporarios.apagar(None) == 0


def test_varredura_apaga_so_as_orfas():
    raiz = Path(tempfile.gettempdir())
    viva = temporarios.criar_pasta()  # dono: este processo, vivo
    _copia(viva)
    morta = Path(tempfile.mkdtemp(prefix=temporarios.PREFIXO))
    pid_morto = str(_pid_morto())
    (morta / temporarios.ARQUIVO_DONO).write_text(pid_morto)
    _copia(morta, tamanho=500)
    recem_criada = Path(tempfile.mkdtemp(prefix=temporarios.PREFIXO))  # sem dono ainda
    sem_dono_velha = Path(tempfile.mkdtemp(prefix=temporarios.PREFIXO))
    velho = time.time() - 3600
    os.utime(sem_dono_velha, (velho, velho))
    antiga = Path(tempfile.mkdtemp())  # formato antigo: tmpXXXX/<nome>_16k.wav
    _copia(antiga, "reuniao_11_16k.wav", tamanho=300)
    antiga_com_mais = Path(tempfile.mkdtemp())
    _copia(antiga_com_mais)
    (antiga_com_mais / "outra_coisa.txt").write_text("x")
    alheia = Path(tempfile.mkdtemp())
    (alheia / "audio.wav").write_bytes(b"x")

    quantas, total = temporarios.limpar_orfas()

    # 500 + 300 das copias, mais o arquivo do dono da pasta orfa
    assert (quantas, total) == (3, 800 + len(pid_morto)), (quantas, total)
    assert not morta.exists() and not antiga.exists() and not sem_dono_velha.exists()
    for fica in (viva, recem_criada, antiga_com_mais, alheia):
        assert fica.exists(), fica
    assert {p.name for p in raiz.iterdir()} >= {viva.name, alheia.name}
    temporarios.apagar(viva)


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
