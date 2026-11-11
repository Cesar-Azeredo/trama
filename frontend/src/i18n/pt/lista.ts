/** Tela Lista de reuniões (telas/Lista.tsx). */
export const lista = {
  iniciando: "Iniciando…",
  interrompeuMais: (pessoa: string) => `${pessoa} interrompeu mais`,
  ninguemInterrompeu: "ninguém interrompeu",
  disputas: (n: number): string => (n === 1 ? "disputa" : "disputas"),
  semDinamica: "sem dinâmica",
  revisar: "Revisar",
  naFala: "Na fala",
  maisFalas: (n: number) => (n === 1 ? "e mais 1 fala nesta reunião" : `e mais ${n} falas nesta reunião`),
  carregando: "Carregando reuniões…",
  semReunioes: "Nenhuma reunião encontrada em audios/.",
  buscar: "Buscar",
  placeholderBusca: "Título, pessoa ou trecho da fala",
  contagemBusca: (encontradas: number, total: number) => `${encontradas} de ${total}`,
  contagem: (n: number) => (n === 1 ? "1 reunião" : `${n} reuniões`),
  semResultado: (busca: string) => `Nenhuma reunião com “${busca}”.`,
};
