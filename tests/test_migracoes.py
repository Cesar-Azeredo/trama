"""
tests/test_migracoes.py - Motor de migracoes versionadas (migracoes/) e a
migracao 001 (ledger de contribuicoes). Ver ADR 0006.

So usa sqlite3 puro - nenhum stub de torch/pyannote e necessario, porque o
motor de migracoes nao importa nucleo.py (ver docstring de migracoes/__init__.py
para o porque disso).

Uso:
    python tests/test_migracoes.py
"""

import shutil
import sqlite3
import sys
import tempfile
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import _ambiente  # noqa: E402

_ambiente.isolar()

from trama import migracoes  # noqa: E402
from trama.migracoes._util import EstadoBancoInconsistente  # noqa: E402

# --------------------------------------------------------------------------
# infraestrutura de teste
# --------------------------------------------------------------------------


def _banco_temporario():
    return Path(tempfile.mkdtemp(prefix="rec-meet-test-migracoes-"))


def _tabelas(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _versao(con):
    row = con.execute("SELECT versao FROM schema_version").fetchone()
    return row[0] if row else None


def _criar_schema_pre_ledger(db, pessoas):
    """Estado B: so a tabela 'pessoas', como era antes do ADR 0006."""
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE pessoas (
        nome TEXT PRIMARY KEY, embedding BLOB NOT NULL,
        peso REAL NOT NULL, atualizado TEXT NOT NULL)""")
    for nome, peso in pessoas.items():
        con.execute(
            "INSERT INTO pessoas VALUES (?,?,?,?)",
            (nome, b"emb", peso, "2026-01-01T00:00:00+00:00"),
        )
    con.commit()
    con.close()


def _criar_schema_ja_migrado(db, pessoas_atual, pessoas_legado, contribs):
    """
    Estado C: o schema final do ledger ja existe (pessoas, pessoas_legado,
    contribuicoes com dados), mas sem schema_version - exatamente o que o
    commit cc0cc9a produziu antes deste mecanismo existir.
    """
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE pessoas (
        nome TEXT PRIMARY KEY, embedding BLOB NOT NULL,
        peso REAL NOT NULL, atualizado TEXT NOT NULL)""")
    con.execute("""CREATE TABLE pessoas_legado (
        nome TEXT PRIMARY KEY, embedding BLOB NOT NULL,
        peso REAL NOT NULL, migrado_em TEXT NOT NULL)""")
    con.execute("""CREATE TABLE contribuicoes (
        reuniao_id TEXT NOT NULL, cluster TEXT NOT NULL, pessoa TEXT NOT NULL,
        embedding BLOB NOT NULL, peso REAL NOT NULL, versao INTEGER NOT NULL,
        atualizado TEXT NOT NULL, PRIMARY KEY (reuniao_id, cluster))""")
    for nome, peso in pessoas_atual.items():
        con.execute(
            "INSERT INTO pessoas VALUES (?,?,?,?)",
            (nome, b"emb", peso, "2026-01-01T00:00:00+00:00"),
        )
    for nome, peso in pessoas_legado.items():
        con.execute(
            "INSERT INTO pessoas_legado VALUES (?,?,?,?)",
            (nome, b"emb", peso, "2026-01-01T00:00:00+00:00"),
        )
    for reuniao_id, cluster, pessoa, peso in contribs:
        con.execute(
            "INSERT INTO contribuicoes VALUES (?,?,?,?,?,?,?)",
            (reuniao_id, cluster, pessoa, b"emb", peso, 1, "2026-01-01T00:00:00+00:00"),
        )
    con.commit()
    con.close()


