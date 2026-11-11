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
  mostrarInteracoes: "Show interactions (acknowledgments, interruptions, crosstalk)",
  legendaFaixa: "Highlighted text: someone else was talking at the same time (shown in their color).",
  corrigir: "Correct",
  falaDe: (nome, tempo) => `${nome} at ${tempo}`,
  tipoEvento: {
    apoio: "acknowledgment",
    interrupcao: "interruption",
    disputa: "crosstalk",
  },
  ocorrenciaEvento: (tempo, tipo, aproximado) =>
    `${tempo} ${tipo}` + (aproximado ? " (nearest segment, not exact)" : ""),
  confiancaBaixa: "low confidence",
  tituloConfiancaBaixa: (pct) =>
    `Low average confidence in this segment (${pct}%) — worth checking the audio before quoting`,
  editadoAMao: "edited by hand",
  tituloEditada: (original) => `Corrected by hand. Transcribed text: “${original}”`,
  lacuna: "[untranscribed audio]",
  tituloLacuna:
    "No words were transcribed here (laughter, coughing, background noise) — the transcript doesn't guess what it was",
  tituloPista: (nome) => `Possibly ${nome} — word-level guess, not confirmed`,
  tituloSobreposicao: (nome) => `Overlap: ${nome} was speaking at the same time`,
  pctDaFala: (pct) => `${pct}% of speaking time`,
  interrompeu: (n) => `interrupted ${n}×`,
  foiInterrompido: (n) => `was interrupted ${n}×`,
};
