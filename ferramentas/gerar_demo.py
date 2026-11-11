"""
ferramentas/gerar_demo.py - Gera os dados de demonstracao: audios-demo/ com
tres reunioes ficticias (.json e .txt, sem audio) e audios-demo/vozes-demo.db
com os perfis de voz ficticios aprendidos nelas.

Os .json saem das funcoes de verdade do pipeline - alinhar(), a analise de
interacao, a decisao de nome por cluster, montar_saida() - e a revisao das
reunioes 1 e 2 passa por revisao.aplicar_e_gravar(), a mesma que a tela usa.
So a entrada e sintetica: palavras com tempos calculados a partir do
roteiro (ferramentas/roteiro_demo.py), diarizacao igual aos turnos do
roteiro e embeddings de voz sorteados (semente fixa) em volta de um vetor
por pessoa. Deterministico: rodar de novo gera os mesmos .json e .txt, e
o banco com o mesmo conteudo (os carimbos de hora sao fixados nas datas
das reunioes; so a ordem fisica das linhas do SQLite pode variar).

Uso (a partir da raiz):
    python ferramentas/gerar_demo.py

Depois:
    REC_MEET_DEMO=1 REC_MEET_AUDIOS=audios-demo \\
    VOZES_DB=audios-demo/vozes-demo.db REC_MEET_TERMOS=termos.exemplo.txt \\
    trama-servidor
"""

import json
import os
import shutil
import sys
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "audios-demo"
BANCO = PASTA / "vozes-demo.db"

# Antes de importar o pacote: nucleo le VOZES_DB no import.
os.environ["VOZES_DB"] = str(BANCO)
sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402

from ferramentas.roteiro_demo import PESSOAS, REUNIOES  # noqa: E402
from trama import interacao, nucleo, pipeline, revisao, termos  # noqa: E402

SEMENTE = 2026
DIMENSAO = 256  # mesma do wespeaker-voxceleb-resnet34-LM
RUIDO_VOZ = 0.035  # similaridade de cosseno ~0,87 com a voz base
SEGUNDOS_POR_PALAVRA = 0.34
PROB_NORMAL = 0.93
PROB_DUVIDA = 0.31
SILENCIO_LACUNA_S = 1.3
# Espaco de nomes fixo: reuniao_id deterministico (uuid5) entre execucoes.
NAMESPACE = uuid.UUID("6f1c2a52-6a0b-4c1e-9a43-7c1d2f0e8b11")


class Trecho:
    """O que iter_turns espera de um segmento do pyannote: .start/.end."""

    def __init__(self, inicio, fim):
        self.start, self.end = inicio, fim


def _vozes_base(rng):
    nomes = PESSOAS + ["Sofia"]  # Sofia nao esta na galeria: vira voz desconhecida
    return {n: nucleo.l2(rng.normal(size=DIMENSAO)) for n in nomes}


def _eh_apoio(texto, pausa):
    """Fala curta que entra bem antes do fim de quem fala ("Uhum.")."""
    return pausa <= -1.5 and len(texto.split()) <= 2


def _palavras_e_turnos(falas, rng):
    """Palavras com tempo (formato do Whisper) e turnos (inicio, fim, pessoa).

    Como no Whisper de verdade, as palavras sao UM fluxo em sequencia -
    nunca duas pessoas com palavras intercaladas no tempo. Quem interrompe
    tem o TURNO (diarizacao) comecando por cima do fim do outro, mas as
    palavras dele so vem depois das do outro; e e esse descompasso que vira
    sobreposicao, interrupcao e pista de divergencia na analise. O apoio
    ("Uhum.") fica so na diarizacao, sem texto - o Whisper costuma nao
    transcrever."""
    palavras, turnos = [], []
    fim_ate_aqui = 0.0  # fim do turno de quem esta com a palavra
    fim_palavras = 0.0  # fim da ultima palavra transcrita
    for pessoa, texto, pausa in falas:
        inicio = max(0.0, fim_ate_aqui + pausa)
        if _eh_apoio(texto, pausa):
            turnos.append((inicio, inicio + 0.45, pessoa))
            continue
        t = max(inicio, fim_palavras + 0.04)
        for token in texto.split():
            if token == "|":
                t += SILENCIO_LACUNA_S
                continue
            duvida = token.startswith("~")
            token = token.lstrip("~")
            dur = SEGUNDOS_POR_PALAVRA * (0.6 + len(token) / 8)
            prob = PROB_DUVIDA if duvida else min(0.99, PROB_NORMAL + rng.normal(0, 0.03))
            palavras.append(
                {
                    "word": " " + token,
                    "start": round(t, 2),
                    "end": round(t + dur, 2),
                    "probability": round(float(prob), 3),
                }
            )
            t += dur + 0.04
        fim_palavras = t
        turnos.append((inicio, t, pessoa))
        fim_ate_aqui = max(fim_ate_aqui, t)
    return palavras, turnos


def _diarizacao(turnos, rotulos):
    """(nao-exclusiva, exclusiva). Na exclusiva, quem entra por cima corta
    o turno de quem falava - um falante por instante, como a do pyannote."""
    nao_exclusiva = [(Trecho(a, b), rotulos[p]) for a, b, p in turnos]
    ordenados = sorted(turnos)
    exclusiva = []
    for i, (a, b, p) in enumerate(ordenados):
        proximo = ordenados[i + 1][0] if i + 1 < len(ordenados) else b
        fim = min(b, proximo) if proximo > a else b
        exclusiva.append((Trecho(a, fim), rotulos[p]))
    return nao_exclusiva, exclusiva


