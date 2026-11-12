"""
tests/test_servidor_reunioes.py - Lista, upload, detalhe, audio recortado, busca e /api/sistema.

Parte das suites do servidor FastAPI (trama/servidor/, ADR 0004); a
infraestrutura comum esta em tests/servidor_apoio.py.

Uso:
    python tests/test_servidor_reunioes.py
"""

import json
import shutil
import sys
import tempfile
import threading
from pathlib import Path

import servidor_apoio  # noqa: F401 - isola o ambiente e instala os stubs ANTES do projeto
from servidor_apoio import (
    _ambiente_temporario,
    _criar_audio_real,
    _criar_reuniao_completa,
    _criar_reuniao_incompleta,
    _criar_reuniao_nao_processada,
    erro_de,
    rodar_suite,
)

import trama.servidor.app as app_mod
from trama import pipeline
from trama.servidor import busca, processamento, reunioes, sistema, upload

# ==========================================================================
# reunioes._caminho_audio - independente de extensao
# ==========================================================================


def test_caminho_audio_encontra_mp3_e_wav_no_apenas_m4a():
    """
    REGRESSAO: todo lookup de audio era fixo em ".m4a" - upload de .mp3
    ou .wav (servidor/upload.py aceita os tres) ficava invisivel para
    duracao, Detalhe e a rota de recorte, mesmo com o arquivo la no disco.
    """
    pasta = Path(tempfile.mkdtemp())
    try:
        (pasta / "reuniao_x.mp3").write_bytes(b"x")
        assert reunioes._caminho_audio(pasta, "reuniao_x").name == "reuniao_x.mp3"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)

    pasta = Path(tempfile.mkdtemp())
    try:
        (pasta / "reuniao_x.wav").write_bytes(b"x")
        assert reunioes._caminho_audio(pasta, "reuniao_x").name == "reuniao_x.wav"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_caminho_audio_ignora_json_txt_e_upload_parcial():
    pasta = Path(tempfile.mkdtemp())
    try:
        (pasta / "reuniao_x.json").write_text("{}")
        (pasta / "reuniao_x.txt").write_text("")
        (pasta / "reuniao_x.m4a.parcial").write_bytes(b"upload incompleto")
        assert reunioes._caminho_audio(pasta, "reuniao_x") is None

        (pasta / "reuniao_x.m4a").write_bytes(b"audio de verdade")
        assert reunioes._caminho_audio(pasta, "reuniao_x").name == "reuniao_x.m4a"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# GET /api/reunioes
# ==========================================================================


