"""
servidor/conferir.py - "Termos para conferir", a etapa da revisao depois das
vozes (ADR 0022). Aponta sozinho, sem IA, o que vale a pessoa olhar:

  - siglas: 2 a 5 letras maiusculas;
  - palavras de 4 letras ou mais que o Whisper marcou em
    palavras_baixa_confianca 2 vezes ou mais nesta reuniao, em pelo menos
    metade das vezes em que ela aparece aqui, e que aparecem em no maximo
    MAX_REUNIOES_PALAVRA reunioes (palavra comum aparece em todas);

fora sempre: nomes da galeria, termos da empresa (e cada palavra deles),
formas que ja tem correcao, e formas ja respondidas (glossario,
"#! forma"). No maximo MAX_ITENS, os mais frequentes primeiro - passou
disso, a etapa vira trabalho em vez de ajuda.

Criterio medido nas 13 reunioes reais antes de implementar: de 2 a 10
itens por reuniao, com a memoria das respostas valendo de uma para a
outra; sem os filtros de tamanho e de frequencia, eram 24 a 115 por
reuniao, quase todos "e", "o", "que".

Nada daqui vai para o log: e texto da reuniao (CLAUDE.md, regra 3).
"""

import json
import re

from trama import nucleo, termos
from trama.servidor import glossario, reunioes

MAX_ITENS = 10
MIN_LETRAS_PALAVRA = 4
MIN_MARCAS = 2
FRACAO_MIN_DUVIDA = 0.5
MAX_REUNIOES_PALAVRA = 4
CONTEXTO = 70
# Trecho tocado: a palavra com um pouco de antes e depois, dentro da fala.
FOLGA_AUDIO_S = 3.0

_SIGLA = re.compile(r"\b[A-Z]{2,5}\b")
_PALAVRA = re.compile(r"\w+(?:[.'\-]\w+)*")


def _chave(texto):
    return termos.sem_acento(texto).lower().strip(".,;:!?\"'()…-")


def _excluidos():
    fora = set()
    try:
        fora |= {_chave(n) for n, _, _ in nucleo.listar_pessoas()}
    except Exception:
        pass
    for termo, _ in glossario.vocabulario():
        fora.add(_chave(termo))
        fora |= {_chave(w) for w in termo.split()}
    fora |= {_chave(i["errado"]) for i in glossario.ler() if i["tipo"] == "regra"}
    fora |= {_chave(r) for r in glossario.ler_respondidos()}
    return fora


def _em_quantas_reunioes():
    contagem = {}
    if not reunioes.PASTA_AUDIOS.is_dir():
        return contagem
    for pasta in reunioes.PASTA_AUDIOS.iterdir():
        caminho = pasta / f"{pasta.name}.json"
        if not pasta.is_dir() or not caminho.exists():
            continue
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        vistas = {_chave(w) for f in dados.get("falas") or [] for w in f["texto"].split()}
        for w in vistas:
            contagem[w] = contagem.get(w, 0) + 1
    return contagem


def _aparar(texto, a, b):
    """Tira pontuacao e espaco das pontas: a marca de duvida do Whisper
    leva a pontuacao junto ("Office.", "-coins")."""
    while a < b and not texto[a].isalnum():
        a += 1
    while b > a and not texto[b - 1].isalnum():
        b -= 1
    return a, b


def _ocorrencia(indice, fala, a, b, duvida):
    tempos = [w for w in fala.get("palavras_tempo") or [] if a <= w[0] < b]
    ini = tempos[0][2] if tempos else fala["inicio"]
    fim = tempos[-1][3] if tempos else fala["fim"]
    texto = fala["texto"]
    return {
        "indice": indice,
        "posicao": a,
        "comprimento": b - a,
        "inicio": ini,
        "audio_inicio": max(fala["inicio"], ini - FOLGA_AUDIO_S),
        "audio_fim": min(fala["fim"], fim + FOLGA_AUDIO_S),
        "antes": texto[max(0, a - CONTEXTO) : a],
        "trecho": texto[a:b],
        "depois": texto[b : b + CONTEXTO],
        "duvida": duvida,
    }


def _ler_falas(id):
    pasta = reunioes.resolver_pasta(id)
    caminho = pasta / f"{id}.json"
    if not caminho.exists():
        raise reunioes.ReuniaoNaoEncontrada(id)
    return json.loads(caminho.read_text(encoding="utf-8")).get("falas") or []


