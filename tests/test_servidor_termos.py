"""
tests/test_servidor_termos.py - Glossario, correcao por texto, variacoes, termos da empresa e termos para conferir.

Parte das suites do servidor FastAPI (trama/servidor/, ADR 0004); a
infraestrutura comum esta em tests/servidor_apoio.py.

Uso:
    python tests/test_servidor_termos.py
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
from trama.servidor import glossario, reunioes

# ==========================================================================
# GET/PUT /api/termos - glossario
# ==========================================================================

TERMOS_EXEMPLO = """# cabecalho do arquivo
#
# --- ferramentas de IA ---
chat APT => ChatGPT
# CUIDADO: comente se falar de nuvem
o Claudio => o Claude

linha sem seta, malformada
matriz de goutes=>matriz GUT
"""


def test_termos_get_separa_regra_de_texto_na_ordem_do_arquivo():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EXEMPLO, encoding="utf-8")
        itens = cliente.get("/api/termos").json()["itens"]
        regras = [(i["errado"], i["certo"]) for i in itens if i["tipo"] == "regra"]
        assert regras == [
            ("chat APT", "ChatGPT"),
            ("o Claudio", "o Claude"),
            ("matriz de goutes", "matriz GUT"),
        ]
        textos = [i["texto"] for i in itens if i["tipo"] == "texto"]
        assert "# CUIDADO: comente se falar de nuvem" in textos
        assert "linha sem seta, malformada" in textos
        assert [i["tipo"] for i in itens][3:5] == ["regra", "texto"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_termos_get_bate_com_o_que_o_run_py_aplica():
    """A tela nunca pode mostrar como regra o que o pipeline.py nao aplica, nem
    esconder como texto o que ele aplica."""
    from trama import termos

    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EXEMPLO, encoding="utf-8")
        itens = cliente.get("/api/termos").json()["itens"]
        da_tela = [i["errado"] for i in itens if i["tipo"] == "regra"]
        do_run = [orig for _, _, orig in termos.carregar(glossario.CAMINHO)]
        assert da_tela == do_run
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_termos_get_sem_arquivo_devolve_lista_vazia():
    pasta, cliente = _ambiente_temporario()
    try:
        r = cliente.get("/api/termos")
        assert r.status_code == 200
        assert r.json() == {"itens": [], "descricoes": {}}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_termos_put_sem_mudanca_preserva_comentarios_e_ordem():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EXEMPLO, encoding="utf-8")
        itens = cliente.get("/api/termos").json()["itens"]
        r = cliente.put("/api/termos", json={"itens": itens})
        assert r.status_code == 200, r.text
        gravado = glossario.CAMINHO.read_text(encoding="utf-8")
        # unica diferenca aceita: a regra sem espaco sai normalizada
        assert gravado == TERMOS_EXEMPLO.replace(
            "matriz de goutes=>matriz GUT", "matriz de goutes => matriz GUT"
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_descricao_do_termo_vai_no_fim_do_arquivo_sem_mexer_no_resto():
    from trama import termos

    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EXEMPLO, encoding="utf-8")
        regras_antes = [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)]
        itens = cliente.get("/api/termos").json()["itens"]
        r = cliente.put(
            "/api/termos",
            json={
                "itens": itens,
                "descricoes": {"ChatGPT": "  assistente de IA da OpenAI ", "o Claude": ""},
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["descricoes"] == {"ChatGPT": "assistente de IA da OpenAI"}

        gravado = glossario.CAMINHO.read_text(encoding="utf-8")
        base = TERMOS_EXEMPLO.replace(
            "matriz de goutes=>matriz GUT", "matriz de goutes => matriz GUT"
        )
        assert gravado.startswith(base), "linha existente mudou"
        assert gravado[len(base) :].endswith("#= ChatGPT => assistente de IA da OpenAI\n"), gravado[
            len(base) :
        ]
        # o pipeline.py le exatamente as mesmas regras de antes
        assert [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)] == regras_antes

        # GET devolve; a secao nunca aparece como item da tela
        d = cliente.get("/api/termos").json()
        assert d["descricoes"] == {"ChatGPT": "assistente de IA da OpenAI"}
        assert d["itens"] == itens

        # PUT sem "descricoes" (corpo antigo) mantem as gravadas
        cliente.put("/api/termos", json={"itens": itens})
        assert glossario.CAMINHO.read_text(encoding="utf-8") == gravado
        # sem nenhuma descricao, a secao some e o arquivo volta a ser o de antes
        cliente.put("/api/termos", json={"itens": itens, "descricoes": {}})
        assert glossario.CAMINHO.read_text(encoding="utf-8") == base
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_termo_sem_regra_entra_so_no_vocabulario_e_fica_ate_ser_removido():
    from trama import termos

    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EXEMPLO, encoding="utf-8")
        regras_antes = [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)]
        itens = cliente.get("/api/termos").json()["itens"]
        r = cliente.put(
            "/api/termos",
            json={
                "itens": itens,
                "descricoes": {
                    "MQX": "empresa que fornece o servidor",
                    "ChatGPT": "assistente de IA",
                },
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["descricoes"] == {
            "ChatGPT": "assistente de IA",
            "MQX": "empresa que fornece o servidor",
        }
        # nenhuma regra nova: o pipeline.py le as mesmas de antes
        assert [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)] == regras_antes
        # vocabulario: termos das regras na ordem, depois os so com descricao
        assert glossario.vocabulario() == [
            ("ChatGPT", "assistente de IA"),
            ("Claude", None),
            ("matriz GUT", None),
            ("MQX", "empresa que fornece o servidor"),
        ]
        # remover a regra do ChatGPT nao apaga o que a empresa disse dele
        sem_chatgpt = [i for i in itens if i.get("certo") != "ChatGPT"]
        d = cliente.put(
            "/api/termos",
            json={
                "itens": sem_chatgpt,
                "descricoes": {
                    "MQX": "empresa que fornece o servidor",
                    "ChatGPT": "assistente de IA",
                },
            },
        ).json()
        assert "ChatGPT" in d["descricoes"]
        # descricao vazia: o termo continua conhecido, so sem descricao
        # ("#= MQX"); tirar da empresa e remover_termo, explicito
        d = cliente.put(
            "/api/termos", json={"itens": sem_chatgpt, "descricoes": {"MQX": "  "}}
        ).json()
        assert d["descricoes"] == {"MQX": ""}
        assert "#= MQX\n" in glossario.CAMINHO.read_text(encoding="utf-8")
        assert glossario.vocabulario() == [("Claude", None), ("matriz GUT", None), ("MQX", None)]
        glossario.remover_termo("MQX")
        assert [t for t, _ in glossario.vocabulario()] == ["Claude", "matriz GUT"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_descricao_invalida_e_recusada_em_portugues_sem_tocar_o_arquivo():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EXEMPLO, encoding="utf-8")
        itens = cliente.get("/api/termos").json()["itens"]
        for desc, trecho in [
            ("x" * 121, ("descricao_longa_demais", {"termo": "ChatGPT", "maximo": 120})),
            ("duas\nlinhas", ("descricao_com_quebra", {"termo": "ChatGPT"})),
        ]:
            r = cliente.put("/api/termos", json={"itens": itens, "descricoes": {"ChatGPT": desc}})
            assert r.status_code == 400 and erro_de(r) == trecho, r.text
        assert glossario.CAMINHO.read_text(encoding="utf-8") == TERMOS_EXEMPLO
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_termos_put_sem_descricao_nao_mexe_em_linha_em_branco_do_fim():
    pasta, cliente = _ambiente_temporario()
    try:
        original = "chat APT => ChatGPT\n\n"
        glossario.CAMINHO.write_text(original, encoding="utf-8")
        itens = cliente.get("/api/termos").json()["itens"]
        cliente.put("/api/termos", json={"itens": itens, "descricoes": {}})
        assert glossario.CAMINHO.read_text(encoding="utf-8") == original
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_transcricao_baixada_termina_com_o_vocabulario_da_empresa():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(
            "chat APT => ChatGPT\nchat EPT => ChatGPT\njornal da vista => Tabela à Vista\n"
            "do tabula da vista => da Tabela à Vista\nchatgpt => chatgpt\n"
            "# a Provium => Aprovio\napaga isto =>\n",
            encoding="utf-8",
        )
        itens = cliente.get("/api/termos").json()["itens"]
        cliente.put(
            "/api/termos",
            json={"itens": itens, "descricoes": {"Tabela à Vista": "painel de métricas do gestor"}},
        )
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_13")
        corpo = cliente.get("/api/reunioes/reuniao_13/transcricao").content.decode("utf-8")
        assert corpo.endswith(
            "] Ramiro: Ola.\n"
            "\n"
            "Vocabulário desta empresa\n"
            "Esta transcrição foi feita automaticamente. Alguns termos podem ter "
            "sido transcritos errado; use esta lista para interpretar. Antes de "
            "escrever a ata, liste os termos que parecem errados ou fora de "
            "contexto e pergunte o que significam.\n"
            "- ChatGPT\n"
            "- Tabela à Vista: painel de métricas do gestor\n"
        ), corpo
        # o artigo da regra de concordancia nao vira um termo a mais, e a
        # tela tem um campo so para "Tabela à Vista"
        assert cliente.get("/api/termos").json()["descricoes"] == {
            "Tabela à Vista": "painel de métricas do gestor"
        }
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_transcricao_baixada_sem_glossario_nao_tem_secao_de_vocabulario():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_13")
        corpo = cliente.get("/api/reunioes/reuniao_13/transcricao").content.decode("utf-8")
        assert "Vocabulário" not in corpo and corpo.endswith("] Ramiro: Ola.\n")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_termos_put_edita_remove_e_adiciona_regra():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EXEMPLO, encoding="utf-8")
        itens = cliente.get("/api/termos").json()["itens"]
        itens = [i for i in itens if i.get("errado") != "o Claudio"]
        for i in itens:
            if i.get("errado") == "chat APT":
                i["certo"] = "ChatGPT (editado)"
        itens.append({"tipo": "regra", "errado": "  cloud code ", "certo": "Claude Code"})
        r = cliente.put("/api/termos", json={"itens": itens})
        assert r.status_code == 200, r.text
        gravado = glossario.CAMINHO.read_text(encoding="utf-8")
        assert "chat APT => ChatGPT (editado)" in gravado
        assert "o Claudio" not in gravado
        assert gravado.rstrip("\n").endswith("cloud code => Claude Code")
        assert "# CUIDADO: comente se falar de nuvem" in gravado
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_termos_put_invalido_rejeita_em_portugues_sem_tocar_o_arquivo():
    casos = [
        {"tipo": "regra", "errado": "", "certo": "x"},
        {"tipo": "regra", "errado": "a => b", "certo": "x"},
        {"tipo": "regra", "errado": "# vira comentario", "certo": "x"},
        {"tipo": "regra", "errado": "quebra\nde linha", "certo": "x"},
        {"tipo": "regra", "errado": "a" * 201, "certo": "x"},
        {"tipo": "texto", "texto": "regra escondida => sim"},
        {"tipo": "outro"},
    ]
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EXEMPLO, encoding="utf-8")
        for ruim in casos:
            itens = [{"tipo": "regra", "errado": "ok", "certo": "OK"}, ruim]
            r = cliente.put("/api/termos", json={"itens": itens})
            assert r.status_code == 400, (ruim, r.text)
            assert erro_de(r)[1].get("linha") == 2, r.json()
            assert glossario.CAMINHO.read_text(encoding="utf-8") == TERMOS_EXEMPLO
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_termos_put_falha_na_escrita_mantem_o_arquivo_anterior():
    pasta, cliente = _ambiente_temporario()
    original = nucleo.confirmar_escrita_atomica
    try:
        glossario.CAMINHO.write_text(TERMOS_EXEMPLO, encoding="utf-8")

        def falha(*a, **k):
            raise OSError("disco cheio simulado")

        nucleo.confirmar_escrita_atomica = falha
        r = cliente.put(
            "/api/termos", json={"itens": [{"tipo": "regra", "errado": "a", "certo": "b"}]}
        )
        assert r.status_code == 500
        assert erro_de(r) == ("falha_gravar_glossario", {})
        assert glossario.CAMINHO.read_text(encoding="utf-8") == TERMOS_EXEMPLO
        sobras = [f for f in pasta.iterdir() if f.name != "termos.txt" and f.name != "audios"]
        assert not sobras, f"temporario orfao: {sobras}"
    finally:
        nucleo.confirmar_escrita_atomica = original
        shutil.rmtree(pasta, ignore_errors=True)


def _reuniao_com_texto(pasta_audios, id, texto, extras=None):
    pasta = _criar_reuniao_completa(pasta_audios, id)
    j = pasta / f"{id}.json"
    d = json.loads(j.read_text(encoding="utf-8"))
    d["falas"][0]["texto"] = texto
    d["falas"][0].update(extras or {})
    j.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return j


# --------------------------------------------------------------------------
# corrigir um termo pelo texto, em todas as reunioes (servidor/correcao.py)
# --------------------------------------------------------------------------


def _itens(*linhas):
    itens = []
    for l in linhas:
        if "=>" in l and not l.startswith("#"):
            e, c = (x.strip() for x in l.split("=>", 1))
            itens.append({"tipo": "regra", "errado": e, "certo": c})
        else:
            itens.append({"tipo": "texto", "texto": l})
    return itens


def _errados(itens):
    return [i.get("errado") or i.get("texto") for i in itens]


def test_correcao_entra_antes_da_regra_mais_geral_e_depois_da_mais_especifica():
    from trama.servidor import correcao

    # mais geral antes: a nova (especifica) entra antes dela
    itens, aviso = correcao.posicionar(
        _itens("chat APT => ChatGPT", "tabula da vista => Tabela à Vista", "# fim"),
        "do tabula da vista",
        "da Tabela à Vista",
    )
    assert _errados(itens) == ["chat APT", "do tabula da vista", "tabula da vista", "# fim"]
    assert aviso is None
    # mais especifica antes: a nova (geral) entra depois dela
    itens, aviso = correcao.posicionar(
        _itens(
            "do tabula da vista => da Tabela à Vista",
            "chat APT => ChatGPT",
            "# palpites",
            "# a Provium => Aprovion",
        ),
        "tabula da vista",
        "Tabela à Vista",
    )
    assert _errados(itens)[:3] == ["do tabula da vista", "chat APT", "tabula da vista"], (
        "sem relacao com nenhuma: depois da ultima regra, nunca no meio dos comentarios"
    )
    assert aviso is None
    # mesmo trecho (sem olhar acento nem maiuscula) ja corrigido: troca o certo no lugar
    itens, _ = correcao.posicionar(_itens("Aprovio => Aprovio", "x => y"), "aprovio", "Aprovion")
    assert [(i["errado"], i["certo"]) for i in itens] == [("Aprovio", "Aprovion"), ("x", "y")]


def test_correcao_sem_lugar_que_respeite_tudo_avisa_e_nao_quebra_o_que_existe():
    from trama.servidor import correcao

    itens, aviso = correcao.posicionar(
        _itens("tabula => T", "do tabula da vista => da Tabela à Vista"),
        "tabula da vista",
        "Tabela à Vista",
    )
    assert _errados(itens) == ["tabula", "do tabula da vista", "tabula da vista"]
    assert aviso == {
        "codigo": "correcao_existente_prevalece",
        "parametros": {"errado": "tabula", "certo": "T"},
    }


def _reuniao_para_correcao(id, textos, editada=None):
    pasta = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, id)
    j = pasta / f"{id}.json"
    d = json.loads(j.read_text(encoding="utf-8"))
    d["falas"] = [
        {"falante": "Ramiro", "cluster": "S0", "inicio": 10.0 * k, "fim": 10.0 * k + 5, "texto": tx}
        for k, tx in enumerate(textos)
    ]
    if editada is not None:
        d["falas"][editada]["edicao_manual"] = {
            "texto_original": "x",
            "editado_em": "2026-11-10T00:00:00Z",
            "marcas_originais": {},
        }
    j.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return j


def test_correcao_previa_conta_onde_trocaria_sem_gravar():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("chat apt => ChatGPT\n", encoding="utf-8")
        j1 = _reuniao_para_correcao("reuniao_08", ["o aprovium faz isso", "Aprovium não, ChatGPT"])
        _reuniao_para_correcao("reuniao_09", ["olhei a aprovium", "na aprovium editada"], editada=1)
        _reuniao_para_correcao("reuniao_10", ["nada aqui", "já é Aprovion"])
        antes = (j1.read_bytes(), glossario.CAMINHO.read_bytes())
        r = cliente.post(
            "/api/correcoes/previa", json={"trecho": " aprovium ", "certo": "Aprovion"}
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total"] == 3 and d["aviso"] is None
        assert [x["id"] for x in d["reunioes"]] == ["reuniao_08", "reuniao_09"]
        o = d["reunioes"][0]["ocorrencias"][1]
        assert (o["indice"], o["antes"], o["trecho"], o["depois"]) == (
            1,
            "",
            "Aprovium",
            " não, ChatGPT",
        )
        assert d["reunioes"][0]["titulo"] == "Reunião 08"
        assert (j1.read_bytes(), glossario.CAMINHO.read_bytes()) == antes, "previa gravou"
        r = cliente.post("/api/correcoes/previa", json={"trecho": "Aprovion", "certo": "Aprovion"})
        assert r.status_code == 400 and erro_de(r) == ("trecho_ja_certo", {})
        r = cliente.post("/api/correcoes/previa", json={"trecho": "  ", "certo": "x"})
        assert r.status_code == 400 and erro_de(r)[0].startswith("selecione_")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_correcao_aplica_so_a_nova_grava_descricao_e_vale_para_as_proximas():
    from trama import termos

    pasta, cliente = _ambiente_temporario()
    try:
        # uma regra salva e ainda nao aplicada: nao pode entrar de carona
        glossario.CAMINHO.write_text("chat apt => ChatGPT\n# comentario\n", encoding="utf-8")
        j = _reuniao_para_correcao("reuniao_08", ["o aprovium e o chat apt"])
        previa = cliente.post(
            "/api/correcoes/previa", json={"trecho": "aprovium", "certo": "Aprovion"}
        ).json()
        r = cliente.post(
            "/api/correcoes",
            json={
                "trecho": "aprovium",
                "certo": "Aprovion",
                "descricao": "ferramenta de aprovação",
                "assinatura": previa["assinatura"],
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["aplicadas"] == ["reuniao_08"] and r.json()["total"] == 1
        assert (
            json.loads(j.read_text(encoding="utf-8"))["falas"][0]["texto"]
            == "o Aprovion e o chat apt"
        )
        assert "Aprovion" in j.with_suffix(".txt").read_text(encoding="utf-8")
        # vale para as proximas: o pipeline.py le a regra nova
        assert [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)] == [
            ("chat apt", "ChatGPT"),
            ("aprovium", "Aprovion"),
        ]
        assert glossario.ler_descricoes() == {"Aprovion": "ferramenta de aprovação"}
        assert "# comentario" in glossario.CAMINHO.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_correcao_recusa_se_algo_mudou_desde_a_previa():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("", encoding="utf-8")
        j = _reuniao_para_correcao("reuniao_08", ["o aprovium"])
        previa = cliente.post(
            "/api/correcoes/previa", json={"trecho": "aprovium", "certo": "Aprovion"}
        ).json()
        _reuniao_para_correcao("reuniao_09", ["outra aprovium"])
        antes = glossario.CAMINHO.read_bytes()
        r = cliente.post(
            "/api/correcoes",
            json={"trecho": "aprovium", "certo": "Aprovion", "assinatura": previa["assinatura"]},
        )
        assert r.status_code == 409 and erro_de(r) == ("mudou_desde_conferencia", {})
        assert glossario.CAMINHO.read_bytes() == antes
        assert "aprovium" in j.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_descricao_de_um_termo_avulso_pela_rota():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("chat apt => ChatGPT\n", encoding="utf-8")
        r = cliente.put(
            "/api/termos/descricao",
            json={"termo": "da Tabela à Vista", "descricao": "painel do gestor"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["descricoes"] == {"Tabela à Vista": "painel do gestor"}
        assert glossario.CAMINHO.read_text(encoding="utf-8").startswith("chat apt => ChatGPT\n")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# --- variacoes parecidas (ADR 0020) ---------------------------------------


def _reunioes_para_variacoes():
    """Cinco reunioes com palavras comuns ("vale", "aprovação"), para o
    filtro de palavra comum ter o que medir."""
    comuns = "isso vale a aprovação do projeto"
    falas = {
        "reuniao_01": [comuns, "o aprovio faz isso", "não só a Provium e a ChatGPT"],
        "reuniao_02": [comuns, "a gente aprovou isso", "olhe o aprovio de novo"],
        "reuniao_03": [comuns, "o MKX paga o servidor", "a razão social da VQX"],
        "reuniao_04": [comuns, "isso já é Aprovion", "na MQX tem documento"],
        "reuniao_05": [comuns, "vale vale", "nada"],
    }
    for id, textos in falas.items():
        j = _reuniao_para_correcao(id, textos)
        if id == "reuniao_02":
            d = json.loads(j.read_text(encoding="utf-8"))
            texto = d["falas"][2]["texto"]
            pos = texto.index("aprovio")
            d["falas"][2]["palavras_baixa_confianca"] = [
                {"posicao": pos, "comprimento": 6, "probabilidade": 0.3}
            ]
            j.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def test_chave_de_som_e_distancia_das_variacoes():
    from trama.servidor import correcao

    assert correcao.chave_de_som("MKX") == correcao.chave_de_som("MQX")
    assert correcao.chave_de_som("Aprovium") != correcao.chave_de_som("Aprovion")
    assert correcao.distancia("aprovio", "aprvoio") == 1, "transposicao conta 1"
    assert correcao.distancia("provium", "aprovion") == 3  # +a, u->o, m->n


def test_variacoes_sugere_formas_parecidas_sem_palavra_comum():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("", encoding="utf-8")
        _reunioes_para_variacoes()
        r = cliente.post(
            "/api/correcoes/variacoes", json={"trecho": "aprovium", "certo": "Aprovion"}
        )
        assert r.status_code == 200, r.text
        v = {x["forma"]: x for x in r.json()["variacoes"]}
        assert set(v) == {"aprovio", "a Provium"}, v.keys()
        # com duvida do Whisper em UM lugar: entra, contando todos
        assert v["aprovio"]["total"] == 2 and v["aprovio"]["baixa_confianca"]
        assert r.json()["variacoes"][0]["forma"] == "aprovio", "duvida primeiro"
        # "a Provium" junto e o parecido; a correcao de "aprovium" nao o pega
        assert v["a Provium"]["ocorrencias"][0]["antes"] == "não só "
        # "aprovou": familia de "aprovação" (comum) e sem duvida - fora;
        # "vale", "Aprovion" (ja e o certo) - fora
        r = cliente.post("/api/correcoes/variacoes", json={"trecho": "MKX", "certo": "MQX"})
        assert [x["forma"] for x in r.json()["variacoes"]] == ["VQX"], r.json()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_variacoes_marcadas_viram_correcao_em_todas_e_as_outras_nao():
    from trama import termos

    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("", encoding="utf-8")
        _reunioes_para_variacoes()
        s = cliente.post(
            "/api/correcoes/variacoes", json={"trecho": "aprovium", "certo": "Aprovion"}
        ).json()
        r = cliente.post(
            "/api/correcoes/variacoes/aplicar",
            json={"certo": "Aprovion", "formas": [], "assinatura": s["assinatura"]},
        )
        assert r.status_code == 400 and erro_de(r) == ("marque_pelo_menos_uma", {})
        r = cliente.post(
            "/api/correcoes/variacoes/aplicar",
            json={"certo": "Aprovion", "formas": ["aprovio"], "assinatura": s["assinatura"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 2
        assert [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)] == [
            ("aprovio", "Aprovion")
        ]
        f1 = json.loads(
            (reunioes.PASTA_AUDIOS / "reuniao_01" / "reuniao_01.json").read_text(encoding="utf-8")
        )["falas"]
        assert f1[1]["texto"] == "o Aprovion faz isso"
        assert f1[2]["texto"] == "não só a Provium e a ChatGPT", "nao marcada foi trocada"
        # sugestao velha: recusa
        r = cliente.post(
            "/api/correcoes/variacoes/aplicar",
            json={"certo": "Aprovion", "formas": ["a Provium"], "assinatura": s["assinatura"]},
        )
        assert r.status_code == 409
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# --- Termos da empresa (ADR 0021) -------------------------------------------

TERMOS_EMPRESA = """# --- sistemas ---
aprovium => Aprovion
a Provium => Aprovion
do tabula da vista => da Tabela à Vista
tabula da vista => Tabela à Vista
# chutes:
# Rovio => Aprovion
"""


def test_termos_da_empresa_agrupa_variacoes_pelo_termo():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EMPRESA, encoding="utf-8")
        glossario.definir_descricao("MQX", "empresa que fornece o servidor")
        glossario.definir_descricao("Aprovion", "ferramenta de aprovação")
        r = cliente.get("/api/termos/empresa")
        assert r.status_code == 200, r.text
        assert r.json()["termos"] == [
            {
                "termo": "Aprovion",
                "descricao": "ferramenta de aprovação",
                "variacoes": [
                    {"errado": "aprovium", "certo": "Aprovion"},
                    {"errado": "a Provium", "certo": "Aprovion"},
                ],
            },
            {
                "termo": "Tabela à Vista",
                "descricao": "",
                "variacoes": [
                    {"errado": "do tabula da vista", "certo": "da Tabela à Vista"},
                    {"errado": "tabula da vista", "certo": "Tabela à Vista"},
                ],
            },
            {"termo": "MQX", "descricao": "empresa que fornece o servidor", "variacoes": []},
        ]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_adicionar_termo_sem_descricao_e_so_vocabulario_sem_mudar_regras():
    from trama import termos

    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EMPRESA, encoding="utf-8")
        regras = [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)]
        r = cliente.post("/api/termos/empresa", json={"termo": " Lumen ", "descricao": ""})
        assert r.status_code == 200, r.text
        assert {"termo": "Lumen", "descricao": "", "variacoes": []} in r.json()["termos"]
        assert "#= Lumen\n" in glossario.CAMINHO.read_text(encoding="utf-8")
        assert ("Lumen", None) in glossario.vocabulario()
        assert [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)] == regras
        # termo que ja existe (de uma variacao): so ganha a descricao
        r = cliente.post(
            "/api/termos/empresa", json={"termo": "aprovion", "descricao": "ferramenta"}
        )
        aprovion = [x for x in r.json()["termos"] if x["termo"] == "Aprovion"]
        assert len(aprovion) == 1 and aprovion[0]["descricao"] == "ferramenta"
        r = cliente.post("/api/termos/empresa", json={"termo": "  ", "descricao": "x"})
        assert r.status_code == 400 and erro_de(r) == ("escreva_nome_do_termo", {})
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_remover_variacao_e_termo_preserva_o_resto_do_arquivo():
    from trama import termos

    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(TERMOS_EMPRESA, encoding="utf-8")
        glossario.definir_descricao("Aprovion", "ferramenta")
        r = cliente.delete("/api/termos/variacao", params={"errado": "A PROVIUM"})
        assert r.status_code == 200, r.text
        assert [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)] == [
            ("aprovium", "Aprovion"),
            ("do tabula da vista", "da Tabela à Vista"),
            ("tabula da vista", "Tabela à Vista"),
        ]
        # remover o termo leva as variacoes e a descricao; comentarios ficam
        r = cliente.delete("/api/termos/empresa", params={"termo": "Tabela à Vista"})
        assert [x["termo"] for x in r.json()["termos"]] == ["Aprovion"]
        texto = glossario.CAMINHO.read_text(encoding="utf-8")
        assert "# chutes:\n# Rovio => Aprovion\n" in texto and "# --- sistemas ---" in texto
        r = cliente.delete("/api/termos/empresa", params={"termo": "Aprovion"})
        assert r.json()["termos"] == []
        assert glossario.vocabulario() == []
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_mesma_variacao_nunca_entra_duas_vezes_no_mesmo_termo():
    """Sem diferenciar maiuscula, acento nem espacamento - a mesma regra
    casaria o mesmo texto. Fica a primeira (a unica que dispara); a mesma
    forma para OUTRO termo nao e repeticao."""
    from trama import termos

    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(
            "# --- IA ---\n"
            "chat APT => ChatGPT\n"
            "short JVT => ChatGPT\n"
            "Chat  apt => ChatGPT\n"
            "chát APT => ChatGPT\n"
            "chat APT => outra coisa\n",
            encoding="utf-8",
        )
        # a tela ve uma vez so, mesmo antes de qualquer gravacao
        r = cliente.get("/api/termos/empresa")
        chatgpt = [t for t in r.json()["termos"] if t["termo"] == "ChatGPT"][0]
        assert [v["errado"] for v in chatgpt["variacoes"]] == ["chat APT", "short JVT"]
        # qualquer gravacao tira a repetida do arquivo
        glossario.definir_descricao("ChatGPT", "assistente de IA")
        assert [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)] == [
            ("chat APT", "ChatGPT"),
            ("short JVT", "ChatGPT"),
            ("chat APT", "outra coisa"),
        ]
        assert "# --- IA ---" in glossario.CAMINHO.read_text(encoding="utf-8")
        # e o PUT direto com repetida grava uma so
        itens = glossario.ler() + [{"tipo": "regra", "errado": "SHORT jvt", "certo": "ChatGPT"}]
        r = cliente.put("/api/termos", json={"itens": itens})
        assert r.status_code == 200, r.text
        errados = [i["errado"] for i in r.json()["itens"] if i["tipo"] == "regra"]
        assert errados == ["chat APT", "short JVT", "chat APT"], errados
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# --- termos para conferir na revisao (ADR 0022) ------------------------------


def _duvida(texto, palavra, n=0):
    """Marca de baixa confianca na n-esima ocorrencia de `palavra`."""
    pos = -1
    for _ in range(n + 1):
        pos = texto.index(palavra, pos + 1)
    return {"posicao": pos, "comprimento": len(palavra), "probabilidade": 0.3}


def _reuniao_para_conferir(id, falas):
    pasta = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, id)
    j = pasta / f"{id}.json"
    d = json.loads(j.read_text(encoding="utf-8"))
    d["falas"] = [
        {
            "falante": "Ramiro",
            "cluster": "S0",
            "inicio": 10.0 * k,
            "fim": 10.0 * k + 8,
            "texto": tx,
            "palavras_baixa_confianca": marcas,
            "palavras_tempo": [
                [tx.index(w), len(w), 10.0 * k + 1, 10.0 * k + 1.5]
                for w in set(tx.split())
                if w.isalpha()
            ],
        }
        for k, (tx, marcas) in enumerate(falas)
    ]
    j.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def test_termos_para_conferir_siglas_e_duvidas_repetidas_com_os_filtros():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("chat apt => ChatGPT\n", encoding="utf-8")
        glossario.adicionar_termo("MQX", "servidor")
        # "comum" aparece em 5 reunioes: palavra comum, nunca perguntada
        for n in range(2, 7):
            _reuniao_para_conferir(f"reuniao_0{n}", [("algo comum aqui", [])])
        t1 = "a IA e o MKX e a IA e de novo a IA"
        t2 = "o lucaz falou com lucaz sobre o tal comum e o tal"
        t3 = "o MQX e o ChatGPT e chat apt"
        _reuniao_para_conferir(
            "reuniao_01",
            [
                (t1, []),
                (
                    t2,
                    [
                        _duvida(t2, "lucaz"),
                        _duvida(t2, "lucaz", 1),
                        _duvida(t2, "comum"),
                        _duvida(t2, "tal"),
                        _duvida(t2, "tal", 1),
                    ],
                ),
                (t3, []),
            ],
        )
        r = cliente.get("/api/reunioes/reuniao_01/termos-para-conferir")
        assert r.status_code == 200, r.text
        itens = r.json()["itens"]
        assert [(i["forma"], i["total"]) for i in itens] == [("IA", 3), ("lucaz", 2), ("MKX", 1)], (
            itens
        )
        # fora: "comum" (5 reunioes), "tal" (curta), MQX (termo da empresa),
        # "chat apt"/ChatGPT (termo e variacao)
        o = itens[1]["ocorrencia"]
        assert (o["trecho"], o["duvida"]) == ("lucaz", True)
        assert t2[o["posicao"] : o["posicao"] + o["comprimento"]] == "lucaz"
        assert 10.0 <= o["audio_inicio"] < o["audio_fim"] <= 18.0, "audio fora da fala"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_resposta_dada_nunca_e_perguntada_de_novo_em_nenhuma_reuniao():
    from trama import termos

    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("chat apt => ChatGPT\n", encoding="utf-8")
        for id in ("reuniao_01", "reuniao_02"):
            _reuniao_para_conferir(id, [("a IA o SDR e o DAB", [])])
        assert cliente.post("/api/termos/respondido", json={"forma": "dab"}).status_code == 200
        glossario.adicionar_termo("IA", "inteligência artificial")
        for id in ("reuniao_01", "reuniao_02"):
            formas = [
                i["forma"]
                for i in cliente.get(f"/api/reunioes/{id}/termos-para-conferir").json()["itens"]
            ]
            assert formas == ["SDR"], formas
        texto = glossario.CAMINHO.read_text(encoding="utf-8")
        assert "#! dab\n" in texto and "#= IA => inteligência artificial\n" in texto
        assert [(o, c) for _, c, o in termos.carregar(glossario.CAMINHO)] == [
            ("chat apt", "ChatGPT")
        ]
        # marcar de novo nao duplica; salvar os termos pela tela nao perde
        cliente.post("/api/termos/respondido", json={"forma": "DAB"})
        glossario.definir_descricao("IA", "IA")
        assert glossario.ler_respondidos() == ["dab"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_no_maximo_dez_termos_para_conferir_os_mais_frequentes_primeiro():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("", encoding="utf-8")
        siglas = [f"S{chr(65 + k)}" for k in range(14)]
        texto = " ".join(s for k, s in enumerate(siglas) for _ in range(k + 1))
        _reuniao_para_conferir("reuniao_01", [(texto, [])])
        itens = cliente.get("/api/reunioes/reuniao_01/termos-para-conferir").json()["itens"]
        assert [i["forma"] for i in itens] == list(reversed(siglas))[:10]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_reaplicar_previa_conta_por_reuniao_e_nao_grava():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("chat apt => ChatGPT\n", encoding="utf-8")
        j1 = _reuniao_com_texto(reunioes.PASTA_AUDIOS, "reuniao_01", "o chat apt e o chat APT")
        _reuniao_com_texto(reunioes.PASTA_AUDIOS, "reuniao_02", "nada pra corrigir")
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_03")
        antes = j1.read_bytes()

        d = cliente.get("/api/termos/reaplicar").json()
        assert d["total"] == 2
        assert d["reunioes"] == [
            {"id": "reuniao_01", "substituicoes": 2, "por_termo": {"chat apt": 2}}
        ]
        assert j1.read_bytes() == antes, "previa nao pode gravar"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_reaplicar_grava_json_e_txt_com_posicoes_deslocadas():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("chat apt => ChatGPT\n", encoding="utf-8")
        texto = "o chat apt ajuda e a Amanda concorda"
        pos = texto.index("Amanda")
        j = _reuniao_com_texto(
            reunioes.PASTA_AUDIOS,
            "reuniao_01",
            texto,
            {
                "palavras_baixa_confianca": [
                    {"posicao": pos, "comprimento": 6, "probabilidade": 0.3}
                ]
            },
        )
        assinatura = cliente.get("/api/termos/reaplicar").json()["assinatura"]
        r = cliente.post("/api/termos/reaplicar", json={"assinatura": assinatura})
        assert r.status_code == 200, r.text
        assert r.json()["aplicadas"] == ["reuniao_01"]

        d = json.loads(j.read_text(encoding="utf-8"))
        f = d["falas"][0]
        assert f["texto"] == "o ChatGPT ajuda e a Amanda concorda"
        b = f["palavras_baixa_confianca"][0]
        assert f["texto"][b["posicao"] : b["posicao"] + 6] == "Amanda"
        assert "ChatGPT" in j.with_suffix(".txt").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_reaplicar_duas_vezes_nao_muda_nada_na_segunda():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text(
            "chat apt => ChatGPT\nepoca web => Epoca Web\n", encoding="utf-8"
        )
        j = _reuniao_com_texto(reunioes.PASTA_AUDIOS, "reuniao_01", "o chat apt no epoca web")
        a1 = cliente.get("/api/termos/reaplicar").json()["assinatura"]
        cliente.post("/api/termos/reaplicar", json={"assinatura": a1})
        depois_da_primeira = (j.read_bytes(), j.with_suffix(".txt").read_bytes())

        segunda = cliente.get("/api/termos/reaplicar").json()
        assert segunda["total"] == 0 and segunda["reunioes"] == []
        r = cliente.post("/api/termos/reaplicar", json={"assinatura": segunda["assinatura"]})
        assert r.status_code == 200 and r.json()["aplicadas"] == []
        assert (j.read_bytes(), j.with_suffix(".txt").read_bytes()) == depois_da_primeira
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_reaplicar_recusa_se_algo_mudou_desde_a_previa():
    pasta, cliente = _ambiente_temporario()
    try:
        glossario.CAMINHO.write_text("chat apt => ChatGPT\n", encoding="utf-8")
        j = _reuniao_com_texto(reunioes.PASTA_AUDIOS, "reuniao_01", "o chat apt")
        assinatura = cliente.get("/api/termos/reaplicar").json()["assinatura"]
        glossario.CAMINHO.write_text("chat apt => ChatGPT\nfoo => bar\n", encoding="utf-8")
        antes = j.read_bytes()
        r = cliente.post("/api/termos/reaplicar", json={"assinatura": assinatura})
        assert r.status_code == 409
        assert erro_de(r) == ("mudou_desde_previa", {})
        assert j.read_bytes() == antes
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
