"""
tests/test_servidor_processo.py - Servidor de verdade (trama-servidor) e processamento em subprocess.

Parte das suites do servidor FastAPI (trama/servidor/, ADR 0004); a
infraestrutura comum esta em tests/servidor_apoio.py.

Uso:
    python tests/test_servidor_processo.py
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import servidor_apoio  # noqa: F401 - isola o ambiente e instala os stubs ANTES do projeto
from servidor_apoio import (
    RAIZ,
    _ambiente_temporario,
    _criar_reuniao_nao_processada,
    erro_de,
    rodar_suite,
)

from trama.servidor import processamento, reunioes

# ==========================================================================
# invocacao real ('trama-servidor'), nao import de modulo
# ==========================================================================


def _porta_efemera():
    """
    Porta livre escolhida pelo SO (bind na 0). Os testes que sobem
    'trama-servidor' de verdade nunca usam a 8000 fixa: com o
    Trama real rodando (o uso normal de quem desenvolve), a 8000 esta
    ocupada - um teste falhava por isso, e o outro podia passar FALSO,
    respondido pelo servidor real em vez do processo sob teste.

    Ha uma janela minima entre fechar este socket e o processo filho
    fazer o bind dele; aceitavel para teste local.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_servidor_roda_como_script_a_partir_da_raiz_sem_pythonpath():
    """
    REGRESSAO relatada: 'trama-servidor' a partir da raiz do
    projeto falhava com "ModuleNotFoundError: No module named 'core'".
    Python poe o DIRETORIO DO SCRIPT (servidor/) em sys.path[0] quando o
    script e chamado por caminho, nao a raiz do projeto - "import core"
    (que mora na raiz) nao era encontrado sem PYTHONPATH=. na frente, o
    que nao e aceitavel para um comando que precisa funcionar sem truque.

    Todo o RESTO desta suite importa servidor.app como MODULO
    ("import servidor.app as app_mod") - isso NAO pega essa classe de
    erro, porque nesse caso o proprio processo de teste ja tem a raiz em
    sys.path por outro motivo (o sys.path.insert no topo deste arquivo).
    So sobe o processo de verdade, exatamente como o usuario roda na mao
    ("trama-servidor"), pega isso.

    Isolado de audios/ e vozes.db reais via env var, mesmo sendo so
    leitura - o processo real nao tem os stubs de torch/pyannote desta
    suite, entao ele importa o nucleo.py de verdade.
    """
    pasta = Path(tempfile.mkdtemp(prefix="trama-test-subprocess-"))
    (pasta / "audios").mkdir()
    porta = _porta_efemera()
    ambiente = {
        **os.environ,
        "TRAMA_AUDIOS": str(pasta / "audios"),
        "VOZES_DB": str(pasta / "vozes_teste.db"),
        "TRAMA_PORTA": str(porta),
    }
    processo = subprocess.Popen(
        [sys.executable, "trama/servidor/app.py"],
        cwd=str(RAIZ),
        env=ambiente,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        respondeu = False
        for _ in range(150):
            if processo.poll() is not None:
                saida = processo.stdout.read()
                raise AssertionError(
                    f"processo terminou sozinho (codigo "
                    f"{processo.returncode}) antes de responder:\n{saida}"
                )
            try:
                resp = urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/reunioes", timeout=0.5)
                assert resp.status == 200
                respondeu = True
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.2)
        assert respondeu, "servidor nao respondeu a tempo"
    finally:
        processo.terminate()
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait()
        shutil.rmtree(pasta, ignore_errors=True)


