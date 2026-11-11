"""
servidor/glossario.py - leitura e escrita do termos.txt pela tela de Perfil.

O arquivo tem mais do que regras: comentario de secao ("# --- ferramentas
de IA ---"), aviso ("CUIDADO: se voce falar de nuvem...") e linha em
branco. A tela edita as regras, mas nunca pode apagar isso por tabela -
por isso o arquivo e lido como uma lista ORDENADA de itens, cada um regra
ou texto, e escrito de volta na mesma ordem. Um GET seguido de um PUT sem
mudanca devolve o mesmo arquivo (as regras saem normalizadas como
"errado => certo", o formato que o arquivo ja usa).

Mesma regra de leitura de termos.carregar - o que la vira regra, aqui
vira item "regra"; o resto (comentario, branco, linha malformada) vira
"texto" e passa intacto. As duas nunca podem divergir: uma linha que o
pipeline.py aplicaria como regra tem que aparecer como regra na tela.

A escrita e atomica (nucleo.escrever_atomico): o pipeline.py pode estar lendo o
termos.txt no mesmo instante, e nunca pode pegar um arquivo pela metade.

Descricao de um termo ("Tabela à Vista" -> "painel de métricas do gestor")
mora no proprio termos.txt, numa secao no FIM, em linhas que comecam com
"#= " - para o pipeline.py (termos.carregar) sao comentario, o formato
"errado => certo" nao muda. A descricao e do termo CERTO, nao da regra:
varias regras levam ao mesmo termo (14 para "ChatGPT"). So essa secao e
reescrita pela tela; o resto do arquivo passa intacto, como sempre. Ela
vai para o .txt baixado (servidor/transcricao.py, "Vocabulário desta
empresa").
"""

import os
from pathlib import Path

from trama import nucleo

RAIZ = Path(__file__).resolve().parents[2]
CAMINHO = Path(os.environ.get("REC_MEET_TERMOS", str(RAIZ / "termos.txt")))

MAX_ITENS = 2000
MAX_LEN = 200
DESCRICAO_MAX_LEN = 120

PREFIXO_DESCRICAO = "#= "
SEPARADOR_DESCRICAO = " => "
# "#! forma": ja respondida na revisao de termos ("Ignorar", ou corrigida
# so numa fala) - nunca perguntada de novo (servidor/conferir.py).
PREFIXO_RESPONDIDO = "#! "
CABECALHO_RESPONDIDOS = (
    '# "#! forma": ja respondida na revisao de termos - nao perguntar de novo.',
)
CABECALHO_DESCRICOES = (
    "# --- descricoes dos termos (tela Glossario) ---",
    '# "#= termo => descricao": comeca com #, o pipeline.py le como comentario.',
    "# Vai para o vocabulario do .txt baixado. Editado pela tela - so esta",
    "# secao e reescrita.",
)


class GlossarioInvalido(ValueError):
    """Mensagem ja em portugues, pronta para o detail da resposta HTTP."""


def _como_regra(linha):
    """(errado, certo) se termos.carregar aplicaria esta linha como regra,
    senao None."""
    limpa = linha.strip()
    if not limpa or limpa.startswith("#") or "=>" not in limpa:
        return None
    errado, certo = (x.strip() for x in limpa.split("=>", 1))
    if not errado:
        return None
    return errado, certo


# Regra de concordancia e de contexto poe artigo/preposicao no lado certo
# ("do tabula da vista => da Tabela à Vista", "o Claudio => o Claude"). No
# vocabulario, o termo e "Tabela à Vista", uma vez so. Mesma lista em
# frontend/src/telas/perfil/Glossario.tsx (termoDoVocabulario).
_PALAVRAS_DE_LIGACAO = {
    "o",
    "a",
    "os",
    "as",
    "do",
    "da",
    "dos",
    "das",
    "no",
    "na",
    "nos",
    "nas",
    "de",
    "em",
    "um",
    "uma",
}


