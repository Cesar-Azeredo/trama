"""
tests/test_pipeline.py - Testes de regressao da logica pura.

Roda em segundos, sem baixar modelo, sem tocar audio. Cobre as partes onde os
bugs de verdade apareceram: alinhamento palavra->falante, consolidacao por
frase, juncao de texto, atribuicao cluster->pessoa e normalizacao de segmentos.

Uso:
    python -m pytest tests/ -q
    python tests/test_pipeline.py      # sem pytest instalado

Cada teste tem um comentario dizendo QUAL bug real ele protege. Se um teste
falhar depois de uma mudanca no pipeline, ele esta te avisando que um defeito
ja corrigido voltou.
"""

import io
import json
import shutil
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import _ambiente  # noqa: E402

_ambiente.isolar()


# --------------------------------------------------------------------------
# stubs: as dependencias pesadas nao entram nos testes
# --------------------------------------------------------------------------


class Segment:
    """Dublê de pyannote.core.Segment. So aceita ser construido com numeros."""

    def __init__(self, start, end):
        self.start, self.end = float(start), float(end)

    def __repr__(self):
        return f"Segment({self.start}, {self.end})"


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
    pipeline,  # noqa: E402
)
from trama.cli import processar as processar_cli  # noqa: E402

# Com pytest, todas as suites rodam num processo so: se outra suite
# importou o nucleo antes (com o stub de Segment dela, ou com o pyannote de
# verdade), o "from pyannote.core import Segment" do nucleo ja ficou preso
# a outra classe. Os testes de embed daqui dependem DESTE duble.
nucleo.Segment = Segment


class FakeInference:
    """
    Imita o Inference.crop do pyannote: EXIGE um Segment de verdade.

    Esse rigor e intencional. Foi passar objeto duck-typed para o crop que
    causou o bug "nenhum trecho utilizavel" em todos os clusters.
    """

    def crop(self, path, seg):
        if not isinstance(seg, Segment):
            raise TypeError(f"esperava Segment, recebeu {type(seg).__name__}")
        rng = np.random.RandomState(int(seg.start * 100) % 9999)
        return rng.randn(256)

    def __call__(self, path):
        return np.random.RandomState(7).randn(256)


class Anotacao:
    """Dublê de uma Annotation do pyannote."""

    def __init__(self, turnos):
        self._turnos = turnos

    def itertracks(self, yield_label=True):
        for a, b, label in self._turnos:
            yield Segment(a, b), None, label


def palavras_de(spec):
    """[(inicio, fim, texto), ...] -> formato de palavra do pipeline."""
    return [{"start": a, "end": b, "word": t} for a, b, t in spec]


def com_prob(palavras, probs):
    """Anexa 'probability' a cada palavra, na mesma ordem - so os testes de
    confianca precisam disso; os demais testam o alinhamento sem o campo,
    de proposito, para garantir que ele e opcional."""
    for p, prob in zip(palavras, probs):
        p["probability"] = prob
    return palavras


# ==========================================================================
# nucleo.embed_segments
# ==========================================================================


def test_embed_aceita_tuplas_do_json():
    """
    REGRESSAO: colher_vozes.py le segmentos do fase0.json como listas [ini, fim].
    Passar isso direto ao Inference.crop levantava excecao em todo trecho, e o
    except silencioso reportava "nenhum trecho utilizavel" para todo mundo.
    """
    nucleo._inference = FakeInference()
    emb, dur = nucleo.embed_segments("x.wav", [[0.0, 5.0], [10.0, 18.0]])
    assert emb is not None, "tuplas do JSON precisam ser aceitas"
    assert emb.shape == (256,)
    assert abs(dur - 13.0) < 1e-6


def test_embed_aceita_segment_e_duck_typed():
    """fase0.py passa Segment; outros caminhos passam objetos com .start/.end."""
    nucleo._inference = FakeInference()

    class D:
        def __init__(self, a, b):
            self.start, self.end = a, b

    for entrada in ([Segment(0, 5), Segment(10, 18)], [D(0, 5), D(10, 18)]):
        emb, _ = nucleo.embed_segments("x.wav", entrada)
        assert emb is not None, f"falhou para {type(entrada[0]).__name__}"


def test_embed_normalizado_e_descarta_curtos():
    """Embedding tem de sair normalizado (cosseno == produto escalar)."""
    nucleo._inference = FakeInference()
    emb, dur = nucleo.embed_segments("x.wav", [[0, 5], [10, 10.4], [20, 25]])
    assert abs(np.linalg.norm(emb) - 1.0) < 1e-5, "precisa ser L2-normalizado"
    assert abs(dur - 10.0) < 1e-6, "trecho de 0.4s deveria ter sido descartado"


def test_embed_sem_trecho_valido_retorna_none():
    nucleo._inference = FakeInference()
    emb, dur = nucleo.embed_segments("x.wav", [[0, 0.3], [1, 1.4]])
    assert emb is None and dur == 0.0


def test_embed_respeita_teto_de_audio():
    """Nao deve processar audio infinito: o teto existe por performance."""
    nucleo._inference = FakeInference()
    segs = [[i * 20.0, i * 20.0 + 15.0] for i in range(40)]
    _, dur = nucleo.embed_segments("x.wav", segs, max_total=60.0)
    assert dur <= 75.0, f"passou muito do teto: {dur}"


# ==========================================================================
# pipeline.alinhar
# ==========================================================================


def test_alinhamento_basico():
    exc = Anotacao([(0, 5, "S0"), (5, 9, "S1"), (9, 14, "S0")])
    palavras = palavras_de([(i * 0.5, i * 0.5 + 0.5, f" w{i}") for i in range(28)])
    mapa = {"S0": {"nome": "Amanda"}, "S1": {"nome": "Celso"}}
    falas, _ = pipeline.alinhar(palavras, exc, mapa)
    assert [f["falante"] for f in falas] == ["Amanda", "Celso", "Amanda"]


def test_frase_nao_e_dividida_entre_falantes():
    """
    REGRESSAO: o limite de turno da diarizacao chega alguns decimos atrasado,
    entao a primeira palavra do novo falante caia no turno anterior. Sintoma:
    'Ramiro: E eu' / 'Amanda: acho que era importante'.
    """
    exc = Anotacao([(0.0, 5.4, "S0"), (5.4, 11.0, "S1")])
    palavras = palavras_de(
        [
            (0.5, 1.0, " Isso"),
            (1.0, 1.4, " aí."),
            (4.6, 5.0, " Mas"),
            (5.0, 5.3, " eu"),  # <- pertencem a S1
            (5.6, 6.0, " acho"),
            (6.0, 6.3, " que"),
            (6.3, 6.9, " vai"),
            (6.9, 7.4, " ser"),
            (7.4, 8.0, " isso"),
            (8.0, 8.2, "."),
        ]
    )
    mapa = {"S0": {"nome": "Ramiro"}, "S1": {"nome": "Celso"}}
    falas, _ = pipeline.alinhar(palavras, exc, mapa)

    assert len(falas) == 2, f"esperava 2 turnos, veio {len(falas)}"
    assert falas[0]["texto"] == "Isso aí."
    assert falas[1]["texto"] == "Mas eu acho que vai ser isso.", falas[1]["texto"]


def test_frase_longa_sem_pontuacao_nao_e_consolidada():
    """
    Salvaguarda: Whisper as vezes devolve blocos longos sem pontuacao. Aplicar
    voto unico ali entregaria minutos de varios falantes a uma pessoa so.
    """
    exc = Anotacao([(0.0, 15.0, "S0"), (15.0, 30.0, "S1")])
    palavras = palavras_de([(t, t + 0.9, f" w{int(t)}") for t in np.arange(0.0, 29.0, 1.0)])
    mapa = {"S0": {"nome": "Amanda"}, "S1": {"nome": "Luciano"}}
    falas, _ = pipeline.alinhar(palavras, exc, mapa)
    nomes = {f["falante"] for f in falas}
    assert nomes == {"Amanda", "Luciano"}, "bloco de 29s sem pontuacao nao pode virar um falante so"


def test_espacamento_entre_palavras():
    """REGRESSAO: saiam textos colados - 'quanto tempoeu', 'protocolovai'."""
    exc = Anotacao([(0, 10, "S0")])
    palavras = palavras_de(
        [
            (0.0, 0.5, " Quanto"),
            (0.5, 1.0, " tempo"),
            (1.0, 1.4, "ela"),
            (1.4, 2.0, " vai"),
            (2.0, 2.5, " levar"),
            (2.5, 2.7, "?"),
        ]
    )
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Ramiro"}})
    assert falas[0]["texto"] == "Quanto tempo ela vai levar?", falas[0]["texto"]


def test_alinhar_grava_o_intervalo_de_cada_palavra_na_posicao_do_texto():
    """Cada [posicao, comprimento, inicio, fim] de palavras_tempo aponta para
    a palavra certa dentro de "texto" - inclusive com a pontuacao e o "ela"
    que o juntar() cola sem espaco."""
    exc = Anotacao([(0, 10, "S0")])
    palavras = palavras_de(
        [
            (0.0, 0.5, " Quanto"),
            (0.5, 1.0, " tempo"),
            (1.0, 1.4, "ela"),
            (1.4, 2.0, " vai"),
            (2.0, 2.5, " levar"),
            (2.5, 2.7, "?"),
        ]
    )
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Ramiro"}})
    f = falas[0]
    fatias = [(f["texto"][a : a + b], ini, fim) for a, b, ini, fim in f["palavras_tempo"]]
    assert [x[0] for x in fatias] == ["Quanto", "tempo", "ela", "vai", "levar", "?"], fatias
    assert fatias[2][1:] == (1.0, 1.4)
    assert all(len(t) == 4 for t in f["palavras_tempo"])


