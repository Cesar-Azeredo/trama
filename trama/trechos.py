"""
trechos.py - "Trechos para conferir", a terceira etapa da revisao, depois
das vozes e dos termos (ADR 0028).

Escolhe, sozinho e sem IA, onde vale a pessoa ouvir e escrever o que foi
dito:

  - ate MAX_FALAS falas de confianca baixa (a mesma regra da marca do
    Detalhe: confianca_media abaixo do limiar, com o piso de palavras), as
    mais longas;
  - ate MAX_LACUNAS lacunas sem texto de MIN_LACUNA_S ou mais, as mais
    longas.

No maximo MAX_FALAS + MAX_LACUNAS (5) por reuniao. Uma lista unica so por
duracao mostraria apenas falas: elas sempre sao mais longas que lacunas
(medido nas 13 reunioes reais: nenhuma lacuna passa de 2,0 s; falas de
confianca baixa chegam a 25 s).

Respostas:
  - fala: a correcao manual que ja existe (edicao.py, ADR 0016);
  - lacuna: o texto fica DENTRO da propria lacuna (lacuna["texto_manual"]),
    nunca no texto da fala - a lacuna e um ponto de insercao, nao ocupa
    caractere, entao nenhuma marca de posicao muda;
  - "Nao da para entender": lacuna["ininteligivel"] ou
    fala["ininteligivel"] - nunca perguntado de novo;
  - "Pular": nada gravado (so a tela).

Ao reprocessar, preservar() casa cada resposta com a lacuna/fala nova pelo
TEMPO (metade de cada uma no mesmo trecho, como as correcoes de fala).
Texto de lacuna sem par nunca some: vai para dados["lacunas_sem_lugar"] e
volta se um reprocessamento futuro achar a lacuna.

Nada daqui escreve no log: e conteudo da reuniao (CLAUDE.md, regra 3).
"""

from datetime import datetime, timezone

from trama import edicao

MAX_FALAS = 3
MAX_LACUNAS = 2
MIN_LACUNA_S = 1.5
# Trecho tocado da lacuna: um pouco de antes e de depois, dentro da fala -
# o silencio sozinho nao diz nada.
FOLGA_AUDIO_S = 3.0
CONTEXTO = 70
# Tolerancia para achar a lacuna pelo tempo que a tela mandou (o .json
# guarda com 2 casas).
TOLERANCIA_S = 1e-3
CAMPO_TEXTO = "texto_manual"
CAMPO_ININTELIGIVEL = "ininteligivel"


class LacunaNaoEncontrada(LookupError):
    """Nenhuma lacuna com aquele inicio/fim - reprocessada no meio, ou a
    fala dela foi corrigida a mao."""


def _agora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _duracao(x):
    return x["fim"] - x["inicio"]


def _contar_palavras(texto):
    return len(texto.split())


def fala_de_confianca_baixa(fala, limiar, min_palavras):
    """Mesma regra da marca "confiança baixa" do Detalhe (Detalhe.tsx)."""
    return (
        not edicao.esta_editada(fala)
        and "confianca_media" in fala
        and limiar is not None
        and fala["confianca_media"] < limiar
        and _contar_palavras(fala["texto"]) >= (min_palavras or 0)
    )


def _respondida(lacuna):
    return CAMPO_TEXTO in lacuna or lacuna.get(CAMPO_ININTELIGIVEL)


def _dentro(lacuna, fala):
    return lacuna["inicio"] >= fala["inicio"] and lacuna["fim"] <= fala["fim"]


def _item_fala(indice, fala):
    return {
        "tipo": "fala",
        "indice": indice,
        "inicio": fala["inicio"],
        "fim": fala["fim"],
        "falante": fala["falante"],
        "audio_inicio": fala["inicio"],
        "audio_fim": fala["fim"],
        "texto": fala["texto"],
    }


def _item_lacuna(indice, fala, lacuna):
    texto = fala["texto"]
    p = min(lacuna["posicao"], len(texto))
    return {
        "tipo": "lacuna",
        "indice": indice,
        "inicio": lacuna["inicio"],
        "fim": lacuna["fim"],
        "falante": fala["falante"],
        "audio_inicio": max(fala["inicio"], lacuna["inicio"] - FOLGA_AUDIO_S),
        "audio_fim": min(fala["fim"], lacuna["fim"] + FOLGA_AUDIO_S),
        "antes": texto[max(0, p - CONTEXTO) : p],
        "depois": texto[p : p + CONTEXTO],
    }


def trechos_para_conferir(dados):
    """
    [item] na ordem da reuniao - no maximo MAX_FALAS falas e MAX_LACUNAS
    lacunas. `dados` e o .json da reuniao. Fala ja corrigida a mao ou
    marcada "nao da para entender" nao entra; lacuna ja respondida
    tambem nao, nem a que fica dentro de uma das falas escolhidas
    (corrigir a fala tira as lacunas dela - a pergunta sumiria no meio).
    """
    falas = dados.get("falas") or []
    limiar = dados.get("limiar_confianca_fala")
    min_palavras = dados.get("min_palavras_confianca_fala")

    candidatas = [
        (i, f)
        for i, f in enumerate(falas)
        if not f.get(CAMPO_ININTELIGIVEL) and fala_de_confianca_baixa(f, limiar, min_palavras)
    ]
    candidatas.sort(key=lambda c: (-_duracao(c[1]), c[1]["inicio"]))
    escolhidas = candidatas[:MAX_FALAS]

    lacunas = []
    for lacuna in dados.get("lacunas_sem_texto") or []:
        if _duracao(lacuna) < MIN_LACUNA_S - TOLERANCIA_S or _respondida(lacuna):
            continue
        dona = next(((i, f) for i, f in enumerate(falas) if _dentro(lacuna, f)), None)
        if dona is None or edicao.esta_editada(dona[1]):
            continue
        if any(_dentro(lacuna, f) for _, f in escolhidas):
            continue
        lacunas.append((dona[0], dona[1], lacuna))
    lacunas.sort(key=lambda c: (-_duracao(c[2]), c[2]["inicio"]))

    itens = [_item_fala(i, f) for i, f in escolhidas]
    itens += [_item_lacuna(i, f, lac) for i, f, lac in lacunas[:MAX_LACUNAS]]
    itens.sort(key=lambda item: item["inicio"])
    return itens


