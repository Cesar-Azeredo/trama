/**
 * Cliente da API do servidor local (ADR 0004). Tipos espelham exatamente o
 * que servidor/reunioes.py devolve - inclusive os campos que podem vir
 * ausentes (null), que nunca sao inventados como 0 ou lista vazia.
 */

import {
  buscarJson,
  enviarJson,
  ErroDaApi,
  mensagemDeErro,
  type CodigoComParametros,
} from "./cliente";
import { mensagem } from "../i18n/mensagem";

/** "processando"/"interrompido" so existem por causa do marco 2 (upload +
 * processamento pelo servidor, ver ARCHITECTURE.md) - "interrompido" e o
 * servidor tendo reiniciado no meio de um processamento anterior, nunca
 * confundido com "nao_processada" (que nunca foi tentada) nem "completa"
 * (nao ha .json). */
export type EstadoReuniao =
  | "completa"
  | "incompleta"
  | "nao_processada"
  | "processando"
  | "interrompido";

export interface FalaPorPessoa {
  pessoa: string;
  fala_pct: number;
}

/** "motivo" e contexto sobre o ESTADO, nao motivo de "disponivel" ser
 * false - as duas coisas nao sao a mesma pergunta (ver
 * servidor/reunioes.py:_estado_e_acao_sem_json). None quando nao ha nada
 * para explicar (nao_processada). */
export interface AcaoProcessar {
  disponivel: boolean;
  /** Codigo + parametros (trama/erros.py); a tela traduz no render. */
  motivo: CodigoComParametros | null;
}

/** Dinamica em duas linhas (servidor/reunioes.py:_interacao_resumida) -
 * null quando a reuniao nao tem dinamica/eventos. */
export interface InteracaoResumida {
  mais_interrompeu: { pessoa: string; vezes: number } | null;
  disputas: number;
}

/** Data e titulo (servidor/reunioes.py:_data_e_titulo). data em UTC
 * ("...Z"); a tela converte para o fuso da maquina. data_origem
 * "gravacao" = creation_time do audio (a data da reuniao); "arquivo" = so
 * a data de modificacao do arquivo, mostrada como "chegou em", nunca como
 * data da reuniao. titulo null = "Reuniao NN". */
export interface DataETitulo {
  data: string | null;
  data_origem: "gravacao" | "arquivo" | null;
  titulo: string | null;
}

export interface ResumoReuniao extends DataETitulo {
  id: string;
  estado: EstadoReuniao;
  duracao_s: number | null;
  pessoas: string[] | null;
  dinamica: FalaPorPessoa[] | null;
  interacao: InteracaoResumida | null;
  /** Todos os clusters com decisao da revisao (servidor/reunioes.py:
   * _revisada). False para reuniao sem .json. */
  revisada: boolean;
  acao_processar: AcaoProcessar | null;
}

export function listarReunioes(): Promise<ResumoReuniao[]> {
  return buscarJson<ResumoReuniao[]>("/api/reunioes");
}

// ---- GET /api/reunioes/{id} ---------------------------------------------

export interface Cluster {
  nome: string;
  sim: number;
  margem: number;
  fala_s: number;
  scores: Record<string, number>;
  confirmado?: boolean;
  /** Revisao decidiu "so nomear" (review.aplicar_e_gravar). */
  sem_aprender?: boolean;
  /** A voz deste cluster esta no ledger (servidor/reunioes.py:carregar). */
  voz_aprendida?: boolean;
}

/** Palavra cuja atribuicao ORIGINAL (por palavra, na sobreposicao de fala)
 * difere de quem ganhou a fala inteira no voto por duracao - ver
 * pipeline.py:alinhar. Pista de quem pode ter dito aquela palavra, nunca
 * certeza: e onde a atribuicao por palavra e menos confiavel. Posicao e
 * comprimento sao em CARACTERES dentro de "texto", nao indice de palavra
 * (ver termos.py:_aplicar_uma_regra_com_divergencias). */