def test_hifen_e_pontuacao_nao_ganham_espaco():
    """REGRESSAO: a correcao de espacamento gerou 'e -mail'."""
    exc = Anotacao([(0, 10, "S0")])
    palavras = palavras_de(
        [
            (0.0, 0.4, " Manda"),
            (0.4, 0.7, " por"),
            (0.7, 1.1, " e"),
            (1.1, 1.4, "-"),
            (1.4, 1.8, "mail"),
            (1.8, 1.9, ","),
            (1.9, 2.4, " beleza"),
            (2.4, 2.5, "?"),
        ]
    )
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    texto = falas[0]["texto"]
    assert "e-mail" in texto, texto
    assert " ," not in texto, texto


def test_pausa_longa_quebra_turno_do_mesmo_falante():
    """
    REGRESSAO: falas do mesmo falante separadas por 60s de silencio eram
    coladas num paragrafo unico com o timestamp da primeira. Timestamp errado,
    e impossivel marcar so o trecho sobreposto.
    """
    exc = Anotacao([(0.0, 25.0, "S0"), (60.0, 75.0, "S0")])
    palavras = palavras_de(
        [
            (1.0, 1.5, " Fala"),
            (1.5, 2.0, " limpa"),
            (2.0, 2.1, "."),
            (62.0, 62.5, " Outra"),
            (62.5, 63.2, " coisa"),
            (63.2, 63.3, "."),
        ]
    )
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert len(falas) == 2, f"esperava 2 turnos, veio {len(falas)}"
    assert falas[0]["texto"] == "Fala limpa."
    assert falas[1]["inicio"] >= 60.0, "timestamp do 2o turno esta errado"


def test_pausa_curta_nao_quebra_turno():
    """Hesitacao de 1s no meio da frase nao deve virar turno novo."""
    exc = Anotacao([(0.0, 20.0, "S0")])
    palavras = palavras_de(
        [
            (1.0, 1.5, " Eu"),
            (1.5, 2.0, " acho"),
            (3.0, 3.5, " que"),
            (3.5, 4.0, " sim"),
            (4.0, 4.1, "."),
        ]
    )
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Amanda"}})
    assert len(falas) == 1, f"pausa de 1s nao deveria quebrar: {falas}"


def test_alinhar_preserva_origem_de_clusters_com_mesmo_nome():
    """
    REGRESSAO: a troca de turno em alinhar() so olhava o NOME exibido, nao o
    cluster. Se dois clusters diferentes (a mesma pessoa dividida pela
    diarizacao, ou dois clusters que o revisao.py corrigiu para o mesmo nome)
    se sucediam sem pausa longa, viravam UMA fala so com o "cluster" do
    PRIMEIRO - uma correcao posterior mirando no segundo cluster deixava de
    alcancar essas palavras, silenciosamente.
    """
    exc = Anotacao([(0.0, 5.0, "S0"), (5.0, 10.0, "S1")])
    palavras = palavras_de(
        [
            (0.5, 1.0, " Isso"),
            (1.5, 2.0, " aí."),
            (5.5, 6.0, " Outra"),
            (6.5, 7.0, " coisa."),
        ]
    )
    mapa = {"S0": {"nome": "Ramiro"}, "S1": {"nome": "Ramiro"}}
    falas, _ = pipeline.alinhar(palavras, exc, mapa)

    assert len(falas) == 2, "clusters diferentes nao podem virar uma fala so"
    assert falas[0]["cluster"] == "S0" and falas[1]["cluster"] == "S1"
    assert falas[0]["falante"] == falas[1]["falante"] == "Ramiro"
    # Os intervalos de cada cluster continuam intactos, so o nome e igual.
    assert falas[0]["inicio"] == 0.5 and falas[0]["fim"] == 2.0
    assert falas[1]["inicio"] == 5.5 and falas[1]["fim"] == 7.0


def test_alinhar_sem_palavras():
    exc = Anotacao([(0, 5, "S0")])
    assert pipeline.alinhar([], exc, {"S0": {"nome": "Amanda"}}) == ([], [])


def test_palavra_fora_de_qualquer_turno():
    """Palavra em silencio nao pode ser descartada: cai no turno mais proximo."""
    exc = Anotacao([(0.0, 2.0, "S0"), (8.0, 10.0, "S1")])
    palavras = palavras_de([(4.0, 4.5, " orfa"), (4.5, 4.7, ".")])
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "A"}, "S1": {"nome": "B"}})
    assert len(falas) == 1 and falas[0]["texto"] == "orfa."


def test_alinhar_grava_divergencia_de_palavra_dentro_da_frase():
    """
    Uma interjeicao curta (Amanda) durante a fala do Celso - a diarizacao
    parte o turno dele em dois em volta dela. Por palavra, dono() acerta
    "que" para Amanda (maior sobreposicao); o voto da FRASE inteira (por
    duracao total) vai para Celso, que falou mais no trecho. alinhar() tem
    que preservar a divergencia da palavra, nao so o vencedor da frase -
    e o dado que a tela usa para mostrar quem entrou ali.
    """
    exc = Anotacao(
        [
            (0.0, 2.0, "S0"),  # Celso antes da interjeicao
            (2.0, 2.6, "S1"),  # Amanda interjeita
            (2.5, 5.0, "S0"),  # Celso retoma
        ]
    )
    palavras = palavras_de(
        [
            (0.0, 0.5, " Eu"),
            (0.5, 1.0, " acho"),
            (2.0, 2.5, " que"),
            (2.5, 3.0, " sim."),
        ]
    )
    mapa = {"S0": {"nome": "Celso"}, "S1": {"nome": "Amanda"}}
    falas, _ = pipeline.alinhar(palavras, exc, mapa)

    assert len(falas) == 1
    fala = falas[0]
    assert fala["falante"] == "Celso", "o voto da frase vai para quem falou mais"
    assert fala["texto"] == "Eu acho que sim."
    assert fala["palavras_divergentes"] == [
        {
            "posicao": fala["texto"].index("que"),
            "comprimento": 3,
            "falante": "Amanda",
            "cluster": "S1",
        },
    ]


def test_alinhar_sem_divergencia_nao_grava_o_campo():
    """Ausente e ausente: fala sem interjeicao nao ganha lista vazia."""
    exc = Anotacao([(0.0, 5.0, "S0")])
    palavras = palavras_de([(0.0, 0.5, " Tudo"), (0.5, 1.0, " certo.")])
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert "palavras_divergentes" not in falas[0]


def test_alinhar_token_de_duracao_zero_dentro_de_um_turno_e_divergencia_real():
    """
    REGRESSAO (reuniao_09, 44.4-55.3s): token com start==end (comum no
    Whisper) nunca tem sobreposicao de DURACAO positiva - dono() cai
    direto no desempate por proximidade, que pode empatar exatamente e
    vencer por ordem de lista, um artefato. Para duracao zero, alinhar()
    tem que usar CONTENCAO do instante (dono_do_instante), nao a
    sobreposicao/desempate de dono(). Aqui o instante CAI dentro do turno
    da Amanda de verdade - isso e medicao real, tem que virar divergencia.
    """
    exc = Anotacao(
        [
            (0.0, 2.0, "S0"),  # Celso
            (2.0, 2.6, "S1"),  # Amanda - instante zero cai aqui dentro
            (2.6, 5.0, "S0"),  # Celso retoma
        ]
    )
    palavras = palavras_de(
        [
            (0.0, 0.5, " Eu"),
            (0.5, 1.0, " acho"),
            (2.3, 2.3, " que"),  # duracao zero, DENTRO do turno da Amanda
            (2.6, 3.0, " sim."),
        ]
    )
    mapa = {"S0": {"nome": "Celso"}, "S1": {"nome": "Amanda"}}
    falas, _ = pipeline.alinhar(palavras, exc, mapa)

    assert len(falas) == 1
    fala = falas[0]
    assert fala["falante"] == "Celso"
    assert fala["texto"] == "Eu acho que sim."
    assert fala["palavras_divergentes"] == [
        {
            "posicao": fala["texto"].index("que"),
            "comprimento": 3,
            "falante": "Amanda",
            "cluster": "S1",
        },
    ]


def test_alinhar_token_de_duracao_zero_em_lacuna_nao_vira_divergencia():
    """
    REGRESSAO: o mesmo token de duracao zero, agora com o instante caindo
    numa LACUNA entre dois turnos (nenhum o contem). A atribuicao e
    indefinida - "ausente e ausente", nao pode virar uma marca na tela
    dizendo "pode ter sido outra pessoa" quando o sistema nao mediu nada.
    """
    exc = Anotacao(
        [
            (0.0, 2.0, "S0"),  # Celso
            (2.6, 2.8, "S1"),  # Amanda - blip curto, longe do instante zero
            (2.8, 5.0, "S0"),  # Celso
        ]
    )
    palavras = palavras_de(
        [
            (0.0, 0.5, " Eu"),
            (0.5, 1.0, " acho"),
            (2.55, 2.55, " que"),  # duracao zero, na LACUNA entre 2.0 e 2.6
            (2.9, 3.2, " sim."),
        ]
    )
    mapa = {"S0": {"nome": "Celso"}, "S1": {"nome": "Amanda"}}
    falas, _ = pipeline.alinhar(palavras, exc, mapa)

    assert len(falas) == 1
    fala = falas[0]
    assert fala["falante"] == "Celso"
    assert "palavras_divergentes" not in fala, (
        "instante fora de qualquer turno tem que ficar indefinido, "
        f"nao virar divergencia: {fala.get('palavras_divergentes')}"
    )


