"""
tests/test_review.py - Ledger de contribuicoes de voz (nucleo.py) e o fluxo de
revisao idempotente (revisao.py).

Testa as FUNCOES REAIS - nucleo.registrar_contribuicoes, nucleo.upsert_pessoa,
nucleo.connect (com a migracao para pessoas_legado) e revisar.main() de ponta a
ponta, com um banco sqlite e um JSON de reuniao TEMPORARIOS. Nunca toca em
vozes.db nem em audio de verdade.

Uso:
    python tests/test_review.py
"""

import builtins
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import _ambiente  # noqa: E402

_ambiente.isolar()


# --------------------------------------------------------------------------
# stubs: mesma tecnica do test_pipeline.py - sem baixar modelo, sem tocar audio
# --------------------------------------------------------------------------


class Segment:
    def __init__(self, start, end):
        self.start, self.end = float(start), float(end)


def _instalar_stubs():
    for nome in ["torch", "pyannote", "pyannote.audio", "pyannote.core", "soundfile"]:
        sys.modules.setdefault(nome, types.ModuleType(nome))
    sys.modules["torch"].device = lambda x: x
    sys.modules["pyannote.audio"].Model = object
    sys.modules["pyannote.audio"].Inference = object
    sys.modules["pyannote.core"].Segment = Segment


_instalar_stubs()

from trama import (
    nucleo,  # noqa: E402
    revisao,  # noqa: E402
)
from trama.cli import revisar  # noqa: E402

# --------------------------------------------------------------------------
# infraestrutura de teste
# --------------------------------------------------------------------------


def _banco_temporario():
    """Aponta nucleo.DB_PATH para um sqlite descartavel. Retorna a pasta (para
    limpeza) - NUNCA toca no vozes.db real."""
    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-"))
    nucleo.DB_PATH = pasta / "vozes_teste.db"
    return pasta


def _vetor(seed, dim=8):
    return np.random.RandomState(seed).randn(dim).astype(np.float32)


def _reuniao_fixture(pasta, reuniao_id="reuniao-teste-1", nome_sugerido="DESCONHECIDO_S0"):
    """
    JSON minimo, mas estruturalmente igual ao que o pipeline.py grava: um cluster
    so, sugestao fraca, um turno bruto e um txt correspondente.
    """
    emb = _vetor(1).tolist()
    dados = {
        "audio": str(pasta / "reuniao.wav"),
        "reuniao_id": reuniao_id,
        "wav16k": str(pasta / "reuniao_16k.wav"),
        "clusters": {
            "S0": {
                "nome": nome_sugerido,
                "sim": 0.1,
                "margem": 0.0,
                "fala_s": 30.0,
                "embedding": emb,
                "scores": {},
            },
        },
        "falas": [
            {
                "falante": nome_sugerido,
                "cluster": "S0",
                "inicio": 0.0,
                "fim": 5.0,
                "texto": "Ola pessoal, bom dia.",
            },
        ],
        "turnos": [[0.0, 5.0, "S0"]],
        "dinamica": {},
        "matriz_interrupcoes": {},
        "eventos": [],
        "regioes_sobrepostas": [],
    }
    p = pasta / "reuniao.json"
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def _rodar_review(json_path, respostas, sem_aprender=False, confirmar="s"):
    """Roda revisar.main() de verdade, com input() e sys.argv trocados.

    `respostas`: uma por cluster ("Quem e?"). `confirmar`: a resposta ao
    "Confirmar? [s/N]" que o CLI faz quando a revisao muda voz aprendida
    (inclusive ensinando voz nova - revisao.efeitos_no_ledger)."""
    respostas_iter = iter(respostas)

    def fake_input(prompt=""):
        if prompt.startswith("Confirmar?"):
            return confirmar
        return next(respostas_iter)

    argv_antigo, input_antigo = sys.argv, builtins.input
    sys.argv = ["revisao.py", str(json_path)] + (["--sem-aprender"] if sem_aprender else [])
    builtins.input = fake_input
    try:
        revisar.main()
    finally:
        sys.argv, builtins.input = argv_antigo, input_antigo


# ==========================================================================
# revisao.selecionar_trechos - amostras para ouvir na revisao
# ==========================================================================


def _fala(cluster, inicio, fim, texto="fala de teste"):
    return {"falante": cluster, "cluster": cluster, "inicio": inicio, "fim": fim, "texto": texto}


