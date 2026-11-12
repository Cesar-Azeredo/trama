"""
tests/rodar.py - Roda todas as suites (tests/test_*.py), cada uma no seu
processo, como a CI e o dia a dia, e diz SEMPRE o nome e o erro de cada
teste que falhar - nunca so o total. Um "424/425" sem nome nao e
informacao: foi assim que um teste instavel escapou num commit.

Sai com codigo 1 se qualquer teste falhar ou qualquer suite cair sem
relatorio (erro de import, por exemplo), para o commit poder depender
disto:

    python tests/rodar.py && git commit ...

Uso:
    python tests/rodar.py            # todas
    python tests/rodar.py pipeline   # so as suites com "pipeline" no nome
"""

import re
import subprocess
import sys
import time
from pathlib import Path

PASTA = Path(__file__).resolve().parent
_TOTAL = re.compile(r"^(\d+)/(\d+) passaram\s*$")
_FALHA = re.compile(r"^\s*(?:\x1b\[\d+m)?(FALHOU|ERRO)(?:\x1b\[0m)?\s+(\S+)")
_COR = re.compile(r"\x1b\[\d+m")


def _falhas(saida):
    """[(nome, erro)] dos testes FALHOU/ERRO, com as linhas recuadas que o
    executor de cada suite imprime embaixo (o erro)."""
    linhas = saida.splitlines()
    falhas = []
    for i, linha in enumerate(linhas):
        m = _FALHA.match(linha)
        if not m:
            continue
        erro = []
        for seguinte in linhas[i + 1 :]:
            if not seguinte.startswith("        ") or _FALHA.match(seguinte):
                break
            erro.append(_COR.sub("", seguinte).strip())
        falhas.append((m.group(2), "\n".join(erro) or m.group(1)))
    return falhas


def rodar(filtro=""):
    suites = sorted(p for p in PASTA.glob("test_*.py") if filtro in p.stem)
    total_ok = total = 0
    problemas = []  # (suite, nome, erro)
    inicio = time.monotonic()
    for suite in suites:
        r = subprocess.run(
            [sys.executable, str(suite)],
            cwd=PASTA.parent,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        saida = r.stdout + r.stderr
        linhas_total = [m for m in map(_TOTAL.match, saida.splitlines()) if m]
        falhas = _falhas(saida)
        if linhas_total:
            ok, n = map(int, linhas_total[-1].groups())
        else:
            ok, n = 0, 1
        total_ok, total = total_ok + ok, total + n
        for nome, erro in falhas:
            problemas.append((suite.name, nome, erro))
        if r.returncode != 0 and not falhas:
            # caiu sem dizer qual teste: mostra o fim da saida
            problemas.append((suite.name, "(a suite inteira)", "\n".join(saida.splitlines()[-25:])))
        marca = "ok " if r.returncode == 0 and ok == n else "XX "
        print(f"{marca} {suite.name:<36} {ok}/{n}", flush=True)

    print(f"\n{total_ok}/{total} em {len(suites)} suites, {time.monotonic() - inicio:.0f} s")
    if problemas:
        print(f"\n{len(problemas)} FALHA(S):")
        for suite, nome, erro in problemas:
            print(f"\n- {suite} :: {nome}")
            for linha in erro.splitlines():
                print(f"    {linha}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(rodar(sys.argv[1] if len(sys.argv) > 1 else ""))
