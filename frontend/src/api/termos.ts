import { buscarJson, enviarJson } from "./cliente";

/** Espelha glossario.MAX_LEN - validacao de verdade e no servidor. */
export const TERMO_MAX_LEN = 200;
/** Espelha glossario.DESCRICAO_MAX_LEN. */
export const DESCRICAO_MAX_LEN = 120;

// GET/PUT /api/termos (o termos.txt como lista de regra/texto) continuam no
// servidor; a tela usa Termos da empresa (abaixo), que ve o mesmo arquivo
// por termo.

// ---- reaplicar nas reunioes ja processadas -------------------------------

/** Espelha servidor/glossario.previa_reaplicacao. */
export interface PreviaReaplicacao {
  reunioes: { id: string; substituicoes: number; por_termo: Record<string, number> }[];
  total: number;
  assinatura: string;
}

export function previaReaplicacao(): Promise<PreviaReaplicacao> {
  return buscarJson<PreviaReaplicacao>("/api/termos/reaplicar");
}

/** So grava o que a previa com esta assinatura mostrou - 409 se o
 * glossario ou alguma reuniao mudou desde ela. */
export function reaplicarGlossario(
  assinatura: string,
): Promise<{ aplicadas: string[]; total: number }> {
  return enviarJson("/api/termos/reaplicar", { assinatura });
}

/** Descricao de UM termo ("O que é isso?" da correcao pelo texto). Vazia
 * tira a descricao. */
export async function definirDescricao(
  termo: string,
  descricao: string,
): Promise<Record<string, string>> {
  return (
    await enviarJson<{ descricoes: Record<string, string> }>(
      "/api/termos/descricao",
      { termo, descricao },
      "PUT",
    )
  ).descricoes;
}

// ---- Termos da empresa (ADR 0021) ---------------------------------------

/** Espelha servidor/glossario.termos_da_empresa: o termos.txt visto por
 * termo. Cada variacao e uma correcao ja feita ("aprovium" -> "Aprovion"). */
export interface TermoDaEmpresa {
  termo: string;
  /** "" = termo conhecido, sem descricao */
  descricao: string;
  variacoes: { errado: string; certo: string }[];
}

export async function lerTermosDaEmpresa(): Promise<TermoDaEmpresa[]> {
  return (await buscarJson<{ termos: TermoDaEmpresa[] }>("/api/termos/empresa")).termos;
}

export async function adicionarTermo(termo: string, descricao: string): Promise<TermoDaEmpresa[]> {
  return (
    await enviarJson<{ termos: TermoDaEmpresa[] }>("/api/termos/empresa", { termo, descricao })
  ).termos;
}

export async function removerTermo(termo: string): Promise<TermoDaEmpresa[]> {
  return (
    await enviarJson<{ termos: TermoDaEmpresa[] }>(
      `/api/termos/empresa?termo=${encodeURIComponent(termo)}`,
      null,
      "DELETE",
    )
  ).termos;
}

export async function removerVariacao(errado: string): Promise<TermoDaEmpresa[]> {
  return (
    await enviarJson<{ termos: TermoDaEmpresa[] }>(
      `/api/termos/variacao?errado=${encodeURIComponent(errado)}`,
      null,
      "DELETE",
    )
  ).termos;
}

// ---- revisao de termos (ADR 0022) ---------------------------------------

export interface TermoParaConferir {
  forma: string;
  /** quantas vezes aparece nesta reuniao */
  total: number;
  /** a primeira em que o Whisper duvidou (senao, a primeira) */
  ocorrencia: {
    indice: number;
    /** posicao da forma em falas[indice].texto */
    posicao: number;
    comprimento: number;
    inicio: number;
    audio_inicio: number;
    audio_fim: number;
    antes: string;
    trecho: string;
    depois: string;
    duvida: boolean;
  };
}

export async function lerTermosParaConferir(id: string): Promise<TermoParaConferir[]> {
  return (
    await buscarJson<{ itens: TermoParaConferir[] }>(
      `/api/reunioes/${encodeURIComponent(id)}/termos-para-conferir`,
    )
  ).itens;
}

/** "Ignorar", ou corrigido so numa fala: nunca perguntar de novo. */
export async function marcarRespondido(forma: string): Promise<void> {
  await enviarJson("/api/termos/respondido", { forma });
}