def test_selecionar_trechos_prefere_duracao_entre_4_e_15s():
    """
    REGRESSAO: o criterio antigo escolhia os 3 trechos com MAIS
    caracteres de texto, o que podia incluir um monologo de varios
    minutos - no terminal a linha era truncada em 90 caracteres e o
    problema nao aparecia; na tela de revisao, o cartao de uma fala
    dessas virava tres telas de rolagem para uma decisao de segundos.
    """
    falas = [
        _fala("S0", 0, 300, "monologo gigante"),  # 300s, fora da faixa
        _fala("S0", 400, 408, "trecho bom 1"),  # 8s
        _fala("S0", 500, 510, "trecho bom 2"),  # 10s
        _fala("S0", 600, 605, "trecho bom 3"),  # 5s
    ]
    trechos = revisao.selecionar_trechos(falas, "S0", n=3)
    duracoes = [f["fim"] - f["inicio"] for f in trechos]
    assert all(revisao.DURACAO_MIN_TRECHO <= d <= revisao.DURACAO_MAX_TRECHO for d in duracoes), (
        duracoes
    )
    assert all(f["texto"] != "monologo gigante" for f in trechos)


def test_selecionar_trechos_espalha_no_tempo_inicio_meio_fim():
    """As amostras vem de partes DIFERENTES da reuniao, nao das primeiras
    falas boas que aparecerem - tres amostras espalhadas dizem mais sobre
    a voz de alguem do que tres do mesmo trecho da conversa."""
    falas = (
        [_fala("S0", i * 20, i * 20 + 5) for i in range(5)]  # comeco: 0-100s
        + [_fala("S0", 5000, 5008)]  # meio
        + [_fala("S0", 9990, 9998)]  # fim
    )
    trechos = revisao.selecionar_trechos(falas, "S0", n=3)
    inicios = sorted(f["inicio"] for f in trechos)
    assert inicios[0] < 100, "deveria ter uma amostra do comeco"
    assert 4000 < inicios[1] < 6000, "deveria ter uma amostra do meio"
    assert inicios[2] > 9000, "deveria ter uma amostra do fim"


def test_selecionar_trechos_sem_candidato_na_faixa_cai_para_o_mais_proximo():
    """Cluster so tem falas curtas demais (< 4s): nao trava nem devolve
    vazio - usa o que existe, mais perto da faixa ideal."""
    falas = [_fala("S0", 0, 1), _fala("S0", 10, 11.5), _fala("S0", 20, 21)]
    trechos = revisao.selecionar_trechos(falas, "S0", n=3)
    assert len(trechos) == 3


def test_selecionar_trechos_nao_repete_a_mesma_fala():
    falas = [_fala("S0", 0, 5), _fala("S0", 10, 15)]
    trechos = revisao.selecionar_trechos(falas, "S0", n=3)
    assert len(trechos) == len(falas) == 2
    assert len({id(f) for f in trechos}) == len(trechos)


def test_selecionar_trechos_cluster_sem_falas_devolve_vazio():
    assert revisao.selecionar_trechos([], "S0") == []


# ==========================================================================
# nucleo.registrar_contribuicoes - idempotencia e correcao
# ==========================================================================


