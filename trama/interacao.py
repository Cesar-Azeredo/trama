"""
interacao.py - Sobreposicao de fala, interrupcao e dinamica da reuniao.

Este modulo nao usa modelo novo. Ele le a diarizacao NAO-exclusiva que o
community-1 ja produz e que o pipeline vinha descartando: a versao exclusiva
forca um falante por instante, o que e conveniente para casar com o Whisper
mas apaga justamente a informacao de quem falou por cima de quem.

Tres conceitos, deliberadamente separados:

  APOIO       entrada curta enquanto o outro fala ("uhum", "sim", "claro").
              Nao e interrupcao - e sinal de escuta. Contar isso como
              interrupcao inflaria os numeros de quem so concorda em voz alta.

  INTERRUPCAO alguem entra falando e o que estava com a palavra CEDE em
              seguida.

              LEIA ISTO ANTES DE USAR O NUMERO: so com timing nao da para
              separar "A cedeu porque foi interrompido" de "A estava
              terminando e B antecipou". A contagem serve para comparar
              pessoas na MESMA reuniao, nao como acusacao. Se o numero for
              circular na empresa, confira o audio dos casos.

  DISPUTA     os dois falam ao mesmo tempo e nenhum cede logo. E aqui que a
              transcricao degringola, porque as vozes se misturam no sinal.
              Esta e a metrica mais confiavel do modulo: fala simultanea
              sustentada e bem definida e verificavel no audio.

Nenhum dos tres e julgamento de valor. Interromper pode ser colaborativo.
O modulo mede o que aconteceu, nao se foi bom.
"""

# Todos os limiares sao configuraveis por variavel de ambiente. Use o
# calibrar.py para escolher os valores com base no SEU audio, nao no chute de
# ninguem. Os padroes abaixo foram derivados da distribuicao real de pausas de
# uma reuniao de 70 min com 4 pessoas (mic de mesa).
import os

# Pausa maxima para tratar dois segmentos do mesmo falante como uma fala unica.
# A diarizacao fragmenta muito uma fala continua (respiracao, hesitacao).
GAP_MESCLAGEM = float(os.environ.get("GAP_MESCLAGEM", "0.5"))

# Sobreposicao minima para o evento existir.
#
# CUIDADO AO BAIXAR ISTO. Numa reuniao real, metade das sobreposicoes fica em
# torno de 0.6s, e isso e transicao NORMAL de turno: a pessoa comeca a falar um
# pouco antes da outra terminar. E cooperativo, nao interrupcao. Com 0.20 o
# modulo reportava 132 "interrupcoes" em 70 min - numero inflado por ruido de
# fronteira da diarizacao.
MIN_SOBREPOSICAO = float(os.environ.get("MIN_SOBREPOSICAO", "0.80"))

# Limiar SEPARADO para apoio. Um "uhum" de 0.4s tem, por definicao, no maximo
# 0.4s de sobreposicao - com o limiar de 0.80 a categoria desapareceria. Sao
# dois fenomenos distintos: tomada de palavra precisa de sobreposicao
# substancial para se distinguir de transicao normal; backchannel se identifica
# pela brevidade de quem entra enquanto o outro segue falando.
MIN_SOBREPOSICAO_APOIO = float(os.environ.get("MIN_SOBREPOSICAO_APOIO", "0.15"))

# Entrada mais curta que isto e apoio, nao tentativa de tomar a palavra.
MIN_ENTRADA = float(os.environ.get("MIN_ENTRADA", "0.60"))

# Se quem estava falando termina dentro desta janela apos a entrada do outro,
# consideramos que cedeu a palavra.
JANELA_CESSAO = float(os.environ.get("JANELA_CESSAO", "2.0"))


def mesclar_turnos(turnos, gap_max=GAP_MESCLAGEM):
    """
    [(inicio, fim, falante)] -> mesma lista com fragmentos do mesmo falante
    unidos quando separados por pausa curta.

    Sem isso, uma fala de 40s vira 15 "turnos" e qualquer contagem de
    interrupcao fica sem sentido.
    """
    por_falante = {}
    for ini, fim, quem in turnos:
        por_falante.setdefault(quem, []).append([float(ini), float(fim)])

    saida = []
    for quem, segs in por_falante.items():
        segs.sort()
        atual = list(segs[0])
        for ini, fim in segs[1:]:
            if ini - atual[1] <= gap_max:
                atual[1] = max(atual[1], fim)
            else:
                saida.append((atual[0], atual[1], quem))
                atual = [ini, fim]
        saida.append((atual[0], atual[1], quem))

    saida.sort()
    return saida


