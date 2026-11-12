"""
trama/servidor/app.py - API FastAPI local do Trama.

Casca fina (ADR 0004): as rotas so leem o que o pipeline e a revisao ja
escreveram em audios/ e o que trama/nucleo.py ja mantem em vozes.db.
Nenhuma logica de pipeline reimplementada aqui.

O bind em 127.0.0.1 fica so em main() - o objeto FastAPI em si nao sabe de
rede (CLAUDE.md, regra 2). Rodar com: trama-servidor, python -m
trama.servidor.app ou python trama/servidor/app.py (a partir da raiz) -
todos funcionam, sem precisar setar PYTHONPATH.
"""

import sys
from pathlib import Path

# 'python trama/servidor/app.py' poe o DIRETORIO DO SCRIPT
# (trama/servidor/) em sys.path[0], nao a raiz do projeto - o pacote
# trama (que mora na raiz) nao seria encontrado sem isto, se nao estiver
# instalado. 'python -m trama.servidor.app' e o comando trama-servidor ja
# funcionam sem essa linha, mas o insert abaixo e inofensivo nesses casos
# - so nao duplica a entrada.
RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from trama import edicao, nucleo, trechos
from trama.servidor import (
    busca,
    conferir,
    correcao,
    glossario,
    origem,
    pessoas,
    processamento,
    reunioes,
    revisao,
    sistema,
    transcricao,
    upload,
)


def _erro(status, codigo, **parametros):
    """Resposta de erro para a tela: codigo + parametros, nunca frase pronta
    - o texto em cada idioma mora no catalogo do frontend (trama/erros.py)."""
    return HTTPException(status_code=status, detail={"codigo": codigo, "parametros": parametros})


@asynccontextmanager
async def _ciclo_de_vida(app):
    processamento.verificar_marcadores_orfaos(reunioes.PASTA_AUDIOS)
    # Copias WAV de processamentos interrompidos (trama/temporarios.py).
    processamento.limpar_wavs_orfaos()
    yield


# "Trama" e o nome que o usuario ve (ADR 0023) - aparece no /docs local.
app = FastAPI(title="Trama", lifespan=_ciclo_de_vida)


@app.middleware("http")
async def _so_o_proprio_app(request: Request, chamar):
    """Host e Origin conferidos antes de qualquer rota (servidor/origem.py,
    ADR 0030). Recusa com 403 e codigo, sem tocar disco nem banco."""
    motivo = origem.motivo_de_recusa(request.headers.get("host"), request.headers.get("origin"))
    if motivo == "host_recusado":
        recusa = _erro(403, "host_recusado")
    elif motivo == "origem_recusada":
        recusa = _erro(403, "origem_recusada")
    else:
        return await chamar(request)
    return JSONResponse({"detail": recusa.detail}, status_code=recusa.status_code)


# A revisao toca trechos de poucos segundos por cluster, nunca a reuniao
# inteira. Sem teto, inicio=0&fim=99999 faz o ffmpeg materializar a
# gravacao inteira como WAV 16 bits (~32 KB/s) na memoria do servidor.
DURACAO_MAXIMA_TRECHO_S = 120.0


@app.get("/api/reunioes")
def listar_reunioes():
    return reunioes.listar()


@app.post("/api/reunioes", status_code=201)
async def criar_reuniao(arquivo: UploadFile = File(...)):
    """
    So recebe o audio e cria a pasta - nao dispara o processamento (isso
    e a etapa seguinte do marco 2, ver servidor/upload.py e
    ARCHITECTURE.md). Devolve o mesmo formato de GET /api/reunioes/{id},
    que sai como "nao_processada" (correto: e exatamente o que a
    reuniao e agora).
    """
    try:
        id_novo = await upload.receber_upload(reunioes.PASTA_AUDIOS, arquivo.filename, arquivo)
    except upload.ExtensaoInvalida as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except upload.ArquivoMuitoGrande as exc:
        raise HTTPException(status_code=413, detail=exc.para_resposta())
    except Exception as exc:
        # Nunca a fala das pessoas no log - aqui nem existe ainda, mas a
        # mesma regra vale para qualquer detalhe interno (CLAUDE.md,
        # regra 3): so o tipo da falha.
        print(f"[upload] falha ao salvar audio novo: {type(exc).__name__}")
        raise _erro(500, "falha_salvar_audio")

    return reunioes.carregar(id_novo)