def test_confirmar_de_novo_nao_dobra_o_peso():
    """
    REGRESSAO relatada: revisar a mesma reuniao duas vezes reaplicava a
    contribuicao ao perfil - peso 20 virava 40 na segunda revisao, sem audio
    novo. A chave primaria (reuniao_id, cluster) tem de fazer a segunda
    chamada SUBSTITUIR a primeira, nao somar.
    """
    pasta = _banco_temporario()
    try:
        emb = _vetor(1)
        contribs = [("S0", "Ramiro", emb, 20.0)]
        t1 = nucleo.registrar_contribuicoes("reuniao-1", contribs)
        t2 = nucleo.registrar_contribuicoes("reuniao-1", contribs)
        assert t1["Ramiro"] == 20.0, t1
        assert t2["Ramiro"] == 20.0, t2
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_corrigir_pessoa_move_contribuicao_sem_contaminar_a_antiga():
    """Corrigir S0 de Ramiro para Amanda tem de TIRAR a contribuicao do
    perfil de Ramiro (nao deixar residuo) e SOMAR ao de Amanda."""
    pasta = _banco_temporario()
    try:
        emb = _vetor(2)
        nucleo.registrar_contribuicoes("reuniao-1", [("S0", "Ramiro", emb, 20.0)])
        totais = nucleo.registrar_contribuicoes("reuniao-1", [("S0", "Amanda", emb, 20.0)])

        assert totais["Amanda"] == 20.0
        nomes = {n for n, _, _ in nucleo.listar_pessoas()}
        assert "Amanda" in nomes
        assert "Ramiro" not in nomes, "Ramiro continua com um perfil apos a contribuicao ser movida"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_contribuicoes_de_reunioes_diferentes_se_somam():
    """Sanidade: isto NAO deveria ficar tao restrito que reunioes distintas
    parem de reforcar o mesmo perfil."""
    pasta = _banco_temporario()
    try:
        nucleo.registrar_contribuicoes("reuniao-1", [("S0", "Ramiro", _vetor(3), 20.0)])
        totais = nucleo.registrar_contribuicoes("reuniao-2", [("S0", "Ramiro", _vetor(4), 20.0)])
        assert totais["Ramiro"] == 40.0, totais
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# migracao para pessoas_legado
# ==========================================================================