def sobreposicoes(turnos, min_dur=MIN_SOBREPOSICAO):
    """
    Intervalos em que dois ou mais falantes estao ativos ao mesmo tempo.

    Retorna [(inicio, fim, [falantes])] por varredura de eventos.
    """
    eventos = []
    for ini, fim, quem in turnos:
        eventos.append((ini, 1, quem))
        eventos.append((fim, -1, quem))
    # Fecha antes de abrir no mesmo instante: turnos que se tocam nao contam.
    eventos.sort(key=lambda e: (e[0], e[1]))

    ativos, regioes, inicio = set(), [], None
    for tempo, delta, quem in eventos:
        antes = len(ativos)
        ativos.add(quem) if delta == 1 else ativos.discard(quem)
        agora = len(ativos)

        if antes < 2 <= agora:
            inicio = tempo
            atores = set(ativos)
        elif antes >= 2 > agora and inicio is not None:
            if tempo - inicio >= min_dur:
                regioes.append((inicio, tempo, sorted(atores)))
            inicio = None
        elif agora >= 2 and inicio is not None:
            atores |= ativos

    return regioes


def eventos_de_fala(
    turnos,
    min_sobrep=MIN_SOBREPOSICAO,
    min_entrada=MIN_ENTRADA,
    janela_cessao=JANELA_CESSAO,
    min_sobrep_apoio=MIN_SOBREPOSICAO_APOIO,
):
    """
    Classifica cada encontro de vozes em apoio, interrupcao ou disputa.

    Retorna lista de dicts com: tempo, tipo, entrante, falava, sobreposicao_s.
    """
    turnos = sorted(turnos)
    eventos = []

    for i, (ini_a, fim_a, quem_a) in enumerate(turnos):
        for ini_b, fim_b, quem_b in turnos[i + 1 :]:
            if ini_b >= fim_a:
                break  # lista ordenada: nada adiante sobrepoe
            if quem_a == quem_b:
                continue

            ov = min(fim_a, fim_b) - ini_b
            dur_b = fim_b - ini_b

            if dur_b < min_entrada:
                # Apoio: entrada breve enquanto o outro SEGUE falando.
                if ov < min_sobrep_apoio or fim_b >= fim_a:
                    continue
                tipo = "apoio"
            else:
                # Tomada de palavra. Sobreposicao pequena aqui e transicao
                # normal de turno (a pessoa emenda no fim da fala do outro),
                # nao gente falando junto.
                if ov < min_sobrep:
                    continue
                tipo = "interrupcao" if fim_a - ini_b <= janela_cessao else "disputa"

            eventos.append(
                {
                    "tempo": round(ini_b, 2),
                    "tipo": tipo,
                    "entrante": quem_b,
                    "falava": quem_a,
                    "sobreposicao_s": round(ov, 2),
                }
            )

    eventos.sort(key=lambda e: e["tempo"])
    return eventos


def matriz_interrupcoes(eventos):
    """{quem_interrompeu: {quem_foi_interrompido: n}} - so interrupcoes."""
    m = {}
    for e in eventos:
        if e["tipo"] != "interrupcao":
            continue
        m.setdefault(e["entrante"], {})
        m[e["entrante"]][e["falava"]] = m[e["entrante"]].get(e["falava"], 0) + 1
    return m


