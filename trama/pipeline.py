"""
trama/pipeline.py - Pipeline completo: audio da reuniao -> transcricao com
nomes (antigo pipeline.py). A linha de comando mora em trama/cli/processar.py;
aqui fica so a biblioteca - processar() e as etapas que o servidor e os
testes usam direto.

Uso tipico (sabendo quem estava na sala - MUITO mais preciso):
    trama-processar reuniao.m4a --pessoas Joao,Maria,Pedro

Sem saber quem estava:
    trama-processar reuniao.m4a --max-falantes 6

Saidas:
    reuniao.txt   -> transcricao legivel com nomes
    reuniao.json  -> dados completos (usados pela revisao)
"""

import json
import os
import uuid
from pathlib import Path

import numpy as np

from trama import edicao, erros, interacao, nucleo, temporarios, termos, trechos
from trama.idioma import t

DIAR_MODEL = os.environ.get("DIAR_MODEL", "pyannote/speaker-diarization-community-1")

# Limiar de cosseno para aceitar uma identificacao.
# 0.60 e a calibracao real deste ambiente: 16 identificacoes em 4 reunioes
# (ver test_limiar_calibrado_separa_acertos_de_erros) separam acertos
# (0.83-0.95) de erros (0.26-0.36) com folga em torno de 0.60. Continua
# configuravel por variavel de ambiente para quem calibrar num audio/mic
# diferente - rode calibrar.py e confira a matriz de similaridade impressa
# abaixo antes de mudar o valor.
SIM_MIN = float(os.environ.get("SIM_MIN", "0.60"))

# Margem minima entre o 1o e o 2o colocado. Evita o caso classico de duas
# vozes parecidas onde o sistema "quase empata" e cravaria a errada.
MARGEM_MIN = float(os.environ.get("MARGEM_MIN", "0.06"))

# Abaixo disto, uma palavra individual entra em "palavras_baixa_confianca"
# da fala - so registro, nunca vira marca na tela por si so (ver
# LIMIAR_CONFIANCA_FALA: uma palavra isolada de baixa probabilidade, como
# "ta", da falso positivo com frequencia).
LIMIAR_PALAVRA_BAIXA_CONFIANCA = float(os.environ.get("LIMIAR_PALAVRA_BAIXA_CONFIANCA", "0.5"))

# Abaixo disto, a MEDIA de probabilidade das palavras de uma fala marca a
# fala inteira como baixa confianca na tela. Calibrado medindo a
# distribuicao real das medias por fala (reuniao_07 e reuniao_09) - ver
# ARCHITECTURE.md, secao de calibracao.
LIMIAR_CONFIANCA_FALA = float(os.environ.get("LIMIAR_CONFIANCA_FALA", "0.6"))

# Fala com menos palavras do que isto nao ganha a marca de confianca baixa,
# mesmo com confianca_media abaixo do limiar. Numa fala de 1-2 palavras nao
# existe media de verdade - a palavra unica incerta E o valor inteiro, e
# marcar isso e ruido (medido: quase metade das falas abaixo do limiar em
# reuniao_07/09 eram de 1-3 palavras como "Ok.", "Não.", "aqui" - o usuario
# aprende a ignorar a marca se ela dispara em cada bordao curto). Nao afeta
# o CALCULO de confianca_media nem palavras_baixa_confianca, so a decisao
# de MOSTRAR a marca da fala inteira - ver DetalheProcessado no frontend.
MIN_PALAVRAS_CONFIANCA_FALA = int(os.environ.get("MIN_PALAVRAS_CONFIANCA_FALA", "4"))

# Pausa minima, DENTRO de um turno ja ativo (mesma pessoa, sem trocar de
# falante), sem nenhum token do Whisper cobrindo o intervalo. Acima disto e
# lacuna real (respiracao longa, riso, gesto) que a transcricao nao
# capturou - nao e erro, e omissao honesta, entao e registrada em vez de
# desaparecer no texto colado. Nunca excede GAP_TURNO (2.0s): uma pausa
# maior que isso ja abre um turno novo antes de chegar aqui.
LIMIAR_LACUNA_S = float(os.environ.get("LIMIAR_LACUNA_S", "0.8"))

# Tolerancia numerica para "o turno cru da diarizacao cobre o intervalo da
# lacuna por completo" (ver turno_cru_unico_cobre em alinhar()). So absorve
# arredondamento entre os timestamps do Whisper e os da diarizacao - nao e
# um parametro para ajustar quantas lacunas aparecem.
TOLERANCIA_LACUNA_S = float(os.environ.get("TOLERANCIA_LACUNA_S", "0.05"))


def iter_turns(annotation):
    """Compatibilidade entre versoes do pyannote."""
    if hasattr(annotation, "itertracks"):
        for turn, _, label in annotation.itertracks(yield_label=True):
            yield turn, label
    else:
        for turn, label in annotation:
            yield turn, label


# --------------------------------------------------------------------------
# 1. diarizacao
# --------------------------------------------------------------------------


def diarizar(wav, device, num_speakers=None, min_speakers=None, max_speakers=None):
    # Aqui, nao no topo: quem so le resultados (o servidor) nunca carrega
    # torch/pyannote - ver o comentario em nucleo.py.
    import torch
    from pyannote.audio import Pipeline
    from pyannote.audio.pipelines.utils.hook import ProgressHook

    pipeline = Pipeline.from_pretrained(DIAR_MODEL, token=nucleo.HF_TOKEN)
    pipeline.to(torch.device(device))

    kwargs = {}
    if num_speakers:
        kwargs["num_speakers"] = num_speakers
    else:
        if min_speakers:
            kwargs["min_speakers"] = min_speakers
        if max_speakers:
            kwargs["max_speakers"] = max_speakers

    with ProgressHook() as hook:
        out = pipeline(wav, hook=hook, **kwargs)

    # 'exclusive' garante um unico falante ativo por instante, o que torna o
    # casamento com os timestamps do Whisper trivial. Novidade do community-1.
    exclusiva = getattr(out, "exclusive_speaker_diarization", None)
    if exclusiva is None:
        exclusiva = out.speaker_diarization
    return out.speaker_diarization, exclusiva


# --------------------------------------------------------------------------
# 2. identificacao dos clusters
# --------------------------------------------------------------------------


