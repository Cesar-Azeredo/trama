"""
nucleo.py - Banco de perfis de voz + extracao de embeddings.

Usa o mesmo modelo de embedding que o pyannote carrega internamente
(wespeaker-voxceleb-resnet34-LM, 256 dimensoes, comparacao por cosseno).
"""

import json
import os
import sqlite3
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from pyannote.audio import Inference, Model
from pyannote.core import Segment

from trama import migracoes

EMBED_MODEL = "pyannote/wespeaker-voxceleb-resnet34-LM"
DB_PATH = Path(os.environ.get("VOZES_DB", "vozes.db"))
HF_TOKEN = os.environ.get("HF_TOKEN")

# Duracao minima de um trecho para virar embedding confiavel.
# Abaixo de ~1s o embedding fica instavel e polui a media.
MIN_SEG_DUR = 1.0

# Quanto audio (em segundos) usar no maximo por cluster/pessoa.
# Passar disso nao melhora e so gasta tempo.
MAX_SPEECH_PER_CLUSTER = 120.0


# --------------------------------------------------------------------------
# utilidades
# --------------------------------------------------------------------------


def l2(v):
    """Normaliza L2. Com vetores normalizados, cosseno == produto escalar."""
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def to_wav16k(src, dst=None):
    """Converte qualquer audio para WAV 16 kHz mono (o que os modelos esperam)."""
    src = str(src)
    if dst is None:
        dst = str(Path(tempfile.mkdtemp()) / (Path(src).stem + "_16k.wav"))
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-loglevel",
            "error",
            "-i",
            src,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            dst,
        ],
        # -nostdin + stdin=DEVNULL: sem isso o ffmpeg le o terminal por
        # padrao (esperando tecla) e COME a entrada de quem chamou o
        # pipeline.py - num laco "while read" de bash, a lista de reunioes
        # perdia caracteres ("reuniao_02" chegava como "uniao_02").
        stdin=subprocess.DEVNULL,
        check=True,
    )
    return dst


