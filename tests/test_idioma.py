"""
tests/test_idioma.py - Idioma da linha de comando e do .txt em disco
(trama/idioma.py, trama/textos.py): a ordem de escolha (TRAMA_IDIOMA, o
idioma do sistema, ingles) e o catalogo nos dois idiomas.

Uso:
    python tests/test_idioma.py
"""

import os
import re
import string
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

import _ambiente  # noqa: E402

_ambiente.isolar()

from servidor_apoio import rodar_suite  # noqa: E402

from trama import idioma  # noqa: E402
from trama.textos import TEXTOS  # noqa: E402

LOCALE = ("TRAMA_IDIOMA", "LC_ALL", "LC_MESSAGES", "LANG")


class _Ambiente:
    """Troca as variaveis de idioma so dentro do bloco."""

    def __init__(self, **valores):
        self.valores = valores

    def __enter__(self):
        self.antes = {k: os.environ.get(k) for k in LOCALE}
        for k in LOCALE:
            os.environ.pop(k, None)
        os.environ.update(self.valores)

    def __exit__(self, *_):
        for k, v in self.antes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _campos(texto):
    return {campo.split(":")[0] for _, campo, _, _ in string.Formatter().parse(texto) if campo}


def test_catalogo_tem_as_mesmas_chaves_e_os_mesmos_parametros():
    assert set(TEXTOS["pt"]) == set(TEXTOS["en"])
    for chave, texto in TEXTOS["pt"].items():
        assert _campos(texto) == _campos(TEXTOS["en"][chave]), chave


def test_colunas_da_dinamica_tem_oito_titulos_que_cabem():
    larguras = (14, 8, 6, 7, 7, 8, 7, 7)
    for lingua in idioma.IDIOMAS:
        titulos = TEXTOS[lingua]["colunas_dinamica"].split("|")
        assert len(titulos) == 8, lingua
        assert all(len(t) <= w for t, w in zip(titulos, larguras)), (lingua, titulos)


def test_ordem_de_escolha():
    with _Ambiente(TRAMA_IDIOMA="en", LANG="pt_BR.UTF-8"):
        assert idioma.atual() == "en", "TRAMA_IDIOMA ganha do sistema"
    with _Ambiente(TRAMA_IDIOMA="pt-BR"):
        assert idioma.atual() == "pt"
    with _Ambiente(LANG="pt_BR.UTF-8"):
        assert idioma.atual() == "pt", "sem TRAMA_IDIOMA, o sistema"
    with _Ambiente(LC_ALL="en_US.UTF-8", LANG="pt_BR.UTF-8"):
        assert idioma.atual() == "en", "LC_ALL antes de LANG"
    with _Ambiente(LANG="es_ES.UTF-8"):
        assert idioma.atual() == "en", "outro idioma: ingles, como a tela"
    with _Ambiente(LANG="C"):
        assert idioma.atual() == "en"
    with _Ambiente():
        assert idioma.atual() == "en"


def test_t_preenche_parametros_e_nao_formata_texto_sem_parametro():
    assert idioma.t("faixa_entre", "pt", min=4, max=5) == " - entre 4 e 5 falantes"
    assert idioma.t("faixa_entre", "en", min=4, max=5) == " - between 4 and 5 speakers"
    # valor com chaves (texto do glossario, por exemplo) nao quebra nada
    assert "{x}" in idioma.t("termos_sem_uso", "pt", n=1, lista="{x}")


def test_nenhum_texto_portugues_sem_acento_onde_precisa():
    """O catalogo pt e texto que alguem le: acentuado (CLAUDE.md)."""
    sem_acento = re.compile(r"(?<![.\w])(nao|voce|reuniao|transcricao|correcao|audio|ja|sera)\b")
    for chave, texto in TEXTOS["pt"].items():
        assert not sem_acento.search(texto.lower()), (chave, texto)


def test_trama_revisar_escreve_em_ingles_com_trama_idioma_en():
    ambiente = {**os.environ, "TRAMA_IDIOMA": "en"}
    r = subprocess.run(
        [sys.executable, "-m", "trama.cli.revisar", "--help"],
        cwd=str(RAIZ),
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert "Fixes the text but doesn't update the voice profiles" in r.stdout, r.stdout
    ambiente["TRAMA_IDIOMA"] = "pt"
    r = subprocess.run(
        [sys.executable, "-m", "trama.cli.revisar", "--help"],
        cwd=str(RAIZ),
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "Corrige o texto mas não atualiza os perfis de voz" in r.stdout, r.stdout


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