@app.get("/api/reunioes/{id}")
def obter_reuniao(id: str):
    try:
        return reunioes.carregar(id)
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")


class CorpoProcessar(BaseModel):
    # --pessoas do pipeline.py - o maior ganho de precisao que existe. Vazio e
    # valido (o pipeline roda sem galeria, so com rotulos SPEAKER_XX).
    pessoas: list[str] = []
    # Das `pessoas`, quem "estava, mas talvez nao tenha falado": vira a
    # faixa de falantes (processamento.argumentos_de_falantes). Opcional:
    # corpo antigo, so com "pessoas", continua valido.
    talvez_calados: list[str] = []


@app.get("/api/reunioes/{id}/exclusao")
def previa_apagar_reuniao(id: str):
    """O que apagar a reuniao tiraria de voz de cada pessoa - nada e
    apagado aqui."""
    try:
        return reunioes.previa_exclusao(id)
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")


@app.delete("/api/reunioes/{id}")
def apagar_reuniao(id: str):
    """
    Apaga a reuniao: audio, .json, .txt, a pasta inteira e o que ela
    ensinou de voz (servidor/reunioes.apagar). O id e validado e resolvido
    dentro da pasta de audios (CLAUDE.md, regra 4).
    """
    try:
        return {"ok": True, **reunioes.apagar(id)}
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")
    except processamento.JaEmProcessamento:
        raise _erro(409, "reuniao_processando")
    except Exception as exc:
        print(f"[reunioes] falha ao apagar {id}: {type(exc).__name__}")
        raise _erro(500, "falha_apagar_reuniao")


@app.post("/api/reunioes/{id}/processar", status_code=202)
def processar_reuniao(id: str, corpo: CorpoProcessar):
    """
    Dispara o pipeline.py de verdade (servidor/processamento.py) para uma
    reuniao que ja tem audio em disco - vinda de upload (POST
    /api/reunioes) ou copiada a mao. So enfileira; o progresso sai por
    GET /api/reunioes/{id}/progresso.
    """
    try:
        pasta = reunioes.resolver_pasta(id)
        caminho_audio = reunioes.resolver_audio(id)
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")
    except reunioes.AudioNaoEncontrado:
        raise _erro(404, "sem_audio_para_processar")

    try:
        processamento.iniciar(id, pasta, caminho_audio, corpo.pessoas, corpo.talvez_calados)
    except processamento.JaEmProcessamento as exc:
        raise _erro(409, "ja_processando", id=str(exc))

    return {"ok": True, "id": id}


@app.post("/api/reunioes/{id}/cancelar")
def cancelar_processamento(id: str):
    try:
        reunioes.resolver_pasta(id)
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")

    try:
        processamento.cancelar(id)
    except processamento.NadaParaCancelar:
        raise _erro(409, "nada_para_cancelar")

    return {"ok": True}


# Intervalo entre checagens do estado compartilhado - nao ha por que ser
# menor que isto (5 etapas ao longo de minutos, nao um medidor continuo)
# nem maior (a pessoa esta olhando a tela esperando).
INTERVALO_PROGRESSO_S = 0.5


@app.get("/api/reunioes/{id}/progresso")
async def progresso_reuniao(id: str):
    """
    SSE. Reconectar (reabrir a aba) funciona porque o estado vive no
    SERVIDOR, nao na conexao - o primeiro evento sempre manda o snapshot
    atual, quem acabou de conectar nao perde contexto. Encerra sozinho
    quando o status deixa de ser "rodando" (concluido/erro/cancelado),
    depois de mandar esse ultimo evento.
    """
    try:
        reunioes.resolver_pasta(id)
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")

    async def eventos():
        ultimo = None
        while True:
            atual = processamento.estado_atual()
            if atual is None or atual["reuniao_id"] != id:
                yield f"data: {json.dumps({'status': 'ocioso'})}\n\n"
                return
            if atual != ultimo:
                yield f"data: {json.dumps(atual, ensure_ascii=False)}\n\n"
                ultimo = atual
            if atual["status"] != "rodando":
                return
            await asyncio.sleep(INTERVALO_PROGRESSO_S)

    return StreamingResponse(eventos(), media_type="text/event-stream")


