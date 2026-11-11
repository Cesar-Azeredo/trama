/** Textos montados em util/ (formatação compartilhada entre telas). */
export const formatos = {
  tituloPadrao: (numero: string) => `Reunião ${numero}`,
  chegouEm: (data: string) => `chegou em ${data}`,
  processar: "Processar",
  processando: "Processando…",
  tentarNovamente: "Tentar novamente",
  vozSemPessoa: "voz não atribuída",
  vozSemPessoaNumerada: (n: number) => `voz não atribuída ${n}`,
  vozesSemPessoa: (n: number) => (n === 1 ? "1 voz não atribuída" : `${n} vozes não atribuídas`),
  grupoFila: "Na fila",
  grupoARevisar: "A revisar",
  grupoSemData: "Sem data da gravação",
};
