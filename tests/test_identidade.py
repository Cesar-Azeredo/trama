"""
tests/test_identidade.py - Checagens estaticas da identidade visual
(frontend/). Ver ADR 0023.

Fontes: a SIL OFL 1.1 exige que o texto da licenca acompanhe a fonte
redistribuida. O app empacota as .woff2 (nunca CDN), entao toda familia
declarada em fontes.css precisa do OFL.txt dela em
frontend/public/licencas/ - que o Vite copia tal e qual para o dist/.
As fontes do marco 1 ficaram meses sem ele; estes testes impedem que
uma fonte nova entre do mesmo jeito.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _ambiente  # noqa: E402

_ambiente.isolar()

RAIZ = Path(__file__).resolve().parent.parent
FRONTEND = RAIZ / "frontend"
FONTES_CSS = FRONTEND / "src" / "estilos" / "fontes.css"
PASTA_FONTES = FRONTEND / "src" / "estilos" / "fontes"
LICENCAS = FRONTEND / "public" / "licencas"


def _faces(css):
    """[(familia, arquivo .woff2)] de cada @font-face."""
    faces = []
    for bloco in re.findall(r"@font-face\s*\{(.*?)\}", css, re.S):
        familia = re.search(r'font-family:\s*"([^"]+)"', bloco).group(1)
        arquivo = re.search(r'url\("\./fontes/([^"]+)"\)', bloco).group(1)
        faces.append((familia, arquivo))
    return faces


def _licencas(pasta):
    """{nome do arquivo: texto} dos OFL-*.txt da pasta."""
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(pasta.glob("OFL-*.txt"))}


def _e_ofl_completa(texto):
    return (
        "SIL OPEN FONT LICENSE Version 1.1" in texto
        and "PERMISSION & CONDITIONS" in texto
        and "DISCLAIMER" in texto
    )


def _licenca_da_familia(familia, licencas):
    """A licenca cuja linha de copyright cita um nome proprio da familia
    ("Plex" em "IBM Plex Sans"). Palavras genericas de estilo nao contam:
    "Sans" casaria com qualquer fonte sem serifa."""
    genericas = {"sans", "serif", "mono", "display", "text"}
    palavras = [w for w in familia.split() if len(w) >= 4 and w.lower() not in genericas]
    for nome, texto in licencas.items():
        copyright = texto.strip().splitlines()[0]
        if any(w.lower() in copyright.lower() for w in palavras):
            return nome
    return None


# ==========================================================================


def test_toda_familia_de_fontes_css_tem_licenca_ofl():
    licencas = _licencas(LICENCAS)
    familias = sorted({f for f, _ in _faces(FONTES_CSS.read_text(encoding="utf-8"))})
    assert familias, "nenhuma @font-face em fontes.css"
    for familia in familias:
        nome = _licenca_da_familia(familia, licencas)
        assert nome, f"{familia}: sem OFL-*.txt em {LICENCAS.relative_to(RAIZ)}"
        assert _e_ofl_completa(licencas[nome]), f"{nome}: texto da OFL 1.1 incompleto"


def test_plex_so_pelo_subset_oficial_da_ibm():
    """A IBM Plex tem Reserved Font Name "Plex": subset feito por terceiros
    nao pode ser distribuido com esse nome. So entra o arquivo de subset da
    propria IBM (fonts/split/woff2/ do pacote @ibm/plex-mono), sem
    alteracao - ver ATRIBUICAO.md."""
    plex = [p.name for p in PASTA_FONTES.glob("*.woff2") if "plex" in p.name.lower()]
    assert plex, "nenhuma Plex empacotada"
    for nome in plex:
        assert nome.startswith("IBMPlex") and nome.endswith(("-Latin1.woff2", "-Latin2.woff2")), (
            f"{nome} nao e um subset oficial da IBM"
        )


def test_toda_woff2_empacotada_esta_declarada_em_fontes_css():
    """Uma .woff2 solta na pasta, sem @font-face, escaparia do teste da
    licenca acima - e seria distribuida do mesmo jeito se alguem a
    importasse por outro caminho."""
    declaradas = {a for _, a in _faces(FONTES_CSS.read_text(encoding="utf-8"))}
    na_pasta = {p.name for p in PASTA_FONTES.glob("*.woff2")}
    assert na_pasta == declaradas, (
        f"soltas: {sorted(na_pasta - declaradas)}; faltando: {sorted(declaradas - na_pasta)}"
    )


def test_familia_sem_licenca_reprovaria():
    """O teste de licenca pega o caso real: uma familia nova sem o OFL."""
    licencas = _licencas(LICENCAS)
    assert _licenca_da_familia("Fonte Inventada", licencas) is None
    assert _licenca_da_familia("Literata", licencas) is not None
    # "Sans" sozinho nao pode casar uma familia com a licenca de outra
    assert _licenca_da_familia("Source Sans", licencas) is None


def _sem_comentarios(codigo):
    """Tira /* */, {/* */} e // de .ts/.tsx/.html - comentario de
    desenvolvedor pode citar a ata (ADR 0002); texto de tela nao."""
    codigo = re.sub(r"/\*.*?\*/", " ", codigo, flags=re.S)
    codigo = re.sub(r"<!--.*?-->", " ", codigo, flags=re.S)
    return re.sub(r"(?<![:\"'])//[^\n]*", " ", codigo)


_PROMESSA_DE_ATA = re.compile(r"\batas?\b", re.I)


def _arquivos_de_interface():
    yield FRONTEND / "index.html"
    for p in sorted((FRONTEND / "src").rglob("*")):
        if p.suffix in (".ts", ".tsx"):
            yield p


def test_nenhum_texto_da_interface_promete_ata():
    """ADR 0002 e 0023: o valor e quem falou o que. A "memoria entre
    reunioes" da marca e a galeria de vozes e os termos da empresa."""
    achados = []
    for p in _arquivos_de_interface():
        texto = _sem_comentarios(p.read_text(encoding="utf-8"))
        for n, linha in enumerate(texto.splitlines(), 1):
            if _PROMESSA_DE_ATA.search(linha):
                achados.append(f"{p.relative_to(RAIZ)}:{n}")
    assert not achados, f"texto de interface fala em ata: {achados}"