def _instalar_migracao_falha(numero=99):
    """
    Registra uma migracao FALSA que cria uma tabela e depois levanta um
    erro, para testar a atomicidade do motor sem depender da migracao 001
    real. Retorna uma funcao de restauracao - chamar sempre num finally.
    """
    registro_original = migracoes.REGISTRO
    carregar_original = migracoes._carregar

    modulo_falso = types.SimpleNamespace()

    def aplicar_com_falha(con):
        con.execute("CREATE TABLE tabela_da_migracao_que_falhou (x INTEGER)")
        raise RuntimeError("falha simulada no meio da migracao")

    modulo_falso.aplicar = aplicar_com_falha

    def carregar_falso(nome_arquivo):
        if nome_arquivo == "099_falha_simulada":
            return modulo_falso
        return carregar_original(nome_arquivo)

    migracoes.REGISTRO = registro_original + [(numero, "099_falha_simulada")]
    migracoes._carregar = carregar_falso

    def restaurar():
        migracoes.REGISTRO = registro_original
        migracoes._carregar = carregar_original

    return restaurar


# ==========================================================================
# os tres estados chegam ao mesmo schema final
# ==========================================================================


def test_estado_novo_cria_schema_completo_do_zero():
    """Banco vazio (maquina nova) tem de terminar com as 4 tabelas e
    versao 1, sem exigir nenhum arquivo pre-existente."""
    pasta = _banco_temporario()
    try:
        db = pasta / "novo.db"
        con = sqlite3.connect(db)
        migracoes.aplicar_pendentes(con, db)
        assert _tabelas(con) == {"pessoas", "pessoas_legado", "contribuicoes", "schema_version"}
        assert _versao(con) == 1
        con.close()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_estado_pre_ledger_congela_pessoas_em_pessoas_legado():
    """
    Banco com so a tabela 'pessoas' (schema anterior ao ADR 0006) tem que
    congelar o peso existente em pessoas_legado, SEM alterar o valor em
    'pessoas' - e a garantia que abre caminho para o proximo recalculo
    (legado + contribuicoes) nao perder nem inflar o que ja existia.
    """
    pasta = _banco_temporario()
    try:
        db = pasta / "pre_ledger.db"
        _criar_schema_pre_ledger(db, {"Ramiro": 100.0, "Amanda": 40.0})

        con = sqlite3.connect(db)
        migracoes.aplicar_pendentes(con, db)

        assert _tabelas(con) == {"pessoas", "pessoas_legado", "contribuicoes", "schema_version"}
        assert _versao(con) == 1
        legado = dict(con.execute("SELECT nome, peso FROM pessoas_legado"))
        atual = dict(con.execute("SELECT nome, peso FROM pessoas"))
        assert legado == {"Ramiro": 100.0, "Amanda": 40.0}
        assert atual == {"Ramiro": 100.0, "Amanda": 40.0}, (
            "a migracao alterou o peso ja existente em 'pessoas'"
        )
        con.close()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_estado_ja_migrado_preserva_pesos_identicos():
    """
    O TESTE MAIS IMPORTANTE DA SUITE. Um banco no estado C (ja passou pela
    migracao ad-hoc do commit cc0cc9a: pessoas, pessoas_legado e
    contribuicoes ja existem e ja tem os pesos certos) NAO PODE ter
    'pessoas_legado' recongelada. Se recongelasse, o peso de cada pessoa
    dobraria (uma vez como legado, outra vez como a soma legado+contribuicao
    que ja esta em 'pessoas'). Compara os pesos numero a numero, antes e
    depois - nao so "a tabela existe" ou "nao deu erro".
    """
    pasta = _banco_temporario()
    try:
        db = pasta / "ja_migrado.db"
        pessoas_atual = {"Ramiro": 45.5, "Amanda": 22.0}
        pessoas_legado = {"Ramiro": 30.0, "Amanda": 22.0}
        contribs = [("reuniao-1", "S0", "Ramiro", 15.5)]
        _criar_schema_ja_migrado(db, pessoas_atual, pessoas_legado, contribs)

        con = sqlite3.connect(db)
        migracoes.aplicar_pendentes(con, db)

        atual_depois = dict(con.execute("SELECT nome, peso FROM pessoas"))
        legado_depois = dict(con.execute("SELECT nome, peso FROM pessoas_legado"))
        contribs_depois = con.execute(
            "SELECT reuniao_id, cluster, pessoa, peso FROM contribuicoes"
        ).fetchall()

        assert atual_depois == pessoas_atual, (
            f"peso em 'pessoas' mudou: {pessoas_atual} -> {atual_depois}"
        )
        assert legado_depois == pessoas_legado, (
            f"peso em 'pessoas_legado' mudou: {pessoas_legado} -> {legado_depois}"
        )
        assert contribs_depois == [("reuniao-1", "S0", "Ramiro", 15.5)], contribs_depois
        assert _versao(con) == 1
        con.close()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# estado inconsistente
