"""
tests/test_servidor_transcricao.py - Transcricao em .txt e correcao manual do texto de uma fala (ADR 0016).

Parte das suites do servidor FastAPI (trama/servidor/, ADR 0004); a
infraestrutura comum esta em tests/servidor_apoio.py.

Uso:
    python tests/test_servidor_transcricao.py
"""

import json
import shutil
import sys

import servidor_apoio  # noqa: F401 - isola o ambiente e instala os stubs ANTES do projeto
from servidor_apoio import (
    _ambiente_temporario,
    _criar_reuniao_completa,
    _criar_reuniao_incompleta,
    _criar_reuniao_nao_processada,
    rodar_suite,
)

from trama import nucleo
from trama.servidor import glossario, reunioes

# --------------------------------------------------------------------------
# transcricao em .txt (servidor/transcricao.py)
# --------------------------------------------------------------------------


def _dados_para_txt(**extra):
    """O que reunioes.carregar devolveria: titulo/data ja resolvidos."""
    dados = {
        "titulo": None,
        "data": "2026-11-04T11:59:48Z",
        "data_origem": "gravacao",
        "clusters": {
            "S0": {"nome": "Celso"},
            "S1": {"nome": "Clélia"},
            "S2": {"nome": "IGNORADO_S2"},
            "S3": {"nome": "DESCONHECIDO_S3"},
        },
        "falas": [
            {
                "falante": "Celso",
                "cluster": "S0",
                "inicio": 4.7,
                "fim": 9.0,
                "texto": "  Bom dia,\n todo mundo. ",
                "palavras_baixa_confianca": [{"posicao": 0, "comprimento": 3}],
            },
            {
                "falante": "Clélia",
                "cluster": "S1",
                "inicio": 65.0,
                "fim": 70.0,
                "texto": "Ação aprovada.",
            },
            {
                "falante": "DESCONHECIDO_S3",
                "cluster": "S3",
                "inicio": 71.0,
                "fim": 72.0,
                "texto": "Uhum.",
            },
            {
                "falante": "IGNORADO_S2",
                "cluster": "S2",
                "inicio": 80.0,
                "fim": 1530.0,
                "texto": "Tchau.",
            },
            {"falante": "Celso", "cluster": "S0", "inicio": 90.0, "fim": 91.0, "texto": "   "},
        ],
        "dinamica": {
            "Clélia": {"fala_pct": 20.4},
            "Celso": {"fala_pct": 60.6},
            "IGNORADO_S2": {"fala_pct": 15.0},
            "DESCONHECIDO_S3": {"fala_pct": 4.0},
        },
        "regioes_sobrepostas": [[4.7, 6.0]],
    }
    dados.update(extra)
    return dados


def test_transcricao_txt_cabecalho_e_uma_linha_por_fala_sem_marca_de_interface():
    from datetime import timedelta, timezone

    from trama.servidor import transcricao

    fuso = timezone(timedelta(hours=-3))
    texto = transcricao.montar_texto("reuniao_13", _dados_para_txt(), fuso=fuso)

    assert texto == (
        "Reunião 13\n"
        "Data: 4 de novembro de 2026, 08:59\n"
        "Duração: 26 min\n"
        "Participantes (parcela do tempo de fala):\n"
        "- Celso: 61%\n"
        "- Clélia: 20%\n"
        "- voz não atribuída 2: 15%\n"
        "- voz não atribuída 1: 4%\n"
        "\n"
        "[00:04] Celso: Bom dia, todo mundo.\n"
        "[01:05] Clélia: Ação aprovada.\n"
        "[01:11] voz não atribuída 1: Uhum.\n"
        "[01:20] voz não atribuída 2: Tchau.\n"
    ), texto
    # numeracao igual a da tela: ordem do rotulo cru (DESCONHECIDO < IGNORADO)
    assert "DESCONHECIDO" not in texto and "IGNORADO" not in texto
    assert "\r" not in texto


