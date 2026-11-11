import type { Catalogo } from "../textos";

export const comum: Catalogo["comum"] = {
  secoes: "Sections",
  novaReuniao: "New meeting",
  novaCurta: "New",
  reunioes: "Meetings",
  pessoas: "People",
  perfil: "Profile",
  tocar: (rotulo) => `Play ${rotulo}`,
  pausar: (rotulo) => `Pause ${rotulo}`,
  semAudioNaDemonstracao: "Audio is not available in the demo.",
};