def identificar(wav, diar, galeria, device):
    """
    Atribui um nome a CADA CLUSTER (nao a cada trecho), de forma
    INDEPENDENTE: cada cluster e comparado contra a galeria e recebe o
    candidato de maior similaridade, sem excluir esse candidato dos demais
    clusters.

    Isso permite a MESMA pessoa em varios clusters - o cenario normal quando
    a diarizacao fragmenta uma pessoa em clusters diferentes (mudou de
    posicao, eco, distancia do mic). Atribuicao otima global (ex.: Hungaro),
    que forca no maximo uma pessoa por cluster, foi tentada e descartada: ela
    da a pessoa certa a UM cluster so e joga os outros em DESCONHECIDO (ou,
    pior, no nome errado) so para manter a exclusividade - o oposto do que se
    quer aqui.
    """
    clusters, embeddings, falas = _embeddings_por_cluster(wav, diar, device)
    labels = sorted(embeddings)
    nomes = sorted(galeria)
    if not labels or not nomes:
        return {
            label: _desconhecido(
                label, falas.get(label, 0.0), embeddings.get(label, np.zeros(1)).tolist()
            )
            for label in clusters
        }

    S = _similaridades(labels, nomes, embeddings, galeria)
    _imprimir_similaridades(S, labels, nomes)
    resultado = {
        label: _decidir(label, S[i], nomes, embeddings[label], falas.get(label, 0.0))
        for i, label in enumerate(labels)
    }
    for label in clusters:
        resultado.setdefault(label, _desconhecido(label, 0.0, []))
    return resultado


def _desconhecido(label, fala_s, embedding):
    return {
        "nome": f"DESCONHECIDO_{label}",
        "sim": 0.0,
        "margem": 0.0,
        "fala_s": fala_s,
        "embedding": embedding,
        "scores": {},
    }


def _embeddings_por_cluster(wav, diar, device):
    """(segmentos por cluster, embedding por cluster, segundos de fala por
    cluster). Cluster sem fala suficiente para embedding fica sem."""
    clusters = {}
    for turn, label in iter_turns(diar):
        clusters.setdefault(label, []).append(turn)
    embeddings, falas = {}, {}
    for label, segs in clusters.items():
        emb, dur = nucleo.embed_segments(wav, segs, device=device)
        if emb is not None:
            embeddings[label] = emb
            falas[label] = dur
    return clusters, embeddings, falas


def _similaridades(labels, nomes, embeddings, galeria):
    """Matriz cluster x pessoa de similaridade de cosseno."""
    S = np.zeros((len(labels), len(nomes)), dtype=np.float32)
    for i, label in enumerate(labels):
        for j, n in enumerate(nomes):
            S[i, j] = float(np.dot(embeddings[label], nucleo.l2(galeria[n])))
    return S


def _imprimir_similaridades(S, labels, nomes):
    print(t("similaridade"))
    print("    " + "".join(f"{n[:10]:>12}" for n in nomes))
    for i, label in enumerate(labels):
        print(f"    {label:<8}" + "".join(f"{S[i, j]:>12.3f}" for j in range(len(nomes))))


def _decidir(label, linha, nomes, embedding, fala_s):
    """Nome do cluster pela linha dele na matriz: o mais parecido, se a
    similaridade e a margem para o segundo passarem dos limiares."""
    j = int(np.argmax(linha))
    sim = float(linha[j])
    outros = [linha[k] for k in range(len(nomes)) if k != j]
    margem = float(sim - max(outros)) if outros else 1.0
    # Nao chuta. Se nao tem confianca, marca como desconhecido e deixa
    # voce resolver em 5 segundos na revisao.
    nome = nomes[j] if (sim >= SIM_MIN and margem >= MARGEM_MIN) else f"DESCONHECIDO_{label}"
    return {
        "nome": nome,
        "sim": round(sim, 4),
        "margem": round(margem, 4),
        "fala_s": round(fala_s, 1),
        "embedding": embedding.tolist(),
        "scores": {nomes[k]: round(float(linha[k]), 4) for k in range(len(nomes))},
    }


# --------------------------------------------------------------------------
# 3. transcricao
# --------------------------------------------------------------------------


def transcrever(wav, backend, modelo, idioma, prompt=None):
    """
    Devolve lista de palavras com timestamps:
    [{'start', 'end', 'word', 'probability'}, ...]

    'probability' vem de ambos os backends (confianca do decoder Whisper
    naquele token) - antes desta mudanca era extraida e descartada aqui
    mesmo. Usada em alinhar() para marcar falas de baixa confianca.
    """
    palavras = []

    if backend == "mlx":
        import mlx_whisper

        r = mlx_whisper.transcribe(
            wav,
            path_or_hf_repo=modelo,
            language=idioma,
            word_timestamps=True,
            condition_on_previous_text=False,
            initial_prompt=prompt,
        )
        for seg in r["segments"]:
            for w in seg.get("words", []):
                palavras.append(
                    {
                        "start": float(w["start"]),
                        "end": float(w["end"]),
                        "word": w["word"],
                        "probability": float(w["probability"]),
                    }
                )
    else:
        from faster_whisper import WhisperModel

        m = WhisperModel(modelo, device="cpu", compute_type="int8")
        segs, _ = m.transcribe(
            wav,
            language=idioma,
            word_timestamps=True,
            vad_filter=False,
            condition_on_previous_text=False,
            initial_prompt=prompt,
        )
        for seg in segs:
            for w in seg.words or []:
                palavras.append(
                    {
                        "start": float(w.start),
                        "end": float(w.end),
                        "word": w.word,
                        "probability": float(w.probability),
                    }
                )
    return palavras


# --------------------------------------------------------------------------
# 4. alinhamento palavra -> falante
# --------------------------------------------------------------------------


# Pausa a partir da qual comeca um turno novo mesmo sendo a mesma pessoa.
# Sem isso, uma fala as 00:01 e outra as 01:02 viravam um paragrafo unico
# com o timestamp da primeira - timestamp errado e trecho impossivel de
# marcar corretamente como sobreposto.
GAP_TURNO = 2.0

# Frase mais longa que isto provavelmente e Whisper sem pontuacao cobrindo
# varios falantes - o voto por frase seria pior que a atribuicao por palavra.
FRASE_MAX_S = 12.0

_FIM_DE_FRASE = (".", "?", "!", ":", ";")


def _turno_cru_unico_cobre(ini, fim, label, turnos_para_lacuna, tol=TOLERANCIA_LACUNA_S):
    """
    Uma lacuna so conta como "dentro de turno ativo" se existe UM turno
    de `turnos_para_lacuna` cobrindo o intervalo inteiro, com o MESMO
    label. Se o intervalo cruza a fronteira entre dois turnos do mesmo
    cluster (a diarizacao viu um turno terminar e outro comecar - por
    exemplo, perdeu e reencontrou a mesma voz - mesmo que os dois
    tenham o mesmo rotulo), a diarizacao NAO marcou a pessoa como
    ativa durante esse intervalo especifico: e um intervalo ENTRE dois
    turnos que o GAP_TURNO (2.0s, generoso de proposito para nao
    fragmentar paragrafos na tela exibida) mesclou na mesma fala - nao
    e omissao dentro de fala continua.

    REGRESSAO medida: sem esta checagem, ~40% das lacunas detectadas
    (reuniao_07/09) cruzavam fronteira de turno cru, inflando a
    contagem (ver ARCHITECTURE.md, secao de calibracao).
    """
    return any(
        lbl == label and a - tol <= ini and fim <= b + tol for a, b, lbl in turnos_para_lacuna
    )


