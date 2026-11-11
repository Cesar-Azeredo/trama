"""
servidor/pessoas.py - a tela Pessoas: voz aprendida e participacao de cada
pessoa da galeria, reuniao por reuniao.

A grade responde a pergunta "a presenca foi CONFIRMADA?", nao "a voz foi
aprendida?" - quanto de voz foi aprendido ja aparece na coluna propria.
As reunioes 01, 03 e 05 foram revisadas com --sem-aprender porque a voz
delas ja estava na base legada: sao presencas confirmadas, e mostra-las
como "voz nao aprendida" era enganoso.

Estados por celula (pessoa x reuniao), todos de dado que ja existe:

  confirmada  a revisao confirmou o cluster com o nome dessa pessoa
              (aprendendo ou so nomeando), ou o ledger tem uma
              contribuicao dela nessa reuniao.
  na_sala     estava na sala mas a presenca nao foi confirmada: o nome
              aparece num cluster ainda nao revisado, ou era quem o
              pipeline tinha identificado num cluster que a revisao
              IGNOROU (ver _sugerido_do_ignorado).
  (ausente)   nenhum dos dois. Fica FORA do dict - nunca uma string
              "ausente", mesma convencao do resto da API.

Reuniao nao processada nao tem como dizer quem estava na sala (as
pessoas marcadas no upload vivem so na memoria do processamento) - a
tela a marca como tal, em vez de fingir ausencia.
"""

import json

from trama import nucleo, pipeline
from trama.servidor import reunioes

PREFIXOS_SEM_PESSOA = ("DESCONHECIDO", "IGNORADO")


def _sugerido_do_ignorado(cluster, dados):
    """
    Quem o pipeline tinha identificado num cluster que a revisao ignorou.
    Desde 2026-09-24 a revisao guarda isso ao ignorar
    ("nome_antes_de_ignorar", revisao.aplicar_e_gravar). Para cluster
    ignorado antes disso o nome se perdeu - reconstroi a MESMA decisao que
    o pipeline.py tomou, com os scores e limiares gravados no proprio .json: o
    primeiro colocado, se passou de sim_min com margem_min sobre o
    segundo. Nunca um chute abaixo do limiar.
    """
    antes = cluster.get("nome_antes_de_ignorar")
    if antes:
        return antes
    scores = sorted((cluster.get("scores") or {}).values(), reverse=True)
    if not scores:
        return None
    melhor = max(cluster["scores"], key=cluster["scores"].get)
    sim_min = dados.get("sim_min", pipeline.SIM_MIN)
    margem_min = dados.get("margem_min", pipeline.MARGEM_MIN)
    segundo = scores[1] if len(scores) > 1 else 0.0
    if scores[0] >= sim_min and scores[0] - segundo >= margem_min:
        return melhor
    return None


def _presencas(dados):
    """{pessoa: "confirmada" | "na_sala"} tirado so dos clusters."""
    presencas = {}
    for c in (dados.get("clusters") or {}).values():
        nome = c["nome"]
        if nome.startswith("IGNORADO"):
            sugerido = _sugerido_do_ignorado(c, dados)
            if sugerido:
                presencas.setdefault(sugerido, "na_sala")
            continue
        if nome.startswith(PREFIXOS_SEM_PESSOA):
            continue
        if c.get("confirmado"):
            presencas[nome] = "confirmada"
        else:
            presencas.setdefault(nome, "na_sala")
    return presencas


def participacao():
    lista = []
    if reunioes.PASTA_AUDIOS.is_dir():
        for pasta in sorted(reunioes.PASTA_AUDIOS.iterdir()):
            if not pasta.is_dir() or not reunioes.PADRAO_ID.fullmatch(pasta.name):
                continue
            caminho = pasta / f"{pasta.name}.json"
            dados = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else None
            lista.append((pasta.name, dados))

    aprendidas = {}
    for reuniao_id, pessoa in nucleo.listar_contribuicoes():
        aprendidas.setdefault(pessoa, set()).add(reuniao_id)

    presencas_por_reuniao = {id: _presencas(dados) for id, dados in lista if dados is not None}

    pessoas = []
    for nome, peso, _ in nucleo.listar_pessoas():
        celulas = {}
        for id, dados in lista:
            if dados is None:
                continue
            if dados.get("reuniao_id") in aprendidas.get(nome, ()):
                celulas[id] = "confirmada"
            elif nome in presencas_por_reuniao[id]:
                celulas[id] = presencas_por_reuniao[id][nome]
        presentes = [id for id, _ in lista if id in celulas]
        pessoas.append(
            {
                "nome": nome,
                "peso_s": peso,
                "participacao": celulas,
                "total_reunioes": len(presentes),
                "ultima": presentes[-1] if presentes else None,
            }
        )
    pessoas.sort(key=lambda p: (-p["peso_s"], p["nome"]))

    return {
        "reunioes": [{"id": id, "processada": dados is not None} for id, dados in lista],
        "pessoas": pessoas,
    }