def _iso_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def data_da_gravacao(caminho_audio):
    """
    Quando a reuniao aconteceu: {"data": ISO em UTC, "origem": ...}.

    origem "gravacao": o creation_time dos metadados do audio - o iPhone
    grava o INICIO da gravacao ali (conferido nas dez reunioes reais: as
    reunioes seguidas do mesmo dia encadeiam, uma comeca quando a outra
    termina). E a data da reuniao.

    origem "arquivo": sem creation_time, a data de modificacao do arquivo.
    NAO e a data da reuniao - e quando o arquivo chegou aqui (as reunioes
    01 a 07 tem todas o mesmo mtime, do dia em que foram copiadas). A tela
    mostra essa como "chegou em", nunca como data da reuniao.

    None se o arquivo nem existe. Sempre em UTC ("...Z"); quem mostra
    converte para o fuso da maquina. ffprobe com stdin fechado (ele NAO
    aceita -nostdin - ver servidor/reunioes.py).
    """
    caminho_audio = Path(caminho_audio)
    try:
        saida = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format_tags=creation_time",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(caminho_audio),
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        bruto = saida.stdout.strip().splitlines()[0] if saida.stdout.strip() else ""
        if bruto:
            dt = datetime.fromisoformat(bruto.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return {"data": _iso_utc(dt), "origem": "gravacao"}
    except (subprocess.SubprocessError, OSError, ValueError):
        pass  # sem metadado legivel: cai para a data do arquivo
    try:
        mtime = caminho_audio.stat().st_mtime
    except OSError:
        return None
    return {"data": _iso_utc(datetime.fromtimestamp(mtime, timezone.utc)), "origem": "arquivo"}


# Titulo dado a uma reuniao que ainda NAO tem .json (na Nova reuniao, antes
# de processar): fica aqui, na pasta dela, ate o pipeline.py criar o .json e
# incorporar (pipeline.preservar_metadados). Com .json, o titulo mora nele.
NOME_META_REUNIAO = "meta.json"


def ler_meta_reuniao(pasta):
    try:
        dados = json.loads((Path(pasta) / NOME_META_REUNIAO).read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def hhmmss(seconds):
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def preparar_escrita_atomica(caminho, texto, encoding="utf-8"):
    """
    Fase 1 de uma escrita atomica em duas fases: grava o conteudo NOVO num
    arquivo temporario na mesma pasta, sem tocar no destino. Devolve o
    caminho do temp - quem chama decide quando confirmar (com
    confirmar_escrita_atomica), depois que uma operacao mais critica (o
    banco, por exemplo) tiver sucesso. Existe para casos como a revisao,
    onde a ordem certa e: preparar os arquivos, so DEPOIS gravar no banco,
    e so DEPOIS DISSO trocar os arquivos de verdade - uma falha em
    qualquer etapa nunca deixa nem o banco nem o arquivo pela metade.

    Mesma pasta e obrigatorio: os.replace (em confirmar_escrita_atomica)
    so e atomico dentro do mesmo sistema de arquivos.
    """
    caminho = Path(caminho)
    tmp = caminho.with_name(f".{caminho.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    try:
        tmp.write_text(texto, encoding=encoding)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp


def confirmar_escrita_atomica(tmp, caminho):
    """Fase 2: troca o temporario por cima do destino com os.replace -
    rapido e atomico, a prova de deixar o arquivo pela metade."""
    os.replace(tmp, caminho)


def _eh_numero(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _json_indentado(obj, nivel):
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        dentro = " " * (nivel + 1)
        itens = [
            f"{dentro}{json.dumps(str(k), ensure_ascii=False)}: {_json_indentado(v, nivel + 1)}"
            for k, v in obj.items()
        ]
        return "{\n" + ",\n".join(itens) + "\n" + " " * nivel + "}"
    if isinstance(obj, (list, tuple)):
        if not obj:
            return "[]"
        if all(_eh_numero(x) for x in obj):
            return "[" + ", ".join(json.dumps(x) for x in obj) + "]"
        dentro = " " * (nivel + 1)
        itens = [dentro + _json_indentado(v, nivel + 1) for v in obj]
        return "[\n" + ",\n".join(itens) + "\n" + " " * nivel + "]"
    return json.dumps(obj, ensure_ascii=False)


def json_para_disco(dados):
    """
    O .json de uma reuniao como vai para o disco: o mesmo formato de
    json.dumps(indent=1) de sempre, com uma diferenca - lista SO de numeros
    fica numa linha so. Sem isso, os tempos de cada palavra
    (fala["palavras_tempo"], quatro numeros por palavra) virariam quatro
    linhas por palavra, dezenas de milhares numa reuniao de uma hora.

    Percorre a estrutura, nunca o texto: conteudo de string (a fala das
    pessoas) sai exatamente como esta. Usado por pipeline.py, revisao.py e pelo
    glossario (servidor/glossario.py), para os tres gravarem igual.
    """
    return _json_indentado(dados, 0)


def escrever_atomico(caminho, texto, encoding="utf-8"):
    """
    Escrita atomica de um passo so, para quem nao precisa separar preparo
    de confirmacao (ex: pipeline.py gerando o .json/.txt originais, sem nada
    mais critico por perto). Se o processo morrer no meio, o arquivo
    original continua intacto - sobra um temp orfao, no pior caso, nunca
    um .json ou .txt pela metade.
    """
    caminho = Path(caminho)
    tmp = preparar_escrita_atomica(caminho, texto, encoding)
    try:
        confirmar_escrita_atomica(tmp, caminho)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------
# embeddings
# --------------------------------------------------------------------------

_inference = None


def get_inference(device="cpu"):
    global _inference
    if _inference is None:
        model = Model.from_pretrained(EMBED_MODEL, token=HF_TOKEN)
        inf = Inference(model, window="whole")
        inf.to(torch.device(device))
        _inference = inf
    return _inference


def embed_segments(
    wav_path, segments, device="cpu", min_dur=MIN_SEG_DUR, max_total=MAX_SPEECH_PER_CLUSTER
):
    """
    Recebe varios trechos de UMA MESMA pessoa/cluster e devolve um unico
    embedding: media dos trechos ponderada pela duracao, normalizada.

    Este e o ponto chave do sistema. Comparar UM trecho curto contra a galeria
    erra muito; comparar a media de 60-120s de fala do mesmo cluster e
    dramaticamente mais estavel.

    Retorna (embedding, segundos_de_fala_usados) ou (None, 0.0).
    """
    inf = get_inference(device)

    # Normaliza a entrada: aceita Segment do pyannote, tupla (ini, fim) ou
    # qualquer objeto com .start/.end. O Inference.crop SO aceita um
    # pyannote.core.Segment de verdade - passar outra coisa levanta excecao
    # em todos os trechos e a funcao parece "nao ter achado audio".
    segs = []
    for s in segments:
        if isinstance(s, Segment):
            a, b = s.start, s.end
        elif isinstance(s, (tuple, list)):
            a, b = float(s[0]), float(s[1])
        else:
            a, b = float(s.start), float(s.end)
        if (b - a) >= min_dur:
            segs.append(Segment(a, b))

    # Prioriza os trechos mais longos: sao os de melhor qualidade acustica.
    segs.sort(key=lambda s: s.end - s.start, reverse=True)

    vecs, weights, total = [], [], 0.0
    primeiro_erro = None
    for s in segs:
        try:
            e = inf.crop(wav_path, s)
        except Exception as exc:
            if primeiro_erro is None:
                primeiro_erro = exc
            continue
        e = np.asarray(e, dtype=np.float32).reshape(-1)
        if e.size == 0 or not np.isfinite(e).all():
            continue
        dur = s.end - s.start
        vecs.append(l2(e))
        weights.append(dur)
        total += dur
        if total >= max_total:
            break

    if not vecs:
        if primeiro_erro is not None:
            # Nunca falhe em silencio: mostre a causa real.
            print(
                f"      ! erro ao extrair embedding: "
                f"{type(primeiro_erro).__name__}: {primeiro_erro}"
            )
        elif not segs:
            print(f"      ! nenhum trecho com duracao minima de {min_dur}s")
        return None, 0.0

    mean = np.average(np.stack(vecs), axis=0, weights=np.asarray(weights))
    return l2(mean), total


def embed_file(wav_path, device="cpu"):
    """Embedding do arquivo inteiro (usado no cadastro de voz)."""
    inf = get_inference(device)
    e = inf(wav_path)
    return l2(np.asarray(e, dtype=np.float32).reshape(-1))


# --------------------------------------------------------------------------
# banco de perfis
# --------------------------------------------------------------------------


def connect():
    """
    Abre o banco e garante que o schema esta na versao mais recente antes de
    devolver a conexao. A logica de migracao (o que criar, o que congelar,
    quando fazer backup) mora em migracoes/, nao aqui - ver ADR 0006.
    """
    con = sqlite3.connect(DB_PATH)
    migracoes.aplicar_pendentes(con, DB_PATH)
    return con


def _recompute_pessoa(con, nome):
    """
    Recalcula o perfil "atual" (tabela `pessoas`) de UMA pessoa a partir da
    base legada + todas as contribuicoes que apontam para ela agora.

    Deterministico: chamar de novo com os mesmos dados da sempre o mesmo
    resultado. E por isso que confirmar de novo nao infla o perfil e corrigir
    a pessoa nao deixa residuo no perfil errado - o perfil errado simplesmente
    para de incluir aquela contribuicao na proxima vez que for recalculado.
    """
    legado = con.execute(
        "SELECT embedding, peso FROM pessoas_legado WHERE nome = ?", (nome,)
    ).fetchone()
    contribs = con.execute(
        "SELECT embedding, peso FROM contribuicoes WHERE pessoa = ?", (nome,)
    ).fetchall()

    vecs, pesos = [], []
    if legado:
        vecs.append(np.frombuffer(legado[0], dtype=np.float32))
        pesos.append(float(legado[1]))
    for emb, peso in contribs:
        vecs.append(np.frombuffer(emb, dtype=np.float32))
        pesos.append(float(peso))

    if not vecs:
        con.execute("DELETE FROM pessoas WHERE nome = ?", (nome,))
        return 0.0

    pesos_arr = np.asarray(pesos, dtype=np.float64)
    peso_total = float(pesos_arr.sum())
    if peso_total > 0:
        media = np.average(np.stack(vecs), axis=0, weights=pesos_arr)
    else:
        media = np.mean(np.stack(vecs), axis=0)
    novo = l2(media)

    con.execute(
        "REPLACE INTO pessoas (nome, embedding, peso, atualizado) VALUES (?,?,?,?)",
        (
            nome,
            novo.astype(np.float32).tobytes(),
            peso_total,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )
    return peso_total


def upsert_pessoa(nome, embedding, peso=1.0):
    """
    Cadastro manual de voz (cadastro_avulso.py / colher_vozes.py) - FORA do ledger de
    contribuicoes de reuniao, porque nao ha reuniao+cluster de origem aqui.

    A atualizacao e uma media movel ponderada sobre a BASE LEGADA: cada
    cadastro empurra um pouco o centroide da pessoa na direcao de como ela
    realmente soa NA SUA SALA, com o SEU microfone. Atualizar a base legada
    (em vez de `pessoas` direto) e o que garante que um cadastro novo nao se
    perca na proxima vez que uma contribuicao de reuniao for recalculada.
    """
    nome = nome.strip()
    emb = l2(embedding)
    con = connect()
    try:
        row = con.execute(
            "SELECT embedding, peso FROM pessoas_legado WHERE nome = ?", (nome,)
        ).fetchone()
        if row:
            antigo = np.frombuffer(row[0], dtype=np.float32)
            peso_antigo = float(row[1])
            novo = l2(antigo * peso_antigo + emb * peso)
            peso_total_legado = peso_antigo + peso
        else:
            novo, peso_total_legado = emb, float(peso)

        con.execute(
            "REPLACE INTO pessoas_legado (nome, embedding, peso, migrado_em) VALUES (?,?,?,?)",
            (
                nome,
                novo.astype(np.float32).tobytes(),
                peso_total_legado,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        total = _recompute_pessoa(con, nome)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return total


def contribuicoes_da_reuniao(reuniao_id):
    """{cluster: (pessoa, peso)} do que o ledger ja aprendeu desta reuniao
    - o que uma revisao nova pode mover ou remover."""
    if not reuniao_id:
        return {}
    con = connect()
    try:
        rows = con.execute(
            "SELECT cluster, pessoa, peso FROM contribuicoes WHERE reuniao_id = ?", (reuniao_id,)
        ).fetchall()
    finally:
        con.close()
    return {cluster: (pessoa, float(peso)) for cluster, pessoa, peso in rows}


def registrar_contribuicoes(reuniao_id, contribs, retirar=()):
    """
    Registra as contribuicoes de UMA revisao (revisao.py) numa unica
    transacao: ou todas entram, ou nenhuma entra - nunca aprendizado parcial
    de uma reuniao por causa de uma falha no meio.

    `contribs`: [(cluster, pessoa, embedding, peso), ...]

    Chave primaria (reuniao_id, cluster) faz o REPLACE substituir a linha
    inteira em vez de somar: revisar de novo com a mesma pessoa reproduz o
    mesmo peso (idempotente); revisar com pessoa diferente move a linha e os
    DOIS perfis afetados (o antigo e o novo) sao recalculados.

    `retirar`: clusters desta reuniao cuja contribuicao anterior sai do
    ledger - o cluster foi ignorado ou so nomeado numa revisao nova, e a
    voz dele deixou de valer para quem ela tinha sido atribuida. Na MESMA
    transacao das contribuicoes novas.

    Retorna {pessoa: peso_total_apos_recalculo} so das pessoas afetadas.
    """
    con = connect()
    try:
        afetados = set()
        for cluster in retirar:
            anterior = con.execute(
                "SELECT pessoa FROM contribuicoes WHERE reuniao_id = ? AND cluster = ?",
                (reuniao_id, cluster),
            ).fetchone()
            if anterior:
                con.execute(
                    "DELETE FROM contribuicoes WHERE reuniao_id = ? AND cluster = ?",
                    (reuniao_id, cluster),
                )
                afetados.add(anterior[0])
        for cluster, pessoa, embedding, peso in contribs:
            nome = pessoa.strip()
            emb = l2(embedding)
            anterior = con.execute(
                "SELECT pessoa, versao FROM contribuicoes WHERE reuniao_id = ? AND cluster = ?",
                (reuniao_id, cluster),
            ).fetchone()
            versao = (anterior[1] + 1) if anterior else 1
            con.execute(
                "REPLACE INTO contribuicoes "
                "(reuniao_id, cluster, pessoa, embedding, peso, versao, atualizado) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    reuniao_id,
                    cluster,
                    nome,
                    emb.astype(np.float32).tobytes(),
                    float(peso),
                    versao,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            afetados.add(nome)
            if anterior and anterior[0] != nome:
                afetados.add(anterior[0])

        totais = {n: _recompute_pessoa(con, n) for n in afetados}
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return totais


def get_galeria(nomes=None):
    """Devolve {nome: embedding}. Se `nomes` for passado, filtra so essas pessoas."""
    con = connect()
    rows = con.execute("SELECT nome, embedding FROM pessoas").fetchall()
    con.close()
    galeria = {n: np.frombuffer(b, dtype=np.float32) for n, b in rows}
    if nomes:
        alvo = {n.strip().lower() for n in nomes}
        faltando = alvo - {k.lower() for k in galeria}
        if faltando:
            raise SystemExit(
                "Pessoas sem perfil de voz cadastrado: "
                + ", ".join(sorted(faltando))
                + "\nRode cadastro_avulso.py para cadastrar."
            )
        galeria = {k: v for k, v in galeria.items() if k.lower() in alvo}
    return galeria


def listar_pessoas():
    con = connect()
    rows = con.execute("SELECT nome, peso, atualizado FROM pessoas ORDER BY nome").fetchall()
    con.close()
    return rows


def primeira_aparicao_por_pessoa():
    """
    {nome: data ISO} de quando cada pessoa ENTROU na galeria - o mais cedo
    entre a base legada (migrado_em: a migracao do ADR 0006, ou o cadastro
    manual por enroll/harvest depois dela) e a primeira contribuicao de
    reuniao. Nao muda quando o perfil e atualizado depois; e o que da uma
    ordem estavel para as cores de voz (frontend/src/vozes/corDaVoz.ts),
    em que uma pessoa nova entra no FIM e nao desloca ninguem.
    """
    con = connect()
    try:
        rows = con.execute(
            "SELECT p.nome, MIN(COALESCE(l.migrado_em, '9999'), "
            "COALESCE((SELECT MIN(c.atualizado) FROM contribuicoes c "
            "WHERE c.pessoa = p.nome), '9999')) "
            "FROM pessoas p LEFT JOIN pessoas_legado l ON l.nome = p.nome"
        ).fetchall()
    finally:
        con.close()
    return {nome: (None if data == "9999" else data) for nome, data in rows}


def listar_contribuicoes():
    """[(reuniao_id, pessoa)] - de que reuniao veio cada parte da voz
    aprendida de cada pessoa. Sem embedding: quem chama so precisa saber
    SE a voz foi aprendida ali."""
    con = connect()
    try:
        return con.execute("SELECT reuniao_id, pessoa FROM contribuicoes").fetchall()
    finally:
        con.close()


def clusters_aprendidos():
    """{reuniao_id: {cluster, ...}} de toda reuniao com voz aprendida - o
    registro de que a revisao DECIDIU aquele cluster, mesmo num .json que
    nao tem o campo "confirmado" (revisado por uma versao antiga do
    revisao.py)."""
    con = connect()
    try:
        rows = con.execute("SELECT reuniao_id, cluster FROM contribuicoes").fetchall()
    finally:
        con.close()
    por_reuniao = {}
    for reuniao_id, cluster in rows:
        por_reuniao.setdefault(reuniao_id, set()).add(cluster)
    return por_reuniao


def remapear_contribuicoes(reuniao_id, remapa):
    """
    O ledger e indexado por (reuniao_id, label do cluster), e reprocessar
    pode renumerar os labels (SPEAKER_02 vira SPEAKER_01). `remapa`
    ({label_antigo: label_novo}, de pipeline.preservar_revisao) leva cada
    contribuicao para o label novo do MESMO trecho de audio.

    Contribuicao de um label antigo que nao casou com nenhum cluster novo
    continua valendo para a pessoa (e voz que ela falou), mas sai do
    caminho: vira "orfao-<label>-<sufixo>", para nunca ser lida como se
    fosse do cluster novo que herdou aquele numero.

    Uma transacao; primeiro tudo para chaves temporarias, depois para as
    finais - sem isso, trocar SPEAKER_01 <-> SPEAKER_02 colidiria na chave
    primaria no meio do caminho. Nenhum perfil muda (mesmas pessoas, mesmos
    vetores); devolve quantas linhas mudaram de label.
    """
    if not reuniao_id:
        return 0
    con = connect()
    try:
        rows = con.execute(
            "SELECT cluster FROM contribuicoes WHERE reuniao_id = ?", (reuniao_id,)
        ).fetchall()
        sufixo = uuid.uuid4().hex[:8]
        destino = {}
        for (cluster,) in rows:
            if cluster.startswith("orfao-"):
                continue
            novo = remapa.get(cluster, f"orfao-{cluster}-{sufixo}")
            if novo != cluster:
                destino[cluster] = novo
        for antigo in destino:
            con.execute(
                "UPDATE contribuicoes SET cluster = ? WHERE reuniao_id = ? AND cluster = ?",
                (f"__remap__{antigo}", reuniao_id, antigo),
            )
        for antigo, novo in destino.items():
            con.execute(
                "UPDATE contribuicoes SET cluster = ? WHERE reuniao_id = ? AND cluster = ?",
                (novo, reuniao_id, f"__remap__{antigo}"),
            )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return len(destino)


class PessoaNaoEncontrada(LookupError):
    pass


def excluir_pessoa(nome):
    """
    Remove TODA a voz aprendida de uma pessoa (requisito de LGPD do marco
    3): o perfil atual (`pessoas`), cada contribuicao de reuniao no ledger
    (`contribuicoes`) e a base legada (`pessoas_legado`) - numa transacao
    so. Apagar so o perfil nao bastaria: `_recompute_pessoa` o
    reconstruiria a partir do ledger na proxima revisao de qualquer
    reuniao que a mencione.

    Depois do commit, VACUUM: um DELETE no SQLite so marca as paginas como
    livres, e o vetor de voz continuaria legivel no arquivo ate ser
    sobrescrito. O VACUUM reescreve o banco sem elas.

    NAO toca: as transcricoes (.json/.txt em audios/, onde o nome continua
    como registro de quem falou - e texto da reuniao, nao dado biometrico)
    nem os backups vozes.db.bak-* que as migracoes deixam ao lado do banco,
    que continuam contendo o vetor antigo.

    Levanta PessoaNaoEncontrada se nao houver nada com esse nome. Devolve
    quantas linhas sairam de cada tabela, e se o VACUUM rodou.
    """
    con = connect()
    try:
        removidos = {
            "perfil": con.execute("DELETE FROM pessoas WHERE nome = ?", (nome,)).rowcount,
            "contribuicoes": con.execute(
                "DELETE FROM contribuicoes WHERE pessoa = ?", (nome,)
            ).rowcount,
            "legado": con.execute("DELETE FROM pessoas_legado WHERE nome = ?", (nome,)).rowcount,
        }
        if not any(removidos.values()):
            con.rollback()
            raise PessoaNaoEncontrada(nome)
        con.commit()
    except PessoaNaoEncontrada:
        raise
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    # Falha AQUI nao desfaz nada - o apagamento ja foi confirmado acima.
    # Quem chama recebe compactado=False para nunca dizer "nada foi
    # apagado" quando foi, nem "apagado de vez" quando o vetor ainda pode
    # estar nas paginas livres do arquivo.
    removidos["compactado"] = True
    try:
        con = sqlite3.connect(DB_PATH)
        try:
            con.execute("VACUUM")
        finally:
            con.close()
    except sqlite3.Error:
        removidos["compactado"] = False
    return removidos
