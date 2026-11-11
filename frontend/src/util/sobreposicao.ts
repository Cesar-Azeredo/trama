import type { RegiaoSobreposta } from "../api/reunioes";

/** Trecho do texto de uma fala (em CARACTERES) em que outra pessoa falava
 * junto - `outra` e quem, nunca de quem sao as palavras dentro dele. */
export interface FaixaSobreposicao {
  inicio: number;
  fim: number;
  outra: string;
}

/**
 * Faixas de sobreposicao de UMA fala: cada palavra (palavras_tempo) cujo
 * ponto medio cai dentro de uma regiao de regioes_sobrepostas que tem
 * outra pessoa alem de quem fala, na cor dessa outra pessoa. Ponto medio,
 * nao "qualquer toque": uma palavra que so encosta na borda da regiao nao
 * foi dita por cima de ninguem.
 *
 * Palavras seguidas com a mesma outra pessoa viram UMA faixa, do comeco
 * da primeira ao fim da ultima - o espaco entre elas entra, e a faixa le
 * como um trecho continuo, nao como palavras soltas.
 *
 * Diz so "aqui outra pessoa falava junto". Nao afirma de quem sao as
 * palavras dentro da faixa - isso e a pista pontilhada, outra coisa.
 */
export function faixasDaFala(
  palavrasTempo: [number, number, number, number][] | undefined,
  falante: string,
  regioes: RegiaoSobreposta[] | undefined,
): FaixaSobreposicao[] {
  if (!palavrasTempo?.length || !regioes?.length) return [];
  const faixas: FaixaSobreposicao[] = [];
  let indiceAnterior = -2;
  palavrasTempo.forEach(([posicao, comprimento, inicio, fim], i) => {
    const meio = (inicio + fim) / 2;
    const regiao = regioes.find(
      (r) => meio >= r.inicio && meio <= r.fim && r.falantes.some((n) => n !== falante),
    );
    if (!regiao) return;
    const outra = regiao.falantes.find((n) => n !== falante)!;
    const ultima = faixas[faixas.length - 1];
    // Emenda so com a palavra IMEDIATAMENTE anterior: uma palavra fora da
    // sobreposicao no meio quebra a faixa.
    if (ultima && ultima.outra === outra && indiceAnterior === i - 1) {
      ultima.fim = posicao + comprimento;
    } else {
      faixas.push({ inicio: posicao, fim: posicao + comprimento, outra });
    }
    indiceAnterior = i;
  });
  return faixas;
}
