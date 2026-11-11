"""
migracoes/001_ledger_contribuicoes.py - Introduz pessoas_legado e
contribuicoes: o ledger de contribuicoes de voz por reuniao+cluster. Ver ADR
0001 (identificacao por cluster) e ADR 0006 (migracoes versionadas).

Escrita depois que a mudanca ja tinha sido aplicada a mao, sem controle de
versao, em pelo menos um banco de producao (commit cc0cc9a). Por isso
reconhece QUATRO estados possiveis, nao dois:

  NOVO          - nem "pessoas" existe. Banco vazio (maquina nova). So cria
                  o schema; nao ha nada para congelar.

  PRE_LEDGER    - "pessoas" existe, "pessoas_legado" e "contribuicoes" nao.
                  E o schema anterior a este ADR. O conteudo atual de
                  "pessoas" precisa ser CONGELADO em "pessoas_legado" antes
                  que o ledger passe a alimentar "pessoas" por recalculo -
                  senao a proxima contribuicao apagaria o que existia.

  JA_MIGRADO    - "pessoas_legado" E "contribuicoes" ja existem. O banco
                  passou pela migracao ad-hoc do commit cc0cc9a antes de
                  existir schema_version. NAO congela de novo: pessoas_legado
                  ja tem o congelamento feito naquela migracao, e repeti-lo
                  dobraria o peso de todo mundo. So garante que o schema
                  bate (CREATE TABLE IF NOT EXISTS e no-op aqui) e deixa o
                  motor carimbar a versao.

  INCONSISTENTE - "pessoas_legado" OU "contribuicoes" existe, mas nao as
                  duas. So acontece se uma migracao antiga (sem a transacao
                  explicita que este motor agora usa) foi interrompida no
                  meio - por exemplo, um processo morto entre criar uma
                  tabela e a outra. Nao ha heuristica segura para completar
                  isso sozinho: um congelamento parcial ou repetido corrompe
                  o peso dos perfis. Aborta.

A deteccao e por TABELA, nunca por numero de versao (schema_version pode nem
existir ainda) nem por flag: e a unica fonte de verdade que sobrevive a um
banco copiado, restaurado de backup ou aberto por uma versao antiga do
codigo.
"""

from datetime import datetime, timezone

from ._util import EstadoBancoInconsistente, tabela_existe

NOVO = "novo"
PRE_LEDGER = "pre_ledger"
JA_MIGRADO = "ja_migrado"
INCONSISTENTE = "inconsistente"


def _detectar_estado(con):
    tem_legado = tabela_existe(con, "pessoas_legado")
    tem_contribuicoes = tabela_existe(con, "contribuicoes")

    if tem_legado and tem_contribuicoes:
        return JA_MIGRADO
    if tem_legado or tem_contribuicoes:
        return INCONSISTENTE
    if tabela_existe(con, "pessoas"):
        return PRE_LEDGER
    return NOVO


def _congelar_legado(con):
    """
    Congela o estado ATUAL de "pessoas" em "pessoas_legado", de uma vez. So
    roda no estado PRE_LEDGER (ver deteccao acima). Nao inventa procedencia:
    o schema antigo so guardava a media agregada, entao nao ha como saber
    quanto de cada pessoa veio de qual reuniao. Este congelamento vira a base
    IMUTAVEL sobre a qual as contribuicoes futuras (rastreadas por
    reuniao+cluster) sao somadas e podem ser corrigidas sem tocar no que veio
    de antes.
    """
    linhas = con.execute("SELECT nome, embedding, peso FROM pessoas").fetchall()
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for nome, emb, peso in linhas:
        con.execute(
            "INSERT OR IGNORE INTO pessoas_legado "
            "(nome, embedding, peso, migrado_em) VALUES (?,?,?,?)",
            (nome, emb, peso, agora),
        )


def aplicar(con):
    estado = _detectar_estado(con)

    if estado == INCONSISTENTE:
        existente = "pessoas_legado" if tabela_existe(con, "pessoas_legado") else "contribuicoes"
        faltando = "contribuicoes" if existente == "pessoas_legado" else "pessoas_legado"
        raise EstadoBancoInconsistente(
            f"O banco tem a tabela '{existente}' mas nao tem '{faltando}'. "
            "Isso indica uma migracao antiga interrompida no meio, de antes "
            "deste mecanismo de migracoes (sem transacao explicita para "
            "proteger contra isso). Esta migracao NAO vai tentar adivinhar "
            "como completar o schema sozinha, porque um congelamento "
            "parcial ou repetido de 'pessoas' em 'pessoas_legado' corrompe "
            "o peso dos perfis de voz de um jeito dificil de perceber "
            "depois. Restaure um backup de antes desta tentativa "
            "(vozes.db.bak-pre-contribuicoes-* ou vozes.db.bak-v*-*) e "
            "investigue manualmente antes de rodar de novo."
        )

    con.execute("""
        CREATE TABLE IF NOT EXISTS pessoas (
            nome        TEXT PRIMARY KEY,
            embedding   BLOB NOT NULL,
            peso        REAL NOT NULL,
            atualizado  TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS pessoas_legado (
            nome        TEXT PRIMARY KEY,
            embedding   BLOB NOT NULL,
            peso        REAL NOT NULL,
            migrado_em  TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS contribuicoes (
            reuniao_id  TEXT NOT NULL,
            cluster     TEXT NOT NULL,
            pessoa      TEXT NOT NULL,
            embedding   BLOB NOT NULL,
            peso        REAL NOT NULL,
            versao      INTEGER NOT NULL,
            atualizado  TEXT NOT NULL,
            PRIMARY KEY (reuniao_id, cluster)
        )
    """)

    if estado == PRE_LEDGER:
        _congelar_legado(con)
    # NOVO: as tabelas acima acabaram de ser criadas vazias - nada a congelar.
    # JA_MIGRADO: pessoas_legado e contribuicoes ja tinham os dados certos
    # antes desta migracao rodar; so faltava o carimbo de versao.