export interface PalavraDivergente {
  posicao: number;
  comprimento: number;
  falante: string;
  /** Cluster do dono da palavra - a revisao renomeia por ele. Ausente em
   * reuniao processada antes deste campo. */
  cluster?: string;
}

/** Palavra abaixo de run.LIMIAR_PALAVRA_BAIXA_CONFIANCA (probabilidade do
 * decoder Whisper). So registro - nunca vira marca isolada na tela: uma
 * palavra de baixa confianca sozinha ("tá") deu falso positivo na
 * medicao. A tela marca a FALA (ver DetalheProcessado.limiar_confianca_fala
 * e confianca_media abaixo), nao a palavra. */
export interface PalavraBaixaConfianca {
  posicao: number;
  comprimento: number;
  probabilidade: number;
}

export interface Fala {
  falante: string;
  cluster: string;
  inicio: number;
  fim: number;
  texto: string;
  /** Ausente quando a fala nao tem nenhuma divergencia, ou quando a
   * reuniao foi processada antes deste campo existir. Ausente e ausente. */
  palavras_divergentes?: PalavraDivergente[];
  /** Media de probabilidade das palavras da fala. Ausente quando a
   * reuniao foi processada antes deste campo existir - nunca 0, que
   * pareceria confianca minima medida. */
  confianca_media?: number;
  palavras_baixa_confianca?: PalavraBaixaConfianca[];
  /** [posicao, comprimento, inicio, fim] de cada palavra (pipeline.py:alinhar).
   * Ausente em reuniao processada antes deste campo - ai nao ha faixa de
   * sobreposicao no texto, so a marca de evento na margem. */
  palavras_tempo?: [number, number, number, number][];
  /** Texto corrigido a mao no Detalhe (edicao.py, ADR 0016). Presente so
   * na fala corrigida: "texto" e o da pessoa, texto_original o transcrito.
   * Fala corrigida nao tem marcas de posicao (palavras_*, lacunas) - nao
   * ha como saber onde cairiam num texto escrito a mao. */
  edicao_manual?: EdicaoManual;
}

export interface EdicaoManual {
  texto_original: string;
  /** ISO UTC */
  editado_em: string;
}

/** Trecho DENTRO de um turno ativo (mesma pessoa, sem troca de falante)
 * sem nenhum token do Whisper cobrindo o intervalo - run.LIMIAR_LACUNA_S.
 * Nao afirma o que era (riso, gesto, respiracao) - so marca a omissao.
 * "posicao" e o deslocamento em caracteres dentro do "texto" da fala que
 * contem a lacuna (mesma convencao de PalavraDivergente), para a tela
 * inserir a marca no ponto exato do fluxo, nao so na margem. */
export interface LacunaSemTexto {
  posicao: number;
  inicio: number;
  fim: number;
  falante: string;
  /** Ausente em reuniao processada antes deste campo. */
  cluster?: string;
}

/** [inicio, fim, rotulo_do_cluster] - como o .json grava cada turno. */
export type Turno = [number, number, string];

export interface DinamicaPessoa {
  fala_s: number;
  turnos: number;
  turno_medio_s: number;
  interrompeu: number;
  foi_interrompido: number;
  apoios: number;
  sobreposicao_s: number;
  fala_pct: number;
}

export interface Evento {
  tempo: number;
  tipo: "apoio" | "interrupcao" | "disputa";
  entrante: string;
  falava: string;
  sobreposicao_s: number;
}

export interface RegiaoSobreposta {
  inicio: number;
  fim: number;
  falantes: string[];
}

