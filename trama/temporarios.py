"""
temporarios.py - A copia WAV 16 kHz que o pipeline faz do audio da
reuniao (nucleo.to_wav16k), na pasta temporaria do sistema.

E o mesmo audio da reuniao, entao nao pode ficar para tras. Antes ficava:
cada processamento deixava uma pasta tmpXXXX/<nome>_16k.wav, e nada a
apagava (1474 copias, 0,66 GB, medido em 2026-11-12 - 7 de reunioes reais,
o resto do audio de teste da suite do pipeline).

Agora:
  - o pipeline cria a pasta com prefixo proprio (PREFIXO) e grava nela o
    PID do processo dono; apaga a pasta ao terminar, com sucesso ou falha
    (cancelamento: o SIGTERM vira saida normal em trama/cli/processar.py,
    para o finally rodar);
  - o servidor varre as orfas (limpar_orfas) ao terminar cada
    processamento e ao iniciar: pasta cujo dono ja morreu (SIGKILL, queda
    da maquina), e as do formato antigo.

Nada daqui escreve nome de arquivo no log - so contagem e tamanho.
"""

import os
import shutil
import tempfile
import time
from pathlib import Path

PREFIXO = "trama-wav-"
ARQUIVO_DONO = "dono.pid"
# Pasta sem o arquivo do dono: pode ser um pipeline entre criar a pasta e
# gravar o PID. So e orfa depois disto.
IDADE_MIN_SEM_DONO_S = 60.0


def _raiz():
    return Path(tempfile.gettempdir()).resolve()


def criar_pasta():
    """Pasta nova para a copia WAV deste processo, com o PID dele dentro."""
    pasta = Path(tempfile.mkdtemp(prefix=PREFIXO))
    (pasta / ARQUIVO_DONO).write_text(str(os.getpid()), encoding="ascii")
    return pasta


def _e_nossa(pasta):
    """So pasta direto dentro da pasta temporaria, com o nosso prefixo."""
    try:
        pasta = Path(pasta).resolve()
    except OSError:
        return False
    return pasta.parent == _raiz() and pasta.name.startswith(PREFIXO)


def _tamanho(pasta):
    total = 0
    for f in pasta.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def apagar(pasta):
    """Apaga a pasta de copia WAV - so se for uma nossa. Devolve os bytes."""
    if pasta is None or not _e_nossa(pasta):
        return 0
    pasta = Path(pasta)
    tamanho = _tamanho(pasta)
    shutil.rmtree(pasta, ignore_errors=True)
    return 0 if pasta.exists() else tamanho


def _processo_vivo(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existe, de outro usuario
    except OSError:
        return False
    return True


def _orfa(pasta, agora):
    dono = pasta / ARQUIVO_DONO
    try:
        pid = int(dono.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        try:
            return agora - pasta.stat().st_mtime > IDADE_MIN_SEM_DONO_S
        except OSError:
            return False
    return not _processo_vivo(pid)


def _do_formato_antigo(pasta):
    """tmpXXXX/<nome>_16k.wav e nada mais: o que to_wav16k criava sozinho."""
    if not pasta.name.startswith("tmp"):
        return False
    try:
        itens = list(pasta.iterdir())
    except OSError:
        return False
    return len(itens) == 1 and itens[0].is_file() and itens[0].name.endswith("_16k.wav")


def limpar_orfas():
    """Apaga as copias WAV sem dono vivo. Devolve (quantas, bytes)."""
    raiz, agora = _raiz(), time.time()
    quantas = total = 0
    try:
        candidatas = [p for p in raiz.iterdir() if p.is_dir() and not p.is_symlink()]
    except OSError:
        return 0, 0
    for pasta in candidatas:
        if pasta.name.startswith(PREFIXO):
            if not _orfa(pasta, agora):
                continue
        elif not _do_formato_antigo(pasta):
            continue
        tamanho = _tamanho(pasta)
        shutil.rmtree(pasta, ignore_errors=True)
        if not pasta.exists():
            quantas += 1
            total += tamanho
    return quantas, total
