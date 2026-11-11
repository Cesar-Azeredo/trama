"""
tests/test_demo.py - Os dados de demonstracao (audios-demo/, gerados por
ferramentas/gerar_demo.py) abrem pelo servidor sem erro e mostram o que a
demonstracao promete: tres reunioes ficticias, duas revisadas e uma a
revisar, perfis de voz aprendidos, e audio indisponivel com o aviso certo.

Roda sobre uma COPIA de audios-demo/ - a revisao e o glossario escrevem em
disco, e os arquivos versionados nao podem mudar por causa de um teste.

Uso:
    python tests/test_demo.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

import servidor_apoio  # noqa: F401 - isola o ambiente e instala os stubs ANTES do projeto
from servidor_apoio import rodar_suite

from trama import nucleo
from trama.servidor import glossario, reunioes, sistema

RAIZ = Path(__file__).resolve().parent.parent
DEMO = RAIZ / "audios-demo"


def _cliente_na_copia():
    from fastapi.testclient import TestClient

    import trama.servidor.app as app_mod

    pasta = Path(tempfile.mkdtemp(prefix="rec-meet-test-demo-"))
    copia = pasta / "audios-demo"
    shutil.copytree(DEMO, copia)
    reunioes.PASTA_AUDIOS = copia
    nucleo.DB_PATH = copia / "vozes-demo.db"
    glossario.CAMINHO = pasta / "termos.txt"
    shutil.copy(RAIZ / "termos.exemplo.txt", glossario.CAMINHO)
    return pasta, TestClient(app_mod.app)


def test_demo_lista_tres_reunioes_ficticias():
    pasta, cliente = _cliente_na_copia()
    try:
        lista = cliente.get("/api/reunioes").json()
        assert [r["id"] for r in lista] == ["reuniao_03", "reuniao_02", "reuniao_01"]
        assert all(r["estado"] == "completa" and r["titulo"] for r in lista), lista
        assert [r["revisada"] for r in lista] == [False, True, True]
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_demo_detalhe_tem_o_que_a_tela_mostra():
    pasta, cliente = _cliente_na_copia()
    try:
        d = cliente.get("/api/reunioes/reuniao_01").json()
        assert d["falas"] and d["eventos"] and d["regioes_sobrepostas"]
        assert d["lacunas_sem_texto"], "a demonstracao mostra uma lacuna"
        assert any(f.get("palavras_baixa_confianca") for f in d["falas"])
        assert any(f.get("palavras_divergentes") for f in d["falas"])
        # reuniao revisada: pista e lacuna com o nome confirmado, nunca o
        # rotulo de maquina de antes da revisao
        marcas = [m for f in d["falas"] for m in f.get("palavras_divergentes") or []]
        marcas += d["lacunas_sem_texto"]
        assert not [m for m in marcas if m["falante"].startswith("DESCONHECIDO")], marcas
        # o glossario de exemplo corrigiu o produto ficticio
        assert any("Painel Órbita" in f["texto"] for f in d["falas"])
        # reuniao 3: voz que nao esta na galeria fica a revisar
        d3 = cliente.get("/api/reunioes/reuniao_03").json()
        nomes = [c["nome"] for c in d3["clusters"].values()]
        assert any(n.startswith("DESCONHECIDO") for n in nomes), nomes
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_demo_tem_perfis_de_voz_e_nenhum_caminho_da_maquina():
    pasta, cliente = _cliente_na_copia()
    try:
        nomes = [p["nome"] for p in cliente.get("/api/pessoas").json()]
        assert nomes and "Sofia" not in nomes, nomes
        for arquivo in DEMO.rglob("*.json"):
            texto = arquivo.read_text(encoding="utf-8")
            assert "/Users/" not in texto and "/home/" not in texto, arquivo
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_demo_audio_indisponivel_avisa():
    pasta, cliente = _cliente_na_copia()
    sistema.DEMONSTRACAO = True
    try:
        r = cliente.get("/api/reunioes/reuniao_01/audio", params={"inicio": 0, "fim": 3})
        assert r.status_code == 404
        assert r.json()["detail"] == "Áudio não disponível na demonstração."
    finally:
        sistema.DEMONSTRACAO = False
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
