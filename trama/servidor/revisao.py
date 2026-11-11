"""
servidor/revisao.py - POST /api/reunioes/{id}/revisao. A UNICA rota que
escreve no vozes.db (ADR 0004: servidor e casca fina).

Nao reimplementa NADA do ledger: revisao.decidir_contribuicao() e
revisao.aplicar_e_gravar() sao as MESMAS funcoes que revisao.py (CLI) usa -
extraidas de la justamente para isto. Nenhum SQL aqui; a unica escrita no
banco continua sendo nucleo.registrar_contribuicoes(), chamada de dentro de
revisao.aplicar_e_gravar().
"""

import json
import re

from trama import revisao

NOME_MAX_LEN = 80
PADRAO_CARACTERE_DE_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


class NomeInvalido(ValueError):
    """Nome recusado por formato, antes de tocar disco ou banco."""


class ReuniaoSemClusters(LookupError):
    """Reuniao existe mas nao tem .json processado (nao_processada) - nao
    ha o que revisar."""


def validar_nome(nome):
    if len(nome) > NOME_MAX_LEN:
        raise NomeInvalido(f"Nome tem {len(nome)} caracteres; o máximo é {NOME_MAX_LEN}.")
    if PADRAO_CARACTERE_DE_CONTROLE.search(nome):
        raise NomeInvalido("Nome contém caractere de controle, não permitido.")


def planejar(dados, escolhas, sem_aprender=()):
    """
    A decisao da revisao, sem tocar disco nem banco: (renomear, aprender,
    retirar). Usada pela gravacao (aplicar) e pela previa (previa) - as
    duas nunca podem decidir coisas diferentes com o mesmo corpo.

    escolhas: {cluster_label: nome_bruto}. String vazia (ou so espaco)
    mantem o nome atual do cluster, mesma convencao do Enter em branco na
    CLI; "-" ignora o cluster, tambem igual a CLI.

    sem_aprender: labels a NOMEAR sem aprender - o nome vai para o
    transcript, mas o cluster nao entra no ledger. E o --sem-aprender do
    revisao.py, so que por cluster: para um cluster majoritariamente de uma
    pessoa com trechos de outras (reuniao_06, SPEAKER_02). "-" tem
    precedencia: cluster ignorado nao ganha nome.

    retirar: cluster cuja contribuicao ANTERIOR (de uma revisao passada)
    sai do ledger - ignorado ou so nomeado agora, ou com nome confirmado
    mas sem fala suficiente para aprender (revisao.decidir_contribuicao).
    Quem diz que a voz nao serve, ou que ela e de outra pessoa sem dar
    base para aprender, nao pode deixar a contribuicao antiga valendo.
    """
    sem_aprender = set(sem_aprender)
    clusters = dados["clusters"]
    renomear, aprender, retirar = {}, [], []
    for label, nome_bruto in escolhas.items():
        info = clusters.get(label)
        if info is None:
            continue  # cluster que o cliente inventou - ignorado, nao criado

        nome = nome_bruto.strip() or info["nome"]
        if nome == "-":
            renomear[label] = f"IGNORADO_{label}"
            retirar.append(label)
            continue

        renomear[label] = nome
        if label in sem_aprender:
            retirar.append(label)
            continue
        contrib = revisao.decidir_contribuicao(label, nome, info)
        if contrib:
            aprender.append(contrib)
        else:
            retirar.append(label)
    return renomear, aprender, retirar


def _validar(escolhas):
    for nome_bruto in escolhas.values():
        nome_limpo = nome_bruto.strip()
        if nome_limpo and nome_limpo != "-":
            validar_nome(nome_limpo)


def previa(caminho_json, escolhas, sem_aprender=()):
    """O que a revisao tiraria de voz ja aprendida - sem gravar nada
    (revisao.efeitos_no_ledger). Nao atribui reuniao_id: sem um, nao ha
    nada aprendido desta reuniao para tirar."""
    _validar(escolhas)
    dados = json.loads(caminho_json.read_text(encoding="utf-8"))
    _, aprender, retirar = planejar(dados, escolhas, sem_aprender)
    return revisao.efeitos_no_ledger(dados.get("reuniao_id"), aprender, retirar)


def aplicar(caminho_json, escolhas, sem_aprender=()):
    """
    Valida TODOS os nomes primeiro - antes de ler o arquivo, tocar o banco
    ou escrever qualquer coisa - e grava a decisao de planejar().

    Devolve (dados_atualizados, totais_aprendidos).
    """
    _validar(escolhas)
    dados = json.loads(caminho_json.read_text(encoding="utf-8"))
    reuniao_id = revisao.garantir_reuniao_id(caminho_json, dados)
    renomear, aprender, retirar = planejar(dados, escolhas, sem_aprender)
    so_nomear = [
        label
        for label in sem_aprender
        if label in renomear and not renomear[label].startswith("IGNORADO")
    ]
    totais = revisao.aplicar_e_gravar(
        caminho_json, dados, reuniao_id, renomear, aprender, retirar, so_nomear=so_nomear
    )
    return dados, totais