def _dono(ini, fim, turnos):
    """Label com maior sobreposicao com [ini, fim]; sem sobreposicao, o
    mais perto."""
    melhor, melhor_ov = None, 0.0
    mais_perto, menor_dist = None, float("inf")
    for a, b, label in turnos:
        ov = min(fim, b) - max(ini, a)
        if ov > melhor_ov:
            melhor, melhor_ov = label, ov
        dist = 0.0 if ov > 0 else min(abs(ini - b), abs(a - fim))
        if dist < menor_dist:
            mais_perto, menor_dist = label, dist
    return melhor or mais_perto


def _dono_do_instante(t, turnos):
    """
    So para token de duracao zero (start == end). "_dono()" mede
    sobreposicao de DURACAO - com duracao zero, a sobreposicao e
    sempre exatamente 0 nunca > 0, entao a palavra cai direto no
    desempate por proximidade e pode empatar exatamente entre dois
    turnos (a distancia ate o inicio de um e ate o fim do outro
    e a mesma), vencendo por ordem de lista - um artefato, nao uma
    medicao. Aqui e so contencao: o turno tem que cobrir o instante
    de verdade. Ninguem cobrindo, a atribuicao e None (indefinida).
    """
    contidos = [label for a, b, label in turnos if a <= t < b]
    return contidos[0] if contidos else None


def _atribuir_donos(palavras, turnos):
    for p in palavras:
        p["_label"] = _dono(p["start"], p["end"], turnos)
        # Guarda o dono ORIGINAL por palavra antes da consolidacao por
        # frase sobrescrever "_label" com o vencedor - e o dado que a tela
        # usa para marcar quem realmente disse aquela palavra, quando
        # difere de quem ganhou a frase (ver _marcar_palavra).
        # Token de duracao zero usa a contencao estrita (_dono_do_instante),
        # nunca o desempate por proximidade de _dono() - None quando nenhum
        # turno cobre o instante, para NAO virar divergencia.
        if p["end"] == p["start"]:
            p["_dono"] = _dono_do_instante(p["start"], turnos)
        else:
            p["_dono"] = p["_label"]


def _frases(palavras):
    frases, atual = [], []
    for p in palavras:
        atual.append(p)
        if p["word"].rstrip().endswith(_FIM_DE_FRASE):
            frases.append(atual)
            atual = []
    if atual:
        frases.append(atual)
    return frases


def _consolidar_por_frase(palavras):
    """Uma frase pertence a uma pessoa so: voto ponderado na duracao."""
    for fr in _frases(palavras):
        if fr[-1]["end"] - fr[0]["start"] > FRASE_MAX_S:
            continue
        votos = {}
        for p in fr:
            votos[p["_label"]] = votos.get(p["_label"], 0.0) + (p["end"] - p["start"])
        vencedor = max(votos, key=votos.get)
        for p in fr:
            p["_label"] = vencedor


def _juntar(texto, token):
    if not texto:
        return token.lstrip()
    if token[:1].isspace() or texto[-1:].isspace():
        return texto + token
    if token[:1] in ",.!?;:)%-/'’":
        return texto + token
    if texto[-1:] in "-/'’":
        return texto + token
    return texto + " " + token


def _novo_turno(nome, p):
    return {
        "falante": nome,
        "cluster": p["_label"],
        "inicio": p["start"],
        "fim": p["end"],
        "texto": p["word"].lstrip(),
        "_divergentes": [],
        "_soma_prob": 0.0,
        "_n_prob": 0,
        "_baixa_confianca": [],
        "_lacunas": [],
        "_tempos": [],
    }


def _anotar_lacuna(turno, fim_do_anterior, p, turnos_para_lacuna):
    """
    Lacuna: dentro do MESMO turno (nao houve troca de falante nem pausa
    longa o bastante pra abrir um turno novo), sem nenhum token cobrindo
    o intervalo. Por isso o gap nunca passa de GAP_TURNO: se passasse, um
    turno novo ja teria sido aberto. Mas isso so garante que a FALA
    EXIBIDA continuou a mesma - o turno CRU da diarizacao por baixo pode
    ja ter terminado e comecado outro (mesmo rotulo) dentro desse
    intervalo; _turno_cru_unico_cobre exige um turno cru SO cobrindo tudo,
    senao a lacuna e fronteira entre dois turnos crus, nao omissao dentro
    de um.
    """
    gap = p["start"] - fim_do_anterior
    if gap <= LIMIAR_LACUNA_S or not _turno_cru_unico_cobre(
        fim_do_anterior, p["start"], turno["cluster"], turnos_para_lacuna
    ):
        return
    turno["_lacunas"].append(
        {
            # Posicao em CARACTERES dentro de "texto" (mesma convencao de
            # palavras_divergentes/palavras_baixa_confianca) - onde a tela
            # insere a marca "[som nao transcrito]" no meio do texto
            # corrido. Seguro tomar len(turno["texto"]) aqui: o primeiro
            # token de um turno ja nasce sem espaco a frente (.lstrip() na
            # criacao), entao nenhum strip() posterior em montar_saida
            # desloca posicoes anteriores ao ultimo token.
            "posicao": len(turno["texto"]),
            "inicio": round(fim_do_anterior, 2),
            "fim": round(p["start"], 2),
            "falante": turno["falante"],
            "cluster": turno["cluster"],
        }
    )


def _acrescentar(turno, p):
    """Junta a palavra ao texto do turno. Devolve (posicao, texto_palavra)."""
    antes = turno["texto"]
    turno["fim"] = p["end"]
    turno["texto"] = _juntar(antes, p["word"])
    # O que "_juntar" acrescentou pode vir com espaco na frente (do
    # proprio token ou inserido por _juntar) - a posicao da palavra em si
    # comeca depois desse espaco.
    acrescido = turno["texto"][len(antes) :]
    texto_palavra = acrescido.lstrip()
    return len(antes) + (len(acrescido) - len(texto_palavra)), texto_palavra


def _marcar_palavra(turno, p, posicao, texto_palavra, mapa):
    """Marcas por palavra, todas em posicao de caractere dentro de "texto"."""
    # A palavra pertence de fato a quem "_dono()" deu a ela (_dono), mas a
    # frase inteira foi para o vencedor do voto (_label). Divergem so na
    # sobreposicao de fala, exatamente onde a atribuicao por palavra e
    # menos confiavel - por isso isto e pista, nao correcao (ver
    # ARCHITECTURE.md/tela de detalhe). "_dono" None (token de duracao zero
    # fora de qualquer turno) nunca vira divergencia - indefinido nao e
    # pista de ninguem, e ausente tem que continuar ausente.
    if p["_dono"] is not None and p["_dono"] != p["_label"]:
        turno["_divergentes"].append(
            {
                "posicao": posicao,
                "comprimento": len(texto_palavra),
                "falante": mapa.get(p["_dono"], {}).get("nome", "DESCONHECIDO"),
                # O cluster, alem do nome: a revisao renomeia por ele
                # (revisao.aplicar_e_gravar) - pelo nome so, dois clusters
                # com o mesmo nome sugerido seriam indistinguiveis.
                "cluster": p["_dono"],
            }
        )

    # Intervalo de CADA palavra: [posicao, comprimento, inicio, fim]. E o
    # que deixa a tela marcar, palavra por palavra, o trecho de uma fala
    # que caiu dentro de uma regiao de sobreposicao (regioes_sobrepostas) -
    # so com inicio/fim da fala inteira, nao ha como saber ONDE no
    # paragrafo a outra pessoa entrou.
    if texto_palavra:
        turno["_tempos"].append(
            [posicao, len(texto_palavra), round(p["start"], 2), round(p["end"], 2)]
        )

    # Probabilidade do decoder Whisper para este token. Ausente (dados de
    # teste antigos, ou um backend sem a chave) e so ignorado -
    # confianca_media so aparece quando ha pelo menos uma palavra medida.
    prob = p.get("probability")
    if prob is None:
        return
    turno["_soma_prob"] += prob
    turno["_n_prob"] += 1
    if prob < LIMIAR_PALAVRA_BAIXA_CONFIANCA:
        turno["_baixa_confianca"].append(
            {
                "posicao": posicao,
                "comprimento": len(texto_palavra),
                "probabilidade": round(prob, 3),
            }
        )


