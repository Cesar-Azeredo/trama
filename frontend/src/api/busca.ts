import { buscarJson } from "./cliente";

/** Espelha servidor/busca.py. `destaques`: [inicio, fim) em caracteres
 * DENTRO de `texto` - a tela desenha como <mark>, nunca como HTML. */
export interface TrechoEncontrado {
  inicio: number;
  falante: string;
  texto: string;
  destaques: [number, number][];
}

export interface ReuniaoEncontrada {
  id: string;
  trechos: TrechoEncontrado[];
  /** Falas que casaram - pode passar de trechos.length (limite por
   * reuniao no servidor). */
  total: number;
}

/** Espelha busca.MAX_BUSCA_LEN. */
export const BUSCA_MAX_LEN = 200;

export async function buscarNasFalas(q: string): Promise<ReuniaoEncontrada[]> {
  return (
    await buscarJson<{ resultados: ReuniaoEncontrada[] }>(
      `/api/busca?q=${encodeURIComponent(q)}`,
    )
  ).resultados;
}