@app.get("/api/reunioes/{id}/audio")
def audio_recortado(id: str, inicio: float, fim: float):
    # Validacao pura primeiro (nao toca disco) - um intervalo absurdo e
    # rejeitado antes de gastar uma resolucao de caminho ou um subprocess.
    if inicio < 0 or fim <= inicio:
        raise _erro(400, "intervalo_invalido")
    if fim - inicio > DURACAO_MAXIMA_TRECHO_S:
        raise _erro(
            400,
            "trecho_longo_demais",
            pedido=round(fim - inicio),
            maximo=round(DURACAO_MAXIMA_TRECHO_S),
        )

    if sistema.DEMONSTRACAO:
        raise _erro(404, "sem_audio_na_demonstracao")

    try:
        caminho = reunioes.resolver_audio(id)
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")
    except reunioes.AudioNaoEncontrado:
        raise _erro(404, "audio_nao_encontrado")

    try:
        audio = reunioes.recortar_audio(caminho, inicio, fim)
    except reunioes.FalhaAoRecortarAudio as exc:
        print(f"[audio] falha ao recortar {id}: {type(exc).__name__}")
        raise _erro(500, "falha_recortar_audio")

    return Response(content=audio, media_type="audio/wav")


@app.get("/api/reunioes/{id}/transcricao")
def baixar_transcricao(id: str, idioma: str = "pt"):
    """
    A transcricao em .txt, gerada agora a partir do .json (nunca o .txt do
    pipeline, que pode estar desatualizado) - ver servidor/transcricao.py.
    """
    try:
        dados = reunioes.carregar(id)
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")
    if "falas" not in dados:
        raise _erro(404, "sem_transcricao_para_baixar")

    # Idioma da interface (?idioma=pt|en); qualquer outro valor cai no
    # portugues - nunca erro por isso.
    idioma = idioma if idioma in transcricao.IDIOMAS else "pt"
    texto = transcricao.montar_texto(id, dados, vocabulario=glossario.vocabulario(), idioma=idioma)
    nome = transcricao.nome_do_arquivo(id, dados, idioma=idioma)
    return Response(
        content=texto.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": transcricao.content_disposition(nome)},
    )


class CorpoFala(BaseModel):
    # Validacao (vazio, tamanho, caractere de controle) em
    # edicao.validar_texto, com a mensagem em portugues.
    texto: str
    # O inicio da fala que a tela mostrava - se o indice aponta para outra
    # fala (reprocessada entre abrir e gravar), a gravacao recusa.
    inicio: float


def _alterar_fala_ou_erro(id, funcao):
    try:
        return funcao()
    except edicao.TextoInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")
    except edicao.FalaNaoEncontrada:
        raise _erro(404, "fala_mudou")
    except edicao.FalaMudou:
        raise _erro(409, "fala_mudou")
    except Exception as exc:
        # Nunca o texto da fala no log (CLAUDE.md, regra 3).
        print(f"[fala] falha ao gravar {id}: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_correcao_fala")


@app.put("/api/reunioes/{id}/falas/{indice}")
def corrigir_fala(id: str, indice: int, corpo: CorpoFala):
    """Texto de uma fala corrigido a mao (edicao.py, ADR 0016)."""
    return _alterar_fala_ou_erro(
        id, lambda: reunioes.editar_fala(id, indice, corpo.texto, corpo.inicio)
    )


@app.delete("/api/reunioes/{id}/falas/{indice}/edicao")
def desfazer_correcao_fala(id: str, indice: int, inicio: float):
    """Volta a fala ao texto transcrito, com as marcas que ela tinha."""
    return _alterar_fala_ou_erro(id, lambda: reunioes.desfazer_edicao_fala(id, indice, inicio))


class CorpoTitulo(BaseModel):
    # Validacao (tamanho, caractere de controle) em reunioes.validar_titulo,
    # com a mensagem em portugues - aqui e so o formato do corpo.
    titulo: str


@app.put("/api/reunioes/{id}/titulo")
def gravar_titulo(id: str, corpo: CorpoTitulo):
    """Titulo da reuniao; vazio volta ao padrao ("Reuniao NN")."""
    try:
        titulo = reunioes.gravar_titulo(id, corpo.titulo)
    except reunioes.TituloInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")
    except Exception as exc:
        print(f"[titulo] falha ao gravar {id}: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_titulo")
    return {"titulo": titulo}


