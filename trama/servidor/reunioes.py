"""
servidor/reunioes.py - leitura do que existe em audios/, sem reimplementar
nada do pipeline (ADR 0004). So le arquivos que pipeline.py/review.py/fase0.py ja
escreveram.

Cinco estados por reuniao, explicitos no campo "estado" de cada resposta -
nunca inferidos pelo frontend a partir de um campo ausente:

  completa       .json tem "turnos" e "dinamica" (saida do pipeline.py atual).
  incompleta     .json existe mas e de uma versao anterior do pipeline.py - falta
                 "turnos" e/ou "dinamica" (e por tabela "reuniao_id", que
                 revisao.py preenche na primeira revisao e por isso pode
                 faltar mesmo numa reuniao completa recem-processada).
  nao_processada nao ha .json nenhum - so audio e, as vezes, saida de
                 fase0.py. Isto NAO e um erro: e a fila de trabalho pendente
                 do usuario, o lugar onde a rota de processamento do marco 2
                 vai encaixar.
  processando    sem .json, mas o marcador de processamento
                 (processamento.NOME_MARCADOR) bate com um job rodando
                 agora NESTE servidor (ver _estado_e_acao_sem_json).
  interrompido   sem .json, com o marcador sobrando mas SEM job
                 correspondente em memoria - o servidor reiniciou no meio
                 de um processamento anterior (ver
                 servidor/processamento.py, verificar_marcadores_orfaos).

Campo ausente no .json fica ausente na resposta (chave fora do dict, nunca
0 ou lista vazia) - uma reuniao sem "dinamica" nao e uma reuniao em que
ninguem interrompeu ninguem, e "nao sabemos" tem de continuar distinguivel
de "sabemos que foi zero".
"""

import json
import os
import re
import subprocess
from pathlib import Path

from trama import edicao, erros, nucleo, pipeline
from trama.erros import ErroDeUsuario
from trama.servidor import processamento

PASTA_AUDIOS = Path(os.environ.get("TRAMA_AUDIOS", "audios"))

PADRAO_ID = re.compile(r"^[a-z0-9_-]+$")


class IdInvalido(ValueError):
    """Id de reuniao que nao bate com PADRAO_ID ou que resolveria para fora
    de PASTA_AUDIOS. Nunca deixa um caminho vindo do cliente tocar o disco
    sem essa checagem (CLAUDE.md, regra 4)."""


class ReuniaoNaoEncontrada(LookupError):
    """Id valido no formato, mas sem pasta correspondente em audios/."""


class AudioNaoEncontrado(LookupError):
    """Pasta da reuniao existe, mas sem o .m4a - por exemplo, se o original
    foi apagado apos o processamento para liberar espaço."""


class FalhaAoRecortarAudio(RuntimeError):
    """ffmpeg falhou ao recortar o trecho pedido."""


def resolver_pasta(id):
    if not PADRAO_ID.fullmatch(id or ""):
        raise IdInvalido(f"id de reuniao invalido: {id!r}")
    raiz = PASTA_AUDIOS.resolve()
    pasta = (PASTA_AUDIOS / id).resolve()
    if pasta.parent != raiz:
        # So pode acontecer via symlink ou id com caracteres que o regex
        # deveria ter barrado - checagem de cinto e suspensorio, nao
        # confiamos so na regex para isto.
        raise IdInvalido(f"id de reuniao invalido: {id!r}")
    if not pasta.is_dir():
        raise ReuniaoNaoEncontrada(id)
    return pasta


def _duracao_por_falas(falas):
    if not falas:
        return None
    return round(max(f["fim"] for f in falas), 1)


def _duracao_por_ffprobe(caminho_audio):
    """Melhor esforco: reunioes nao processadas nao tem 'falas', so o
    proprio arquivo de audio para medir a duracao. Nunca derruba a
    listagem - qualquer falha (ffprobe ausente, arquivo corrompido) vira
    None, nao uma excecao."""
    try:
        saida = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(caminho_audio),
            ],
            # ffprobe NAO aceita -nostdin (falha com "Option not found" - e
            # aqui a falha viraria "sem duracao" calado); stdin=DEVNULL tira
            # o terminal dele do mesmo jeito.
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return round(float(saida.stdout.strip()), 1)
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