# --------------------------------------------------------------------------
# respostas
# --------------------------------------------------------------------------


def _achar_lacuna(dados, inicio, fim):
    for lacuna in dados.get("lacunas_sem_texto") or []:
        if (
            abs(lacuna["inicio"] - float(inicio)) <= TOLERANCIA_S
            and abs(lacuna["fim"] - float(fim)) <= TOLERANCIA_S
        ):
            return lacuna
    raise LacunaNaoEncontrada((inicio, fim))


def escrever_lacuna(dados, inicio, fim, bruto):
    """O que foi dito na lacuna, gravado DENTRO dela (em memoria; quem chama
    grava o .json). Mesma validacao do texto de fala. Devolve a lacuna."""
    texto = edicao.validar_texto(bruto)
    lacuna = _achar_lacuna(dados, inicio, fim)
    lacuna[CAMPO_TEXTO] = texto
    lacuna["escrito_em"] = _agora()
    lacuna.pop(CAMPO_ININTELIGIVEL, None)
    return lacuna


def marcar_lacuna_ininteligivel(dados, inicio, fim):
    lacuna = _achar_lacuna(dados, inicio, fim)
    lacuna[CAMPO_ININTELIGIVEL] = True
    return lacuna


def marcar_fala_ininteligivel(dados, indice, inicio):
    """ "Nao da para entender" numa fala de confianca baixa. Mesma checagem
    de indice + inicio da correcao (edicao.FalaMudou)."""
    fala = edicao._fala(dados, indice, inicio)
    fala[CAMPO_ININTELIGIVEL] = True
    return fala


# --------------------------------------------------------------------------
# texto corrido (.txt)
# --------------------------------------------------------------------------


def texto_com_lacunas_escritas(fala, lacunas):
    """O texto da fala com o que foi escrito em cada lacuna dela, no ponto
    da lacuna. Fala corrigida a mao nao tem lacunas (edicao.py)."""
    escritas = sorted(
        (lac for lac in lacunas or () if CAMPO_TEXTO in lac and _dentro(lac, fala)),
        key=lambda lac: lac["posicao"],
    )
    if not escritas or edicao.esta_editada(fala):
        return fala["texto"]
    texto, partes, anterior = fala["texto"], [], 0
    for lac in escritas:
        p = min(lac["posicao"], len(texto))
        partes.append(texto[anterior:p])
        partes.append(f" {lac[CAMPO_TEXTO]} ")
        anterior = p
    partes.append(texto[anterior:])
    return " ".join("".join(partes).split())


# --------------------------------------------------------------------------
# reprocessamento
# --------------------------------------------------------------------------


def _respostas_de_lacuna(dados_anteriores):
    """Toda lacuna respondida da execucao anterior: na lista da reuniao,
    guardada dentro de uma fala corrigida (marcas_originais) ou ja sem
    lugar numa execucao antes dela."""
    if not dados_anteriores:
        return []
    todas = list(dados_anteriores.get("lacunas_sem_texto") or [])
    for f in dados_anteriores.get("falas") or []:
        marcas = (f.get(edicao.CHAVE) or {}).get("marcas_originais") or {}
        todas += marcas.get("lacunas_sem_texto") or []
    todas += dados_anteriores.get("lacunas_sem_lugar") or []
    return [lac for lac in todas if _respondida(lac)]


def _melhor_par(antiga, novas, usadas):
    candidatas = [
        (i, edicao._sobreposicao(antiga, n))
        for i, n in enumerate(novas)
        if i not in usadas and edicao._casa(antiga, n)
    ]
    return max(candidatas, key=lambda c: c[1])[0] if candidatas else None


def preservar(falas, lacunas, dados_anteriores):
    """
    Reaplica nas lacunas e falas NOVAS as respostas da execucao anterior,
    casando pelo tempo. Muta `falas` e `lacunas` no lugar. Rodar ANTES de
    edicao.preservar_edicoes: uma lacuna respondida dentro de uma fala que
    volta a ser corrigida viaja com ela para marcas_originais.

    Devolve as lacunas respondidas que nao acharam par - so as com texto
    (um "nao da para entender" sem lugar nao tem o que guardar).
    """
    sem_lugar, usadas = [], set()
    for antiga in _respostas_de_lacuna(dados_anteriores):
        i = _melhor_par(antiga, lacunas, usadas)
        if i is None:
            if CAMPO_TEXTO in antiga:
                sem_lugar.append(
                    {
                        k: antiga[k]
                        for k in ("inicio", "fim", "falante", CAMPO_TEXTO, "escrito_em")
                        if k in antiga
                    }
                )
            continue
        usadas.add(i)
        for campo in (CAMPO_TEXTO, "escrito_em", CAMPO_ININTELIGIVEL):
            if campo in antiga:
                lacunas[i][campo] = antiga[campo]

    usadas_falas = set()
    for antiga in (dados_anteriores or {}).get("falas") or []:
        if not antiga.get(CAMPO_ININTELIGIVEL):
            continue
        i = _melhor_par(antiga, falas, usadas_falas)
        if i is not None:
            usadas_falas.add(i)
            falas[i][CAMPO_ININTELIGIVEL] = True
    return sem_lugar
