"""
servidor/processamento.py - dispara e acompanha o pipeline.py de verdade
(marco 2, etapa 2). Casca fina (ADR 0004): so orquestra o SUBPROCESS do
pipeline.py, nunca reimplementa nada da logica do pipeline.

Por que subprocess e nao import: um crash do pipeline (driver de GPU,
out-of-memory) mata o subprocess, nunca o servidor - o resto do app
continua respondendo. E a mesma chamada que um humano digitaria no
terminal, so trocando quem aperta enter.

Como o progresso e lido: pipeline.py imprime "N/5  <texto>..." no stdout, ja
hoje, para quem roda pela CLI. Uma thread do servidor le essas linhas
(com -u no subprocess, sem isso o stdout redirecionado para um pipe fica
em buffer de bloco e as linhas so sairiam todas juntas no final) e
atualiza um estado compartilhado em memoria - nunca deixa a leitura do
stdout presa a uma conexao SSE (so pode haver UM leitor do pipe).

Um processamento por vez (o cliente vai rodar isto numa maquina pior que
a de desenvolvimento - dois pipeline.py ao mesmo tempo disputam GPU e
memoria): um lock global e um unico slot de estado.

Sobrevivencia a reinicio do servidor: um arquivo de marcacao e gravado na
pasta da propria reuniao quando o processamento comeca e apagado quando
termina (sucesso, erro OU cancelamento). Se o servidor cair e subir de
novo, o marcador sobra sem ninguem cuidando dele - servidor/reunioes.py
cruza a EXISTENCIA do marcador com o estado em memoria (que comeca vazio
a cada reinicio) para reportar "interrompido" em vez de fingir
"nao_processada" (a reuniao foi tentada, nao e a fila normal) ou
"completa" (nao tem .json nenhum). E a versao barata: nao tenta
readotar o processo antigo, so marca a interrupcao com honestidade.
"""

import importlib.util
import json
import os
import platform
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from trama import erros

RAIZ = Path(__file__).resolve().parents[2]
# Modulo do pipeline rodado como subprocess (python -m, com cwd=RAIZ).
MODULO_PROCESSAR = "trama.cli.processar"

NOME_MARCADOR = ".processando.json"

_PADRAO_ETAPA = re.compile(r"^(\d)/5\s+(.+?)\.*$")

# O que o pipeline acrescenta ao texto fixo de uma etapa (pipeline.py:
# descrever_faixa na 2, motor e termos na 5) vira DADO, nunca frase: a tela
# monta o texto no idioma dela (i18n/*/processamento.ts). O stdout e
# portugues de linha de comando; so os numeros e o nome do motor saem dele.
_FALANTES = re.compile(r" - (\d+) falantes\b")
_ENTRE = re.compile(r" - entre (\d+) e (\d+) falantes\b")
_PELO_MENOS = re.compile(r" - pelo menos (\d+) falantes\b")
_ATE = re.compile(r" - até (\d+) falantes\b")
_MOTOR = re.compile(r"\bcom (\w+)")
_TERMOS = re.compile(r"\((\d+) termos do dominio\)")


def detalhe_da_etapa(texto):
    """{falantes | min, max | asr, termos} do texto de uma etapa; {} quando
    a etapa nao tem nada alem do texto fixo."""
    detalhe = {}
    if m := _FALANTES.search(texto):
        detalhe["falantes"] = int(m.group(1))
    elif m := _ENTRE.search(texto):
        detalhe["min"], detalhe["max"] = int(m.group(1)), int(m.group(2))
    elif m := _PELO_MENOS.search(texto):
        detalhe["min"] = int(m.group(1))
    elif m := _ATE.search(texto):
        detalhe["max"] = int(m.group(1))
    if texto.startswith("Transcrevendo") and (m := _MOTOR.search(texto)):
        detalhe["asr"] = m.group(1)
        if t := _TERMOS.search(texto):
            detalhe["termos"] = int(t.group(1))
    return detalhe


_trava = threading.Lock()
_estado = None  # None quando ocioso; dict enquanto ha (ou houve) trabalho


class JaEmProcessamento(RuntimeError):
    """Ja existe uma reuniao sendo processada - so uma por vez (GPU e
    memoria da maquina do cliente nao aguentam duas)."""


class NadaParaCancelar(RuntimeError):
    """Pediu para cancelar uma reuniao que nao esta rodando agora."""


def detectar_device_e_asr():
    """
    mlx (Apple Silicon, via MPS) e mais rapido aqui, mas a maquina do
    cliente pode nao ser um Mac com chip Apple - mlx_whisper nem importa
    em outro hardware. Detecta em vez de fixar: MPS disponivel usa
    mps+mlx (o par que o desenvolvimento usa); senao cai para cpu+faster
    (funciona em qualquer maquina).
    """
    # Sem importar torch: carregar o torch inteiro so para perguntar "e
    # Apple Silicon?" custava segundos na primeira chamada de /api/sistema.
    # MPS existe em todo Mac com chip Apple; mlx_whisper so instala nele.
    apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"
    if apple_silicon and importlib.util.find_spec("mlx_whisper") is not None:
        return "mps", "mlx"
    return "cpu", "faster"


def _caminho_marcador(pasta):
    return Path(pasta) / NOME_MARCADOR


