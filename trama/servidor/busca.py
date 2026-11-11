"""
servidor/busca.py - busca por trecho da fala nas reunioes ja processadas.

Mesmo criterio da busca da lista (frontend/src/telas/Lista.tsx:casaBusca):
sem diferenciar acento nem maiuscula, e CADA palavra digitada tem de
aparecer - aqui, na mesma fala. Devolve, por reuniao, as falas que casam:
quem falou, o horario e um trecho do texto em volta, com as posicoes a
destacar DENTRO desse trecho. A tela desenha o destaque como texto
(<mark>), nunca como HTML (CLAUDE.md, regra 9).

A comparacao e feita no texto normalizado (sem acento, minusculo), mas as
posicoes devolvidas sao no texto ORIGINAL: "voce" acha "Você", e o
destaque marca o "Você" inteiro. _normalizar_com_mapa guarda, para cada
caractere normalizado, de qual caractere original ele veio.

Nunca registra a busca nem o texto no log (CLAUDE.md, regra 3).

Cache em memoria por arquivo (tamanho + mtime): cada .json e lido e
normalizado uma vez, nao a cada tecla digitada na busca.
"""

import json
import threading
import unicodedata

from trama.servidor import reunioes

MAX_BUSCA_LEN = 200
MAX_TRECHOS_POR_REUNIAO = 20
MARGEM_TRECHO = 60  # caracteres de contexto antes e depois da primeira palavra

_cache = {}
_trava = threading.Lock()


def _normalizar_com_mapa(texto):
    """(texto_normalizado, mapa): mapa[i] = indice no texto original do
    caractere normalizado i. Remove acento (NFD sem as marcas
    combinantes) e poe em minusculo, caractere a caractere - um "ç"
    vira "c", e o "c" aponta de volta para o "ç"."""
    saida, mapa = [], []
    for i, c in enumerate(texto):
        for d in unicodedata.normalize("NFD", c):
            if unicodedata.combining(d):
                continue
            for m in d.lower():
                saida.append(m)
                mapa.append(i)
    return "".join(saida), mapa


def normalizar(texto):
    return _normalizar_com_mapa(texto)[0]


def _falas_normalizadas(caminho_json):
    """[(fala, texto_normalizado, mapa)] de uma reuniao, com cache por
    tamanho + mtime do .json (um .json regravado - revisao, glossario,
    reprocessamento - recalcula sozinho)."""
    st = caminho_json.stat()
    chave = (str(caminho_json), st.st_size, st.st_mtime_ns)
    with _trava:
        if chave in _cache:
            return _cache[chave]
    dados = json.loads(caminho_json.read_text(encoding="utf-8"))
    falas = [(f, *_normalizar_com_mapa(f.get("texto", ""))) for f in dados.get("falas", [])]
    with _trava:
        for k in [k for k in _cache if k[0] == chave[0]]:
            del _cache[k]
        _cache[chave] = falas
    return falas


def _trecho(texto, mapa, ocorrencias):
    """Janela do texto original em volta da primeira ocorrencia, com as
    ocorrencias (em indices do original) relativas ao inicio da janela.
    Reticencias quando a janela corta o texto."""
    ini_orig = min(mapa[a] for a, _ in ocorrencias)
    ini = max(0, ini_orig - MARGEM_TRECHO)
    fim = min(len(texto), ini_orig + MARGEM_TRECHO * 2)
    # nao cortar palavra no meio: anda ate o espaco mais proximo
    if ini > 0:
        espaco = texto.find(" ", ini)
        if espaco != -1 and espaco < ini_orig:
            ini = espaco + 1
    if fim < len(texto):
        espaco = texto.rfind(" ", ini_orig, fim)
        if espaco != -1:
            fim = espaco
    prefixo = "…" if ini > 0 else ""
    sufixo = "…" if fim < len(texto) else ""
    destaques = []
    for a, b in sorted(ocorrencias):
        o_ini, o_fim = mapa[a], mapa[b - 1] + 1
        if o_ini < ini or o_fim > fim:
            continue
        d_ini, d_fim = o_ini - ini + len(prefixo), o_fim - ini + len(prefixo)
        # palavras da busca que se sobrepoem no texto ("reun" e "reuniao")
        # viram UM destaque - nunca marcacao dentro de marcacao.
        if destaques and d_ini <= destaques[-1][1]:
            destaques[-1][1] = max(destaques[-1][1], d_fim)
        else:
            destaques.append([d_ini, d_fim])
    return prefixo + texto[ini:fim] + sufixo, destaques


def buscar(consulta):
    """
    [{"id", "trechos": [{"inicio", "falante", "texto", "destaques"}],
      "total"}] das reunioes processadas com pelo menos uma fala que tem
    TODAS as palavras da consulta. "total" conta as falas que casaram;
    "trechos" vem limitado a MAX_TRECHOS_POR_REUNIAO, na ordem da reuniao.
    Consulta vazia devolve [].
    """
    palavras = normalizar(consulta).split()
    if not palavras:
        return []
    resultado = []
    if not reunioes.PASTA_AUDIOS.is_dir():
        return resultado
    for pasta in sorted(reunioes.PASTA_AUDIOS.iterdir(), reverse=True):
        if not pasta.is_dir() or not reunioes.PADRAO_ID.fullmatch(pasta.name):
            continue
        caminho = pasta / f"{pasta.name}.json"
        if not caminho.exists():
            continue
        trechos, total = [], 0
        for fala, norm, mapa in _falas_normalizadas(caminho):
            if not all(p in norm for p in palavras):
                continue
            total += 1
            if len(trechos) >= MAX_TRECHOS_POR_REUNIAO:
                continue
            ocorrencias = []
            for p in palavras:
                ini = norm.find(p)
                while ini != -1:
                    ocorrencias.append((ini, ini + len(p)))
                    ini = norm.find(p, ini + len(p))
            texto, destaques = _trecho(fala["texto"], mapa, ocorrencias)
            trechos.append(
                {
                    "inicio": fala["inicio"],
                    "falante": fala["falante"],
                    "texto": texto,
                    "destaques": destaques,
                }
            )
        if total:
            resultado.append({"id": pasta.name, "trechos": trechos, "total": total})
    return resultado
