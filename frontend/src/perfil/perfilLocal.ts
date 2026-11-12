import { useSyncExternalStore } from "react";

/**
 * Quem usa o app nesta maquina: um nome e, opcionalmente, qual pessoa da
 * galeria e ela. Guardado so no localStorage - nao existe login nem
 * multiusuario (CLAUDE.md: um processo em localhost, um
 * usuario). Nunca vai para o servidor.
 */

export interface PerfilLocal {
  nome: string;
  pessoa: string | null;
}

const CHAVE = "trama:perfil";
const VAZIO: PerfilLocal = { nome: "", pessoa: null };

function ler(): PerfilLocal {
  try {
    const bruto = localStorage.getItem(CHAVE);
    if (!bruto) return VAZIO;
    const dados = JSON.parse(bruto);
    return {
      nome: typeof dados?.nome === "string" ? dados.nome : "",
      pessoa: typeof dados?.pessoa === "string" ? dados.pessoa : null,
    };
  } catch {
    // bloqueado ou corrompido - comeca vazio, nunca quebra a tela.
    return VAZIO;
  }
}

let atual: PerfilLocal = ler();
const ouvintes = new Set<() => void>();

export function salvarPerfil(novo: PerfilLocal) {
  atual = novo;
  try {
    localStorage.setItem(CHAVE, JSON.stringify(novo));
  } catch {
    // conveniencia local - sem armazenamento, vale so ate recarregar.
  }
  ouvintes.forEach((f) => f());
}

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

export function usePerfilLocal(): PerfilLocal {
  return useSyncExternalStore(assinar, () => atual);
}
