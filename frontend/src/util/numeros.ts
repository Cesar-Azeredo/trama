import { localeAtual } from "../i18n/idioma";

/**
 * Números na tela pelo Intl, no idioma escolhido (0,772 em português,
 * 0.772 em inglês) - nunca toFixed, que sempre usa ponto.
 */
export function numero(valor: number, casas = 0): string {
  return new Intl.NumberFormat(localeAtual(), {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(valor);
}