def _agrupar_em_turnos(palavras, mapa, turnos_para_lacuna):
    falas, turno, fim_anterior = [], None, None
    for p in palavras:
        nome = mapa.get(p["_label"], {}).get("nome", "DESCONHECIDO")
        pausou = fim_anterior is not None and p["start"] - fim_anterior > GAP_TURNO
        # A troca de turno tem de olhar o CLUSTER, nao so o nome exibido.
        # Se so olhasse o nome, dois clusters diferentes que calham de
        # mostrar o mesmo nome (a mesma pessoa dividida em dois clusters
        # pela diarizacao, ou dois clusters corrigidos na revisao para a
        # mesma pessoa) virariam UMA fala so com o "cluster" do primeiro -
        # e uma correcao posterior num dos dois clusters silenciosamente
        # deixaria de alcancar as palavras que vieram do outro.
        if turno is None or turno["falante"] != nome or turno["cluster"] != p["_label"] or pausou:
            turno = _novo_turno(nome, p)
            falas.append(turno)
            posicao, texto_palavra = 0, turno["texto"]
        else:
            _anotar_lacuna(turno, fim_anterior, p, turnos_para_lacuna)
            posicao, texto_palavra = _acrescentar(turno, p)
        fim_anterior = p["end"]
        _marcar_palavra(turno, p, posicao, texto_palavra, mapa)
    return falas


def _finalizar(falas):
    """Tira os campos de trabalho, grava as marcas que existirem e
    descarta fala vazia (com as lacunas dela). Devolve (falas, lacunas)."""
    lacunas = []
    for f in falas:
        f["texto"] = f["texto"].strip()
        for campo, destino in (
            ("_divergentes", "palavras_divergentes"),
            ("_baixa_confianca", "palavras_baixa_confianca"),
        ):
            marcas = f.pop(campo)
            if marcas:
                f[destino] = marcas
        soma_prob, n_prob = f.pop("_soma_prob"), f.pop("_n_prob")
        if n_prob:
            f["confianca_media"] = round(soma_prob / n_prob, 3)
        f["palavras_tempo"] = f.pop("_tempos")
        lacunas_turno = f.pop("_lacunas")
        if f["texto"]:
            lacunas.extend(lacunas_turno)
    return [f for f in falas if f["texto"]], lacunas


def alinhar(palavras, diar_exclusiva, mapa, turnos_ativos=None):
    """
    Atribui cada palavra ao falante com maior sobreposicao temporal, e depois
    consolida por FRASE.

    Por que consolidar: os limites de turno da diarizacao ficam alguns decimos
    atrasados em relacao ao inicio real da fala, entao a primeira palavra do
    novo falante cai dentro do segmento do anterior. O sintoma e turno comecando
    em minuscula ("acho que...") com o "Eu" preso no turno de outra pessoa.
    Uma frase pertence a uma pessoa so, decidida por voto ponderado na duracao.

    `turnos_ativos`: [(inicio, fim, label_cru), ...] usados SO para decidir
    se uma lacuna esta "dentro de turno ativo" (ver turno_cru_unico_cobre) -
    o pipeline.py passa analise["turnos_brutos"] (interacao.py, diarizacao
    NAO-exclusiva mesclada por GAP_MESCLAGEM=0.5). Nao usa a exclusiva
    (diar_exclusiva, usada para o resto desta funcao) de proposito: a
    exclusiva forca UM falante por instante, e durante fala sobreposta
    esse desempate pode alternar entre os dois falantes so por artefato do
    algoritmo, fragmentando quem na verdade nao parou de falar. A
    nao-exclusiva mede presenca de voz sem essa exclusividade forcada - o
    sinal mais fiel a pergunta "esta pessoa estava mesmo ativa aqui".
    None (chamador antigo/teste sem a analise de interacao) usa a propria
    `turnos` (exclusiva) como fallback, entao os testes que so tem UMA
    fonte de diarizacao continuam validos.
    """
    turnos = sorted((t.start, t.end, label) for t, label in iter_turns(diar_exclusiva))
    turnos_para_lacuna = sorted(turnos_ativos) if turnos_ativos is not None else turnos
    if not palavras:
        return [], []
    _atribuir_donos(palavras, turnos)
    _consolidar_por_frase(palavras)
    return _finalizar(_agrupar_em_turnos(palavras, mapa, turnos_para_lacuna))


def montar_texto_txt(falas, mapa, regioes=None, lacunas=None):
    """
    So monta o texto (string pura, nada de disco) - separado de
    escrever_txt para quem precisa preparar o conteudo ANTES de decidir
    gravar (a revisao prepara .txt e .json em temporario antes de tocar o
    banco; so escreve de verdade depois que o banco confirmar).

    Marcadores no fim da linha, nunca no meio do texto - assim o transcript
    continua colavel numa IA sem que os avisos poluam o conteudo.

      <- conferir        identificacao com similaridade baixa
      [vozes sobrepostas]  trecho onde duas pessoas falavam junto, entao a
                           transcricao e menos confiavel

    `lacunas`: lacunas_sem_texto da reuniao - o que alguem escreveu numa
    lacuna (trechos para conferir, ADR 0028) entra no texto da fala, no
    ponto dela.
    """
    regioes_tuplas = [(r["inicio"], r["fim"], r["falantes"]) for r in regioes] if regioes else []
    linhas = []
    for f in falas:
        info = mapa.get(f["cluster"], {})
        marcas = []
        if not info.get("confirmado") and info.get("sim", 0.0) < SIM_MIN + 0.1:
            marcas.append("<- conferir")
        if regioes_tuplas and interacao.em_sobreposicao(f["inicio"], f["fim"], regioes_tuplas):
            marcas.append("[vozes sobrepostas]")
        sufixo = ("  " + "  ".join(marcas)) if marcas else ""
        texto = trechos.texto_com_lacunas_escritas(f, lacunas)
        linhas.append(f"[{nucleo.hhmmss(f['inicio'])}] {f['falante']}: {texto}{sufixo}")
    return "\n".join(linhas)


