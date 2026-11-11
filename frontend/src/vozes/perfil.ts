/**
 * Abaixo disto de voz aprendida (peso_s em GET /api/pessoas), o perfil
 * ainda esta "em formacao" - a comparacao contra ele ainda e instavel
 * (ADR 0011: fica mais estavel a cada revisao). Um numero so, usado pela
 * Nova reuniao (bloco Galeria) e pela tela Pessoas - nunca dois limiares
 * que divergem.
 */
export const PERFIL_EM_FORMACAO_S = 120;

export function perfilEmFormacao(pesoS: number): boolean {
  return pesoS < PERFIL_EM_FORMACAO_S;
}