def test_servidor_porta_ocupada_avisa_em_portugues_e_nao_em_ingles():
    """
    REGRESSAO relatada: fechar a janela sem parar o servidor deixa a porta
    8000 ocupada; a proxima tentativa de 'trama-servidor' morria
    com o log em ingles do uvicorn ("ERROR: [Errno 48] ...address already
    in use") espremido entre "startup complete" e "shutdown complete" -
    parecia que o servidor tinha subido e caido sozinho, sem dizer por
    que nem o que fazer. Isso acontece toda vez que alguem fecha a janela
    sem Ctrl+C, entao precisa ser claro na primeira vez que aparece.

    Ocupa a porta com um socket cru "escutando", sem aceitar nenhuma
    conexao - de proposito, para nunca ter uma conexao ESTABELECIDA cujo
    fechamento deixaria a porta em TIME_WAIT (o SO leva de dezenas de
    segundos a minutos para liberar isso, o que faria este teste vazar
    para o proximo que tambem sobe um servidor real). Um socket
    so escutando, fechado sem nunca aceitar ninguem, libera a porta na
    hora - e o suficiente para testar o bind-check de servidor/app.py.

    Isolado de audios/ e vozes.db reais via env var, mesmo o processo
    nunca chegando a servir uma rota - ele importa nucleo.py de verdade
    (sem os stubs desta suite) so para achar a porta ocupada e sair, mas
    "so importar" nao e garantia de "nunca toca o banco real" (ver
    test_servidor_roda_como_script_a_partir_da_raiz_sem_pythonpath, que
    documenta a mesma cautela).
    """
    pasta = Path(tempfile.mkdtemp(prefix="trama-test-porta-ocupada-"))
    (pasta / "audios").mkdir()
    ambiente = {
        **os.environ,
        "TRAMA_AUDIOS": str(pasta / "audios"),
        "VOZES_DB": str(pasta / "vozes_teste.db"),
    }
    # Porta efemera (bind na 0), nunca a 8000 fixa - ver _porta_efemera.
    # Aqui o proprio ocupante escolhe a porta, sem janela de corrida.
    ocupante = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ocupante.bind(("127.0.0.1", 0))
    ocupante.listen(1)
    porta = ocupante.getsockname()[1]
    ambiente["TRAMA_PORTA"] = str(porta)
    try:
        processo = subprocess.run(
            [sys.executable, "trama/servidor/app.py"],
            cwd=str(RAIZ),
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert processo.returncode != 0, f"deveria sair com erro, saida:\n{processo.stdout}"
        assert "Já existe um servidor Trama" in processo.stdout, processo.stdout
        assert f"127.0.0.1:{porta}" in processo.stdout, processo.stdout
        assert "Errno" not in processo.stdout, (
            f"vazou o erro cru do uvicorn em vez da mensagem em portugues:\n{processo.stdout}"
        )
    finally:
        ocupante.close()
        shutil.rmtree(pasta, ignore_errors=True)


def test_servidor_porta_invalida_avisa_em_portugues():
    """
    TRAMA_PORTA existe para os testes usarem porta efemera; um valor
    errado nela (digitado a mao) tem que sair com mensagem em portugues,
    nunca o ValueError cru do int() nem o OverflowError do bind.
    """
    pasta = Path(tempfile.mkdtemp(prefix="trama-test-porta-invalida-"))
    (pasta / "audios").mkdir()
    try:
        for valor in ("abc", "0", "70000"):
            ambiente = {
                **os.environ,
                "TRAMA_AUDIOS": str(pasta / "audios"),
                "VOZES_DB": str(pasta / "vozes_teste.db"),
                "TRAMA_PORTA": valor,
            }
            processo = subprocess.run(
                [sys.executable, "trama/servidor/app.py"],
                cwd=str(RAIZ),
                env=ambiente,
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert processo.returncode != 0, processo.stdout
            assert "TRAMA_PORTA inválida" in processo.stdout, processo.stdout + processo.stderr
            assert "Traceback" not in processo.stderr, processo.stderr
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# servidor/processamento.py - pipeline.py de verdade, so que um FALSO
# ==========================================================================
#
# Testar contra o pipeline.py real levaria minutos (diarizacao + Whisper) por
# caso. Em vez disso, um "pipeline.py" de mentira e escrito numa RAIZ falsa
# (processamento.RAIZ e trocado para la) - imprime as mesmas linhas
# "N/5  texto..." e "@progresso {json}" que o real imprime (a segunda so
# com --progresso-json, como o real), e decide o
# codigo de saida por variavel de ambiente. Isso exercita o subprocess,
# a leitura de stdout e a maquina de estados de verdade - so o CONTEUDO
# do pipeline e falso, a orquestracao nao.

_FAKE_RUN_PY = """\
import os
import sys
import time

import json

etapas = [
    ("Convertendo audio para 16 kHz mono", {}),
    ("Diarizando (quem falou quando) - entre 2 e 3 falantes", {"min": 2, "max": 3}),
    ("Identificando as pessoas pela voz", {}),
    ("Analisando sobreposicao e interrupcoes", {}),
    ("Transcrevendo com mlx", {"asr": "mlx"}),
]
atraso = float(os.environ.get("FAKE_RUN_ATRASO_S", "0.02"))
# Opcional: registra os argumentos de cada execucao (uma linha JSON por
# chamada), para o teste conferir o que o servidor passou ao pipeline.py.
if os.environ.get("FAKE_RUN_ARGS"):
    import json
    with open(os.environ["FAKE_RUN_ARGS"], "a", encoding="utf-8") as f:
        f.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\\n")
# Opcional: o TRAMA_IDIOMA que o pipeline recebeu, um por execucao.
if os.environ.get("FAKE_RUN_IDIOMA"):
    with open(os.environ["FAKE_RUN_IDIOMA"], "a", encoding="utf-8") as f:
        f.write(os.environ.get("TRAMA_IDIOMA", "-") + "\\n")
maquina = "--progresso-json" in sys.argv
for i, (texto, detalhe) in enumerate(etapas, 1):
    print(f"{i}/5  {texto}...", flush=True)
    if maquina:
        print("@progresso " + json.dumps({"etapa": i, "total": 5, "detalhe": detalhe}), flush=True)
    time.sleep(atraso)
sys.exit(int(os.environ.get("FAKE_RUN_CODIGO_SAIDA", "0")))
"""


def _preparar_raiz_falsa():
    """Cria uma RAIZ com um pipeline.py falso e devolve o caminho - o chamador
    troca processamento.RAIZ por ele e restaura no finally."""
    raiz_falsa = Path(tempfile.mkdtemp(prefix="trama-test-raiz-"))
    # O servidor roda "python -m <processamento.MODULO_PROCESSAR>" com
    # cwd na RAIZ: o falso mora no mesmo caminho de modulo, com os
    # __init__.py de cada nivel do pacote.
    partes = processamento.MODULO_PROCESSAR.split(".")
    pasta = raiz_falsa
    for parte in partes[:-1]:
        pasta = pasta / parte
        pasta.mkdir()
        (pasta / "__init__.py").write_text("", encoding="utf-8")
    (pasta / f"{partes[-1]}.py").write_text(_FAKE_RUN_PY, encoding="utf-8")
    return raiz_falsa


def _esperar(condicao, timeout=5.0, intervalo=0.02):
    """Poll ate a condicao ser verdadeira ou estourar o timeout - usado
    para esperar a thread de acompanhamento reagir, sem sleep fixo
    (mais rapido quando da certo, sem flakiness quando a maquina esta
    ocupada)."""
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(intervalo)
    return False


def _ambiente_processamento():
    """Isola processamento.RAIZ (pipeline.py falso) e o estado global do
    modulo (_estado comeca sempre None) - sem isso, um teste anterior que
    deixou um job rodando vazaria para o proximo."""
    raiz_falsa = _preparar_raiz_falsa()
    processamento.RAIZ = raiz_falsa
    processamento._estado = None
    pasta_audios = Path(tempfile.mkdtemp(prefix="trama-test-audios-"))
    return raiz_falsa, pasta_audios


def _limpar_ambiente_processamento(raiz_falsa, pasta_audios):
    # Se um job ainda estiver rodando, mata para nao vazar processo entre
    # testes - nunca deixa um subprocess falso orfao rodando na maquina.
    atual = processamento.estado_atual()
    if atual and atual["status"] == "rodando":
        try:
            processamento.cancelar(atual["reuniao_id"])
        except processamento.NadaParaCancelar:
            pass
        _esperar(lambda: processamento.estado_atual()["status"] != "rodando")
    processamento._estado = None
    shutil.rmtree(raiz_falsa, ignore_errors=True)
    shutil.rmtree(pasta_audios, ignore_errors=True)


def test_iniciar_roda_de_verdade_e_atualiza_etapas_ate_concluir():
    raiz_falsa, pasta_audios = _ambiente_processamento()
    try:
        pasta = pasta_audios / "reuniao_x"
        pasta.mkdir()
        audio = pasta / "reuniao_x.m4a"
        audio.write_bytes(b"x")

        processamento.iniciar("reuniao_x", pasta, audio, ["Ana", "Bia"])

        assert _esperar(lambda: processamento.estado_atual()["status"] != "rodando", timeout=5.0), (
            "job falso nao terminou a tempo"
        )

        final = processamento.estado_atual()
        assert final["status"] == "concluido"
        assert final["etapa"] == 5
        # o detalhe da ultima etapa veio da linha de maquina, nao da frase
        assert final["detalhe"] == {"asr": "mlx"}, final["detalhe"]
        assert not (pasta / processamento.NOME_MARCADOR).exists(), (
            "marcador tem que sumir quando o servidor VIU o fim"
        )
    finally:
        _limpar_ambiente_processamento(raiz_falsa, pasta_audios)


def test_iniciar_grava_marcador_com_pid_enquanto_roda():
    raiz_falsa, pasta_audios = _ambiente_processamento()
    os.environ["FAKE_RUN_ATRASO_S"] = "0.3"
    try:
        pasta = pasta_audios / "reuniao_x"
        pasta.mkdir()
        audio = pasta / "reuniao_x.m4a"
        audio.write_bytes(b"x")

        processamento.iniciar("reuniao_x", pasta, audio, [])

        marcador = processamento.ler_marcador(pasta)
        assert marcador is not None
        assert isinstance(marcador["pid"], int)
    finally:
        del os.environ["FAKE_RUN_ATRASO_S"]
        _limpar_ambiente_processamento(raiz_falsa, pasta_audios)


def test_iniciar_com_outro_job_rodando_recusa():
    raiz_falsa, pasta_audios = _ambiente_processamento()
    os.environ["FAKE_RUN_ATRASO_S"] = "0.3"
    try:
        pasta_a = pasta_audios / "reuniao_a"
        pasta_a.mkdir()
        (pasta_a / "reuniao_a.m4a").write_bytes(b"x")
        pasta_b = pasta_audios / "reuniao_b"
        pasta_b.mkdir()
        (pasta_b / "reuniao_b.m4a").write_bytes(b"x")

        processamento.iniciar("reuniao_a", pasta_a, pasta_a / "reuniao_a.m4a", [])
        try:
            processamento.iniciar("reuniao_b", pasta_b, pasta_b / "reuniao_b.m4a", [])
            assert False, "deveria ter recusado - ja tem um job rodando"
        except processamento.JaEmProcessamento as exc:
            assert "reuniao_a" in str(exc)
    finally:
        del os.environ["FAKE_RUN_ATRASO_S"]
        _limpar_ambiente_processamento(raiz_falsa, pasta_audios)


def test_subprocess_com_erro_marca_status_erro_em_portugues_e_apaga_marcador():
    raiz_falsa, pasta_audios = _ambiente_processamento()
    os.environ["FAKE_RUN_CODIGO_SAIDA"] = "1"
    try:
        pasta = pasta_audios / "reuniao_x"
        pasta.mkdir()
        audio = pasta / "reuniao_x.m4a"
        audio.write_bytes(b"x")

        processamento.iniciar("reuniao_x", pasta, audio, [])
        assert _esperar(lambda: processamento.estado_atual()["status"] != "rodando")

        final = processamento.estado_atual()
        assert final["status"] == "erro"
        assert final["erro"] == {"codigo": "processamento_falhou", "parametros": {}}
        assert not (pasta / processamento.NOME_MARCADOR).exists()
        # audio continua no disco - tentar de novo nao pede novo upload
        assert audio.exists()
    finally:
        del os.environ["FAKE_RUN_CODIGO_SAIDA"]
        _limpar_ambiente_processamento(raiz_falsa, pasta_audios)


def test_cancelar_mata_o_processo_mantem_audio_e_apaga_marcador():
    raiz_falsa, pasta_audios = _ambiente_processamento()
    os.environ["FAKE_RUN_ATRASO_S"] = "5.0"  # bem mais que o teste precisa
    try:
        pasta = pasta_audios / "reuniao_x"
        pasta.mkdir()
        audio = pasta / "reuniao_x.m4a"
        audio.write_bytes(b"conteudo original")

        processamento.iniciar("reuniao_x", pasta, audio, [])
        assert _esperar(lambda: processamento.ler_marcador(pasta) is not None)

        processamento.cancelar("reuniao_x")
        assert _esperar(lambda: processamento.estado_atual()["status"] != "rodando", timeout=5.0), (
            "processo nao morreu a tempo do SIGTERM"
        )

        assert processamento.estado_atual()["status"] == "cancelado"
        assert not (pasta / processamento.NOME_MARCADOR).exists()
        assert audio.read_bytes() == b"conteudo original", (
            "cancelar nao pode apagar o audio - mesmo principio de uma "
            "falha, tentar de novo nao pode pedir novo upload"
        )
    finally:
        del os.environ["FAKE_RUN_ATRASO_S"]
        _limpar_ambiente_processamento(raiz_falsa, pasta_audios)


def test_cancelar_sem_nada_rodando_leventa_nada_para_cancelar():
    raiz_falsa, pasta_audios = _ambiente_processamento()
    try:
        try:
            processamento.cancelar("reuniao_qualquer")
            assert False, "deveria ter levantado NadaParaCancelar"
        except processamento.NadaParaCancelar:
            pass
    finally:
        _limpar_ambiente_processamento(raiz_falsa, pasta_audios)


def test_ler_marcador_ausente_e_corrompido_devolvem_none():
    pasta = Path(tempfile.mkdtemp())
    try:
        assert processamento.ler_marcador(pasta) is None
        (pasta / processamento.NOME_MARCADOR).write_text("{nao e json valido")
        assert processamento.ler_marcador(pasta) is None
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_verificar_marcadores_orfaos_mata_processo_vivo_e_ignora_morto():
    """
    REGRESSAO do cenario que motivou o marcador: servidor reinicia com um
    pipeline.py orfao ainda rodando (ou ja morto) por tras. So um best-effort -
    nunca levanta excecao, mesmo com PID invalido ou morto.
    """
    pasta_audios = Path(tempfile.mkdtemp())
    try:
        # processo de verdade, de vida curta, so para ter um PID vivo
        processo_vivo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            pasta_a = pasta_audios / "reuniao_a"
            pasta_a.mkdir()
            (pasta_a / processamento.NOME_MARCADOR).write_text(
                json.dumps({"pid": processo_vivo.pid})
            )

            pasta_b = pasta_audios / "reuniao_b"
            pasta_b.mkdir()
            (pasta_b / processamento.NOME_MARCADOR).write_text(
                json.dumps({"pid": 999999999})
            )  # pid que nao existe

            processamento.verificar_marcadores_orfaos(pasta_audios)

            assert _esperar(lambda: processo_vivo.poll() is not None), (
                "processo vivo deveria ter sido encerrado (SIGTERM)"
            )
        finally:
            processo_vivo.kill()
            processo_vivo.wait()
    finally:
        shutil.rmtree(pasta_audios, ignore_errors=True)


# ==========================================================================
# rotas: POST /processar, POST /cancelar, GET /progresso
# ==========================================================================


def test_rota_processar_dispara_o_job_e_reuniao_aparece_processando():
    pasta, cliente = _ambiente_temporario()
    raiz_falsa = _preparar_raiz_falsa()
    processamento.RAIZ = raiz_falsa
    processamento._estado = None
    os.environ["FAKE_RUN_ATRASO_S"] = "0.3"
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_a")

        r = cliente.post("/api/reunioes/reuniao_a/processar", json={"pessoas": ["Ana"]})
        assert r.status_code == 202, r.text

        r2 = cliente.get("/api/reunioes/reuniao_a")
        assert r2.json()["estado"] == "processando"
        assert r2.json()["acao_processar"]["disponivel"] is False

        assert _esperar(lambda: processamento.estado_atual()["status"] != "rodando")
    finally:
        del os.environ["FAKE_RUN_ATRASO_S"]
        _limpar_ambiente_processamento(raiz_falsa, reunioes.PASTA_AUDIOS)
        shutil.rmtree(pasta, ignore_errors=True)


def test_tentar_de_novo_usa_as_mesmas_pessoas_da_primeira_vez():
    """
    Marco 2, etapa 4: depois de uma falha, "Tentar novamente"
    (frontend/src/telas/ProcessamentoReuniao.tsx) reenvia as pessoas que
    o PROGRESSO devolveu - nao pergunta de novo. Sem "pessoas" no estado
    do processamento, o evento de progresso nao as trazia e a segunda
    tentativa ia sem --pessoas, em silencio: o maior ganho de precisao do
    pipeline perdido sem ninguem ver.

    Faz o caminho inteiro pela API, como a tela: processa com pessoas, o
    pipeline.py falha, le o evento final do SSE, reenvia o que ele trouxe, e
    confere que o pipeline.py recebeu as MESMAS pessoas nas duas vezes.
    """
    pasta, cliente = _ambiente_temporario()
    raiz_falsa = _preparar_raiz_falsa()
    processamento.RAIZ = raiz_falsa
    processamento._estado = None
    args = pasta / "args_do_run.txt"
    os.environ["FAKE_RUN_ARGS"] = str(args)
    os.environ["FAKE_RUN_CODIGO_SAIDA"] = "1"
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_a")
        pessoas = ["Amanda", "Celso", "Clélia"]

        r = cliente.post("/api/reunioes/reuniao_a/processar", json={"pessoas": pessoas})
        assert r.status_code == 202, r.text
        assert _esperar(lambda: processamento.estado_atual()["status"] != "rodando")

        # o que a tela recebe: o ultimo evento do SSE, com status "erro"
        sse = cliente.get("/api/reunioes/reuniao_a/progresso").text
        ultimo = json.loads([l for l in sse.splitlines() if l.startswith("data: ")][-1][6:])
        assert ultimo["status"] == "erro"
        assert ultimo["pessoas"] == pessoas, "o progresso nao devolveu as pessoas"

        # "Tentar novamente": reenvia exatamente o que o progresso trouxe
        r = cliente.post("/api/reunioes/reuniao_a/processar", json={"pessoas": ultimo["pessoas"]})
        assert r.status_code == 202, r.text
        assert _esperar(lambda: processamento.estado_atual()["status"] != "rodando")

        chamadas = [json.loads(l) for l in args.read_text(encoding="utf-8").splitlines()]
        assert len(chamadas) == 2
        for argv in chamadas:
            assert argv[argv.index("--pessoas") + 1] == "Amanda,Celso,Clélia", argv
    finally:
        del os.environ["FAKE_RUN_ARGS"]
        del os.environ["FAKE_RUN_CODIGO_SAIDA"]
        _limpar_ambiente_processamento(raiz_falsa, reunioes.PASTA_AUDIOS)
        shutil.rmtree(pasta, ignore_errors=True)


def test_talvez_nao_tenha_falado_vira_faixa_de_falantes():
    f = processamento.argumentos_de_falantes
    assert f([], ["Ana"]) == []
    assert f(["Ana", "Bia", "Caio"]) == ["--pessoas", "Ana,Bia,Caio"], "sem marca: numero exato"
    assert f(["Ana", "Bia", "Caio"], ["Caio"]) == [
        "--pessoas",
        "Ana,Bia,Caio",
        "--min-falantes",
        "2",
        "--max-falantes",
        "3",
    ]
    # todos talvez calados: so o teto (nao existe "pelo menos 0")
    assert f(["Ana", "Bia"], ["Ana", "Bia"]) == ["--pessoas", "Ana,Bia", "--max-falantes", "2"]
    # nome marcado que nao foi selecionado nao conta
    assert f(["Ana", "Bia"], ["Zeca"]) == ["--pessoas", "Ana,Bia"]


def test_rota_processar_leva_talvez_calados_ao_pipeline_e_ao_tentar_de_novo():
    pasta, cliente = _ambiente_temporario()
    raiz_falsa = _preparar_raiz_falsa()
    processamento.RAIZ = raiz_falsa
    processamento._estado = None
    args = pasta / "args_do_run.txt"
    os.environ["FAKE_RUN_ARGS"] = str(args)
    os.environ["FAKE_RUN_CODIGO_SAIDA"] = "1"
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_a")
        corpo = {"pessoas": ["Amanda", "Celso", "Clélia"], "talvez_calados": ["Clélia"]}
        r = cliente.post("/api/reunioes/reuniao_a/processar", json=corpo)
        assert r.status_code == 202, r.text
        assert _esperar(lambda: processamento.estado_atual()["status"] != "rodando")

        sse = cliente.get("/api/reunioes/reuniao_a/progresso").text
        ultimo = json.loads([l for l in sse.splitlines() if l.startswith("data: ")][-1][6:])
        assert ultimo["talvez_calados"] == ["Clélia"], ultimo

        r = cliente.post(
            "/api/reunioes/reuniao_a/processar",
            json={"pessoas": ultimo["pessoas"], "talvez_calados": ultimo["talvez_calados"]},
        )
        assert r.status_code == 202, r.text
        assert _esperar(lambda: processamento.estado_atual()["status"] != "rodando")

        chamadas = [json.loads(l) for l in args.read_text(encoding="utf-8").splitlines()]
        assert len(chamadas) == 2
        for argv in chamadas:
            assert argv[argv.index("--min-falantes") + 1] == "2", argv
            assert argv[argv.index("--max-falantes") + 1] == "3", argv
            assert argv[argv.index("--pessoas") + 1] == "Amanda,Celso,Clélia", argv
    finally:
        del os.environ["FAKE_RUN_ARGS"]
        del os.environ["FAKE_RUN_CODIGO_SAIDA"]
        _limpar_ambiente_processamento(raiz_falsa, reunioes.PASTA_AUDIOS)
        shutil.rmtree(pasta, ignore_errors=True)


def test_rota_processar_passa_o_idioma_da_interface_ao_pipeline():
    pasta, cliente = _ambiente_temporario()
    raiz_falsa = _preparar_raiz_falsa()
    processamento.RAIZ = raiz_falsa
    processamento._estado = None
    registro = pasta / "idioma_do_run.txt"
    os.environ["FAKE_RUN_IDIOMA"] = str(registro)
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_a")
        for corpo in ({"pessoas": [], "idioma": "en"}, {"pessoas": [], "idioma": "pt"}):
            r = cliente.post("/api/reunioes/reuniao_a/processar", json=corpo)
            assert r.status_code == 202, r.text
            assert _esperar(lambda: processamento.estado_atual()["status"] != "rodando")
        r = cliente.post("/api/reunioes/reuniao_a/processar", json={"pessoas": [], "idioma": "fr"})
        assert r.status_code == 422, "so pt ou en"
        assert registro.read_text(encoding="utf-8").split() == ["en", "pt"]
    finally:
        del os.environ["FAKE_RUN_IDIOMA"]
        _limpar_ambiente_processamento(raiz_falsa, reunioes.PASTA_AUDIOS)
        shutil.rmtree(pasta, ignore_errors=True)


def test_rota_processar_duas_reunioes_ao_mesmo_tempo_recusa_com_409():
    pasta, cliente = _ambiente_temporario()
    raiz_falsa = _preparar_raiz_falsa()
    processamento.RAIZ = raiz_falsa
    processamento._estado = None
    os.environ["FAKE_RUN_ATRASO_S"] = "0.3"
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_a")
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_b")

        r1 = cliente.post("/api/reunioes/reuniao_a/processar", json={"pessoas": []})
        assert r1.status_code == 202

        r2 = cliente.post("/api/reunioes/reuniao_b/processar", json={"pessoas": []})
        assert r2.status_code == 409
        assert erro_de(r2) == ("ja_processando", {"id": "reuniao_a"})
    finally:
        del os.environ["FAKE_RUN_ATRASO_S"]
        _limpar_ambiente_processamento(raiz_falsa, reunioes.PASTA_AUDIOS)
        shutil.rmtree(pasta, ignore_errors=True)


def test_rota_processar_sem_audio_da_404_em_portugues():
    pasta, cliente = _ambiente_temporario()
    try:
        (reunioes.PASTA_AUDIOS / "reuniao_a").mkdir()
        r = cliente.post("/api/reunioes/reuniao_a/processar", json={"pessoas": []})
        assert r.status_code == 404
        assert erro_de(r) == ("sem_audio_para_processar", {})
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_rota_cancelar_sem_nada_rodando_da_409():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_a")
        r = cliente.post("/api/reunioes/reuniao_a/cancelar")
        assert r.status_code == 409
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_rota_progresso_reuniao_ociosa_manda_um_evento_e_encerra():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_a")
        with cliente.stream("GET", "/api/reunioes/reuniao_a/progresso") as r:
            linhas = list(r.iter_lines())
        assert any("ocioso" in linha for linha in linhas), linhas
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_rota_progresso_reconecta_e_ve_o_estado_atual_na_hora():
    """O ESSENCIAL da reconexao: uma conexao SSE que comeca DEPOIS do job
    ja estar rodando ainda ve o estado atual no primeiro evento - nao
    depende de ter estado conectada desde o inicio."""
    pasta, cliente = _ambiente_temporario()
    raiz_falsa = _preparar_raiz_falsa()
    processamento.RAIZ = raiz_falsa
    processamento._estado = None
    os.environ["FAKE_RUN_ATRASO_S"] = "0.3"
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_a")
        cliente.post("/api/reunioes/reuniao_a/processar", json={"pessoas": []})

        assert _esperar(
            lambda: (
                processamento.estado_atual() is not None
                and processamento.estado_atual()["etapa"] >= 1
            )
        )

        with cliente.stream("GET", "/api/reunioes/reuniao_a/progresso") as r:
            primeira_linha = next(r.iter_lines())
        assert "rodando" in primeira_linha or "concluido" in primeira_linha
    finally:
        del os.environ["FAKE_RUN_ATRASO_S"]
        _limpar_ambiente_processamento(raiz_falsa, reunioes.PASTA_AUDIOS)
        shutil.rmtree(pasta, ignore_errors=True)


def test_servidor_sobe_sem_carregar_torch_nem_pyannote():
    """REGRESSAO (teste instavel na CI): o servidor importava torch e
    pyannote no topo do nucleo/pipeline sem usar nenhum dos dois - ~2 s a
    cada partida, e num primeiro uso frio o bastante para estourar o prazo
    dos testes que sobem o servidor de verdade. Interpretador limpo, sem os
    stubs desta suite."""
    codigo = (
        "import sys, trama.servidor.app as a; "
        "a.sistema.processamento.detectar_device_e_asr(); "
        "print(sorted(m for m in ('torch', 'pyannote.audio', 'pyannote.core') "
        "if m in sys.modules))"
    )
    r = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "[]", r.stdout


def test_progresso_vem_da_linha_de_maquina_nunca_da_frase():
    """O servidor le "@progresso {json}"; a frase do terminal (que muda de
    idioma) nao move a etapa. Detalhe so com os campos conhecidos."""
    ler = processamento.ler_progresso
    assert ler('@progresso {"etapa": 2, "total": 5, "detalhe": {"min": 4, "max": 5}}') == (
        2,
        {"min": 4, "max": 5},
    )
    assert ler('@progresso {"etapa": 5, "detalhe": {"asr": "mlx", "termos": 12}}') == (
        5,
        {"asr": "mlx", "termos": 12},
    )
    assert ler('@progresso {"etapa": 1, "detalhe": {}}') == (1, {})
    assert ler("2/5  Diarizando (quem falou quando) - 3 falantes...") is None
    assert ler("2/5  Diarizing (who spoke when) - 3 speakers...") is None
    assert ler("@progresso {quebrado") is None
    assert ler('@progresso {"etapa": 9}') is None
    assert ler('@progresso {"etapa": "2"}') is None
    assert ler(
        '@progresso {"etapa": 2, "detalhe": {"falantes": 3, "x": 1, "asr": "a b", "min": -1}}'
    ) == (2, {"falantes": 3})


def test_pipeline_emite_a_linha_de_maquina_so_quando_pedido():
    import contextlib
    import io

    from trama import pipeline

    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        pipeline._progresso(2, "2/5  Diarizando...", min=4, max=5)
    assert saida.getvalue() == "2/5  Diarizando...\n", "terminal sem linha de maquina"
    pipeline.PROGRESSO_MAQUINA = True
    saida = io.StringIO()
    try:
        with contextlib.redirect_stdout(saida):
            pipeline._progresso(
                2,
                "2/5  Diarizando...",
                **pipeline.detalhe_da_faixa({"min_speakers": 4, "max_speakers": 5}),
            )
    finally:
        pipeline.PROGRESSO_MAQUINA = False
    frase, maquina = saida.getvalue().splitlines()
    assert processamento.ler_progresso(maquina) == (2, {"min": 4, "max": 5}), maquina


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