NOME_CACHE_DURACAO = ".duracao_cache.json"


def _duracao_com_cache(caminho_audio):
    """
    ffprobe e um subprocess por chamada. GET /api/reunioes chama isto uma
    vez por reuniao NAO_PROCESSADA a cada carregamento da lista - com
    dezenas de gravacoes na fila (o caso real de um cliente, nao os quatro
    de hoje), isso vira dezenas de processos por tela aberta. O resultado
    fica cacheado num arquivo oculto ao lado do audio, com o tamanho e o
    mtime do arquivo original como chave - se o audio for substituido (novo
    tamanho ou nova data), o cache e recalculado sozinho, sem intervencao.
    """
    try:
        st = caminho_audio.stat()
    except OSError:
        return None
    chave = [st.st_size, st.st_mtime_ns]

    caminho_cache = caminho_audio.with_name(NOME_CACHE_DURACAO)
    if caminho_cache.exists():
        try:
            cache = json.loads(caminho_cache.read_text(encoding="utf-8"))
            if cache.get("chave") == chave:
                return cache.get("duracao_s")
        except (json.JSONDecodeError, OSError):
            pass  # cache corrompido - recalcula e sobrescreve abaixo

    duracao = _duracao_por_ffprobe(caminho_audio)
    try:
        caminho_cache.write_text(
            json.dumps({"chave": chave, "duracao_s": duracao}), encoding="utf-8"
        )
    except OSError:
        pass  # cache e otimizacao - uma falha ao escrever nao pode derrubar a resposta
    return duracao


NOME_CACHE_DATA = ".data_cache.json"


def _data_com_cache(caminho_audio):
    """
    nucleo.data_da_gravacao chama o ffprobe - mesmo problema e mesma solucao
    de _duracao_com_cache: cacheado num arquivo oculto ao lado do audio,
    com tamanho + mtime do original como chave (audio substituido
    recalcula sozinho). So para reuniao SEM .json: com .json, a data mora
    nele (pipeline.preservar_metadados).
    """
    try:
        st = caminho_audio.stat()
    except OSError:
        return None
    chave = [st.st_size, st.st_mtime_ns]
    caminho_cache = caminho_audio.with_name(NOME_CACHE_DATA)
    if caminho_cache.exists():
        try:
            cache = json.loads(caminho_cache.read_text(encoding="utf-8"))
            if cache.get("chave") == chave:
                return cache.get("data")
        except (json.JSONDecodeError, OSError):
            pass  # cache corrompido - recalcula e sobrescreve abaixo
    data = nucleo.data_da_gravacao(caminho_audio)
    try:
        caminho_cache.write_text(json.dumps({"chave": chave, "data": data}), encoding="utf-8")
    except OSError:
        pass  # cache e otimizacao - falha ao escrever nao derruba a resposta
    return data


def _data_e_titulo(pasta, id, dados):
    """
    {"data", "data_origem", "titulo"} de uma reuniao - do .json quando
    existe; senao, a data do audio (cache) e o titulo do meta.json que a
    Nova reuniao gravou (nucleo.NOME_META_REUNIAO). Ausente vira None, nunca
    string vazia: a tela decide o padrao ("Reuniao NN").
    """
    if dados is not None and dados.get("data_reuniao"):
        data = {"data": dados["data_reuniao"], "origem": dados.get("data_origem", "arquivo")}
    else:
        audio = _caminho_audio(pasta, id)
        data = _data_com_cache(audio) if audio else None
    titulo = (
        dados.get("titulo") if dados is not None else nucleo.ler_meta_reuniao(pasta).get("titulo")
    )
    return {
        "data": data["data"] if data else None,
        "data_origem": data["origem"] if data else None,
        "titulo": titulo or None,
    }


def _tamanho_arquivo(caminho):
    try:
        return caminho.stat().st_size
    except OSError:
        return None


_EXTENSOES_NAO_AUDIO = {".json", ".txt"}


