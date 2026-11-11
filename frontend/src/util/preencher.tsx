import { Fragment, type ReactNode } from "react";

/**
 * Frase do catalogo com {marcador}: cada marcador vira o elemento dado
 * (numero ou trecho com estilo proprio), o resto continua texto. A frase
 * inteira vem do catalogo, na ordem do idioma - nunca pedacos colados.
 *
 * Por isso o catalogo escreve "{total}" SEM $ em frases como
 * correcao.aparece: o marcador e substituido aqui, por um <span> com o
 * numero estilizado, e nao pela interpolacao do template.
 */
export function preencher(modelo: string, partes: Record<string, ReactNode>): ReactNode[] {
  return modelo.split(/(\{[a-z]+\})/).map((pedaco, i) => {
    const chave = pedaco.match(/^\{([a-z]+)\}$/)?.[1];
    return chave !== undefined && chave in partes ? (
      <Fragment key={i}>{partes[chave]}</Fragment>
    ) : (
      pedaco
    );
  });
}