def escrever_txt(falas, mapa, destino, regioes=None, lacunas=None):
    nucleo.escrever_atomico(destino, montar_texto_txt(falas, mapa, regioes, lacunas))


def imprimir_dinamica(analise):
    """
    Metricas objetivas. Nada aqui infere estado emocional - sao contagens de
    tempo e de eventos, que voce pode conferir no audio.
    """
    din = analise["dinamica"]
    if not din:
        return

    # (titulo, largura, alinhamento). Cada coluna e unida a proxima por um
    # separador LITERAL de 2 espacos (ver "linha" abaixo) - REGRESSAO:
    # antes, os campos so tinham largura minima (":>N") e nada de
    # separador nenhum entre eles; um valor com N digitos ou mais some com
    # o espaco de sobra e gruda no campo seguinte ("823" para SOFREU=8,
    # APOIOS=23). Um separador literal nao depende de sobra de largura.
    titulos = t("colunas_dinamica").split("|")
    larguras = [(14, "<"), (8, ">"), (6, ">"), (7, ">"), (7, ">"), (8, ">"), (7, ">"), (7, ">")]
    colunas = [(titulo, larg, alin) for titulo, (larg, alin) in zip(titulos, larguras)]

    def linha(celulas):
        return "  ".join(f"{v:{alin}{larg}}" for v, (_, larg, alin) in zip(celulas, colunas))

    print(t("dinamica"))
    print(f"    {linha([titulo for titulo, _, _ in colunas])}")
    for nome, s in sorted(din.items(), key=lambda kv: -kv[1]["fala_s"]):
        celulas = [
            nome,
            f"{s['fala_s']:.0f}s",
            f"{s['fala_pct']:.1f}",
            str(s["turnos"]),
            f"{s['turno_medio_s']:.1f}s",
            str(s["interrompeu"]),
            str(s["foi_interrompido"]),
            str(s["apoios"]),
        ]
        print(f"    {linha(celulas)}")

    m = analise["matriz_interrupcoes"]
    if m:
        print(t("quem_interrompeu"))
        for quem, alvos in sorted(m.items()):
            for alvo, n in sorted(alvos.items(), key=lambda kv: -kv[1]):
                print(f"    {quem} -> {alvo}: {n}x")

    disputas = [e for e in analise["eventos"] if e["tipo"] == "disputa"]
    if disputas:
        total = sum(e["sobreposicao_s"] for e in disputas)
        print(t("disputas", n=len(disputas), total=f"{total:.0f}"))
        for e in sorted(disputas, key=lambda x: -x["sobreposicao_s"])[:5]:
            print(
                f"    {nucleo.hhmmss(e['tempo'])}  {e['entrante']} x "
                f"{e['falava']}  ({e['sobreposicao_s']:.1f}s)"
            )


def montar_saida(
    caminho_audio,
    wav16k,
    mapa,
    falas,
    analise,
    reuniao_id=None,
    lacunas=None,
    device=None,
    asr=None,
    metadados=None,
):
    """
    Monta o dict gravado em <saida>.json. Separado de main() para ser
    testavel sem rodar diarizacao/transcricao de verdade.

    Grava sim_min/margem_min - o limiar EM VIGOR nesta execucao, nao um
    valor generico. Sem isso, a tela de revisao (servidor/reunioes.py)
    nao tem como saber se uma reuniao antiga foi calibrada com um limiar
    diferente do de hoje; ela so pode mostrar o limiar atual, marcado
    como tal, nunca fingir que era o mesmo de quando a reuniao rodou.

    `reuniao_id`: passe o id de uma execucao anterior (ver
    preservar_reuniao_id) ao REPROCESSAR o mesmo audio. Sem argumento,
    gera um novo - o caso normal de uma reuniao inedita.

    `lacunas`: segundo elemento devolvido por alinhar() - trechos DENTRO de
    um turno ativo sem nenhum token do Whisper (ver LIMIAR_LACUNA_S). None
    (chamador que ainda nao roda alinhar() com a versao nova) vira lista
    vazia, nao ausencia - e um campo sempre presente em reuniao processada
    por esta versao, como "eventos"/"regioes_sobrepostas".

    `device`/`asr`: o par usado NESTA execucao (--device/--asr do CLI, ou
    o que o servidor decidiu automaticamente no marco 2 - ver
    servidor/processamento.py). None (chamador que nao informou) fica de
    fora do dict - ausente e ausente, igual sim_min/margem_min para
    reunioes de antes deles existirem. Motivo de gravar quando informado:
    mlx (Apple Silicon) e faster_whisper (CPU) tem caracteristicas de
    transcricao diferentes - comparar duas reunioes sem saber qual rodou
    em qual pode levar a conclusao errada.
    """
    saida = {
        "audio": str(Path(caminho_audio).resolve()),
        # Identidade estavel da reuniao, independente do caminho do arquivo
        # (que pode mudar de pasta/nome). O revisao.py usa isto como chave do
        # ledger de contribuicoes de voz - sem ela, revisar o mesmo audio
        # duas vezes com o JSON movido de lugar pareceria "uma reuniao nova".
        "reuniao_id": reuniao_id or str(uuid.uuid4()),
        "wav16k": wav16k,
        "clusters": mapa,
        "falas": falas,
        # Turnos crus (por LABEL da diarizacao, antes de qualquer nome) vao
        # para o JSON para o calibrar.py poder varrer limiares offline, sem
        # reprocessar o audio, e para o revisao.py poder recalcular
        # dinamica/eventos/regioes apos uma correcao de nome.
        "turnos": [[round(a, 3), round(b, 3), q] for a, b, q in analise["turnos_brutos"]],
        "dinamica": analise["dinamica"],
        "matriz_interrupcoes": analise["matriz_interrupcoes"],
        "eventos": analise["eventos"],
        "regioes_sobrepostas": analise["regioes_sobrepostas"],
        "lacunas_sem_texto": lacunas or [],
        "sim_min": SIM_MIN,
        "margem_min": MARGEM_MIN,
        "limiar_confianca_fala": LIMIAR_CONFIANCA_FALA,
        "min_palavras_confianca_fala": MIN_PALAVRAS_CONFIANCA_FALA,
    }
    # titulo, data_reuniao, data_origem (preservar_metadados) - ausentes
    # ficam ausentes, nunca string vazia.
    saida.update(metadados or {})
    if device is not None:
        saida["device_usado"] = device
    if asr is not None:
        saida["asr_usado"] = asr
    return saida