def _caminho_audio(pasta, id):
    """
    Encontra o audio original da reuniao, seja qual for a extensao. Nao
    fixa em ".m4a": a pratica normal ate hoje era copiar o .m4a do
    celular a mao, mas o upload do marco 2 tambem aceita .mp3/.wav
    (servidor/upload.py) - e alguem pode copiar qualquer coisa que o
    ffmpeg leia a mao mesmo. Ignora o que o proprio pipeline grava do
    lado do audio (.json, .txt) e um upload que ficou pela metade
    (".parcial") - nunca os trata como se fossem o audio.

    None se nao houver nenhum audio.
    """
    for candidato in sorted(pasta.glob(f"{id}.*")):
        if candidato.suffix in _EXTENSOES_NAO_AUDIO or candidato.name.endswith(".parcial"):
            continue
        return candidato
    return None


def _tem_fase0(pasta):
    return (pasta / "fase0" / "fase0.json").exists()


def _pessoas_por_clusters(clusters):
    if not clusters:
        return None
    return sorted({c["nome"] for c in clusters.values()})


def _dinamica_resumida(dados):
    """
    [{pessoa, fala_pct}] ordenado por fala_pct decrescente - e a MESMA
    ordem em que o frontend desenha os segmentos da barra de tempo de fala
    (SKILL.md, elemento de assinatura) e a lista de nomes ao lado dela. A
    correspondencia entre segmento e nome e o que sustenta a acessibilidade
    da barra (cor nunca e o unico portador de significado); se os dois
    vierem em ordens diferentes, o nome errado fica ao lado da cor errada.

    None quando a reuniao nao tem "dinamica" - a tela mostra "sem dinamica"
    em vez de uma barra zerada; zero e um dado (ninguem interrompeu
    ninguem), ausente e outra coisa.
    """
    dinamica = dados.get("dinamica")
    if not dinamica:
        return None
    itens = [{"pessoa": nome, "fala_pct": info.get("fala_pct")} for nome, info in dinamica.items()]
    itens.sort(key=lambda item: item["fala_pct"] or 0, reverse=True)
    return itens


def _revisada(dados, aprendidos):
    """
    Revisada = TODOS os clusters com decisao da revisao. Decisao e
    confirmado=True (que revisao.aplicar_e_gravar grava em cada cluster -
    aprendendo, so nomeando ou ignorado) OU uma contribuicao no ledger
    daquele cluster: a reuniao_09 foi revisada antes de o campo existir, e
    so o ledger guarda isso. Um cluster sem decisao basta para a reuniao
    ainda estar "a revisar". Reuniao sem cluster nenhum nao tem o que
    revisar e nao e contada como revisada.

    `aprendidos`: {reuniao_id: {cluster}} de nucleo.clusters_aprendidos.
    """
    clusters = dados.get("clusters") or {}
    do_ledger = aprendidos.get(dados.get("reuniao_id"), set())
    return bool(clusters) and all(
        c.get("confirmado") or label in do_ledger for label, c in clusters.items()
    )


def _interacao_resumida(dados):
    """
    Dinamica em duas linhas para a coluna da lista de reunioes em tela
    larga: quem mais interrompeu (e quantas vezes) e quantas disputas.
    None quando a reuniao nao tem "dinamica"/"eventos" - ausente e
    ausente, nunca "ninguem interrompeu". Voz sem pessoa (DESCONHECIDO_/
    IGNORADO_) nunca e "quem mais interrompeu": o nome exibido seria
    "voz nao atribuida", que nao diz nada sobre a dinamica.
    """
    dinamica, eventos = dados.get("dinamica"), dados.get("eventos")
    if dinamica is None or eventos is None:
        return None
    pessoas = [
        (nome, info.get("interrompeu") or 0)
        for nome, info in dinamica.items()
        if not nome.startswith(("DESCONHECIDO", "IGNORADO"))
    ]
    pessoas.sort(key=lambda x: (-x[1], x[0]))
    mais = (
        {"pessoa": pessoas[0][0], "vezes": pessoas[0][1]} if pessoas and pessoas[0][1] > 0 else None
    )
    return {
        "mais_interrompeu": mais,
        "disputas": sum(1 for e in eventos if e.get("tipo") == "disputa"),
    }


# Codigo + parametros (trama/erros.py), nunca frase: a tela traduz.
MOTIVO_JA_PROCESSANDO = erros.aviso("motivo_ja_processando")
MOTIVO_INTERROMPIDA = erros.aviso("motivo_interrompida")


