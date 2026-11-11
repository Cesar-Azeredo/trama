"""
migracoes/__init__.py - motor de migracoes versionadas do vozes.db.

Ver ADR 0006. Cada arquivo migracoes/NNN_descricao.py expoe uma funcao
aplicar(con) e e registrado em REGISTRO abaixo, na ordem em que deve rodar.
Os nomes de arquivo comecam com digito (001_..., 002_...) para ordenar bem
no `ls`, o que os torna identificadores Python invalidos - por isso o
carregamento usa importlib.import_module por string, no lugar de um `import`
comum (a mesma tecnica que o Django usa para migrations).

O motor:

  1. Le a versao atual em schema_version.versao (0 se a tabela nao existe -
     banco anterior a este mecanismo, seja novo ou ja com dados de antes).
  2. Se nenhuma migracao registrada tem numero maior que a versao atual, nao
     faz nada: nenhum backup, nenhuma mensagem. E o caso comum (banco ja
     atualizado) e roda em toda abertura de conexao.
  3. Senao, faz UM backup do banco inteiro (nao um por migracao) e aplica
     cada migracao pendente, em ordem, dentro de uma transacao propria (BEGIN
     explicito - sem isso o driver sqlite3 do Python nao garante que um
     CREATE TABLE seja revertido por um rollback() depois de um erro): ou a
     migracao inteira entra e a versao avanca, ou nada muda e o erro sobe
     para quem chamou connect().

Fica num pacote proprio, fora de nucleo.py, porque nucleo.py importa
pyannote.audio/torch no nivel de modulo - um teste do motor de migracoes
precisaria dos stubs pesados de ML so para testar leitura de versao e
transacao. Isolado aqui, o motor e os arquivos de migracao sao testaveis com
sqlite3 puro (ver tests/test_migracoes.py).
"""

import importlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ._util import tabela_existe

REGISTRO = [
    (1, "001_ledger_contribuicoes"),
]


def _carregar(nome_arquivo):
    return importlib.import_module(f"{__name__}.{nome_arquivo}")


def _ler_versao(con):
    """
    Leitura pura, sem criar nem alterar nada. Precisa rodar ANTES de decidir
    se ha migracao pendente, porque essa decisao e o que decide se um backup
    vai ser feito - criar schema_version aqui ja seria uma mutacao antes do
    backup.
    """
    if not tabela_existe(con, "schema_version"):
        return 0
    linha = con.execute("SELECT versao FROM schema_version").fetchone()
    return linha[0] if linha else 0


def _bootstrap_schema_version(con, versao):
    """
    Sem commit proprio: roda dentro da mesma transacao (BEGIN) da primeira
    migracao pendente, para que um erro nela desfaca tambem a criacao desta
    tabela. Um banco que abortou (ex: estado INCONSISTENTE) nao pode ficar
    com uma schema_version nova sozinha - isso seria uma mutacao permanente
    num banco que a migracao recusou a tocar."""
    con.execute("CREATE TABLE IF NOT EXISTS schema_version (versao INTEGER NOT NULL)")
    if con.execute("SELECT 1 FROM schema_version").fetchone() is None:
        con.execute("INSERT INTO schema_version (versao) VALUES (?)", (versao,))


def _fazer_backup(caminho_db, versao_atual):
    """
    Uma copia do banco por EXECUCAO (nao por migracao), e so quando ha algo
    de fato para aplicar. sqlite3.connect() cria o arquivo na hora, mesmo
    vazio (tamanho 0 byte) - por isso o tamanho, nao so a existencia, decide
    se ha algo real para proteger. Sem essa checagem, todo `trama-processar`
    numa maquina nova geraria um backup de banco vazio.
    """
    caminho_db = Path(caminho_db)
    if not caminho_db.exists() or caminho_db.stat().st_size == 0:
        return
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = caminho_db.with_name(f"{caminho_db.name}.bak-v{versao_atual}-{carimbo}")
    if not destino.exists():
        shutil.copy2(caminho_db, destino)
        print(f"  [migracoes] backup antes de migrar: {destino}")


def aplicar_pendentes(con, caminho_db):
    versao = _ler_versao(con)
    pendentes = [(numero, arquivo) for numero, arquivo in REGISTRO if numero > versao]
    if not pendentes:
        return

    _fazer_backup(caminho_db, versao)

    for numero, nome_arquivo in sorted(pendentes):
        modulo = _carregar(nome_arquivo)
        con.execute("BEGIN")
        try:
            _bootstrap_schema_version(con, versao)
            modulo.aplicar(con)
            con.execute("UPDATE schema_version SET versao = ?", (numero,))
            con.commit()
        except Exception:
            con.rollback()
            raise
        versao = numero