def carregar_saida_anterior(caminho_json):
    """
    Le o .json de uma execucao anterior para ESTE MESMO destino, se
    existir. None na primeira vez que a reuniao e processada - so faz
    sentido preservar algo de uma rodada anterior quando ela existiu.
    """
    p = Path(caminho_json)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def preservar_reuniao_id(dados_anteriores):
    """
    Reprocessar e reprocessar o AUDIO, nao criar uma reuniao nova. Sem
    isto, cada rodada gerava um reuniao_id novo (uuid4 em montar_saida) e
    uma revisao ja feita - o ledger de vozes e idempotente por
    reuniao_id+cluster (ver revisao.aplicar_e_gravar) - deixava de
    reconhecer a reuniao como a mesma. A proxima revisao duplicava o
    aprendizado de voz das mesmas pessoas, silenciosamente.
    """
    if dados_anteriores and dados_anteriores.get("reuniao_id"):
        return dados_anteriores["reuniao_id"]
    return None


def preservar_metadados(dados_anteriores, caminho_audio):
    """
    Titulo e data da reuniao, que o reprocessamento nunca pode apagar -
    mesma regra do reuniao_id (preservar_reuniao_id) e da revisao
    (preservar_revisao).

    titulo: o do .json anterior; sem .json anterior, o que a Nova reuniao
    gravou em meta.json (nucleo.NOME_META_REUNIAO). Sem nenhum, ausente - a
    tela mostra "Reuniao NN".

    data: a do .json anterior, se veio da gravacao (creation_time). Senao
    le de novo (nucleo.data_da_gravacao) - um arquivo que antes so tinha a
    data de modificacao pode ter sido substituido pelo original com
    metadado; e se a leitura falhar, fica a anterior, nunca nada.
    """
    anterior = dados_anteriores or {}
    meta = {}
    titulo = anterior.get("titulo")
    if titulo is None:
        titulo = nucleo.ler_meta_reuniao(Path(caminho_audio).parent).get("titulo")
    if titulo:
        meta["titulo"] = titulo

    if anterior.get("data_reuniao") and anterior.get("data_origem") == "gravacao":
        meta["data_reuniao"] = anterior["data_reuniao"]
        meta["data_origem"] = "gravacao"
    else:
        nova = nucleo.data_da_gravacao(caminho_audio)
        if nova:
            meta["data_reuniao"], meta["data_origem"] = nova["data"], nova["origem"]
        elif anterior.get("data_reuniao"):
            meta["data_reuniao"] = anterior["data_reuniao"]
            meta["data_origem"] = anterior.get("data_origem", "arquivo")
    return meta


def preservar_confirmacoes(mapa, dados_anteriores):
    """
    Reprocessar nao desfaz uma revisao humana que continua valida.
    Compara por NOME, nao por label de cluster - a diarizacao pode
    renumerar SPEAKER_XX entre rodadas (a ordem de clusterizacao nao e
    garantida), entao o cluster novo que resolveu para o MESMO nome de
    um cluster confirmado antes herda o "confirmado". Nome diferente (ou
    pessoa que antes nao tinha confirmacao) fica sem - a revisao anterior
    era sobre outra identificacao, nao vale mais para esta.

    Muta `mapa` no lugar; sem dados_anteriores, e um no-op.
    """
    if not dados_anteriores:
        return
    nomes_confirmados = {
        info.get("nome")
        for info in dados_anteriores.get("clusters", {}).values()
        if info.get("confirmado") and info.get("nome")
    }
    for info in mapa.values():
        if info.get("nome") in nomes_confirmados:
            info["confirmado"] = True


# Casamento cluster novo <-> cluster antigo ao reprocessar (preservar_revisao).
# Metade da fala dos DOIS tem de ser o mesmo trecho de audio; e o cluster
# novo nao pode ter mais que isto de fala de OUTRO cluster antigo - senao e
# uma mistura, e herdar a decisao antiga nele seria confirmar em silencio
# um cluster que ninguem ouviu.
FRACAO_MIN_CASAMENTO = 0.5
FRACAO_MAX_MISTURA = 0.2


def _intervalos_por_label(turnos):
    por = {}
    for a, b, q in turnos:
        por.setdefault(q, []).append((float(a), float(b)))
    return {q: sorted(v) for q, v in por.items()}


def _sobreposicao(xs, ys):
    """Segundos em comum entre duas listas ordenadas de intervalos."""
    total, i, j = 0.0, 0, 0
    while i < len(xs) and j < len(ys):
        a = max(xs[i][0], ys[j][0])
        b = min(xs[i][1], ys[j][1])
        if b > a:
            total += b - a
        if xs[i][1] < ys[j][1]:
            i += 1
        else:
            j += 1
    return total


def _intersecao(xs, ys):
    """Intervalos em comum entre duas listas ordenadas de intervalos."""
    saida, i, j = [], 0, 0
    while i < len(xs) and j < len(ys):
        a = max(xs[i][0], ys[j][0])
        b = min(xs[i][1], ys[j][1])
        if b > a:
            saida.append((a, b))
        if xs[i][1] < ys[j][1]:
            i += 1
        else:
            j += 1
    return saida


def casar_clusters(turnos_novos, turnos_antigos):
    """
    {label_novo: label_antigo} dos clusters que sao o MESMO trecho de audio
    nas duas rodadas - pela sobreposicao no tempo dos turnos crus, nunca
    pelo nome sugerido (que pode mudar, ou ser justamente o que a revisao
    corrigiu) nem pelo numero do label (a diarizacao renumera).

    Um-para-um, do par com mais tempo em comum para o de menos. So casa se
    o tempo em comum passar de FRACAO_MIN_CASAMENTO da fala de cada um, e
    se o cluster novo nao tiver mais que FRACAO_MAX_MISTURA de fala de
    algum OUTRO cluster antigo em que o casado estava calado. Cluster novo
    sem par nao herda nada: vai para "A revisar".
    """
    novos = _intervalos_por_label(turnos_novos)
    antigos = _intervalos_por_label(turnos_antigos)

    def dur(xs):
        return sum(b - a for a, b in xs)

    comum = {(n, a): _sobreposicao(novos[n], antigos[a]) for n in novos for a in antigos}
    casamento, usados = {}, set()
    for (n, a), comum_s in sorted(comum.items(), key=lambda kv: -kv[1]):
        if n in casamento or a in usados or comum_s <= 0:
            continue
        if comum_s < FRACAO_MIN_CASAMENTO * dur(novos[n]) or comum_s < FRACAO_MIN_CASAMENTO * dur(
            antigos[a]
        ):
            continue

        # Mistura = o cluster novo falando junto com OUTRO antigo enquanto o
        # antigo casado estava calado. Fala sobreposta (duas pessoas ao mesmo
        # tempo) nao conta: nela os dois antigos estao ativos, e contar isso
        # reprovava a reuniao_02 casada consigo mesma.
        def mistura(o):
            com_o = _intersecao(novos[n], antigos[o])
            return dur(com_o) - _sobreposicao(com_o, antigos[a])

        if any(mistura(o) > FRACAO_MAX_MISTURA * dur(novos[n]) for o in antigos if o != a):
            continue
        casamento[n] = a
        usados.add(a)
    return casamento


