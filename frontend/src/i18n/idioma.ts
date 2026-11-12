import { useSyncExternalStore } from "react";

/**
 * Idioma da interface: Português ou English, escolhido em Perfil >
 * Configurações > Idioma. Sem escolha salva, segue o idioma do navegador
 * (português se navigator.language começa com "pt", inglês em qualquer
 * outro caso). Mesmo desenho do tema (tema/useTema.ts): estado de módulo,
 * guardado no localStorage, lido também fora do React (formatação de data
 * e número em util/).
 *
 * Só o texto que a pessoa lê muda de idioma. Identificadores do código
 * continuam em português (ADR 0025), e a fala das pessoas nunca é
 * traduzida.
 */

export type Idioma = "pt" | "en";

export const IDIOMAS: Idioma[] = ["pt", "en"];

/** Nome de cada idioma no proprio idioma - nunca traduzido. */
export const NOME_DO_IDIOMA: Record<Idioma, string> = { pt: "Português", en: "English" };

const LOCALE: Record<Idioma, string> = { pt: "pt-BR", en: "en-US" };
const CHAVE_LOCALSTORAGE = "trama:idioma";

export function idiomaDoNavegador(linguagem: string | undefined): Idioma {
  return (linguagem ?? "").toLowerCase().startsWith("pt") ? "pt" : "en";
}

function lerIdiomaSalvo(): Idioma | null {
  try {
    const valor = localStorage.getItem(CHAVE_LOCALSTORAGE);
    return valor === "pt" || valor === "en" ? valor : null;
  } catch {
    // localStorage bloqueado (aba privada): segue o navegador, sem guardar.
    return null;
  }
}

function idiomaInicial(): Idioma {
  const salvo = typeof localStorage === "undefined" ? null : lerIdiomaSalvo();
  if (salvo) return salvo;
  return idiomaDoNavegador(typeof navigator === "undefined" ? undefined : navigator.language);
}

let atual: Idioma = idiomaInicial();
const ouvintes = new Set<() => void>();

function aplicar() {
  if (typeof document !== "undefined") document.documentElement.lang = LOCALE[atual];
}

/** Chamado UMA vez, em main.tsx. */
export function iniciarIdioma() {
  aplicar();
}

export function idiomaAtual(): Idioma {
  return atual;
}

/** Locale do Intl (datas, números) no idioma escolhido. */
export function localeAtual(): string {
  return LOCALE[atual];
}

export function definirIdioma(novo: Idioma) {
  atual = novo;
  try {
    localStorage.setItem(CHAVE_LOCALSTORAGE, novo);
  } catch {
    // conveniência - uma falha ao salvar não pode quebrar a troca em si.
  }
  aplicar();
  ouvintes.forEach((f) => f());
}

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

export function useIdioma(): Idioma {
  return useSyncExternalStore(assinar, () => atual);
}