def test_promessa_de_ata_reprovaria():
    assert _PROMESSA_DE_ATA.search("<p>Gere a ata da reunião</p>")
    assert _PROMESSA_DE_ATA.search('"Atas anteriores"')
    assert not _PROMESSA_DE_ATA.search(_sem_comentarios("// gera a ata (ADR 0002)\nx = 1"))
    assert not _PROMESSA_DE_ATA.search("const data = atalho; plataforma")


def _seletores_que_usam(css, token):
    """Seletores de toda regra cujo corpo usa var(--token)."""
    sem_coment = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    return [
        sel.strip()
        for sel, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", sem_coment)
        if f"var(--{token})" in corpo
    ]


# --tinta-apagada passa so 3:1 (SKILL.md): numero de reuniao de 30px, nada mais.
SELETORES_DO_APAGADO = {".linha-reuniao__numero--apagado"}


def test_tinta_apagada_so_no_numero_da_reuniao():
    """Ja vazou: as etapas pendentes do processamento usavam o apagado em
    texto de 14px, a 3,21:1."""
    usos = []
    for p in sorted((FRONTEND / "src").rglob("*.css")):
        if p.name == "tokens.css":
            continue
        for sel in _seletores_que_usam(p.read_text(encoding="utf-8"), "tinta-apagada"):
            if sel not in SELETORES_DO_APAGADO:
                usos.append(f"{p.relative_to(RAIZ)}: {sel}")
    assert not usos, f"--tinta-apagada fora do numero da reuniao: {usos}"


def test_apagado_em_texto_pequeno_reprovaria():
    css = ".lista-etapas__texto {\n  font-size: 14px;\n  color: var(--tinta-apagada);\n}"
    assert _seletores_que_usam(css, "tinta-apagada") == [".lista-etapas__texto"]
    assert (
        _seletores_que_usam("/* var(--tinta-apagada) */ .x { color: red; }", "tinta-apagada") == []
    )


def _declaracoes_com(css, trecho):
    """[(propriedade, valor)] de toda declaracao cujo valor contem trecho."""
    sem_coment = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    return [
        (prop.strip(), val.strip())
        for prop, val in re.findall(r"([a-z-]+)\s*:\s*([^;{}]+);", sem_coment)
        if trecho in val
    ]


def test_fio_so_aparece_como_fundo():
    """ADR 0023: o Fio e so fundo de destaque - nunca texto, linha, borda
    nem cor de voz (1,93:1 sobre o Linho). Fora do tokens.css, so o
    --destaque-fundo (ja misturado ao papel), e so em background."""
    erros = []
    for p in sorted((FRONTEND / "src").rglob("*.css")):
        if p.name == "tokens.css":
            continue
        css = p.read_text(encoding="utf-8")
        for prop, val in _declaracoes_com(css, "var(--destaque"):
            if "var(--destaque)" in val or prop not in ("background", "background-color"):
                erros.append(f"{p.relative_to(RAIZ)}: {prop}: {val}")
    assert not erros, f"Fio fora de fundo: {erros}"


