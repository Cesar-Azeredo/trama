import type { Catalogo } from "../textos";

export const lista: Catalogo["lista"] = {
  iniciando: "Starting…",
  interrompeuMais: (pessoa) => `${pessoa} interrupted most`,
  ninguemInterrompeu: "no one interrupted",
  disputas: (n) => (n === 1 ? "crosstalk moment" : "crosstalk moments"),
  semDinamica: "no dynamics data",
  revisar: "Review",
  naFala: "In the transcript",
  maisFalas: (n) => (n === 1 ? "and 1 more segment in this meeting" : `and ${n} more segments in this meeting`),
  carregando: "Loading meetings…",
  semReunioes: "No meetings yet. Upload your first one in New meeting.",
  buscar: "Search",
  placeholderBusca: "Title, person or passage",
  contagemBusca: (encontradas, total) => `${encontradas} of ${total}`,
  contagem: (n) => (n === 1 ? "1 meeting" : `${n} meetings`),
  semResultado: (busca) => `No meetings matching “${busca}”.`,
};
