"""
trama/revisao.py - Correcao humana + realimentacao dos perfis de voz
(antigo revisao.py). A conversa no terminal mora em trama/cli/revisar.py;
o servidor (servidor/revisao.py) usa as MESMAS funcoes daqui.

Este arquivo e o que transforma "IA que as vezes erra" em ferramenta confiavel.

Voce nao corrige 300 falas. Voce corrige de 3 a 6 clusters - uma decisao por
pessoa presente na reuniao. Leva ~20 segundos. E cada confirmacao sua alimenta
o perfil de voz daquela pessoa gravado NA SUA SALA, com o SEU microfone,
entao a proxima reuniao ja sai melhor.

IDEMPOTENTE: revisar a mesma reuniao duas vezes com a mesma resposta nao
infla o perfil (a contribuicao e identificada por reuniao_id+cluster e
SUBSTITUI a anterior, nunca soma). Corrigir a pessoa de um cluster move a
contribuicao do perfil antigo para o novo - os dois sao recalculados.

Uso:
    trama-revisar reuniao.json
"""

import uuid

import numpy as np

from trama import erros, interacao, nucleo, pipeline
from trama.idioma import t

DURACAO_MIN_TRECHO = 4.0  # segundos
DURACAO_MAX_TRECHO = 15.0  # segundos


def selecionar_trechos(falas, label, n=3):
    """
    Ate n trechos do cluster para ouvir na revisao. Dois criterios, nessa
    ordem de importancia:

      1. Duracao entre DURACAO_MIN_TRECHO e DURACAO_MAX_TRECHO segundos -
         curto demais nao da pra ouvir a cadencia da voz; longo demais
         (um monologo de varios minutos) faz o cartao da tela de revisao
         virar rolagem, quando a decisao deveria levar segundos.
      2. Espalhados no TEMPO (inicio, meio, fim da participacao da pessoa
         na reuniao), nunca so os mais longos - tres amostras de
         momentos diferentes dizem mais sobre a voz de alguem do que um
         trecho so, por mais longo que seja.

    MESMO criterio usado pela tela de revisao do servidor
    (frontend/src/telas/Revisao.tsx:selecionarTrechos) - CLI e navegador
    tem que escolher os mesmos trechos para a mesma reuniao.

    REGRESSAO corrigida: o criterio antigo escolhia os 3 trechos com MAIS
    caracteres de texto. No terminal, a linha truncada em 90 caracteres
    escondia o problema; na tela de revisao, o cartao de uma fala de
    varios minutos ocupava tres telas de rolagem para uma decisao de
    poucos segundos.

    Se o cluster nao tiver nenhuma fala na faixa ideal (so falas muito
    curtas ou muito longas), cai para as mais proximas da faixa - ainda
    assim devolvidas em ordem cronologica.
    """
    trechos = [f for f in falas if f["cluster"] == label]
    if not trechos:
        return []

    candidatos = [
        f for f in trechos if DURACAO_MIN_TRECHO <= (f["fim"] - f["inicio"]) <= DURACAO_MAX_TRECHO
    ]
    if not candidatos:

        def distancia_da_faixa(f):
            duracao = f["fim"] - f["inicio"]
            if duracao < DURACAO_MIN_TRECHO:
                return DURACAO_MIN_TRECHO - duracao
            return duracao - DURACAO_MAX_TRECHO

        escolhidos = sorted(trechos, key=distancia_da_faixa)[:n]
        return sorted(escolhidos, key=lambda f: f["inicio"])

    return _espalhar_no_tempo(candidatos, trechos, n)


