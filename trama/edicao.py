"""
edicao.py - correcao manual do texto de uma fala (ADR 0016).

Para o que nenhuma regra do glossario pode corrigir sem estragar texto
certo em outra reuniao ("questão à vista" e portugues; numa fala especifica,
era "Tabela à Vista").

A fala editada guarda tudo o que era antes em fala["edicao_manual"]:

  {"texto_original": texto da maquina (ja com o glossario),
   "editado_em": ISO UTC,
   "marcas_originais": {campo: valor}}  # so o que existia

As marcas ancoradas em posicao de CARACTERE (palavras_divergentes,
palavras_baixa_confianca, palavras_tempo e as lacunas_sem_texto da fala)
nao sabem onde cair num texto escrito a mao: saem da fala - ausente e
ausente, nunca recalculado. Ficam so dentro de marcas_originais, para
desfazer devolver a fala exatamente como era.

Quem respeita a edicao:
  - termos.aplicar_em_falas pula fala editada (glossario nunca sobrescreve);
  - pipeline.py casa a edicao com a fala nova pelo TEMPO ao reprocessar
    (preservar_edicoes); edicao que nao casa nunca some - vai para
    dados["edicoes_sem_fala"];
  - a revisao so troca o falante, o texto fica.

Nada daqui escreve no log: e conteudo da reuniao (CLAUDE.md, regra 3).
"""

import re
from datetime import datetime, timezone

from trama.erros import ErroDeUsuario

CHAVE = "edicao_manual"
CAMPOS_DE_POSICAO = ("palavras_divergentes", "palavras_baixa_confianca", "palavras_tempo")
TEXTO_MAX_LEN = 5000
_CARACTERE_DE_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")

# Mesmo criterio do casamento de clusters (pipeline.FRACAO_MIN_CASAMENTO): metade
# da fala antiga E metade da nova tem de ser o mesmo trecho de audio.
FRACAO_MIN_CASAMENTO = 0.5


class TextoInvalido(ErroDeUsuario):
    """Texto de fala recusado (codigo + parametros, trama/erros.py)."""


class FalaNaoEncontrada(LookupError):
    pass


class FalaMudou(RuntimeError):
    """A fala daquele indice nao e mais a que a tela mostrava."""


def validar_texto(bruto):
    texto = (bruto or "").strip()
    if not texto:
        raise TextoInvalido("fala_vazia")
    if _CARACTERE_DE_CONTROLE.search(texto):
        raise TextoInvalido("fala_com_controle")
    if len(texto) > TEXTO_MAX_LEN:
        raise TextoInvalido("fala_longa_demais", tamanho=len(texto), maximo=TEXTO_MAX_LEN)
    return texto


def esta_editada(fala):
    return CHAVE in fala


def _lacunas_da_fala(fala, lacunas):
    """Mesma regra de termos._lacunas_por_fala e da tela: a lacuna e da
    fala que a contem no tempo."""
    return [
        lac
        for lac in lacunas or ()
        if lac["inicio"] >= fala["inicio"] and lac["fim"] <= fala["fim"]
    ]


def _guardar_e_tirar_marcas(fala, lacunas):
    """Tira as marcas de posicao da fala (e as lacunas dela da lista da
    reuniao, no lugar) e devolve o que tirou."""
    marcas = {c: fala.pop(c) for c in CAMPOS_DE_POSICAO if c in fala}
    minhas = _lacunas_da_fala(fala, lacunas)
    if minhas and lacunas is not None:
        marcas["lacunas_sem_texto"] = minhas
        ids = {id(lac) for lac in minhas}
        lacunas[:] = [lac for lac in lacunas if id(lac) not in ids]
    return marcas


def _agora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fala(dados, indice, inicio):
    falas = dados.get("falas") or []
    if not 0 <= indice < len(falas):
        raise FalaNaoEncontrada(indice)
    fala = falas[indice]
    # A tela manda o inicio que mostrava: reprocessar entre abrir a pagina
    # e gravar muda o que esta naquele indice.
    if inicio is not None and abs(float(fala["inicio"]) - float(inicio)) > 1e-3:
        raise FalaMudou(indice)
    return fala


