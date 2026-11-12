"""
tests/test_servidor_trechos.py - Trechos para conferir (trama/trechos.py,
ADR 0028): a terceira etapa da revisao, a escolha dos trechos, o texto
gravado dentro da lacuna, "Nao da para entender" e o .txt baixado.

Parte das suites do servidor FastAPI (trama/servidor/, ADR 0004); a
infraestrutura comum esta em tests/servidor_apoio.py.

Uso:
    python tests/test_servidor_trechos.py
"""

import json
import shutil
import sys

import servidor_apoio  # noqa: F401 - isola o ambiente e instala os stubs ANTES do projeto
from servidor_apoio import _ambiente_temporario, _criar_reuniao_completa, erro_de, rodar_suite

from trama import trechos
from trama.servidor import reunioes


def _fala(inicio, fim, texto, confianca=None, falante="Celso"):
    f = {"falante": falante, "cluster": "S0", "inicio": inicio, "fim": fim, "texto": texto}
    if confianca is not None:
        f["confianca_media"] = confianca
    return f


def _lacuna(inicio, fim, posicao=0, falante="Celso"):
    return {"posicao": posicao, "inicio": inicio, "fim": fim, "falante": falante}


def _dados(falas, lacunas=()):
    return {
        "falas": falas,
        "lacunas_sem_texto": list(lacunas),
        "limiar_confianca_fala": 0.6,
        "min_palavras_confianca_fala": 4,
    }


QUATRO = "uma duas tres quatro"


# --------------------------------------------------------------------------
# escolha dos trechos
# --------------------------------------------------------------------------


def test_escolhe_as_3_falas_de_confianca_baixa_mais_longas_e_as_2_lacunas_mais_longas():
    falas = [
        _fala(0, 4, QUATRO, 0.4),  # 4 s
        _fala(10, 20, QUATRO, 0.5),  # 10 s
        _fala(30, 38, QUATRO, 0.3),  # 8 s
        _fala(40, 46, QUATRO, 0.55),  # 6 s
        _fala(50, 70, QUATRO, 0.9),  # confianca boa
        _fala(80, 99, "so tres palavras", 0.1),  # abaixo do piso de palavras
        _fala(100, 130, QUATRO + " cinco seis", 0.95),  # dona das lacunas
    ]
    lacunas = [
        _lacuna(101, 102.6),  # 1,6 s
        _lacuna(105, 106.4),  # 1,4 s: abaixo de 1,5
        _lacuna(110, 111.9),  # 1,9 s
        _lacuna(120, 121.7),  # 1,7 s
        _lacuna(12, 14),  # dentro de uma fala escolhida: fora
    ]
    itens = trechos.trechos_para_conferir(_dados(falas, lacunas))
    assert [(i["tipo"], i["inicio"]) for i in itens] == [
        ("fala", 10),
        ("fala", 30),
        ("fala", 40),
        ("lacuna", 110),
        ("lacuna", 120),
    ], itens
    assert len(itens) <= trechos.MAX_FALAS + trechos.MAX_LACUNAS


def test_lacuna_de_exatamente_1_5_s_entra():
    dados = _dados([_fala(0, 10, QUATRO, 0.9)], [_lacuna(2.0, 3.5)])
    assert [i["tipo"] for i in trechos.trechos_para_conferir(dados)] == ["lacuna"]


def test_respondido_corrigido_ou_ininteligivel_nao_volta():
    falas = [
        _fala(0, 10, QUATRO, 0.4),
        _fala(20, 30, QUATRO, 0.4),
        _fala(40, 50, QUATRO + " cinco", 0.9),
    ]
    falas[0]["edicao_manual"] = {"texto_original": QUATRO, "editado_em": "x"}
    falas[1]["ininteligivel"] = True
    lacunas = [_lacuna(41, 43), _lacuna(44, 46), _lacuna(1, 3)]
    lacunas[0]["texto_manual"] = "ja escrito"
    lacunas[1]["ininteligivel"] = True
    # a terceira esta numa fala corrigida a mao
    assert trechos.trechos_para_conferir(_dados(falas, lacunas)) == []


def test_reuniao_sem_limiar_gravado_nao_tem_fala_de_confianca_baixa():
    dados = {"falas": [_fala(0, 10, QUATRO, 0.1)], "lacunas_sem_texto": []}
    assert trechos.trechos_para_conferir(dados) == []


def test_item_de_lacuna_traz_contexto_e_audio_com_folga_dentro_da_fala():
    fala = _fala(10, 20, "antes da lacuna depois", 0.9)
    (item,) = trechos.trechos_para_conferir(_dados([fala], [_lacuna(11, 13, posicao=16)]))
    assert item["antes"] == "antes da lacuna " and item["depois"] == "depois"
    assert item["audio_inicio"] == 10 and item["audio_fim"] == 16
    assert item["indice"] == 0 and item["falante"] == "Celso"


# --------------------------------------------------------------------------
# texto corrido
# --------------------------------------------------------------------------


def test_texto_da_lacuna_entra_no_ponto_dela_sem_mexer_no_texto_da_fala():
    fala = _fala(0, 10, "Então a gente. Fechou", 0.9)
    lac = _lacuna(2, 4, posicao=14)
    lac["texto_manual"] = "vai assinar amanhã."
    outra = _lacuna(6, 8, posicao=21)  # sem texto: nada entra
    assert (
        trechos.texto_com_lacunas_escritas(fala, [lac, outra])
        == "Então a gente. vai assinar amanhã. Fechou"
    )
    assert fala["texto"] == "Então a gente. Fechou"


# --------------------------------------------------------------------------
# rotas
# --------------------------------------------------------------------------


