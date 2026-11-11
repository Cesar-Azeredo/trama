import { buscarJson } from "./cliente";

/** Espelha servidor/sistema.py:resumo() - tudo somente leitura. */
export interface ItemLicenca {
  rotulo: string;
  texto: string;
}

export interface Licenca {
  nome: string;
  itens: ItemLicenca[];
}

export interface Sistema {
  versao: string;
  device: string;
  asr: string;
  pasta_audios: string;
  banco_vozes: string;
  licencas: Licenca[];
  /** REC_MEET_DEMO=1: reunioes ficticias de audios-demo/<idioma>, sem audio. */
  demonstracao: boolean;
}

export function lerSistema(): Promise<Sistema> {
  return buscarJson<Sistema>("/api/sistema");
}

let demonstracao: Promise<boolean> | null = null;

/** Se o servidor esta em modo demonstracao - lido uma vez por sessao. Falha
 * de rede conta como "nao": o pior caso e o comportamento normal. */
export function emDemonstracao(): Promise<boolean> {
  demonstracao ??= lerSistema()
    .then((s) => s.demonstracao === true)
    .catch(() => false);
  return demonstracao;
}
