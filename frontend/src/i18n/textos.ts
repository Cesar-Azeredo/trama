import { en } from "./en";
import { idiomaAtual, useIdioma, type Idioma } from "./idioma";
import { pt } from "./pt";

/** Formato dos catálogos: o de português é a referência. */
export type Catalogo = typeof pt;

const CATALOGOS: Record<Idioma, Catalogo> = { pt, en };

export function catalogo(idioma: Idioma): Catalogo {
  return CATALOGOS[idioma];
}

/** Textos no idioma atual, re-renderizando quando ele muda. */
export function useTextos(): Catalogo {
  return CATALOGOS[useIdioma()];
}

/** Fora do React (util/, api/): lê o idioma atual no momento da chamada. */
export function textosAtuais(): Catalogo {
  return CATALOGOS[idiomaAtual()];
}