@app.get("/api/busca")
def buscar_nas_falas(q: str = ""):
    """
    Busca por trecho da fala nas reunioes processadas (servidor/busca.py).
    Em /api/busca, nao /api/reunioes/busca: la ela seria capturada pela
    rota /api/reunioes/{id}, declarada antes, como se "busca" fosse o id
    de uma reuniao. Nunca registra a consulta no log (CLAUDE.md, regra 3).
    """
    if len(q) > busca.MAX_BUSCA_LEN:
        raise _erro(400, "busca_longa_demais", maximo=busca.MAX_BUSCA_LEN)
    return {"resultados": busca.buscar(q)}


@app.get("/api/pessoas")
def listar_pessoas():
    # primeira_aparicao: ordem estavel das cores de voz, ver
    # nucleo.primeira_aparicao_por_pessoa.
    entrada = nucleo.primeira_aparicao_por_pessoa()
    return [
        {
            "nome": nome,
            "peso_s": peso,
            "atualizado": atualizado,
            "primeira_aparicao": entrada.get(nome),
        }
        for nome, peso, atualizado in nucleo.listar_pessoas()
    ]


@app.get("/api/pessoas/participacao")
def participacao_pessoas():
    """Tela Pessoas: voz aprendida e participacao reuniao a reuniao - ver
    servidor/pessoas.py para os tres estados de cada celula."""
    return pessoas.participacao()


@app.delete("/api/pessoas/{nome}")
def excluir_pessoa(nome: str):
    """
    Exclusao de perfil de voz (LGPD): perfil, contribuicoes no ledger e
    base legada - ver nucleo.excluir_pessoa. O nome vem do cliente, mas so
    como valor de SQL parametrizado (CLAUDE.md, regra 6), nunca como
    caminho.
    """
    nome = nome.strip()
    if not nome or len(nome) > revisao.NOME_MAX_LEN:
        raise _erro(400, "nome_invalido")
    try:
        removidos = nucleo.excluir_pessoa(nome)
    except nucleo.PessoaNaoEncontrada:
        raise _erro(404, "pessoa_nao_encontrada")
    except Exception as exc:
        print(f"[pessoas] falha ao excluir perfil: {type(exc).__name__}")
        raise _erro(500, "falha_excluir_pessoa")
    return {"ok": True, "removidos": removidos}


class CorpoRevisao(BaseModel):
    # {cluster_label: nome_escolhido}. Validacao de formato do nome
    # (tamanho, caractere de controle) e feita em revisao.aplicar, antes
    # de tocar disco ou banco - aqui e so o formato do corpo.
    nomes: dict[str, str]
    # Labels a nomear SEM aprender a voz (ver revisao.aplicar). Opcional:
    # corpo antigo, so com "nomes", continua valido e aprende tudo.
    sem_aprender: list[str] = []


def _json_para_revisar(id):
    try:
        pasta = reunioes.resolver_pasta(id)
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")
    caminho_json = pasta / f"{id}.json"
    if not caminho_json.exists():
        raise _erro(404, "sem_clusters_para_revisar")
    return caminho_json


@app.post("/api/reunioes/{id}/revisao/previa")
def previa_revisao(id: str, corpo: CorpoRevisao):
    """
    O que a revisao tiraria de voz ja aprendida, SEM gravar nada - a tela
    mostra ("isso vai remover 64 s da voz de Luciano") e so grava depois
    de confirmar. Mesma decisao da gravacao (revisao.planejar).
    """
    caminho_json = _json_para_revisar(id)
    try:
        efeitos = revisao.previa(caminho_json, corpo.nomes, corpo.sem_aprender)
    except revisao.NomeInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    return {"efeitos": efeitos}


@app.post("/api/reunioes/{id}/revisao")
def revisar_reuniao(id: str, corpo: CorpoRevisao):
    """
    A UNICA rota que escreve no vozes.db. Toda a logica e a MESMA que
    revisao.py usa (servidor/revisao.py so organiza a chamada) - ver ADR
    0004 e o modulo revisao.py para o porque.
    """
    caminho_json = _json_para_revisar(id)

    try:
        dados, totais = revisao.aplicar(caminho_json, corpo.nomes, corpo.sem_aprender)
    except revisao.NomeInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except Exception as exc:
        # Nunca a fala das pessoas no log - so o id e o tipo da falha
        # (CLAUDE.md, regra 3).
        print(f"[revisao] falha ao gravar {id}: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_revisao")

    return {
        "ok": True,
        "reuniao_id": dados.get("reuniao_id"),
        "totais_aprendidos": totais,
    }


