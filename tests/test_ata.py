"""
tests/test_ata.py - Testes da verificacao de citacoes da ata.

A verificacao existe porque uma ata gerada por LLM inventou, num teste real:
  - que um custo "nao foi concluido na reuniao" quando havia numero explicito;
  - que uma pessoa "respondeu com nervosismo";
  - uma parafrase apresentada como fala literal.

Estes testes reproduzem a forma daquele transcript, com falas ficticias,
e o tipo de cada invencao real.

Uso:
    python tests/test_ata.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _ambiente  # noqa: E402

_ambiente.isolar()

from experimental import ata as A  # noqa: E402

TRANSCRIPT = """
[00:19:57] Celso: 40 relatorios por mes, montando todos na mao, talvez custe 15. 15 reais.
[00:20:04] Amanda: O total? E.
[00:21:32] Amanda: A gente vai construir do zero ou a gente vai contratar um sistema pronto?
[00:01:51] Celso: Pode ser, colocar dentro da planilha.
[00:49:13] Ramiro: Entao a gente fecha hoje com a decisao que vai testar o chat EPT e essa semana.
[01:03:28] Amanda: Eu vou fechar mais 20 contratos por semana.
[00:02:31] Luciano: o barco de tarde o pensando que nos uma ladeira  [vozes sobrepostas]
"""


def _suspeitas(citacoes):
    """Citacoes que NAO foram confirmadas (aproximadas ou nem isso)."""
    _, aprox = A.verificar_citacoes(citacoes, TRANSCRIPT)
    return {c for c, _, _ in aprox}


def _confirmadas(citacoes, transcript=TRANSCRIPT):
    conf, _ = A.verificar_citacoes(citacoes, transcript)
    return conf


# ==========================================================================
# normalizacao
# ==========================================================================


def test_normalizar_remove_acento_e_pontuacao():
    assert A.normalizar("Não, é ISSO!") == "nao e isso"


def test_normalizar_colapsa_espacos():
    assert A.normalizar("a   b\n c") == "a b c"


# ==========================================================================
# extracao
# ==========================================================================


def test_extrai_citacao_entre_aspas():
    md = 'Decisão: "Pode ser, colocar dentro da planilha"'
    assert A.extrair_citacoes(md) == ["Pode ser, colocar dentro da planilha"]


def test_ignora_citacao_curta():
    """'Sim' e 'Pode ser' geram falso positivo: casam com qualquer coisa."""
    assert A.extrair_citacoes('Ele disse "Sim" e depois "Tá bom"') == []


def test_deduplica_citacoes():
    md = '1. "Pode ser, colocar dentro da planilha"\n2. "pode ser, colocar dentro da planilha!"'
    assert len(A.extrair_citacoes(md)) == 1


def test_nao_captura_texto_entre_citacoes():
    """
    REGRESSAO: com o filtro de tamanho DENTRO da regex, uma citacao curta como
    "Pode ser" falhava o minimo e o pareamento das aspas desalinhava, passando
    a capturar o texto entre a aspa que fecha uma citacao e a que abre a
    seguinte. Produziu tres falsos positivos numa ata real.
    """
    real = (
        'Celso concordou ("Pode ser"). Amanda afirmou que a matriz GUT '
        'esta "bem para baixo" e ainda nao iniciada.'
    )
    for c in A.extrair_citacoes(real):
        assert c[0] not in ")];|,.:", f"capturou texto entre citacoes: {c!r}"


def test_ignora_separador_de_tabela():
    linha = (
        '| Grupo | Definir objetivo | nao definido | "a gente so precisa '
        'combinar aqui qual e a meta" |'
    )
    cit = A.extrair_citacoes(linha)
    assert len(cit) == 1, cit
    assert " | " not in cit[0]


def test_extrai_aspas_curvas():
    md = "\u201cA gente vai construir do zero ou contratar\u201d"
    assert len(A.extrair_citacoes(md)) == 1


# ==========================================================================
# verificacao - citacoes verdadeiras (exatas e so-diferem-em-formatacao)
# ==========================================================================


def test_confirma_citacao_literal():
    c = "A gente vai construir do zero ou a gente vai contratar um sistema pronto?"
    assert c not in _suspeitas([c])
    tipos = {t for cit, t in _confirmadas([c]) if cit == c}
    assert tipos == {"exata"}, tipos


def test_confirma_numero_que_o_modelo_dizia_nao_existir():
    """
    O erro mais grave da ata de teste: o modelo afirmou que o custo nao foi
    definido, quando o transcript traz o numero.
    """
    c = "talvez custe 15. 15 reais"
    assert c not in _suspeitas([c])


def test_confirma_mesmo_sem_acento_no_transcript():
    """Transcript sem acento, citacao com acento: tem de casar como
    diferenca de FORMATACAO, nao como exata (o texto bruto difere)."""
    c = "a gente fecha hoje com a decisão que vai testar o chat EPT"
    assert c not in _suspeitas([c])
    tipos = {t for cit, t in _confirmadas([c]) if cit == c}
    assert tipos == {"formatacao"}, tipos


def test_confirma_com_pontuacao_diferente():
    c = "Pode ser colocar dentro da planilha"
    assert c not in _suspeitas([c])
    tipos = {t for cit, t in _confirmadas([c]) if cit == c}
    assert tipos == {"formatacao"}, tipos


# ==========================================================================
# verificacao - invencoes reais (paráfrase, fato invertido)
# ==========================================================================


def test_acusa_descricao_de_emocao_inventada():
    c = "Amanda respondeu com nervosismo que tem fila de um milhão de pedidos"
    assert c in _suspeitas([c])


def test_acusa_afirmacao_contraria_ao_transcript():
    c = "o número não foi concluído na reunião"
    assert c in _suspeitas([c])


def test_acusa_parafrase_apresentada_como_fala():
    c = "a automação in-house de Celso se mostrou muito complexa"
    assert c in _suspeitas([c])


def test_lote_misto_classifica_todos_corretamente():
    verdadeiras = [
        "A gente vai construir do zero ou a gente vai contratar um sistema pronto?",
        "talvez custe 15. 15 reais",
        "Eu vou fechar mais 20 contratos por semana",
    ]
    falsas = [
        "Amanda respondeu com nervosismo que tem fila de um milhão",
        "o número não foi concluído na reunião",
        "Celso prometeu entregar o sistema na segunda-feira",
    ]
    susp = _suspeitas(verdadeiras + falsas)
    for c in verdadeiras:
        assert c not in susp, f"falso alarme: {c}"
    for c in falsas:
        assert c in susp, f"nao pegou invencao: {c}"


# ==========================================================================
# verificacao - negacao e numero trocados (a semelhanca de caracteres NAO
# pode confundir isso com citacao confirmada)
# ==========================================================================


def test_negacao_acrescentada_nao_e_confirmada():
    """
    O bug relatado de verdade: a fonte aprova a compra, a citacao da ata
    afirma o CONTRARIO ("não aprovamos"). So um "não" a mais, textualmente
    quase identico - e e exatamente por isso que a comparacao aproximada
    (difflib) NAO PODE contar como confirmacao.
    """
    transcript = (
        "[00:10:00] Ramiro: Nós aprovamos a compra de todos os "
        "equipamentos para a equipe neste trimestre."
    )
    c = "Nós não aprovamos a compra de todos os equipamentos para a equipe neste trimestre"
    conf, aprox = A.verificar_citacoes([c], transcript)
    assert conf == [], conf
    assert any(cit == c for cit, _, _ in aprox)


def test_negacao_removida_nao_e_confirmada():
    """O inverso: a fonte tem a negacao, a citacao da ata a removeu."""
    transcript = "[00:10:00] Ramiro: Nós não aprovamos a compra de equipamentos neste trimestre."
    c = "Nós aprovamos a compra de equipamentos neste trimestre"
    conf, aprox = A.verificar_citacoes([c], transcript)
    assert conf == [], conf
    assert any(cit == c for cit, _, _ in aprox)


def test_numero_alterado_nao_e_confirmado():
    transcript = "[00:05:00] Celso: Fechamos em 40 relatórios por mês, esse é o volume."
    c = "Fechamos em 42 relatórios por mês, esse é o volume"
    conf, aprox = A.verificar_citacoes([c], transcript)
    assert conf == [], conf
    assert any(cit == c for cit, _, _ in aprox)


def test_aproximada_nunca_e_promovida_a_confirmada_mesmo_com_alta_semelhanca():
    """
    REGRESSAO DIRETA: antes desta correcao, verificar_citacoes tinha uma
    segunda etapa que promovia qualquer correspondencia aproximada acima de
    SEMELHANCA_MIN a 'confirmada'. Isso e o que deixou passar o caso da
    negacao acima. Este teste trava o contrato: aproximada por definicao
    nunca aparece em `confirmadas`, nao importa quao alta a semelhanca.
    """
    transcript = "Nós aprovamos a compra de todos os equipamentos para a equipe."
    c = "Nós não aprovamos a compra de todos os equipamentos para a equipe"
    conf, aprox = A.verificar_citacoes([c], transcript)
    assert conf == []
    assert len(aprox) == 1
    _, semelhanca, _ = aprox[0]
    assert semelhanca >= A.SEMELHANCA_MIN, (
        "o teste so faz sentido se a semelhanca for alta apesar do sentido "
        f"trocado - veio {semelhanca:.2f}"
    )


# ==========================================================================
# blocos e carregamento
# ==========================================================================


def test_blocos_nao_perdem_linha():
    linhas = [f"linha {i}" for i in range(400)]
    b = A.blocos(linhas, 30)
    assert sum(len(x.splitlines()) for x in b) == 400
    assert all(len(x.splitlines()) <= 30 for x in b)


def test_blocos_ignora_linha_vazia():
    b = A.blocos(["a", "", "  ", "b"], 30)
    assert b[0].splitlines() == ["a", "b"]


def test_limpar_remove_raciocinio_do_modelo():
    assert A.limpar("<think>penso...</think>\n\nAta real") == "Ata real"


def test_carregar_json_marca_fala_sobreposta(tmp_path=None):
    import json
    import tempfile

    p = Path(tempfile.mkdtemp()) / "t.json"
    json.dump(
        {
            "falas": [
                {"inicio": 10.0, "fim": 20.0, "falante": "Amanda", "texto": "limpa"},
                {"inicio": 100.0, "fim": 110.0, "falante": "Celso", "texto": "junto"},
            ],
            "regioes_sobrepostas": [
                {"inicio": 100.0, "fim": 108.0, "falantes": ["Celso", "Ramiro"]}
            ],
            "dinamica": {"Amanda": {"fala_s": 10.0, "fala_pct": 50.0}},
        },
        open(p, "w"),
    )
    linhas, din = A.carregar(p)
    assert "[vozes sobrepostas]" not in linhas[0], linhas[0]
    assert "[vozes sobrepostas]" in linhas[1], linhas[1]
    assert "Amanda" in din


def test_em_sobreposicao_exige_fracao_minima():
    reg = [{"inicio": 39.0, "fim": 40.0}]
    assert A.em_sobreposicao(0.0, 40.0, reg) is False
    assert A.em_sobreposicao(39.0, 40.0, reg) is True


# ==========================================================================
# rodape_verificacao - o que o usuario realmente le na ata
# ==========================================================================


def test_rodape_sem_nenhuma_citacao_extraida_avisa_sem_transmitir_aprovacao():
    """
    Se a ata nao tem nenhuma citacao para checar, o rodape tem de dizer isso
    explicitamente - nunca dar a entender que a ausencia de citacoes
    suspeitas significa "tudo confirmado".
    """
    linhas = A.rodape_verificacao([], [], [])
    texto = "\n".join(linhas)
    assert "nenhuma citação foi extraída" in texto.lower()
    assert "pôde ser verificado" in texto.lower()


def test_rodape_nenhuma_confirmada_alerta_explicitamente():
    """Citacoes existem mas nenhuma bateu: nao pode parecer uma ata limpa."""
    aprox = [("frase qualquer nao encontrada no transcript", 0.3, "")]
    linhas = A.rodape_verificacao(["frase qualquer nao encontrada no transcript"], [], aprox)
    texto = "\n".join(linhas)
    assert "nenhuma citação pôde ser confirmada" in texto.lower()


def test_rodape_nao_usa_mais_a_palavra_parafraseou_como_veredito():
    """
    REGRESSAO: o aviso antigo dizia "o modelo parafraseou", afirmando uma
    causa que a verificacao textual nao tem como provar. A frase certa e
    'nao foi possivel localizar' - o texto pode ser parafrase, erro de
    transcricao OU invencao; so a leitura humana decide qual.
    """
    aprox = [("algo nao encontrado", 0.5, "")]
    linhas = A.rodape_verificacao(["algo nao encontrado"], [], aprox)
    texto = "\n".join(linhas).lower()
    assert "modelo parafraseou" not in texto
    assert "não foram localizados" in texto or "nao foram localizados" in texto


def test_rodape_deixa_claro_que_localizar_nao_valida_o_conteudo():
    """A localização de uma citação não comprova que a decisão/responsável
    estejam corretos - isso tem de estar escrito, nao so implicito."""
    linhas = A.rodape_verificacao(
        ["A gente vai construir do zero ou a gente vai contratar um sistema pronto?"],
        [("A gente vai construir do zero ou a gente vai contratar um sistema pronto?", "exata")],
        [],
    )
    texto = "\n".join(linhas).lower()
    assert "não comprova" in texto or "nao comprova" in texto


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
