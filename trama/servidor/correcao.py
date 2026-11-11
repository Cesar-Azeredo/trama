"""
servidor/correcao.py - corrigir um termo selecionado no texto, "em todas as
reunioes e nas proximas" (ADR 0019).

Por baixo e uma regra do termos.txt ("trecho => certo"), aplicada as
reunioes ja processadas pela MESMA rotina do botao de reaplicar
(glossario._calcular/gravar_reunioes) - mas so ela: regras salvas e ainda
nao aplicadas continuam esperando o botao, nunca entram de carona numa
correcao que a pessoa fez de outra coisa.

Quem usa nunca ve "regra" nem "ordem". As regras rodam na ordem do
arquivo, e uma regra mais geral que venha antes captura o trecho primeiro
("tabula da vista" antes de "do tabula da vista" faria a especifica nunca
disparar). A posicao da regra nova e escolhida aqui: antes da primeira
regra que capturaria o trecho dela, e depois de toda regra mais especifica
que ela capturaria. So quando as duas exigencias se contradizem ha aviso.

Nada daqui vai para o log: trecho e texto das reunioes (CLAUDE.md, regra 3).
"""

import json
import re

from trama import erros, termos
from trama.erros import ErroDeUsuario
from trama.servidor import glossario, reunioes

TRECHO_MAX_LEN = glossario.MAX_LEN
CONTEXTO = 60


class CorrecaoInvalida(ErroDeUsuario):
    """Correcao recusada antes de tocar disco (codigo + parametros, trama/erros.py)."""


def validar(trecho, certo):
    trecho = " ".join((trecho or "").split())
    certo = " ".join((certo or "").split())
    if not trecho:
        raise CorrecaoInvalida("selecione_trecho")
    if not certo:
        raise CorrecaoInvalida("escreva_certo")
    for valor, campo in ((trecho, "trecho"), (certo, "certo")):
        if len(valor) > TRECHO_MAX_LEN:
            raise CorrecaoInvalida("correcao_longa_demais", campo=campo, maximo=TRECHO_MAX_LEN)
    if "=>" in trecho or "=>" in certo:
        raise CorrecaoInvalida("correcao_com_seta")
    if trecho.startswith("#"):
        raise CorrecaoInvalida("trecho_com_cerquilha")
    if trecho == certo:
        raise CorrecaoInvalida("trecho_ja_certo")
    if not any(c.isalnum() for c in trecho):
        raise CorrecaoInvalida("selecione_palavra")
    return trecho, certo


def _chave(texto):
    return termos.sem_acento(texto).lower()


def _capturaria(regra, texto):
    """A regra trocaria alguma coisa em `texto`? Mesma condicao de
    termos._aplicar_uma_regra_com_posicoes: trecho que ja e o certo (sem
    olhar acento) nao conta."""
    rx, certo, _ = regra
    alvo = termos.sem_acento(texto)
    return any(
        termos.sem_acento(texto[m.start() : m.end()]) != termos.sem_acento(certo)
        for m in rx.finditer(alvo)
    )


def posicionar(itens, trecho, certo):
    """
    Insere (ou atualiza) a regra "trecho => certo" em `itens` (lista de
    glossario.ler), no lugar certo. Devolve (itens_novos, aviso ou None).

    Mesmo trecho ja com regra ativa: troca o certo no lugar - a pessoa
    disse o que e certo agora.
    """
    itens = [dict(i) for i in itens]
    for i in itens:
        if i["tipo"] == "regra" and glossario._chave_variacao(
            i["errado"]
        ) == glossario._chave_variacao(trecho):
            i["certo"] = certo
            return itens, None

    nova = termos.compilar(trecho, certo)
    regras = [
        (k, i, termos.compilar(i["errado"], i["certo"]))
        for k, i in enumerate(itens)
        if i["tipo"] == "regra"
    ]
    # mais geral: capturaria o trecho da nova antes dela -> nova vem antes
    gerais = [k for k, _, r in regras if _capturaria(r, trecho)]
    # mais especifica: a nova capturaria o trecho dela -> nova vem depois
    especificas = [k for k, i, _ in regras if _capturaria(nova, i["errado"])]
    item = {"tipo": "regra", "errado": trecho, "certo": certo}

    if gerais:
        antes_de = gerais[0]
        if all(k < antes_de for k in especificas):
            return itens[:antes_de] + [item] + itens[antes_de:], None
        # Nao ha lugar que respeite as duas: fica depois das especificas
        # (nada que ja funcionava para de funcionar), e avisa.
        depois_de = max(especificas)
        conflito = itens[antes_de]
        aviso = erros.aviso(
            "correcao_existente_prevalece", errado=conflito["errado"], certo=conflito["certo"]
        )
        return itens[: depois_de + 1] + [item] + itens[depois_de + 1 :], aviso

    depois_de = max([k for k, _, _ in regras] + especificas, default=len(itens) - 1)
    return itens[: depois_de + 1] + [item] + itens[depois_de + 1 :], None


