import { useTextos, type Catalogo } from "./textos";

/**
 * Mensagem que a tela guarda para mostrar depois (erro, aviso, "feito"):
 * nunca texto pronto, sempre uma funcao do catalogo, resolvida no render.
 * Guardada assim, trocar de idioma redesenha a mensagem que ja esta na tela
 * - texto pronto ficaria no idioma do momento em que chegou (ADR 0026).
 */
export interface Mensagem {
  texto: (t: Catalogo) => string;
}

export function mensagem(texto: (t: Catalogo) => string): Mensagem {
  return { texto };
}

/** Para o render: resolve a Mensagem no idioma atual (null fica null). */
export function useMensagem(): (m: Mensagem | null | undefined) => string | null {
  const t = useTextos();
  return (m) => (m ? m.texto(t) : null);
}
