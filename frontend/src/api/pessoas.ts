import { buscarJson, enviarJson } from "./cliente";

export interface Pessoa {
  nome: string;
  peso_s: number;
  atualizado: string;
  /** Quando a pessoa entrou na galeria (core.primeira_aparicao_por_pessoa)
   * - so para a ordem estavel das cores de voz. */
  primeira_aparicao: string | null;
}

export function listarPessoas(): Promise<Pessoa[]> {
  return buscarJson<Pessoa[]>("/api/pessoas");
}

// ---- GET /api/pessoas/participacao ---------------------------------------

/** Espelha servidor/pessoas.py. Celula ausente fica FORA do dict. */
export type EstadoCelula = "confirmada" | "na_sala";

export interface ReuniaoDaGrade {
  id: string;
  processada: boolean;
}

export interface PessoaComParticipacao {
  nome: string;
  peso_s: number;
  participacao: Record<string, EstadoCelula>;
  total_reunioes: number;
  ultima: string | null;
}

export interface Participacao {
  reunioes: ReuniaoDaGrade[];
  pessoas: PessoaComParticipacao[];
}

export function lerParticipacao(): Promise<Participacao> {
  return buscarJson<Participacao>("/api/pessoas/participacao");
}

// ---- DELETE /api/pessoas/{nome} ------------------------------------------

export interface RespostaExclusao {
  ok: boolean;
  removidos: {
    perfil: number;
    contribuicoes: number;
    legado: number;
    compactado: boolean;
  };
}

export function excluirPessoa(nome: string): Promise<RespostaExclusao> {
  return enviarJson<RespostaExclusao>(
    `/api/pessoas/${encodeURIComponent(nome)}`,
    {},
    "DELETE",
  );
}