# ==========================================================================
# pipeline.alinhar - confianca por fala (probabilidade do Whisper)
# ==========================================================================


def test_alinhar_grava_confianca_media_da_fala():
    exc = Anotacao([(0.0, 5.0, "S0")])
    palavras = com_prob(palavras_de([(0.0, 0.5, " Tudo"), (0.5, 1.0, " certo.")]), [0.9, 0.7])
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert falas[0]["confianca_media"] == 0.8


def test_alinhar_sem_probabilidade_nao_grava_confianca_media():
    """Palavra sem 'probability' (backend hipotetico, ou dado de teste
    antigo) e so ignorada - sem NENHUMA palavra medida no turno, o campo
    fica ausente, nunca 0.0 (0.0 pareceria confianca minima medida)."""
    exc = Anotacao([(0.0, 5.0, "S0")])
    palavras = palavras_de([(0.0, 0.5, " Tudo"), (0.5, 1.0, " certo.")])
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert "confianca_media" not in falas[0]


def test_alinhar_grava_palavras_baixa_confianca_com_posicao():
    """Abaixo de LIMIAR_PALAVRA_BAIXA_CONFIANCA (0.5 por padrao), a palavra
    entra na lista com posicao/comprimento no MESMO formato de
    palavras_divergentes - so troca 'falante' por 'probabilidade'."""
    exc = Anotacao([(0.0, 5.0, "S0")])
    palavras = com_prob(palavras_de([(0.0, 0.5, " Tudo"), (0.5, 1.0, " certo.")]), [0.9, 0.3])
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    fala = falas[0]
    assert fala["palavras_baixa_confianca"] == [
        {"posicao": fala["texto"].index("certo"), "comprimento": 6, "probabilidade": 0.3},
    ]


def test_alinhar_sem_palavra_baixa_confianca_nao_grava_o_campo():
    exc = Anotacao([(0.0, 5.0, "S0")])
    palavras = com_prob(palavras_de([(0.0, 0.5, " Tudo"), (0.5, 1.0, " certo.")]), [0.9, 0.85])
    falas, _ = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert "palavras_baixa_confianca" not in falas[0]


# ==========================================================================
# pipeline.alinhar - lacunas de fala sem texto (silencio dentro de um turno)
# ==========================================================================


def test_alinhar_grava_lacuna_dentro_do_turno():
    """Pausa de 1.0s ENTRE duas palavras do mesmo turno (acima de
    LIMIAR_LACUNA_S=0.8, abaixo de GAP_TURNO=2.0 - nao abre turno novo)
    tem que virar uma lacuna com inicio/fim/falante."""
    exc = Anotacao([(0.0, 10.0, "S0")])
    palavras = palavras_de(
        [
            (0.0, 0.5, " Eu"),
            (0.5, 1.0, " acho"),
            (2.0, 2.5, " que"),
            (2.5, 3.0, " sim."),
        ]
    )
    falas, lacunas = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert len(falas) == 1, "pausa de 1s nao abre turno novo"
    assert lacunas == [
        {"posicao": 7, "inicio": 1.0, "fim": 2.0, "falante": "Celso", "cluster": "S0"},
    ]


def test_alinhar_pausa_curta_nao_e_lacuna():
    exc = Anotacao([(0.0, 10.0, "S0")])
    palavras = palavras_de(
        [
            (0.0, 0.5, " Eu"),
            (0.5, 1.0, " acho"),
            (1.3, 1.8, " que"),
            (1.8, 2.3, " sim."),
        ]
    )
    falas, lacunas = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert lacunas == []


def test_alinhar_pausa_que_abre_turno_novo_nao_e_lacuna():
    """A mesma pausa longa que ja abre um turno novo (GAP_TURNO) nao pode
    TAMBEM aparecer como lacuna - o silencio virou fronteira de turno, nao
    omissao dentro de um turno ativo."""
    exc = Anotacao([(0.0, 25.0, "S0"), (60.0, 75.0, "S0")])
    palavras = palavras_de(
        [
            (1.0, 1.5, " Fala"),
            (1.5, 2.0, " limpa"),
            (2.0, 2.1, "."),
            (62.0, 62.5, " Outra"),
            (62.5, 63.2, " coisa"),
            (63.2, 63.3, "."),
        ]
    )
    falas, lacunas = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert len(falas) == 2
    assert lacunas == []


def test_alinhar_lacuna_que_cruza_turno_cru_nao_conta():
    """
    REGRESSAO: a diarizacao exclusiva tem DOIS turnos crus separados para
    o MESMO rotulo (perdeu e reencontrou a voz - real na diarizacao). O
    alinhamento por palavra funde as duas palavras na MESMA fala exibida
    (o gap de 1.5s nao abre turno novo - fica abaixo de GAP_TURNO=2.0),
    mas nenhum turno CRU cobre o intervalo [1.5, 3.0] inteiro - o turno
    cru terminou em 2.0 e o outro so comeca em 2.9. Isso NAO e omissao
    dentro de um turno ativo continuo, e fronteira entre dois turnos
    crus que calham de ter o mesmo rotulo - nao pode contar como lacuna
    (medido: sem esta exclusao, ~40% das lacunas detectadas cruzavam
    fronteira de turno cru em reuniao_07/09).
    """
    exc = Anotacao([(0.0, 2.0, "S0"), (2.9, 10.0, "S0")])
    palavras = palavras_de([(1.0, 1.5, " Eu"), (3.0, 3.5, " acho")])
    falas, lacunas = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert len(falas) == 1, "gap de 1.5s fica abaixo de GAP_TURNO, mesma fala"
    assert lacunas == []


def test_alinhar_lacuna_coberta_por_um_so_turno_cru_conta():
    """Contraste com o teste acima: mesmo cenario, mas com UM turno cru
    so cobrindo toda a lacuna - aqui sim e omissao dentro de turno ativo."""
    exc = Anotacao([(0.0, 10.0, "S0")])
    palavras = palavras_de([(1.0, 1.5, " Eu"), (3.0, 3.5, " acho")])
    falas, lacunas = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert len(falas) == 1
    assert lacunas == [
        {"posicao": 2, "inicio": 1.5, "fim": 3.0, "falante": "Celso", "cluster": "S0"}
    ]


def test_alinhar_usa_turnos_ativos_quando_fornecido():
    """
    pipeline.py passa analise['turnos_brutos'] (diarizacao NAO-exclusiva, que
    nao sofre fragmentacao artificial do desempate de exclusividade
    durante fala sobreposta) como turnos_ativos - a checagem de lacuna usa
    ELE, nao a diarizacao exclusiva recebida em diar_exclusiva. Mesmo
    cenario do teste acima (dois turnos exclusivos separados por uma
    fronteira em 2.0-2.9), mas turnos_ativos cobre tudo com UM turno so -
    agora a lacuna conta.
    """
    exc = Anotacao([(0.0, 2.0, "S0"), (2.9, 10.0, "S0")])
    palavras = palavras_de([(1.0, 1.5, " Eu"), (3.0, 3.5, " acho")])
    falas, lacunas = pipeline.alinhar(
        palavras, exc, {"S0": {"nome": "Celso"}}, turnos_ativos=[(0.0, 10.0, "S0")]
    )
    assert lacunas == [
        {"posicao": 2, "inicio": 1.5, "fim": 3.0, "falante": "Celso", "cluster": "S0"}
    ]


def test_alinhar_turnos_ativos_mais_fragmentado_exclui_lacuna():
    """Inverso: diarizacao exclusiva continua (sem fronteira), mas
    turnos_ativos (nao-exclusiva) mostra a pessoa fragmentada em dois
    turnos separados - a lacuna nao conta, porque a fonte usada para a
    decisao e turnos_ativos, nao a exclusiva."""
    exc = Anotacao([(0.0, 10.0, "S0")])
    palavras = palavras_de([(1.0, 1.5, " Eu"), (3.0, 3.5, " acho")])
    falas, lacunas = pipeline.alinhar(
        palavras,
        exc,
        {"S0": {"nome": "Celso"}},
        turnos_ativos=[(0.0, 2.0, "S0"), (2.9, 10.0, "S0")],
    )
    assert lacunas == []


def test_alinhar_varias_lacunas_no_mesmo_turno():
    exc = Anotacao([(0.0, 10.0, "S0")])
    palavras = palavras_de(
        [
            (0.0, 0.5, " Eu"),
            (0.5, 1.0, " acho"),
            (2.0, 2.5, " que"),
            (2.5, 3.0, " sim"),
            (4.5, 4.6, "."),
        ]
    )
    falas, lacunas = pipeline.alinhar(palavras, exc, {"S0": {"nome": "Celso"}})
    assert len(falas) == 1
    assert lacunas == [
        {"posicao": 7, "inicio": 1.0, "fim": 2.0, "falante": "Celso", "cluster": "S0"},
        {"posicao": 15, "inicio": 3.0, "fim": 4.5, "falante": "Celso", "cluster": "S0"},
    ]


# ==========================================================================
# atribuicao cluster -> pessoa (pipeline.identificar - a FUNCAO REAL, nao um
# auxiliar de teste). Cada cenario monkeypatcha nucleo.embed_segments para
# devolver, por cluster, exatamente a linha de similaridade desejada contra
# uma galeria de vetores da base canonica - assim S[i, j] == dot(embeddings[l],
# l2(galeria[n])) cai exatamente no valor da linha, sem precisar resolver
# normalizacao af.
# ==========================================================================


