/**
 * O app se chamava rec-meet e guardava as preferencias em chaves
 * "rec-meet:*" do localStorage. Agora sao "trama:*". Na primeira abertura
 * depois da troca, cada valor antigo e copiado para a chave nova (se a
 * nova ainda nao existir) e a antiga e apagada - o tema, o idioma e o
 * perfil de quem ja usava nao se perdem.
 *
 * Importado PRIMEIRO em main.tsx: useTema, idioma e perfilLocal leem o
 * localStorage ao carregar o modulo, entao a copia tem que vir antes.
 * index.html le o tema antes de qualquer modulo; por isso ele ainda
 * aceita a chave antiga (so na primeira abertura ela existe).
 */

export const PREFIXO = "trama:";
export const PREFIXO_ANTIGO = "rec-meet:";
export const SUFIXOS = ["tema", "idioma", "perfil", "mostrar-eventos"] as const;

type Armazenamento = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function migrarChaves(armazenamento: Armazenamento) {
  for (const sufixo of SUFIXOS) {
    const antiga = PREFIXO_ANTIGO + sufixo;
    const valor = armazenamento.getItem(antiga);
    if (valor === null) continue;
    if (armazenamento.getItem(PREFIXO + sufixo) === null) {
      armazenamento.setItem(PREFIXO + sufixo, valor);
    }
    armazenamento.removeItem(antiga);
  }
}

try {
  migrarChaves(localStorage);
} catch {
  // localStorage bloqueado (aba privada) ou indisponivel (testes em node):
  // nao ha o que migrar, e cada leitor ja trata a falha do proprio jeito.
}