# ==========================================================================


def test_estado_inconsistente_aborta_sem_mexer_no_banco():
    """
    Uma migracao ad-hoc antiga interrompida no meio pode deixar so uma das
    duas tabelas do ledger (aqui, pessoas_legado sem contribuicoes). Isso
    NAO pode cair no ramo PRE_LEDGER (congelaria pessoas em cima de um
    pessoas_legado que ja tem linhas) nem no JA_MIGRADO (contribuicoes nem
    existe). Tem que abortar, sem criar schema_version nem tocar em nenhuma
    tabela existente - o unico efeito aceitavel e o backup de seguranca.
    """
    pasta = _banco_temporario()
    try:
        db = pasta / "inconsistente.db"
        con = sqlite3.connect(db)
        con.execute("""CREATE TABLE pessoas (
            nome TEXT PRIMARY KEY, embedding BLOB, peso REAL, atualizado TEXT)""")
        con.execute("""CREATE TABLE pessoas_legado (
            nome TEXT PRIMARY KEY, embedding BLOB, peso REAL, migrado_em TEXT)""")
        con.execute("INSERT INTO pessoas VALUES ('Ramiro', ?, 45.5, 'x')", (b"e",))
        con.commit()
        con.close()

        con = sqlite3.connect(db)
        try:
            migracoes.aplicar_pendentes(con, db)
            assert False, "deveria ter levantado EstadoBancoInconsistente"
        except EstadoBancoInconsistente as e:
            assert "pessoas_legado" in str(e) and "contribuicoes" in str(e), e

        assert _tabelas(con) == {"pessoas", "pessoas_legado"}, (
            "abortar nao pode deixar schema_version nem outra tabela para tras"
        )
        peso = con.execute("SELECT peso FROM pessoas WHERE nome='Ramiro'").fetchone()[0]
        assert peso == 45.5, "abortar nao pode alterar dado existente"
        con.close()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_estado_inconsistente_no_outro_sentido_tambem_aborta():
    """Mesmo caso, com as tabelas invertidas: contribuicoes existe mas
    pessoas_legado nao. A deteccao e por par de tabelas, nao por uma so."""
    pasta = _banco_temporario()
    try:
        db = pasta / "inconsistente2.db"
        con = sqlite3.connect(db)
        con.execute("""CREATE TABLE pessoas (
            nome TEXT PRIMARY KEY, embedding BLOB, peso REAL, atualizado TEXT)""")
        con.execute("""CREATE TABLE contribuicoes (
            reuniao_id TEXT, cluster TEXT, pessoa TEXT, embedding BLOB,
            peso REAL, versao INTEGER, atualizado TEXT,
            PRIMARY KEY (reuniao_id, cluster))""")
        con.commit()
        con.close()

        con = sqlite3.connect(db)
        try:
            migracoes.aplicar_pendentes(con, db)
            assert False, "deveria ter levantado EstadoBancoInconsistente"
        except EstadoBancoInconsistente as e:
            assert "pessoas_legado" in str(e) and "contribuicoes" in str(e), e
        con.close()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================
# idempotencia, atomicidade e ruido de backup
# ==========================================================================