def _ocorrencias(regra):
    """Onde a regra trocaria algo, reuniao por reuniao - a mesma contagem
    de aplicar_em_falas (fala corrigida a mao fica de fora)."""
    rx, certo, _ = regra
    certo_sem = termos.sem_acento(certo)
    saida = []
    if not reunioes.PASTA_AUDIOS.is_dir():
        return saida
    for pasta in sorted(reunioes.PASTA_AUDIOS.iterdir()):
        if not pasta.is_dir() or not reunioes.PADRAO_ID.fullmatch(pasta.name):
            continue
        caminho = pasta / f"{pasta.name}.json"
        if not caminho.exists():
            continue
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        achadas = []
        for indice, fala in enumerate(dados.get("falas") or []):
            if "edicao_manual" in fala:
                continue
            texto = fala["texto"]
            for m in rx.finditer(termos.sem_acento(texto)):
                if termos.sem_acento(texto[m.start() : m.end()]) == certo_sem:
                    continue
                inicio = next(
                    (w[2] for w in fala.get("palavras_tempo") or [] if w[0] == m.start()),
                    fala["inicio"],
                )
                achadas.append(
                    {
                        "indice": indice,
                        "inicio": inicio,
                        "antes": texto[max(0, m.start() - CONTEXTO) : m.start()],
                        "trecho": texto[m.start() : m.end()],
                        "depois": texto[m.end() : m.end() + CONTEXTO],
                    }
                )
        if achadas:
            saida.append(
                {
                    "id": pasta.name,
                    # so o titulo DADO; sem titulo, None - a tela monta o
                    # padrao ("Reuniao NN") no idioma dela, pelo id.
                    "titulo": dados.get("titulo") or None,
                    "ocorrencias": achadas,
                }
            )
    return saida


def previa(trecho, certo):
    """Quantas vezes e onde a correcao trocaria o texto, sem gravar nada."""
    trecho, certo = validar(trecho, certo)
    regra = termos.compilar(trecho, certo)
    assinatura, _ = glossario._calcular([regra])
    _, aviso = posicionar(glossario.ler(), trecho, certo)
    lista = _ocorrencias(regra)
    return {
        "trecho": trecho,
        "certo": certo,
        "total": sum(len(r["ocorrencias"]) for r in lista),
        "reunioes": lista,
        "aviso": aviso,
        "assinatura": assinatura,
    }


def aplicar(trecho, certo, descricao, assinatura):
    """
    Grava a regra no termos.txt (na posicao certa, com a descricao do
    termo, se veio) e aplica SO ela nas reunioes ja processadas - so se
    nada mudou desde a previa (glossario.GlossarioMudou).
    """
    trecho, certo = validar(trecho, certo)
    regra = termos.compilar(trecho, certo)
    atual, resultado = glossario._calcular([regra])
    if atual != assinatura:
        raise glossario.GlossarioMudou()

    itens, aviso = posicionar(glossario.ler(), trecho, certo)
    descricoes = glossario.ler_descricoes()
    descricao = (descricao or "").strip()
    if descricao:
        descricoes[glossario.termo_do_vocabulario(certo)] = descricao
    glossario.escrever(itens, descricoes)

    gravado = glossario.gravar_reunioes(resultado)
    return {**gravado, "aviso": aviso}


