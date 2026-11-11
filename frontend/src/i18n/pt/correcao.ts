/**
 * Correção de fala, de trecho e de título (componentes/PainelCorrecao,
 * FalaEditavel, TituloEditavel) e as peças visuais da reunião
 * (FitaDeTempo, BarraFala).
 *
 * Modelos com {marcador}: o componente troca cada marcador por um
 * elemento (número ou trecho com estilo próprio) - a frase inteira fica
 * aqui, na ordem do idioma.
 */
export const correcao = {
  // PainelCorrecao
  tituloPainel: "Corrigir “{trecho}”",
  oCertoE: "O certo é",
  ondeCorrigir: "Onde corrigir",
  soNestaFala: "Só nesta fala",
  emTodas: "Em todas as reuniões e nas próximas",
  conferindo: "Conferindo as reuniões…",
  naoAparece: "Não aparece em nenhuma reunião processada. Vale para as próximas.",
  /** Modelo com {total} e {reunioes}. */
  aparece: (total: number, reunioes: number) =>
    `Aparece {total} ${total === 1 ? "vez" : "vezes"} em {reunioes} ${reunioes === 1 ? "reunião" : "reuniões"}`,
  oQueEIsso: "O que é isso?",
  opcional: "opcional",
  exemploDescricao: "ex.: ferramenta de aprovação de projetos",
  corrigir: "Corrigir",
  corrigirEmLugares: (n: number) => `Corrigir em ${n} ${n === 1 ? "lugar" : "lugares"}`,
  corrigirEmTodas: "Corrigir em todas",
  corrigindo: "Corrigindo…",
  cancelar: "Cancelar",
  fechar: "Fechar",
  corrigidoEmTodas: (total: number, reunioes: number) =>
    `Corrigido em ${total} ${total === 1 ? "lugar" : "lugares"}` +
    (reunioes > 1 ? `, em ${reunioes} reuniões` : "") +
    ". Vale também para as próximas reuniões.",
  // VariacoesParecidas
  procurandoParecidas: "Procurando formas parecidas…",
  talvezTambem: (certo: string) => `Talvez estas também sejam ${certo}`,
  vezes: (n: number) => (n === 1 ? `${n} vez` : `${n} vezes`),
  jaTinhaDuvida: "a transcrição já tinha dúvida",
  marqueAsQueSao: "Marque as que são",
  corrigirMarcadas: (n: number) => (n === 1 ? "Corrigir a marcada" : `Corrigir as ${n} marcadas`),
  maisCorrigidos: (n: number) => `Mais ${n} ${n === 1 ? "lugar corrigido" : "lugares corrigidos"}.`,
  // FalaEditavel
  editarFala: "Editar o texto desta fala",
  tituloEditarFala: "Editar o texto da fala inteira",
  textoDaFala: "Texto da fala",
  ajudaFala: "Enter grava, Esc cancela.",
  voltarAoOriginal: "Voltar ao original",
  textoTranscrito: (original: string) => `Texto transcrito: “${original}”`,
  // TituloEditavel
  cliqueParaEditarTitulo: "Clique para editar o título",
  tituloDaReuniao: "Título da reunião",
  ajudaTitulo: "Enter grava, Esc cancela. Vazio volta para o nome padrão.",
  // FitaDeTempo
  fitaDeTempo: "Fita de tempo da reunião inteira. Clique para saltar o transcript para aquele ponto.",
  // BarraFala
  tempoDeFala: (itens: string) => `Tempo de fala: ${itens}`,
  itemTempoDeFala: (nome: string, pct: string) => `${nome} ${pct}%`,
};
