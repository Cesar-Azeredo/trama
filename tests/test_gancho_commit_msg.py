"""
tests/test_gancho_commit_msg.py - ganchos/commit-msg tira coautor e
assinatura da mensagem de commit, e nada mais.

Uso:
    python tests/test_gancho_commit_msg.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GANCHO = RAIZ / "ganchos" / "commit-msg"


def _aplicar(mensagem):
    with tempfile.TemporaryDirectory(prefix="trama-test-gancho-") as pasta:
        arquivo = Path(pasta) / "COMMIT_EDITMSG"
        arquivo.write_text(mensagem, encoding="utf-8")
        subprocess.run([str(GANCHO), str(arquivo)], check=True)
        return arquivo.read_text(encoding="utf-8")


def test_remove_coautor_e_assinatura():
    msg = (
        "fix: titulo\n\ncorpo do commit\n\n"
        "Generated with [Claude Code](https://claude.com/claude-code)\n\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n"
    )
    assert _aplicar(msg) == "fix: titulo\n\ncorpo do commit\n"


def test_ignora_maiuscula_e_espaco_no_inicio():
    msg = "feat: x\n\n  co-authored-by: Alguem <a@b.c>\nCO-AUTHORED-BY: Outro <c@d.e>\n"
    assert _aplicar(msg) == "feat: x\n"


def test_mensagem_sem_coautor_fica_igual():
    msg = "docs: titulo\n\nlinha 1\n\nlinha 2 cita co-authored no meio\n"
    assert _aplicar(msg) == msg


def test_linha_que_cita_a_assinatura_no_meio_fica():
    msg = (
        "chore: gancho\n\nremove Co-Authored-By e Generated with Claude Code da\n"
        "mensagem.\n\n\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)\n"
    )
    assert _aplicar(msg) == (
        "chore: gancho\n\nremove Co-Authored-By e Generated with Claude Code da\nmensagem.\n"
    )


def test_mensagem_so_com_coautor_fica_vazia():
    # git aborta o commit com mensagem vazia - comportamento desejado
    assert _aplicar("Co-Authored-By: Claude <noreply@anthropic.com>\n") == ""


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