export interface DetalheProcessado extends DataETitulo {
  id: string;
  estado: "completa" | "incompleta";
  /** Ver ResumoReuniao.revisada. */
  revisada: boolean;
  reuniao_id?: string;
  clusters: Record<string, Cluster>;
  falas: Fala[];
  turnos?: Turno[];
  dinamica?: Record<string, DinamicaPessoa>;
  matriz_interrupcoes?: Record<string, Record<string, number>>;
  eventos?: Evento[];
  regioes_sobrepostas?: RegiaoSobreposta[];
  /** Ausente em reuniao de antes deste campo. Presente e vazio (nunca
   * ausente-quando-zero) numa reuniao processada por esta versao do
   * pipeline.py - mesma convencao de "eventos"/"regioes_sobrepostas". */
  lacunas_sem_texto?: LacunaSemTexto[];
  /** codigo + parametros (servidor atual) ou texto (.json antigo) - a tela
   * resolve no render com textoDoAviso. */
  avisos?: unknown[];
  /** "processamento": valores gravados no .json por esta reuniao (pipeline.py
   * atual). "atual": a reuniao e de antes dessa mudanca - sim_min/
   * margem_min sao run.SIM_MIN/MARGEM_MIN de HOJE, nao os do
   * processamento original, que nao existe como recuperar. */
  sim_min: number;
  margem_min: number;
  limiares_origem: "processamento" | "atual";
  /** Abaixo disto, confianca_media de uma fala marca a fala inteira como
   * baixa confianca na tela. Ausente em reuniao de antes deste campo -
   * nesse caso nenhuma fala tem confianca_media mesmo, entao nao ha o
   * que comparar. */
  limiar_confianca_fala?: number;
  /** Fala com menos palavras do que isto nunca ganha a marca de baixa
   * confianca, mesmo abaixo de limiar_confianca_fala - numa fala de 1-2
   * palavras nao existe media de verdade, a palavra unica incerta E o
   * valor inteiro (medido: quase metade das falas abaixo do limiar em
   * reuniao_07/09 eram bordões de 1-3 palavras como "Ok.", "Não."). */
  min_palavras_confianca_fala?: number;
}

/** Mesmo formato para os TRES estados sem .json - servidor/reunioes.py
 * (_detalhe_nao_processada) devolve exatamente essa forma para
 * nao_processada, processando e interrompido, so troca o "estado" e o
 * "motivo" dentro de acao_processar. */
export interface DetalheNaoProcessada extends DataETitulo {
  id: string;
  estado: "nao_processada" | "processando" | "interrompido";
  audio_nome: string | null;
  audio_tamanho_bytes: number | null;
  duracao_s: number | null;
  tem_fase0: boolean;
  acao_processar: AcaoProcessar;
}

export type DetalheReuniao = DetalheProcessado | DetalheNaoProcessada;

/** Guarda de tipo compartilhada entre Lista e Detalhe - "tem .json" e
 * exatamente "completa ou incompleta", nunca inferido campo a campo. */
export function temResultadoProcessado(
  dados: DetalheReuniao,
): dados is DetalheProcessado {
  return dados.estado === "completa" || dados.estado === "incompleta";
}

export function carregarReuniao(id: string): Promise<DetalheReuniao> {
  return buscarJson<DetalheReuniao>(`/api/reunioes/${encodeURIComponent(id)}`);
}

// ---- GET /api/reunioes/{id}/audio ----------------------------------------

/** Espelha DURACAO_MAXIMA_TRECHO_S de servidor/app.py - nao ha rota que
 * exponha esse valor, entao um trecho pedido acima disso e clampado aqui
 * antes de virar URL, para nunca disparar o 400 do servidor a toa. */
const DURACAO_MAXIMA_TRECHO_S = 120;

export function urlAudioTrecho(id: string, inicio: number, fim: number): string {
  const fimClampado = Math.min(fim, inicio + DURACAO_MAXIMA_TRECHO_S);
  return `/api/reunioes/${encodeURIComponent(id)}/audio?inicio=${inicio}&fim=${fimClampado}`;
}

// ---- POST /api/reunioes/{id}/revisao -------------------------------------

/** Espelha NOME_MAX_LEN de servidor/revisao.py - validacao de verdade e
 * sempre no servidor; isto e so para o campo nao deixar digitar alem do
 * que sera aceito. */
export const NOME_MAX_LEN = 80;

