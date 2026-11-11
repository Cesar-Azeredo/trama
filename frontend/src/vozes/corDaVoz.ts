/**
 * Cor de voz estavel POR PESSOA (SKILL.md: "estaveis"), nunca pela
 * posicao dela na lista de uma reuniao especifica - senao o Celso seria
 * uma cor na reuniao_08 e outra na reuniao_09 so porque a ordem por
 * fala_pct mudou entre as duas.
 *
 * Prioridade: ORDEM DE ENTRADA na galeria (primeira_aparicao de
 * GET /api/pessoas), desempatada pelo nome. Ate 2026-09-24 era a ordem
 * alfabetica - que nao e estavel: uma pessoa nova no meio do alfabeto
 * empurrava a cor de todo mundo depois dela. Na ordem de entrada, quem
 * chega entra no fim e ninguem troca de cor. (Excluir alguem da galeria
 * ainda desloca quem entrou depois - nao ha onde guardar a cor sem
 * mudar o schema.)
 *
 * Zero colisao para ate 8 pessoas (a paleta tem 8, conferidas entre si em
 * tests/test_paleta.py). Um hash do nome foi testado primeiro e
 * descartado: com so 5 nomes reais ja colidia duas vezes. O hash so entra
 * como ultimo recurso, para quem nao esta na galeria (ex:
 * "DESCONHECIDO_S0" antes da primeira revisao).
 */

import { ehVozSemPessoa } from "../util/falante";

const TOTAL_VOZES = 8;

function hashDoNome(nome: string): number {
  let hash = 0;
  for (let i = 0; i < nome.length; i++) {
    hash = (hash * 31 + nome.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % TOTAL_VOZES;
}

export function construirIndiceGaleria(
  pessoas: { nome: string; primeira_aparicao: string | null }[],
): Map<string, number> {
  // Sem data (nao deveria acontecer - toda pessoa da galeria tem base
  // legada ou contribuicao) vai pro fim, nunca pro comeco: nao desloca
  // quem ja tem cor.
  const chave = (p: { primeira_aparicao: string | null }) =>
    p.primeira_aparicao ?? "9999";
  const ordenadas = [...pessoas].sort(
    (a, b) =>
      // pt-BR fixo, nunca o idioma da interface: trocar de idioma nao pode
      // mudar a ordem e, com ela, a cor de ninguem.
      chave(a).localeCompare(chave(b)) || a.nome.localeCompare(b.nome, "pt-BR"),
  );
  const mapa = new Map<string, number>();
  ordenadas.forEach((p, i) => mapa.set(p.nome, i % TOTAL_VOZES));
  return mapa;
}

/**
 * Cor de MARCA (fita de tempo, barra de fala, sublinhado de pista). Voz
 * sem pessoa (DESCONHECIDO_/IGNORADO_) e --tinta-tenue, o tom de falante
 * nao identificado (SKILL.md) - nunca uma cor de voz por hash, que
 * poderia repetir a de uma pessoa de verdade.
 */
export function corDaVoz(
  nome: string,
  indiceGaleria: Map<string, number>,
): string {
  if (ehVozSemPessoa(nome)) return "var(--tinta-tenue)";
  const indice = indiceGaleria.get(nome) ?? hashDoNome(nome);
  return `var(--voz-${indice + 1})`;
}

/**
 * Cor de TEXTO para um nome (margem do transcript, marca de evento,
 * palavra de pista). Igual a corDaVoz para pessoas - as oito cores de voz
 * passam 4,5:1 (tests/test_paleta.py). Para voz sem pessoa e --tinta-fraca,
 * nao --tinta-tenue: o tenue so passa 3:1, e SKILL.md o reserva para texto
 * de 24px ou mais e para o que nao e texto.
 */
export function corDoTextoDaVoz(
  nome: string,
  indiceGaleria: Map<string, number>,
): string {
  return ehVozSemPessoa(nome) ? "var(--tinta-fraca)" : corDaVoz(nome, indiceGaleria);
}