def editar(dados, indice, bruto, inicio=None):
    """
    Grava `bruto` como texto da fala `indice`, em memoria (quem chama grava
    o .json). Texto igual ao original desfaz a edicao. Devolve a fala.
    """
    texto = validar_texto(bruto)
    fala = _fala(dados, indice, inicio)
    if esta_editada(fala):
        if texto == fala[CHAVE]["texto_original"]:
            return desfazer(dados, indice, inicio)
        if texto == fala["texto"]:
            return fala
        fala["texto"] = texto
        fala[CHAVE]["editado_em"] = _agora()
        return fala
    if texto == fala["texto"]:
        return fala
    # A chave nunca e criada nem removida aqui: presente (mesmo vazia) e
    # reuniao processada com lacunas; ausente e reuniao de antes do campo.
    marcas = _guardar_e_tirar_marcas(fala, dados.get("lacunas_sem_texto"))
    fala[CHAVE] = {
        "texto_original": fala["texto"],
        "editado_em": _agora(),
        "marcas_originais": marcas,
    }
    fala["texto"] = texto
    return fala


def desfazer(dados, indice, inicio=None):
    """Volta a fala ao texto da maquina, com as marcas que ela tinha."""
    fala = _fala(dados, indice, inicio)
    edicao = fala.pop(CHAVE, None)
    if edicao is None:
        return fala
    fala["texto"] = edicao["texto_original"]
    marcas = dict(edicao.get("marcas_originais") or {})
    lacunas = marcas.pop("lacunas_sem_texto", None)
    fala.update(marcas)
    if lacunas:
        todas = dados.setdefault("lacunas_sem_texto", [])
        todas.extend(lacunas)
        todas.sort(key=lambda lac: (lac["inicio"], lac["fim"]))
    return fala


def para_a_tela(fala):
    """A fala como a rota devolve: sem marcas_originais (a tela nao usa)."""
    if not esta_editada(fala):
        return fala
    edicao = {k: v for k, v in fala[CHAVE].items() if k != "marcas_originais"}
    return {**fala, CHAVE: edicao}


# --------------------------------------------------------------------------
# reprocessamento
# --------------------------------------------------------------------------


def _sobreposicao(a, b):
    return max(0.0, min(a["fim"], b["fim"]) - max(a["inicio"], b["inicio"]))


def _casa(antiga, nova):
    comum = _sobreposicao(antiga, nova)
    dur_a = max(antiga["fim"] - antiga["inicio"], 1e-6)
    dur_n = max(nova["fim"] - nova["inicio"], 1e-6)
    return comum / dur_a >= FRACAO_MIN_CASAMENTO and comum / dur_n >= FRACAO_MIN_CASAMENTO


def edicoes_de(dados_anteriores):
    """Todas as edicoes manuais de uma execucao anterior: as que estavam
    em falas e as que ja tinham ficado sem fala numa execucao antes dela."""
    if not dados_anteriores:
        return []
    edicoes = [
        {
            "inicio": f["inicio"],
            "fim": f["fim"],
            "texto": f["texto"],
            "falante": f.get("falante"),
            "editado_em": f[CHAVE].get("editado_em"),
            "texto_original": f[CHAVE].get("texto_original"),
        }
        for f in dados_anteriores.get("falas") or []
        if esta_editada(f)
    ]
    return edicoes + list(dados_anteriores.get("edicoes_sem_fala") or [])


def preservar_edicoes(falas, lacunas, dados_anteriores):
    """
    Reaplica nas falas NOVAS as edicoes manuais da execucao anterior. Cada
    edicao vai para a fala nova com mais tempo em comum, se metade de cada
    uma for o mesmo trecho (FRACAO_MIN_CASAMENTO); uma fala nova recebe no
    maximo uma edicao. Na fala casada, o texto novo da maquina vira o
    texto_original (e o que "desfazer" mostra) e as marcas novas de posicao
    saem, como em editar().

    Muta `falas` e `lacunas` no lugar. Devolve as edicoes que nao casaram -
    nunca descartadas: o pipeline.py grava em "edicoes_sem_fala".
    """
    sem_fala, usadas = [], set()
    for edicao in edicoes_de(dados_anteriores):
        candidatas = [
            (i, _sobreposicao(edicao, f))
            for i, f in enumerate(falas)
            if i not in usadas and _casa(edicao, f)
        ]
        if not candidatas:
            sem_fala.append(edicao)
            continue
        i = max(candidatas, key=lambda c: c[1])[0]
        usadas.add(i)
        fala = falas[i]
        marcas = _guardar_e_tirar_marcas(fala, lacunas)
        fala[CHAVE] = {
            "texto_original": fala["texto"],
            "editado_em": edicao.get("editado_em") or _agora(),
            "marcas_originais": marcas,
        }
        fala["texto"] = edicao["texto"]
    return sem_fala