def test_fio_como_borda_reprovaria():
    css = ".x { border-bottom: 2px solid var(--destaque-fundo); }"
    assert _declaracoes_com(css, "var(--destaque") == [
        ("border-bottom", "2px solid var(--destaque-fundo)")
    ]


def test_papeis_das_fontes():
    """ADR 0023: Figtree na interface, Literata no transcript, Plex Mono
    nos numeros. A Plex Sans saiu - nem token, nem @font-face, nem
    font-family solto em componente."""
    tokens = (FRONTEND / "src" / "estilos" / "tokens.css").read_text(encoding="utf-8")
    papel = lambda nome: re.search(rf"--fonte-{nome}:\s*\"([^\"]+)\"", tokens).group(1)
    assert papel("interface") == "Figtree"
    assert papel("corpo") == "Literata"
    assert papel("numeros") == "IBM Plex Mono"
    restos = [
        str(p.relative_to(RAIZ))
        for p in (FRONTEND / "src").rglob("*")
        if p.suffix in (".css", ".ts", ".tsx")
        and "Plex Sans" in _sem_comentarios(p.read_text(encoding="utf-8"))
    ]
    assert not restos, f"IBM Plex Sans ainda citada: {restos}"


CORES_DA_MARCA = {"#0e5a4a", "#e3a33b", "#14201c", "#f4f0e6"}


def test_marca_e_o_logotipo_trama():
    """ADR 0023: o simbolo e a palavra desenhada do kit, inline. Nunca o
    nome digitado no lugar, nunca as cores das vozes (a marca de quatro
    barras), nunca uma cor solta no componente."""
    tsx = (FRONTEND / "src" / "componentes" / "Marca.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Trama"' in tsx
    assert 'role="img"' in tsx
    codigo = _sem_comentarios(tsx)
    assert "rec·meet" not in codigo and "--voz-" not in codigo
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", codigo), "cor solta na Marca"
    # dois desenhos (claro e invertido), cada um com os dois fios do
    # simbolo e a palavra
    assert codigo.count("<path") == 6


def test_cor_da_marca_e_da_paleta_nos_dois_modos():
    css = (FRONTEND / "src" / "estilos" / "tokens.css").read_text(encoding="utf-8")
    valores = re.findall(r"--cor-marca:\s*(#[0-9a-fA-F]{6})", css)
    assert len(valores) == 2, valores
    assert {v.lower() for v in valores} <= CORES_DA_MARCA


def test_favicon_e_o_simbolo_nas_cores_da_marca():
    svg = (FRONTEND / "public" / "favicon.svg").read_text(encoding="utf-8")
    assert "Gradient" not in svg, "gradiente no favicon (proibido na skill)"
    cores = {c.lower() for c in re.findall(r'fill="(#[0-9a-fA-F]{6})"', svg)}
    assert cores and cores <= CORES_DA_MARCA, cores


_NOME_ANTIGO = re.compile(r"rec[-·_ ]?meet", re.I)
# Identificadores internos ficam (ADR 0023): chaves do localStorage.
_INTERNO = re.compile(r"""["']rec-meet:[a-z-]+["']""")


def test_nenhum_texto_da_interface_usa_o_nome_antigo():
    """O usuario ve "Trama". Comentario e chave do localStorage nao sao
    texto de tela - trocar a chave apagaria o tema e o perfil salvos."""
    achados = []
    for p in _arquivos_de_interface():
        texto = _INTERNO.sub(" ", _sem_comentarios(p.read_text(encoding="utf-8")))
        for n, linha in enumerate(texto.splitlines(), 1):
            if _NOME_ANTIGO.search(linha):
                achados.append(f"{p.relative_to(RAIZ)}:{n}: {linha.strip()[:60]}")
    assert not achados, f"nome antigo na interface: {achados}"


def test_titulo_da_pagina_e_trama():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert re.search(r"<title>\s*Trama\s*</title>", html)


def test_nome_antigo_reprovaria_e_chave_interna_passa():
    assert _NOME_ANTIGO.search("<p>rec·meet 1.0</p>")
    assert _NOME_ANTIGO.search("<title>rec-meet</title>")
    assert not _NOME_ANTIGO.search(_INTERNO.sub(" ", 'localStorage.getItem("rec-meet:tema")'))


def test_pagina_declara_portugues_do_brasil():
    """Com lang="en" o leitor de tela le o portugues com pronuncia de
    ingles - o app fica inutilizavel para quem depende dele."""
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    m = re.search(r"<html[^>]*\blang=\"([^\"]+)\"", html)
    assert m, "index.html sem lang no <html>"
    assert m.group(1) == "pt-BR", f'lang="{m.group(1)}"'


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
