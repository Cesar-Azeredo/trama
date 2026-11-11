"""
tests/test_servidor_revisao.py - POST /api/reunioes/{id}/revisao - a unica rota que escreve no vozes.db.

Parte das suites do servidor FastAPI (trama/servidor/, ADR 0004); a
infraestrutura comum esta em tests/servidor_apoio.py.

Uso:
    python tests/test_servidor_revisao.py
"""

import json
import shutil
import sys
from pathlib import Path

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
# POST /api/reunioes/{id}/revisao - a UNICA rota que escreve no vozes.db
# ==========================================================================


def test_revisao_confirmar_duas_vezes_pela_rota_nao_dobra_o_peso():
    """
    A idempotencia do ledger ja e testada por funcao em tests/test_review.py
    - este teste garante a MESMA propriedade pela ROTA HTTP: revisar a
    mesma reuniao duas vezes com a mesma resposta nao pode inflar o peso
    de ninguem.
    """
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("Ramiro", "Amanda"))
        corpo = {"nomes": {"S0": "Ramiro", "S1": "Amanda"}}

        r1 = cliente.post("/api/reunioes/reuniao_a/revisao", json=corpo)
        assert r1.status_code == 200, r1.text
        r2 = cliente.post("/api/reunioes/reuniao_a/revisao", json=corpo)
        assert r2.status_code == 200, r2.text

        pesos = {n: w for n, w, _ in nucleo.listar_pessoas()}
        assert pesos["Ramiro"] == 15.0, pesos  # 30s de fala_s * 0.5
        assert pesos["Amanda"] == 15.0, pesos
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_nomear_sem_aprender_poe_o_nome_e_nao_toca_o_ledger():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(
            reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("DESCONHECIDO_S0", "Amanda")
        )
        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao",
            json={"nomes": {"S0": "Luciano", "S1": "Amanda"}, "sem_aprender": ["S0"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["totais_aprendidos"] == {"Amanda": 15.0}

        dados = json.loads(
            (reunioes.PASTA_AUDIOS / "reuniao_a" / "reuniao_a.json").read_text(encoding="utf-8")
        )
        assert dados["clusters"]["S0"]["nome"] == "Luciano"
        assert dados["falas"][0]["falante"] == "Luciano"
        assert "Luciano" in (reunioes.PASTA_AUDIOS / "reuniao_a" / "reuniao_a.txt").read_text(
            encoding="utf-8"
        )
        assert {n for n, _, _ in nucleo.listar_pessoas()} == {"Amanda"}
        assert all(p != "Luciano" for _, p in nucleo.listar_contribuicoes())

        # a grade de Pessoas le isso como presenca CONFIRMADA (nomear sem
        # aprender ainda e confirmar quem estava la)
        nucleo.registrar_contribuicoes("outra", [("S0", "Luciano", [0.1, 0.2], 40.0)])
        d = cliente.get("/api/pessoas/participacao").json()
        luciano = next(p for p in d["pessoas"] if p["nome"] == "Luciano")
        assert luciano["participacao"] == {"reuniao_a": "confirmada"}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_de_novo_de_cluster_ignorado_com_campo_vazio_nao_cria_perfil():
    """REGRESSAO: rever uma reuniao com cluster ja IGNORADO_*, deixando o
    campo em branco, mantinha o nome IGNORADO_S0 e o APRENDIA como pessoa."""
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("Ramiro", "Amanda"))
        cliente.post("/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "-", "S1": "Amanda"}})
        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "", "S1": "Amanda"}}
        )
        assert r.status_code == 200, r.text
        nomes = {n for n, _, _ in nucleo.listar_pessoas()}
        assert nomes == {"Amanda"}, nomes
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_previa_mostra_o_que_sai_e_nao_grava_nada():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("Luciano", "Amanda"))
        cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Luciano", "S1": "Amanda"}}
        )
        json_antes = (reunioes.PASTA_AUDIOS / "reuniao_a" / "reuniao_a.json").read_text(
            encoding="utf-8"
        )
        pesos_antes = nucleo.listar_pessoas()

        corpo = {"nomes": {"S0": "-", "S1": "Ramiro"}}
        r = cliente.post("/api/reunioes/reuniao_a/revisao/previa", json=corpo)
        assert r.status_code == 200, r.text
        assert r.json()["efeitos"] == [
            {
                "cluster": "S0",
                "tipo": "remover",
                "pessoa": "Luciano",
                "peso_s": 15.0,
                "para": None,
                "perfil_some": True,
            },
            {
                "cluster": "S1",
                "tipo": "mover",
                "pessoa": "Amanda",
                "peso_s": 15.0,
                "para": "Ramiro",
                "perfil_some": True,
            },
        ]
        assert (reunioes.PASTA_AUDIOS / "reuniao_a" / "reuniao_a.json").read_text(
            encoding="utf-8"
        ) == json_antes
        assert nucleo.listar_pessoas() == pesos_antes
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_ignorar_ou_so_nomear_depois_de_aprender_tira_a_contribuicao():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("Luciano", "Amanda"))
        # base legada, do mesmo tamanho dos embeddings da reuniao de teste
        nucleo.upsert_pessoa("Amanda", [0.5, 0.1, 0.2], 100.0)
        cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Luciano", "S1": "Amanda"}}
        )
        assert dict((n, w) for n, w, _ in nucleo.listar_pessoas()) == {
            "Luciano": 15.0,
            "Amanda": 115.0,
        }

        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao/previa",
            json={"nomes": {"S0": "-", "S1": "Amanda"}, "sem_aprender": ["S1"]},
        )
        efeitos = {e["pessoa"]: e for e in r.json()["efeitos"]}
        assert efeitos["Luciano"]["perfil_some"] is True
        assert efeitos["Amanda"]["perfil_some"] is False, "tem base legada"

        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao",
            json={"nomes": {"S0": "-", "S1": "Amanda"}, "sem_aprender": ["S1"]},
        )
        assert r.status_code == 200, r.text
        assert dict((n, w) for n, w, _ in nucleo.listar_pessoas()) == {"Amanda": 100.0}
        assert nucleo.listar_contribuicoes() == []
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_previa_mostra_a_voz_nova_que_vai_ser_ensinada():
    """Nenhuma voz entra no banco sem a pessoa ver o numero: a previa de
    uma primeira revisao mostra o que vai ser ENSINADO (fala_s * 0,5, o
    mesmo peso que a gravacao usa). Ignorar sem nada aprendido antes nao
    e efeito; reconfirmar a mesma pessoa tambem nao."""
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("Luciano", "Amanda"))
        corpo = {"nomes": {"S0": "-", "S1": "Amanda"}}
        r = cliente.post("/api/reunioes/reuniao_a/revisao/previa", json=corpo)
        assert r.json() == {
            "efeitos": [
                {
                    "cluster": "S1",
                    "tipo": "ensinar",
                    "pessoa": "Amanda",
                    "peso_s": 15.0,
                    "para": None,
                    "perfil_some": False,
                }
            ]
        }
        cliente.post("/api/reunioes/reuniao_a/revisao", json=corpo)
        assert {n: w for n, w, _ in nucleo.listar_pessoas()} == {"Amanda": 15.0}, (
            "o numero da previa tem de ser o que entrou"
        )
        r = cliente.post("/api/reunioes/reuniao_a/revisao/previa", json=corpo)
        assert r.json() == {"efeitos": []}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_ignorar_tem_precedencia_sobre_sem_aprender():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("Ramiro", "Amanda"))
        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao",
            json={"nomes": {"S0": "-", "S1": "Amanda"}, "sem_aprender": ["S0"]},
        )
        assert r.status_code == 200, r.text
        dados = json.loads(
            (reunioes.PASTA_AUDIOS / "reuniao_a" / "reuniao_a.json").read_text(encoding="utf-8")
        )
        assert dados["clusters"]["S0"]["nome"] == "IGNORADO_S0"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_sem_campo_sem_aprender_continua_aprendendo_tudo():
    """Corpo antigo (so "nomes") continua valido - nada muda para quem ja
    chamava a rota assim."""
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("Ramiro", "Amanda"))
        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Ramiro", "S1": "Amanda"}}
        )
        assert r.status_code == 200, r.text
        assert r.json()["totais_aprendidos"] == {"Ramiro": 15.0, "Amanda": 15.0}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_nome_com_caractere_de_controle_e_rejeitado_antes_do_banco():
    """Nome com caractere de controle nao pode tocar disco nem banco -
    validacao acontece antes de ler o .json de verdade."""
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        original = (pasta_reuniao / "reuniao_a.json").read_text()

        r = cliente.post("/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Ramiro\x07"}})
        assert r.status_code == 400
        assert erro_de(r) == ("nome_com_controle", {})
        assert nucleo.listar_pessoas() == []
        assert (pasta_reuniao / "reuniao_a.json").read_text() == original
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_nome_acima_do_tamanho_maximo_e_rejeitado():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        r = cliente.post("/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "X" * 200}})
        assert r.status_code == 400
        assert erro_de(r) == ("nome_longo_demais", {"tamanho": 200, "maximo": 80})
        assert nucleo.listar_pessoas() == []
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_corrigir_pessoa_move_contribuicao_e_recalcula_os_dois_perfis():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("Ramiro", "Amanda"))
        cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Ramiro", "S1": "Amanda"}}
        )
        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Luciano", "S1": "Amanda"}}
        )
        assert r.status_code == 200, r.text

        pesos = {n: w for n, w, _ in nucleo.listar_pessoas()}
        assert pesos.get("Luciano") == 15.0, pesos
        assert "Ramiro" not in pesos, "Ramiro continua com um perfil apos a contribuicao ser movida"
        assert pesos.get("Amanda") == 15.0, pesos
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_reuniao_sem_reuniao_id_ganha_um_e_ele_persiste():
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        dados = json.loads((pasta_reuniao / "reuniao_a.json").read_text())
        del dados["reuniao_id"]
        (pasta_reuniao / "reuniao_a.json").write_text(json.dumps(dados, ensure_ascii=False))

        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Ramiro", "S1": "Amanda"}}
        )
        assert r.status_code == 200, r.text
        novo_id = r.json()["reuniao_id"]
        assert novo_id, "rota deveria ter devolvido um reuniao_id novo"

        dados_depois = json.loads((pasta_reuniao / "reuniao_a.json").read_text())
        assert dados_depois["reuniao_id"] == novo_id

        # segunda revisao usa o MESMO id (nao gera outro a cada chamada)
        r2 = cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Ramiro", "S1": "Amanda"}}
        )
        assert r2.json()["reuniao_id"] == novo_id
        pesos = {n: w for n, w, _ in nucleo.listar_pessoas()}
        assert pesos["Ramiro"] == 15.0, (
            "peso dobrou - a segunda revisao usou um reuniao_id diferente"
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_corrige_nome_nas_falas_e_reescreve_o_txt():
    """O ponto do marco 1: revisar pela tela tem que atualizar o que a
    tela de Detalhe mostra depois - falante nas falas e o .txt, nao so
    o cluster."""
    pasta, cliente = _ambiente_temporario()
    try:
        pasta_reuniao = _criar_reuniao_completa(
            reunioes.PASTA_AUDIOS, "reuniao_a", pessoas=("DESCONHECIDO_S0", "Amanda")
        )
        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Ramiro", "S1": "Amanda"}}
        )
        assert r.status_code == 200, r.text

        dados = json.loads((pasta_reuniao / "reuniao_a.json").read_text())
        assert dados["clusters"]["S0"]["nome"] == "Ramiro"
        assert dados["clusters"]["S0"]["confirmado"] is True
        assert dados["falas"][0]["falante"] == "Ramiro"

        texto_txt = (pasta_reuniao / "reuniao_a.txt").read_text()
        assert "Ramiro" in texto_txt

        detalhe = cliente.get("/api/reunioes/reuniao_a").json()
        assert detalhe["clusters"]["S0"]["nome"] == "Ramiro"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_falha_ao_preparar_arquivo_nao_toca_o_banco():
    """
    Ordem deliberada em revisao.aplicar_e_gravar: os arquivos sao
    PREPARADOS (escritos em temporario) ANTES do banco ser tocado. Se a
    preparacao falhar, o banco tem que continuar exatamente como estava -
    nunca "meio atualizado".
    """
    pasta, cliente = _ambiente_temporario()
    original_preparar = nucleo.preparar_escrita_atomica
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")

        def preparar_com_falha(*a, **kw):
            raise OSError("disco cheio (simulado)")

        nucleo.preparar_escrita_atomica = preparar_com_falha
        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Ramiro", "S1": "Amanda"}}
        )
        assert r.status_code == 500

        nucleo.preparar_escrita_atomica = original_preparar
        assert nucleo.listar_pessoas() == [], (
            "banco foi atualizado apesar da falha ao preparar os arquivos"
        )
    finally:
        nucleo.preparar_escrita_atomica = original_preparar
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_falha_ao_confirmar_arquivo_nao_corrompe_original_e_retentativa_e_segura():
    """
    Se a CONFIRMACAO (o os.replace do temporario por cima do real) falhar
    depois do banco ja ter sido gravado, o arquivo ORIGINAL tem que
    continuar intacto (nunca pela metade - e por isso que e um os.replace
    atomico, nao uma escrita direta). O banco ja registrou a contribuicao
    nesse ponto; repetir a mesma revisao e seguro (idempotente por
    reuniao_id+cluster) e fecha o arquivo corretamente na segunda vez.
    """
    pasta, cliente = _ambiente_temporario()
    original_confirmar = nucleo.confirmar_escrita_atomica
    try:
        pasta_reuniao = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_a")
        original_json = (pasta_reuniao / "reuniao_a.json").read_text()

        def confirmar_com_falha(tmp, caminho):
            if Path(caminho).suffix == ".json":
                raise OSError("falha simulada ao confirmar")
            return original_confirmar(tmp, caminho)

        nucleo.confirmar_escrita_atomica = confirmar_com_falha
        r = cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Ramiro", "S1": "Amanda"}}
        )
        assert r.status_code == 500

        assert (pasta_reuniao / "reuniao_a.json").read_text() == original_json, (
            "arquivo original foi corrompido por uma falha na confirmacao"
        )
        # o banco ja tinha sido gravado neste ponto - e o unico jeito de
        # saber, dado que a troca do arquivo e a ultima etapa da sequencia.
        pesos = {n: w for n, w, _ in nucleo.listar_pessoas()}
        assert pesos.get("Ramiro") == 15.0, pesos

        nucleo.confirmar_escrita_atomica = original_confirmar
        r2 = cliente.post(
            "/api/reunioes/reuniao_a/revisao", json={"nomes": {"S0": "Ramiro", "S1": "Amanda"}}
        )
        assert r2.status_code == 200, r2.text
        pesos_depois = {n: w for n, w, _ in nucleo.listar_pessoas()}
        assert pesos_depois["Ramiro"] == 15.0, "retentativa dobrou o peso em vez de ser idempotente"
    finally:
        nucleo.confirmar_escrita_atomica = original_confirmar
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_reuniao_nao_processada_da_404_em_portugues():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_b")
        r = cliente.post("/api/reunioes/reuniao_b/revisao", json={"nomes": {"S0": "Ramiro"}})
        assert r.status_code == 404
        assert erro_de(r) == ("sem_clusters_para_revisar", {})
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_revisao_id_invalido_e_rejeitado_antes_do_disco():
    pasta, cliente = _ambiente_temporario()
    try:
        r = cliente.post("/api/reunioes/..%2Fetc/revisao", json={"nomes": {}})
        assert r.status_code in (400, 404)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
