"""
tests/test_interacao.py - Testes do modulo de sobreposicao e interrupcao.

Todos os cenarios sao construidos a mao, com a resposta conhecida. Sem audio,
sem modelo, rodam em milissegundos.

Uso:
    python tests/test_interacao.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _ambiente  # noqa: E402

_ambiente.isolar()

from trama import interacao as I  # noqa: E402

# ==========================================================================
# mesclar_turnos
# ==========================================================================


def test_mescla_fragmentos_do_mesmo_falante():
    """
    A diarizacao parte uma fala continua em muitos pedacos (respiracao,
    hesitacao). Sem mesclar, uma fala de 40s vira 15 'turnos' e qualquer
    contagem de interrupcao perde sentido.
    """
    turnos = [(0.0, 5.0, "A"), (5.2, 9.0, "A"), (9.3, 12.0, "A")]
    assert I.mesclar_turnos(turnos) == [(0.0, 12.0, "A")]


def test_nao_mescla_com_pausa_longa():
    turnos = [(0.0, 5.0, "A"), (20.0, 25.0, "A")]
    assert len(I.mesclar_turnos(turnos)) == 2


def test_mescla_nao_junta_falantes_diferentes():
    turnos = [(0.0, 5.0, "A"), (5.1, 9.0, "B")]
    r = I.mesclar_turnos(turnos)
    assert len(r) == 2 and {x[2] for x in r} == {"A", "B"}


# ==========================================================================
# sobreposicoes
# ==========================================================================


def test_sem_sobreposicao_quando_turnos_apenas_se_tocam():
    """Fim de um exatamente no inicio do outro NAO e falar por cima."""
    turnos = [(0.0, 5.0, "A"), (5.0, 10.0, "B")]
    assert I.sobreposicoes(turnos) == []


def test_detecta_sobreposicao_simples():
    turnos = [(0.0, 6.0, "A"), (4.0, 10.0, "B")]
    regioes = I.sobreposicoes(turnos)
    assert len(regioes) == 1
    ini, fim, atores = regioes[0]
    assert abs(ini - 4.0) < 1e-6 and abs(fim - 6.0) < 1e-6
    assert atores == ["A", "B"]


def test_ignora_sobreposicao_minuscula():
    """0.05s de sobreposicao e imprecisao de fronteira, nao gente falando junto."""
    turnos = [(0.0, 5.0, "A"), (4.95, 10.0, "B")]
    assert I.sobreposicoes(turnos) == []


def test_sobreposicao_de_tres_falantes():
    turnos = [(0.0, 10.0, "A"), (2.0, 8.0, "B"), (3.0, 6.0, "C")]
    regioes = I.sobreposicoes(turnos)
    assert len(regioes) == 1
    assert regioes[0][2] == ["A", "B", "C"]


# ==========================================================================
# classificacao dos eventos
# ==========================================================================


def test_apoio_nao_conta_como_interrupcao():
    """
    'uhum' de 0.4s durante fala longa e sinal de escuta. Contar como
    interrupcao inflaria os numeros de quem so concorda em voz alta.
    """
    turnos = [(0.0, 30.0, "A"), (10.0, 10.4, "B")]
    eventos = I.eventos_de_fala(turnos)
    assert len(eventos) == 1 and eventos[0]["tipo"] == "apoio"
    assert I.matriz_interrupcoes(eventos) == {}


def test_interrupcao_quando_quem_falava_cede():
    """B entra falando e A encerra logo depois: A cedeu a palavra."""
    turnos = [(0.0, 11.0, "A"), (10.0, 20.0, "B")]
    eventos = I.eventos_de_fala(turnos)
    assert len(eventos) == 1, eventos
    assert eventos[0]["tipo"] == "interrupcao"
    assert eventos[0]["entrante"] == "B" and eventos[0]["falava"] == "A"
    assert I.matriz_interrupcoes(eventos) == {"B": {"A": 1}}


def test_disputa_quando_ninguem_cede():
    """
    Os dois seguem falando por cima. E aqui que a transcricao degringola,
    porque as vozes se misturam no sinal - o caso da reuniao_05 as 05:25.
    """
    turnos = [(0.0, 30.0, "A"), (10.0, 25.0, "B")]
    eventos = I.eventos_de_fala(turnos)
    assert len(eventos) == 1 and eventos[0]["tipo"] == "disputa"
    assert I.matriz_interrupcoes(eventos) == {}, "disputa nao e interrupcao"


def test_troca_limpa_nao_gera_evento():
    turnos = [(0.0, 5.0, "A"), (5.5, 10.0, "B"), (10.5, 15.0, "A")]
    assert I.eventos_de_fala(turnos) == []


def test_direcao_da_interrupcao_nao_se_inverte():
    """Quem entra depois e o entrante, sempre. Erro de direcao acusaria a
    pessoa errada, o que e pior do que nao medir nada."""
    turnos = [(0.0, 21.0, "Amanda"), (20.0, 40.0, "Ramiro")]
    e = I.eventos_de_fala(turnos)[0]
    assert e["entrante"] == "Ramiro" and e["falava"] == "Amanda"

    turnos = [(0.0, 21.0, "Ramiro"), (20.0, 40.0, "Amanda")]
    e = I.eventos_de_fala(turnos)[0]
    assert e["entrante"] == "Amanda" and e["falava"] == "Ramiro"


# ==========================================================================
# dinamica
# ==========================================================================


def test_dinamica_soma_tempos_e_percentuais():
    turnos = [(0.0, 60.0, "A"), (60.0, 90.0, "B"), (90.0, 100.0, "A")]
    d = I.dinamica(turnos, [], [])
    assert d["A"]["fala_s"] == 70.0
    assert d["A"]["turnos"] == 2
    assert d["B"]["fala_pct"] == 30.0
    assert abs(d["A"]["fala_pct"] + d["B"]["fala_pct"] - 100.0) < 0.1


def test_dinamica_conta_interrupcoes_dos_dois_lados():
    turnos = [(0.0, 11.0, "A"), (10.0, 30.0, "B")]
    eventos = I.eventos_de_fala(turnos)
    regioes = I.sobreposicoes(turnos)
    d = I.dinamica(turnos, eventos, regioes)
    assert d["B"]["interrompeu"] == 1
    assert d["A"]["foi_interrompido"] == 1
    assert d["A"]["interrompeu"] == 0
    assert d["A"]["sobreposicao_s"] > 0


# ==========================================================================
# marcacao no transcript
# ==========================================================================


def test_em_sobreposicao_marca_fala_dentro_da_regiao():
    regioes = [(10.0, 20.0, ["A", "B"])]
    assert I.em_sobreposicao(12.0, 18.0, regioes) is True
    assert I.em_sobreposicao(0.0, 5.0, regioes) is False


def test_em_sobreposicao_exige_fracao_minima():
    """Fala de 40s que toca 1s de sobreposicao nao deve ser marcada inteira."""
    regioes = [(39.0, 40.0, ["A", "B"])]
    assert I.em_sobreposicao(0.0, 40.0, regioes) is False


# ==========================================================================
# recalcular (substitui o antigo renomear - key-swap pos-hoc que perdia dados
# quando dois labels apontavam para o mesmo nome)
# ==========================================================================


def test_recalcular_troca_labels_por_nomes():
    turnos = [(0.0, 11.0, "SPEAKER_00"), (10.0, 30.0, "SPEAKER_01")]
    mapa = {"SPEAKER_00": {"nome": "Amanda"}, "SPEAKER_01": {"nome": "Celso"}}
    r = I.recalcular(turnos, mapa)
    assert set(r["dinamica"]) == {"Amanda", "Celso"}
    assert r["matriz_interrupcoes"] == {"Celso": {"Amanda": 1}}
    assert r["eventos"][0]["entrante"] == "Celso"
    assert r["regioes_sobrepostas"][0]["falantes"] == ["Amanda", "Celso"]


def test_recalcular_dois_clusters_do_mesmo_nome_nao_perdem_tempo_de_fala():
    """
    REGRESSAO: o renomear() antigo so trocava chaves de dicionarios ja
    calculados por label. Se dois clusters iguais na pessoa (diarizacao
    dividiu alguem em dois, ou o revisao.py corrigiu os dois para o mesmo
    nome), o dict comprehension last-write-wins DESCARTAVA as estatisticas
    de um dos dois - reproducao sintetica: um cluster de 10s e outro de 20s
    terminavam em so 20s de fala para a pessoa.
    """
    turnos = [(0.0, 10.0, "SPEAKER_00"), (100.0, 120.0, "SPEAKER_01")]
    mapa = {"SPEAKER_00": {"nome": "Ramiro"}, "SPEAKER_01": {"nome": "Ramiro"}}
    r = I.recalcular(turnos, mapa)
    assert r["dinamica"]["Ramiro"]["fala_s"] == 30.0, r["dinamica"]
    assert r["dinamica"]["Ramiro"]["turnos"] == 2


def test_recalcular_dois_clusters_do_mesmo_nome_nao_geram_autoevento():
    """
    REGRESSAO: sobreposicao de tempo ENTRE dois clusters que o revisao.py
    corrigiu para a MESMA pessoa virava, depois da troca de nome, um evento
    de "pessoa interrompendo/disputando com ela mesma" - porque o calculo
    original rodava sobre os labels (diferentes), so a troca de nome vinha
    depois. Aqui os turnos sao renomeados ANTES de calcular: os dois viram
    um intervalo mesclado so, sem sobreposicao consigo mesmo.
    """
    turnos = [(0.0, 20.0, "SPEAKER_00"), (10.0, 25.0, "SPEAKER_01")]
    mapa = {"SPEAKER_00": {"nome": "Ramiro"}, "SPEAKER_01": {"nome": "Ramiro"}}
    r = I.recalcular(turnos, mapa)
    assert r["eventos"] == [], r["eventos"]
    assert r["regioes_sobrepostas"] == [], r["regioes_sobrepostas"]
    assert r["dinamica"]["Ramiro"]["fala_s"] == 25.0


def test_recalcular_preserva_intervalos_de_pessoas_diferentes():
    """Nomes diferentes continuam gerando eventos normalmente - o dedup e so
    para o MESMO nome."""
    turnos = [(0.0, 21.0, "SPEAKER_00"), (20.0, 40.0, "SPEAKER_01")]
    mapa = {"SPEAKER_00": {"nome": "Amanda"}, "SPEAKER_01": {"nome": "Ramiro"}}
    r = I.recalcular(turnos, mapa)
    assert len(r["eventos"]) == 1
    assert r["eventos"][0]["entrante"] == "Ramiro"
    assert r["eventos"][0]["falava"] == "Amanda"
    assert r["dinamica"]["Amanda"]["fala_s"] == 21.0
    assert r["dinamica"]["Ramiro"]["fala_s"] == 20.0


def test_recalcular_sem_mapa_mantem_labels():
    """Sem mapa (ou label ausente do mapa), cai de volta no label bruto -
    e assim que calibrar.py usa a mesma funcao para varredura offline."""
    turnos = [(0.0, 5.0, "SPEAKER_00")]
    r = I.recalcular(turnos, {})
    assert set(r["dinamica"]) == {"SPEAKER_00"}


# ==========================================================================
# cenario realista de ponta a ponta
# ==========================================================================


def test_cenario_reuniao_completo():
    """
    Reuniao curta com os quatro comportamentos: fala limpa, apoio, interrupcao
    bem-sucedida e disputa. Verifica o pipeline inteiro do modulo.
    """
    turnos_brutos = [
        (0.0, 20.0, "Celso"),  # fala limpa
        (20.3, 25.0, "Celso"),  # fragmento -> deve mesclar
        (8.0, 8.4, "Amanda"),  # apoio ("uhum")
        (24.0, 40.0, "Amanda"),  # entra e Celso cede -> interrupcao
        (50.0, 80.0, "Ramiro"),
        (60.0, 75.0, "Luciano"),  # ninguem cede -> disputa
    ]
    turnos = I.mesclar_turnos(turnos_brutos)
    regioes = I.sobreposicoes(turnos)
    eventos = I.eventos_de_fala(turnos)
    din = I.dinamica(turnos, eventos, regioes)

    # Celso mesclado: 0.0 -> 25.0
    celso = [t for t in turnos if t[2] == "Celso"]
    assert len(celso) == 1 and abs(celso[0][1] - 25.0) < 1e-6

    tipos = [e["tipo"] for e in eventos]
    assert "apoio" in tipos, tipos
    assert "interrupcao" in tipos, tipos
    assert "disputa" in tipos, tipos

    m = I.matriz_interrupcoes(eventos)
    assert m.get("Amanda", {}).get("Celso") == 1
    assert "Luciano" not in m, "disputa nao deve virar interrupcao"

    assert din["Amanda"]["apoios"] == 1
    assert din["Celso"]["foi_interrompido"] == 1
    # Duas regioes, nao tres: o apoio de 0.4s fica abaixo do limiar de regiao.
    # Correto - um "uhum" nao torna a transcricao menos confiavel. As regioes
    # existem para marcar trechos duvidosos no .txt, e backchannel nao e um.
    assert len(regioes) == 2, regioes


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
