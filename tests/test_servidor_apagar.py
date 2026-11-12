"""
tests/test_servidor_apagar.py - Apagar uma reuniao: a previa do que cada
pessoa perde de voz e o DELETE (pasta inteira + contribuicoes no ledger,
com VACUUM).

Parte das suites do servidor FastAPI (trama/servidor/, ADR 0004); a
infraestrutura comum esta em tests/servidor_apoio.py.

Uso:
    python tests/test_servidor_apagar.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import servidor_apoio  # noqa: F401 - isola o ambiente e instala os stubs ANTES do projeto
from servidor_apoio import (
    _ambiente_temporario,
    _criar_reuniao_completa,
    _criar_reuniao_nao_processada,
    erro_de,
    rodar_suite,
)

from trama import nucleo
from trama.servidor import processamento, reunioes


def _vetor(valor):
    """Formato proprio por valor: vetor constante normalizado da sempre o
    mesmo, e a checagem de bytes no arquivo acharia o de outra pessoa."""
    import numpy as np

    return np.sin(np.arange(64, dtype=np.float32) * valor + valor).astype(np.float32)


def _cenario(pasta_audios):
    """reuniao_05 ensinou Ramiro (40 s) e Amanda (20 s); Ramiro tem voz
    tambem de outra reuniao, Amanda so desta."""
    _criar_reuniao_completa(pasta_audios, "reuniao_05")
    _criar_reuniao_completa(pasta_audios, "reuniao_06")
    nucleo.registrar_contribuicoes(
        "uuid-reuniao_05",
        [("S0", "Ramiro", _vetor(0.31), 40.0), ("S1", "Amanda", _vetor(0.6543), 20.0)],
    )
    nucleo.registrar_contribuicoes("uuid-reuniao_06", [("S0", "Ramiro", _vetor(0.29), 30.0)])


def test_previa_diz_quanto_cada_pessoa_perde_sem_apagar_nada():
    pasta, cliente = _ambiente_temporario()
    try:
        _cenario(reunioes.PASTA_AUDIOS)
        antes = nucleo.DB_PATH.read_bytes()
        r = cliente.get("/api/reunioes/reuniao_05/exclusao")
        assert r.status_code == 200, r.text
        assert r.json()["perdas"] == [
            {"pessoa": "Ramiro", "peso_s": 40.0, "restante_s": 30.0, "perfil_some": False},
            {"pessoa": "Amanda", "peso_s": 20.0, "restante_s": 0.0, "perfil_some": True},
        ]
        assert (reunioes.PASTA_AUDIOS / "reuniao_05").is_dir()
        assert nucleo.DB_PATH.read_bytes() == antes
        # reuniao sem nada no ledger (ou sem .json): nenhuma perda
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_07")
        assert cliente.get("/api/reunioes/reuniao_07/exclusao").json() == {"perdas": []}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_apagar_tira_a_pasta_e_a_voz_desta_reuniao_e_nada_mais():
    import sqlite3

    pasta, cliente = _ambiente_temporario()
    try:
        _cenario(reunioes.PASTA_AUDIOS)
        gravado = nucleo.l2(_vetor(0.6543)).astype("float32").tobytes()
        assert gravado in nucleo.DB_PATH.read_bytes(), "premissa: vetor esta no arquivo"
        r = cliente.delete("/api/reunioes/reuniao_05")
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["pessoas"] == {"Ramiro": 30.0, "Amanda": 0.0}, corpo
        assert corpo["compactado"] is True

        assert not (reunioes.PASTA_AUDIOS / "reuniao_05").exists()
        assert list(reunioes.PASTA_AUDIOS.iterdir()) == [reunioes.PASTA_AUDIOS / "reuniao_06"], (
            "nenhuma pasta escondida sobrando"
        )
        ids = [x["id"] for x in cliente.get("/api/reunioes").json()]
        assert ids == ["reuniao_06"]
        # Amanda so tinha voz daqui: sai da galeria; Ramiro fica com a outra
        nomes = {p["nome"]: p for p in cliente.get("/api/pessoas").json()}
        assert set(nomes) == {"Ramiro"}
        con = sqlite3.connect(nucleo.DB_PATH)
        linhas = con.execute("SELECT reuniao_id FROM contribuicoes").fetchall()
        con.close()
        assert linhas == [("uuid-reuniao_06",)]
        # o vetor de voz da Amanda nao fica legivel nas paginas livres
        assert gravado not in nucleo.DB_PATH.read_bytes()
        assert cliente.get("/api/reunioes/reuniao_05").status_code == 404
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_apagar_reuniao_na_fila_sem_json():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_nao_processada(reunioes.PASTA_AUDIOS, "reuniao_02")
        r = cliente.delete("/api/reunioes/reuniao_02")
        assert r.status_code == 200, r.text
        assert r.json()["pessoas"] == {}
        assert not (reunioes.PASTA_AUDIOS / "reuniao_02").exists()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_apagar_leva_a_copia_wav_temporaria_mas_so_dentro_da_pasta_temporaria():
    pasta, cliente = _ambiente_temporario()
    fora = None
    try:
        pasta_reuniao = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_05")
        sub = Path(tempfile.mkdtemp())
        wav = sub / "reuniao_05_16k.wav"
        wav.write_bytes(b"RIFF")
        j = pasta_reuniao / "reuniao_05.json"
        d = json.loads(j.read_text(encoding="utf-8"))
        d["wav16k"] = str(wav)
        j.write_text(json.dumps(d), encoding="utf-8")
        assert cliente.delete("/api/reunioes/reuniao_05").status_code == 200
        assert not wav.exists() and not sub.exists()

        # um wav16k apontando para fora da pasta temporaria nunca e tocado
        fora = Path(tempfile.mkdtemp(dir=pasta)) / "x_16k.wav"
        fora.write_bytes(b"RIFF")
        pasta_reuniao = _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_06")
        j = pasta_reuniao / "reuniao_06.json"
        d = json.loads(j.read_text(encoding="utf-8"))
        d["wav16k"] = str(fora)
        j.write_text(json.dumps(d), encoding="utf-8")
        assert cliente.delete("/api/reunioes/reuniao_06").status_code == 200
        assert fora.exists()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_apagar_recusa_reuniao_sendo_processada_sem_tocar_nada():
    pasta, cliente = _ambiente_temporario()
    try:
        _cenario(reunioes.PASTA_AUDIOS)
        antes = nucleo.DB_PATH.read_bytes()
        processamento._estado = {"reuniao_id": "reuniao_05", "status": "rodando"}
        try:
            r = cliente.delete("/api/reunioes/reuniao_05")
        finally:
            processamento._estado = None
        assert r.status_code == 409 and erro_de(r) == ("reuniao_processando", {}), r.text
        assert (reunioes.PASTA_AUDIOS / "reuniao_05" / "reuniao_05.json").exists()
        assert nucleo.DB_PATH.read_bytes() == antes
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_apagar_falha_no_ledger_nao_apaga_a_pasta():
    pasta, cliente = _ambiente_temporario()
    original = nucleo.excluir_contribuicoes_da_reuniao
    try:
        _cenario(reunioes.PASTA_AUDIOS)

        def quebra(_):
            raise RuntimeError("banco travado")

        nucleo.excluir_contribuicoes_da_reuniao = quebra
        r = cliente.delete("/api/reunioes/reuniao_05")
        assert r.status_code == 500 and erro_de(r) == ("falha_apagar_reuniao", {}), r.text
        assert (reunioes.PASTA_AUDIOS / "reuniao_05" / "reuniao_05.json").exists()
    finally:
        nucleo.excluir_contribuicoes_da_reuniao = original
        shutil.rmtree(pasta, ignore_errors=True)


def test_apagar_id_invalido_ou_inexistente():
    pasta, cliente = _ambiente_temporario()
    try:
        assert cliente.delete("/api/reunioes/reuniao_99").status_code == 404
        r = cliente.delete("/api/reunioes/Reuniao.05")
        assert r.status_code == 400 and erro_de(r)[0] == "id_invalido", r.text
        assert cliente.get("/api/reunioes/x..y/exclusao").status_code == 400
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
