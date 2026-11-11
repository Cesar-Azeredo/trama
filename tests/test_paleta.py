"""
Testes da paleta de cores de voz (frontend/src/estilos/tokens.css).

Contraste contra o fundo nao basta: as cores antigas passavam 4,5:1 e
ainda assim Amanda e Rolando (voz-1/voz-7, dE2000 8,1) e Gerardo e Ramiro
(voz-4/voz-6, 11,8) saiam "o mesmo bege" e "o mesmo azul" numa barrinha de
3px. Estes testes travam a distancia perceptual ENTRE as cores - em visao
normal e simulando daltonismo - e contra as cores reservadas que uma voz
nunca pode parecer: os tres papeis de cor da marca Trama (ADR 0023) -
--acento (Verde: acao e foco), --alerta (vermelho funcional: disputa e
erro) e --destaque (Fio: fundo de destaque) - e --tinta-tenue (falante
desconhecido). Tambem travam os proprios papeis: contraste de texto e
de rotulo de botao, e alerta distinguivel do acento com daltonismo.

Sem dependencia nova: CIEDE2000 e simulacao de daltonismo (Machado 2009,
severidade 1) escritos aqui, sobre sRGB -> CIELAB (D65).
"""

import itertools
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import _ambiente  # noqa: E402

_ambiente.isolar()

TOKENS = Path(__file__).resolve().parent.parent / "frontend" / "src" / "estilos" / "tokens.css"

MIN_ENTRE_VOZES = 14.0  # dE2000, visao normal
MIN_DALTONISMO = 6.0  # dE2000, deuteranopia e protanopia simuladas
MIN_ACENTO = 18.0  # voz nunca parece um papel de cor (acao, erro, destaque)
PAPEIS = ("acento", "alerta", "destaque")
MIN_ALERTA_ACENTO_DALTONISMO = 10.0  # erro nunca parece acao, nem com daltonismo
MIN_TENUE = 12.0  # voz nunca parece "desconhecido"
MIN_CONTRASTE = 4.5  # nome do falante e texto de 11px


def _blocos():
    css = TOKENS.read_text(encoding="utf-8")
    claro = re.search(r":root\s*\{(.*?)\}", css, re.S).group(1)
    escuro = re.search(r':root\[data-tema="escuro"\]\s*\{(.*?)\}', css, re.S).group(1)
    ler = lambda bloco: dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", bloco))
    return {"claro": ler(claro), "escuro": ler(escuro)}


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(h):
    h = h.lstrip("#")
    return [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]


