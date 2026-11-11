"""
tests/test_termos.py - Testes da correcao de vocabulario.

O risco desse modulo e sobrecorrigir: estragar texto que estava certo. A
maioria dos testes abaixo existe para provar que isso NAO acontece.

Uso:
    python tests/test_termos.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _ambiente  # noqa: E402

_ambiente.isolar()

from trama import termos as T  # noqa: E402


def regras_de(texto):
    f = Path(tempfile.mkdtemp()) / "t.txt"
    f.write_text(texto, encoding="utf-8")
    return T.carregar(f)


# ==========================================================================
# carregamento
# ==========================================================================


def test_ignora_comentario_e_linha_vazia():
    r = regras_de("# comentario\n\nchat APT => ChatGPT\n")
    assert len(r) == 1


def test_arquivo_inexistente_nao_quebra():
    assert T.carregar(Path(tempfile.mkdtemp()) / "nao_existe.txt") == []


def test_preserva_ordem_do_arquivo():
    """Padrao especifico tem de vir antes do generico, ou o generico vence."""
    r = regras_de("chat de EPT => ChatGPT\nchat => ChatGPT\n")
    assert r[0][2] == "chat de EPT"


# ==========================================================================
# substituicao
# ==========================================================================


def test_corrige_termo_simples():
    r = regras_de("chat APT => ChatGPT\n")
    t, c = T.aplicar("o chat APT faz melhor que o nosso", r)
    assert t == "o ChatGPT faz melhor que o nosso"
    assert c == {"chat APT": 1}


def test_ignora_caixa():
    r = regras_de("chat apt => ChatGPT\n")
    t, _ = T.aplicar("O Chat APT e o CHAT APT", r)
    assert t == "O ChatGPT e o ChatGPT"


def test_tolera_espacamento_irregular():
    """O Whisper produz espacamento inconsistente entre palavras."""
    r = regras_de("matriz de goutes => matriz GUT\n")
    t, _ = T.aplicar("a matriz  de   goutes esta aqui", r)
    assert t == "a matriz GUT esta aqui"


def test_conta_multiplas_ocorrencias():
    r = regras_de("em housing => in house\n")
    _, c = T.aplicar("em housing, depois em housing e em housing", r)
    assert c == {"em housing": 3}


# ==========================================================================
# NAO sobrecorrigir - o risco real do modulo
# ==========================================================================


def test_nao_corrige_dentro_de_outra_palavra():
    """
    Sem \\b nas pontas, 'chat' casaria dentro de 'chateado' e o transcript
    viraria 'ChatGPTeado'. Este e o modo de falha mais grave do modulo.
    """
    r = regras_de("chat => ChatGPT\n")
    t, c = T.aplicar("ele ficou chateado com o chat", r)
    assert "ChatGPTeado" not in t, t
    assert t == "ele ficou chateado com o ChatGPT"
    assert c == {"chat": 1}


def test_nao_toca_texto_sem_o_termo():
    r = regras_de("chat APT => ChatGPT\n")
    original = "precisamos rotacionar as chaves da API em 90 dias"
    t, c = T.aplicar(original, r)
    assert t == original and c == {}


def test_sem_regras_nao_altera_nada():
    original = "texto qualquer"
    t, c = T.aplicar(original, [])
    assert t == original and c == {}


def test_caracteres_especiais_no_padrao_sao_literais():
    """Padrao com ponto ou parentese nao pode virar metacaractere de regex."""
    r = regras_de("e-mail. => e-mail\n")
    t, _ = T.aplicar("manda por e-mailX", r)
    assert t == "manda por e-mailX", t


# ==========================================================================
# aplicacao nas falas
# ==========================================================================


def test_aplica_em_falas_e_agrega_contagem():
    r = regras_de("chat APT => ChatGPT\nem housing => in house\n")
    falas = [
        {"texto": "o chat APT resolve", "falante": "Celso"},
        {"texto": "fazer em housing ou comprar", "falante": "Ramiro"},
        {"texto": "o chat APT de novo", "falante": "Amanda"},
    ]
    c = T.aplicar_em_falas(falas, r)
    assert falas[0]["texto"] == "o ChatGPT resolve"
    assert falas[1]["texto"] == "fazer in house ou comprar"
    assert c == {"chat APT": 2, "em housing": 1}


def test_aplicar_em_falas_preserva_outros_campos():
    r = regras_de("chat APT => ChatGPT\n")
    falas = [{"texto": "chat APT", "falante": "Celso", "inicio": 12.5, "cluster": "SPEAKER_00"}]
    T.aplicar_em_falas(falas, r)
    assert falas[0]["falante"] == "Celso"
    assert falas[0]["inicio"] == 12.5
    assert falas[0]["cluster"] == "SPEAKER_00"


def test_divergencia_desloca_com_correcao_que_muda_o_comprimento():
    """
    "chat apt" (8 caracteres) -> "ChatGPT" (7) encurta o texto em 1. Uma
    palavra divergente gravada DEPOIS do trecho corrigido (pipeline.py:alinhar,
    antes de termos.aplicar_em_falas rodar) tem que deslocar junto a
    posicao, ou aponta pro lugar errado no texto ja corrigido.
    """
    r = regras_de("chat apt => ChatGPT\n")
    texto = "o chat apt ajuda muito e a Amanda concorda"
    pos_original = texto.index("Amanda")
    falas = [
        {
            "texto": texto,
            "falante": "Celso",
            "palavras_divergentes": [
                {"posicao": pos_original, "comprimento": len("Amanda"), "falante": "Ramiro"},
            ],
        }
    ]
    T.aplicar_em_falas(falas, r)

    novo_texto = falas[0]["texto"]
    assert "ChatGPT" in novo_texto
    d = falas[0]["palavras_divergentes"][0]
    assert novo_texto[d["posicao"] : d["posicao"] + d["comprimento"]] == "Amanda"


def test_divergencia_dentro_do_trecho_reescrito_e_descartada():
    """
    Se a propria palavra divergente esta dentro do trecho que a correcao
    reescreve ("apt" de "chat apt" -> "ChatGPT"), nao ha mais "aquela
    palavra" pra apontar depois - a entrada tem que sair da lista, nao
    ficar com uma posicao que nao aponta pra nada.
    """
    r = regras_de("chat apt => ChatGPT\n")
    texto = "o chat apt ajuda muito"
    pos_apt = texto.index("apt")
    falas = [
        {
            "texto": texto,
            "falante": "Celso",
            "palavras_divergentes": [
                {"posicao": pos_apt, "comprimento": len("apt"), "falante": "Ramiro"},
            ],
        }
    ]
    T.aplicar_em_falas(falas, r)
    assert "palavras_divergentes" not in falas[0]


def test_baixa_confianca_desloca_com_correcao_que_muda_o_comprimento():
    """REGRESSAO: so palavras_divergentes deslocava; palavras_baixa_confianca
    ficava apontando pro lugar errado depois de qualquer correcao que mudasse
    o comprimento do texto - inclusive no proprio pipeline.py."""
    r = regras_de("chat apt => ChatGPT\n")
    texto = "o chat apt ajuda muito e a Amanda concorda"
    pos = texto.index("Amanda")
    falas = [
        {
            "texto": texto,
            "inicio": 0.0,
            "fim": 5.0,
            "palavras_baixa_confianca": [{"posicao": pos, "comprimento": 6, "probabilidade": 0.3}],
        }
    ]
    T.aplicar_em_falas(falas, r)
    b = falas[0]["palavras_baixa_confianca"][0]
    assert falas[0]["texto"][b["posicao"] : b["posicao"] + 6] == "Amanda"


def test_lacuna_desloca_e_fica_na_fala_certa():
    r = regras_de("chat apt => ChatGPT\n")
    t1 = "sem nada pra corrigir aqui"
    t2 = "o chat apt ajuda muito e depois"
    lacunas = [
        {"posicao": t1.index("pra"), "inicio": 1.0, "fim": 1.9, "falante": "A"},
        {"posicao": t2.index(" e depois"), "inicio": 11.0, "fim": 12.0, "falante": "B"},
    ]
    falas = [{"texto": t1, "inicio": 0.0, "fim": 5.0}, {"texto": t2, "inicio": 10.0, "fim": 15.0}]
    T.aplicar_em_falas(falas, r, lacunas)
    assert lacunas[0]["posicao"] == t1.index("pra"), "fala sem correcao nao mexe"
    novo = falas[1]["texto"]
    assert novo[lacunas[1]["posicao"] :].startswith(" e depois"), novo


def test_lacuna_dentro_do_trecho_reescrito_vai_para_o_fim_da_substituicao():
    r = regras_de("chat apt => ChatGPT\n")
    texto = "o chat apt ajuda"
    lacunas = [{"posicao": texto.index(" apt"), "inicio": 1.0, "fim": 2.0, "falante": "A"}]
    falas = [{"texto": texto, "inicio": 0.0, "fim": 5.0}]
    T.aplicar_em_falas(falas, r, lacunas)
    assert falas[0]["texto"] == "o ChatGPT ajuda"
    assert lacunas[0]["posicao"] == len("o ChatGPT")


def test_tempos_de_palavra_deslocam_e_fundem_no_trecho_reescrito():
    """palavras_tempo: palavra depois da correcao desloca; as palavras DENTRO
    do trecho reescrito viram uma so, do tamanho da substituicao, do inicio
    da primeira ao fim da ultima - nunca somem sem horario."""
    r = regras_de("chat apt => ChatGPT\n")
    texto = "o chat apt ajuda"
    falas = [
        {
            "texto": texto,
            "inicio": 0.0,
            "fim": 3.0,
            "palavras_tempo": [
                [0, 1, 0.0, 0.2],
                [2, 4, 0.3, 0.6],
                [7, 3, 0.6, 1.0],
                [11, 5, 1.1, 1.6],
            ],
        }
    ]
    T.aplicar_em_falas(falas, r)
    f = falas[0]
    assert f["texto"] == "o ChatGPT ajuda"
    assert f["palavras_tempo"] == [[0, 1, 0.0, 0.2], [2, 7, 0.3, 1.0], [10, 5, 1.1, 1.6]]
    assert [f["texto"][a : a + b] for a, b, _, _ in f["palavras_tempo"]] == [
        "o",
        "ChatGPT",
        "ajuda",
    ]


def test_aplicar_em_falas_duas_vezes_nao_muda_nada_na_segunda():
    import copy

    r = regras_de("chat apt => ChatGPT\nmatriz lute => matriz GUT\n")
    texto = "o chat apt e a Matriz Lute com a Amanda"
    falas = [
        {
            "texto": texto,
            "inicio": 0.0,
            "fim": 9.0,
            "palavras_divergentes": [
                {"posicao": texto.index("Amanda"), "comprimento": 6, "falante": "X"}
            ],
            "palavras_baixa_confianca": [
                {"posicao": texto.index("com"), "comprimento": 3, "probabilidade": 0.2}
            ],
        }
    ]
    lacunas = [{"posicao": texto.index(" com"), "inicio": 1.0, "fim": 2.0, "falante": "A"}]
    primeira = T.aplicar_em_falas(falas, r, lacunas)
    assert sum(primeira.values()) == 2
    retrato = copy.deepcopy((falas, lacunas))
    segunda = T.aplicar_em_falas(falas, r, lacunas)
    assert segunda == {}
    assert (falas, lacunas) == retrato


# ==========================================================================
# casamento sem diferenciar acento
# ==========================================================================


def test_regra_sem_acento_casa_texto_com_e_sem_acento():
    """reuniao_07 ficou com "o Cláudio": a regra "o Claudio" nao pegava a
    palavra acentuada. O texto que entra e sempre o escrito na regra."""
    r = regras_de("o Claudio => o Claude\n")
    for entrada in (
        "pergunta pro o Cláudio agora",
        "pergunta pro o Claudio agora",
        "pergunta pro O CLÁUDIO agora",
    ):
        saida, contagem = T.aplicar(entrada, r)
        assert saida == "pergunta pro o Claude agora", f"{entrada!r} -> {saida!r}"
        assert contagem == {"o Claudio": 1}


def test_regra_com_acento_casa_texto_sem_acento():
    r = regras_de("matriz útil => matriz GUT\n")
    for entrada in ("a matriz útil", "a matriz util", "a Matriz Útil"):
        saida, _ = T.aplicar(entrada, r)
        assert saida == "a matriz GUT", f"{entrada!r} -> {saida!r}"


def test_sem_acento_nao_casa_dentro_de_outra_palavra():
    r = regras_de("o Claudio => o Claude\n")
    saida, contagem = T.aplicar("o Cláudiozinho chegou", r)
    assert saida == "o Cláudiozinho chegou" and not contagem, saida


def test_texto_que_ja_e_o_certo_com_acento_fica_como_esta():
    """ "Ja e o certo" ignora acento, nunca caixa: "Época Web" nao perde o
    acento para a grafia da regra, mas "época web" ainda ganha a caixa."""
    r = regras_de("epoca web => Epoca Web\n")
    saida, contagem = T.aplicar("no Época Web tem", r)
    assert saida == "no Época Web tem" and not contagem, saida
    saida, contagem = T.aplicar("no época web tem", r)
    assert saida == "no Epoca Web tem" and contagem == {"epoca web": 1}, saida


def test_sem_acento_mantem_o_comprimento():
    for t in ("Cláudio", "ação útil", "ÇÃO", "straße", "ﬁm", "a\u0301b", ""):
        assert len(T.sem_acento(t)) == len(t), t
    assert T.sem_acento("Cláudio ação") == "Claudio acao"


def test_posicoes_continuam_certas_depois_de_corrigir_com_acento():
    """ "o Cláudio" (9) -> "o Claude" (8): as quatro listas com posicao
    (divergentes, baixa confianca, lacunas, tempos de palavra) apontam
    para as mesmas palavras no texto corrigido - antes e depois do trecho
    com acento, e com acento tambem DEPOIS da correcao ("João")."""
    r = regras_de("o Claudio => o Claude\n")
    texto = "então o Cláudio respondeu ao João"
    palavras = texto.split()
    posicoes = []
    cursor = 0
    for w in palavras:
        cursor = texto.index(w, cursor)
        posicoes.append(cursor)
        cursor += len(w)
    tempos = [
        [p, len(w), i * 1.0, i * 1.0 + 0.9] for i, (p, w) in enumerate(zip(posicoes, palavras))
    ]
    lacunas = [{"posicao": texto.index(" ao"), "inicio": 2.0, "fim": 2.5, "falante": "A"}]
    falas = [
        {
            "texto": texto,
            "inicio": 0.0,
            "fim": 9.0,
            "palavras_divergentes": [
                {"posicao": texto.index("então"), "comprimento": 5, "falante": "X"},
                {"posicao": texto.index("João"), "comprimento": 4, "falante": "X"},
            ],
            "palavras_baixa_confianca": [
                {"posicao": texto.index("respondeu"), "comprimento": 9, "probabilidade": 0.3}
            ],
            "palavras_tempo": tempos,
        }
    ]
    contagem = T.aplicar_em_falas(falas, r, lacunas)
    f = falas[0]
    novo = f["texto"]
    assert novo == "então o Claude respondeu ao João", novo
    assert contagem == {"o Claudio": 1}
    assert [
        novo[d["posicao"] : d["posicao"] + d["comprimento"]] for d in f["palavras_divergentes"]
    ] == ["então", "João"]
    b = f["palavras_baixa_confianca"][0]
    assert novo[b["posicao"] : b["posicao"] + b["comprimento"]] == "respondeu"
    assert novo[lacunas[0]["posicao"] :].startswith(" ao João"), lacunas
    assert [novo[a : a + c] for a, c, _, _ in f["palavras_tempo"]] == [
        "então",
        "o Claude",
        "respondeu",
        "ao",
        "João",
    ]
    # "o" + "Cláudio" viram UMA palavra, do inicio da primeira ao fim da segunda
    assert f["palavras_tempo"][1][2:] == [1.0, 2.9]


# ==========================================================================
# prompt do Whisper
# ==========================================================================


def test_prompt_usa_lado_certo_e_deduplica():
    r = regras_de("chat APT => ChatGPT\nchat de EPT => ChatGPT\nmatriz root => matriz GUT\n")
    p = T.prompt_whisper(r)
    assert p.count("ChatGPT") == 1, p
    assert "matriz GUT" in p
    assert "chat APT" not in p, "o prompt deve conter o termo CORRETO"


def test_prompt_respeita_limite():
    r = regras_de("\n".join(f"errado{i} => TermoBemLongoNumero{i}" for i in range(50)))
    p = T.prompt_whisper(r, limite=100)
    assert len(p) <= 100


def test_prompt_vazio_retorna_none():
    assert T.prompt_whisper([]) is None


# ==========================================================================
# termos.exemplo.txt - o glossario de exemplo versionado (o termos.txt real
# e dado da empresa, fora do git)
# ==========================================================================

EXEMPLO = Path(__file__).resolve().parent.parent / "termos.exemplo.txt"


def test_termos_do_exemplo_carregam():
    # versionado: ausente e defeito, nunca motivo pra passar sem testar nada
    assert EXEMPLO.exists(), f"termos.exemplo.txt sumiu: {EXEMPLO}"
    r = T.carregar(EXEMPLO)
    assert len(r) > 0, "termos.exemplo.txt existe mas nenhuma regra foi lida"


def test_termos_do_exemplo_corrigem_as_formas_do_proprio_exemplo():
    """Cada grupo do exemplo corrige o que promete. Se alguem editar o
    exemplo e quebrar isso, o teste avisa."""
    r = T.carregar(EXEMPLO)
    casos = [
        ("hoje o chat de tibete escreve melhor que a gente", "ChatGPT"),
        ("fechamos o primeiro ponto da matriz de goutes", "matriz GUT"),
        ("quando o projeto e em housing, o prazo muda", "in house"),
        ("vamos testar o chat APT e comparar", "ChatGPT"),
        # "matriz útil" e "matriz util" pela MESMA regra (sem acento)
        ("fica com a gente levar para a matriz útil.", "matriz GUT"),
        ("levar para a matriz util", "matriz GUT"),
        # "o Claudio" pega a palavra com acento
        ("pergunta para o Cláudio o que ele acha", "o Claude"),
        ("para fechar, essa matriz good.", "matriz GUT"),
        # o lado certo leva acento: "extensao do Claude" vazaria sem
        ("instalei a extensão do cloud ontem", "a extensão do Claude ontem"),
        ("instalei a extensao do cloud ontem", "a extensão do Claude ontem"),
        # a mais especifica primeiro: a concordancia vai junto
        ("o numero do painel de orbita subiu", "do Painel Órbita"),
        ("abre o painel orbita", "o Painel Órbita"),
    ]
    for entrada, esperado in casos:
        saida, _ = T.aplicar(entrada, r)
        assert esperado in saida, f"{entrada!r} -> {saida!r}"


def test_termos_do_exemplo_nao_repetem_variacao_no_mesmo_termo():
    """ "chat APT => ChatGPT" estava duas vezes. A segunda nunca dispara (a
    primeira ja trocou o trecho) e aparecia repetida na tela."""
    from trama.servidor import glossario

    caminho = EXEMPLO
    vistas = {}
    for _, certo, errado in T.carregar(caminho):
        chave = (glossario.termo_do_vocabulario(certo).lower(), glossario._chave_variacao(errado))
        assert chave not in vistas, f"{errado!r} repetida em {certo!r}"
        vistas[chave] = errado


def test_termos_do_exemplo_lado_certo_com_acento():
    """O lado certo e o que vai para o transcript: palavra portuguesa sem
    o acento dela ("extensao", "gestao", "informacoes") e erro que a
    propria correcao introduz. Terminacao -ao/-aos/-oes sem til quase
    nunca e portugues - pega a familia toda sem lista de palavras."""
    import re

    caminho = EXEMPLO
    for _, certo, errado in T.carregar(caminho):
        sem_til = re.findall(r"\b\w+(?:ao|aos|oes)\b", certo, re.IGNORECASE)
        assert not sem_til, f"{errado!r} => {certo!r}: {sem_til} sem acento"


def test_termos_do_exemplo_sao_idempotentes():
    """Reaplicar o glossario numa reuniao ja corrigida (Perfil > Glossario
    > "Aplicar as reunioes ja processadas") nao pode mudar nada na segunda
    vez - o lado certo de uma regra nunca pode casar com o errado de
    outra."""
    caminho = EXEMPLO
    r = T.carregar(caminho)
    for _, _, errado in r:
        uma, _ = T.aplicar(f"antes {errado} depois", r)
        duas, contagem = T.aplicar(uma, r)
        assert duas == uma and not contagem, f"{errado!r}: {uma!r} -> {duas!r}"


def test_fala_corrigida_a_mao_nunca_passa_pelo_glossario():
    """edicao.py: a correcao manual e a palavra final - nem conta nem troca."""
    r = regras_de("questão à vista => Tabela à Vista\n")
    corrigida = {
        "falante": "X",
        "inicio": 0.0,
        "fim": 2.0,
        "texto": "a questão à vista, aqui, era isso mesmo",
        "edicao_manual": {
            "texto_original": "a questão à vista",
            "editado_em": "2026-11-10T12:00:00Z",
            "marcas_originais": {},
        },
    }
    normal = {"falante": "X", "inicio": 3.0, "fim": 5.0, "texto": "a questão à vista"}
    lacunas = [{"posicao": 2, "inicio": 0.5, "fim": 1.0, "falante": "X"}]
    contagem = T.aplicar_em_falas([corrigida, normal], r, lacunas)
    assert corrigida["texto"] == "a questão à vista, aqui, era isso mesmo"
    assert normal["texto"] == "a Tabela à Vista"
    assert contagem == {"questão à vista": 1}
    assert lacunas[0]["posicao"] == 2, "lacuna da fala corrigida foi deslocada"


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
