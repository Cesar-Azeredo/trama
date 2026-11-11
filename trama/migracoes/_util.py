"""
migracoes/_util.py - utilidades compartilhadas entre o motor de migracoes
(migracoes/__init__.py) e os arquivos de migracao individuais.

Isolado num modulo proprio para que uma migracao possa importar so isto, sem
importar o motor (__init__.py) - e o motor quem importa as migracoes, nunca
o contrario.
"""


def tabela_existe(con, nome):
    return (
        con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone()
        is not None
    )


class EstadoBancoInconsistente(RuntimeError):
    """
    Uma migracao levanta isto quando o banco esta num estado intermediario
    que nenhuma heuristica deveria tentar consertar sozinha - por exemplo,
    uma tabela nova sem a tabela irma que deveria ter sido criada na mesma
    migracao. E sinal de uma migracao antiga interrompida no meio, de antes
    deste mecanismo (que agora impede isso com transacao explicita).
    """