def preservar_revisao(mapa, turnos_novos, dados_anteriores):
    """
    Reprocessar nao desfaz uma revisao humana. Cada cluster novo casado
    (casar_clusters) com um cluster JA DECIDIDO na revisao herda a decisao
    inteira:

      nome dado na revisao (inclusive corrigido, ou dado a um
      DESCONHECIDO) + confirmado; "so nomear" (sem_aprender); ignorado
      (vira IGNORADO_<label novo>, com nome_antes_de_ignorar).

    Muta `mapa` no lugar. Devolve {label_antigo: label_novo} dos casados -
    o ledger de vozes e indexado por (reuniao_id, label), e o label pode
    ter mudado (ver nucleo.remapear_contribuicoes).

    Execucao anterior sem "turnos" (schema antigo) nao tem como casar por
    tempo: cai no casamento por nome de antes (preservar_confirmacoes) e
    devolve None - nao ha remapeamento que se saiba fazer (None, nao {}:
    {} diria "nada casou" e mandaria todo o ledger da reuniao para orfao).
    """
    if not dados_anteriores:
        return None
    if not dados_anteriores.get("turnos"):
        preservar_confirmacoes(mapa, dados_anteriores)
        return None
    antigos = dados_anteriores.get("clusters", {})
    casamento = casar_clusters(turnos_novos, dados_anteriores["turnos"])
    for novo, antigo in casamento.items():
        info, velho = mapa.get(novo), antigos.get(antigo)
        if info is None or not velho or not velho.get("confirmado"):
            continue
        info["confirmado"] = True
        if velho["nome"].startswith("IGNORADO"):
            # Quem era: o que a revisao guardou; ignorado antes de o campo
            # existir, quem o pipeline identifica agora - nunca um rotulo
            # de maquina (DESCONHECIDO_ nao e "quem estava na sala").
            antes = velho.get("nome_antes_de_ignorar") or info["nome"]
            info.pop("nome_antes_de_ignorar", None)
            if not antes.startswith(("DESCONHECIDO", "IGNORADO")):
                info["nome_antes_de_ignorar"] = antes
            info["nome"] = f"IGNORADO_{novo}"
            continue
        info["nome"] = velho["nome"]
        if velho.get("sem_aprender"):
            info["sem_aprender"] = True
    return {antigo: novo for novo, antigo in casamento.items()}


# --------------------------------------------------------------------------


def faixa_de_falantes(falantes, min_falantes, max_falantes, pessoas):
    """
    Quantos falantes a diarizacao procura - kwargs de diarizar().

    --falantes fixa o numero. Senao, uma faixa (--min-falantes/
    --max-falantes) vale como faixa, mesmo com --pessoas: quem estava na
    sala nao e quem falou - alguem pode ter so ouvido, e forcar um grupo
    por nome divide outra pessoa em dois. Nesse caso --pessoas so restringe
    a comparacao de voz a esses nomes. Sem numero e sem faixa, o numero de
    nomes vira o numero exato (o comportamento de sempre).
    """
    if falantes:
        return {"num_speakers": falantes}
    if min_falantes or max_falantes:
        faixa = {}
        if min_falantes:
            faixa["min_speakers"] = min_falantes
        if max_falantes:
            faixa["max_speakers"] = max_falantes
        return faixa
    if pessoas:
        return {"num_speakers": len(pessoas)}
    return {}


def descrever_faixa(faixa):
    if "num_speakers" in faixa:
        return t("faixa_exata", n=faixa["num_speakers"])
    minimo, maximo = faixa.get("min_speakers"), faixa.get("max_speakers")
    if minimo and maximo:
        return t("faixa_entre", min=minimo, max=maximo)
    if minimo:
        return t("faixa_min", min=minimo)
    if maximo:
        return t("faixa_max", max=maximo)
    return ""


MODELO_PADRAO = "mlx-community/whisper-large-v3-mlx"

# Progresso para maquina (o servidor, servidor/processamento.py): com
# PROGRESSO_MAQUINA ligado (--progresso-json na CLI), cada etapa imprime,
# alem da frase para quem le o terminal, uma linha
#   @progresso {"etapa": 2, "total": 5, "detalhe": {"min": 4, "max": 5}}
# O servidor le so isto - nunca a frase, que muda de idioma.
PREFIXO_PROGRESSO = "@progresso "
TOTAL_ETAPAS = 5
PROGRESSO_MAQUINA = False


def _progresso(etapa, frase, **detalhe):
    print(frase, flush=True)
    if PROGRESSO_MAQUINA:
        dados = {"etapa": etapa, "total": TOTAL_ETAPAS, "detalhe": detalhe}
        print(PREFIXO_PROGRESSO + json.dumps(dados), flush=True)


def detalhe_da_faixa(faixa):
    """Os numeros de faixa_de_falantes como o progresso os manda."""
    nomes = {"num_speakers": "falantes", "min_speakers": "min", "max_speakers": "max"}
    return {nomes[k]: v for k, v in faixa.items() if k in nomes}


def _imprimir_identificacao(mapa):
    print(t("identificacao"))
    for label, info in sorted(mapa.items()):
        print(
            t(
                "linha_identificacao",
                label=label,
                nome=info["nome"],
                sim=f"{info['sim']:.3f}",
                margem=f"{info['margem']:.3f}",
                fala=f"{info['fala_s']:.0f}",
            )
        )


def _identificar_com_revisao_anterior(wav, diar, pessoas, device, dados_anteriores):
    """Etapa 3: galeria -> mapa de clusters, herdando as decisoes da
    revisao anterior. Devolve (mapa, remapa)."""
    galeria = nucleo.get_galeria(pessoas)
    if not galeria:
        print(t("galeria_vazia"))
    mapa = identificar(wav, diar, galeria, device)
    # Decisoes da revisao anterior (nome, confirmado, so nomear, ignorado)
    # casadas pelo TRECHO de audio, nao pelo nome sugerido - ver
    # preservar_revisao. Os mesmos turnos crus que analisar() calcula.
    turnos_novos = interacao.mesclar_turnos(
        [(t.start, t.end, label) for t, label in iter_turns(diar)]
    )
    remapa = preservar_revisao(mapa, turnos_novos, dados_anteriores)
    if dados_anteriores and dados_anteriores.get("clusters"):
        herdados = sum(1 for i in mapa.values() if i.get("confirmado"))
        print(t("revisao_herdada", herdados=herdados, total=len(mapa)))
    return mapa, remapa


