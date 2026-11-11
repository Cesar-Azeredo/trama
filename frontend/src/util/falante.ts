import type { FalaPorPessoa } from "../api/reunioes";
import { textosAtuais } from "../i18n/textos";

/**
 * Rotulos de maquina que nao sao uma pessoa: DESCONHECIDO_* (ninguem
 * identificado e ainda nao revisado) e IGNORADO_* (cluster ignorado na
 * revisao). Nunca aparecem crus na lista de reunioes - viram "voz nao
 * atribuida", contados, depois dos nomes de verdade.
 */
export function ehVozSemPessoa(nome: string): boolean {
  return nome.startsWith("DESCONHECIDO") || nome.startsWith("IGNORADO");
}

export function textoVozesSemPessoa(n: number): string {
  return textosAtuais().formatos.vozesSemPessoa(n);
}

/**
 * Ordem da barra de fala: pessoas primeiro (na ordem de fala_pct que o
 * servidor ja manda), vozes sem pessoa no fim. E o que mantem a lista de
 * nomes ao lado da barra batendo com os segmentos: nomes na mesma ordem, e
 * o "N vozes nao atribuidas" no fim, junto dos segmentos neutros do fim.
 */
export function ordemDaBarra(dinamica: FalaPorPessoa[]): FalaPorPessoa[] {
  return [
    ...dinamica.filter((d) => !ehVozSemPessoa(d.pessoa)),
    ...dinamica.filter((d) => ehVozSemPessoa(d.pessoa)),
  ];
}

/**
 * Rotulo exibido para cada nome de UMA reuniao. Pessoa fica como esta;
 * voz sem pessoa vira "voz não atribuída" - numerada ("voz não atribuída
 * 1", "2") so quando a reuniao tem mais de uma, senao duas vozes
 * diferentes ficariam indistinguiveis no transcript. Numerada na ordem
 * do rotulo cru (SPEAKER_00 antes de SPEAKER_02), estavel entre telas.
 */
export function rotulosDaReuniao(nomes: Iterable<string>): (nome: string) => string {
  const t = textosAtuais().formatos;
  const semPessoa = [...new Set(nomes)].filter(ehVozSemPessoa).sort();
  const mapa = new Map<string, string>();
  semPessoa.forEach((n, i) =>
    mapa.set(n, semPessoa.length === 1 ? t.vozSemPessoa : t.vozSemPessoaNumerada(i + 1)),
  );
  return (nome: string) =>
    mapa.get(nome) ?? (ehVozSemPessoa(nome) ? t.vozSemPessoa : nome);
}