def test_enroll_apos_migracao_nao_se_perde_no_proximo_recalculo():
    """
    REGRESSAO evitada por design: se um cadastro manual (upsert_pessoa)
    escrevesse direto em `pessoas` em vez da base legada, a proxima
    contribuicao de reuniao (que recalcula `pessoas` = legado + ledger)
    apagaria silenciosamente o que o cadastro_avulso.py acabou de gravar.
    """
    pasta = _banco_temporario()
    try:
        nucleo.upsert_pessoa("Luciano", _vetor(6), peso=90.0)
        # Uma contribuicao de reuniao para OUTRA pessoa dispara recalculo
        # geral só da pessoa afetada - aqui simulamos o pior caso chamando
        # o recalculo de Luciano diretamente, como uma 2a revisao faria.
        con = nucleo.connect()
        total = nucleo._recompute_pessoa(con, "Luciano")
        con.commit()
        con.close()
        assert total == 90.0, (
            "cadastro manual foi perdido no recalculo - upsert_pessoa "
            "nao esta gravando na base legada"
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# revisao.py de ponta a ponta
# ==========================================================================


def test_review_repetido_nao_dobra_peso_end_to_end():
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        _rodar_review(p, ["Ramiro"])
        _rodar_review(p, ["Ramiro"])  # revisar de novo, mesma resposta

        pesos = dict((n, w) for n, w, _ in nucleo.listar_pessoas())
        assert pesos.get("Ramiro") == 15.0, pesos  # 30s * 0.5 de reducao
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_mudanca_de_pessoa_atualiza_os_dois_perfis():
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        _rodar_review(p, ["Ramiro"])
        # corrige quem era o cluster S0 - mover voz aprendida pede
        # confirmacao ("s")
        _rodar_review(p, ["Amanda"])

        pesos = dict((n, w) for n, w, _ in nucleo.listar_pessoas())
        assert pesos.get("Amanda") == 15.0, pesos
        assert "Ramiro" not in pesos, pesos

        dados = json.loads(p.read_text(encoding="utf-8"))
        assert dados["clusters"]["S0"]["nome"] == "Amanda"
        assert dados["falas"][0]["falante"] == "Amanda"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_renomeia_pista_de_divergencia_e_lacuna():
    """REGRESSAO: a revisao trocava o falante das falas e deixava as pistas
    de divergencia e as lacunas com o nome sugerido de antes - na tela, um
    DESCONHECIDO_S0 em cinza onde ja havia uma pessoa confirmada."""
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        dados = json.loads(p.read_text(encoding="utf-8"))
        dados["falas"][0]["palavras_divergentes"] = [
            {"posicao": 0, "comprimento": 3, "falante": "DESCONHECIDO_S0", "cluster": "S0"}
        ]
        dados["lacunas_sem_texto"] = [
            {"posicao": 0, "inicio": 1.0, "fim": 2.0, "falante": "DESCONHECIDO_S0"}
        ]
        p.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        _rodar_review(p, ["Ramiro"])

        dados = json.loads(p.read_text(encoding="utf-8"))
        assert dados["falas"][0]["palavras_divergentes"][0]["falante"] == "Ramiro"
        # lacuna antiga (sem "cluster"): pelo nome antigo, que era de um cluster so
        assert dados["lacunas_sem_texto"][0]["falante"] == "Ramiro"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_renomear_marcas_por_cluster_e_sem_chute_no_nome_ambiguo():
    """Marca com cluster: pelo cluster, mesmo com dois clusters de mesmo
    nome. Marca antiga sem cluster: so pelo nome que era de UM cluster."""
    dados = {
        "clusters": {
            "S0": {"nome": "Diego"},
            "S1": {"nome": "Diego"},
            "S2": {"nome": "DESCONHECIDO_S2"},
        },
        "falas": [
            {
                "palavras_divergentes": [
                    {"falante": "Diego", "cluster": "S1"},
                    {"falante": "Diego"},
                    {"falante": "DESCONHECIDO_S2"},
                ]
            }
        ],
        "lacunas_sem_texto": [
            {"falante": "Diego", "cluster": "S0"},
            {"falante": "Outro", "cluster": "S9"},
        ],
    }
    revisao._renomear_marcas(dados, {"S0": "Diego", "S1": "Tiago", "S2": "Helena"})
    d = dados["falas"][0]["palavras_divergentes"]
    assert [m["falante"] for m in d] == ["Tiago", "Diego", "Helena"]
    assert [m["falante"] for m in dados["lacunas_sem_texto"]] == ["Diego", "Outro"]


def test_review_ignorar_depois_de_aprender_tira_a_voz_com_confirmacao():
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        _rodar_review(p, ["Ramiro"])
        antes = p.read_text(encoding="utf-8")

        try:
            _rodar_review(p, ["-"], confirmar="n")  # recusa: nada gravado
            raise AssertionError("deveria ter saido sem gravar")
        except SystemExit:
            pass
        assert p.read_text(encoding="utf-8") == antes
        assert {n for n, _, _ in nucleo.listar_pessoas()} == {"Ramiro"}

        _rodar_review(p, ["-"])
        assert nucleo.listar_pessoas() == [], "voz do cluster ignorado ficou no perfil"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_remapear_contribuicoes_segue_o_label_novo_e_isola_orfas():
    """Reprocessar renumerou SPEAKER_00 <-> SPEAKER_01 e SPEAKER_02 sumiu:
    cada contribuicao vai para o label novo do MESMO audio (sem colidir na
    troca), a de SPEAKER_02 continua valendo para a pessoa mas nunca mais
    e lida como se fosse de um cluster novo, e nenhum perfil muda."""
    pasta = _banco_temporario()
    try:
        nucleo.registrar_contribuicoes(
            "r",
            [
                ("SPEAKER_00", "Ramiro", _vetor(1), 20.0),
                ("SPEAKER_01", "Amanda", _vetor(2), 20.0),
                ("SPEAKER_02", "Celso", _vetor(3), 20.0),
            ],
        )
        nucleo.registrar_contribuicoes("outra", [("SPEAKER_00", "Luciano", _vetor(4), 20.0)])
        pesos_antes = nucleo.listar_pessoas()

        n = nucleo.remapear_contribuicoes(
            "r", {"SPEAKER_00": "SPEAKER_01", "SPEAKER_01": "SPEAKER_00"}
        )
        assert n == 3
        atual = nucleo.contribuicoes_da_reuniao("r")
        assert atual["SPEAKER_01"][0] == "Ramiro"
        assert atual["SPEAKER_00"][0] == "Amanda"
        orfas = [c for c in atual if c.startswith("orfao-SPEAKER_02-")]
        assert len(orfas) == 1 and atual[orfas[0]][0] == "Celso"
        assert nucleo.contribuicoes_da_reuniao("outra") == {"SPEAKER_00": ("Luciano", 20.0)}
        assert nucleo.listar_pessoas() == pesos_antes
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_sem_aprender_grava_a_decisao_no_cluster():
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        _rodar_review(p, ["Ramiro"], sem_aprender=True)
        dados = json.loads(p.read_text(encoding="utf-8"))
        assert all(
            c.get("sem_aprender")
            for c in dados["clusters"].values()
            if not c["nome"].startswith("IGNORADO")
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_primeira_revisao_mostra_a_voz_nova_e_recusar_nao_grava():
    """Nenhuma voz entra no banco sem a pessoa ver o numero antes: ensinar
    voz nova tambem pede confirmacao, e "n" nao grava nada."""
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        antes = p.read_text(encoding="utf-8")
        try:
            _rodar_review(p, ["Ramiro"], confirmar="n")
            raise AssertionError("deveria ter saido sem gravar")
        except SystemExit:
            pass
        assert nucleo.listar_pessoas() == []
        assert p.read_text(encoding="utf-8") == antes
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_sem_aprender_corrige_texto_mas_nao_toca_perfil():
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        _rodar_review(p, ["Ramiro"], sem_aprender=True)

        assert nucleo.listar_pessoas() == []
        dados = json.loads(p.read_text(encoding="utf-8"))
        assert dados["clusters"]["S0"]["nome"] == "Ramiro"
        assert dados["falas"][0]["falante"] == "Ramiro"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_recupera_apos_falha_no_banco_sem_corromper_json():
    """
    Se a atualizacao do banco falhar no meio, o JSON/TXT NAO podem ser
    reescritos com uma correcao que o banco nao registrou - senao os dois
    ficam inconsistentes e a inconsistencia nao seria detectavel depois. A
    execucao seguinte, sem a falha, tem de completar normalmente.
    """
    pasta = _banco_temporario()
    p = _reuniao_fixture(pasta)
    original = p.read_text(encoding="utf-8")

    original_fn = nucleo.registrar_contribuicoes
    nucleo.registrar_contribuicoes = lambda *a, **kw: (_ for _ in ()).throw(
        RuntimeError("disco cheio (simulado)")
    )
    try:
        try:
            _rodar_review(p, ["Ramiro"])
            assert False, "revisar.main() deveria ter abortado"
        except SystemExit:
            pass
        assert p.read_text(encoding="utf-8") == original, (
            "JSON foi alterado mesmo com falha no banco"
        )
        assert nucleo.listar_pessoas() == []
    finally:
        nucleo.registrar_contribuicoes = original_fn
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_recupera_e_completa_apos_segunda_tentativa():
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        original = p.read_text(encoding="utf-8")

        original_fn = nucleo.registrar_contribuicoes
        nucleo.registrar_contribuicoes = lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("disco cheio (simulado)")
        )
        try:
            _rodar_review(p, ["Ramiro"])
        except SystemExit:
            pass
        finally:
            nucleo.registrar_contribuicoes = original_fn

        assert p.read_text(encoding="utf-8") == original

        _rodar_review(p, ["Ramiro"])  # tentativa seguinte, sem falha
        dados = json.loads(p.read_text(encoding="utf-8"))
        assert dados["clusters"]["S0"]["nome"] == "Ramiro"
        pesos = dict((n, w) for n, w, _ in nucleo.listar_pessoas())
        assert pesos.get("Ramiro") == 15.0, pesos
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_gera_reuniao_id_estavel_para_arquivo_antigo():
    """JSON sem 'reuniao_id' (arquivo de antes desta mudanca) recebe um
    agora, gravado IMEDIATAMENTE - antes do proprio processo de revisao -
    para que uma segunda execucao reuse o mesmo id em vez de gerar outro."""
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        dados = json.loads(p.read_text(encoding="utf-8"))
        del dados["reuniao_id"]
        p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

        _rodar_review(p, ["Ramiro"])
        id1 = json.loads(p.read_text(encoding="utf-8"))["reuniao_id"]
        assert id1

        _rodar_review(p, ["Ramiro"])
        id2 = json.loads(p.read_text(encoding="utf-8"))["reuniao_id"]
        assert id1 == id2, "reuniao_id nao pode mudar entre revisoes"

        pesos = dict((n, w) for n, w, _ in nucleo.listar_pessoas())
        assert pesos.get("Ramiro") == 15.0, pesos
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_recalcula_dinamica_apos_correcao_de_nome():
    """
    REGRESSAO: a revisao alterava falas/clusters mas deixava a dinamica com
    o nome SUGERIDO antigo. Aqui a reuniao tem dois clusters que a revisao
    aponta para a MESMA pessoa - a dinamica final tem de refletir o nome
    corrigido e somar os dois, nao perder um dos dois nem gerar autoevento.
    """
    pasta = _banco_temporario()
    try:
        p = pasta / "reuniao2.json"
        dados = {
            "reuniao_id": "r2",
            "clusters": {
                "S0": {
                    "nome": "DESCONHECIDO_S0",
                    "sim": 0.1,
                    "margem": 0.0,
                    "fala_s": 30.0,
                    "embedding": _vetor(9).tolist(),
                    "scores": {},
                },
                "S1": {
                    "nome": "DESCONHECIDO_S1",
                    "sim": 0.1,
                    "margem": 0.0,
                    "fala_s": 25.0,
                    "embedding": _vetor(10).tolist(),
                    "scores": {},
                },
            },
            "falas": [
                {
                    "falante": "DESCONHECIDO_S0",
                    "cluster": "S0",
                    "inicio": 0.0,
                    "fim": 10.0,
                    "texto": "Parte um.",
                },
                {
                    "falante": "DESCONHECIDO_S1",
                    "cluster": "S1",
                    "inicio": 100.0,
                    "fim": 120.0,
                    "texto": "Parte dois.",
                },
            ],
            "turnos": [[0.0, 10.0, "S0"], [100.0, 120.0, "S1"]],
            "dinamica": {},
            "matriz_interrupcoes": {},
            "eventos": [],
            "regioes_sobrepostas": [],
        }
        p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

        _rodar_review(p, ["Ramiro", "Ramiro"], sem_aprender=True)
        saida = json.loads(p.read_text(encoding="utf-8"))
        assert saida["dinamica"]["Ramiro"]["fala_s"] == 30.0, saida["dinamica"]
        assert saida["eventos"] == [], saida["eventos"]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_arquivo_antigo_sem_turnos_avisa_e_nao_inventa():
    """Sem 'turnos' no JSON (versao antiga do pipeline.py), revisao.py nao pode
    recalcular dinamica/eventos - tem de avisar em vez de inventar dado."""
    pasta = _banco_temporario()
    try:
        p = _reuniao_fixture(pasta)
        dados = json.loads(p.read_text(encoding="utf-8"))
        del dados["turnos"]
        p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

        _rodar_review(p, ["Ramiro"], sem_aprender=True)
        saida = json.loads(p.read_text(encoding="utf-8"))
        assert any("turnos" in a for a in saida.get("avisos", [])), saida.get("avisos")
        assert saida["clusters"]["S0"]["nome"] == "Ramiro"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_review_txt_reaproveita_exportador_com_marcadores():
    """O TXT reescrito pela revisao tem de vir do MESMO exportador do
    pipeline.py (marcador de sobreposicao inclusive), nao de um write ad-hoc."""
    pasta = _banco_temporario()
    try:
        p = pasta / "reuniao3.json"
        dados = {
            "reuniao_id": "r3",
            "clusters": {
                "S0": {
                    "nome": "Ramiro",
                    "sim": 0.9,
                    "margem": 0.5,
                    "fala_s": 30.0,
                    "embedding": [],
                    "scores": {},
                    "confirmado": True,
                },
            },
            "falas": [
                {
                    "falante": "Ramiro",
                    "cluster": "S0",
                    "inicio": 10.0,
                    "fim": 20.0,
                    "texto": "Fala com sobreposicao.",
                },
            ],
            # Um segundo cluster (sem entrada em "clusters" - simula alguem
            # nao identificado) sobrepondo o mesmo intervalo, para que o
            # recalculo de revisao.py REPRODUZA a regiao sobreposta a partir
            # dos turnos crus, em vez de depender de um valor pre-calculado.
            "turnos": [[10.0, 20.0, "S0"], [10.0, 18.0, "S1"]],
            "dinamica": {},
            "matriz_interrupcoes": {},
            "eventos": [],
            "regioes_sobrepostas": [],
        }
        p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

        _rodar_review(p, [""], sem_aprender=True)  # aceita o nome sugerido
        txt = p.with_suffix(".txt").read_text(encoding="utf-8")
        assert "[vozes sobrepostas]" in txt, txt
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================


def _rodar():
    testes = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = []
    for nome, fn in testes:
        try:
            fn()
            print(f"  \033[92mPASSOU\033[0m  {nome}")
        except AssertionError as e:
            falhas.append(nome)
            print(f"  \033[91mFALHOU\033[0m  {nome}\n            {e}")
        except Exception as e:
            falhas.append(nome)
            print(f"  \033[91mERRO\033[0m    {nome}\n            {type(e).__name__}: {e}")
    print(f"\n{len(testes) - len(falhas)}/{len(testes)} passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(_rodar())
