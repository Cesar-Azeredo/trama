import type { Catalogo } from "../textos";

export const formatos: Catalogo["formatos"] = {
  tituloPadrao: (numero) => `Meeting ${numero}`,
  chegouEm: (data) => `arrived on ${data}`,
  processar: "Process",
  processando: "Processing…",
  tentarNovamente: "Try again",
  vozSemPessoa: "unassigned voice",
  vozSemPessoaNumerada: (n) => `unassigned voice ${n}`,
  vozesSemPessoa: (n) => (n === 1 ? "1 unassigned voice" : `${n} unassigned voices`),
  grupoFila: "In the queue",
  grupoARevisar: "To review",
  grupoSemData: "No recording date",
};