def _lab(h):
    r, g, b = [_lin(c) for c in _rgb(h)]
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def de2000(h1, h2):
    L1, a1, b1 = _lab(h1)
    L2, a2, b2 = _lab(h2)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cm**7 / (Cm**7 + 25**7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dL, dC = L2 - L1, C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dH = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lm, Cmp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hm = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hm = (h1p + h2p) / 2
    else:
        hm = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    T = (
        1
        - 0.17 * math.cos(math.radians(hm - 30))
        + 0.24 * math.cos(math.radians(2 * hm))
        + 0.32 * math.cos(math.radians(3 * hm + 6))
        - 0.20 * math.cos(math.radians(4 * hm - 63))
    )
    dT = 30 * math.exp(-(((hm - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cmp**7 / (Cmp**7 + 25**7))
    Sl = 1 + 0.015 * (Lm - 50) ** 2 / math.sqrt(20 + (Lm - 50) ** 2)
    Sc = 1 + 0.045 * Cmp
    Sh = 1 + 0.015 * Cmp * T
    Rt = -math.sin(math.radians(2 * dT)) * Rc
    return math.sqrt((dL / Sl) ** 2 + (dC / Sc) ** 2 + (dH / Sh) ** 2 + Rt * (dC / Sc) * (dH / Sh))


def contraste(a, b):
    lum = lambda h: sum(k * _lin(c) for k, c in zip((0.2126, 0.7152, 0.0722), _rgb(h)))
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


_DEUTAN = [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.011820, 0.042940, 0.968881],
]
_PROTAN = [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
]


def _simular(h, m):
    r, g, b = [_lin(c) for c in _rgb(h)]
    out = [max(0.0, min(1.0, m[i][0] * r + m[i][1] * g + m[i][2] * b)) for i in range(3)]
    enc = lambda c: 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return "#" + "".join(f"{round(enc(c) * 255):02x}" for c in out)


def _vozes(tokens):
    return {f"voz-{i}": tokens[f"voz-{i}"] for i in range(1, 9)}


def _pior_par(cores):
    return min(
        (de2000(a, b), na, nb) for (na, a), (nb, b) in itertools.combinations(cores.items(), 2)
    )


# ==========================================================================


def test_oito_vozes_nos_dois_modos():
    for modo, tokens in _blocos().items():
        assert len(_vozes(tokens)) == 8, modo


def test_vozes_distintas_entre_si_em_visao_normal():
    for modo, tokens in _blocos().items():
        d, a, b = _pior_par(_vozes(tokens))
        assert d >= MIN_ENTRE_VOZES, f"{modo}: {a} e {b} a dE {d:.1f}"


def test_vozes_distintas_simulando_daltonismo():
    for modo, tokens in _blocos().items():
        for nome, m in (("deuteranopia", _DEUTAN), ("protanopia", _PROTAN)):
            sim = {k: _simular(v, m) for k, v in _vozes(tokens).items()}
            d, a, b = _pior_par(sim)
            assert d >= MIN_DALTONISMO, f"{modo}/{nome}: {a} e {b} a dE {d:.1f}"


def test_os_tres_papeis_de_cor_existem_nos_dois_modos():
    """Se o bloco escuro nao redefine um papel, o navegador herda o valor
    do claro - vermelho escuro sobre fundo escuro - e os testes abaixo nao
    veriam, porque leem cada bloco sozinho."""
    for modo, tokens in _blocos().items():
        for papel in PAPEIS + ("acento-fundo", "alerta-fundo"):
            assert papel in tokens, f"{modo}: --{papel} nao definido"


def test_nenhuma_voz_parece_um_papel_de_cor_nem_desconhecido():
    for modo, tokens in _blocos().items():
        for voz, cor in _vozes(tokens).items():
            for papel in PAPEIS:
                d = de2000(cor, tokens[papel])
                assert d >= MIN_ACENTO, f"{modo}: {voz} a dE {d:.1f} do --{papel}"
            dt = de2000(cor, tokens["tinta-tenue"])
            assert dt >= MIN_TENUE, f"{modo}: {voz} a dE {dt:.1f} do tinta-tenue"


def test_acento_e_alerta_passam_contraste_de_texto():
    """Os dois viram texto: link e acao ("adicionar", "trocar") no
    acento; mensagem de erro no alerta. E os hovers de texto tambem."""
    for modo, tokens in _blocos().items():
        for papel in ("acento", "acento-fundo", "alerta", "alerta-fundo"):
            for fundo in ("fundo", "superficie"):
                c = contraste(tokens[papel], tokens[fundo])
                assert c >= MIN_CONTRASTE, f"{modo}: --{papel} {c:.2f}:1 em --{fundo}"


def test_rotulo_do_botao_passa_contraste_sobre_acento_e_alerta():
    """Botao principal (acento) e o de exclusao (alerta) escrevem em
    --fundo sobre a cor, em repouso e no hover."""
    for modo, tokens in _blocos().items():
        for papel in ("acento", "acento-fundo", "alerta", "alerta-fundo"):
            c = contraste(tokens["fundo"], tokens[papel])
            assert c >= MIN_CONTRASTE, f"{modo}: rotulo sobre --{papel} {c:.2f}:1"


def test_alerta_nunca_parece_acento_nem_com_daltonismo():
    """Erro em vermelho ao lado de acao em verde: o par classico que some
    em protanopia. O vermelho carmim cai a dE 3-5 do Verde Trama
    simulado; o vermelhao segura acima de 12 (medido no ADR 0023)."""
    for modo, tokens in _blocos().items():
        for nome, m in (("deuteranopia", _DEUTAN), ("protanopia", _PROTAN)):
            d = de2000(_simular(tokens["alerta"], m), _simular(tokens["acento"], m))
            assert d >= MIN_ALERTA_ACENTO_DALTONISMO, f"{modo}/{nome}: dE {d:.1f}"


def test_tons_de_tinta_passam_o_limiar_de_cada_um():
    """Os tres tons fracos nao sao intercambiaveis (SKILL.md): fraca e
    texto de qualquer tamanho (4,5:1); tenue e apagada, so 24px+ ou nao
    texto (3:1). Corpo e media, texto corrido: folga de 7:1.

    Tenue e apagada so aparecem sobre o --fundo (numero da reuniao na
    lista, etapa pendente, regua): medidos so contra ele. O apagado do
    escuro da paleta Arquivo cai a 2,88:1 sobre a --superficie."""
    limiares = {
        "tinta": 7.0,
        "tinta-corpo": 7.0,
        "tinta-media": 7.0,
        "tinta-fraca": 4.5,
        "tinta-tenue": 3.0,
        "tinta-apagada": 3.0,
    }
    so_no_fundo = {"tinta-tenue", "tinta-apagada"}
    for modo, tokens in _blocos().items():
        for tom, minimo in limiares.items():
            fundos = ("fundo",) if tom in so_no_fundo else ("fundo", "superficie")
            for fundo in fundos:
                c = contraste(tokens[tom], tokens[fundo])
                assert c >= minimo, f"{modo}: --{tom} {c:.2f}:1 em --{fundo}"


def test_alerta_carmim_reprovaria():
    """O teste de daltonismo pega o vermelho que pareceria natural."""
    m = _PROTAN
    assert de2000(_simular("#a0333a", m), _simular("#0e5a4a", m)) < MIN_ALERTA_ACENTO_DALTONISMO


def test_vozes_passam_contraste_de_texto_no_fundo_e_na_superficie():
    for modo, tokens in _blocos().items():
        for voz, cor in _vozes(tokens).items():
            for fundo in ("fundo", "superficie"):
                c = contraste(cor, tokens[fundo])
                assert c >= MIN_CONTRASTE, f"{modo}: {voz} {c:.2f}:1 em --{fundo}"


def _opacidade_sobreposicao():
    css = TOKENS.read_text(encoding="utf-8")
    return float(re.search(r"--opacidade-sobreposicao:\s*([\d.]+)%", css).group(1)) / 100


def _sobre_o_papel(cor, papel, a):
    """color-mix(in srgb, cor a%, transparent) desenhado sobre o papel: a
    mistura em sRGB codificado, que e o que o navegador compoe."""
    return "#" + "".join(
        f"{round((a * x + (1 - a) * y) * 255):02x}" for x, y in zip(_rgb(cor), _rgb(papel))
    )


def test_texto_sobre_a_faixa_de_sobreposicao_passa_contraste_folgado():
    """So --tinta-corpo fica em cima da faixa (a pista troca a letra para
    ela, Detalhe.css). Sobre qualquer faixa - cor de qualquer voz, ou
    tinta-tenue de voz sem pessoa - o corpo do transcript tem de seguir
    acima de 7:1 nos dois modos: e texto corrido, lido por muito tempo."""
    a = _opacidade_sobreposicao()
    for modo, tokens in _blocos().items():
        faixas = list(_vozes(tokens).values()) + [tokens["tinta-tenue"]]
        for faixa in faixas:
            fundo = _sobre_o_papel(faixa, tokens["fundo"], a)
            c = contraste(tokens["tinta-corpo"], fundo)
            assert c >= 7.0, f"{modo}: corpo sobre faixa {faixa} a {c:.2f}:1"


def test_faixa_de_sobreposicao_e_visivel_sobre_o_papel():
    """Visivel "o suficiente para ver": dE2000 >= 5 contra o papel para
    TODA cor de faixa, nos dois modos - a mais clara incluida."""
    a = _opacidade_sobreposicao()
    for modo, tokens in _blocos().items():
        for faixa in list(_vozes(tokens).values()) + [tokens["tinta-tenue"]]:
            d = de2000(_sobre_o_papel(faixa, tokens["fundo"], a), tokens["fundo"])
            assert d >= 5.0, f"{modo}: faixa {faixa} a dE {d:.1f} do papel"


def test_pista_na_cor_da_voz_sobre_a_faixa_reprovaria():
    """Motivo de a pista trocar a letra para --tinta-corpo dentro da faixa:
    na cor da voz, sobre a faixa, algum par cai abaixo de 4,5:1."""
    a = _opacidade_sobreposicao()
    tokens = _blocos()["claro"]
    pior = min(
        contraste(t, _sobre_o_papel(f, tokens["fundo"], a))
        for t in _vozes(tokens).values()
        for f in _vozes(tokens).values()
    )
    assert pior < MIN_CONTRASTE


def _opacidade_destaque():
    """{modo: fracao} de --opacidade-destaque em cada bloco."""
    css = TOKENS.read_text(encoding="utf-8")
    claro = re.search(r":root\s*\{(.*?)\}", css, re.S).group(1)
    escuro = re.search(r':root\[data-tema="escuro"\]\s*\{(.*?)\}', css, re.S).group(1)
    ler = lambda b: float(re.search(r"--opacidade-destaque:\s*([\d.]+)%", b).group(1)) / 100
    return {"claro": ler(claro), "escuro": ler(escuro)}


def _destaque_fundo(tokens, a):
    """--destaque-fundo: color-mix(in srgb, destaque a%, fundo) - opaco."""
    return _sobre_o_papel(tokens["destaque"], tokens["fundo"], a)


def test_texto_sobre_o_destaque_passa_contraste():
    """Trecho tocando, busca e selecao: corpo e tinta por cima a 7:1
    (texto corrido); --tinta-media, para onde sobem lacuna e lapis dentro
    do trecho tocando, a 4,5:1."""
    ops = _opacidade_destaque()
    for modo, tokens in _blocos().items():
        fundo = _destaque_fundo(tokens, ops[modo])
        for tom, minimo in (("tinta", 7.0), ("tinta-corpo", 7.0), ("tinta-media", 4.5)):
            c = contraste(tokens[tom], fundo)
            assert c >= minimo, f"{modo}: --{tom} {c:.2f}:1 sobre o destaque"


def test_faixa_de_voz_dentro_do_trecho_tocando_passa_contraste():
    """A faixa de sobreposicao (transparente) desenha por cima do
    destaque quando a fala toca: o corpo segue legivel nas duas camadas."""
    ops, a = _opacidade_destaque(), _opacidade_sobreposicao()
    for modo, tokens in _blocos().items():
        base = _destaque_fundo(tokens, ops[modo])
        for faixa in list(_vozes(tokens).values()) + [tokens["tinta-tenue"]]:
            c = contraste(tokens["tinta-corpo"], _sobre_o_papel(faixa, base, a))
            assert c >= MIN_CONTRASTE, f"{modo}: corpo sobre faixa {faixa}+destaque {c:.2f}:1"


def test_destaque_e_visivel_e_nao_parece_faixa_de_voz():
    """Visivel contra o papel, e nunca confundivel com a faixa de
    sobreposicao de uma voz (a castanha, no claro, e a mais perto)."""
    ops, a = _opacidade_destaque(), _opacidade_sobreposicao()
    for modo, tokens in _blocos().items():
        d = _destaque_fundo(tokens, ops[modo])
        vis = de2000(d, tokens["fundo"])
        assert vis >= 8.0, f"{modo}: destaque a dE {vis:.1f} do papel"
        for voz, cor in _vozes(tokens).items():
            dv = de2000(d, _sobre_o_papel(cor, tokens["fundo"], a))
            assert dv >= 8.0, f"{modo}: destaque a dE {dv:.1f} da faixa da {voz}"


def test_cor_de_voz_e_tinta_fraca_sobre_o_destaque_reprovariam():
    """Motivo de o Detalhe.css trocar a pista para --tinta-corpo e a
    lacuna/lapis para --tinta-media dentro de .trecho-tocando."""
    ops = _opacidade_destaque()
    tokens = _blocos()["claro"]
    d = _destaque_fundo(tokens, ops["claro"])
    assert contraste(tokens["tinta-fraca"], d) < MIN_CONTRASTE
    assert min(contraste(v, d) for v in _vozes(tokens).values()) < MIN_CONTRASTE


def test_paleta_antiga_reprovaria():
    """O teste pega o defeito que motivou a troca - senao ele nao prova
    nada sobre a paleta nova."""
    antiga = {"voz-1": "#8a5a34", "voz-7": "#7a6240"}
    d, _, _ = _pior_par(antiga)
    assert d < MIN_ENTRE_VOZES


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
