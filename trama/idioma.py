"""
idioma.py - Idioma do que a linha de comando escreve (progresso do
pipeline, trama-revisar, trama-verificar) e do .txt gravado em disco.

Ordem de escolha:
  1. TRAMA_IDIOMA ("pt" ou "en"; aceita "pt-BR", "en_US"...). Quando a tela
     dispara o processamento, o servidor passa o idioma da interface por
     aqui (servidor/processamento.py).
  2. O idioma do sistema: LC_ALL, LC_MESSAGES, LANG, nessa ordem (a ordem
     do POSIX).
  3. Mesma regra da tela (frontend/src/i18n/idioma.ts): portugues se o
     idioma comeca com "pt", ingles em qualquer outro caso - inclusive
     sem idioma nenhum.

Nao confundir com o --idioma do trama-processar, que e o idioma da FALA
para o Whisper. Os textos moram em trama/textos.py.
"""

import os

IDIOMAS = ("pt", "en")


def _de(valor):
    """ "pt" | "en" de um valor de idioma ou locale; None se vazio."""
    valor = (valor or "").strip().lower()
    if not valor or valor in ("c", "posix"):
        return None
    return "pt" if valor.startswith("pt") else "en"


def atual():
    escolhido = _de(os.environ.get("TRAMA_IDIOMA"))
    if escolhido:
        return escolhido
    for valor in (
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
    ):
        do_sistema = _de(valor)
        if do_sistema:
            return do_sistema
    return "en"


def t(chave, idioma=None, **parametros):
    """O texto `chave` no idioma (o atual, sem argumento), com os
    parametros no lugar."""
    from trama.textos import TEXTOS

    texto = TEXTOS[idioma or atual()][chave]
    return texto.format(**parametros) if parametros else texto