def termo_do_vocabulario(certo):
    """O termo de uma regra como entra no vocabulario e como a descricao e
    guardada: sem espaco nas pontas e sem a palavra de ligacao do comeco."""
    partes = (certo or "").split()
    if len(partes) > 1 and partes[0].lower() in _PALAVRAS_DE_LIGACAO:
        partes = partes[1:]
    return " ".join(partes)


def _chave_variacao(texto):
    """Mesma variacao para a tela e para a gravacao: sem acento, sem
    maiuscula e com o espacamento normalizado. E como a regra casa
    (termos.compilar ja tolera qualquer espaco e ignora acento e caixa):
    "chat APT" e "Chat  apt" trocam exatamente o mesmo texto. Mesma funcao
    em frontend/src/telas/perfil/TermosDaEmpresa.tsx (chaveDaVariacao)."""
    from trama import termos

    return " ".join(termos.sem_acento(texto).lower().split())


def _sem_variacao_repetida(linhas):
    """As linhas sem a segunda (e seguintes) regra de uma variacao que o
    mesmo termo ja tem. Fica a primeira: e a unica que dispara - quando a
    segunda roda, o trecho ja foi trocado pela primeira."""
    vistas, saida = set(), []
    for linha in linhas:
        regra = _como_regra(linha)
        if regra:
            chave = (termo_do_vocabulario(regra[1]).lower(), _chave_variacao(regra[0]))
            if chave in vistas:
                continue
            vistas.add(chave)
        saida.append(linha)
    return saida


def _termos(linhas):
    """Termos do vocabulario das regras de `linhas`, na ordem, sem repeticao
    (sem diferenciar maiuscula - fica a primeira grafia) e sem vazio."""
    vistos, termos = set(), []
    for regra in map(_como_regra, linhas):
        termo = termo_do_vocabulario(regra[1]) if regra else ""
        if termo and termo.lower() not in vistos:
            vistos.add(termo.lower())
            termos.append(termo)
    return termos


def _separar(linhas):
    """(linhas do arquivo sem a secao de descricoes, {termo: descricao})."""
    resto, descricoes, achou = [], {}, False
    for linha in linhas:
        if linha in CABECALHO_DESCRICOES or linha in CABECALHO_RESPONDIDOS:
            achou = True
            continue
        if linha.startswith(PREFIXO_RESPONDIDO):
            # lidas por ler_respondidos; reescritas no fim por escrever
            achou = True
            continue
        if linha.startswith(PREFIXO_DESCRICAO):
            achou = True
            corpo = linha[len(PREFIXO_DESCRICAO) :]
            # "#= termo => descricao", ou "#= termo": termo conhecido sem
            # descricao (Termos da empresa, "Está certo" da revisao).
            termo, _, descricao = corpo.partition(SEPARADOR_DESCRICAO)
            if termo.strip():
                descricoes[termo.strip()] = descricao.strip()
            continue
        resto.append(linha)
    # Linha em branco que separava a secao do resto nao e do resto - so
    # quando a secao existe; sem ela, o arquivo volta exatamente como era.
    while achou and resto and not resto[-1].strip():
        resto.pop()
    return resto, descricoes


def _linhas_do_arquivo():
    if not CAMINHO.exists():
        return []
    return CAMINHO.read_text(encoding="utf-8").splitlines()


def ler_respondidos():
    """Formas ja respondidas na revisao de termos, na ordem do arquivo."""
    return [
        linha[len(PREFIXO_RESPONDIDO) :].strip()
        for linha in _linhas_do_arquivo()
        if linha.startswith(PREFIXO_RESPONDIDO) and linha[len(PREFIXO_RESPONDIDO) :].strip()
    ]


def marcar_respondido(forma):
    """Guarda que a forma ja foi respondida - nunca mais perguntada."""
    forma = " ".join((forma or "").split())
    if not forma or len(forma) > MAX_LEN:
        raise GlossarioInvalido("Forma inválida.")
    respondidos = ler_respondidos()
    if not any(_mesmo(r, forma) for r in respondidos):
        respondidos.append(forma)
    escrever(ler(), ler_descricoes(), respondidos)
    return respondidos