@app.get("/api/termos")
def obter_termos():
    """Glossario (termos.txt) como lista ordenada de regra/texto - ver
    servidor/glossario.py para por que comentario tambem vem."""
    return {"itens": glossario.ler(), "descricoes": glossario.ler_descricoes()}


class CorpoTermos(BaseModel):
    # Validacao de cada item e em glossario.escrever, que tem as mensagens
    # em portugues - aqui e so o formato do corpo.
    itens: list
    # {termo certo: descricao}. Ausente (corpo antigo) mantem as gravadas.
    descricoes: dict | None = None


@app.put("/api/termos")
def gravar_termos(corpo: CorpoTermos):
    try:
        itens = glossario.escrever(corpo.itens, corpo.descricoes)
    except glossario.GlossarioInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except Exception as exc:
        print(f"[termos] falha ao gravar termos.txt: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_glossario")
    return {"itens": itens, "descricoes": glossario.ler_descricoes()}


def _termos_ou_erro(funcao):
    try:
        return {"termos": funcao()}
    except glossario.GlossarioInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except Exception as exc:
        print(f"[termos] falha: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_termos")


@app.get("/api/termos/empresa")
def listar_termos_da_empresa():
    """Termos da empresa (ADR 0021): o termos.txt visto por termo - nome,
    descricao e as variacoes ja corrigidas."""
    return {"termos": glossario.termos_da_empresa()}


class CorpoTermo(BaseModel):
    termo: str
    descricao: str = ""


@app.post("/api/termos/empresa")
def adicionar_termo_da_empresa(corpo: CorpoTermo):
    return _termos_ou_erro(lambda: glossario.adicionar_termo(corpo.termo, corpo.descricao))


@app.delete("/api/termos/empresa")
def remover_termo_da_empresa(termo: str):
    return _termos_ou_erro(lambda: glossario.remover_termo(termo))


@app.delete("/api/termos/variacao")
def remover_variacao_de_termo(errado: str):
    return _termos_ou_erro(lambda: glossario.remover_variacao(errado))


@app.get("/api/reunioes/{id}/termos-para-conferir")
def termos_para_conferir(id: str):
    """Revisao de termos, depois das vozes (servidor/conferir.py, ADR
    0022): no maximo 10, mais frequentes primeiro."""
    try:
        return {"itens": conferir.termos_para_conferir(id)}
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")


@app.get("/api/reunioes/{id}/trechos-para-conferir")
def trechos_para_conferir(id: str):
    """Terceira etapa da revisao (trama/trechos.py, ADR 0028): ate 3 falas
    de confianca baixa e 2 lacunas, no maximo 5, na ordem da reuniao."""
    try:
        return {"itens": reunioes.trechos_para_conferir(id)}
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")


def _alterar_trecho_ou_erro(id, funcao):
    try:
        return funcao()
    except edicao.TextoInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except reunioes.IdInvalido:
        raise _erro(400, "id_invalido")
    except reunioes.ReuniaoNaoEncontrada:
        raise _erro(404, "reuniao_nao_encontrada")
    except (edicao.FalaNaoEncontrada, edicao.FalaMudou, trechos.LacunaNaoEncontrada):
        raise _erro(409, "trecho_mudou")
    except Exception as exc:
        # Nunca o texto escrito no log (CLAUDE.md, regra 3).
        print(f"[trecho] falha ao gravar {id}: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_trecho")


class CorpoLacuna(BaseModel):
    # A lacuna e achada pelo tempo (nao tem indice proprio); validacao do
    # texto em edicao.validar_texto, a mesma da fala.
    inicio: float
    fim: float
    texto: str


@app.put("/api/reunioes/{id}/lacunas")
def escrever_lacuna(id: str, corpo: CorpoLacuna):
    """O que foi dito numa lacuna, gravado dentro dela (trechos.py)."""
    return _alterar_trecho_ou_erro(
        id, lambda: reunioes.escrever_lacuna(id, corpo.inicio, corpo.fim, corpo.texto)
    )


class CorpoIninteligivel(BaseModel):
    tipo: Literal["fala", "lacuna"]
    inicio: float
    fim: float
    # So para tipo "fala": o indice dela (com o inicio, como na correcao).
    indice: int | None = None


@app.put("/api/reunioes/{id}/ininteligivel")
def marcar_ininteligivel(id: str, corpo: CorpoIninteligivel):
    """ "Não dá para entender": o trecho nunca e perguntado de novo."""
    if corpo.tipo == "fala" and corpo.indice is None:
        raise _erro(400, "trecho_mudou")
    return _alterar_trecho_ou_erro(
        id,
        lambda: reunioes.marcar_ininteligivel(
            id, corpo.tipo, corpo.inicio, corpo.fim, corpo.indice
        ),
    )


