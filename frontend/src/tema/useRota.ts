import { useEffect, useRef, useState } from "react";
import { navegarComTransicao } from "./transicaoDeRota";

/**
 * Roteador minimo por hash - oito telas hoje, nao justifica trazer
 * react-router para um app local de um usuario so.
 *
 *   #/                                -> nova reuniao (tela inicial)
 *   #/reunioes                         -> lista de reunioes
 *   #/reuniao/<id>                     -> detalhe da reuniao <id>
 *   #/reuniao/<id>/em/<segundos>       -> detalhe, ja rolado ate a fala
 *                                         desse instante (busca da lista)
 *   #/reuniao/<id>/revisar             -> revisao da reuniao <id>
 *   #/reuniao/<id>/processando         -> acompanhar processamento (SSE)
 *   #/pessoas                          -> galeria de vozes
 *   #/perfil                           -> perfil e configuracoes (inclui o glossario)
 *
 * Enderecos antigos continuam abrindo algo coerente, nunca uma tela
 * errada em silencio: #/nova -> nova reuniao; #/glossario,
 * #/configuracoes e #/ajustes -> perfil (o glossario e as configuracoes
 * viraram secoes de Perfil).
 * Qualquer outra coisa desconhecida cai na tela inicial.
 *
 * "secao" agrupa rotas para a nav do cabecalho saber qual item destacar
 * (Cabecalho.tsx). Nova reuniao e secao propria (a primeira aba), nao
 * mais uma acao dentro de Reunioes. detalhe/revisao/processando sao
 * drill-down dentro de Reunioes - inclusive o processando que se abre
 * logo depois de "Transcrever" na Nova reuniao: ele e sobre UMA reuniao,
 * e o "voltar" dele leva a lista.
 */
export type Rota =
  | { tipo: "nova" }
  | { tipo: "lista" }
  | { tipo: "detalhe"; id: string; em?: number }
  | { tipo: "revisao"; id: string }
  | { tipo: "processando"; id: string }
  | { tipo: "pessoas" }
  | { tipo: "perfil" };

export type Secao = "nova" | "reunioes" | "pessoas" | "perfil";

export function secaoDaRota(rota: Rota): Secao {
  switch (rota.tipo) {
    case "nova":
      return "nova";
    case "pessoas":
      return "pessoas";
    case "perfil":
      return "perfil";
    default:
      return "reunioes";
  }
}

function lerRota(): Rota {
  const hash = window.location.hash.replace(/^#\/?/, "");
  const partes = hash.split("/").filter(Boolean);
  if (partes[0] === "reunioes") {
    return { tipo: "lista" };
  }
  if (partes[0] === "pessoas") {
    return { tipo: "pessoas" };
  }
  if (
    partes[0] === "perfil" ||
    partes[0] === "ajustes" ||
    partes[0] === "glossario" ||
    partes[0] === "configuracoes"
  ) {
    return { tipo: "perfil" };
  }
  if (partes[0] === "reuniao" && partes[1] && partes[2] === "revisar") {
    return { tipo: "revisao", id: partes[1] };
  }
  if (partes[0] === "reuniao" && partes[1] && partes[2] === "processando") {
    return { tipo: "processando", id: partes[1] };
  }
  if (partes[0] === "reuniao" && partes[1] && partes[2] === "em") {
    const em = Number(partes[3]);
    return Number.isFinite(em)
      ? { tipo: "detalhe", id: partes[1], em }
      : { tipo: "detalhe", id: partes[1] };
  }
  if (partes[0] === "reuniao" && partes[1]) {
    return { tipo: "detalhe", id: partes[1] };
  }
  return { tipo: "nova" };
}

export function useRota(): Rota {
  const [rota, setRota] = useState<Rota>(lerRota);
  const rotaRef = useRef(rota);

  useEffect(() => {
    rotaRef.current = rota;
  }, [rota]);

  useEffect(() => {
    const ouvir = () => {
      const nova = lerRota();
      navegarComTransicao(rotaRef.current, nova, () => setRota(nova));
    };
    window.addEventListener("hashchange", ouvir);
    return () => window.removeEventListener("hashchange", ouvir);
  }, []);

  return rota;
}
