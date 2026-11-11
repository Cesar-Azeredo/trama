"""
servidor/upload.py - POST /api/reunioes: recebe o audio, cria a pasta da
reuniao nova. So isso - nao dispara processamento. O marco 2 separa
deliberadamente as duas coisas (ver ARCHITECTURE.md): esta etapa so
valida e salva; disparar o pipeline.py e a etapa seguinte.

O nome do arquivo que o cliente manda NUNCA vira caminho - so serve para
checar a extensao contra uma lista fixa (CLAUDE.md, regra 4, a mesma
garantia que reunioes.resolver_pasta ja da para o id). O nome gravado em
disco e sempre gerado pelo servidor: reuniao_NN.<ext>.
"""

import os
import re
from pathlib import Path

from trama.erros import ErroDeUsuario

EXTENSOES_PERMITIDAS = {".m4a", ".mp3", ".wav"}

# iPhone, 72 min = ~37 MB (medido em audios/reuniao_09). 500 MB cobre uma
# gravacao de varias horas com folga generosa, sem abrir para upload
# absurdo.
TAMANHO_MAXIMO_BYTES = 500 * 1024 * 1024

TAMANHO_BLOCO = 1024 * 1024  # 1 MB por leitura/escrita - streaming, nunca
# o upload inteiro na memoria

_PADRAO_PASTA_REUNIAO = re.compile(r"^reuniao_(\d+)$")


class ExtensaoInvalida(ErroDeUsuario):
    """Nome do arquivo enviado nao termina numa extensao permitida."""


class ArquivoMuitoGrande(ErroDeUsuario):
    """
    Upload excedeu TAMANHO_MAXIMO_BYTES - abortado no MEIO do stream,
    contando bytes efetivamente escritos. Nunca confia so no
    Content-Length declarado pelo cliente, que pode mentir.
    """


def extensao_permitida(nome_original):
    sufixo = Path(nome_original or "").suffix.lower()
    return sufixo if sufixo in EXTENSOES_PERMITIDAS else None


def _maior_numero_existente(pasta_audios):
    maior = 0
    if pasta_audios.is_dir():
        for pasta in pasta_audios.iterdir():
            m = _PADRAO_PASTA_REUNIAO.fullmatch(pasta.name)
            if m:
                maior = max(maior, int(m.group(1)))
    return maior


def proximo_id(pasta_audios):
    """
    reuniao_01, reuniao_02, ... - mesma convencao ja usada em audios/. Le
    os NUMEROS das pastas existentes (nao a CONTAGEM - uma reuniao
    apagada nao pode fazer o proximo numero ser reusado) e devolve o
    seguinte.

    So um PALPITE inicial para exibir/testar - quem cria a pasta de
    verdade e _criar_pasta_exclusiva, que resolve a corrida entre duas
    requisicoes simultaneas (ver la).
    """
    return f"reuniao_{_maior_numero_existente(pasta_audios) + 1:02d}"


def _criar_pasta_exclusiva(pasta_audios):
    """
    Cria a pasta reuniao_NN, avancando para o proximo numero se a
    tentativa colidir. `Path.mkdir()` sem exist_ok e atomico no sistema
    operacional - e o que faz isto seguro sob concorrencia, nao um
    lock em Python: "ler o maior numero, decidir NN, criar a pasta" tem
    uma corrida classica (duas requisicoes simultaneas podem LER o mesmo
    maior numero antes de qualquer uma ter CRIADO a pasta, e as duas
    decidiriam o mesmo id). Aqui, quem perde a corrida do mkdir nunca
    sobrescreve a pasta da outra - so tenta o numero seguinte.
    """
    n = _maior_numero_existente(pasta_audios) + 1
    while True:
        id_tentativa = f"reuniao_{n:02d}"
        pasta = pasta_audios / id_tentativa
        try:
            pasta.mkdir()
            return id_tentativa, pasta
        except FileExistsError:
            n += 1


async def receber_upload(pasta_audios, nome_original, arquivo_upload):
    """
    Cria a pasta da reuniao nova e grava o audio em streaming.
    `arquivo_upload` e um fastapi.UploadFile (ou qualquer objeto com
    `.read(n)` assincrono).

    Grava num arquivo TEMPORARIO dentro da pasta nova e so renomeia para
    o nome final se o upload inteiro couber no limite - um upload grande
    demais ou interrompido no meio nao pode deixar uma pasta "reuniao_NN"
    pela metade ocupando esse numero (mesmo principio do ADR 0007:
    prepara tudo, troca no fim).

    Devolve o id da reuniao nova. Levanta ExtensaoInvalida antes de tocar
    disco; ArquivoMuitoGrande so depois de comecar a gravar (o tamanho
    real so se sabe lendo o corpo).
    """
    extensao = extensao_permitida(nome_original)
    if extensao is None:
        raise ExtensaoInvalida(
            "extensao_invalida", formatos=", ".join(sorted(EXTENSOES_PERMITIDAS))
        )

    pasta_audios.mkdir(parents=True, exist_ok=True)
    id_novo, pasta = _criar_pasta_exclusiva(pasta_audios)

    destino_final = pasta / f"{id_novo}{extensao}"
    destino_temp = pasta / f"{id_novo}{extensao}.parcial"

    total = 0
    try:
        with open(destino_temp, "wb") as f:
            while True:
                bloco = await arquivo_upload.read(TAMANHO_BLOCO)
                if not bloco:
                    break
                total += len(bloco)
                if total > TAMANHO_MAXIMO_BYTES:
                    raise ArquivoMuitoGrande(
                        "arquivo_grande_demais", maximo_mb=TAMANHO_MAXIMO_BYTES // (1024 * 1024)
                    )
                f.write(bloco)
        os.replace(destino_temp, destino_final)
    except BaseException:
        destino_temp.unlink(missing_ok=True)
        try:
            pasta.rmdir()  # so remove se ficou vazia - nunca rmtree aqui
        except OSError:
            pass
        raise

    return id_novo