class CorpoRespondido(BaseModel):
    forma: str


@app.post("/api/termos/respondido")
def marcar_termo_respondido(corpo: CorpoRespondido):
    """ "Ignorar" (ou corrigido so numa fala) na revisao de termos: nunca
    perguntar de novo, nesta reuniao nem nas proximas."""
    try:
        glossario.marcar_respondido(corpo.forma)
        return {"ok": True}
    except glossario.GlossarioInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except Exception as exc:
        print(f"[termos] falha ao marcar respondido: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_resposta")


class CorpoDescricao(BaseModel):
    termo: str
    descricao: str = ""


@app.put("/api/termos/descricao")
def gravar_descricao_termo(corpo: CorpoDescricao):
    """Descricao de UM termo ("O que é isso?" da correcao pelo texto)."""
    try:
        return {"descricoes": glossario.definir_descricao(corpo.termo, corpo.descricao)}
    except glossario.GlossarioInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except Exception as exc:
        print(f"[termos] falha ao gravar descricao: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_descricao")


class CorpoCorrecao(BaseModel):
    # Validacao em correcao.validar, com mensagem em portugues.
    trecho: str
    certo: str
    descricao: str = ""
    assinatura: str = ""


@app.post("/api/correcoes/previa")
def previa_correcao(corpo: CorpoCorrecao):
    """Onde "trecho => certo" trocaria o texto, em todas as reunioes - sem
    gravar (servidor/correcao.py, ADR 0019)."""
    try:
        return correcao.previa(corpo.trecho, corpo.certo)
    except correcao.CorrecaoInvalida as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())


@app.post("/api/correcoes")
def aplicar_correcao(corpo: CorpoCorrecao):
    """Grava a correcao para as proximas reunioes e aplica nas ja
    processadas - so o que a previa com esta assinatura mostrou."""
    try:
        return correcao.aplicar(corpo.trecho, corpo.certo, corpo.descricao, corpo.assinatura)
    except correcao.CorrecaoInvalida as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except glossario.GlossarioInvalido as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except glossario.GlossarioMudou:
        raise _erro(409, "mudou_desde_conferencia")
    except glossario.FalhaAoReaplicar as exc:
        print(f"[correcao] falha ao gravar: {type(exc.__cause__).__name__}")
        raise _erro(500, "correcao_parcial", corrigidas=len(exc.aplicadas))
    except Exception as exc:
        print(f"[correcao] falha: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_correcao")


class CorpoVariacoes(BaseModel):
    trecho: str = ""
    certo: str
    formas: list = []
    assinatura: str = ""


@app.post("/api/correcoes/variacoes")
def sugerir_variacoes(corpo: CorpoVariacoes):
    """Formas parecidas do termo que acabou de ser corrigido em todas as
    reunioes (servidor/correcao.sugerir, ADR 0020). So leitura."""
    try:
        return correcao.sugerir(corpo.trecho, corpo.certo)
    except correcao.CorrecaoInvalida as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())


@app.post("/api/correcoes/variacoes/aplicar")
def aplicar_variacoes(corpo: CorpoVariacoes):
    """Corrige em todas as reunioes so as formas marcadas."""
    try:
        return correcao.aplicar_variacoes(corpo.certo, corpo.formas, corpo.assinatura)
    except (correcao.CorrecaoInvalida, glossario.GlossarioInvalido) as exc:
        raise HTTPException(status_code=400, detail=exc.para_resposta())
    except glossario.GlossarioMudou:
        raise _erro(409, "mudou_desde_sugestao")
    except glossario.FalhaAoReaplicar as exc:
        print(f"[variacoes] falha ao gravar: {type(exc.__cause__).__name__}")
        raise _erro(500, "correcoes_parciais", corrigidas=len(exc.aplicadas))
    except Exception as exc:
        print(f"[variacoes] falha: {type(exc).__name__}")
        raise _erro(500, "falha_gravar_correcoes")


@app.get("/api/termos/reaplicar")
def previa_reaplicar_termos():
    """Quantas substituicoes o glossario de agora faria nas reunioes ja
    processadas, e em quais - sem gravar. A tela mostra e so grava com a
    assinatura desta previa."""
    return glossario.previa_reaplicacao()