def ler_descricoes():
    """{termo: descricao}, na ordem do arquivo - de termo de regra ou de
    termo so do vocabulario (sem regra: "MQX", que o Whisper ja escreve
    certo na maioria das vezes, nao precisa de substituicao para a IA
    saber o que e). Descricao "" = termo conhecido, sem descricao."""
    return _separar(_linhas_do_arquivo())[1]


def vocabulario():
    """[(termo, descricao ou None)]: os termos das regras
    (termo_do_vocabulario), na ordem do arquivo, e depois os que so tem
    descricao - sem repeticao, sem diferenciar maiuscula."""
    resto, descricoes = _separar(_linhas_do_arquivo())
    por_minuscula = {t.lower(): (d or None) for t, d in descricoes.items()}
    saida = [(t, por_minuscula.get(t.lower())) for t in _termos(resto)]
    vistos = {t.lower() for t, _ in saida}
    saida += [(t, d or None) for t, d in descricoes.items() if t.lower() not in vistos]
    return saida


def ler():
    itens = []
    for linha in _separar(_linhas_do_arquivo())[0]:
        regra = _como_regra(linha)
        if regra:
            itens.append({"tipo": "regra", "errado": regra[0], "certo": regra[1]})
        else:
            itens.append({"tipo": "texto", "texto": linha})
    return itens


def _validar_campo(valor, rotulo, posicao):
    if not isinstance(valor, str):
        raise GlossarioInvalido(f"Linha {posicao}: {rotulo} precisa ser texto.")
    if "\n" in valor or "\r" in valor:
        raise GlossarioInvalido(f"Linha {posicao}: {rotulo} não pode ter quebra de linha.")
    if len(valor) > MAX_LEN:
        raise GlossarioInvalido(f"Linha {posicao}: {rotulo} passa de {MAX_LEN} caracteres.")


def _linha_de(item, posicao):
    if not isinstance(item, dict):
        raise GlossarioInvalido(f"Linha {posicao}: formato inválido.")
    tipo = item.get("tipo")

    if tipo == "regra":
        errado, certo = item.get("errado"), item.get("certo")
        _validar_campo(errado, "o termo errado", posicao)
        _validar_campo(certo, "o termo certo", posicao)
        errado, certo = errado.strip(), certo.strip()
        if not errado:
            raise GlossarioInvalido(f"Linha {posicao}: o termo errado não pode ficar vazio.")
        if errado.startswith("#"):
            raise GlossarioInvalido(
                f"Linha {posicao}: o termo errado não pode começar com # "
                "(a linha viraria comentário)."
            )
        if "=>" in errado:
            raise GlossarioInvalido(f"Linha {posicao}: o termo errado não pode conter =>.")
        return f"{errado} => {certo}"

    if tipo == "texto":
        texto = item.get("texto")
        _validar_campo(texto, "o comentário", posicao)
        # Um "texto" que o pipeline.py leria como regra seria uma regra entrando
        # escondida, sem aparecer como regra na tela.
        if _como_regra(texto):
            raise GlossarioInvalido(f"Linha {posicao}: comentário com => seria lido como regra.")
        return texto

    raise GlossarioInvalido(f"Linha {posicao}: tipo desconhecido.")