def _mapa(turnos, rotulos, vozes, rng):
    """Cluster -> {nome, sim, margem, ...} pela MESMA decisao do pipeline
    (pipeline._decidir), com a galeria aprendida nas reunioes anteriores."""
    galeria = nucleo.get_galeria()
    nomes = sorted(galeria)
    mapa = {}
    for pessoa, label in rotulos.items():
        fala_s = sum(b - a for a, b, p in turnos if p == pessoa)
        emb = nucleo.l2(vozes[pessoa] + rng.normal(scale=RUIDO_VOZ, size=DIMENSAO))
        if nomes:
            linha = np.array([float(np.dot(emb, nucleo.l2(galeria[n]))) for n in nomes])
            mapa[label] = pipeline._decidir(label, linha, nomes, emb, fala_s)
        else:
            mapa[label] = pipeline._desconhecido(label, round(fala_s, 1), emb.tolist())
    return mapa


def _gerar(reuniao, vozes, rng, regras):
    id = reuniao["id"]
    pasta = PASTA / id
    pasta.mkdir(parents=True)
    falantes = list(dict.fromkeys(p for p, _, _ in reuniao["falas"]))
    rotulos = {p: f"SPEAKER_{i:02d}" for i, p in enumerate(falantes)}

    palavras, turnos = _palavras_e_turnos(reuniao["falas"], rng)
    nao_exclusiva, exclusiva = _diarizacao(turnos, rotulos)
    mapa = _mapa(turnos, rotulos, vozes, rng)

    analise = interacao.analisar(nao_exclusiva, pipeline.iter_turns, mapa)
    falas, lacunas = pipeline.alinhar(
        palavras, exclusiva, mapa, turnos_ativos=analise["turnos_brutos"]
    )
    termos.aplicar_em_falas(falas, regras, lacunas)

    reuniao_id = str(uuid.uuid5(NAMESPACE, id))
    saida = pipeline.montar_saida(
        f"{id}.m4a",
        f"{id}_16k.wav",
        mapa,
        falas,
        analise,
        reuniao_id=reuniao_id,
        lacunas=lacunas,
        device="mps",
        asr="mlx",
        metadados={
            "titulo": reuniao["titulo"],
            "data_reuniao": reuniao["data"],
            "data_origem": "gravacao",
        },
    )
    # Caminhos relativos: montar_saida resolve para absoluto, e o caminho
    # da maquina de quem gerou nao entra no repositorio.
    saida["audio"], saida["wav16k"] = f"{id}.m4a", f"{id}_16k.wav"
    caminho = pasta / f"{id}.json"
    caminho.write_text(nucleo.json_para_disco(saida), encoding="utf-8")
    pipeline.escrever_txt(falas, mapa, pasta / f"{id}.txt", regioes=analise["regioes_sobrepostas"])

    if reuniao["revisar"]:
        _revisar(caminho, rotulos)


def _revisar(caminho, rotulos):
    """Confirma o nome de cada cluster como a tela de Revisao faria."""
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    renomear = {label: pessoa for pessoa, label in rotulos.items()}
    aprender, retirar = [], []
    for label, nome in renomear.items():
        contrib = revisao.decidir_contribuicao(label, nome, dados["clusters"][label])
        (aprender.append(contrib) if contrib else retirar.append(label))
    revisao.aplicar_e_gravar(caminho, dados, dados["reuniao_id"], renomear, aprender, retirar)


def _datas_das_revisoes():
    """Carimbos de hora do banco: cada contribuicao na data da propria
    reuniao, cada perfil na ultima contribuicao dele. Sem isto o banco
    mudaria a cada execucao (o ledger grava a hora da revisao), e a ordem
    das cores de voz - que sai da primeira contribuicao de cada pessoa -
    ficaria por conta do relogio."""
    import sqlite3

    con = sqlite3.connect(BANCO)
    try:
        for reuniao in REUNIOES:
            reuniao_id = str(uuid.uuid5(NAMESPACE, reuniao["id"]))
            data = reuniao["data"].replace("Z", "+00:00")
            con.execute(
                "UPDATE contribuicoes SET atualizado = ? WHERE reuniao_id = ?", (data, reuniao_id)
            )
        con.execute(
            "UPDATE pessoas SET atualizado = (SELECT MAX(c.atualizado) FROM contribuicoes c "
            "WHERE c.pessoa = pessoas.nome)"
        )
        con.commit()
    finally:
        con.close()


def _sem_caminho_absoluto():
    """Nenhum arquivo gerado pode conter o caminho desta maquina."""
    for arquivo in PASTA.rglob("*"):
        if arquivo.suffix in (".json", ".txt") and str(RAIZ) in arquivo.read_text("utf-8"):
            raise SystemExit(f"caminho absoluto vazou em {arquivo}")


def main():
    if PASTA.exists():
        shutil.rmtree(PASTA)
    PASTA.mkdir()
    rng = np.random.default_rng(SEMENTE)
    vozes = _vozes_base(rng)
    regras = termos.carregar(RAIZ / "termos.exemplo.txt")
    for reuniao in REUNIOES:
        _gerar(reuniao, vozes, rng, regras)
    _datas_das_revisoes()
    for backup in PASTA.glob("vozes-demo.db.bak-*"):
        backup.unlink()
    _sem_caminho_absoluto()
    print(f"Pronto: {PASTA.relative_to(RAIZ)}/ ({len(REUNIOES)} reunioes) e {BANCO.name}")
    for nome, peso, _ in nucleo.listar_pessoas():
        print(f"  {nome:<10} {peso:5.0f} s de voz aprendida")


if __name__ == "__main__":
    main()
