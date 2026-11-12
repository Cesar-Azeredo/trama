"""
tests/test_servidor_origem.py - So o proprio app fala com o servidor
(servidor/origem.py, ADR 0030): Host 127.0.0.1/localhost na porta do
servidor, Origin ausente ou da porta do frontend. Upload, leitura e
exclusao vindos de outro site, e DNS rebinding (Host de outro nome).

Parte das suites do servidor FastAPI (trama/servidor/, ADR 0004); a
infraestrutura comum esta em tests/servidor_apoio.py.

Uso:
    python tests/test_servidor_origem.py
"""

import shutil
import sys

import servidor_apoio  # noqa: F401 - isola o ambiente e instala os stubs ANTES do projeto
from servidor_apoio import _ambiente_temporario, _criar_reuniao_completa, erro_de, rodar_suite

from trama.servidor import origem, reunioes

ESTRANHA = {"Origin": "http://site-qualquer.example"}


def test_regra_de_host_e_origin():
    m = lambda host, origin=None: origem.motivo_de_recusa(host, origin, 8000, 5173)  # noqa: E731
    assert m("127.0.0.1:8000") is None
    assert m("localhost:8000") is None
    assert m("LOCALHOST:8000") is None
    assert m("127.0.0.1:8000", "http://localhost:5173") is None
    assert m("127.0.0.1:8000", "http://127.0.0.1:5173") is None
    assert m("127.0.0.1:8000", "http://127.0.0.1:8000") is None, "pagina servida pelo proprio"
    assert m("evil.example:8000") == "host_recusado", "DNS rebinding"
    assert m("127.0.0.1:9999") == "host_recusado", "outra porta"
    assert m("127.0.0.1") == "host_recusado", "porta 80 implicita"
    assert m(None) == "host_recusado"
    assert m("127.0.0.1.evil.example:8000") == "host_recusado"
    assert m("127.0.0.1:8000", "http://evil.example") == "origem_recusada"
    assert m("127.0.0.1:8000", "http://localhost:3000") == "origem_recusada"
    assert m("127.0.0.1:8000", "https://localhost:5173") == "origem_recusada"
    assert m("127.0.0.1:8000", "null") == "origem_recusada", "iframe sandbox, file://"


def test_upload_vindo_de_outro_site_e_recusado_sem_criar_reuniao():
    pasta, cliente = _ambiente_temporario()
    try:
        r = cliente.post(
            "/api/reunioes",
            files={"arquivo": ("x.m4a", b"\x00" * 10, "audio/mp4")},
            headers=ESTRANHA,
        )
        assert r.status_code == 403 and erro_de(r) == ("origem_recusada", {}), r.text
        assert list(reunioes.PASTA_AUDIOS.iterdir()) == []
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_leitura_e_exclusao_vindas_de_outro_site_sao_recusadas():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_01")
        r = cliente.get("/api/reunioes/reuniao_01", headers=ESTRANHA)
        assert r.status_code == 403 and erro_de(r)[0] == "origem_recusada", r.text
        r = cliente.delete("/api/reunioes/reuniao_01", headers=ESTRANHA)
        assert r.status_code == 403, r.text
        assert (reunioes.PASTA_AUDIOS / "reuniao_01" / "reuniao_01.json").exists()
        # o proprio app (Vite na 5173) continua passando
        r = cliente.get("/api/reunioes/reuniao_01", headers={"Origin": "http://localhost:5173"})
        assert r.status_code == 200, r.text
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_dns_rebinding_host_de_outro_nome_e_recusado():
    pasta, cliente = _ambiente_temporario()
    try:
        _criar_reuniao_completa(reunioes.PASTA_AUDIOS, "reuniao_01")
        # a pagina do atacante, ja "na mesma origem": sem Origin, mas com o
        # nome dela no Host
        for metodo in ("get", "delete"):
            r = getattr(cliente, metodo)(
                "/api/reunioes/reuniao_01", headers={"Host": "rebind.example:8000"}
            )
            assert r.status_code == 403 and erro_de(r)[0] == "host_recusado", r.text
        r = cliente.get(
            "/api/reunioes/reuniao_01/transcricao", headers={"Host": "rebind.example:8000"}
        )
        assert r.status_code == 403
        assert (reunioes.PASTA_AUDIOS / "reuniao_01").is_dir()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def test_porta_do_frontend_vem_de_trama_porta_frontend():
    import os

    os.environ["TRAMA_PORTA_FRONTEND"] = "5199"
    try:
        assert origem.motivo_de_recusa("127.0.0.1:8000", "http://127.0.0.1:5199") is None
        assert origem.motivo_de_recusa("127.0.0.1:8000", "http://127.0.0.1:5173") == (
            "origem_recusada"
        )
    finally:
        del os.environ["TRAMA_PORTA_FRONTEND"]


if __name__ == "__main__":
    sys.exit(rodar_suite(globals()))
