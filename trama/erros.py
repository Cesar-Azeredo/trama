"""
trama/erros.py - Erro e aviso que a pessoa le: codigo estavel + parametros.

O texto em cada idioma mora no catalogo do frontend
(frontend/src/i18n/pt/erros.ts e en/erros.ts); o servidor nunca manda frase
pronta. Resposta de erro da API: {"detail": {"codigo": ..., "parametros":
{...}}}. Aviso gravado no .json ou devolvido numa resposta: o mesmo par.
tests/test_codigos_de_erro.py confere que todo codigo usado aqui existe nos
dois catalogos.

Codigo: snake_case em portugues, sem acento (como todo identificador).
Parametro: so dado (numero, nome de termo, id) - nunca texto em portugues
montado aqui.
"""


class ErroDeUsuario(ValueError):
    """Base das excecoes de dominio que viram resposta para a pessoa."""

    def __init__(self, codigo, **parametros):
        super().__init__(codigo)
        self.codigo = codigo
        self.parametros = parametros

    def para_resposta(self):
        return {"codigo": self.codigo, "parametros": self.parametros}


def aviso(codigo, **parametros):
    """Aviso (nao erro) no mesmo formato, para gravar no .json ou devolver."""
    return {"codigo": codigo, "parametros": parametros}