def _validar_descricoes(descricoes):
    """Termo presente = termo da empresa; descricao "" = sem descricao.
    Termo sem regra e valido: entra so no vocabulario. Tirar um termo e
    tirar a chave (remover_termo)."""
    if not isinstance(descricoes, dict):
        raise GlossarioInvalido("Formato inválido das descrições.")
    limpas = {}
    for termo, descricao in descricoes.items():
        if not isinstance(descricao, str):
            raise GlossarioInvalido(f"A descrição de {termo} precisa ser texto.")
        # A chave e o termo como o vocabulario o ve ("o Claude" -> "Claude").
        termo, descricao = termo_do_vocabulario(termo), descricao.strip()
        if not termo:
            raise GlossarioInvalido("Uma descrição ficou sem o termo.")
        if any(c in termo for c in "\n\r\t") or len(termo) > MAX_LEN:
            raise GlossarioInvalido(
                f"O termo {termo[:40]} não pode ter quebra de linha nem passar "
                f"de {MAX_LEN} caracteres."
            )
        if termo.lower() in {t.lower() for t in limpas}:
            raise GlossarioInvalido(f"O termo {termo} aparece duas vezes.")
        if any(c in descricao for c in "\n\r\t"):
            raise GlossarioInvalido(f"A descrição de {termo} não pode ter quebra de linha.")
        if len(descricao) > DESCRICAO_MAX_LEN:
            raise GlossarioInvalido(
                f"A descrição de {termo} passa de {DESCRICAO_MAX_LEN} caracteres."
            )
        if SEPARADOR_DESCRICAO.strip() in termo:
            raise GlossarioInvalido(f"O termo {termo} tem => e não pode receber descrição.")
        limpas[termo] = descricao
    return limpas


def escrever(itens, descricoes=None, respondidos=None):
    """Valida TUDO antes de tocar o disco - um item invalido no meio nunca
    deixa o arquivo meio gravado. Devolve o que ficou gravado, relido.

    `descricoes`: {termo (termo_do_vocabulario): descricao}. None (corpo
    antigo, so com itens) mantem as que ja existem. A secao vai sempre no
    fim; termo de regra sem descricao nao precisa de linha, termo sem regra
    e sem descricao vira "#= termo". Sem nenhuma linha, a secao nao
    existe - o arquivo fica como era."""
    if not isinstance(itens, list):
        raise GlossarioInvalido("Formato inválido.")
    if len(itens) > MAX_ITENS:
        raise GlossarioInvalido(f"O glossário passa de {MAX_ITENS} linhas.")
    linhas = [_linha_de(item, i) for i, item in enumerate(itens, 1)]
    # O que vem da tela e o arquivo SEM a secao (ler() ja a tira); um item
    # "texto" que imitasse a secao viraria descricao escondida.
    linhas, _ = _separar(linhas)
    # A mesma variacao duas vezes no mesmo termo nunca e gravada - nem
    # vinda da tela, nem de um termos.txt editado a mao que ja a tenha.
    linhas = _sem_variacao_repetida(linhas)
    termos = _termos(linhas)
    if descricoes is None:
        descricoes = _separar(_linhas_do_arquivo())[1]
    if respondidos is None:
        respondidos = ler_respondidos()
    descricoes = _validar_descricoes(descricoes)
    # Termos de regra na ordem das regras; depois os so do vocabulario,
    # na ordem recebida.
    das_regras = {t.lower() for t in termos}
    ordem = [t for t in termos if t in descricoes]
    ordem += [t for t in descricoes if t not in ordem]
    secao = []
    for t in ordem:
        if descricoes[t]:
            secao.append(f"{PREFIXO_DESCRICAO}{t}{SEPARADOR_DESCRICAO}{descricoes[t]}")
        elif t.lower() not in das_regras:
            secao.append(f"{PREFIXO_DESCRICAO}{t}")
    if secao:
        linhas = linhas + [""] + list(CABECALHO_DESCRICOES) + secao
    if respondidos:
        linhas = (
            linhas
            + ([""] if not secao else [])
            + list(CABECALHO_RESPONDIDOS)
            + [f"{PREFIXO_RESPONDIDO}{r}" for r in respondidos]
        )
    nucleo.escrever_atomico(CAMINHO, "\n".join(linhas) + "\n")
    return ler()


# --------------------------------------------------------------------------
# reaplicar o glossario nas reunioes ja processadas
# --------------------------------------------------------------------------


class GlossarioMudou(RuntimeError):
    """O termos.txt ou algum .json mudou entre a previa e o "Aplicar" - o
    que a pessoa viu nao e mais o que seria gravado."""


class FalhaAoReaplicar(RuntimeError):
    def __init__(self, aplicadas):
        super().__init__("falha ao reaplicar")
        self.aplicadas = aplicadas