def _espalhar_no_tempo(candidatos, todos, n):
    """
    Divide a janela de tempo em que o cluster fala (do primeiro ao ultimo
    'inicio' entre TODOS os trechos, nao so os candidatos) em n fatias
    iguais, e pega um candidato de cada fatia - assim as amostras vem do
    inicio, do meio e do fim da participacao da pessoa, nao de um trecho
    concentrado.
    """
    inicio_min = min(f["inicio"] for f in todos)
    inicio_max = max(f["inicio"] for f in todos)
    largura = (inicio_max - inicio_min) / n or 1.0

    escolhidos, usados = [], set()
    for i in range(n):
        limite_inf = inicio_min + i * largura
        limite_sup = inicio_min + (i + 1) * largura
        do_bucket = [
            f for f in candidatos if limite_inf <= f["inicio"] <= limite_sup and id(f) not in usados
        ]
        if do_bucket:
            escolha = do_bucket[len(do_bucket) // 2]
            escolhidos.append(escolha)
            usados.add(id(escolha))

    if len(escolhidos) < n:
        restantes = sorted(
            (f for f in candidatos if id(f) not in usados), key=lambda f: f["inicio"]
        )
        for f in restantes:
            if len(escolhidos) >= n:
                break
            escolhidos.append(f)
            usados.add(id(f))

    return sorted(escolhidos, key=lambda f: f["inicio"])


def garantir_reuniao_id(caminho, dados):
    """
    Identidade estavel da reuniao para o ledger de contribuicoes de voz.

    Arquivos gerados pelo pipeline.py atual ja trazem "reuniao_id". Para um JSON
    antigo (sem o campo), atribui um agora e grava IMEDIATAMENTE - antes de
    qualquer outra coisa, inclusive antes do loop interativo. Isso importa
    para a recuperacao apos falha: se o processo morrer mais adiante, o
    reuniao_id ja esta no disco e a proxima execucao usa o MESMO id (nao gera
    um novo, o que faria a revisao parecer "uma reuniao nova" e duplicaria a
    contribuicao no perfil).

    Chamada tanto pelo revisao.py (CLI) quanto pela rota
    POST /api/reunioes/{id}/revisao (servidor/revisao.py) - mesmo
    comportamento nos dois: a reuniao so ganha um reuniao_id na primeira
    revisao, nunca dois.

    Limitacao que nao da para contornar: revisoes JA FEITAS neste arquivo
    antes desta mudanca nao tem como ser conciliadas retroativamente - o
    aprendizado que ja foi para o perfil (pelo upsert_pessoa antigo) fica
    onde esta. So as revisoes a partir de agora ficam rastreaveis.
    """
    if dados.get("reuniao_id"):
        return dados["reuniao_id"]
    novo = str(uuid.uuid4())
    dados["reuniao_id"] = novo
    nucleo.escrever_atomico(caminho, nucleo.json_para_disco(dados))
    print(t("reuniao_id_novo", id=novo[:8]))
    return novo


LIMIAR_FALA_MINIMA_PARA_APRENDER = 20.0  # segundos


def decidir_contribuicao(label, nome, info):
    """
    Decide se um cluster corrigido deve alimentar o ledger de vozes:
    precisa ter embedding, nome real (nao um placeholder DESCONHECIDO_* nem
    IGNORADO_*)
    e fala suficiente para um embedding estavel (>=20s, mesmo raciocinio
    de MIN_SEG_DUR/MAX_SPEECH_PER_CLUSTER em nucleo.py). MESMA regra usada
    pelo loop interativo do CLI e pela rota de revisao do servidor - uma
    unica funcao, para as duas nunca aprenderem coisas diferentes com a
    mesma decisao humana.

    Devolve (label, nome, embedding_np, peso_fala_s) ou None.
    """
    if not info.get("embedding"):
        return None
    # Rotulo de maquina nunca vira perfil de voz: DESCONHECIDO_* (ninguem
    # identificado) e IGNORADO_* (cluster ignorado numa revisao anterior -
    # revisar de novo com o campo em branco mantem esse nome, e sem esta
    # guarda a galeria ganhava uma "pessoa" chamada IGNORADO_SPEAKER_02).
    if nome.startswith(("DESCONHECIDO", "IGNORADO")):
        return None
    if info["fala_s"] < LIMIAR_FALA_MINIMA_PARA_APRENDER:
        return None
    return (label, nome, np.asarray(info["embedding"], dtype=np.float32), info["fala_s"])


# Peso gravado no ledger = fala do cluster * isto (aplicar_e_gravar). A
# previa usa o MESMO numero, para "vai ensinar 110 s" ser o que entra.
FATOR_PESO_CONTRIBUICAO = 0.5


def efeitos_no_ledger(reuniao_id, aprender, retirar):
    """
    O que a revisao vai MUDAR na voz aprendida, antes de gravar - nenhuma
    voz entra nem sai do banco sem a pessoa ver o numero (a tela mostra e
    pede confirmacao; o CLI pergunta). Nada e gravado aqui.

    [{"cluster", "tipo", "pessoa", "peso_s", "para", "perfil_some"}]:
      tipo="ensinar"  voz NOVA entra no perfil de "pessoa". Faltava:
                      reabrir a reuniao_01 (revisada so nomeando) e salvar
                      sem mexer ensinou 293 s de voz sem aviso nenhum.
      tipo="remover"  a voz de "pessoa" sai (cluster ignorado, so
                      nomeado, ou sem fala para aprender).
      tipo="mover"    a voz passa de "pessoa" para "para" (outro nome
                      confirmado no mesmo cluster).
    Reconfirmar a mesma pessoa no mesmo cluster nao e efeito: a
    contribuicao e substituida por ela mesma (idempotente).
    perfil_some: a pessoa fica sem voz nenhuma e sai da galeria.
    """
    existentes = nucleo.contribuicoes_da_reuniao(reuniao_id)
    efeitos = []
    for label in retirar:
        if label in existentes:
            pessoa, peso = existentes[label]
            efeitos.append(
                {
                    "cluster": label,
                    "tipo": "remover",
                    "pessoa": pessoa,
                    "peso_s": peso,
                    "para": None,
                }
            )
    for label, nome, _, fala_s in aprender:
        nome = nome.strip()
        if label not in existentes:
            efeitos.append(
                {
                    "cluster": label,
                    "tipo": "ensinar",
                    "pessoa": nome,
                    "peso_s": fala_s * FATOR_PESO_CONTRIBUICAO,
                    "para": None,
                    "perfil_some": False,
                }
            )
        elif existentes[label][0] != nome:
            pessoa, peso = existentes[label]
            efeitos.append(
                {"cluster": label, "tipo": "mover", "pessoa": pessoa, "peso_s": peso, "para": nome}
            )
    saindo = [e for e in efeitos if e["tipo"] != "ensinar"]
    if saindo:
        totais = {n: p for n, p, _ in nucleo.listar_pessoas()}
        tirado = {}
        for e in saindo:
            tirado[e["pessoa"]] = tirado.get(e["pessoa"], 0.0) + e["peso_s"]
        for e in saindo:
            e["perfil_some"] = (totais.get(e["pessoa"], 0.0) - tirado[e["pessoa"]]) <= 1e-6
    return sorted(efeitos, key=lambda e: e["cluster"])


def _renomear_marcas(dados, renomear):
    """
    Pistas de divergencia (palavras_divergentes, dentro de cada fala) e
    lacunas (lacunas_sem_texto) guardam o NOME de quem falou - sem isto,
    depois da revisao elas continuavam com o nome sugerido de antes (um
    DESCONHECIDO_* na tela, em cinza, onde ja havia uma pessoa confirmada).

    Marca gravada por esta versao do pipeline traz o "cluster": renomeia
    por ele. Marca antiga, sem cluster: renomeia pelo nome antigo, so
    quando esse nome era de UM cluster - nome que estava em dois clusters
    nao diz de qual dos dois era, e fica como esta (sem chute).
    """
    contagem = {}
    for info in dados["clusters"].values():
        contagem[info["nome"]] = contagem.get(info["nome"], 0) + 1
    por_nome_antigo = {
        info["nome"]: renomear[label]
        for label, info in dados["clusters"].items()
        if label in renomear and contagem[info["nome"]] == 1
    }

    def renomear_marca(marca):
        if marca.get("cluster") in renomear:
            marca["falante"] = renomear[marca["cluster"]]
        elif "cluster" not in marca and marca.get("falante") in por_nome_antigo:
            marca["falante"] = por_nome_antigo[marca["falante"]]

    for f in dados["falas"]:
        for marca in f.get("palavras_divergentes") or []:
            renomear_marca(marca)
    for marca in dados.get("lacunas_sem_texto") or []:
        renomear_marca(marca)


def aplicar_e_gravar(caminho, dados, reuniao_id, renomear, aprender, retirar=(), so_nomear=()):
    """
    Parte NAO interativa da revisao: aprende os perfis de voz (ledger),
    corrige falas/clusters, recalcula dinamica e grava .json/.txt.
    Chamada tanto pelo revisao.py (CLI, apos o loop interativo) quanto
    pela rota POST /api/reunioes/{id}/revisao - a MESMA funcao, para as
    duas nunca divergirem no que gravam.

    `renomear`: {cluster_label: nome_final}, decisao ja tomada.
    `aprender`: [(label, nome, embedding_np, peso_fala_s)] - so os
    clusters que devem alimentar o ledger (ver decidir_contribuicao).
    `so_nomear`: labels nomeados sem aprender - gravado no cluster
    ("sem_aprender": true) para a decisao sobreviver a um reprocessamento
    (pipeline.preservar_revisao) e a tela de revisao reabrir no modo certo.
    `retirar`: labels cuja contribuicao ANTERIOR sai do ledger (cluster
    ignorado, so nomeado, ou renomeado sem fala suficiente para aprender
    - ver planejar_revisao). Mesma transacao de `aprender`.

    ORDEM DELIBERADA, para uma falha em qualquer etapa nunca deixar nem o
    banco nem os arquivos pela metade:

      1. calcula tudo em MEMORIA (falas, clusters, dinamica, os textos de
         .txt e .json) - nada tocado em disco ou banco ainda.
      2. PREPARA os dois arquivos em temporario (nucleo.
         preparar_escrita_atomica) - se isso falhar (disco cheio, por
         exemplo), nem o banco nem os arquivos reais foram tocados.
      3. so agora grava no banco (nucleo.registrar_contribuicoes) - se
         falhar, os temporarios ficam orfaos (nunca confirmados) e os
         arquivos reais continuam exatamente como estavam; rodar de novo
         com as mesmas respostas e seguro (idempotente por
         reuniao_id+cluster).
      4. so com o banco confirmado, troca os temporarios pelos arquivos
         reais (nucleo.confirmar_escrita_atomica) - essa troca e uma
         operacao de sistema de arquivos quase instantanea, a etapa com
         a menor chance de falhar de toda a sequencia.

    Devolve o dict de totais (pessoa -> peso) das pessoas afetadas.
    """
    clusters, falas = dados["clusters"], dados["falas"]

    for f in falas:
        f["falante"] = renomear.get(f["cluster"], f["falante"])
    _renomear_marcas(dados, renomear)
    for label, info in clusters.items():
        novo = renomear.get(label, info["nome"])
        # Ignorar apaga o nome - guarda quem era, para a tela Pessoas ainda
        # saber que essa pessoa estava na sala (servidor/pessoas.py). So
        # nome de pessoa: ignorar um DESCONHECIDO_ nao tem quem guardar.
        if novo.startswith("IGNORADO") and not info["nome"].startswith(
            ("IGNORADO", "DESCONHECIDO")
        ):
            info["nome_antes_de_ignorar"] = info["nome"]
        info["nome"] = novo
        info["confirmado"] = True
        if label in so_nomear and not novo.startswith("IGNORADO"):
            info["sem_aprender"] = True
        else:
            info.pop("sem_aprender", None)

    # Reconstroi dinamica/matriz/eventos/regioes a partir dos intervalos
    # crus + mapeamento de nomes atual, em vez de deixar nomes antigos
    # presos nessas estruturas (bug original: a revisao so trocava falas e
    # clusters, e a dinamica continuava com o nome sugerido de antes).
    if dados.get("turnos"):
        analise = interacao.recalcular([(a, b, q) for a, b, q in dados["turnos"]], clusters)
        dados["dinamica"] = analise["dinamica"]
        dados["matriz_interrupcoes"] = analise["matriz_interrupcoes"]
        dados["eventos"] = analise["eventos"]
        dados["regioes_sobrepostas"] = analise["regioes_sobrepostas"]
    else:
        dados.setdefault("avisos", []).append(erros.aviso("arquivo_sem_turnos"))

    # Reaproveita o exportador de TXT do pipeline.py (marcadores de "<- conferir"
    # e "[vozes sobrepostas]" inclusive) em vez de reescrever um TXT simples
    # que perdia essas informacoes.
    txt = caminho.with_suffix(".txt")
    texto_txt = pipeline.montar_texto_txt(
        falas,
        clusters,
        regioes=dados.get("regioes_sobrepostas"),
        lacunas=dados.get("lacunas_sem_texto"),
    )
    texto_json = nucleo.json_para_disco(dados)

    tmp_txt = nucleo.preparar_escrita_atomica(txt, texto_txt)
    try:
        tmp_json = nucleo.preparar_escrita_atomica(caminho, texto_json)
    except BaseException:
        tmp_txt.unlink(missing_ok=True)
        raise

    totais = {}
    try:
        if aprender or retirar:
            contribs = [
                (label, nome, emb, peso * FATOR_PESO_CONTRIBUICAO)
                for label, nome, emb, peso in aprender
            ]
            totais = nucleo.registrar_contribuicoes(reuniao_id, contribs, retirar)
    except BaseException:
        tmp_txt.unlink(missing_ok=True)
        tmp_json.unlink(missing_ok=True)
        raise

    nucleo.confirmar_escrita_atomica(tmp_txt, txt)
    nucleo.confirmar_escrita_atomica(tmp_json, caminho)

    return totais
