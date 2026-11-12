"""
servidor/origem.py - Quem pode falar com o servidor (ADR 0030).

Sem autenticacao, a fronteira e "so o proprio app fala com o servidor". O
bind em 127.0.0.1 barra outra maquina, mas nao uma pagina de outro site
aberta no mesmo navegador. Duas checagens, em toda requisicao:

  Host    tem de ser 127.0.0.1 ou localhost, na porta do servidor. Fecha o
          DNS rebinding: uma pagina que troca o proprio dominio para
          127.0.0.1 continua mandando o NOME dela no Host.
  Origin  ausente (o navegador nao manda em GET da mesma origem, nem a
          linha de comando), ou 127.0.0.1/localhost na porta do frontend
          (o Vite, que encaminha /api) ou na do proprio servidor. Fecha o
          upload multipart, que e pedido simples, sem preflight.

O Vite encaminha com changeOrigin (vite.config.ts): o Host chega como
127.0.0.1:<porta do servidor>, e o Origin continua o da pagina.
"""

import os
from urllib.parse import urlsplit

NOMES_LOCAIS = ("127.0.0.1", "localhost")
PORTA_PADRAO = 8000
PORTA_FRONTEND_PADRAO = 5173


def _porta(bruto, padrao):
    try:
        valor = int(bruto if bruto is not None else padrao)
    except ValueError:
        return padrao
    return valor if 1 <= valor <= 65535 else padrao


# Nomes literais: tests/_ambiente.py acha as variaveis lidas pelo codigo
# procurando os.environ.get("NOME").
def porta_do_servidor():
    return _porta(os.environ.get("TRAMA_PORTA"), PORTA_PADRAO)


def porta_do_frontend():
    return _porta(os.environ.get("TRAMA_PORTA_FRONTEND"), PORTA_FRONTEND_PADRAO)


def _host_e_porta(valor, porta_padrao):
    """("localhost", 8000) de "localhost:8000"; None se nao der para ler."""
    try:
        partes = urlsplit(f"//{valor}")
        return (partes.hostname or "").lower(), partes.port or porta_padrao
    except ValueError:
        return None


def motivo_de_recusa(host, origin, porta_servidor=None, porta_frontend=None):
    """None se a requisicao pode passar; senao o codigo de erro (trama/erros.py)."""
    porta_servidor = porta_servidor or porta_do_servidor()
    porta_frontend = porta_frontend or porta_do_frontend()

    lido = _host_e_porta(host or "", 80)
    if lido is None or lido[0] not in NOMES_LOCAIS or lido[1] != porta_servidor:
        return "host_recusado"

    if origin is None:
        return None
    try:
        partes = urlsplit(origin)
        nome, porta = (partes.hostname or "").lower(), partes.port
    except ValueError:
        return "origem_recusada"
    if (
        partes.scheme != "http"
        or nome not in NOMES_LOCAIS
        or porta not in (porta_frontend, porta_servidor)
    ):
        return "origem_recusada"
    return None