class DiarUmSegPorCluster:
    """
    Dubla de Annotation onde cada cluster tem UM turno so, com start == indice
    do cluster na lista `rotulos`. embed_segments fake le esse indice de volta
    a partir de segs[0].start para saber qual linha de similaridade devolver.
    """

    def __init__(self, rotulos):
        self._rotulos = rotulos

    def itertracks(self, yield_label=True):
        for i, label in enumerate(self._rotulos):
            yield Segment(i, i + 1), None, label


def _monkeypatch_embed(linhas_por_rotulo):
    """Retorna (aplicar, restaurar) para trocar nucleo.embed_segments."""
    original = nucleo.embed_segments

    def fake(wav, segs, device="cpu", **kw):
        idx = int(segs[0].start)
        linha = linhas_por_rotulo[idx]
        return np.asarray(linha, dtype=np.float32), 30.0

    def aplicar():
        nucleo.embed_segments = fake

    def restaurar():
        nucleo.embed_segments = original

    return aplicar, restaurar


def _galeria_base_canonica(nomes):
    """Vetores one-hot: dot(linha, l2(galeria[nome_j])) == linha[j] exato."""
    base = np.eye(len(nomes), dtype=np.float32)
    return {n: base[j] for j, n in enumerate(nomes)}


def test_identificar_pessoa_pode_ocupar_dois_clusters():
    """
    REGRESSAO: com atribuicao exclusiva (Hungaro), quando a diarizacao dividia
    Ramiro em dois clusters, um deles recebia o nome de quem nem estava na sala.
    Aconteceu de verdade: --pessoas com 5 nomes numa reuniao de 4 pessoas.
    """
    nomes = ["Amanda", "Celso", "Luciano", "Ramiro", "Rolando"]
    linhas = [
        [0.240, 0.276, 0.085, 0.747, 0.102],  # cluster 0: Ramiro (dividido)
        [0.135, 0.924, 0.235, 0.191, 0.285],  # cluster 1: Celso
        [0.891, 0.079, 0.060, 0.173, 0.210],  # cluster 2: Amanda
        [0.108, 0.341, 0.921, 0.237, 0.276],  # cluster 3: Luciano
        [0.175, 0.240, 0.067, 0.832, 0.185],  # cluster 4: Ramiro (dividido)
    ]
    rotulos = [f"S{i}" for i in range(5)]
    diar = DiarUmSegPorCluster(rotulos)
    galeria = _galeria_base_canonica(nomes)

    aplicar, restaurar = _monkeypatch_embed(linhas)
    aplicar()
    try:
        mapa = pipeline.identificar("x.wav", diar, galeria, "cpu")
    finally:
        restaurar()

    obtidos = [mapa[r]["nome"] for r in rotulos]
    assert obtidos == ["Ramiro", "Celso", "Amanda", "Luciano", "Ramiro"], obtidos
    assert "Rolando" not in obtidos, "Rolando nao estava na reuniao"


def test_identificar_pessoa_ausente_na_galeria_vira_desconhecido():
    """A pessoa real nao esta cadastrada: nenhum candidato bate, DESCONHECIDO."""
    nomes = ["Amanda", "Celso"]
    linhas = [[0.20, 0.18]]  # baixo contra os dois - o falante nao e nenhum
    diar = DiarUmSegPorCluster(["S0"])
    galeria = _galeria_base_canonica(nomes)

    aplicar, restaurar = _monkeypatch_embed(linhas)
    aplicar()
    try:
        mapa = pipeline.identificar("x.wav", diar, galeria, "cpu")
    finally:
        restaurar()

    assert mapa["S0"]["nome"] == "DESCONHECIDO_S0"


def test_identificar_similaridade_insuficiente_vira_desconhecido():
    """Margem boa, mas o melhor escore fica abaixo de SIM_MIN: nao chuta."""
    nomes = ["Amanda", "Celso"]
    linhas = [[pipeline.SIM_MIN - 0.05, 0.05]]
    diar = DiarUmSegPorCluster(["S0"])
    galeria = _galeria_base_canonica(nomes)

    aplicar, restaurar = _monkeypatch_embed(linhas)
    aplicar()
    try:
        mapa = pipeline.identificar("x.wav", diar, galeria, "cpu")
    finally:
        restaurar()

    assert mapa["S0"]["nome"] == "DESCONHECIDO_S0"
    assert mapa["S0"]["sim"] < pipeline.SIM_MIN


def test_identificar_empate_vira_desconhecido():
    """Dois candidatos com o mesmo escore: margem 0, nao da para decidir."""
    nomes = ["Amanda", "Celso"]
    empatado = min(pipeline.SIM_MIN + 0.1, 0.95)
    linhas = [[empatado, empatado]]
    diar = DiarUmSegPorCluster(["S0"])
    galeria = _galeria_base_canonica(nomes)

    aplicar, restaurar = _monkeypatch_embed(linhas)
    aplicar()
    try:
        mapa = pipeline.identificar("x.wav", diar, galeria, "cpu")
    finally:
        restaurar()

    assert mapa["S0"]["nome"] == "DESCONHECIDO_S0", mapa["S0"]
    assert mapa["S0"]["margem"] == 0.0


def test_identificar_galeria_vazia_no_json_ainda_sai_com_desconhecido():
    """Sem ninguem cadastrado, pipeline.identificar nao pode quebrar - so devolve
    DESCONHECIDO_<label> para cada cluster, com fala_s preservado."""
    diar = DiarUmSegPorCluster(["S0", "S1"])

    aplicar, restaurar = _monkeypatch_embed([[0.9], [0.9]])
    aplicar()
    try:
        mapa = pipeline.identificar("x.wav", diar, {}, "cpu")
    finally:
        restaurar()

    assert set(mapa) == {"S0", "S1"}
    assert all(v["nome"].startswith("DESCONHECIDO_") for v in mapa.values())


def test_limiar_calibrado_separa_acertos_de_erros():
    """
    Guarda a calibracao real: 16 identificacoes em 4 reunioes.
    Se alguma mudanca comprimir essa separacao, este teste avisa.
    """
    acertos = [
        0.832,
        0.893,
        0.895,
        0.903,
        0.905,
        0.909,
        0.917,
        0.922,
        0.923,
        0.924,
        0.930,
        0.930,
        0.932,
        0.935,
        0.950,
    ]
    falsos = [0.357, 0.341, 0.315, 0.305, 0.301, 0.288, 0.276, 0.265]
    assert min(acertos) > pipeline.SIM_MIN, "limiar rejeitaria um acerto"
    assert max(falsos) < pipeline.SIM_MIN, "limiar aceitaria um erro"
    assert min(acertos) - max(falsos) > 0.4, "margem de seguranca encolheu"


def test_sim_min_default_e_060_no_codigo():
    """
    REGRESSAO: o padrao no codigo era 0.45, mas a calibracao real (ver teste
    acima) aponta 0.60 - e o ambiente ja roda com SIM_MIN=0.60 via variavel
    de ambiente. O padrao no codigo (usado por quem ainda nao setou a
    variavel) tem de refletir a MESMA calibracao, sem deixar de ser
    configuravel.
    """
    fonte = (RAIZ / "trama" / "pipeline.py").read_text(encoding="utf-8")
    assert 'os.environ.get("SIM_MIN", "0.60")' in fonte, (
        "o padrao de SIM_MIN no codigo nao e mais 0.60"
    )


def test_imprimir_dinamica_nao_gruda_colunas_numericas():
    """
    REGRESSAO relatada: SOFREU e APOIOS apareciam grudados na tabela do
    CLI ("823" para 8 e 23, "1623" para 16 e 23) porque os campos eram
    formatados so com largura minima (":>N"), sem separador literal - um
    valor cujos digitos alcancam a largura do campo nao sobra espaco
    nenhum, e cola no campo anterior. Usa os MESMOS numeros do relato.
    """
    analise = {
        "dinamica": {
            "Luciano": {
                "fala_s": 662.4,
                "fala_pct": 15.7,
                "turnos": 132,
                "turno_medio_s": 5.0,
                "interrompeu": 16,
                "foi_interrompido": 8,
                "apoios": 23,
            },
        },
        "matriz_interrupcoes": {},
        "eventos": [],
    }
    saida = io.StringIO()
    with redirect_stdout(saida):
        pipeline.imprimir_dinamica(analise)
    texto = saida.getvalue()

    assert "823" not in texto, texto
    assert "1623" not in texto, texto
    linha = next(l for l in texto.splitlines() if "Luciano" in l)
    assert linha.split() == ["Luciano", "662s", "15.7", "132", "5.0s", "16", "8", "23"], linha


def test_montar_saida_grava_o_limiar_em_vigor_na_execucao():
    """
    REGRESSAO: o .json nao guardava sim_min/margem_min, entao a tela de
    revisao nao tinha como saber se uma reuniao antiga foi calibrada com
    um limiar diferente do de hoje - so podia mostrar o limiar atual como
    se fosse o do processamento. montar_saida() e o unico lugar que monta
    o dict gravado; se sim_min/margem_min sumirem daqui, o servidor volta
    a nao ter de onde ler o limiar historico.
    """
    analise = {
        "turnos_brutos": [(0.0, 1.0, "S0")],
        "dinamica": {},
        "matriz_interrupcoes": {},
        "eventos": [],
        "regioes_sobrepostas": [],
    }
    dados = pipeline.montar_saida("x.m4a", "x16k.wav", {}, [], analise)
    assert dados["sim_min"] == pipeline.SIM_MIN
    assert dados["margem_min"] == pipeline.MARGEM_MIN
    assert dados["limiar_confianca_fala"] == pipeline.LIMIAR_CONFIANCA_FALA
    assert dados["min_palavras_confianca_fala"] == pipeline.MIN_PALAVRAS_CONFIANCA_FALA


