/**
 * Selecao do navegador -> posicao no TEXTO da fala (fala.texto), para o
 * "Corrigir" do Detalhe (ADR 0019).
 *
 * O texto exibido pode ter marcas inseridas que nao estao em fala.texto
 * ("[som não transcrito]", .marca-lacuna) e o lapis de corrigir: os dois
 * saem da contagem. O resultado so vale se o trecho bater exatamente com o
 * texto da fala naquelas posicoes - senao, nada (sem chute).
 */

export interface SelecaoNaFala {
  /** Elemento do texto da fala (tem data-indice). */
  elemento: HTMLElement;
  indice: number;
  inicio: number;
  fim: number;
}

const FORA_DA_CONTAGEM = ".marca-lacuna, .botao-corrigir-fala";

function falaDe(no: Node | null): HTMLElement | null {
  const el = no instanceof Element ? no : no?.parentElement;
  return el?.closest<HTMLElement>("[data-indice]") ?? null;
}

function posicaoAte(elemento: HTMLElement, no: Node, offset: number): number {
  const pedaco = document.createRange();
  pedaco.setStart(elemento, 0);
  pedaco.setEnd(no, offset);
  const frag = pedaco.cloneContents();
  frag.querySelectorAll(FORA_DA_CONTAGEM).forEach((n) => n.remove());
  return (frag.textContent ?? "").length;
}

/** Tira das pontas o que nao e palavra (espaco, pontuacao): o clique duplo
 * do Safari leva o espaco junto, e "Aprovium," nao e o termo. */
export function aparar(texto: string, inicio: number, fim: number): [number, number] {
  const ehPalavra = (c: string) => /[\p{L}\p{N}]/u.test(c);
  while (inicio < fim && !ehPalavra(texto[inicio])) inicio++;
  while (fim > inicio && !ehPalavra(texto[fim - 1])) fim--;
  return [inicio, fim];
}

export function selecaoNaFala(textoDaFala: (indice: number) => string | undefined): SelecaoNaFala | null {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return null;
  const r = sel.getRangeAt(0);
  const elemento = falaDe(r.startContainer);
  // Selecao que atravessa duas falas: nao ha um trecho so para corrigir.
  if (!elemento || elemento !== falaDe(r.endContainer)) return null;
  const indice = Number(elemento.dataset.indice);
  const texto = textoDaFala(indice);
  if (texto === undefined) return null;

  const a = posicaoAte(elemento, r.startContainer, r.startOffset);
  const b = posicaoAte(elemento, r.endContainer, r.endOffset);
  const frag = r.cloneContents();
  frag.querySelectorAll(FORA_DA_CONTAGEM).forEach((n) => n.remove());
  if (b <= a || texto.slice(a, b) !== (frag.textContent ?? "")) return null;

  const [inicio, fim] = aparar(texto, a, b);
  if (fim <= inicio) return null;
  return { elemento, indice, inicio, fim };
}