def _estado_e_acao_sem_json(id, pasta):
    """
    Reuniao sem .json ainda pode estar em tres situacoes, nao so
    "parada": sendo processada NESTE INSTANTE, ou com uma tentativa
    anterior interrompida por queda do servidor (marcador em disco
    sobrou, sem processo rodando por tras) - ver servidor/processamento.py.

    O marcador em disco e o que sobrevive a um reinicio do servidor;
    cruzar com o estado em memoria (`processamento.estado_atual()`) e o
    que distingue "rodando de verdade agora" de "sobra de uma execucao
    que nao terminou". So NENHUM dos dois vira "nao_processada", o
    padrao de sempre.

    "motivo" e contexto sobre o ESTADO, nao motivo de o botao estar
    desabilitado - as duas coisas nao sao a mesma pergunta. "processando"
    tem as duas (motivo explica por que "disponivel" e False: so um
    processamento por vez). "interrompido" tem so a primeira: o botao
    funciona (dispara um processamento novo, sem as pessoas da tentativa
    anterior - isso nao sobrevive a queda do servidor, so vive em memoria),
    mas o motivo de ter chegado nesse estado continua valendo a pena
    explicar. "nao_processada" nao tem nada pra explicar - motivo None.
    """
    if processamento.ler_marcador(pasta) is not None:
        atual = processamento.estado_atual()
        if atual and atual["reuniao_id"] == id and atual["status"] == "rodando":
            return "processando", {"disponivel": False, "motivo": MOTIVO_JA_PROCESSANDO}
        return "interrompido", {"disponivel": True, "motivo": MOTIVO_INTERROMPIDA}
    return "nao_processada", {"disponivel": True, "motivo": None}


def _sem_embeddings(clusters):
    """
    Decisao de arquitetura, nao detalhe de implementacao (ver ARCHITECTURE.md,
    secao de rotas): clusters[*].embedding e o vetor de voz bruto - dado
    biometrico. O frontend nao tem uso para ele (nenhuma tela desenha a
    partir de um vetor de 256 dimensoes) e ele nunca deveria deixar o
    servidor. Fica disponivel para quem le o .json direto do disco (a rota
    de revisao, que precisa dele para realimentar o perfil em nucleo.py).
    """
    return {
        label: {k: v for k, v in cluster.items() if k != "embedding"}
        for label, cluster in clusters.items()
    }


def _estado(dados):
    return "completa" if ("turnos" in dados and "dinamica" in dados) else "incompleta"


def _resumo(id, pasta, aprendidos):
    caminho_json = pasta / f"{id}.json"
    if not caminho_json.exists():
        caminho_audio = _caminho_audio(pasta, id)
        estado, acao = _estado_e_acao_sem_json(id, pasta)
        return {
            "id": id,
            **_data_e_titulo(pasta, id, None),
            "estado": estado,
            "duracao_s": (_duracao_com_cache(caminho_audio) if caminho_audio else None),
            "pessoas": None,
            "dinamica": None,
            "interacao": None,
            "revisada": False,
            "acao_processar": acao,
        }
    dados = json.loads(caminho_json.read_text(encoding="utf-8"))
    return {
        "id": id,
        **_data_e_titulo(pasta, id, dados),
        "estado": _estado(dados),
        "duracao_s": _duracao_por_falas(dados.get("falas")),
        "pessoas": _pessoas_por_clusters(dados.get("clusters")),
        "dinamica": _dinamica_resumida(dados),
        "interacao": _interacao_resumida(dados),
        "revisada": _revisada(dados, aprendidos),
        "acao_processar": None,
    }


def listar():
    """Mais recente primeiro - reuniao_09 antes de reuniao_01. O id e o
    nome da pasta e cresce com o tempo, entao ordem reversa do nome e
    ordem cronologica reversa."""
    if not PASTA_AUDIOS.is_dir():
        return []
    resumos = []
    aprendidos = nucleo.clusters_aprendidos()
    for pasta in sorted(PASTA_AUDIOS.iterdir(), reverse=True):
        if not pasta.is_dir() or not PADRAO_ID.fullmatch(pasta.name):
            continue
        resumos.append(_resumo(pasta.name, pasta, aprendidos))
    return resumos