def ler_marcador(pasta):
    """None se nao ha marcador ou se o arquivo estiver corrompido (nao
    trava a leitura de estado por causa de um marcador ilegivel - nesse
    caso o mais seguro e agir como se ele nao existisse)."""
    caminho = _caminho_marcador(pasta)
    if not caminho.exists():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _escrever_marcador(pasta, conteudo):
    _caminho_marcador(pasta).write_text(json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")


def _apagar_marcador(pasta):
    _caminho_marcador(pasta).unlink(missing_ok=True)


def estado_atual():
    """Copia serializavel do trabalho atual (ou None) - nunca devolve o
    dict interno direto (tem o Popen e a Thread, que ninguem de fora
    deveria tocar nem serializar)."""
    with _trava:
        if _estado is None:
            return None
        return {k: v for k, v in _estado.items() if k not in ("processo", "thread")}


def _acompanhar(id, pasta, processo):
    """
    Roda numa thread separada: le o stdout do subprocess linha a linha
    (o UNICO leitor - SSE nunca le o pipe direto, so este estado
    compartilhado) e atualiza a etapa atual. Ao terminar, decide
    concluido/erro/cancelado pelo codigo de saida (nunca por procurar
    "Pronto:" no texto - o codigo de saida e o sinal correto do SO) e
    apaga o marcador: o servidor viu o fim com os proprios olhos, entao
    nao e mais uma interrupcao sem explicacao.
    """
    global _estado

    for linha in processo.stdout:
        m = _PADRAO_ETAPA.match(linha.strip())
        if m:
            with _trava:
                if _estado is not None and _estado["reuniao_id"] == id:
                    _estado["etapa"] = int(m.group(1))
                    _estado["detalhe"] = detalhe_da_etapa(m.group(2).strip())

    codigo = processo.wait()

    with _trava:
        if _estado is None or _estado["reuniao_id"] != id:
            return  # outro job ja assumiu o slot - nada a atualizar aqui
        if _estado.get("cancelado"):
            _estado["status"] = "cancelado"
        elif codigo == 0:
            _estado["status"] = "concluido"
            _estado["etapa"] = 5
        else:
            _estado["status"] = "erro"
            _estado["erro"] = erros.aviso("processamento_falhou")
            print(f"[processamento] {id} falhou, codigo {codigo}")

    _apagar_marcador(pasta)


def iniciar(id, pasta, caminho_audio, pessoas):
    """
    Dispara o pipeline.py de verdade como subprocess. Levanta JaEmProcessamento
    se ja houver um trabalho "rodando" - checagem e escrita do estado sob
    a MESMA trava, para duas chamadas simultaneas nunca passarem as duas.

    `pessoas` fica guardado no estado (nao so passado para o comando) para
    a tela de "tentar novamente" depois de uma falha poder reenviar as
    MESMAS pessoas sem pedir de novo - sem isso, um retry perderia essa
    escolha silenciosamente.
    """
    global _estado

    device, asr = detectar_device_e_asr()

    with _trava:
        if _estado is not None and _estado["status"] == "rodando":
            raise JaEmProcessamento(_estado["reuniao_id"])

        comando = [
            sys.executable,
            "-u",
            "-m",
            MODULO_PROCESSAR,
            str(caminho_audio),
            "--device",
            device,
            "--asr",
            asr,
        ]
        if pessoas:
            comando += ["--pessoas", ",".join(pessoas)]

        processo = subprocess.Popen(
            comando,
            cwd=str(RAIZ),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        _escrever_marcador(
            pasta,
            {
                "pid": processo.pid,
                "iniciado_em": time.time(),
                "device": device,
                "asr": asr,
            },
        )

        _estado = {
            "reuniao_id": id,
            "processo": processo,
            "etapa": 0,
            "total_etapas": 5,
            "detalhe": {},
            "status": "rodando",
            "erro": None,
            "iniciado_em": time.time(),
            "device": device,
            "asr": asr,
            "pessoas": pessoas,
            "cancelado": False,
        }
        thread = threading.Thread(target=_acompanhar, args=(id, pasta, processo), daemon=True)
        _estado["thread"] = thread
        thread.start()


def cancelar(id):
    """
    Pede para o subprocess terminar (SIGTERM - da chance de sair limpo)
    e marca o job como cancelado. Nao apaga o audio nem a pasta: o
    principio e o mesmo de uma falha (ver decisao registrada em
    ARCHITECTURE.md) - o usuario pode tentar de novo sem subir o arquivo
    outra vez. So a marcacao de "em andamento" e removida (pela propria
    thread de acompanhamento, quando o processo terminar de verdade).
    """
    with _trava:
        if _estado is None or _estado["reuniao_id"] != id or _estado["status"] != "rodando":
            raise NadaParaCancelar(id)
        _estado["cancelado"] = True
        processo = _estado["processo"]
    processo.terminate()


def verificar_marcadores_orfaos(pasta_audios):
    """
    Roda uma vez, na inicializacao do servidor. So um best-effort: tenta
    encerrar qualquer processo cujo PID esteja num marcador sobrando (o
    servidor reiniciou, ninguem mais esta lendo o stdout daquele
    subprocess mesmo que ele ainda exista). Nunca falha a inicializacao
    do servidor por causa disto - so avisa no log.

    NAO precisa apagar o marcador nem reescrever nada: e a mera
    EXISTENCIA do marcador, cruzada com o estado em memoria (vazio logo
    apos religar), que faz servidor/reunioes.py reportar "interrompido" -
    ver _estado_e_acao_sem_json.
    """
    if not Path(pasta_audios).is_dir():
        return
    for pasta in Path(pasta_audios).iterdir():
        marcador = ler_marcador(pasta)
        if marcador is None:
            continue
        pid = marcador.get("pid")
        if pid is None:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            print(
                f"[processamento] encerrado processo orfao (pid {pid}) encontrado em {pasta.name}"
            )
        except ProcessLookupError:
            pass  # ja nao existia - nada a fazer
        except OSError as exc:
            print(
                f"[processamento] falha ao encerrar pid {pid} em {pasta.name}: {type(exc).__name__}"
            )
