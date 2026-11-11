import { useSyncExternalStore } from "react";

/**
 * Aparencia (SKILL.md: "Escolha do modo"): claro, escuro ou seguir o
 * sistema - escolhida em Perfil > Configuracoes > Aparencia, nao mais num
 * botao do cabecalho. "sistema" e o padrao e e a AUSENCIA de escolha
 * salva (nada no localStorage), exatamente como index.html le antes do
 * React montar - as duas leituras nunca podem divergir.
 *
 * Estado de modulo (useSyncExternalStore), nao de componente: o tema vale
 * para o app inteiro, inclusive enquanto a tela de Perfil nem esta
 * montada - e quem acompanha o sistema em tempo real (iniciarTema) tem
 * que rodar desde o primeiro quadro, nao so quando alguem abre Perfil.
 */

export type Tema = "claro" | "escuro";
export type PreferenciaTema = Tema | "sistema";

const CHAVE_LOCALSTORAGE = "rec-meet:tema";
const CONSULTA = "(prefers-color-scheme: dark)";

function lerPreferenciaSalva(): PreferenciaTema {
  try {
    const valor = localStorage.getItem(CHAVE_LOCALSTORAGE);
    return valor === "claro" || valor === "escuro" ? valor : "sistema";
  } catch {
    // localStorage pode estar bloqueado (aba privada, politica do SO) -
    // nesse caso so segue o sistema, sem guardar nada.
    return "sistema";
  }
}

function salvarPreferencia(preferencia: PreferenciaTema) {
  try {
    if (preferencia === "sistema") localStorage.removeItem(CHAVE_LOCALSTORAGE);
    else localStorage.setItem(CHAVE_LOCALSTORAGE, preferencia);
  } catch {
    // conveniencia - uma falha ao salvar nao pode quebrar a troca em si.
  }
}

let preferencia: PreferenciaTema = lerPreferenciaSalva();
const ouvintes = new Set<() => void>();

function temaEfetivo(): Tema {
  if (preferencia !== "sistema") return preferencia;
  return window.matchMedia(CONSULTA).matches ? "escuro" : "claro";
}

function aplicar() {
  document.documentElement.setAttribute("data-tema", temaEfetivo());
}

/** Chamado UMA vez, em main.tsx. */
export function iniciarTema() {
  aplicar();
  window.matchMedia(CONSULTA).addEventListener("change", () => {
    if (preferencia === "sistema") aplicar();
  });
}

export function definirPreferenciaTema(nova: PreferenciaTema) {
  preferencia = nova;
  salvarPreferencia(nova);
  aplicar();
  ouvintes.forEach((f) => f());
}

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

export function usePreferenciaTema(): PreferenciaTema {
  return useSyncExternalStore(assinar, () => preferencia);
}
