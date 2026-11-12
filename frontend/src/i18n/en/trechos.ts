import type { Catalogo } from "../textos";

export const trechos: Catalogo["trechos"] = {
  procurando: "Looking for passages to check…",
  titulo: "Passages to check",
  nota: "The transcript may have gotten these wrong or left something out. Listen and write what was said. Nothing here is required, and a passage you answer is not asked again.",
  cabecaFala: (nome, hora) => `${nome}, ${hora} · low confidence`,
  cabecaLacuna: (nome, hora) => `${nome}, ${hora} · untranscribed audio`,
  oTrechoDe: (nome, hora) => `the passage by ${nome} at ${hora}`,
  oQueFoiDito: "What was said",
  oQueFoiDitoAqui: "What was said at this point",
  gravar: "Save",
  gravando: "Saving…",
  naoDaParaEntender: "Can't make it out",
  pular: "Skip",
  gravado: "Saved.",
  marcadoIninteligivel: "Marked. This passage won't be asked again.",
  tudoRespondido: "All answered.",
  concluir: "Done",
  irParaReuniao: "Go to the meeting",
};