def _calcular(regras=None):
    """
    (assinatura, [(id, caminho_json, dados_corrigidos, contagem)]) - o
    glossario de agora (ou so `regras`, ja compiladas - a correcao feita
    pelo texto aplica so a dela) aplicado em memoria a cada reuniao processada, pela
    MESMA funcao do pipeline.py (termos.aplicar_em_falas, com o deslocamento de
    palavras_divergentes, palavras_baixa_confianca e lacunas_sem_texto).

    A assinatura cobre o termos.txt e o conteudo de cada .json: se qualquer
    um mudar entre a previa e a gravacao, a gravacao recusa.
    """
    import hashlib
    import json

    from trama import termos
    from trama.servidor import reunioes

    if regras is None:
        regras = termos.carregar(CAMINHO)
    assinatura = hashlib.sha256(CAMINHO.read_bytes() if CAMINHO.exists() else b"")
    resultado = []
    if reunioes.PASTA_AUDIOS.is_dir():
        for pasta in sorted(reunioes.PASTA_AUDIOS.iterdir()):
            if not pasta.is_dir() or not reunioes.PADRAO_ID.fullmatch(pasta.name):
                continue
            caminho_json = pasta / f"{pasta.name}.json"
            if not caminho_json.exists():
                continue
            bruto = caminho_json.read_bytes()
            assinatura.update(pasta.name.encode())
            assinatura.update(hashlib.sha256(bruto).digest())
            dados = json.loads(bruto)
            if not dados.get("falas"):
                continue
            contagem = termos.aplicar_em_falas(
                dados["falas"], regras, dados.get("lacunas_sem_texto")
            )
            resultado.append((pasta.name, caminho_json, dados, contagem))
    return assinatura.hexdigest(), resultado


def previa_reaplicacao():
    """Quantas substituicoes o glossario de agora faria, em quais reunioes -
    sem gravar nada."""
    assinatura, resultado = _calcular()
    reunioes_afetadas = [
        {"id": id, "substituicoes": sum(contagem.values()), "por_termo": contagem}
        for id, _, _, contagem in resultado
        if contagem
    ]
    return {
        "reunioes": reunioes_afetadas,
        "total": sum(r["substituicoes"] for r in reunioes_afetadas),
        "assinatura": assinatura,
    }


def reaplicar(assinatura_da_previa, regras=None):
    """
    Grava o que a previa mostrou - so se nada mudou desde ela. Cada reuniao
    em escrita atomica, .txt e .json preparados em temporario antes de
    confirmar os dois (mesma ordem de revisao.aplicar_e_gravar); reuniao sem
    nenhuma substituicao nao e tocada. Reaplicar de novo nao muda nada: as
    regras ja aplicadas nao casam mais (termos._aplicar_uma_regra_com_posicoes
    nao conta trecho que ja e o lado certo).
    """
    assinatura, resultado = _calcular(regras)
    if assinatura != assinatura_da_previa:
        raise GlossarioMudou()
    return gravar_reunioes(resultado)


def gravar_reunioes(resultado):
    """Grava o que _calcular devolveu: so as reunioes com substituicao,
    cada uma com .txt e .json preparados antes de confirmar os dois."""
    from trama import pipeline

    aplicadas = []
    try:
        for id, caminho_json, dados, contagem in resultado:
            if not contagem:
                continue
            texto_txt = pipeline.montar_texto_txt(
                dados["falas"], dados.get("clusters", {}), regioes=dados.get("regioes_sobrepostas")
            )
            texto_json = nucleo.json_para_disco(dados)
            txt = caminho_json.with_suffix(".txt")
            tmp_txt = nucleo.preparar_escrita_atomica(txt, texto_txt)
            try:
                tmp_json = nucleo.preparar_escrita_atomica(caminho_json, texto_json)
            except BaseException:
                tmp_txt.unlink(missing_ok=True)
                raise
            nucleo.confirmar_escrita_atomica(tmp_txt, txt)
            nucleo.confirmar_escrita_atomica(tmp_json, caminho_json)
            aplicadas.append(id)
    except Exception as exc:
        raise FalhaAoReaplicar(aplicadas) from exc
    return {"aplicadas": aplicadas, "total": sum(sum(c.values()) for _, _, _, c in resultado)}


