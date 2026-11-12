/** Tela de detalhe da reunião (telas/Detalhe.tsx). */
export const detalhe = {
  carregando: "Carregando reunião…",
  arquivo: "Arquivo",
  tamanho: "Tamanho",
  duracao: "Duração",
  iniciando: "Iniciando…",
  revisada: "Revisada",
  editarRevisao: "Editar revisão",
  revisar: "Revisar",
  baixarTranscricao: "Baixar transcrição (.txt)",
  dinamicaDaReuniao: "Dinâmica da reunião",
  mostrarInteracoes: "Mostrar interações (apoios, interrupções, disputas)",
  legendaFaixa: "Fundo colorido no texto: outra pessoa falava ao mesmo tempo, na cor dela.",
  corrigir: "Corrigir",
  /** Completa comum.tocar/comum.pausar no botão de tocar de cada fala. */
  falaDe: (nome: string, tempo: string) => `fala de ${nome} em ${tempo}`,
  tipoEvento: {
    apoio: "apoio",
    interrupcao: "interrupção",
    disputa: "disputa",
  },
  /** Uma linha do title da marca de evento, por ocorrência. */
  ocorrenciaEvento: (tempo: string, tipo: string, aproximado: boolean) =>
    `${tempo} ${tipo}` + (aproximado ? " (fala mais próxima, não exata)" : ""),
  confiancaBaixa: "confiança baixa",
  tituloConfiancaBaixa: (pct: string) =>
    `Confiança média baixa nesta fala (${pct}%) - vale conferir o áudio antes de citar`,
  editadoAMao: "editado à mão",
  tituloEditada: (original: string) => `Corrigido à mão. Texto transcrito: “${original}”`,
  lacuna: "[som não transcrito]",
  tituloLacuna:
    "Trecho sem nenhuma palavra transcrita aqui (ex.: riso, gesto, respiração) - a transcrição não afirma o que era",
  tituloLacunaEscrita:
    "Escrito à mão por quem ouviu o trecho - não veio da transcrição automática",
  apagarReuniao: "Apagar reunião",
  apagarTitulo: (titulo: string) => `Apagar ${titulo}?`,
  apagarTexto:
    "Apaga o áudio, a transcrição, as correções e as respostas da revisão desta reunião. Não dá para desfazer.",
  apagarCalculando: "Calculando quanto de voz sai do banco…",
  apagarSemVoz: "Nenhuma voz aprendida vem desta reunião: a galeria não muda.",
  apagarPerdas: "A voz aprendida desta reunião também sai do banco:",
  apagarPerde: (nome: string, perde: string, fica: string) =>
    `${nome} perde ${perde} de voz (fica com ${fica}).`,
  apagarPerdeTudo: (nome: string, perde: string) =>
    `${nome} perde ${perde} de voz - era toda a voz aprendida, e ${nome} sai da galeria.`,
  apagarBackups:
    "Cópias de segurança antigas do banco (arquivos vozes.db.bak) não são alteradas.",
  apagando: "Apagando…",
  cancelar: "Cancelar",
  segundos: (valor: string) => `${valor} s`,
  tituloPista: (nome: string) => `Pista: pode ser ${nome} - atribuição por palavra, não confirmada`,
  tituloSobreposicao: (nome: string) => `Sobreposição: ${nome} falava ao mesmo tempo`,
  pctDaFala: (pct: string) => `${pct}% da fala`,
  interrompeu: (n: number) => `interrompeu ${n}×`,
  foiInterrompido: (n: number) => `foi interrompido ${n}×`,
};
