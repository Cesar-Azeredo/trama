"""
Isola as suites das variaveis de ambiente de quem roda os testes.

O codigo le limiares de calibracao (SIM_MIN, MIN_SOBREPOSICAO,
GAP_MESCLAGEM...) e caminhos (VOZES_DB, TRAMA_AUDIOS) do ambiente NA
HORA DO IMPORT. Um shell com qualquer uma delas exportada - o README
convida a calibrar assim, e o ambiente de desenvolvimento ja roda com
SIM_MIN=0.60 exportado - fazia a suite testar outro numero que nao o
padrao do codigo: SIM_MIN=0.9 derrubava 2 testes de test_pipeline,
MIN_SOBREPOSICAO=0.3 derrubava 1 de test_interacao. Pior que falhar: um
valor exportado que por acaso nao quebra nada faz a suite passar
validando um limiar que nao e o que o codigo entrega.

A lista de variaveis NAO e escrita a mao (divergiria na primeira
variavel nova): sai de uma varredura do proprio codigo por
os.environ.get("X") / os.environ["X"] / os.getenv("X").

Uso: no topo de cada suite, ANTES de importar qualquer modulo do
projeto -

    import _ambiente  # noqa: E402
    _ambiente.isolar()
"""

import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Lidas pelo codigo mas nao mudam resultado de teste nenhum - e tirar
# atrapalharia quem roda a suite (nenhum teste baixa modelo, mas nada
# ganha em apagar o token).
PRESERVADAS = {"HF_TOKEN"}

_LEITURA = re.compile(
    r"""os\.(?:environ\.get|getenv)\(\s*["']([A-Z0-9_]+)["']"""
    r"""|os\.environ\[\s*["']([A-Z0-9_]+)["']\s*\]"""
)


def variaveis_lidas_pelo_codigo():
    arquivos = [
        *RAIZ.glob("trama/**/*.py"),
        *RAIZ.glob("ferramentas/*.py"),
        *RAIZ.glob("experimental/*.py"),
    ]
    nomes = set()
    for arquivo in arquivos:
        for m in _LEITURA.finditer(arquivo.read_text(encoding="utf-8")):
            nomes.add(m.group(1) or m.group(2))
    return nomes


def isolar():
    for nome in variaveis_lidas_pelo_codigo() - PRESERVADAS:
        os.environ.pop(nome, None)