class CorpoReaplicar(BaseModel):
    assinatura: str


@app.post("/api/termos/reaplicar")
def reaplicar_termos(corpo: CorpoReaplicar):
    try:
        return glossario.reaplicar(corpo.assinatura)
    except glossario.GlossarioMudou:
        raise _erro(409, "mudou_desde_previa")
    except glossario.FalhaAoReaplicar as exc:
        print(f"[termos] falha ao reaplicar: {type(exc.__cause__).__name__}")
        feitas = ", ".join(exc.aplicadas) or "nenhuma"
        raise _erro(500, "falha_reaplicar", feitas=feitas)


@app.get("/api/sistema")
def obter_sistema():
    """Informacao somente leitura para Perfil > Configuracoes."""
    return sistema.resumo()


def main():
    """Sobe o servidor em 127.0.0.1 (comando trama-servidor)."""
    import os
    import socket

    import uvicorn

    # HOST nunca vem de fora (CLAUDE.md, regra 2: so 127.0.0.1). A PORTA
    # pode: os testes que sobem o processo de verdade precisam de uma
    # porta efemera, senao so passam quando nenhum Trama real esta
    # rodando na 8000 - o que nunca e o caso de quem esta usando o app.
    HOST = "127.0.0.1"
    # A mesma variavel que servidor/origem.py usa para conferir o Host.
    porta_env = os.environ.get("TRAMA_PORTA", "8000")
    try:
        PORTA = int(porta_env)
        if not 1 <= PORTA <= 65535:
            raise ValueError
    except ValueError:
        print(
            f"TRAMA_PORTA inválida: '{porta_env}'. Use um número "
            "entre 1 e 65535, ou remova a variável para usar a 8000."
        )
        raise SystemExit(1)
    # uvicorn.run() ate detecta a porta ocupada, mas so depois de "iniciar"
    # o processo - a falha sai como um log em ingles ("ERROR: [Errno 48]
    # ...address already in use") espremido entre "startup complete" e
    # "shutdown complete", parecendo que o servidor rodou e caiu sozinho.
    # Testar o bind ANTES evita esse log confuso e da o motivo real, em
    # portugues, com o que fazer - quem fecha a janela sem parar o
    # servidor esbarra nisto toda vez.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
        # SO_REUSEADDR: o uvicorn (via asyncio) liga isso por padrao no
        # socket real dele. Sem ligar aqui tambem, este teste seria mais
        # RIGOROSO que o bind de verdade que vem depois - acusaria porta
        # ocupada logo apos um Ctrl+C, enquanto o proprio uvicorn nesse
        # mesmo instante conseguiria subir normalmente (a porta so fica
        # em TIME_WAIT por um tempo, nao ocupada por outro processo).
        teste.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            teste.bind((HOST, PORTA))
        except OSError:
            print(
                f"Já existe um servidor Trama rodando em "
                f"{HOST}:{PORTA}.\n"
                "Provavelmente uma janela ou aba anterior não foi "
                "fechada direito. Feche aquele processo (Ctrl+C na "
                "janela onde ele está rodando) antes de abrir outro - "
                "ou, se não souber qual é, rode "
                f"'lsof -i :{PORTA}' para achar o PID e 'kill <PID>'."
            )
            raise SystemExit(1)

    # --dev: recarrega sozinho quando um .py muda. Sem isso, o servidor
    # continuava rodando o codigo de antes de qualquer mudanca, e toda rota
    # nova respondia 404 ate alguem lembrar de reiniciar.
    #
    # Observa a raiz inteira (o pacote trama/ mora nela), mas so
    # *.py (filtro padrao do uvicorn com watchfiles): um .json gravado em
    # audios/ nunca reinicia nada. .venv, frontend, audios e tests ficam de
    # fora. So para desenvolvimento - ver o aviso no README sobre
    # processamento em andamento.
    if "--dev" in sys.argv[1:]:
        fora = [str(RAIZ / d) for d in (".venv", "frontend", "audios", "tests", "docs")]
        uvicorn.run(
            "trama.servidor.app:app",
            host=HOST,
            port=PORTA,
            reload=True,
            reload_dirs=[str(RAIZ)],
            reload_excludes=[d for d in fora if Path(d).is_dir()],
        )
    else:
        uvicorn.run(app, host=HOST, port=PORTA)


if __name__ == "__main__":
    main()
