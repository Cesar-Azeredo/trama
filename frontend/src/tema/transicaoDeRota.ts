import { flushSync } from "react-dom";
import { secaoDaRota, type Rota } from "./useRota";

/**
 * Skill apple-design (via ADR 0012 - so a parte de movimento/resposta,
 * nunca o vocabulario de material) diferencia trocar de LUGAR (secoes
 * irmas: Nova reuniao/Reunioes/Pessoas/Perfil) de descer/subir uma
 * HIERARQUIA (Lista -> Detalhe -> Revisao/Processando). "secao" e
 * crossfade sem direcao; "avancar"/"voltar" espelham o mesmo caminho
 * (principio 7: "se algo desaparece de um jeito, esperamos que
 * reapareca de onde veio").
 *
 * Profundidade e um mapa estatico, nao uma pilha de historico real - o
 * roteador e por hash, sem back/forward de verdade (useRota.ts). E
 * suficiente pro caso real: nenhuma tela tem mais de um "de onde vim"
 * plausivel na pratica.
 */
const PROFUNDIDADE: Record<Rota["tipo"], number> = {
  nova: 0,
  lista: 0,
  detalhe: 1,
  processando: 2,
  revisao: 2,
  pessoas: 0,
  perfil: 0,
};

export type TipoTransicao = "secao" | "avancar" | "voltar";

function tipoDeTransicao(anterior: Rota, nova: Rota): TipoTransicao {
  if (secaoDaRota(anterior) !== secaoDaRota(nova)) return "secao";
  return PROFUNDIDADE[nova.tipo] < PROFUNDIDADE[anterior.tipo]
    ? "voltar"
    : "avancar";
}

/**
 * Aplica a mudanca de rota dentro de uma View Transition nativa do
 * navegador quando da pra animar - nunca uma biblioteca nova (o app ja
 * tem zero dependencia de motion). Sem suporte (Safari mais antigo) ou
 * com "prefers-reduced-motion", cai direto no `aplicar()` simples -
 * exatamente o comportamento de antes desta mudanca, nunca quebra.
 *
 * Reduced motion e tratado SO aqui, nunca em CSS - `startViewTransition`
 * simplesmente nao e chamado, entao as animacoes em estilos/transicoes.css
 * nunca rodam. Um `@media` duplicando essa checagem no CSS seria o mesmo
 * cenario coberto duas vezes.
 */
export function navegarComTransicao(
  anterior: Rota,
  nova: Rota,
  aplicar: () => void,
) {
  const podeAnimar =
    typeof document.startViewTransition === "function" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (!podeAnimar) {
    aplicar();
    return;
  }

  document.documentElement.dataset.transicao = tipoDeTransicao(anterior, nova);
  document.startViewTransition(() => flushSync(aplicar));
}