# --------------------------------------------------------------------------
# variacoes parecidas (depois de uma correcao "em todas")
# --------------------------------------------------------------------------
#
# Criterio (ADR 0020), sem dicionario e sem rede:
#   - candidato: 1 a n+1 palavras seguidas de uma fala (n = palavras do
#     trecho corrigido), comparado "colado" (sem acento, sem maiuscula, sem
#     espaco nem pontuacao) com o trecho E com o certo;
#   - parecido: distancia de edicao (Damerau-Levenshtein) de no maximo 1
#     letra ate 5 letras, 2 de 6 a 9, 3 acima; OU a mesma chave de som do
#     portugues (v/b, c/k/q, s/z/ç, h mudo, letra dobrada);
#   - palavra comum fica de fora: candidato em que TODAS as palavras
#     aparecem em PALAVRA_COMUM_REUNIOES reunioes ou mais ("vale",
#     "vários") - ou, com 5 letras ou mais, comecam como uma palavra comum
#     (PREFIXO_FAMILIA letras: "aprovou", "aprovem" sao da familia de
#     "aprovação") - a nao ser que o Whisper tenha duvidado dela ali
#     (palavras_baixa_confianca);
#   - mais de uma palavra so quando a junção e o que torna parecido ("a
#     Provium" -> "aprovium"): no maximo 1 letra de distancia, mais parecida
#     que cada palavra dela, e sem conter o proprio termo ("o MKX");
#   - fora tambem: o que ja e o certo, o que ja tem correcao, nome da
#     galeria, termo conhecido, fala corrigida a mao;
#   - ordem: o que o Whisper marcou como duvida primeiro, depois o mais
#     parecido, depois o mais frequente.

PALAVRA_COMUM_REUNIOES = 5
PREFIXO_FAMILIA = 5
MAX_VARIACOES = 15
MAX_CONTEXTOS = 3
_PALAVRA = re.compile(r"\w+(?:[.'\-]\w+)*")


def _colado(texto):
    return "".join(c for c in termos.sem_acento(texto).lower() if c.isalnum())


def chave_de_som(texto):
    """Chave fonetica simples do portugues: o que soa igual fica igual."""
    s = _colado(texto)
    for de, para in (
        ("ph", "f"),
        ("ch", "x"),
        ("sh", "x"),
        ("lh", "l"),
        ("nh", "n"),
        ("qu", "k"),
        ("q", "k"),
        ("w", "v"),
        ("y", "i"),
    ):
        s = s.replace(de, para)
    s = re.sub(r"c(?=[ei])", "s", s)
    s = s.replace("c", "k").replace("z", "s").replace("b", "v").replace("h", "")
    s = re.sub(r"(.)\1+", r"\1", s)
    s = re.sub(r"m$", "n", s)
    s = re.sub(r"e$", "i", s)
    s = re.sub(r"o$", "u", s)
    return s