def definir_descricao(termo, descricao):
    """Grava a descricao de um termo (vazia: termo conhecido sem
    descricao), sem mexer nas regras nem nas outras descricoes. Devolve as
    descricoes gravadas."""
    termo = termo_do_vocabulario(termo or "")
    if not termo:
        raise GlossarioInvalido("O termo não pode ficar vazio.")
    descricoes = ler_descricoes()
    descricoes[termo] = descricao or ""
    escrever(ler(), descricoes)
    return ler_descricoes()


# --------------------------------------------------------------------------
# Termos da empresa: a mesma informacao, vista por termo (ADR 0021)
# --------------------------------------------------------------------------


def _mesmo(a, b):
    """Mesmo texto para uma regra: sem acento e sem maiuscula."""
    from trama import termos

    return termos.sem_acento(a).lower() == termos.sem_acento(b).lower()


def termos_da_empresa():
    """
    [{termo, descricao, variacoes: [{errado, certo}]}]: as regras agrupadas
    pelo termo (termo_do_vocabulario do lado certo) - "aprovium", "a provium"
    sao variacoes de "Aprovion". Depois os termos so do vocabulario. Ordem
    do arquivo. O termos.txt nao muda de formato: e so como a tela ve.
    """
    resto, descricoes = _separar(_linhas_do_arquivo())
    por_minuscula = {t.lower(): t for t in descricoes}
    grupos, ordem = {}, []
    # Repetida no arquivo (editado a mao): a tela mostra uma vez so.
    for regra in map(_como_regra, _sem_variacao_repetida(resto)):
        if not regra:
            continue
        termo = termo_do_vocabulario(regra[1])
        chave = termo.lower()
        if chave not in grupos:
            nome = por_minuscula.get(chave, termo)
            grupos[chave] = {"termo": nome, "descricao": descricoes.get(nome, ""), "variacoes": []}
            ordem.append(chave)
        grupos[chave]["variacoes"].append({"errado": regra[0], "certo": regra[1]})
    for t, d in descricoes.items():
        if t.lower() not in grupos:
            grupos[t.lower()] = {"termo": t, "descricao": d, "variacoes": []}
            ordem.append(t.lower())
    return [grupos[c] for c in ordem]


def adicionar_termo(termo, descricao=""):
    """Termo so do vocabulario (o Whisper ainda nao errou, ou "Está
    certo" da revisao). Termo que ja existe: so atualiza a descricao."""
    termo = " ".join((termo or "").split())
    if not termo:
        raise GlossarioInvalido("Escreva o nome do termo.")
    descricoes = ler_descricoes()
    existente = next((t for t in descricoes if t.lower() == termo.lower()), None)
    das_regras = next(
        (t for t in _termos(_separar(_linhas_do_arquivo())[0]) if t.lower() == termo.lower()), None
    )
    nome = existente or das_regras or termo
    if descricao or nome not in descricoes:
        descricoes[nome] = (descricao or "").strip() or descricoes.get(nome, "")
    escrever(ler(), descricoes)
    return termos_da_empresa()


def remover_termo(termo):
    """Tira o termo da empresa: a descricao e todas as variacoes dele.
    O que ja foi corrigido nas reunioes continua como esta."""
    itens = [
        i
        for i in ler()
        if not (i["tipo"] == "regra" and termo_do_vocabulario(i["certo"]).lower() == termo.lower())
    ]
    descricoes = {t: d for t, d in ler_descricoes().items() if t.lower() != termo.lower()}
    escrever(itens, descricoes)
    return termos_da_empresa()


def remover_variacao(errado):
    """Tira uma variacao (a regra "errado => ..."). O que ja foi corrigido
    nas reunioes continua como esta."""
    itens = [i for i in ler() if not (i["tipo"] == "regra" and _mesmo(i["errado"], errado))]
    escrever(itens, ler_descricoes())
    return termos_da_empresa()
