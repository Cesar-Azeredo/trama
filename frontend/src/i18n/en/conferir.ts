import type { Catalogo } from "../textos";

export const conferir: Catalogo["conferir"] = {
  oTrechoCom: (forma) => `the passage with ${forma}`,
  vezesNestaReuniao: (n) => (n === 1 ? "1 time in this meeting" : `${n} times in this meeting`),
  estaCerto: "It's correct",
  corrigirPara: "Correct to…",
  ignorar: "Ignore",
  ignorado: (forma) => `“${forma}” ignored.`,
  agoraETermo: (forma) => `“${forma}” is now a company term.`,
  oQueE: (forma) => `What is ${forma}?`,
  opcional: "optional",
  gravando: "Saving…",
  confirmar: "Confirm",
  voltar: "Back",
  corrigido: (forma) => `“${forma}” corrected.`,
  corrigidoNestaFala: (forma) => `“${forma}” corrected in this utterance.`,
  irParaReuniao: "Go to the meeting",
  procurando: "Looking for terms to check…",
  titulo: "Terms to check",
  nota: "The voices are saved. These words may have been transcribed wrong - listen and answer the ones you want. Nothing here is required, and an answered term is never asked again.",
  tudoRespondido: "All answered.",
  concluir: "Done",
};
