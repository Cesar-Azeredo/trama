import type { Catalogo } from "../textos";

export const detalhe: Catalogo["detalhe"] = {
  carregando: "Loading meeting…",
  arquivo: "File",
  tamanho: "Size",
  duracao: "Duration",
  iniciando: "Starting…",
  revisada: "Reviewed",
  editarRevisao: "Edit review",
  revisar: "Review",
  baixarTranscricao: "Download transcript (.txt)",
  dinamicaDaReuniao: "Meeting dynamics",
  mostrarInteracoes: "Show interactions (backchannels, interruptions, contested turns)",
  legendaFaixa: "Colored background on the text: someone else was speaking at the same time, in their color.",
  corrigir: "Correct",
  falaDe: (nome, tempo) => `passage by ${nome} at ${tempo}`,
  tipoEvento: {
    apoio: "backchannel",
    interrupcao: "interruption",
    disputa: "contested turn",
  },
  ocorrenciaEvento: (tempo, tipo, aproximado) =>
    `${tempo} ${tipo}` + (aproximado ? " (nearest utterance, not exact)" : ""),
  confiancaBaixa: "low confidence",
  tituloConfiancaBaixa: (pct) =>
    `Low average confidence in this utterance (${pct}%) - worth checking the audio before quoting`,
  editadoAMao: "edited by hand",
  tituloEditada: (original) => `Corrected by hand. Transcribed text: “${original}”`,
  lacuna: "[untranscribed audio]",
  tituloLacuna:
    "No words were transcribed here (e.g. laughter, a gesture, breathing) - the transcript does not claim what it was",
  tituloPista: (nome) => `Hint: may be ${nome} - word-level attribution, not confirmed`,
  tituloSobreposicao: (nome) => `Overlap: ${nome} was speaking at the same time`,
  pctDaFala: (pct) => `${pct}% of speaking time`,
  interrompeu: (n) => `interrupted ${n}×`,
  foiInterrompido: (n) => `was interrupted ${n}×`,
};