def test_lista_ordena_mais_recente_primeiro():
    """A reuniao mais recente (numero mais alto) tem que estar no topo -
    o usuario abre o app para ver o que acabou de gravar, nao a primeira
    reuniao de meses atras."""
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_01")
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_09")
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_05")
        r = cliente.get("/api/reunioes")
        ids = [item["id"] for item in r.json()]
        assert ids == ["reuniao_09", "reuniao_05", "reuniao_01"], ids
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_lista_classifica_os_tres_estados_pela_regra_de_versao_do_run_py():
    """
    REGRESSAO evitada por design: reuniao_08/09 (schema atual) tem que sair
    como 'completa'; reuniao_01/03/05 (schema antigo, sem turnos/dinamica)
    como 'incompleta'; e uma pasta so com audio (sem pipeline.py nunca ter
    rodado) como 'nao_processada'. O campo tem que vir explicito na
    resposta, nunca inferido pelo cliente a partir de uma chave ausente.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        _criar_reuniao_incompleta(reunioes.PASTA_AUDIOS, "reuniao_b")
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_c")

        r = cliente.get("/api/reunioes")
        assert r.status_code == 200
        por_id = {item["id"]: item for item in r.json()}
        assert por_id["reuniao_a"]["estado"] == "completa"
        assert por_id["reuniao_b"]["estado"] == "incompleta"
        assert por_id["reuniao_c"]["estado"] == "nao_processada"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_lista_dinamica_ordenada_por_fala_pct_decrescente():
    """
    A barra de tempo de fala (SKILL.md, elemento de assinatura) desenha os
    segmentos na ordem que 'dinamica' vier - e essa ordem tem que ser a
    mesma que o frontend usa para listar os nomes ao lado da barra (maior
    tempo de fala primeiro). Se as duas ordens divergirem (uma por nome,
    outra por peso), o nome errado fica ao lado da cor errada - e a barra
    perde a acessibilidade que a lista de nomes deveria garantir.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("Ramiro", "Amanda"))
        r = cliente.get("/api/reunioes")
        item = r.json()[0]
        assert item["dinamica"] == [
            {"pessoa": "Ramiro", "fala_pct": 70.0},
            {"pessoa": "Amanda", "fala_pct": 30.0},
        ], item["dinamica"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_lista_dinamica_e_none_quando_incompleta_ou_nao_processada():
    """
    Uma reuniao sem 'dinamica' no .json (schema antigo) ou sem .json nenhum
    nao pode ganhar uma barra fingindo dado que nao existe - dinamica tem
    que vir None, nunca lista vazia (que pareceria '0% para todo mundo').
    """
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_incompleta(reunioes.PASTA_AUDIOS, "reuniao_b")
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_c")
        r = cliente.get("/api/reunioes")
        por_id = {item["id"]: item for item in r.json()}
        assert por_id["reuniao_b"]["dinamica"] is None
        assert por_id["reuniao_c"]["dinamica"] is None
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_lista_nao_processada_traz_acao_processar_disponivel():
    """Marco 2, etapa 5: o botao 'Processar' da lista chama a rota de
    verdade agora - 'nao_processada' nao tem nada para explicar (motivo
    None), so o botao funciona."""
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_c")
        r = cliente.get("/api/reunioes")
        item = r.json()[0]
        assert item["acao_processar"] == {"disponivel": True, "motivo": None}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_lista_reuniao_incompleta_nao_derruba_as_outras():
    """Uma reuniao com .json de schema antigo, faltando campos, nao pode
    fazer a rota inteira quebrar - as outras reunioes tem que continuar
    aparecendo normalmente."""
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_boa")
        _criar_reuniao_incompleta(reunioes.PASTA_AUDIOS, "reuniao_velha")

        r = cliente.get("/api/reunioes")
        assert r.status_code == 200
        ids = {item["id"] for item in r.json()}
        assert ids == {"reuniao_boa", "reuniao_velha"}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_lista_campo_ausente_fica_ausente_nao_vira_zero():
    """
    Uma reuniao incompleta (sem 'dinamica') nao pode aparecer como se
    ninguem tivesse interrompido ninguem - o campo tem que ficar de fora
    (None/ausente), nunca 0 ou lista vazia fingindo um dado que nao existe.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_sem_audio_valido", 0)
        r = cliente.get("/api/reunioes")
        item = r.json()[0]
        assert item["pessoas"] is None, (
            "reuniao sem clusters nao pode ganhar uma lista de pessoas vazia "
            "fingindo que sabemos quem falou"
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# upload.py - funcoes puras
# ==========================================================================


def test_extensao_permitida_aceita_as_tres_e_rejeita_o_resto():
    assert upload.extensao_permitida("reuniao.m4a") == ".m4a"
    assert upload.extensao_permitida("reuniao.MP3") == ".mp3"
    assert upload.extensao_permitida("reuniao.wav") == ".wav"
    assert upload.extensao_permitida("reuniao.exe") is None
    assert upload.extensao_permitida("reuniao") is None
    assert upload.extensao_permitida("") is None
    assert upload.extensao_permitida(None) is None


def test_proximo_id_usa_o_maior_numero_existente_nao_a_contagem():
    """Uma reuniao apagada nao pode fazer o proximo numero ser reusado -
    o id tem que vir do MAIOR numero ja usado, nao de len(pastas)."""
    pasta = Path(tempfile.mkdtemp())
    try:
        (pasta / "reuniao_01").mkdir()
        (pasta / "reuniao_09").mkdir()
        assert upload.proximo_id(pasta) == "reuniao_10"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_proximo_id_pasta_vazia_ou_inexistente_comeca_em_01():
    pasta = Path(tempfile.mkdtemp()) / "nao_existe_ainda"
    assert upload.proximo_id(pasta) == "reuniao_01"


def test_criar_pasta_exclusiva_sob_concorrencia_nunca_colide():
    """
    REGRESSAO: "ler o maior numero, decidir NN, criar a pasta" tinha uma
    corrida classica - duas chamadas simultaneas podiam LER o mesmo maior
    numero antes de qualquer uma ter CRIADO a pasta, e as duas decidiam o
    mesmo id (uma sobrescreveria a outra). _criar_pasta_exclusiva usa o
    mkdir (atomico no SO) como a propria decisao - este teste dispara
    threads de verdade, nao so chama a funcao em sequencia, porque a
    corrida so existe com concorrencia real.
    """
    pasta = Path(tempfile.mkdtemp())
    try:
        resultados = []
        trava_resultados = threading.Lock()
        partida = threading.Barrier(8)

        def tentar():
            partida.wait()  # forca as 8 chamadas a competirem juntas
            id_novo, _ = upload._criar_pasta_exclusiva(pasta)
            with trava_resultados:
                resultados.append(id_novo)

        threads = [threading.Thread(target=tentar) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(resultados) == len(set(resultados)), (
            f"ids colidiram sob concorrencia: {resultados}"
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# POST /api/reunioes
# ==========================================================================


def test_upload_cria_pasta_e_reuniao_aparece_como_nao_processada():
    pasta, cliente = _ambiente_temporario()
    try:
        r = cliente.post(
            "/api/reunioes",
            files={"arquivo": ("gravacao.m4a", b"conteudo falso", "audio/mp4")},
        )
        assert r.status_code == 201, r.text
        corpo = r.json()
        assert corpo["id"] == "reuniao_01"
        assert corpo["estado"] == "nao_processada"

        caminho_audio = reunioes.PASTA_AUDIOS / "reuniao_01" / "reuniao_01.m4a"
        assert caminho_audio.read_bytes() == b"conteudo falso"
        assert not (reunioes.PASTA_AUDIOS / "reuniao_01" / "reuniao_01.m4a.parcial").exists()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_upload_nome_do_cliente_nunca_vira_caminho():
    """O nome enviado pelo cliente so decide a EXTENSAO aceita - o
    arquivo salvo em disco usa sempre o nome gerado pelo servidor
    (CLAUDE.md, regra 4), nunca o que veio no Content-Disposition."""
    pasta, cliente = _ambiente_temporario()
    try:
        r = cliente.post(
            "/api/reunioes",
            files={"arquivo": ("../../etc/passwd.m4a", b"x", "audio/mp4")},
        )
        assert r.status_code == 201, r.text
        id_novo = r.json()["id"]
        pasta_reuniao = reunioes.PASTA_AUDIOS / id_novo
        arquivos = {p.name for p in pasta_reuniao.iterdir()}
        # ".duracao_cache.json" e ".data_cache.json" sao efeito colateral
        # normal de carregar() (chamado no fim da rota) medindo duracao e
        # data via ffprobe - so o nome do audio em si e o que a checagem de
        # seguranca importa.
        assert arquivos == {f"{id_novo}.m4a", ".duracao_cache.json", ".data_cache.json"}, arquivos
        assert not (reunioes.PASTA_AUDIOS.parent / "etc").exists()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_upload_extensao_nao_suportada_e_rejeitado_em_portugues():
    pasta, cliente = _ambiente_temporario()
    try:
        r = cliente.post(
            "/api/reunioes",
            files={"arquivo": ("video.mp4", b"x", "video/mp4")},
        )
        assert r.status_code == 400
        assert erro_de(r)[0] == "extensao_invalida" and ".m4a" in erro_de(r)[1]["formatos"]
        assert not any(reunioes.PASTA_AUDIOS.iterdir())
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_upload_acima_do_limite_e_rejeitado_e_nao_deixa_pasta_orfa():
    pasta, cliente = _ambiente_temporario()
    limite_original = upload.TAMANHO_MAXIMO_BYTES
    try:
        upload.TAMANHO_MAXIMO_BYTES = 10  # pequeno de proposito, so pro teste
        r = cliente.post(
            "/api/reunioes",
            files={"arquivo": ("reuniao.m4a", b"x" * 1000, "audio/mp4")},
        )
        assert r.status_code == 413
        assert not any(reunioes.PASTA_AUDIOS.iterdir()), (
            "upload rejeitado nao pode deixar a pasta reuniao_NN para tras"
        )
    finally:
        upload.TAMANHO_MAXIMO_BYTES = limite_original
        shutil.rmtree(pasta, ignore_errors=True)


def test_upload_duas_reunioes_pegam_ids_sequenciais():
    pasta, cliente = _ambiente_temporario()
    try:
        r1 = cliente.post("/api/reunioes", files={"arquivo": ("a.m4a", b"x", "audio/mp4")})
        r2 = cliente.post("/api/reunioes", files={"arquivo": ("b.wav", b"x", "audio/wav")})
        assert r1.json()["id"] == "reuniao_01"
        assert r2.json()["id"] == "reuniao_02"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# GET /api/reunioes/{id}
# ==========================================================================


def test_detalhe_id_com_barra_ou_ponto_ponto_e_rejeitado_antes_do_disco():
    """
    O CASO QUE MAIS IMPORTA (CLAUDE.md regra 4): o id vem do cliente. Um id
    como '../etc' ou contendo barra nao pode nem chegar perto de um
    Path(...) sem validacao - tem que ser rejeitado pela regex antes de
    qualquer tentativa de abrir arquivo.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        for id_ruim in ["..%2Fatc", "reuniao_01..%2F..%2Fetc", "reuniao-01%2F..", "MAIUSCULA"]:
            r = cliente.get(f"/api/reunioes/{id_ruim}")
            assert r.status_code in (400, 404), (id_ruim, r.status_code)
        # Verificacao direta na camada de validacao, sem depender de como o
        # ASGI decodifica a URL - e aqui que a garantia de fato mora.
        for id_ruim in ["../etc", "a/b", "..", "reuniao_01/", "MAIUSCULA"]:
            try:
                reunioes.carregar(id_ruim)
                assert False, f"{id_ruim!r} deveria ter sido rejeitado"
            except reunioes.IdInvalido:
                pass
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_detalhe_reuniao_completa_nao_expoe_embedding():
    """
    BARREIRA, nao verificacao pontual: nenhuma resposta da API pode conter
    a chave 'embedding' em nenhum cluster. E dado biometrico bruto, o
    frontend nao usa, e alguem vai um dia querer devolve-lo para desenhar
    um grafico - este teste existe para que essa mudanca seja deliberada,
    nao um esquecimento.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        r = cliente.get("/api/reunioes/reuniao_a")
        corpo_bruto = r.text
        assert "embedding" not in corpo_bruto, (
            "a resposta da API contem a chave 'embedding' - dado biometrico vazando para o cliente"
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_detalhe_reuniao_sem_limiar_gravado_usa_o_atual_e_marca_a_origem():
    """
    Reunioes de antes da mudanca que fez pipeline.py gravar sim_min/margem_min
    no .json (as 9 de producao, hoje) nao tem como recuperar o limiar
    HISTORICO - a rota devolve o de hoje, mas 'limiares_origem' tem que
    dizer 'atual', nunca fingir que e o valor do processamento original.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        r = cliente.get("/api/reunioes/reuniao_a")
        d = r.json()
        assert d["sim_min"] == pipeline.SIM_MIN
        assert d["margem_min"] == pipeline.MARGEM_MIN
        assert d["limiares_origem"] == "atual"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_detalhe_reuniao_com_limiar_gravado_usa_o_do_processamento():
    """
    Reunioes processadas pelo pipeline.py atual gravam sim_min/margem_min no
    proprio .json - a rota tem que devolver ESSES valores (o limiar de
    quando a reuniao realmente rodou), mesmo que o ambiente de hoje tenha
    SIM_MIN diferente, e marcar a origem como 'processamento'.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        dados = json.loads((pasta_reuniao / "reuniao_a.json").read_text())
        dados["sim_min"] = 0.75
        dados["margem_min"] = 0.10
        (pasta_reuniao / "reuniao_a.json").write_text(json.dumps(dados, ensure_ascii=False))

        r = cliente.get("/api/reunioes/reuniao_a")
        d = r.json()
        assert d["sim_min"] == 0.75
        assert d["margem_min"] == 0.10
        assert d["limiares_origem"] == "processamento"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_detalhe_reuniao_repassa_confianca_e_lacunas_sem_alteracao():
    """
    carregar() (servidor/reunioes.py) e passagem direta do .json para
    'falas'/campos novos - nao reconstroi nada, ao contrario de
    clusters/sim_min/margem_min que tem logica propria. confianca_media,
    palavras_baixa_confianca, lacunas_sem_texto e limiar_confianca_fala
    tem que sair EXATAMENTE como gravados por pipeline.py.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        caminho = pasta_reuniao / "reuniao_a.json"
        dados = json.loads(caminho.read_text())
        dados["falas"][0]["confianca_media"] = 0.42
        dados["falas"][0]["palavras_baixa_confianca"] = [
            {"posicao": 0, "comprimento": 2, "probabilidade": 0.3}
        ]
        dados["lacunas_sem_texto"] = [
            {"posicao": 3, "inicio": 1.0, "fim": 2.0, "falante": "Ramiro"}
        ]
        dados["limiar_confianca_fala"] = 0.6
        caminho.write_text(json.dumps(dados, ensure_ascii=False))

        r = cliente.get("/api/reunioes/reuniao_a")
        d = r.json()
        assert d["falas"][0]["confianca_media"] == 0.42
        assert d["falas"][0]["palavras_baixa_confianca"] == [
            {"posicao": 0, "comprimento": 2, "probabilidade": 0.3}
        ]
        assert d["lacunas_sem_texto"] == [
            {"posicao": 3, "inicio": 1.0, "fim": 2.0, "falante": "Ramiro"}
        ]
        assert d["limiar_confianca_fala"] == 0.6
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_detalhe_reuniao_incompleta_nao_inventa_dinamica():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_incompleta(reunioes.PASTA_AUDIOS, "reuniao_velha")
        r = cliente.get("/api/reunioes/reuniao_velha")
        d = r.json()
        assert d["estado"] == "incompleta"
        assert "dinamica" not in d, "dinamica nao pode ser inventada"
        assert "turnos" not in d, "turnos nao pode ser inventado"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_duracao_de_nao_processada_usa_cache_nao_chama_ffprobe_toda_vez():
    """
    REGRESSAO evitada por design: sem cache, GET /api/reunioes chamaria
    ffprobe (um subprocess) uma vez por reuniao nao_processada A CADA
    carregamento da lista - com dezenas de gravacoes na fila (o caso real
    de producao, nao os quatro de hoje), isso vira dezenas de processos por
    tela aberta. A segunda chamada tem que ler do cache em disco, nao
    invocar ffprobe de novo.
    """
    pasta, cliente = _ambiente_temporario()
    chamadas = []
    original = reunioes._duracao_por_ffprobe

    def contador(caminho):
        chamadas.append(caminho)
        return 42.0

    reunioes._duracao_por_ffprobe = contador
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_x", 999)

        r1 = cliente.get("/api/reunioes")
        r2 = cliente.get("/api/reunioes")
        assert r1.json()[0]["duracao_s"] == 42.0
        assert r2.json()[0]["duracao_s"] == 42.0
        assert len(chamadas) == 1, (
            f"ffprobe foi chamado {len(chamadas)} vezes em 2 listagens - "
            "o cache em disco nao esta sendo lido"
        )

        caminho_cache = reunioes.PASTA_AUDIOS / "reuniao_x" / reunioes.NOME_CACHE_DURACAO
        assert caminho_cache.exists(), "cache em disco nao foi escrito"
    finally:
        reunioes._duracao_por_ffprobe = original
        shutil.rmtree(pasta, ignore_errors=True)


def test_duracao_com_cache_recalcula_se_o_audio_for_substituido():
    """Um audio reenviado (novo tamanho/mtime) nao pode ficar preso na
    duracao do arquivo antigo - o cache tem que se invalidar sozinho."""
    pasta, cliente = _ambiente_temporario()
    chamadas = []
    original = reunioes._duracao_por_ffprobe
    reunioes._duracao_por_ffprobe = lambda caminho: chamadas.append(1) or float(len(chamadas))
    try:
        pasta_reuniao = _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_y", 100)
        caminho_audio = pasta_reuniao / "reuniao_y.m4a"

        primeira = reunioes._duracao_com_cache(caminho_audio)
        assert len(chamadas) == 1

        segunda = reunioes._duracao_com_cache(caminho_audio)
        assert len(chamadas) == 1, "cache nao deveria ter sido invalidado"
        assert segunda == primeira

        caminho_audio.write_bytes(b"\x00" * 500)  # tamanho novo = audio novo
        terceira = reunioes._duracao_com_cache(caminho_audio)
        assert len(chamadas) == 2, "audio substituido deveria ter invalidado o cache"
        assert terceira != primeira
    finally:
        reunioes._duracao_por_ffprobe = original
        shutil.rmtree(pasta, ignore_errors=True)


def test_duracao_cache_nao_guarda_caminho_do_arquivo():
    """Cache de dado derivado nao pode carregar estrutura de diretorio da
    maquina - so o tamanho/mtime (chave de invalidacao) e o resultado."""
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_z", 50)
        caminho_audio = pasta_reuniao / "reuniao_z.m4a"
        reunioes._duracao_com_cache(caminho_audio)

        conteudo = (pasta_reuniao / reunioes.NOME_CACHE_DURACAO).read_text()
        assert str(pasta) not in conteudo
        assert "audios" not in conteudo
        assert set(json.loads(conteudo).keys()) == {"chave", "duracao_s"}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_duracao_cache_corrompido_e_tratado_como_cache_frio():
    """
    Se o processo morrer no meio da escrita do cache (disco cheio, kill -9),
    o arquivo pode ficar com JSON truncado/invalido. Isso nao pode derrubar
    a listagem - tem que ser tratado como se o cache nao existisse, e
    remedido.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_w", 50)
        caminho_audio = pasta_reuniao / "reuniao_w.m4a"
        (pasta_reuniao / reunioes.NOME_CACHE_DURACAO).write_text(
            '{"chave": [50, 123', encoding="utf-8"
        )  # JSON truncado de proposito

        original = reunioes._duracao_por_ffprobe
        reunioes._duracao_por_ffprobe = lambda caminho: 77.0
        try:
            duracao = reunioes._duracao_com_cache(caminho_audio)
        finally:
            reunioes._duracao_por_ffprobe = original

        assert duracao == 77.0, "cache corrompido deveria ter sido remedido"

        r = cliente.get("/api/reunioes")
        assert r.status_code == 200, "cache corrompido nao pode derrubar a listagem"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_duracao_cache_falha_ao_escrever_nao_derruba_a_listagem():
    """
    Pasta somente leitura ou disco cheio: a escrita do cache tem que falhar
    em silencio (a duracao ainda e calculada e devolvida), nunca propagar
    um erro que derruba GET /api/reunioes.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_v", 50)
        caminho_audio = pasta_reuniao / "reuniao_v.m4a"

        original = reunioes._duracao_por_ffprobe
        reunioes._duracao_por_ffprobe = lambda caminho: 88.0
        # Simula falha de escrita (disco cheio/permissao) sem depender de
        # chmod, que se comporta de formas diferentes dependendo do usuario
        # rodando o teste (root ignora permissao de escrita).
        original_write_text = Path.write_text

        def write_text_com_falha(self, *a, **kw):
            if self.name == reunioes.NOME_CACHE_DURACAO:
                raise OSError("disco cheio (simulado)")
            return original_write_text(self, *a, **kw)

        Path.write_text = write_text_com_falha
        try:
            duracao = reunioes._duracao_com_cache(caminho_audio)
            r = cliente.get("/api/reunioes")
        finally:
            Path.write_text = original_write_text
            reunioes._duracao_por_ffprobe = original

        assert duracao == 88.0, "falha ao escrever cache nao pode impedir a resposta"
        assert r.status_code == 200
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_detalhe_reuniao_nao_processada_mostra_o_que_se_sabe_e_acao_disponivel():
    """
    'nao_processada' e fila de trabalho, nao erro: o detalhe tem que trazer
    o que da para saber so com o arquivo (nome, tamanho) e uma acao de
    processar disponivel (marco 2, etapa 5) - sem motivo, porque nao ha
    nada para explicar nesse estado.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_nova", 12345)
        r = cliente.get("/api/reunioes/reuniao_nova")
        assert r.status_code == 200
        d = r.json()
        assert d["estado"] == "nao_processada"
        assert d["audio_nome"] == "reuniao_nova.m4a"
        assert d["audio_tamanho_bytes"] == 12345
        assert d["acao_processar"] == {"disponivel": True, "motivo": None}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_detalhe_reuniao_interrompida_acao_disponivel_com_motivo():
    """
    'interrompido' (marcador em disco sobrou sem job correspondente em
    memoria - servidor reiniciou no meio) tambem tem acao disponivel: o
    botao 'Tentar novamente' dispara um processamento novo. Diferente de
    'nao_processada', aqui vale explicar o que aconteceu - motivo nao e
    None.
    """
    pasta, cliente = _ambiente_temporario()
    processamento._estado = None
    try:
        pasta_reuniao = _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_interrompida")
        (pasta_reuniao / processamento.NOME_MARCADOR).write_text(
            json.dumps({"pid": 999999999}), encoding="utf-8"
        )

        r = cliente.get("/api/reunioes/reuniao_interrompida")
        d = r.json()
        assert d["estado"] == "interrompido"
        assert d["acao_processar"]["disponivel"] is True
        assert d["acao_processar"]["motivo"] == reunioes.MOTIVO_INTERROMPIDA

        r2 = cliente.get("/api/reunioes")
        item = next(i for i in r2.json() if i["id"] == "reuniao_interrompida")
        assert item["acao_processar"] == d["acao_processar"], (
            "lista e detalhe tem que trazer o mesmo acao_processar - "
            "mesma constante de motivo, nunca dessincronizado"
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_detalhe_reuniao_inexistente_da_404_em_portugues():
    pasta, cliente = _ambiente_temporario()
    try:
        r = cliente.get("/api/reunioes/reuniao_fantasma")
        assert r.status_code == 404
        assert erro_de(r) == ("reuniao_nao_encontrada", {})
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# GET /api/reunioes/{id}/audio
# ==========================================================================


def test_audio_id_com_barra_ou_ponto_ponto_e_rejeitado_antes_do_disco():
    """
    O CASO QUE MAIS PEDE CUIDADO (prompt do marco 1, etapa 2): o id vem do
    cliente numa URL. resolver_audio() usa a MESMA validacao de carregar()
    - testado aqui direto na funcao, sem depender de como o ASGI decodifica
    a URL antes de rotear.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        for id_ruim in ["../etc", "a/b", "..", "reuniao_01/"]:
            try:
                reunioes.resolver_audio(id_ruim)
                assert False, f"{id_ruim!r} deveria ter sido rejeitado"
            except reunioes.IdInvalido:
                pass
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_audio_recorta_trecho_real_devolve_wav():
    """Usa o ffmpeg de verdade (nao mock) contra um audio sintetico curto -
    a suite testa as funcoes reais, nao uma simulacao delas."""
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        _criar_audio_real(pasta_reuniao / "reuniao_a.m4a", duracao_s=3)

        r = cliente.get("/api/reunioes/reuniao_a/audio?inicio=0.5&fim=2")
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"
        assert r.content[:4] == b"RIFF", "corpo da resposta nao e um WAV valido"
        assert len(r.content) > 0
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_audio_fim_alem_da_duracao_real_nao_trava_so_clampa():
    """
    Um cliente pode pedir um 'fim' que passa do ultimo segundo gravado
    (arredondamento na tela, por exemplo) mas ainda dentro do teto de
    trecho. Isso nao pode travar nem estourar - o ffmpeg simplesmente
    devolve ate onde o audio existe.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        _criar_audio_real(pasta_reuniao / "reuniao_a.m4a", duracao_s=2)

        r = cliente.get("/api/reunioes/reuniao_a/audio?inicio=1&fim=60")
        assert r.status_code == 200
        assert len(r.content) > 0
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_audio_fim_menor_ou_igual_a_inicio_e_rejeitado_em_portugues():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        r = cliente.get("/api/reunioes/reuniao_a/audio?inicio=5&fim=5")
        assert r.status_code == 400
        assert erro_de(r) == ("intervalo_invalido", {})
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_audio_trecho_acima_do_teto_e_rejeitado_sem_chamar_ffmpeg():
    """
    REGRESSAO evitada por design: sem teto, inicio=0&fim=99999 faria o
    ffmpeg materializar a reuniao inteira como WAV 16 bits na memoria do
    servidor. A revisao so pede trechos de segundos - qualquer coisa acima
    do teto e rejeitada ANTES de resolver o audio ou rodar o ffmpeg.
    """
    pasta, cliente = _ambiente_temporario()
    chamado = []
    original = reunioes.recortar_audio
    reunioes.recortar_audio = lambda *a, **kw: chamado.append(1) or b""
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        fim = app_mod.DURACAO_MAXIMA_TRECHO_S + 1
        r = cliente.get(f"/api/reunioes/reuniao_a/audio?inicio=0&fim={fim}")
        assert r.status_code == 400
        assert erro_de(r)[0] == "trecho_longo_demais"
        assert not chamado, "ffmpeg nao deveria ter sido chamado para um trecho acima do teto"
    finally:
        reunioes.recortar_audio = original
        shutil.rmtree(pasta, ignore_errors=True)


def test_audio_inicio_negativo_e_rejeitado():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        r = cliente.get("/api/reunioes/reuniao_a/audio?inicio=-1&fim=3")
        assert r.status_code == 400
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_audio_reuniao_sem_m4a_da_erro_claro_em_portugues_nao_stacktrace():
    """
    O .m4a original pode ter sido apagado apos o processamento (espaco em
    disco) mesmo com o .json continuando presente. A rota nao pode
    devolver um 500 com stack trace - tem que reconhecer a ausencia e
    explicar em portugues (CLAUDE.md regra 8).
    """
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_sem_audio")
        # de proposito: NAO cria o .m4a

        r = cliente.get("/api/reunioes/reuniao_sem_audio/audio?inicio=0&fim=3")
        assert r.status_code == 404
        assert erro_de(r) == ("audio_nao_encontrado", {})
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_audio_reuniao_inexistente_da_404():
    pasta, cliente = _ambiente_temporario()
    try:
        r = cliente.get("/api/reunioes/reuniao_fantasma/audio?inicio=0&fim=3")
        assert r.status_code == 404
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# GET /api/busca - trecho da fala
# ==========================================================================


def _reuniao_com_falas(pasta_audios, id, falas):
    pasta = _criar_reuniao_completa(pasta_audios, id)
    j = pasta / f"{id}.json"
    d = json.loads(j.read_text(encoding="utf-8"))
    d["falas"] = [
        {"falante": f, "cluster": "S0", "inicio": i, "fim": i + 5.0, "texto": t}
        for f, i, t in falas
    ]
    j.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return j


def test_busca_sem_acento_sem_maiuscula_e_destaque_no_texto_original():
    pasta, cliente = _ambiente_temporario()
    busca._cache.clear()
    try:
        _reuniao_com_falas(
            reunioes.PASTA_AUDIOS,
            "reuniao_01",
            [
                ("Clélia", 68.3, "Você mandou a pauta já?"),
                ("Celso", 90.0, "Não, ainda não."),
            ],
        )
        r = cliente.get("/api/busca", params={"q": "VOCE ja"})
        assert r.status_code == 200, r.text
        (res,) = r.json()["resultados"]
        assert res["id"] == "reuniao_01" and res["total"] == 1
        (t,) = res["trechos"]
        assert (t["falante"], t["inicio"]) == ("Clélia", 68.3)
        assert [t["texto"][a:b] for a, b in t["destaques"]] == ["Você", "já"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_busca_exige_todas_as_palavras_na_mesma_fala():
    pasta, cliente = _ambiente_temporario()
    busca._cache.clear()
    try:
        _reuniao_com_falas(
            reunioes.PASTA_AUDIOS,
            "reuniao_01",
            [
                ("A", 1.0, "a matriz GUT ficou pronta"),
                ("B", 10.0, "a planilha tambem"),
            ],
        )
        _reuniao_com_falas(
            reunioes.PASTA_AUDIOS,
            "reuniao_02",
            [
                ("C", 1.0, "matriz e planilha na mesma fala"),
            ],
        )
        res = cliente.get("/api/busca", params={"q": "matriz planilha"}).json()["resultados"]
        assert [r["id"] for r in res] == ["reuniao_02"], (
            "palavras espalhadas em falas diferentes nao casam"
        )
        assert cliente.get("/api/busca", params={"q": "   "}).json() == {"resultados": []}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_busca_trecho_longo_corta_com_reticencias_e_limita_por_reuniao():
    pasta, cliente = _ambiente_temporario()
    busca._cache.clear()
    try:
        longo = ("palavra " * 40) + "alvo " + ("palavra " * 40)
        _reuniao_com_falas(
            reunioes.PASTA_AUDIOS,
            "reuniao_01",
            [("A", float(i), longo.strip()) for i in range(busca.MAX_TRECHOS_POR_REUNIAO + 5)],
        )
        (res,) = cliente.get("/api/busca", params={"q": "alvo"}).json()["resultados"]
        assert res["total"] == busca.MAX_TRECHOS_POR_REUNIAO + 5
        assert len(res["trechos"]) == busca.MAX_TRECHOS_POR_REUNIAO
        t = res["trechos"][0]
        assert t["texto"].startswith("…") and t["texto"].endswith("…")
        assert [t["texto"][a:b] for a, b in t["destaques"]] == ["alvo"]
        assert not t["texto"].startswith("…alavra"), "cortou palavra no meio"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_busca_ve_o_json_regravado_e_recusa_consulta_longa_em_portugues():
    pasta, cliente = _ambiente_temporario()
    busca._cache.clear()
    try:
        j = _reuniao_com_falas(reunioes.PASTA_AUDIOS, "reuniao_01", [("A", 1.0, "chat apt")])
        assert cliente.get("/api/busca", params={"q": "chatgpt"}).json()["resultados"] == []
        d = json.loads(j.read_text(encoding="utf-8"))
        d["falas"][0]["texto"] = "ChatGPT"
        d["falas"][0]["inicio"] = 2.0  # muda o tamanho do arquivo
        j.write_text(json.dumps(d), encoding="utf-8")
        assert len(cliente.get("/api/busca", params={"q": "chatgpt"}).json()["resultados"]) == 1
        r = cliente.get("/api/busca", params={"q": "x" * 201})
        assert r.status_code == 400 and erro_de(r) == ("busca_longa_demais", {"maximo": 200})
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# GET /api/sistema
# ==========================================================================


def test_sistema_devolve_versao_dispositivo_caminhos_e_licencas():
    pasta, cliente = _ambiente_temporario()
    try:
        d = cliente.get("/api/sistema").json()
        assert d["versao"] == sistema.VERSAO
        assert d["device"] in ("mps", "cpu") and d["asr"] in ("mlx", "faster")
        assert d["pasta_audios"] == str((pasta / "audios").resolve())
        assert d["banco_vozes"] == str((pasta / "vozes_teste.db").resolve())
        nomes = [s["nome"] for s in d["licencas"]]
        assert "Whisper" in nomes and "Literata" in nomes
        # so secao que declara licenca vira "licenca" na tela (anotacao interna, nunca)
        assert all(any(i["rotulo"] == "Licenca" for i in s["itens"]) for s in d["licencas"])
        literata = next(s for s in d["licencas"] if s["nome"] == "Literata")
        rotulos = {i["rotulo"]: i["texto"] for i in literata["itens"]}
        assert rotulos["Licenca"] == "SIL Open Font License 1.1"
        # linha de continuacao indentada junta com o item de cima
        assert "frontend/src/estilos/fontes/" in rotulos["Arquivos"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_demonstracao_avisa_sem_audio_em_vez_de_procurar_arquivo():
    """REC_MEET_DEMO=1: /api/sistema diz que e demonstracao, e a rota de
    audio responde a frase da tela (em portugues) sem tocar disco - as
    reunioes de demonstracao nao tem audio."""
    pasta, cliente = _ambiente_temporario()
    try:
        assert cliente.get("/api/sistema").json()["demonstracao"] is False
        sistema.DEMONSTRACAO = True
        assert cliente.get("/api/sistema").json()["demonstracao"] is True
        r = cliente.get("/api/reunioes/reuniao_01/audio", params={"inicio": 0, "fim": 2})
        assert r.status_code == 404
        assert erro_de(r) == ("sem_audio_na_demonstracao", {})
        # intervalo absurdo continua 400, antes de qualquer outra coisa
        r = cliente.get("/api/reunioes/reuniao_01/audio", params={"inicio": 2, "fim": 1})
        assert r.status_code == 400
    finally:
        sistema.DEMONSTRACAO = False
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
