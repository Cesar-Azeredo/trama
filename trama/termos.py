"""
termos.py - Correcao de vocabulario do dominio no transcript.

POR QUE NAO APENAS initial_prompt DO WHISPER

O `initial_prompt` parece a solucao obvia, mas so influencia a primeira janela
de 30s quando `condition_on_previous_text=False` - que e o que usamos, e deve
ser usado, porque com True o Whisper entra em loop de repeticao em audio longo.
Numa reuniao de 70 minutos o prompt ajuda os primeiros 0,7% do arquivo.

Entao usamos os dois: o prompt para orientar o inicio, e substituicao
deterministica para cobrir o arquivo todo.

RISCO: SOBRECORRECAO

Toda regra aqui pode estragar texto correto. "APT" isolado pode ser legitimo;
"cloud" pode ser nuvem de verdade. Por isso:

  - prefira padroes de duas ou mais palavras;
  - o pipeline.py imprime quantas vezes cada regra disparou, para voce auditar;
  - regra que dispara muito mais que o esperado provavelmente esta errada;
  - regra que nunca dispara e lixo, pode remover.

Formato do arquivo (termos.txt):

    # comentario
    errado => certo
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ARQUIVO_PADRAO = "termos.txt"


def carregar(caminho=ARQUIVO_PADRAO):
    """
    Le as regras. Retorna [(regex_compilada, substituto, padrao_original)].

    Ordem importa: as regras sao aplicadas na ordem do arquivo, entao coloque
    os padroes mais especificos primeiro (ex.: "chat de EPT" antes de "chat").
    """
    p = Path(caminho)
    if not p.exists():
        return []

    regras = []
    for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if "=>" not in linha:
            print(f"  ! {caminho}:{n} ignorada (falta '=>'): {linha}")
            continue

        errado, certo = (x.strip() for x in linha.split("=>", 1))
        if not errado:
            continue
        regras.append(compilar(errado, certo))
    return regras


def compilar(errado, certo):
    """
    Uma regra no formato que aplicar_em_falas usa: (regex, certo, errado).
    A mesma para o termos.txt e para a correcao feita pela tela
    (servidor/correcao.py) - os dois casam do mesmo jeito.

    Limite de palavra nas pontas evita casar dentro de outra palavra;
    qualquer espaco entre os termos tolera espacamento irregular do
    Whisper. O padrao e compilado SEM acento e casa contra o texto sem
    acento (sem_acento) - "o Claudio" pega "o Cláudio", "matriz util" pega
    "matriz útil".
    """
    corpo = r"\s+".join(re.escape(t) for t in sem_acento(errado).split())
    return (re.compile(rf"\b{corpo}\b", re.IGNORECASE), certo, errado)


@lru_cache(maxsize=512)
def _sem_acento_char(c):
    base = "".join(d for d in unicodedata.normalize("NFD", c) if not unicodedata.combining(d))
    return base if len(base) == 1 else c


def sem_acento(texto):
    """
    O texto sem acento, CARACTERE A CARACTERE: "Cláudio" -> "Claudio", com
    o mesmo comprimento. E o que deixa casar a regra sem acento e usar as
    posicoes do casamento direto no texto original - todo o deslocamento
    de posicoes (palavras_divergentes, lacunas, palavras_tempo) continua
    contando no texto de verdade.

    Caractere que nao vira exatamente UM (marca combinante solta, ja
    decomposta no texto) fica como esta: um "a" + acento separado nao e
    reconhecido, mas nenhuma posicao sai do lugar. O Whisper escreve o
    acento composto (NFC), que e o caso real. Maiuscula fica como esta -
    quem ignora caixa e o IGNORECASE da regra.
    """
    return "".join(_sem_acento_char(c) for c in texto)


def aplicar(texto, regras):
    """Retorna (texto_corrigido, {padrao: n_substituicoes}). Mesma
    substituicao de aplicar_em_falas (_aplicar_uma_regra_com_posicoes), so
    sem posicoes para deslocar."""
    contagem = {}
    for rx, certo, original in regras:
        texto, _, n = _aplicar_uma_regra_com_posicoes(texto, {}, rx, certo)
        if n:
            contagem[original] = contagem.get(original, 0) + n
    return texto, contagem


# Campos de cada fala com posicao em CARACTERES dentro de "texto"
# (pipeline.py:alinhar grava todos no mesmo sistema de coordenadas). Uma regra
# que muda o comprimento do texto ("chat apt" -> "ChatGPT" perde 4
# caracteres) desloca todos eles - antes desta mudanca so
# palavras_divergentes deslocava, e as posicoes de palavras_baixa_confianca
# e das lacunas ficavam apontando para o lugar errado depois de qualquer
# correcao que mudasse o comprimento.
CAMPOS_COM_POSICAO = ("palavras_divergentes", "palavras_baixa_confianca")


def _deslocar(itens, trechos, n_certo):
    """
    Posicoes de `itens` depois de reescrever cada (inicio, fim) de `trechos`
    (ordenados, sem sobreposicao - saida de finditer) por um texto de
    `n_certo` caracteres.

    Item com "comprimento" (uma palavra) dentro de um trecho reescrito sai
    da lista: nao ha mais "aquela palavra" para apontar. Item sem
    comprimento (lacuna: um PONTO entre palavras) nunca sai - se cair
    dentro do trecho, vai para o fim da substituicao, que e onde a pausa
    continua existindo no texto novo.
    """
    resultado = []
    for item in itens:
        p = item["posicao"]
        c = item.get("comprimento", 0)
        delta = 0
        nova = None
        descartar = False
        for ini, fim in trechos:
            antes = (p + c <= ini) if c > 0 else (p <= ini)
            if antes:
                break
            if p >= fim:
                delta += n_certo - (fim - ini)
                continue
            if c > 0:
                descartar = True
            else:
                nova = ini + delta + n_certo
            break
        if descartar:
            continue
        resultado.append({**item, "posicao": nova if nova is not None else p + delta})
    return resultado


def _deslocar_fundindo(itens, trechos, n_certo):
    """
    Como _deslocar, para os tempos de palavra (palavras_tempo): palavra
    dentro de um trecho reescrito nao some - as palavras de um mesmo trecho
    viram UMA, do tamanho da substituicao, do inicio da primeira ao fim da
    ultima ("chat" 1.0-1.2 + "apt" 1.2-1.5 -> "ChatGPT" 1.0-1.5). Sem isso,
    a palavra corrigida ficaria sem horario e nunca seria marcada numa
    sobreposicao.
    """
    saida, grupos = [], {}
    for item in itens:
        p, c = item["posicao"], item["comprimento"]
        delta, trecho = 0, None
        for k, (ini, fim) in enumerate(trechos):
            if p + c <= ini:
                break
            if p >= fim:
                delta += n_certo - (fim - ini)
                continue
            trecho = k
            break
        if trecho is None:
            saida.append({**item, "posicao": p + delta})
            continue
        grupo = grupos.get(trecho)
        if grupo is None:
            grupo = {**item, "posicao": trechos[trecho][0] + delta, "comprimento": n_certo}
            grupos[trecho] = grupo
            saida.append(grupo)
        else:
            grupo["inicio"] = min(grupo["inicio"], item["inicio"])
            grupo["fim"] = max(grupo["fim"], item["fim"])
    return saida


def _aplicar_uma_regra_com_posicoes(texto, marcas, rx, certo):
    """
    Aplica UMA regra ao texto e desloca junto cada lista de `marcas`
    ({nome: [itens com posicao]}). Substituicao LITERAL de `certo` - o
    mesmo texto que vai para o transcript e o comprimento usado no
    deslocamento, sempre o mesmo numero.
    """
    # Trecho que ja e o lado certo nao e substituicao: com IGNORECASE,
    # "epoca web => Epoca Web" casaria de novo com o proprio resultado e
    # seria contado para sempre - uma reaplicacao do glossario mostraria
    # "1 substituicao" que nao muda nada. "Ja e o certo" ignora acento
    # (nunca caixa): "Época Web" no texto fica como esta em vez de perder
    # o acento para a grafia da regra.
    # O casamento e contra sem_acento(texto), do mesmo comprimento: as
    # posicoes de m valem no texto original.
    certo_sem_acento = sem_acento(certo)
    trechos = [
        (m.start(), m.end())
        for m in rx.finditer(sem_acento(texto))
        if sem_acento(texto[m.start() : m.end()]) != certo_sem_acento
    ]
    if not trechos:
        return texto, marcas, 0
    partes, cursor = [], 0
    for ini, fim in trechos:
        partes.append(texto[cursor:ini])
        partes.append(certo)
        cursor = fim
    partes.append(texto[cursor:])
    novas = {
        nome: (_deslocar_fundindo if nome == "palavras_tempo" else _deslocar)(
            itens, trechos, len(certo)
        )
        for nome, itens in marcas.items()
    }
    return "".join(partes), novas, len(trechos)


def _lacunas_por_fala(falas, lacunas):
    """Cada lacuna na primeira fala que a contem no tempo - a MESMA regra
    da tela (frontend/src/telas/Detalhe.tsx:agruparLacunasPorFala), senao
    a posicao deslocada aqui seria lida contra outra fala la."""
    por_fala = {}
    for lacuna in lacunas or ():
        for i, f in enumerate(falas):
            if lacuna["inicio"] >= f["inicio"] and lacuna["fim"] <= f["fim"]:
                por_fala.setdefault(i, []).append(lacuna)
                break
    return por_fala


def aplicar_em_falas(falas, regras, lacunas=None):
    """
    Corrige a lista de falas no lugar. Retorna a contagem agregada.

    `lacunas`: a lista lacunas_sem_texto da reuniao (fora das falas, com
    posicao relativa a fala que as contem) - deslocada no lugar tambem.

    Toda fala passa cada regra por _aplicar_uma_regra_com_posicoes, que
    mantem texto e posicoes consistentes juntos (sem marca nenhuma, e so
    a substituicao). Idempotente sempre que as regras forem: aplicar de
    novo so muda algo se o lado certo de uma regra casar com o errado de
    outra.
    """
    lacunas_da_fala = _lacunas_por_fala(falas, lacunas)
    total = {}
    for i, f in enumerate(falas):
        # Texto corrigido a mao (edicao.py) e a palavra final de uma pessoa:
        # o glossario nunca reescreve por cima - nem no pipeline.py, nem ao
        # reaplicar pela tela.
        if "edicao_manual" in f:
            continue
        marcas = {campo: f[campo] for campo in CAMPOS_COM_POSICAO if f.get(campo)}
        # palavras_tempo e gravado compacto ([posicao, comprimento, inicio,
        # fim]) - vira dict so enquanto as regras rodam.
        if f.get("palavras_tempo"):
            marcas["palavras_tempo"] = [
                {"posicao": a, "comprimento": b, "inicio": c, "fim": d}
                for a, b, c, d in f["palavras_tempo"]
            ]
        minhas_lacunas = lacunas_da_fala.get(i, [])
        if minhas_lacunas:
            marcas["_lacunas"] = minhas_lacunas
        texto = f["texto"]
        c = {}
        for rx, certo, original in regras:
            texto, marcas, n = _aplicar_uma_regra_com_posicoes(texto, marcas, rx, certo)
            if n:
                c[original] = c.get(original, 0) + n
        f["texto"] = texto
        if "palavras_tempo" in marcas:
            f["palavras_tempo"] = [
                [m["posicao"], m["comprimento"], m["inicio"], m["fim"]]
                for m in marcas["palavras_tempo"]
            ]
        for campo in CAMPOS_COM_POSICAO:
            if campo in marcas:
                if marcas[campo]:
                    f[campo] = marcas[campo]
                else:
                    del f[campo]
        # Lacuna nunca sai (_deslocar) - mesma ordem, mesmo tamanho:
        # grava a posicao nova no dict ORIGINAL, que e o que esta na
        # lista lacunas_sem_texto da reuniao.
        for original_lacuna, nova in zip(minhas_lacunas, marcas.get("_lacunas", [])):
            original_lacuna["posicao"] = nova["posicao"]
        for k, v in c.items():
            total[k] = total.get(k, 0) + v
    return total


def prompt_whisper(regras, limite=180):
    """
    Monta o initial_prompt a partir do lado CERTO das regras.

    Curto de proposito: o Whisper so aproveita os ultimos ~224 tokens, e prompt
    longo aumenta o risco de alucinacao. Ajuda o inicio do arquivo; o resto
    fica por conta da substituicao.
    """
    vistos, termos = set(), []
    for _, certo, _ in regras:
        if certo and certo.lower() not in vistos:
            vistos.add(certo.lower())
            termos.append(certo)

    prompt = ""
    for t in termos:
        candidato = (prompt + ", " + t) if prompt else t
        if len(candidato) > limite:
            break
        prompt = candidato
    return prompt or None


def imprimir_contagem(contagem, regras):
    """Auditoria: o que disparou, e o que nunca disparou."""
    if not regras:
        return
    if contagem:
        print("\n  Correcoes de vocabulario aplicadas:")
        for padrao, n in sorted(contagem.items(), key=lambda kv: -kv[1]):
            alerta = "  <- muito alto, confira a regra" if n > 60 else ""
            print(f"    {n:>4}x  {padrao}{alerta}")

    nunca = [orig for _, _, orig in regras if orig not in contagem]
    if nunca:
        print(
            f"  {len(nunca)} regra(s) sem uso nesta reuniao: "
            + ", ".join(nunca[:6])
            + ("..." if len(nunca) > 6 else "")
        )