def _transcrever_e_corrigir(
    wav, diar_exc, mapa, analise, asr, modelo, idioma, regras, saida, dados_anteriores
):
    """Etapa 5: transcricao, alinhamento por palavra, glossario e as
    correcoes feitas a mao. Devolve (falas, lacunas, edicoes_sem_fala,
    lacunas_sem_lugar)."""
    # O initial_prompt so influencia a primeira janela de 30s (usamos
    # condition_on_previous_text=False, sem o qual o Whisper entra em loop de
    # repeticao em audio longo). O arquivo todo e coberto pela substituicao
    # deterministica logo apos o alinhamento.
    prompt = termos.prompt_whisper(regras) if regras else None
    detalhe = {"asr": asr, **({"termos": len(regras)} if regras else {})}
    _progresso(
        5,
        t("etapa_5", asr=asr, termos=t("etapa_5_termos", n=len(regras)) if regras else ""),
        **detalhe,
    )
    palavras = transcrever(wav, asr, modelo, idioma, prompt)
    falas, lacunas = alinhar(palavras, diar_exc, mapa, turnos_ativos=analise["turnos_brutos"])

    if regras:
        # lacunas: posicao relativa ao texto da fala, desloca junto com a
        # correcao (ver termos.CAMPOS_COM_POSICAO).
        contagem = termos.aplicar_em_falas(falas, regras, lacunas)
        termos.imprimir_contagem(contagem, regras)

    # Correcoes feitas a mao no Detalhe (edicao.py), casadas pelo TEMPO com
    # as falas novas. Relido do disco AGORA, como o titulo: uma correcao
    # feita na tela durante este processamento tambem vale. Depois do
    # glossario, que nunca reescreve fala corrigida.
    anteriores = carregar_saida_anterior(f"{saida}.json") or dados_anteriores
    # Respostas dos trechos para conferir (texto escrito numa lacuna, "nao
    # da para entender") ANTES das correcoes: a lacuna respondida dentro de
    # uma fala corrigida viaja com ela (trechos.preservar).
    lacunas_sem_lugar = trechos.preservar(falas, lacunas, anteriores)
    if lacunas_sem_lugar:
        print(t("lacunas_sem_lugar", n=len(lacunas_sem_lugar)))
    edicoes_sem_fala = edicao.preservar_edicoes(falas, lacunas, anteriores)
    if edicoes_sem_fala:
        print(t("edicoes_sem_fala", n=len(edicoes_sem_fala)))
    return falas, lacunas, edicoes_sem_fala, lacunas_sem_lugar


def _gravar(saida_json, saida, remapa, reuniao_id):
    """.json + ledger juntos, ou nenhum dos dois.

    escrever_atomico, nao open()+json.dump() direto: se o processo for
    morto no meio da escrita (o servidor pode cancelar o subprocess), o
    .json anterior (ou nenhum, na primeira vez) continua intacto - nunca
    um .json truncado que servidor/reunioes.py leria como JSONDecodeError,
    um estado ambiguo que nem "completa" nem "nao_processada" descreve.

    E o .json so e confirmado junto com o ledger: se o label de um cluster
    mudou nesta rodada, as contribuicoes de voz dele mudam de label
    tambem (nucleo.remapear_contribuicoes). Um sem o outro deixaria o
    ledger apontando para o cluster errado."""
    caminho_json = Path(f"{saida}.json")
    tmp_json = nucleo.preparar_escrita_atomica(caminho_json, nucleo.json_para_disco(saida_json))
    try:
        if remapa is not None and reuniao_id:
            nucleo.remapear_contribuicoes(reuniao_id, remapa)
    except BaseException:
        tmp_json.unlink(missing_ok=True)
        raise SystemExit(
            "Falha ao atualizar o ledger de vozes para os clusters novos. O "
            ".json anterior continua como estava - rode de novo."
        )
    nucleo.confirmar_escrita_atomica(tmp_json, caminho_json)


def processar(audio, **opcoes):
    """Pipeline inteiro de uma reuniao (ver _processar). A copia WAV do
    audio fica numa pasta temporaria propria, apagada ao terminar - com
    sucesso, falha ou cancelamento (trama/temporarios.py)."""
    pasta_wav = temporarios.criar_pasta()
    try:
        return _processar(audio, pasta_wav, **opcoes)
    finally:
        temporarios.apagar(pasta_wav)


def _processar(
    audio,
    pasta_wav,
    pessoas=None,
    falantes=None,
    min_falantes=None,
    max_falantes=None,
    device="cpu",
    asr="mlx",
    modelo=MODELO_PADRAO,
    idioma="pt",
    arquivo_termos=termos.ARQUIVO_PADRAO,
    sem_termos=False,
    out=None,
):
    """Pipeline inteiro de uma reuniao: audio -> <saida>.txt e <saida>.json.

    Imprime o progresso em "N/5  texto..." para o terminal e, com
    PROGRESSO_MAQUINA, em "@progresso {json}" para o servidor
    (servidor/processamento.py). Devolve o prefixo de saida (Path, sem
    extensao)."""
    saida = Path(out or Path(audio).with_suffix(""))
    dados_anteriores = carregar_saida_anterior(f"{saida}.json")

    _progresso(1, t("etapa_1"))
    wav = nucleo.to_wav16k(audio, str(Path(pasta_wav) / f"{Path(audio).stem}_16k.wav"))

    faixa = faixa_de_falantes(falantes, min_falantes, max_falantes, pessoas)
    _progresso(2, t("etapa_2", faixa=descrever_faixa(faixa)), **detalhe_da_faixa(faixa))
    diar, diar_exc = diarizar(wav, device, **faixa)

    _progresso(3, t("etapa_3"))
    mapa, remapa = _identificar_com_revisao_anterior(wav, diar, pessoas, device, dados_anteriores)
    _imprimir_identificacao(mapa)

    # Analise de sobreposicao usa a diarizacao NAO-exclusiva: a exclusiva
    # apaga justamente a informacao de quem falou por cima de quem.
    _progresso(4, t("etapa_4"))
    analise = interacao.analisar(diar, iter_turns, mapa)
    imprimir_dinamica(analise)

    regras = [] if sem_termos else termos.carregar(arquivo_termos)
    falas, lacunas, edicoes_sem_fala, lacunas_sem_lugar = _transcrever_e_corrigir(
        wav, diar_exc, mapa, analise, asr, modelo, idioma, regras, saida, dados_anteriores
    )

    escrever_txt(
        falas, mapa, f"{saida}.txt", regioes=analise["regioes_sobrepostas"], lacunas=lacunas
    )
    reuniao_id = preservar_reuniao_id(dados_anteriores)
    saida_json = montar_saida(
        audio,
        wav,
        mapa,
        falas,
        analise,
        reuniao_id=reuniao_id,
        lacunas=lacunas,
        device=device,
        asr=asr,
        # Relido do disco AGORA, nao no inicio: um titulo
        # editado na tela durante este processamento (que
        # leva minutos) sobrescreveria o novo pelo antigo.
        metadados=preservar_metadados(
            carregar_saida_anterior(f"{saida}.json") or dados_anteriores, audio
        ),
    )
    avisos = []
    if edicoes_sem_fala:
        saida_json["edicoes_sem_fala"] = edicoes_sem_fala
        avisos.append(erros.aviso("edicoes_sem_fala", n=len(edicoes_sem_fala)))
    if lacunas_sem_lugar:
        saida_json["lacunas_sem_lugar"] = lacunas_sem_lugar
        avisos.append(erros.aviso("lacunas_sem_lugar", n=len(lacunas_sem_lugar)))
    if avisos:
        saida_json["avisos"] = avisos
    _gravar(saida_json, saida, remapa, reuniao_id)
    return saida