export interface RespostaRevisao {
  ok: boolean;
  reuniao_id: string;
  totais_aprendidos: Record<string, number>;
}

/** `semAprender`: clusters a nomear sem atualizar perfil de voz nenhum
 * (servidor/revisao.py:aplicar). */
export function enviarRevisao(
  id: string,
  nomes: Record<string, string>,
  semAprender: string[] = [],
): Promise<RespostaRevisao> {
  return enviarJson<RespostaRevisao>(
    `/api/reunioes/${encodeURIComponent(id)}/revisao`,
    { nomes, sem_aprender: semAprender },
  );
}

/** Espelha review.efeitos_no_ledger: tudo o que a revisao vai mudar na
 * voz aprendida - inclusive voz nova, que tambem so entra depois de a
 * pessoa ver o numero. */
export interface EfeitoNoLedger {
  cluster: string;
  /** ensinar: voz NOVA entra no perfil de `pessoa`; remover: sai;
   * mover: passa de `pessoa` para `para`. */
  tipo: "ensinar" | "remover" | "mover";
  pessoa: string;
  peso_s: number;
  para: string | null;
  perfil_some: boolean;
}

export async function previaRevisao(
  id: string,
  nomes: Record<string, string>,
  semAprender: string[] = [],
): Promise<EfeitoNoLedger[]> {
  return (
    await enviarJson<{ efeitos: EfeitoNoLedger[] }>(
      `/api/reunioes/${encodeURIComponent(id)}/revisao/previa`,
      { nomes, sem_aprender: semAprender },
    )
  ).efeitos;
}

// ---- POST /api/reunioes (upload) -----------------------------------------

/** Espelha upload.EXTENSOES_PERMITIDAS/TAMANHO_MAXIMO_BYTES de
 * servidor/upload.py - validacao de verdade e sempre no servidor; isto e
 * so para nao fazer a pessoa esperar 500MB subirem para descobrir que a
 * extensao ou o tamanho estao errados. */
export const EXTENSOES_AUDIO_PERMITIDAS = [".m4a", ".mp3", ".wav"];
export const TAMANHO_MAXIMO_AUDIO_BYTES = 500 * 1024 * 1024;

/**
 * fetch() nao da progresso de UPLOAD de forma confiavel entre navegadores -
 * XMLHttpRequest e o jeito real de acompanhar bytes enviados, por isso e a
 * unica funcao deste arquivo que nao usa cliente.ts.
 *
 * Devolve o MESMO formato de GET /api/reunioes/{id} (a rota chama
 * reunioes.carregar() no fim) - a reuniao criada sai sempre como
 * DetalheNaoProcessada (acabou de nascer, nunca teve .json).
 */
export function enviarAudio(
  arquivo: File,
  aoProgredir?: (fracao: number) => void,
): Promise<DetalheNaoProcessada> {
  return new Promise((resolve, reject) => {
    const forma = new FormData();
    forma.append("arquivo", arquivo);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/reunioes");
    xhr.upload.onprogress = (evento) => {
      if (evento.lengthComputable) {
        aoProgredir?.(evento.loaded / evento.total);
      }
    };
    xhr.onload = () => {
      let corpo: unknown = null;
      try {
        corpo = JSON.parse(xhr.responseText);
      } catch {
        // resposta sem corpo JSON valido - vira erro generico abaixo
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(corpo as DetalheNaoProcessada);
        return;
      }
      reject(new ErroDaApi(mensagemDeErro(xhr.status, corpo)));
    };
    xhr.onerror = () =>
      reject(new ErroDaApi(mensagem((t) => t.erros.falhaDeRedeNoEnvio)));
    xhr.send(forma);
  });
}

// ---- POST /api/reunioes/{id}/processar -----------------------------------

export function iniciarProcessamento(
  id: string,
  pessoas: string[],
): Promise<{ ok: boolean; id: string }> {
  return enviarJson(`/api/reunioes/${encodeURIComponent(id)}/processar`, {
    pessoas,
  });
}

