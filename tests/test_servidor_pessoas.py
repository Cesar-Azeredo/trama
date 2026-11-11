"""
tests/test_servidor_pessoas.py - GET /api/pessoas, participacao e exclusao de pessoa (LGPD).

Parte das suites do servidor FastAPI (trama/servidor/, ADR 0004); a
infraestrutura comum esta em tests/servidor_apoio.py.

Uso:
    python tests/test_servidor_pessoas.py
"""

import json
import shutil
import sys

import servidor_apoio  # noqa: F401 - isola o ambiente e instala os stubs ANTES do projeto
from servidor_apoio import (
    _ambiente_temporario,
    _criar_reuniao_completa,
    _criar_reuniao_nao_processada,
    erro_de,
    rodar_suite,
)

from trama import nucleo
from trama.servidor import reunioes

# ==========================================================================
# GET /api/pessoas
# ==========================================================================


def test_pessoas_usa_banco_isolado_nunca_o_vozes_db_real():
    """
    REGRESSAO relatada: um smoke test manual chamou esta rota sem isolar
    nucleo.DB_PATH e migrou o vozes.db de PRODUCAO de verdade. Este teste fixa
    que a rota le nucleo.DB_PATH (redirecionavel), nao um caminho fixo.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        assert nucleo.DB_PATH == pasta / "vozes_teste.db"
        assert not nucleo.DB_PATH.exists(), (
            "banco de teste nao pode existir antes da primeira chamada"
        )
        r = cliente.get("/api/pessoas")
        assert r.status_code == 200
        assert r.json() == []
        assert nucleo.DB_PATH.exists(), "rota deveria ter criado o banco isolado"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_pessoas_reflete_a_galeria_cadastrada():
    pasta, cliente = _ambiente_temporario()
    try:
        nucleo.registrar_contribuicoes("reuniao-x", [("S0", "Ramiro", [0.1, 0.2], 20.0)])
        r = cliente.get("/api/pessoas")
        nomes = {p["nome"] for p in r.json()}
        assert nomes == {"Ramiro"}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_pessoas_primeira_aparicao_e_a_entrada_na_galeria_e_nao_muda():
    """
    Ordem estavel das cores de voz: uma pessoa nova entra no FIM. A data e
    a mais cedo entre base legada e contribuicoes, e uma contribuicao nova
    depois nao a move.
    """
    import sqlite3

    pasta, cliente = _ambiente_temporario()
    try:
        nucleo.upsert_pessoa("Amanda", [0.3, 0.1], 10.0)
        nucleo.registrar_contribuicoes("r1", [("S0", "Ramiro", [0.1, 0.2], 20.0)])
        con = sqlite3.connect(nucleo.DB_PATH)
        con.execute("UPDATE pessoas_legado SET migrado_em = '2026-09-16T00:00:00+00:00'")
        con.execute("UPDATE contribuicoes SET atualizado = '2026-09-20T00:00:00+00:00'")
        con.commit()
        con.close()
        nucleo.registrar_contribuicoes("r2", [("S0", "Amanda", [0.3, 0.2], 20.0)])

        d = {p["nome"]: p["primeira_aparicao"] for p in cliente.get("/api/pessoas").json()}
        assert d["Amanda"] == "2026-09-16T00:00:00+00:00", d
        assert d["Ramiro"] == "2026-09-20T00:00:00+00:00", d
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisada_so_quando_todos_os_clusters_tem_decisao():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_b")
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_c")
        # b: revisada so nomeando um e ignorando o outro - ainda e revisada
        r = cliente.post(
            "/api/reunioes/reuniao_b/revisao",
            json={"nomes": {"S0": "Ramiro", "S1": "-"}, "sem_aprender": ["S0"]},
        )
        assert r.status_code == 200, r.text

        por_id = {x["id"]: x for x in cliente.get("/api/reunioes").json()}
        assert por_id["reuniao_a"]["revisada"] is False
        assert por_id["reuniao_b"]["revisada"] is True
        assert por_id["reuniao_c"]["revisada"] is False
        assert cliente.get("/api/reunioes/reuniao_a").json()["revisada"] is False
        assert cliente.get("/api/reunioes/reuniao_b").json()["revisada"] is True

        # revisada por versao antiga (sem "confirmado"), mas com voz aprendida
        # de TODOS os clusters no ledger: conta como revisada
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_d")
        nucleo.registrar_contribuicoes(
            "uuid-reuniao_d",
            [("S0", "Ramiro", [0.1, 0.2, 0.3], 30.0), ("S1", "Amanda", [0.3, 0.2, 0.1], 30.0)],
        )
        assert cliente.get("/api/reunioes/reuniao_d").json()["revisada"] is True
        nucleo.registrar_contribuicoes("uuid-reuniao_d", [], retirar=["S1"])
        assert cliente.get("/api/reunioes/reuniao_d").json()["revisada"] is False

        # um cluster sem decisao basta para voltar a "a revisar"
        j = reunioes.PASTA_AUDIOS / "reuniao_b" / "reuniao_b.json"
        d = json.loads(j.read_text(encoding="utf-8"))
        d["clusters"]["S1"].pop("confirmado")
        j.write_text(json.dumps(d), encoding="utf-8")
        assert cliente.get("/api/reunioes/reuniao_b").json()["revisada"] is False
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_detalhe_diz_por_cluster_se_a_voz_esta_no_ledger():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        cliente.post(
            "/api/reunioes/reuniao_a/revisao",
            json={"nomes": {"S0": "Ramiro", "S1": "Amanda"}, "sem_aprender": ["S1"]},
        )
        c = cliente.get("/api/reunioes/reuniao_a").json()["clusters"]
        assert c["S0"]["voz_aprendida"] is True
        assert c["S1"]["voz_aprendida"] is False
        assert c["S1"]["sem_aprender"] is True
        assert "sem_aprender" not in c["S0"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_data_da_reuniao_vem_do_json_ou_do_audio_com_cache():
    """Processada: a data do .json (pipeline.py). Sem .json: a do audio, lida
    UMA vez e cacheada - a segunda listagem nao chama o ffprobe de novo."""
    pasta, cliente = _ambiente_temporario()
    original = nucleo.data_da_gravacao
    chamadas = []
    try:
        p = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        j = p / "reuniao_a.json"
        d = json.loads(j.read_text(encoding="utf-8"))
        d.update(
            {
                "data_reuniao": "2026-07-02T11:49:13Z",
                "data_origem": "gravacao",
                "titulo": "Planejamento",
            }
        )
        j.write_text(json.dumps(d), encoding="utf-8")
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_b")

        def contando(caminho):
            chamadas.append(caminho)
            return {"data": "2026-09-23T12:40:45Z", "origem": "arquivo"}

        nucleo.data_da_gravacao = contando

        por_id = {r["id"]: r for r in cliente.get("/api/reunioes").json()}
        assert (
            por_id["reuniao_a"]["data"],
            por_id["reuniao_a"]["data_origem"],
            por_id["reuniao_a"]["titulo"],
        ) == ("2026-07-02T11:49:13Z", "gravacao", "Planejamento")
        assert (
            por_id["reuniao_b"]["data"],
            por_id["reuniao_b"]["data_origem"],
            por_id["reuniao_b"]["titulo"],
        ) == ("2026-09-23T12:40:45Z", "arquivo", None)
        cliente.get("/api/reunioes")
        assert len(chamadas) == 1, "a segunda listagem chamou o ffprobe de novo"

        det = cliente.get("/api/reunioes/reuniao_a").json()
        assert (det["data"], det["data_origem"], det["titulo"]) == (
            "2026-07-02T11:49:13Z",
            "gravacao",
            "Planejamento",
        )
    finally:
        nucleo.data_da_gravacao = original
        shutil.rmtree(pasta, ignore_errors=True)


def test_titulo_grava_no_json_sem_tocar_o_resto_e_aparece_na_lista():
    pasta, cliente = _ambiente_temporario()
    try:
        p = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        j = p / "reuniao_a.json"
        antes = json.loads(j.read_text(encoding="utf-8"))

        r = cliente.put("/api/reunioes/reuniao_a/titulo", json={"titulo": "  Comitê de produto  "})
        assert r.status_code == 200, r.text
        assert r.json() == {"titulo": "Comitê de produto"}
        depois = json.loads(j.read_text(encoding="utf-8"))
        assert depois.pop("titulo") == "Comitê de produto"
        assert depois == antes, "gravar o titulo mexeu em outro campo do .json"
        assert cliente.get("/api/reunioes").json()[0]["titulo"] == "Comitê de produto"
        assert cliente.get("/api/reunioes/reuniao_a").json()["titulo"] == "Comitê de produto"

        # vazio volta ao padrao: o campo sai, nunca fica ""
        r = cliente.put("/api/reunioes/reuniao_a/titulo", json={"titulo": "   "})
        assert r.json() == {"titulo": None}
        assert "titulo" not in json.loads(j.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# DELETE /api/pessoas/{nome} - exclusao LGPD; GET /api/pessoas/participacao
# ==========================================================================


def _vetor_marcado(valor):
    """Vetor com um valor improvavel, para achar os bytes dele no arquivo."""
    import numpy as np

    return np.full(8, valor, dtype=np.float32)


def test_excluir_pessoa_apaga_perfil_ledger_e_legado_e_nao_toca_os_outros():
    import sqlite3

    pasta, cliente = _ambiente_temporario()
    try:
        nucleo.upsert_pessoa("Luciano", _vetor_marcado(0.123), 30.0)
        nucleo.registrar_contribuicoes(
            "r1",
            [
                ("S0", "Luciano", _vetor_marcado(0.123), 40.0),
                ("S1", "Amanda", _vetor_marcado(0.456), 40.0),
            ],
        )
        nucleo.registrar_contribuicoes("r2", [("S0", "Luciano", _vetor_marcado(0.123), 20.0)])
        peso_amanda = dict((n, p) for n, p, _ in nucleo.listar_pessoas())["Amanda"]

        r = cliente.delete("/api/pessoas/Luciano")
        assert r.status_code == 200, r.text
        assert r.json()["removidos"] == {
            "perfil": 1,
            "contribuicoes": 2,
            "legado": 1,
            "compactado": True,
        }

        con = sqlite3.connect(nucleo.DB_PATH)
        for tabela, coluna in (
            ("pessoas", "nome"),
            ("contribuicoes", "pessoa"),
            ("pessoas_legado", "nome"),
        ):
            n = con.execute(
                f"SELECT COUNT(*) FROM {tabela} WHERE {coluna} = ?", ("Luciano",)
            ).fetchone()[0]
            assert n == 0, tabela
        con.close()
        nomes = {p["nome"] for p in cliente.get("/api/pessoas").json()}
        assert nomes == {"Amanda"}
        assert dict((n, p) for n, p, _ in nucleo.listar_pessoas())["Amanda"] == peso_amanda
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_excluir_pessoa_nao_deixa_o_vetor_de_voz_legivel_no_arquivo():
    """DELETE no SQLite so marca pagina como livre - sem VACUUM, os bytes
    do vetor continuariam no arquivo. O vetor aqui e unico de proposito."""
    pasta, cliente = _ambiente_temporario()
    try:
        import numpy as np

        marca = np.full(64, 0.7777, dtype=np.float32).tobytes()
        nucleo.upsert_pessoa("Gerardo", np.full(64, 0.7777, dtype=np.float32), 30.0)
        nucleo.registrar_contribuicoes("r1", [("S9", "Outra", _vetor_marcado(0.2), 10.0)])
        # o vetor l2-normalizado e o que vai pro banco
        gravado = nucleo.l2(np.full(64, 0.7777, dtype=np.float32)).astype(np.float32).tobytes()
        assert gravado in nucleo.DB_PATH.read_bytes(), "premissa: vetor esta no arquivo"
        assert cliente.delete("/api/pessoas/Gerardo").status_code == 200
        conteudo = nucleo.DB_PATH.read_bytes()
        assert gravado not in conteudo and marca not in conteudo
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_excluir_pessoa_inexistente_da_404_em_portugues():
    pasta, cliente = _ambiente_temporario()
    try:
        r = cliente.delete("/api/pessoas/Ninguem")
        assert r.status_code == 404
        assert erro_de(r) == ("pessoa_nao_encontrada", {})
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_excluir_pessoa_nome_com_acento_e_espaco_pela_url():
    pasta, cliente = _ambiente_temporario()
    try:
        nucleo.registrar_contribuicoes("r1", [("S0", "Clélia Souza", _vetor_marcado(0.3), 10.0)])
        r = cliente.delete("/api/pessoas/Cl%C3%A9lia%20Souza")
        assert r.status_code == 200, r.text
        assert cliente.get("/api/pessoas").json() == []
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_participacao_tres_estados_por_celula():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_01", ("Ramiro", "Amanda"))
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_02", ("Amanda", "IGNORADO_S1"))
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_03")
        # Ramiro aprendido na 01; Amanda so nomeada na 01, aprendida na 02
        nucleo.registrar_contribuicoes(
            "uuid-reuniao_01", [("S0", "Ramiro", _vetor_marcado(0.1), 80.0)]
        )
        nucleo.registrar_contribuicoes(
            "uuid-reuniao_02", [("S0", "Amanda", _vetor_marcado(0.2), 30.0)]
        )

        d = cliente.get("/api/pessoas/participacao").json()
        assert d["reunioes"] == [
            {"id": "reuniao_01", "processada": True},
            {"id": "reuniao_02", "processada": True},
            {"id": "reuniao_03", "processada": False},
        ]
        por_nome = {p["nome"]: p for p in d["pessoas"]}
        assert [p["nome"] for p in d["pessoas"]] == ["Ramiro", "Amanda"], "por voz aprendida"
        assert por_nome["Ramiro"]["participacao"] == {"reuniao_01": "confirmada"}
        assert por_nome["Amanda"]["participacao"] == {
            "reuniao_01": "na_sala",
            "reuniao_02": "confirmada",
        }
        assert por_nome["Amanda"]["total_reunioes"] == 2
        assert por_nome["Amanda"]["ultima"] == "reuniao_02"
        assert "IGNORADO_S1" not in por_nome
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_participacao_confirmada_sem_aprender_e_preenchida_e_ignorado_e_contorno():
    """
    Novo significado da grade: preenchida = presenca confirmada na
    revisao, aprendendo ou nao (reunioes 01/03/05 foram revisadas com
    --sem-aprender). Contorno = na sala sem confirmacao, inclusive quem o
    pipeline tinha identificado num cluster ignorado.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        # vetores do MESMO tamanho dos embeddings das reunioes de teste (3) -
        # com tamanhos diferentes o recalculo do perfil falha, a revisao da
        # 02 nao grava, e o teste passaria pelo motivo errado (Luciano "na
        # sala" por nao revisado, nao por ignorado).
        nucleo.registrar_contribuicoes(
            "x",
            [
                ("S0", "Luciano", [0.1, 0.2, 0.3], 90.0),
                ("S1", "Amanda", [0.2, 0.1, 0.3], 80.0),
                ("S2", "Ramiro", [0.3, 0.2, 0.1], 70.0),
            ],
        )
        # 01: revisada so nomeando (confirmado, sem ledger)
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_01", ("Amanda", "Ramiro"))
        cliente.post(
            "/api/reunioes/reuniao_01/revisao",
            json={"nomes": {"S0": "Amanda", "S1": "Ramiro"}, "sem_aprender": ["S0", "S1"]},
        )
        # 02: Luciano identificado pelo pipeline, cluster ignorado pela rota
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_02", ("Luciano", "Amanda"))
        r = cliente.post(
            "/api/reunioes/reuniao_02/revisao", json={"nomes": {"S0": "-", "S1": "Amanda"}}
        )
        assert r.status_code == 200, r.text
        d2 = json.loads(
            (reunioes.PASTA_AUDIOS / "reuniao_02" / "reuniao_02.json").read_text(encoding="utf-8")
        )
        assert d2["clusters"]["S0"]["nome"] == "IGNORADO_S0"
        assert d2["clusters"]["S0"]["nome_antes_de_ignorar"] == "Luciano"
        # 03: ignorado ANTES de a revisao guardar o nome - so os scores
        pasta3 = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_03", ("Ramiro", "Amanda"))
        j = pasta3 / "reuniao_03.json"
        d = json.loads(j.read_text(encoding="utf-8"))
        d["clusters"]["S0"].update(
            {"nome": "IGNORADO_S0", "confirmado": True, "scores": {"Ramiro": 0.89, "Amanda": 0.33}}
        )
        d["clusters"]["S1"].update(
            {"nome": "IGNORADO_S1", "confirmado": True, "scores": {"Amanda": 0.55, "Ramiro": 0.50}}
        )
        j.write_text(json.dumps(d), encoding="utf-8")

        por_nome = {
            p["nome"]: p["participacao"]
            for p in cliente.get("/api/pessoas/participacao").json()["pessoas"]
        }
        assert por_nome["Amanda"]["reuniao_01"] == "confirmada"
        assert por_nome["Ramiro"]["reuniao_01"] == "confirmada"
        assert por_nome["Luciano"] == {"reuniao_02": "na_sala"}
        assert por_nome["Ramiro"]["reuniao_03"] == "na_sala"
        # abaixo de SIM_MIN nao vira ninguem
        assert "reuniao_03" not in por_nome["Amanda"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