def test_montar_saida_grava_device_e_asr_quando_informados():
    """mlx (Apple Silicon) e faster_whisper (CPU) transcrevem diferente -
    comparar duas reunioes sem saber qual rodou em qual leva a conclusao
    errada, daqui a um ano."""
    analise = {
        "turnos_brutos": [],
        "dinamica": {},
        "matriz_interrupcoes": {},
        "eventos": [],
        "regioes_sobrepostas": [],
    }
    dados = pipeline.montar_saida("x.m4a", "x16k.wav", {}, [], analise, device="mps", asr="mlx")
    assert dados["device_usado"] == "mps"
    assert dados["asr_usado"] == "mlx"


def test_montar_saida_sem_device_e_asr_fica_ausente():
    """Ausente e ausente - chamador (CLI antiga, ou teste) que nao
    informou nao pode ganhar 'device_usado': None fingindo um dado que
    nao existe."""
    analise = {
        "turnos_brutos": [],
        "dinamica": {},
        "matriz_interrupcoes": {},
        "eventos": [],
        "regioes_sobrepostas": [],
    }
    dados = pipeline.montar_saida("x.m4a", "x16k.wav", {}, [], analise)
    assert "device_usado" not in dados
    assert "asr_usado" not in dados


def test_montar_saida_grava_lacunas_sem_texto():
    analise = {
        "turnos_brutos": [],
        "dinamica": {},
        "matriz_interrupcoes": {},
        "eventos": [],
        "regioes_sobrepostas": [],
    }
    lacunas = [{"inicio": 1.0, "fim": 2.0, "falante": "Celso"}]
    dados = pipeline.montar_saida("x.m4a", "x16k.wav", {}, [], analise, lacunas=lacunas)
    assert dados["lacunas_sem_texto"] == lacunas


def test_montar_saida_sem_lacunas_grava_lista_vazia():
    """Sempre presente como lista, como 'eventos'/'regioes_sobrepostas' -
    nunca ausente numa reuniao processada por esta versao."""
    analise = {
        "turnos_brutos": [],
        "dinamica": {},
        "matriz_interrupcoes": {},
        "eventos": [],
        "regioes_sobrepostas": [],
    }
    dados = pipeline.montar_saida("x.m4a", "x16k.wav", {}, [], analise)
    assert dados["lacunas_sem_texto"] == []


# ==========================================================================
# preservacao entre reprocessamentos (reuniao_id e confirmado)
# ==========================================================================


def test_carregar_saida_anterior_none_quando_arquivo_nao_existe():
    assert pipeline.carregar_saida_anterior(Path(tempfile.mkdtemp()) / "nao_existe.json") is None


def test_carregar_saida_anterior_le_o_json_existente():
    caminho = Path(tempfile.mkdtemp()) / "reuniao.json"
    caminho.write_text(json.dumps({"reuniao_id": "abc-123"}), encoding="utf-8")
    dados = pipeline.carregar_saida_anterior(caminho)
    assert dados["reuniao_id"] == "abc-123"


def test_preservar_reuniao_id_mantem_o_id_de_uma_execucao_anterior():
    """
    REGRESSAO: reprocessar o mesmo audio gerava um reuniao_id novo a cada
    rodada (uuid4 direto em montar_saida). O ledger de vozes e idempotente
    por reuniao_id+cluster (revisao.aplicar_e_gravar) - com o id trocando a
    cada reprocessamento, uma reuniao ja revisada deixava de ser
    reconhecida como a mesma, e a proxima revisao duplicava o aprendizado
    de voz das mesmas pessoas.
    """
    anterior = {"reuniao_id": "id-fixo-da-reuniao"}
    assert pipeline.preservar_reuniao_id(anterior) == "id-fixo-da-reuniao"


def test_preservar_reuniao_id_none_quando_e_a_primeira_vez():
    """Sem execucao anterior, nao ha o que preservar - montar_saida gera um novo."""
    assert pipeline.preservar_reuniao_id(None) is None
    assert pipeline.preservar_reuniao_id({}) is None


def test_montar_saida_usa_o_reuniao_id_passado():
    analise = {
        "turnos_brutos": [],
        "dinamica": {},
        "matriz_interrupcoes": {},
        "eventos": [],
        "regioes_sobrepostas": [],
    }
    dados = pipeline.montar_saida("x.m4a", "x16k.wav", {}, [], analise, reuniao_id="id-preservado")
    assert dados["reuniao_id"] == "id-preservado"


# --------------------------------------------------------------------------
# ffmpeg nunca le o terminal de quem chamou
# --------------------------------------------------------------------------

_RUN_FALSO = """
import sys, types
sys.path.insert(0, {raiz!r})
for nome in ["torch", "pyannote", "pyannote.audio", "pyannote.core", "soundfile"]:
    sys.modules.setdefault(nome, types.ModuleType(nome))
sys.modules["torch"].device = lambda x: x
sys.modules["pyannote.audio"].Model = object
sys.modules["pyannote.audio"].Inference = object
sys.modules["pyannote.core"].Segment = object
from trama import nucleo
nucleo.to_wav16k("audio.m4a", "saida_" + sys.argv[1] + ".wav")
with open("recebidos.txt", "a") as f:
    f.write(sys.argv[1] + "\\n")
"""

# O jeito de antes: ffmpeg herdando o stdin de quem chamou.
_CHAMADA_ANTIGA = """
import subprocess, sys
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "audio.m4a",
                "saida_" + sys.argv[1] + ".wav"], check=True)
with open("recebidos.txt", "a") as f:
    f.write(sys.argv[1] + "\\n")
"""

# ffmpeg FALSO: registra os argumentos e le exatamente 2 bytes do stdin -
# o que o ffmpeg de verdade fez no caso relatado ("reuniao_02" chegou como
# "uniao_02"). dd bs=1 le byte a byte: um head/cat bufferizado leria mais
# que 2 do arquivo do heredoc e o sintoma nao seria o mesmo.
_FFMPEG_FALSO = """#!/bin/bash
echo "$@" >> args.txt
dd bs=1 count=2 of=/dev/null 2>/dev/null
: > "${@: -1}"
"""


def _laco_while_read(script, pasta):
    """Roda `script` uma vez por linha num "while read" de bash, lista vinda
    de um heredoc - como o comando de reprocessamento - com o ffmpeg falso
    na frente do PATH. Devolve o que cada execucao recebeu em argv[1]."""
    import os
    import subprocess

    (pasta / "recebidos.txt").unlink(missing_ok=True)
    laco = (
        f'while read id; do "{sys.executable}" "{script}" "$id" || exit 1; done <<LISTA\n'
        "reuniao_01\nreuniao_02\nLISTA\n"
    )
    env = {**os.environ, "PATH": f"{pasta / 'bin'}:{os.environ['PATH']}"}
    subprocess.run(["bash", "-c", laco], cwd=pasta, env=env, check=True, timeout=120)
    return (pasta / "recebidos.txt").read_text(encoding="utf-8").split()


def test_run_em_laco_while_read_recebe_o_nome_inteiro_de_cada_reuniao():
    """
    REGRESSAO relatada: dentro de um laco "while read" de bash, o ffmpeg
    de nucleo.to_wav16k lia o terminal (padrao dele: espera tecla) e comia a
    lista de entrada - a segunda reuniao chegava como "uniao_02".

    Com o ffmpeg de verdade o teste era instavel: quanto ele le do stdin
    depende do ritmo da conversao (medido: nenhum byte convertendo 20 min
    de audio em cache, um com o disco frio, dois com -re) - passava ou
    falhava conforme a maquina. Um ffmpeg falso que SEMPRE le 2 bytes do
    stdin torna o teste deterministico, e testa o contrato do projeto:
    nunca entregar o stdin ao ffmpeg, sempre com -nostdin. O controle (a
    chamada antiga, sem stdin=DEVNULL) prova que o arranjo reproduz o bug.
    """
    import tempfile

    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-laco-"))
    try:
        (pasta / "bin").mkdir()
        falso = pasta / "bin" / "ffmpeg"
        falso.write_text(_FFMPEG_FALSO, encoding="utf-8")
        falso.chmod(0o755)
        (pasta / "audio.m4a").write_bytes(b"")
        esperado = ["reuniao_01", "reuniao_02"]

        controle = pasta / "chamada_antiga.py"
        controle.write_text(_CHAMADA_ANTIGA, encoding="utf-8")
        mastigado = _laco_while_read(controle, pasta)
        assert mastigado == ["reuniao_01", "uniao_02"], (
            f"o controle nao reproduziu o bug ({mastigado}) - o teste nao provaria nada"
        )

        (pasta / "args.txt").unlink()
        run_falso = pasta / "run_falso.py"
        run_falso.write_text(_RUN_FALSO.format(raiz=str(RAIZ)), encoding="utf-8")
        recebidos = _laco_while_read(run_falso, pasta)
        assert recebidos == esperado, f"o laco entregou {recebidos}"
        chamadas = (pasta / "args.txt").read_text(encoding="utf-8").splitlines()
        assert len(chamadas) == 2 and all(c.startswith("-nostdin ") for c in chamadas), chamadas
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# --------------------------------------------------------------------------
# data e titulo da reuniao
# --------------------------------------------------------------------------


