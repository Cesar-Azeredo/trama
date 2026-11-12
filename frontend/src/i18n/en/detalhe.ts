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
  tituloLacunaEscrita:
    "Written by hand by someone who listened to the passage — not from the automatic transcript",
  apagarReuniao: "Delete meeting",
  apagarTitulo: (titulo) => `Delete ${titulo}?`,
  apagarTexto:
    "Deletes the audio, the transcript, the corrections and the review answers of this meeting. This can't be undone.",
  apagarCalculando: "Working out how much voice leaves the database…",
  apagarSemVoz: "No learned voice comes from this meeting: the gallery doesn't change.",
  apagarPerdas: "The voice learned from this meeting also leaves the database:",
  apagarPerde: (nome, perde, fica) => `${nome} loses ${perde} of voice (keeps ${fica}).`,
  apagarPerdeTudo: (nome, perde) =>
    `${nome} loses ${perde} of voice — that was all of it, and ${nome} leaves the gallery.`,
  apagarBackups: "Old database backups (vozes.db.bak files) are not changed.",
  apagando: "Deleting…",
  cancelar: "Cancel",
  segundos: (valor) => `${valor} s`,
  tituloPista: (nome) => `Possibly ${nome} — word-level guess, not confirmed`,
  tituloSobreposicao: (nome) => `Overlap: ${nome} was speaking at the same time`,
  pctDaFala: (pct) => `${pct}% of speaking time`,
  interrompeu: (n) => `interrupted ${n}×`,
  foiInterrompido: (n) => `was interrupted ${n}×`,
};
