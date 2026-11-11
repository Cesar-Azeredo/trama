import { enviarJson } from "./cliente";

/** Espelha servidor/correcao.py (ADR 0019): corrigir um trecho em todas as
 * reunioes e nas proximas. */

export interface OcorrenciaCorrecao {
  /** indice da fala em dados.falas */
  indice: number;
  /** segundo da palavra (ou do inicio da fala, sem tempo por palavra) */
  inicio: number;
  antes: string;
  trecho: string;
  depois: string;
}

export interface PreviaCorrecao {
  trecho: string;
  certo: string;
  total: number;
  /** titulo: o dado pela pessoa, ou null - a tela monta o padrao
   * ("Reunião NN"/"Meeting NN") pelo id, no idioma dela. */
  reunioes: { id: string; titulo: string | null; ocorrencias: OcorrenciaCorrecao[] }[];
  /** So quando a correcao nao pode valer em todo lugar (uma correcao mais
   * geral, ja existente, continua valendo em parte do texto). */
  /** codigo + parametros, lista deles, ou null - a tela guarda como
   * Mensagem (mensagemDoAviso) e resolve no render. */
  aviso: unknown;
  assinatura: string;
}

export function previaCorrecao(trecho: string, certo: string): Promise<PreviaCorrecao> {
  return enviarJson<PreviaCorrecao>("/api/correcoes/previa", { trecho, certo });
}

export interface CorrecaoAplicada {
  aplicadas: string[];
  total: number;
  /** codigo + parametros, lista deles, ou null - a tela guarda como
   * Mensagem (mensagemDoAviso) e resolve no render. */
  aviso: unknown;
}

/** So grava o que a previa com esta assinatura mostrou - 409 se alguma
 * reuniao mudou desde ela. */
export function aplicarCorrecao(corpo: {
  trecho: string;
  certo: string;
  descricao: string;
  assinatura: string;
}): Promise<CorrecaoAplicada> {
  return enviarJson<CorrecaoAplicada>("/api/correcoes", corpo);
}

// ---- variacoes parecidas (ADR 0020) ---------------------------------------

export interface OcorrenciaVariacao extends OcorrenciaCorrecao {
  id: string;
  /** o dado pela pessoa, ou null - padrao montado na tela pelo id */
  titulo: string | null;
  /** o Whisper marcou duvida nesta palavra */
  baixa_confianca: boolean;
}

export interface Variacao {
  /** como aparece escrita (a grafia mais comum) */
  forma: string;
  total: number;
  baixa_confianca: boolean;
  distancia: number;
  /** ate 3, as de duvida do Whisper primeiro */
  ocorrencias: OcorrenciaVariacao[];
}

export interface SugestaoVariacoes {
  certo: string;
  variacoes: Variacao[];
  assinatura: string;
}

export function sugerirVariacoes(trecho: string, certo: string): Promise<SugestaoVariacoes> {
  return enviarJson<SugestaoVariacoes>("/api/correcoes/variacoes", { trecho, certo });
}

export function aplicarVariacoes(
  certo: string,
  formas: string[],
  assinatura: string,
): Promise<CorrecaoAplicada> {
  return enviarJson<CorrecaoAplicada>("/api/correcoes/variacoes/aplicar", {
    certo,
    formas,
    assinatura,
  });
}