def _falas_nao_editadas(falas):
    """(indice, fala) das falas que nao foram corrigidas a mao."""
    return [(indice, f) for indice, f in enumerate(falas) if "edicao_manual" not in f]


class _Candidatos:
    """chave -> {formas, total, ocorrencias}, na ordem em que aparecem."""

    def __init__(self):
        self.por_chave = {}

    def anotar(self, chave, forma, indice, fala, a, b, duvida):
        c = self.por_chave.setdefault(chave, {"formas": {}, "total": 0, "ocorrencias": []})
        c["formas"][forma] = c["formas"].get(forma, 0) + 1
        c["total"] += 1
        c["ocorrencias"].append(_ocorrencia(indice, fala, a, b, duvida))

    def itens(self):
        itens = []
        for c in self.por_chave.values():
            ocorrencias = sorted(c["ocorrencias"], key=lambda o: not o["duvida"])
            itens.append(
                {
                    "forma": max(c["formas"], key=c["formas"].get),
                    "total": c["total"],
                    "ocorrencia": ocorrencias[0],
                }
            )
        itens.sort(key=lambda i: (-i["total"], i["forma"].lower()))
        return itens[:MAX_ITENS]


def _duvidas_por_palavra(falas):
    """chave -> [(indice, fala, inicio, fim)] de cada marca de duvida do
    Whisper, aparada para a palavra."""
    duvidas = {}
    for indice, f in _falas_nao_editadas(falas):
        for marca in f.get("palavras_baixa_confianca") or []:
            a, b = _aparar(f["texto"], marca["posicao"], marca["posicao"] + marca["comprimento"])
            if b <= a:
                continue
            duvidas.setdefault(_chave(f["texto"][a:b]), []).append((indice, f, a, b))
    return duvidas


def _duvida_repetida(chave, lugares, total, em_quantas, fora):
    """Palavra que o Whisper marcou varias vezes, na maior parte das vezes
    em que ela aparece, rara no conjunto de reunioes e ainda desconhecida."""
    return not (
        len(chave) < MIN_LETRAS_PALAVRA
        or len(lugares) < MIN_MARCAS
        or len(lugares) / max(total.get(chave, 0), 1) < FRACAO_MIN_DUVIDA
        or em_quantas.get(chave, 0) > MAX_REUNIOES_PALAVRA
        or chave in fora
    )


def _anotar_duvidas(candidatos, falas, fora):
    """Palavras com duvida repetida. Devolve as chaves que entraram."""
    em_quantas = _em_quantas_reunioes()
    total = {}
    for f in falas:
        for w in f["texto"].split():
            total[_chave(w)] = total.get(_chave(w), 0) + 1

    vindas_da_duvida = set()
    for chave, lugares in _duvidas_por_palavra(falas).items():
        if not _duvida_repetida(chave, lugares, total, em_quantas, fora):
            continue
        vindas_da_duvida.add(chave)
        for indice, f, a, b in lugares:
            candidatos.anotar(chave, f["texto"][a:b], indice, f, a, b, True)
    return vindas_da_duvida


def _anotar_siglas(candidatos, falas, ignorar):
    for indice, f in _falas_nao_editadas(falas):
        marcadas = [
            (m["posicao"], m["posicao"] + m["comprimento"])
            for m in f.get("palavras_baixa_confianca") or []
        ]
        for m in _SIGLA.finditer(f["texto"]):
            chave = _chave(m.group())
            if chave in ignorar:
                continue
            duvida = any(x < m.end() and y > m.start() for x, y in marcadas)
            candidatos.anotar(chave, m.group(), indice, f, m.start(), m.end(), duvida)


def termos_para_conferir(id):
    """[{forma, total, ocorrencia}] - no maximo MAX_ITENS, mais frequentes
    primeiro. `ocorrencia` e a primeira em que o Whisper duvidou (senao, a
    primeira), com o trecho em volta e o intervalo de audio para tocar."""
    falas = _ler_falas(id)
    fora = _excluidos()
    candidatos = _Candidatos()
    vindas_da_duvida = _anotar_duvidas(candidatos, falas, fora)
    # palavra que ja entrou pelas duvidas (uma sigla marcada duas vezes)
    # nao conta de novo como sigla
    _anotar_siglas(candidatos, falas, fora | vindas_da_duvida)
    return candidatos.itens()