def dinamica(turnos, eventos, regioes):
    """
    Metricas objetivas por falante. Nada de inferencia sobre estado emocional:
    tempo de fala, numero de turnos, duracao media, interrupcoes feitas e
    sofridas, apoios dados, tempo em sobreposicao.
    """
    stats = {}
    for ini, fim, quem in turnos:
        s = stats.setdefault(
            quem,
            {
                "fala_s": 0.0,
                "turnos": 0,
                "turno_medio_s": 0.0,
                "interrompeu": 0,
                "foi_interrompido": 0,
                "apoios": 0,
                "sobreposicao_s": 0.0,
            },
        )
        s["fala_s"] += fim - ini
        s["turnos"] += 1

    for e in eventos:
        if e["tipo"] == "interrupcao":
            stats.setdefault(e["entrante"], {}).setdefault("interrompeu", 0)
            stats[e["entrante"]]["interrompeu"] += 1
            stats.setdefault(e["falava"], {}).setdefault("foi_interrompido", 0)
            stats[e["falava"]]["foi_interrompido"] += 1
        elif e["tipo"] == "apoio":
            stats.setdefault(e["entrante"], {}).setdefault("apoios", 0)
            stats[e["entrante"]]["apoios"] += 1

    for ini, fim, atores in regioes:
        for quem in atores:
            if quem in stats:
                stats[quem]["sobreposicao_s"] += fim - ini

    total = sum(s["fala_s"] for s in stats.values()) or 1.0
    for s in stats.values():
        s["turno_medio_s"] = round(s["fala_s"] / max(s["turnos"], 1), 1)
        s["fala_s"] = round(s["fala_s"], 1)
        s["sobreposicao_s"] = round(s["sobreposicao_s"], 1)
        s["fala_pct"] = round(100.0 * s["fala_s"] / total, 1)
    return stats


def recalcular(turnos_brutos, mapa):
    """
    Reconstroi regioes/eventos/matriz/dinamica a partir dos INTERVALOS crus
    (label bruto da diarizacao) e do mapeamento label -> pessoa ATUAL.

    Substitui o antigo renomear(), que so trocava as chaves dos dicionarios
    JA calculados por label. Esse key-swap tinha dois bugs quando dois labels
    apontavam para a MESMA pessoa (diarizacao dividiu alguem em dois
    clusters, ou o revisao.py corrigiu dois clusters para o mesmo nome):

      1. `{nome(k): v for k, v in dic.items()}` e last-write-wins - as
         estatisticas de UM dos dois clusters eram silenciosamente
         descartadas (peso 20 sumia, so sobrava o 20 do outro).
      2. um evento de interrupcao/disputa ENTRE os dois clusters virava,
         depois da troca de chave, uma pessoa "interrompendo a si mesma".

    Aqui os turnos sao renomeados e RE-MESCLADOS (mesclar_turnos, que ja
    funde segmentos adjacentes ou sobrepostos do mesmo dono) ANTES de calcular
    qualquer coisa. Duas fontes do mesmo nome viram um intervalo so por
    trecho de fala - sem tempo de sobreposicao duplicado, e
    eventos_de_fala() ja pula pares com quem_a == quem_b, entao autoevento
    nao chega a existir.
    """

    def nome(label):
        return mapa.get(label, {}).get("nome", label)

    turnos = mesclar_turnos([(a, b, nome(q)) for a, b, q in turnos_brutos])
    regioes = sobreposicoes(turnos)
    eventos = eventos_de_fala(turnos)
    return {
        "turnos": turnos,
        "regioes_sobrepostas": [
            {"inicio": round(a, 2), "fim": round(b, 2), "falantes": q} for a, b, q in regioes
        ],
        "eventos": eventos,
        "matriz_interrupcoes": matriz_interrupcoes(eventos),
        "dinamica": dinamica(turnos, eventos, regioes),
    }


def analisar(diar_nao_exclusiva, iter_turns, mapa=None):
    """
    Ponto de entrada do pipeline.py. Recebe a diarizacao NAO-exclusiva e a funcao
    de iteracao, calcula os turnos crus (por label bruto) e delega o resto a
    recalcular(). `turnos_brutos` fica disponivel a parte porque o JSON
    precisa gravar os turnos POR LABEL (nao por nome) para o calibrar.py.
    """
    turnos_brutos = mesclar_turnos(
        [(t.start, t.end, label) for t, label in iter_turns(diar_nao_exclusiva)]
    )
    saida = recalcular(turnos_brutos, mapa or {})
    saida["turnos_brutos"] = turnos_brutos
    return saida


def em_sobreposicao(inicio, fim, regioes, min_fracao=0.25):
    """
    A fala cai numa regiao de vozes misturadas?

    Serve para marcar no transcript os trechos onde a transcricao e menos
    confiavel - e onde vale conferir o audio antes de citar alguem.
    """
    dur = max(fim - inicio, 1e-6)
    coberto = sum(max(0.0, min(fim, b) - max(inicio, a)) for a, b, _ in regioes)
    return (coberto / dur) >= min_fracao