def _m4a(caminho, creation_time=None):
    import subprocess

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "sine=duration=1",
        "-c:a",
        "aac",
    ]
    if creation_time:
        cmd += ["-metadata", f"creation_time={creation_time}"]
    subprocess.run(cmd + [str(caminho)], stdin=subprocess.DEVNULL, check=True, timeout=30)


def test_data_da_gravacao_le_o_creation_time_em_utc_ou_cai_no_arquivo():
    import os
    import tempfile

    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-data-"))
    try:
        com, sem = pasta / "com.m4a", pasta / "sem.m4a"
        _m4a(com, "2026-07-02T11:49:13.000000Z")
        _m4a(sem)
        os.utime(sem, (1790000000, 1790000000))
        assert nucleo.data_da_gravacao(com) == {
            "data": "2026-07-02T11:49:13Z",
            "origem": "gravacao",
        }
        assert nucleo.data_da_gravacao(sem) == {"data": "2026-09-21T14:13:20Z", "origem": "arquivo"}
        assert nucleo.data_da_gravacao(pasta / "nao_existe.m4a") is None
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_preservar_metadados_mantem_titulo_e_data_ao_reprocessar():
    import json
    import tempfile

    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-meta-"))
    try:
        audio = pasta / "reuniao_01.m4a"
        _m4a(audio, "2026-08-12T11:37:44.000000Z")
        anterior = {
            "titulo": "Comitê de produto",
            "data_reuniao": "2026-07-02T11:49:13Z",
            "data_origem": "gravacao",
        }
        # data da gravacao ja conhecida nunca e trocada; titulo nunca some
        assert pipeline.preservar_metadados(anterior, audio) == anterior
        # data que era so do arquivo e relida (o audio agora tem metadado)
        assert pipeline.preservar_metadados(
            {"titulo": "X", "data_reuniao": "2026-09-01T00:00:00Z", "data_origem": "arquivo"}, audio
        ) == {"titulo": "X", "data_reuniao": "2026-08-12T11:37:44Z", "data_origem": "gravacao"}
        # primeira vez: titulo do meta.json que a Nova reuniao gravou
        (pasta / nucleo.NOME_META_REUNIAO).write_text(
            json.dumps({"titulo": "Da tela"}), encoding="utf-8"
        )
        assert pipeline.preservar_metadados(None, audio)["titulo"] == "Da tela"
        # sem titulo em lugar nenhum: ausente, nunca ""
        (pasta / nucleo.NOME_META_REUNIAO).unlink()
        assert "titulo" not in pipeline.preservar_metadados(None, audio)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_faixa_de_falantes_com_pessoas_respeita_a_faixa():
    cinco = ["Celso", "Luciano", "Ramiro", "Amanda", "Clélia"]
    # faixa passada: vale a faixa, --pessoas so restringe a comparacao
    assert pipeline.faixa_de_falantes(None, 4, 5, cinco) == {"min_speakers": 4, "max_speakers": 5}
    assert pipeline.faixa_de_falantes(None, 4, None, cinco) == {"min_speakers": 4}
    assert pipeline.faixa_de_falantes(None, None, 5, cinco) == {"max_speakers": 5}
    # sem faixa: o numero de nomes continua fixando, como sempre
    assert pipeline.faixa_de_falantes(None, None, None, cinco) == {"num_speakers": 5}
    # --falantes ganha de tudo
    assert pipeline.faixa_de_falantes(3, 4, 5, cinco) == {"num_speakers": 3}
    assert pipeline.faixa_de_falantes(None, None, None, None) == {}
    assert (
        pipeline.descrever_faixa({"min_speakers": 4, "max_speakers": 5})
        == " - entre 4 e 5 falantes"
    )
    assert pipeline.descrever_faixa({"num_speakers": 5}) == " - 5 falantes"
    assert pipeline.descrever_faixa({}) == ""


def test_run_main_cinco_pessoas_com_faixa_deixa_a_diarizacao_escolher():
    """
    Pelo processar_cli.main() de verdade (argparse incluso): o que chega a
    diarizar() e a faixa, nao o numero de nomes; sem faixa, 5 fixo.
    """
    import tempfile

    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-faixa-"))
    turnos = [(0.0, 10.0, "SPEAKER_00")]
    mapa = {
        "SPEAKER_00": {"nome": "Celso", "sim": 0.9, "margem": 0.5, "fala_s": 10.0, "scores": {}}
    }
    pedidos, galerias = [], []
    originais = (
        pipeline.diarizar,
        pipeline.identificar,
        pipeline.transcrever,
        nucleo.get_galeria,
        nucleo.DB_PATH,
        sys.argv,
    )

    def diarizar_duble(wav, device, **kwargs):
        pedidos.append(kwargs)
        return Anotacao(turnos), Anotacao(turnos)

    def galeria_duble(nomes=None):
        galerias.append(nomes)
        return {n: None for n in nomes or []}

    try:
        audio = pasta / "reuniao_01.m4a"
        _m4a(audio, "2026-11-04T11:59:48.000000Z")
        pipeline.diarizar = diarizar_duble
        pipeline.identificar = lambda *a, **k: dict(mapa)
        pipeline.transcrever = lambda *a, **k: palavras_de([(0.5, 0.9, " oi")])
        nucleo.get_galeria = galeria_duble
        nucleo.DB_PATH = pasta / "vozes_teste.db"
        cinco = "Celso,Luciano,Ramiro,Amanda,Clélia"
        base = [
            "pipeline.py",
            str(audio),
            "--sem-termos",
            "--device",
            "cpu",
            "--asr",
            "mlx",
            "--pessoas",
            cinco,
        ]
        for extra in (["--min-falantes", "4", "--max-falantes", "5"], []):
            sys.argv = base + extra
            with redirect_stdout(io.StringIO()):
                processar_cli.main()
    finally:
        (
            pipeline.diarizar,
            pipeline.identificar,
            pipeline.transcrever,
            nucleo.get_galeria,
            nucleo.DB_PATH,
            sys.argv,
        ) = originais
        shutil.rmtree(pasta, ignore_errors=True)

    assert pedidos == [{"min_speakers": 4, "max_speakers": 5}, {"num_speakers": 5}], pedidos
    # nos dois casos a comparacao de voz fica restrita aos cinco nomes
    assert galerias == [cinco.split(",")] * 2, galerias


def _rodar_run_main(audio, db, turnos, mapa, palavras, termos_arquivo=None, ao_transcrever=None):
    """
    processar_cli.main() DE VERDADE - conversao de audio (ffmpeg), alinhamento,
    analise de interacao, montagem e gravacao do .json/.txt, preservacao
    de reuniao_id, titulo, data e revisao. So as etapas pesadas trocadas
    por dubles: diarizacao, identificacao por voz, transcricao. E a
    ligacao entre as pecas que ja apagou coisa ao reprocessar; testar so
    as funcoes isoladas nao pegaria.
    """
    import copy

    originais = (
        pipeline.diarizar,
        pipeline.identificar,
        pipeline.transcrever,
        nucleo.DB_PATH,
        sys.argv,
    )
    pipeline.diarizar = lambda *a, **k: (Anotacao(turnos), Anotacao(turnos))
    pipeline.identificar = lambda *a, **k: copy.deepcopy(mapa)

    def transcrever(*a, **k):
        # ao_transcrever: o que a tela faria DURANTE o processamento (a
        # transcricao e a etapa que leva minutos).
        if ao_transcrever:
            ao_transcrever()
        return palavras_de(palavras)

    pipeline.transcrever = transcrever
    nucleo.DB_PATH = db
    glossario = ["--termos", str(termos_arquivo)] if termos_arquivo else ["--sem-termos"]
    sys.argv = ["pipeline.py", str(audio), *glossario, "--device", "cpu", "--asr", "mlx"]
    try:
        with redirect_stdout(io.StringIO()):
            processar_cli.main()
    finally:
        pipeline.diarizar, pipeline.identificar, pipeline.transcrever, nucleo.DB_PATH, sys.argv = (
            originais
        )


# --- correcao manual do texto de uma fala (edicao.py, ADR 0016) -----------


def _cenario_de_correcao():
    import tempfile

    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-correcao-"))
    audio = pasta / "reuniao_01.m4a"
    _m4a(audio)

    def cluster(nome):
        return {"nome": nome, "sim": 0.9, "margem": 0.5, "fala_s": 30.0, "scores": {}}

    # duas falas: Ramiro 0-10s, Amanda 10-20s
    palavras = [
        (i * 0.5, i * 0.5 + 0.4, f" p{i}" + ("." if i % 10 == 9 else "")) for i in range(40)
    ]
    turnos = [(0.0, 10.0, "SPEAKER_00"), (10.0, 20.0, "SPEAKER_01")]
    mapa = {"SPEAKER_00": cluster("Ramiro"), "SPEAKER_01": cluster("Amanda")}
    return pasta, audio, palavras, turnos, mapa


def _corrigir_no_disco(caminho_json, indice, texto):
    """O que a rota PUT /api/reunioes/{id}/falas/{indice} grava."""
    import json

    from trama import edicao

    d = json.loads(caminho_json.read_text(encoding="utf-8"))
    edicao.editar(d, indice, texto, d["falas"][indice]["inicio"])
    nucleo.escrever_atomico(caminho_json, nucleo.json_para_disco(d))