def test_reaplicar_migracoes_e_no_op_na_segunda_vez():
    """Rodar aplicar_pendentes duas vezes seguidas (como duas execucoes do
    pipeline.py em sequencia fariam, via connect()) nao pode mudar nada na
    segunda - nem versao, nem dado, nem gerar erro."""
    pasta = _banco_temporario()
    try:
        db = pasta / "banco.db"
        _criar_schema_pre_ledger(db, {"Ramiro": 100.0})

        con = sqlite3.connect(db)
        migracoes.aplicar_pendentes(con, db)
        estado_1 = dict(con.execute("SELECT nome, peso FROM pessoas_legado"))
        con.close()

        con = sqlite3.connect(db)
        migracoes.aplicar_pendentes(con, db)
        estado_2 = dict(con.execute("SELECT nome, peso FROM pessoas_legado"))
        assert estado_1 == estado_2 == {"Ramiro": 100.0}
        assert _versao(con) == 1
        con.close()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_migracao_pre_ledger_gera_backup_com_novo_padrao_de_nome():
    """
    Substitui o teste que existia em test_review.py para o backup da
    migracao ad-hoc (vozes.db.bak-pre-contribuicoes-*). O padrao mudou para
    vozes.db.bak-v<versao-antes>-<timestamp-UTC> (ADR 0006) - este teste
    fixa esse contrato para quem for restaurar um backup manualmente.
    """
    pasta = _banco_temporario()
    try:
        db = pasta / "vozes_legado.db"
        _criar_schema_pre_ledger(db, {"Rolando": 100.0})

        con = sqlite3.connect(db)
        migracoes.aplicar_pendentes(con, db)
        con.close()

        backups = list(pasta.glob("vozes_legado.db.bak-v0-*"))
        assert backups, "migracao rodou sem deixar backup no padrao novo"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_banco_ja_na_versao_mais_alta_nao_gera_backup():
    """
    REGRESSAO que motivou o ADR 0006: hoje todo `connect()` num banco ja
    migrado gera ruido. So deve existir UM backup (o da migracao real), nao
    um por conexao subsequente.
    """
    pasta = _banco_temporario()
    try:
        db = pasta / "banco.db"
        _criar_schema_pre_ledger(db, {"Ramiro": 100.0})

        con = sqlite3.connect(db)
        migracoes.aplicar_pendentes(con, db)
        con.close()
        backups_apos_migrar = list(pasta.glob("*.bak-*"))
        assert len(backups_apos_migrar) == 1, backups_apos_migrar

        for _ in range(3):
            con = sqlite3.connect(db)
            migracoes.aplicar_pendentes(con, db)
            con.close()

        backups_finais = list(pasta.glob("*.bak-*"))
        assert backups_finais == backups_apos_migrar, (
            "reabrir um banco ja atualizado gerou backup novo"
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_migracao_que_falha_no_meio_nao_avanca_versao_nem_deixa_tabela():
    """
    Se uma migracao levantar um erro depois de ja ter criado alguma tabela
    (DDL parcial), o BEGIN explicito do motor tem que reverter TUDO daquela
    migracao - inclusive a tabela criada - e a versao nao pode avancar.
    Sem isso, uma migracao futura que falhe no meio deixaria o banco num
    schema que nenhuma versao registrada reconhece.
    """
    pasta = _banco_temporario()
    restaurar = _instalar_migracao_falha()
    try:
        db = pasta / "banco.db"
        con = sqlite3.connect(db)
        try:
            migracoes.aplicar_pendentes(con, db)
            assert False, "deveria ter propagado o erro da migracao falsa"
        except RuntimeError as e:
            assert "falha simulada" in str(e)

        assert "tabela_da_migracao_que_falhou" not in _tabelas(con), (
            "DDL da migracao que falhou nao foi revertido"
        )
        assert _versao(con) == 1, "versao avancou apesar da migracao seguinte ter falhado"
        con.close()
    finally:
        restaurar()
        shutil.rmtree(pasta, ignore_errors=True)


# ==========================================================================


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
