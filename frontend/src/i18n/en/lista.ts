import type { Catalogo } from "../textos";

export const lista: Catalogo["lista"] = {
  iniciando: "Starting…",
  interrompeuMais: (pessoa) => `${pessoa} interrupted most`,
  ninguemInterrompeu: "no one interrupted",
  disputas: (n) => (n === 1 ? "contested turn" : "contested turns"),
  semDinamica: "no dynamics",
  revisar: "Review",
  naFala: "In the transcript",
  maisFalas: (n) => (n === 1 ? "and 1 more utterance in this meeting" : `and ${n} more utterances in this meeting`),
  carregando: "Loading meetings…",
  semReunioes: "No meetings found in audios/.",
  buscar: "Search",
  placeholderBusca: "Title, person or passage",
  contagemBusca: (encontradas, total) => `${encontradas} of ${total}`,
  contagem: (n) => (n === 1 ? "1 meeting" : `${n} meetings`),
  semResultado: (busca) => `No meetings matching “${busca}”.`,
};