def _detalhe_nao_processada(id, pasta):
    caminho_audio = _caminho_audio(pasta, id)
    estado, acao = _estado_e_acao_sem_json(id, pasta)
    return {
        "id": id,
        **_data_e_titulo(pasta, id, None),
        "estado": estado,
        "audio_nome": caminho_audio.name if caminho_audio else None,
        "audio_tamanho_bytes": (_tamanho_arquivo(caminho_audio) if caminho_audio else None),
        "duracao_s": (_duracao_com_cache(caminho_audio) if caminho_audio else None),
        "tem_fase0": _tem_fase0(pasta),
        "acao_processar": acao,
    }


def carregar(id):
    pasta = resolver_pasta(id)
    caminho_json = pasta / f"{id}.json"
    if not caminho_json.exists():
        return _detalhe_nao_processada(id, pasta)

    dados = dict(json.loads(caminho_json.read_text(encoding="utf-8")))
    dados["clusters"] = _sem_embeddings(dados.get("clusters", {}))
    if "falas" in dados:
        dados["falas"] = [edicao.para_a_tela(f) for f in dados["falas"]]
    dados["id"] = id
    dados.update(_data_e_titulo(pasta, id, dados))
    dados["estado"] = _estado(dados)
    aprendidos = nucleo.clusters_aprendidos()
    dados["revisada"] = _revisada(dados, aprendidos)
    # Por cluster: a voz dele esta no ledger? A tela de revisao usa isto
    # para reabrir um cluster confirmado SEM voz aprendida em "so nomear"
    # (reunioes 01/03/05, revisadas com --sem-aprender antes de o campo
    # "sem_aprender" existir) - senao "Editar revisao" e salvar aprenderia
    # a voz sem ninguem ter pedido.
    do_ledger = aprendidos.get(dados.get("reuniao_id"), set())
    for label, cluster in dados["clusters"].items():
        cluster["voz_aprendida"] = label in do_ledger
    # pipeline.py (a partir de montar_saida()) grava sim_min/margem_min no
    # proprio .json - o limiar QUE ESTAVA EM VIGOR quando esta reuniao foi
    # processada. As reunioes de antes dessa mudanca nao tem esses campos;
    # para elas, nao existe como recuperar o limiar historico, entao a
    # rota devolve o limiar de HOJE, mas marcado explicitamente em
    # "limiares_origem" - nunca finge que 0.60 de hoje era o valor de
    # quando a reuniao rodou.
    tem_limiar_do_processamento = "sim_min" in dados and "margem_min" in dados
    if not tem_limiar_do_processamento:
        dados["sim_min"] = pipeline.SIM_MIN
        dados["margem_min"] = pipeline.MARGEM_MIN
    dados["limiares_origem"] = "processamento" if tem_limiar_do_processamento else "atual"
    return dados


def resolver_audio(id):
    """
    Caminho do audio original para a rota de recorte. Reaproveita
    resolver_pasta - a MESMA validacao de id da leitura do .json, nunca uma
    segunda copia da checagem (CLAUDE.md, regra 4: o caminho nunca vem do
    cliente, so o id, e so existe UM lugar no codigo que transforma id em
    caminho).
    """
    pasta = resolver_pasta(id)
    caminho = _caminho_audio(pasta, id)
    if caminho is None:
        raise AudioNaoEncontrado(id)
    return caminho


def recortar_audio(caminho_audio, inicio, fim):
    """
    Recorta [inicio, fim) do audio original para os trechos tocaveis da
    revisao. -ss/-to ANTES de -i: seek rapido no arquivo de entrada em vez
    de decodificar a reuniao inteira ate o ponto pedido - importa porque um
    trecho perto do fim de uma gravacao de 70 min nao pode custar 70 min
    de decodificacao. A imprecisao tipica (poucos milissegundos) e
    irrelevante para ouvir um cluster na revisao.

    Devolve WAV em memoria (bytes) - os trechos sao de poucos segundos,
    nao ha necessidade de arquivo temporario nem de streaming.
    """
    try:
        resultado = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-loglevel",
                "error",
                "-ss",
                str(inicio),
                "-to",
                str(fim),
                "-i",
                str(caminho_audio),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                "-",
            ],
            # ffmpeg le o terminal por padrao (ver nucleo.to_wav16k).
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
            check=True,
        )
        return resultado.stdout
    except (subprocess.SubprocessError, OSError) as exc:
        raise FalhaAoRecortarAudio(str(exc)) from exc