def test_reprocessar_mantem_correcao_manual_e_o_glossario_nao_sobrescreve():
    import json

    pasta, audio, palavras, turnos, mapa = _cenario_de_correcao()
    try:
        db = pasta / "vozes_teste.db"
        j = pasta / "reuniao_01.json"
        _rodar_run_main(audio, db, turnos, mapa, palavras)
        _corrigir_no_disco(j, 0, "Correção feita à mão.")

        # 2a rodada: clusters renumerados E um glossario que casaria com as
        # duas falas
        termos_arquivo = pasta / "termos.txt"
        termos_arquivo.write_text("p1 => P-UM\np21 => P-VINTE-E-UM\n", encoding="utf-8")
        renumerado = [
            (a, b, "SPEAKER_01" if q == "SPEAKER_00" else "SPEAKER_00") for a, b, q in turnos
        ]
        _rodar_run_main(
            audio,
            db,
            renumerado,
            {"SPEAKER_01": mapa["SPEAKER_00"], "SPEAKER_00": mapa["SPEAKER_01"]},
            palavras,
            termos_arquivo=termos_arquivo,
        )

        d = json.loads(j.read_text(encoding="utf-8"))
        corrigida, outra = d["falas"]
        assert corrigida["texto"] == "Correção feita à mão.", corrigida["texto"]
        # "desfazer" mostra o texto da maquina DESTA rodada, ja com o glossario
        assert "P-UM" in corrigida["edicao_manual"]["texto_original"]
        assert "palavras_tempo" not in corrigida
        assert "palavras_tempo" in corrigida["edicao_manual"]["marcas_originais"]
        # o glossario continua valendo nas falas que ninguem corrigiu
        assert "P-VINTE-E-UM" in outra["texto"] and "edicao_manual" not in outra
        assert "edicoes_sem_fala" not in d and "avisos" not in d
        assert "Correção feita à mão." in j.with_suffix(".txt").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_correcao_feita_na_tela_durante_o_reprocessamento_nao_se_perde():
    import json

    pasta, audio, palavras, turnos, mapa = _cenario_de_correcao()
    try:
        db = pasta / "vozes_teste.db"
        j = pasta / "reuniao_01.json"
        _rodar_run_main(audio, db, turnos, mapa, palavras)
        _rodar_run_main(
            audio,
            db,
            turnos,
            mapa,
            palavras,
            ao_transcrever=lambda: _corrigir_no_disco(j, 1, "Corrigido no meio."),
        )
        d = json.loads(j.read_text(encoding="utf-8"))
        assert d["falas"][1]["texto"] == "Corrigido no meio."
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_correcao_sem_fala_correspondente_fica_guardada_e_volta_depois():
    import json

    pasta, audio, palavras, turnos, mapa = _cenario_de_correcao()
    try:
        db = pasta / "vozes_teste.db"
        j = pasta / "reuniao_01.json"
        _rodar_run_main(audio, db, turnos, mapa, palavras)
        _corrigir_no_disco(j, 0, "Correção feita à mão.")

        # audio dividido de outro jeito: nenhuma fala nova cobre 0-10s
        longe = [(a + 100, b + 100, t) for a, b, t in palavras]
        _rodar_run_main(audio, db, [(a + 100, b + 100, q) for a, b, q in turnos], mapa, longe)
        d = json.loads(j.read_text(encoding="utf-8"))
        assert not any("edicao_manual" in f for f in d["falas"])
        assert [e["texto"] for e in d["edicoes_sem_fala"]] == ["Correção feita à mão."]
        assert "à mão" in d["avisos"][0]

        # um reprocessamento que acha a fala de novo devolve a correcao
        _rodar_run_main(audio, db, turnos, mapa, palavras)
        d = json.loads(j.read_text(encoding="utf-8"))
        assert d["falas"][0]["texto"] == "Correção feita à mão."
        assert "edicoes_sem_fala" not in d and "avisos" not in d
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_reprocessar_reuniao_com_titulo_mantem_titulo_data_id_e_revisao():
    """
    Reprocessa uma reuniao que tem titulo (dado na Nova reuniao e depois
    editado no Detalhe), data de gravacao e revisao feita - com a
    diarizacao nova RENUMERANDO os clusters - e confere que nada disso
    muda. O meta.json antigo da Nova reuniao continua na pasta de
    proposito: o titulo do .json (o editado) tem de ganhar dele.
    """
    import json
    import tempfile

    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-reprocessar-"))
    try:
        audio = pasta / "reuniao_01.m4a"
        _m4a(audio, "2026-07-02T11:49:13.000000Z")
        (pasta / nucleo.NOME_META_REUNIAO).write_text(
            json.dumps({"titulo": "Comitê de produto"}), encoding="utf-8"
        )
        db = pasta / "vozes_teste.db"

        def cluster(nome):
            return {"nome": nome, "sim": 0.9, "margem": 0.5, "fala_s": 30.0, "scores": {}}

        palavras = [(i * 0.5, i * 0.5 + 0.4, f" p{i}") for i in range(40)]

        # 1a rodada: o pipeline chama S0 de Ramiro e S1 de Amanda
        turnos = [(0.0, 10.0, "SPEAKER_00"), (10.0, 20.0, "SPEAKER_01")]
        _rodar_run_main(
            audio,
            db,
            turnos,
            {"SPEAKER_00": cluster("Ramiro"), "SPEAKER_01": cluster("Amanda")},
            palavras,
        )
        j = pasta / "reuniao_01.json"
        primeira = json.loads(j.read_text(encoding="utf-8"))
        assert primeira["titulo"] == "Comitê de produto", "titulo da Nova reuniao nao entrou"
        assert (primeira["data_reuniao"], primeira["data_origem"]) == (
            "2026-07-02T11:49:13Z",
            "gravacao",
        )

        # revisao + edicao do titulo no Detalhe: S0 corrigido para Luciano
        # (so nomear), S1 ignorado
        primeira["titulo"] = "Comitê de produto — julho"
        primeira["clusters"]["SPEAKER_00"].update(
            {"nome": "Luciano", "confirmado": True, "sem_aprender": True}
        )
        primeira["clusters"]["SPEAKER_01"].update(
            {"nome": "IGNORADO_SPEAKER_01", "confirmado": True, "nome_antes_de_ignorar": "Amanda"}
        )
        nucleo.escrever_atomico(j, nucleo.json_para_disco(primeira))

        # 2a rodada: o MESMO audio, labels trocados, sugestao diferente
        turnos2 = [(0.0, 10.0, "SPEAKER_01"), (10.0, 20.0, "SPEAKER_00")]
        _rodar_run_main(
            audio,
            db,
            turnos2,
            {"SPEAKER_01": cluster("Ramiro"), "SPEAKER_00": cluster("Celso")},
            palavras,
        )
        segunda = json.loads(j.read_text(encoding="utf-8"))

        assert segunda["titulo"] == "Comitê de produto — julho"
        assert segunda["reuniao_id"] == primeira["reuniao_id"]
        assert (segunda["data_reuniao"], segunda["data_origem"]) == (
            "2026-07-02T11:49:13Z",
            "gravacao",
        )
        c = segunda["clusters"]
        assert (
            c["SPEAKER_01"]["nome"],
            c["SPEAKER_01"]["confirmado"],
            c["SPEAKER_01"].get("sem_aprender"),
        ) == ("Luciano", True, True)
        assert (
            c["SPEAKER_00"]["nome"],
            c["SPEAKER_00"]["confirmado"],
            c["SPEAKER_00"].get("nome_antes_de_ignorar"),
        ) == ("IGNORADO_SPEAKER_00", True, "Amanda")
        assert {f["falante"] for f in segunda["falas"]} <= {"Luciano", "IGNORADO_SPEAKER_00"}
        assert "Comitê" in (pasta / "reuniao_01.json").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_titulo_editado_durante_o_reprocessamento_nao_e_sobrescrito():
    """O pipeline.py le o .json anterior no INICIO; um titulo editado na tela
    enquanto ele roda (minutos) tem de sobreviver - o pipeline.py rele o .json
    na hora de gravar. A "tela" aqui e o duble da transcricao, que edita o
    titulo no meio da execucao."""
    import json
    import tempfile

    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-reprocessar-"))
    try:
        audio = pasta / "reuniao_01.m4a"
        _m4a(audio, "2026-07-02T11:49:13.000000Z")
        db = pasta / "vozes_teste.db"
        mapa = {
            "SPEAKER_00": {
                "nome": "Ramiro",
                "sim": 0.9,
                "margem": 0.5,
                "fala_s": 30.0,
                "scores": {},
            }
        }
        palavras = [(i * 0.5, i * 0.5 + 0.4, f" p{i}") for i in range(20)]
        turnos = [(0.0, 10.0, "SPEAKER_00")]
        _rodar_run_main(audio, db, turnos, mapa, palavras)
        j = pasta / "reuniao_01.json"
        d = json.loads(j.read_text(encoding="utf-8"))
        d["titulo"] = "Antes"
        nucleo.escrever_atomico(j, nucleo.json_para_disco(d))

        def editando_no_meio(*a, **k):
            atual = json.loads(j.read_text(encoding="utf-8"))
            atual["titulo"] = "Editado durante"
            nucleo.escrever_atomico(j, nucleo.json_para_disco(atual))
            return palavras_de(palavras)

        originais = (
            pipeline.diarizar,
            pipeline.identificar,
            pipeline.transcrever,
            nucleo.DB_PATH,
            sys.argv,
        )
        try:
            pipeline.diarizar = lambda *a, **k: (Anotacao(turnos), Anotacao(turnos))
            pipeline.identificar = lambda *a, **k: json.loads(json.dumps(mapa))
            pipeline.transcrever = editando_no_meio
            nucleo.DB_PATH = db
            sys.argv = [
                "pipeline.py",
                str(audio),
                "--sem-termos",
                "--device",
                "cpu",
                "--asr",
                "mlx",
            ]
            with redirect_stdout(io.StringIO()):
                processar_cli.main()
        finally:
            (
                pipeline.diarizar,
                pipeline.identificar,
                pipeline.transcrever,
                nucleo.DB_PATH,
                sys.argv,
            ) = originais
        assert json.loads(j.read_text(encoding="utf-8"))["titulo"] == "Editado durante"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# --------------------------------------------------------------------------