def test_transcricao_txt_reuniao_longa_usa_hora_no_horario():
    from trama.servidor import transcricao

    dados = _dados_para_txt()
    dados["falas"][-1] = {
        "falante": "Celso",
        "cluster": "S0",
        "inicio": 3725.0,
        "fim": 3730.0,
        "texto": "Fim.",
    }
    texto = transcricao.montar_texto("reuniao_13", dados)
    assert "Duração: 1 h 02 min\n" in texto
    assert "[0:00:04] Celso: Bom dia, todo mundo.\n" in texto
    assert "[1:02:05] Celso: Fim.\n" in texto


def test_transcricao_txt_data_so_do_arquivo_nunca_passa_por_data_da_reuniao():
    from datetime import timezone

    from trama.servidor import transcricao

    dados = _dados_para_txt(data_origem="arquivo", titulo="Comitê")
    texto = transcricao.montar_texto("reuniao_02", dados, fuso=timezone.utc)
    assert (
        "Data: não registrada na gravação (arquivo recebido em 4 de novembro de 2026)\n"
    ) in texto
    assert transcricao.nome_do_arquivo("reuniao_02", dados) == "Comitê.txt"


def test_transcricao_txt_nome_do_arquivo_com_data_e_sem_caractere_proibido():
    from datetime import timedelta, timezone

    from trama.servidor import transcricao

    fuso = timezone(timedelta(hours=-3))
    assert (
        transcricao.nome_do_arquivo("reuniao_13", _dados_para_txt(), fuso=fuso)
        == "2026-11-04 Reunião 13.txt"
    )
    perigoso = _dados_para_txt(titulo='../Q3: "riscos"/ok? <a>|b*\\c.')
    assert (
        transcricao.nome_do_arquivo("reuniao_13", perigoso, fuso=fuso)
        == "2026-11-04 Q3 riscos ok a b c.txt"
    )
    so_lixo = _dados_para_txt(titulo="/:*?")
    assert (
        transcricao.nome_do_arquivo("reuniao_13", so_lixo, fuso=fuso) == "2026-11-04 Reunião 13.txt"
    )
    longo = transcricao.nome_do_arquivo("reuniao_13", _dados_para_txt(titulo="x" * 300), fuso=fuso)
    assert len(longo) <= len("2026-11-04 ") + transcricao.NOME_ARQUIVO_MAX + len(".txt")


def test_transcricao_rota_gera_do_json_nao_do_txt_do_pipeline():
    pasta, cliente = _ambiente_temporario()
    try:
        p = _criar_reuniao_completa(
            reunioes.PASTA_AUDIOS, "reuniao_07", pessoas=("Clélia", "IGNORADO_S1")
        )
        j = p / "reuniao_07.json"
        dados = json.loads(j.read_text(encoding="utf-8"))
        dados.update(
            titulo="Comitê de produto", data_reuniao="2026-11-04T11:59:48Z", data_origem="gravacao"
        )
        j.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        (p / "reuniao_07.txt").write_text("TEXTO VELHO DO PIPELINE", encoding="utf-8")

        r = cliente.get("/api/reunioes/reuniao_07/transcricao")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "text/plain; charset=utf-8"
        cd = r.headers["content-disposition"]
        assert cd.startswith("attachment; "), cd
        assert "filename*=UTF-8''" in cd and "Comit%C3%AA%20de%20produto.txt" in cd, cd
        assert 'filename="' in cd and "Comite de produto.txt" in cd, cd
        corpo = r.content.decode("utf-8")
        assert corpo.startswith("Comitê de produto\nData: 4 de novembro de 2026"), corpo
        assert "] Clélia: Ola.\n" in corpo
        assert "- voz não atribuída: 30%\n" in corpo
        assert "TEXTO VELHO" not in corpo and "IGNORADO" not in corpo

        # editar o .json (revisao, glossario) muda o arquivo na hora
        dados["falas"][0]["texto"] = "Olá, corrigido."
        j.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        corpo = cliente.get("/api/reunioes/reuniao_07/transcricao").content.decode("utf-8")
        assert "] Clélia: Olá, corrigido.\n" in corpo
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# --------------------------------------------------------------------------
# correcao manual do texto de uma fala (edicao.py, ADR 0016)
# --------------------------------------------------------------------------