// ---- POST /api/reunioes/{id}/cancelar ------------------------------------

export function cancelarProcessamento(id: string): Promise<{ ok: boolean }> {
  return enviarJson(`/api/reunioes/${encodeURIComponent(id)}/cancelar`, {});
}

// ---- GET /api/reunioes/{id}/progresso (SSE) ------------------------------

/** Espelha servidor/processamento.py:estado_atual() - "pessoas" existe so
 * para a tela de retry reenviar a MESMA escolha apos uma falha, sem
 * perguntar de novo. */
/** O que o pipeline acrescentou a etapa atual, como dado
 * (servidor/processamento.py: detalhe_da_etapa) - a tela monta o texto. */
export interface DetalheEtapa {
  falantes?: number;
  min?: number;
  max?: number;
  asr?: string;
  termos?: number;
}

export interface EstadoProcessamento {
  reuniao_id: string;
  etapa: number;
  total_etapas: number;
  detalhe: DetalheEtapa;
  status: "rodando" | "concluido" | "erro" | "cancelado";
  /** Codigo + parametros (trama/erros.py); a tela traduz. */
  erro: CodigoComParametros | null;
  iniciado_em: number;
  device: string;
  asr: string;
  pessoas: string[];
}

/** Nenhum job bate com este id agora - nem rodando, nem acabou de
 * terminar (servidor/app.py:progresso_reuniao). */
export interface ProgressoOcioso {
  status: "ocioso";
}

/**
 * Abre a conexao SSE. Devolve o EventSource cru (nao uma Promise) - quem
 * chama decide quando fechar (ao desmontar, ou ao receber um status
 * terminal, para nao deixar o EventSource nativo tentar reconectar
 * sozinho depois que o servidor ja disse a palavra final).
 */
export function conectarProgresso(
  id: string,
  aoReceber: (evento: EstadoProcessamento | ProgressoOcioso) => void,
): EventSource {
  const es = new EventSource(
    `/api/reunioes/${encodeURIComponent(id)}/progresso`,
  );
  es.onmessage = (evento) => {
    aoReceber(JSON.parse(evento.data));
  };
  return es;
}

// ---- PUT /api/reunioes/{id}/titulo ---------------------------------------

/** Espelha reunioes.TITULO_MAX_LEN - validacao de verdade no servidor. */
export const TITULO_MAX_LEN = 120;

/** Vazio volta ao padrao ("Reuniao NN"): devolve null. */
export async function salvarTitulo(id: string, titulo: string): Promise<string | null> {
  return (
    await enviarJson<{ titulo: string | null }>(
      `/api/reunioes/${encodeURIComponent(id)}/titulo`,
      { titulo },
      "PUT",
    )
  ).titulo;
}

/** Limite de edicao.TEXTO_MAX_LEN - o servidor confere de novo. */
export const TEXTO_FALA_MAX_LEN = 5000;

export interface FalaAlterada {
  fala: Fala;
  /** As lacunas da reuniao depois da alteracao: a fala corrigida perde as
   * dela; desfazer devolve. Ausente em reuniao de antes do campo. */
  lacunas_sem_texto?: LacunaSemTexto[];
}

/** `inicio`: o da fala que a tela mostra - se a reuniao foi reprocessada
 * entre abrir e gravar, o servidor recusa em vez de corrigir outra fala. */
export async function corrigirFala(
  id: string,
  indice: number,
  texto: string,
  inicio: number,
): Promise<FalaAlterada> {
  return enviarJson<FalaAlterada>(
    `/api/reunioes/${encodeURIComponent(id)}/falas/${indice}`,
    { texto, inicio },
    "PUT",
  );
}

export async function desfazerCorrecaoFala(
  id: string,
  indice: number,
  inicio: number,
): Promise<FalaAlterada> {
  return enviarJson<FalaAlterada>(
    `/api/reunioes/${encodeURIComponent(id)}/falas/${indice}/edicao?inicio=${inicio}`,
    null,
    "DELETE",
  );
}
