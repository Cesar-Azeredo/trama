import type { Catalogo } from "../textos";

export const conferir: Catalogo["conferir"] = {
  oTrechoCom: (forma) => `the passage with ${forma}`,
  vezesNestaReuniao: (n) => (n === 1 ? "1 time in this meeting" : `${n} times in this meeting`),
  estaCerto: "It's correct",
  corrigirPara: "Change to…",
  ignorar: "Ignore",
  ignorado: (forma) => `“${forma}” ignored.`,
  agoraETermo: (forma) => `“${forma}” is now a company term.`,
  oQueE: (forma) => `What is ${forma}?`,
  opcional: "optional",
  gravando: "Saving…",
  confirmar: "Confirm",
  voltar: "Back",
  corrigido: (forma) => `“${forma}” corrected.`,
  corrigidoNestaFala: (forma) => `“${forma}” corrected in this segment.`,
  irParaReuniao: "Go to the meeting",
  procurando: "Looking for terms to check…",
  titulo: "Terms to check",
  nota: "Voices saved. These words may have been mistranscribed — listen and answer any you like. Nothing here is required, and you'll never be asked about the same term twice.",
  tudoRespondido: "All answered.",
  concluir: "Done",
};