def _reuniao_para_corrigir(pasta_audios, id="reuniao_06"):
    """Duas falas; a primeira com todas as marcas de posicao e uma lacuna,
    a segunda com uma lacuna propria (que nao pode ser tocada)."""
    pasta = _criar_reuniao_completa(pasta_audios, id, pessoas=("Celso", "Amanda"))
    j = pasta / f"{id}.json"
    d = json.loads(j.read_text(encoding="utf-8"))
    texto = "a questão à vista ficou errada"
    d["falas"] = [
        {
            "falante": "Celso",
            "cluster": "S0",
            "inicio": 10.0,
            "fim": 14.0,
            "texto": texto,
            "confianca_media": 0.4,
            "palavras_divergentes": [{"posicao": 2, "comprimento": 7, "falante": "Amanda"}],
            "palavras_baixa_confianca": [{"posicao": 2, "comprimento": 7, "probabilidade": 0.3}],
            "palavras_tempo": [[0, 1, 10.0, 10.2], [2, 7, 10.2, 10.8]],
        },
        {
            "falante": "Amanda",
            "cluster": "S1",
            "inicio": 20.0,
            "fim": 25.0,
            "texto": "Concordo.",
            "palavras_tempo": [[0, 9, 20.0, 20.6]],
        },
    ]
    d["lacunas_sem_texto"] = [
        {"posicao": 9, "inicio": 11.0, "fim": 12.0, "falante": "Celso"},
        {"posicao": 0, "inicio": 21.0, "fim": 22.0, "falante": "Amanda"},
    ]
    j.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return j


