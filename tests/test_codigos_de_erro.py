"""
tests/test_codigos_de_erro.py - Todo codigo de erro ou aviso que o servidor
emite (trama/erros.py) tem texto nos dois catalogos do frontend
(frontend/src/i18n/pt/erros.ts e en/erros.ts). Sem isto, um codigo novo no
servidor apareceria na tela como "Erro do servidor (codigo)".

Uso:
    python tests/test_codigos_de_erro.py
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CATALOGOS = {
    idioma: RAIZ / "frontend" / "src" / "i18n" / idioma / "erros.ts" for idioma in ("pt", "en")
}

# _erro(404, "codigo"), XInvalido("codigo"), ArquivoMuitoGrande("codigo"), aviso("codigo")
_USOS = re.compile(
    r'(?:_erro\(\s*\d+,\s*|Invalid[oa]\(\s*|ArquivoMuitoGrande\(\s*|aviso\(\s*)"([a-z0-9_]+)"'
)


def codigos_do_servidor():
    codigos = set()
    for arquivo in (RAIZ / "trama").rglob("*.py"):
        codigos |= set(_USOS.findall(arquivo.read_text(encoding="utf-8")))
    return codigos


def codigos_do_catalogo(idioma):
    texto = CATALOGOS[idioma].read_text(encoding="utf-8")
    bloco = texto[texto.index("porCodigo: {") :]
    return set(re.findall(r"^\s{4}([a-z0-9_]+):", bloco, re.M))


def test_servidor_emite_codigos():
    # sanidade do proprio teste: a varredura tem de achar os codigos
    codigos = codigos_do_servidor()
    assert len(codigos) > 50, sorted(codigos)
    assert {"reuniao_nao_encontrada", "linha_nao_texto", "edicoes_sem_fala"} <= codigos


def test_todo_codigo_do_servidor_tem_texto_nos_dois_idiomas():
    servidor = codigos_do_servidor()
    for idioma in CATALOGOS:
        faltando = sorted(servidor - codigos_do_catalogo(idioma))
        assert not faltando, f"sem texto em {idioma}/erros.ts: {faltando}"


def test_catalogos_tem_os_mesmos_codigos():
    assert codigos_do_catalogo("pt") == codigos_do_catalogo("en")


def test_nenhuma_resposta_de_erro_com_frase_pronta():
    """O servidor nunca manda texto em portugues como detail."""
    for arquivo in (RAIZ / "trama" / "servidor").glob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        assert not re.search(r'detail=f?"', texto), arquivo


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