# preservar_revisao: decisoes da revisao casadas pelo TRECHO de audio
# --------------------------------------------------------------------------


def _anterior_revisada():
    """Reuniao revisada com as quatro decisoes possiveis, labels 00..04."""
    turnos = [
        [0, 60, "SPEAKER_00"],
        [60, 120, "SPEAKER_01"],
        [120, 180, "SPEAKER_02"],
        [180, 240, "SPEAKER_03"],
        [240, 300, "SPEAKER_04"],
    ]
    clusters = {
        # o pipeline disse Ramiro; a revisao corrigiu para Luciano
        "SPEAKER_00": {"nome": "Luciano", "confirmado": True},
        # ignorado, guardando quem era
        "SPEAKER_01": {
            "nome": "IGNORADO_SPEAKER_01",
            "confirmado": True,
            "nome_antes_de_ignorar": "Rolando",
        },
        # so nomeado
        "SPEAKER_02": {"nome": "Celso", "confirmado": True, "sem_aprender": True},
        # DESCONHECIDO que ganhou nome na revisao
        "SPEAKER_03": {"nome": "Gerardo", "confirmado": True},
        # ainda nao revisado
        "SPEAKER_04": {"nome": "Amanda"},
    }
    return {"reuniao_id": "r", "turnos": turnos, "clusters": clusters}


def test_preservar_revisao_herda_as_decisoes_mesmo_com_labels_renumerados():
    anterior = _anterior_revisada()
    # a diarizacao nova renumerou: o mesmo audio, labels em outra ordem, e
    # o pipeline identificou diferente do que a revisao decidiu
    turnos_novos = [
        (0, 61, "SPEAKER_03"),
        (61, 119, "SPEAKER_00"),
        (119, 180, "SPEAKER_04"),
        (180, 240, "SPEAKER_01"),
        (240, 300, "SPEAKER_02"),
    ]
    mapa = {
        "SPEAKER_03": {"nome": "Ramiro"},
        "SPEAKER_00": {"nome": "Rolando"},
        "SPEAKER_04": {"nome": "Celso"},
        "SPEAKER_01": {"nome": "DESCONHECIDO_SPEAKER_01"},
        "SPEAKER_02": {"nome": "Amanda"},
    }
    remapa = pipeline.preservar_revisao(mapa, turnos_novos, anterior)

    assert mapa["SPEAKER_03"] == {"nome": "Luciano", "confirmado": True}, (
        "a correcao da revisao nao pode voltar para o nome sugerido"
    )
    assert mapa["SPEAKER_00"] == {
        "nome": "IGNORADO_SPEAKER_00",
        "confirmado": True,
        "nome_antes_de_ignorar": "Rolando",
    }
    assert mapa["SPEAKER_04"] == {"nome": "Celso", "confirmado": True, "sem_aprender": True}
    assert mapa["SPEAKER_01"] == {"nome": "Gerardo", "confirmado": True}
    assert mapa["SPEAKER_02"] == {"nome": "Amanda"}, "nao revisado continua a revisar"
    assert remapa == {
        "SPEAKER_00": "SPEAKER_03",
        "SPEAKER_01": "SPEAKER_00",
        "SPEAKER_02": "SPEAKER_04",
        "SPEAKER_03": "SPEAKER_01",
        "SPEAKER_04": "SPEAKER_02",
    }


def test_preservar_revisao_nao_herda_em_cluster_misturado():
    """Cluster novo que junta dois antigos e uma mistura: herdar a decisao
    de um deles confirmaria em silencio um cluster que ninguem ouviu."""
    anterior = _anterior_revisada()
    turnos_novos = [
        (0, 120, "SPEAKER_00"),  # 00 + 01 antigos juntos
        (120, 180, "SPEAKER_01"),
        (180, 300, "SPEAKER_02"),
    ]
    mapa = {
        "SPEAKER_00": {"nome": "Luciano"},
        "SPEAKER_01": {"nome": "Celso"},
        "SPEAKER_02": {"nome": "Gerardo"},
    }
    pipeline.preservar_revisao(mapa, turnos_novos, anterior)
    assert "confirmado" not in mapa["SPEAKER_00"]
    assert mapa["SPEAKER_01"]["confirmado"] is True
    assert "confirmado" not in mapa["SPEAKER_02"], "juntou 03 e 04 antigos"


def test_preservar_revisao_cluster_sem_par_fica_a_revisar():
    anterior = _anterior_revisada()
    turnos_novos = [(0, 60, "SPEAKER_00"), (400, 500, "SPEAKER_09")]
    mapa = {"SPEAKER_00": {"nome": "Ramiro"}, "SPEAKER_09": {"nome": "Luciano"}}
    remapa = pipeline.preservar_revisao(mapa, turnos_novos, anterior)
    assert mapa["SPEAKER_00"]["nome"] == "Luciano"
    assert mapa["SPEAKER_09"] == {"nome": "Luciano"}
    assert remapa == {"SPEAKER_00": "SPEAKER_00"}


def test_preservar_revisao_sem_turnos_antigos_cai_no_casamento_por_nome():
    anterior = {"clusters": {"SPEAKER_00": {"nome": "Celso", "confirmado": True}}}
    mapa = {"SPEAKER_05": {"nome": "Celso"}}
    assert pipeline.preservar_revisao(mapa, [(0, 10, "SPEAKER_05")], anterior) is None
    assert mapa["SPEAKER_05"]["confirmado"] is True
    assert pipeline.preservar_revisao({}, [], None) is None


def test_preservar_confirmacoes_herda_quando_o_nome_e_o_mesmo():
    """
    Reprocessar nao pode desfazer uma revisao humana que continua valida.
    Compara por NOME, nao por label - a diarizacao nao garante a mesma
    numeracao de SPEAKER_XX entre rodadas. O cluster novo (label
    diferente) resolveu para o MESMO nome de um cluster ja confirmado
    antes: o confirmado tem que sobreviver.
    """
    anterior = {
        "clusters": {
            "SPEAKER_00": {"nome": "Celso", "confirmado": True},
        }
    }
    mapa = {"SPEAKER_02": {"nome": "Celso", "sim": 0.9}}
    pipeline.preservar_confirmacoes(mapa, anterior)
    assert mapa["SPEAKER_02"]["confirmado"] is True


def test_preservar_confirmacoes_nao_herda_quando_o_nome_mudou():
    """Nome diferente: a revisao anterior era sobre outra identificacao,
    nao vale mais para esta - "confirmado" nao pode aparecer."""
    anterior = {
        "clusters": {
            "SPEAKER_00": {"nome": "Celso", "confirmado": True},
        }
    }
    mapa = {"SPEAKER_00": {"nome": "Ramiro", "sim": 0.9}}
    pipeline.preservar_confirmacoes(mapa, anterior)
    assert "confirmado" not in mapa["SPEAKER_00"]


def test_preservar_confirmacoes_no_op_sem_execucao_anterior():
    mapa = {"SPEAKER_00": {"nome": "Celso", "sim": 0.9}}
    pipeline.preservar_confirmacoes(mapa, None)
    assert "confirmado" not in mapa["SPEAKER_00"]


# ==========================================================================
# amostragem temporal (fase0)
# ==========================================================================


def test_amostras_cobrem_inicio_e_fim():
    """
    REGRESSAO: a amostragem parava a 07:00 de uma reuniao de 09:00, escondendo
    justamente o fim, onde a voz mais deriva (pessoa recostada, cansaco).
    """
    from ferramentas import fase0

    class S:
        def __init__(self, a, b):
            self.start, self.end = a, b

    segs = [S(i * 60.0, i * 60.0 + 4.0) for i in range(10)]
    esc = fase0.amostras_espalhadas(segs, 4)
    assert esc[0].start == 0.0, "primeiro trecho tem de entrar"
    assert esc[-1].start == segs[-1].start, "ultimo trecho tem de entrar"


def test_amostras_menos_segmentos_que_pedido():
    from ferramentas import fase0

    class S:
        def __init__(self, a, b):
            self.start, self.end = a, b

    esc = fase0.amostras_espalhadas([S(0, 3), S(10, 14)], 8)
    assert len(esc) == 2


# ==========================================================================


def _rodar_sem_pytest():
    testes = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = []
    for nome, fn in testes:
        try:
            fn()
            print(f"  \033[92mPASSOU\033[0m  {nome}")
        except AssertionError as e:
            falhas.append((nome, e))
            print(f"  \033[91mFALHOU\033[0m  {nome}\n            {e}")
        except Exception as e:
            falhas.append((nome, e))
            print(f"  \033[91mERRO\033[0m    {nome}\n            {type(e).__name__}: {e}")
    print(f"\n{len(testes) - len(falhas)}/{len(testes)} passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(_rodar_sem_pytest())