def test_corrigir_fala_grava_texto_guarda_original_e_tira_marcas_de_posicao():
    pasta, cliente = _ambiente_temporario()
    try:
        j = _reuniao_para_corrigir(reunioes.PASTA_AUDIOS)
        r = cliente.put(
            "/api/reunioes/reuniao_06/falas/0",
            json={"texto": "  a Tabela à Vista ficou errada ", "inicio": 10.0},
        )
        assert r.status_code == 200, r.text
        resp = r.json()
        assert resp["fala"]["texto"] == "a Tabela à Vista ficou errada"
        assert resp["fala"]["edicao_manual"]["texto_original"] == "a questão à vista ficou errada"
        assert "marcas_originais" not in resp["fala"]["edicao_manual"], (
            "a tela nao recebe as marcas guardadas"
        )
        assert resp["lacunas_sem_texto"] == [
            {"posicao": 0, "inicio": 21.0, "fim": 22.0, "falante": "Amanda"}
        ]

        d = json.loads(j.read_text(encoding="utf-8"))
        f = d["falas"][0]
        for campo in ("palavras_divergentes", "palavras_baixa_confianca", "palavras_tempo"):
            assert campo not in f, f"{campo} ficou numa fala escrita a mao"
        assert f["confianca_media"] == 0.4, "confianca nao e marca de posicao"
        guardadas = f["edicao_manual"]["marcas_originais"]
        assert set(guardadas) == {
            "palavras_divergentes",
            "palavras_baixa_confianca",
            "palavras_tempo",
            "lacunas_sem_texto",
        }
        assert d["falas"][1]["palavras_tempo"] == [[0, 9, 20.0, 20.6]], "outra fala mexida"
        assert len(d["lacunas_sem_texto"]) == 1
        # o .txt do pipeline acompanha
        assert "Celso: a Tabela à Vista ficou errada" in j.with_suffix(".txt").read_text(
            encoding="utf-8"
        )
        # e o detalhe nao manda as marcas guardadas
        det = cliente.get("/api/reunioes/reuniao_06").json()
        assert det["falas"][0]["edicao_manual"] == {
            "texto_original": "a questão à vista ficou errada",
            "editado_em": f["edicao_manual"]["editado_em"],
        }
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_desfazer_correcao_devolve_a_fala_e_as_lacunas_exatamente_como_eram():
    pasta, cliente = _ambiente_temporario()
    try:
        j = _reuniao_para_corrigir(reunioes.PASTA_AUDIOS)
        antes = json.loads(j.read_text(encoding="utf-8"))
        cliente.put(
            "/api/reunioes/reuniao_06/falas/0", json={"texto": "primeira correção", "inicio": 10.0}
        )
        cliente.put(
            "/api/reunioes/reuniao_06/falas/0", json={"texto": "segunda correção", "inicio": 10.0}
        )
        r = cliente.delete("/api/reunioes/reuniao_06/falas/0/edicao?inicio=10.0")
        assert r.status_code == 200, r.text
        depois = json.loads(j.read_text(encoding="utf-8"))
        assert depois["falas"] == antes["falas"]
        assert depois["lacunas_sem_texto"] == antes["lacunas_sem_texto"]

        # escrever de volta exatamente o texto transcrito tambem desfaz
        cliente.put(
            "/api/reunioes/reuniao_06/falas/0", json={"texto": "outra coisa", "inicio": 10.0}
        )
        r = cliente.put(
            "/api/reunioes/reuniao_06/falas/0",
            json={"texto": "a questão à vista ficou errada", "inicio": 10.0},
        )
        assert "edicao_manual" not in r.json()["fala"]
        assert json.loads(j.read_text(encoding="utf-8"))["falas"] == antes["falas"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_corrigir_fala_recusa_em_portugues_sem_tocar_o_arquivo():
    pasta, cliente = _ambiente_temporario()
    try:
        j = _reuniao_para_corrigir(reunioes.PASTA_AUDIOS)
        antes = j.read_bytes()
        url = "/api/reunioes/reuniao_06/falas"
        r = cliente.put(f"{url}/0", json={"texto": "   ", "inicio": 10.0})
        assert r.status_code == 400 and "não pode ficar vazio" in r.json()["detail"]
        r = cliente.put(f"{url}/0", json={"texto": "duas\nlinhas", "inicio": 10.0})
        assert r.status_code == 400 and "quebra de linha" in r.json()["detail"]
        r = cliente.put(f"{url}/0", json={"texto": "x" * 5001, "inicio": 10.0})
        assert r.status_code == 400 and "máximo" in r.json()["detail"]
        # a fala daquele indice nao e mais a que a tela mostrava
        r = cliente.put(f"{url}/0", json={"texto": "ok", "inicio": 99.0})
        assert r.status_code == 409 and "Recarregue" in r.json()["detail"]
        r = cliente.put(f"{url}/7", json={"texto": "ok", "inicio": 10.0})
        assert r.status_code == 404 and "Recarregue" in r.json()["detail"]
        r = cliente.put("/api/reunioes/Reuniao.A/falas/0", json={"texto": "ok", "inicio": 10.0})
        assert r.status_code == 400
        assert j.read_bytes() == antes, "recusa mexeu no .json"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_glossario_reaplicado_nunca_sobrescreve_fala_corrigida():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("questão à vista => Tabela à Vista\n", encoding="utf-8")
        j = _reuniao_para_corrigir(reunioes.PASTA_AUDIOS)
        # a pessoa decidiu que, AQUI, "questão à vista" estava certo
        cliente.put(
            "/api/reunioes/reuniao_06/falas/0",
            json={"texto": "a questão à vista, mesmo, ficou errada", "inicio": 10.0},
        )
        previa = cliente.get("/api/termos/reaplicar").json()
        assert previa["total"] == 0, previa
        r = cliente.post("/api/termos/reaplicar", json={"assinatura": previa["assinatura"]})
        assert r.status_code == 200, r.text
        f = json.loads(j.read_text(encoding="utf-8"))["falas"][0]
        assert f["texto"] == "a questão à vista, mesmo, ficou errada"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_transcricao_baixada_usa_o_texto_corrigido():
    pasta, cliente = _ambiente_temporario()
    try:
        _reuniao_para_corrigir(reunioes.PASTA_AUDIOS)
        cliente.put(
            "/api/reunioes/reuniao_06/falas/0",
            json={"texto": "a Tabela à Vista ficou errada", "inicio": 10.0},
        )
        corpo = cliente.get("/api/reunioes/reuniao_06/transcricao").content.decode("utf-8")
        assert "[00:10] Celso: a Tabela à Vista ficou errada\n" in corpo, corpo
        assert "questão" not in corpo
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_transcricao_rota_nao_processada_ou_id_invalido_responde_em_portugues():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_a")
        r = cliente.get("/api/reunioes/reuniao_a/transcricao")
        assert r.status_code == 404
        assert "não há transcrição para baixar" in r.json()["detail"]

        assert cliente.get("/api/reunioes/reuniao_zz/transcricao").status_code == 404
        r = cliente.get("/api/reunioes/..%2Fvozes/transcricao")
        assert r.status_code in (400, 404), r.status_code
        r = cliente.get("/api/reunioes/Reuniao.A/transcricao")
        assert r.status_code == 400 and r.json()["detail"] == "Id de reunião inválido."
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_titulo_de_reuniao_na_fila_vai_para_o_meta_json():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_b")
        r = cliente.put("/api/reunioes/reuniao_b/titulo", json={"titulo": "Da Nova reunião"})
        assert r.status_code == 200, r.text
        meta = json.loads(
            (reunioes.PASTA_AUDIOS / "reuniao_b" / nucleo.NOME_META_REUNIAO).read_text(
                encoding="utf-8"
            )
        )
        assert meta == {"titulo": "Da Nova reunião"}
        assert cliente.get("/api/reunioes/reuniao_b").json()["titulo"] == "Da Nova reunião"
        assert not (reunioes.PASTA_AUDIOS / "reuniao_b" / "reuniao_b.json").exists()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_titulo_invalido_rejeitado_em_portugues_sem_tocar_o_arquivo():
    pasta, cliente = _ambiente_temporario()
    try:
        p = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        antes = (p / "reuniao_a.json").read_bytes()
        for ruim, trecho in (
            ("a" * 121, "máximo é 120"),
            ("linha\nquebrada", "caractere de controle"),
            ("tab\taqui", "caractere de controle"),
        ):
            r = cliente.put("/api/reunioes/reuniao_a/titulo", json={"titulo": ruim})
            assert r.status_code == 400, (ruim, r.text)
            assert trecho in r.json()["detail"], r.json()
        assert (
            cliente.put("/api/reunioes/reuniao_a/titulo", json={"titulo": "a" * 120}).status_code
            == 200
        )
        assert (p / "reuniao_a.json").read_bytes() != antes
        assert (
            cliente.put("/api/reunioes/nao_existe/titulo", json={"titulo": "x"}).status_code == 404
        )
        assert cliente.put("/api/reunioes/..%2Fetc/titulo", json={"titulo": "x"}).status_code in (
            400,
            404,
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_listar_traz_interacao_resumida_so_quando_ha_dinamica():
    pasta, cliente = _ambiente_temporario()
    try:
        p = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        j = p / "reuniao_a.json"
        d = json.loads(j.read_text(encoding="utf-8"))
        d["dinamica"]["Ramiro"]["interrompeu"] = 3
        d["dinamica"]["Amanda"]["interrompeu"] = 5
        d["dinamica"]["IGNORADO_S2"] = {"fala_s": 1.0, "fala_pct": 1.0, "interrompeu": 9}
        d["eventos"] = [{"tipo": "disputa"}, {"tipo": "apoio"}, {"tipo": "disputa"}]
        j.write_text(json.dumps(d), encoding="utf-8")
        _criar_reuniao_incompleta(reunioes.PASTA_AUDIOS, "reuniao_b")
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_c")

        por_id = {r["id"]: r for r in cliente.get("/api/reunioes").json()}
        assert por_id["reuniao_a"]["interacao"] == {
            "mais_interrompeu": {"pessoa": "Amanda", "vezes": 5},
            "disputas": 2,
        }
        assert por_id["reuniao_b"]["interacao"] is None
        assert por_id["reuniao_c"]["interacao"] is None
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