# --------------------------------------------------------------------------
# titulo da reuniao
# --------------------------------------------------------------------------

TITULO_MAX_LEN = 120
_CARACTERE_DE_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


class TituloInvalido(ErroDeUsuario):
    """Titulo recusado (codigo + parametros, trama/erros.py)."""


def validar_titulo(bruto):
    """Titulo limpo, ou None para voltar ao padrao ("Reuniao NN") - campo
    vazio (ou so espaco) e a forma de tirar o titulo."""
    if not isinstance(bruto, str):
        raise TituloInvalido("titulo_nao_texto")
    titulo = bruto.strip()
    if _CARACTERE_DE_CONTROLE.search(titulo):
        raise TituloInvalido("titulo_com_controle")
    if len(titulo) > TITULO_MAX_LEN:
        raise TituloInvalido("titulo_longo_demais", tamanho=len(titulo), maximo=TITULO_MAX_LEN)
    return titulo or None


def gravar_titulo(id, bruto):
    """
    Grava o titulo, sempre em escrita atomica. Com .json, no .json (onde o
    pipeline.py o preserva ao reprocessar - pipeline.preservar_metadados). Sem .json
    ainda (reuniao na fila, titulo dado na Nova reuniao), no meta.json da
    pasta, que o pipeline.py incorpora quando criar o .json. Devolve o titulo
    gravado (None = padrao).
    """
    titulo = validar_titulo(bruto)
    pasta = resolver_pasta(id)
    caminho_json = pasta / f"{id}.json"
    if caminho_json.exists():
        dados = json.loads(caminho_json.read_text(encoding="utf-8"))
        if titulo:
            dados["titulo"] = titulo
        else:
            dados.pop("titulo", None)
        nucleo.escrever_atomico(caminho_json, nucleo.json_para_disco(dados))
    else:
        meta = nucleo.ler_meta_reuniao(pasta)
        if titulo:
            meta["titulo"] = titulo
        else:
            meta.pop("titulo", None)
        nucleo.escrever_atomico(
            pasta / nucleo.NOME_META_REUNIAO, json.dumps(meta, ensure_ascii=False, indent=1)
        )
    return titulo


# --------------------------------------------------------------------------
# texto de uma fala corrigido a mao (edicao.py, ADR 0016)
# --------------------------------------------------------------------------


def _alterar_fala(id, operacao):
    """
    Le o .json, aplica `operacao(dados)` (que devolve a fala alterada) e
    grava .json e .txt juntos: os dois preparados em temporario antes de
    confirmar qualquer um - mesma ordem do glossario e da revisao. Devolve
    a fala (como a tela recebe) e as lacunas da reuniao, que podem ter
    mudado.
    """
    pasta = resolver_pasta(id)
    caminho_json = pasta / f"{id}.json"
    if not caminho_json.exists():
        raise ReuniaoNaoEncontrada(id)
    dados = json.loads(caminho_json.read_text(encoding="utf-8"))
    fala = operacao(dados)

    txt = caminho_json.with_suffix(".txt")
    texto_txt = pipeline.montar_texto_txt(
        dados["falas"], dados.get("clusters", {}), regioes=dados.get("regioes_sobrepostas")
    )
    tmp_txt = nucleo.preparar_escrita_atomica(txt, texto_txt)
    try:
        tmp_json = nucleo.preparar_escrita_atomica(caminho_json, nucleo.json_para_disco(dados))
    except BaseException:
        tmp_txt.unlink(missing_ok=True)
        raise
    nucleo.confirmar_escrita_atomica(tmp_txt, txt)
    nucleo.confirmar_escrita_atomica(tmp_json, caminho_json)
    return {"fala": edicao.para_a_tela(fala), "lacunas_sem_texto": dados.get("lacunas_sem_texto")}


def editar_fala(id, indice, texto, inicio):
    return _alterar_fala(id, lambda d: edicao.editar(d, indice, texto, inicio))


def desfazer_edicao_fala(id, indice, inicio):
    return _alterar_fala(id, lambda d: edicao.desfazer(d, indice, inicio))