def _reuniao(pasta_audios, id="reuniao_05"):
    pasta = _criar_reuniao_completa(pasta_audios, id, pessoas=("Celso", "Amanda"))
    j = pasta / f"{id}.json"
    d = json.loads(j.read_text(encoding="utf-8"))
    d.update(
        _dados(
            [
                _fala(10, 20, "Então a gente. Fechou o acordo", 0.95),
                _fala(30, 40, "isso aqui ficou meio confuso", 0.3, falante="Amanda"),
            ],
            [_lacuna(12, 14, posicao=14)],
        )
    )
    j.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return j


def test_rota_lista_escreve_na_lacuna_e_o_txt_baixado_traz_o_texto():
    pasta, cliente = _ambiente_temporario()
    try:
        j = _reuniao(reunioes.PASTA_AUDIOS)
        r = cliente.get("/api/reunioes/reuniao_05/trechos-para-conferir")
        assert r.status_code == 200, r.text
        assert [i["tipo"] for i in r.json()["itens"]] == ["lacuna", "fala"]

        r = cliente.put(
            "/api/reunioes/reuniao_05/lacunas",
            json={"inicio": 12, "fim": 14, "texto": "  vai assinar amanhã. "},
        )
        assert r.status_code == 200, r.text
        assert r.json()["lacuna"]["texto_manual"] == "vai assinar amanhã."

        d = json.loads(j.read_text(encoding="utf-8"))
        assert d["falas"][0]["texto"] == "Então a gente. Fechou o acordo", "fala intocada"
        assert d["lacunas_sem_texto"][0]["posicao"] == 14, "posicao intocada"
        assert "gente. vai assinar amanhã. Fechou" in j.with_suffix(".txt").read_text(
            encoding="utf-8"
        )
        txt = cliente.get("/api/reunioes/reuniao_05/transcricao").text
        assert "Celso: Então a gente. vai assinar amanhã. Fechou o acordo" in txt, txt
        # respondida: nao e perguntada de novo
        itens = cliente.get("/api/reunioes/reuniao_05/trechos-para-conferir").json()["itens"]
        assert [i["tipo"] for i in itens] == ["fala"]
        # o detalhe manda o texto escrito para a tela
        det = cliente.get("/api/reunioes/reuniao_05").json()
        assert det["lacunas_sem_texto"][0]["texto_manual"] == "vai assinar amanhã."
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_rota_nao_da_para_entender_em_fala_e_em_lacuna():
    pasta, cliente = _ambiente_temporario()
    try:
        j = _reuniao(reunioes.PASTA_AUDIOS)
        r = cliente.put(
            "/api/reunioes/reuniao_05/ininteligivel",
            json={"tipo": "fala", "indice": 1, "inicio": 30, "fim": 40},
        )
        assert r.status_code == 200, r.text
        r = cliente.put(
            "/api/reunioes/reuniao_05/ininteligivel",
            json={"tipo": "lacuna", "inicio": 12, "fim": 14},
        )
        assert r.status_code == 200, r.text
        d = json.loads(j.read_text(encoding="utf-8"))
        assert d["falas"][1]["ininteligivel"] is True
        assert d["lacunas_sem_texto"][0]["ininteligivel"] is True
        assert d["falas"][1]["texto"] == "isso aqui ficou meio confuso"
        r = cliente.get("/api/reunioes/reuniao_05/trechos-para-conferir")
        assert r.json()["itens"] == []
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_rota_recusa_texto_vazio_e_trecho_que_mudou_sem_tocar_o_arquivo():
    pasta, cliente = _ambiente_temporario()
    try:
        j = _reuniao(reunioes.PASTA_AUDIOS)
        antes = j.read_bytes()
        r = cliente.put(
            "/api/reunioes/reuniao_05/lacunas", json={"inicio": 12, "fim": 14, "texto": "  "}
        )
        assert r.status_code == 400 and erro_de(r)[0] == "fala_vazia", r.text
        r = cliente.put(
            "/api/reunioes/reuniao_05/lacunas", json={"inicio": 12, "fim": 15, "texto": "x"}
        )
        assert r.status_code == 409 and erro_de(r)[0] == "trecho_mudou", r.text
        r = cliente.put(
            "/api/reunioes/reuniao_05/ininteligivel",
            json={"tipo": "fala", "indice": 1, "inicio": 31, "fim": 40},
        )
        assert r.status_code == 409 and erro_de(r)[0] == "trecho_mudou", r.text
        r = cliente.put(
            "/api/reunioes/reuniao_05/ininteligivel",
            json={"tipo": "fala", "inicio": 30, "fim": 40},
        )
        assert r.status_code == 400, r.text
        assert j.read_bytes() == antes
        r = cliente.get("/api/reunioes/..%2Fx/trechos-para-conferir")
        assert r.status_code in (400, 404), r.text
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_corrigir_e_desfazer_a_fala_leva_e_devolve_o_texto_da_lacuna():
    pasta, cliente = _ambiente_temporario()
    try:
        j = _reuniao(reunioes.PASTA_AUDIOS)
        cliente.put(
            "/api/reunioes/reuniao_05/lacunas",
            json={"inicio": 12, "fim": 14, "texto": "escrito"},
        )
        cliente.put(
            "/api/reunioes/reuniao_05/falas/0", json={"texto": "Tudo reescrito.", "inicio": 10}
        )
        d = json.loads(j.read_text(encoding="utf-8"))
        assert d["lacunas_sem_texto"] == []
        guardada = d["falas"][0]["edicao_manual"]["marcas_originais"]["lacunas_sem_texto"]
        assert guardada[0]["texto_manual"] == "escrito"
        cliente.delete("/api/reunioes/reuniao_05/falas/0/edicao", params={"inicio": 10})
        d = json.loads(j.read_text(encoding="utf-8"))
        assert d["lacunas_sem_texto"][0]["texto_manual"] == "escrito"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