def distancia(a, b):
    """Damerau-Levenshtein (transposicao de vizinhas conta 1)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            custo = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + custo)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def _limite(alvo):
    return 1 if len(alvo) <= 5 else 2 if len(alvo) <= 9 else 3


def _preparar_alvos(alvos):
    return [(a, _limite(a), chave_de_som(a)) for a in map(_colado, alvos)]


def _parecido(candidato, alvos):
    """Menor distancia aos alvos (de _preparar_alvos), se parecido; None
    se nao. A distancia nunca e menor que a diferenca de tamanho - corta
    antes de calcular (sao dezenas de milhares de candidatos)."""
    c = _colado(candidato)
    if len(c) < 2:
        return None
    melhor = None
    for a, limite, som in alvos:
        if abs(len(c) - len(a)) > limite + 3:
            continue
        d = distancia(c, a) if abs(len(c) - len(a)) <= limite else limite + 1
        if d <= limite or chave_de_som(c) == som:
            d = d if d <= limite else distancia(c, a)
            melhor = d if melhor is None else min(melhor, d)
    return melhor


def _reunioes_processadas():
    if not reunioes.PASTA_AUDIOS.is_dir():
        return
    for pasta in sorted(reunioes.PASTA_AUDIOS.iterdir()):
        if not pasta.is_dir() or not reunioes.PADRAO_ID.fullmatch(pasta.name):
            continue
        caminho = pasta / f"{pasta.name}.json"
        if caminho.exists():
            yield pasta.name, json.loads(caminho.read_text(encoding="utf-8"))


def _excluidos():
    """Chaves (coladas) que nunca sao sugeridas: nomes da galeria, termos
    conhecidos e o que ja tem correcao."""
    from trama import nucleo

    fora = set()
    try:
        fora |= {_colado(n) for n, _, _ in nucleo.listar_pessoas()}
    except Exception:
        pass
    fora |= {_colado(t) for t, _ in glossario.vocabulario()}
    fora |= {_colado(i["errado"]) for i in glossario.ler() if i["tipo"] == "regra"}
    return fora


class _Busca:
    """O que vale para a busca inteira de uma sugestao: os alvos, o que ja
    casa ou ja e o certo, o que nunca e sugerido, os tamanhos de janela e
    quais palavras sao comuns no conjunto de reunioes."""

    def __init__(self, trecho, certo, reunioes_processadas):
        self.alvos = _preparar_alvos([trecho, certo])
        # O que a propria correcao (ou o certo) ja casa nao e variacao: e o
        # termo, talvez embrulhado ("o termo. O", "o termo"). Colado nao
        # serve aqui: duas palavras coladas podem virar o termo, mas a
        # correcao casa palavra inteira e nao pega - essa e justamente a
        # variacao.
        self.ja_casa = [termos.compilar(trecho, certo)[0], termos.compilar(certo, certo)[0]]
        self.ja_certo = {_colado(certo), _colado(trecho)}
        self.fora = _excluidos()
        n = len(_PALAVRA.findall(trecho)) or 1
        self.tamanhos = range(max(1, n - 1), n + 2)
        self.em_quantas, self.familia = _frequencia_das_palavras(reunioes_processadas)

    def comum(self, w):
        """Palavra que aparece em muitas reunioes, ou da familia (mesmo
        prefixo) de uma que aparece."""
        return self.em_quantas.get(w, 0) >= PALAVRA_COMUM_REUNIOES or (
            len(w) >= PREFIXO_FAMILIA and self.familia.get(w[:PREFIXO_FAMILIA], False)
        )

    def parecida_sozinha(self, w):
        d = _parecido(w, self.alvos)
        return 99 if d is None else d

    def descartar_forma(self, forma, chave):
        return chave in self.fora or any(rx.search(termos.sem_acento(forma)) for rx in self.ja_casa)

    def descartar_trecho_composto(self, d, palavras_do_trecho):
        """Trecho de mais de uma palavra so entra se for mais parecido que
        cada palavra dele sozinha, e sem conter o proprio termo."""
        return (
            d > 1
            or any(w in self.ja_certo or w in self.fora for w in palavras_do_trecho)
            or d >= min(self.parecida_sozinha(w) for w in palavras_do_trecho)
        )


def _frequencia_das_palavras(reunioes_processadas):
    """(em quantas reunioes cada palavra colada aparece, prefixos das
    palavras comuns)."""
    em_quantas, familia = {}, {}
    for _, dados in reunioes_processadas:
        vistas = {
            _colado(w) for f in dados.get("falas") or [] for w in _PALAVRA.findall(f["texto"])
        }
        for w in vistas:
            em_quantas[w] = em_quantas.get(w, 0) + 1
    for w, n_reun in em_quantas.items():
        if n_reun >= PALAVRA_COMUM_REUNIOES and len(w) >= PREFIXO_FAMILIA:
            familia[w[:PREFIXO_FAMILIA]] = True
    return em_quantas, familia


def _achados_na_fala(texto, fala, busca):
    """Cada janela de palavras da fala que parece o termo:
    (distancia, -tamanho, inicio, fim, forma, chave, duvida, eh_comum)."""
    palavras = [(m.start(), m.end()) for m in _PALAVRA.finditer(texto)]
    duvidas = [
        (b["posicao"], b["posicao"] + b["comprimento"])
        for b in fala.get("palavras_baixa_confianca") or []
    ]
    achados = []
    for k in busca.tamanhos:
        for i in range(len(palavras) - k + 1):
            a, b = palavras[i][0], palavras[i + k - 1][1]
            forma = texto[a:b]
            chave = _colado(forma)
            if busca.descartar_forma(forma, chave):
                continue
            d = _parecido(forma, busca.alvos)
            if d is None:
                continue
            palavras_do_trecho = [_colado(texto[x:y]) for x, y in palavras[i : i + k]]
            if k > 1 and busca.descartar_trecho_composto(d, palavras_do_trecho):
                continue
            duvida = any(x < b and y > a for x, y in duvidas)
            eh_comum = all(busca.comum(w) for w in palavras_do_trecho)
            achados.append((d, -(b - a), a, b, forma, chave, duvida, eh_comum))
    return achados


def _sem_sobreposicao(achados):
    """Um trecho de texto vira no maximo uma variacao: a mais parecida."""
    usados = []
    for achado in sorted(achados):
        a, b = achado[2], achado[3]
        if any(a < y and b > x for x, y in usados):
            continue
        usados.append((a, b))
        yield achado


def _registrar(grupos, achado, ocorrencia):
    d, _, _, _, forma, chave, duvida, eh_comum = achado
    g = grupos.setdefault(
        chave,
        {
            "formas": {},
            "distancia": d,
            "baixa_confianca": False,
            "elegivel": False,
            "ocorrencias": [],
        },
    )
    # Palavra comum so entra se o Whisper duvidou dela em algum lugar - e
    # ai entra com TODAS as ocorrencias: a correcao troca a forma em todo
    # lugar, a contagem tem de dizer isso.
    g["elegivel"] |= duvida or not eh_comum
    g["formas"][forma] = g["formas"].get(forma, 0) + 1
    g["distancia"] = min(g["distancia"], d)
    g["baixa_confianca"] |= duvida
    g["ocorrencias"].append(ocorrencia)


def _ocorrencia(id, titulo, indice, fala, texto, achado):
    _, _, a, b, forma, _, duvida, _ = achado
    inicio = next((w[2] for w in fala.get("palavras_tempo") or [] if w[0] == a), fala["inicio"])
    return {
        "id": id,
        "titulo": titulo,
        "indice": indice,
        "inicio": inicio,
        "antes": texto[max(0, a - CONTEXTO) : a],
        "trecho": forma,
        "depois": texto[b : b + CONTEXTO],
        "baixa_confianca": duvida,
    }


def _variacoes(grupos):
    variacoes = []
    for g in grupos.values():
        if not g["elegivel"]:
            continue
        forma = max(g["formas"], key=g["formas"].get)
        ocorr = sorted(g["ocorrencias"], key=lambda o: not o["baixa_confianca"])
        variacoes.append(
            {
                "forma": forma,
                "total": len(ocorr),
                "baixa_confianca": g["baixa_confianca"],
                "distancia": g["distancia"],
                "ocorrencias": ocorr[:MAX_CONTEXTOS],
            }
        )
    variacoes.sort(key=lambda v: (not v["baixa_confianca"], v["distancia"], -v["total"]))
    return variacoes[:MAX_VARIACOES]


def sugerir(trecho, certo):
    """Formas parecidas com o termo nas reunioes processadas (ADR 0020):
    {certo, variacoes, assinatura}. So leitura - nada e gravado aqui."""
    trecho, certo = validar(trecho, certo)
    todas = list(_reunioes_processadas())
    busca = _Busca(trecho, certo, todas)
    grupos = {}
    for id, dados in todas:
        titulo = dados.get("titulo") or None  # padrao montado na tela, pelo id
        for indice, fala in enumerate(dados.get("falas") or []):
            if "edicao_manual" in fala:
                continue
            texto = fala["texto"]
            for achado in _sem_sobreposicao(_achados_na_fala(texto, fala, busca)):
                _registrar(grupos, achado, _ocorrencia(id, titulo, indice, fala, texto, achado))
    assinatura, _ = glossario._calcular([])
    return {"certo": certo, "variacoes": _variacoes(grupos), "assinatura": assinatura}


def aplicar_variacoes(certo, formas, assinatura):
    """Cada forma marcada vira uma correcao "em todas", na posicao certa;
    todas aplicadas de uma vez, so se nada mudou desde a sugestao."""
    if not isinstance(formas, list) or not formas:
        raise CorrecaoInvalida("marque_pelo_menos_uma")
    pares = [validar(f, certo) for f in formas]
    regras = [termos.compilar(t, c) for t, c in pares]
    atual, resultado = glossario._calcular(regras)
    if atual != assinatura:
        raise glossario.GlossarioMudou()
    itens, avisos = glossario.ler(), []
    for t, c in pares:
        itens, aviso = posicionar(itens, t, c)
        if aviso:
            avisos.append(aviso)
    glossario.escrever(itens, glossario.ler_descricoes())
    gravado = glossario.gravar_reunioes(resultado)
    return {**gravado, "aviso": avisos[0] if len(avisos) == 1 else (avisos or None)}
