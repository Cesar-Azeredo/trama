import type { Catalogo } from "../textos";

export const perfil: Catalogo["perfil"] = {
  idioma: "Language",
  idiomaNota: "Only the app's text changes. What people said is never translated.",
  voce: "You",
  seuNome: "Your name",
  voceNaGaleria: "You in the voice gallery (optional)",
  nenhuma: "None",
  foraDaGaleria: (nome) => `${nome} (not in the gallery)`,
  notaLocal: "Saved only in this browser. There's no login — the app has a single user, on this machine.",
  configuracoes: "Settings",
  aparencia: "Appearance",
  tema: {
    sistema: "Match system",
    claro: "Light",
    escuro: "Dark",
  },
  termosDaEmpresa: "Company terms",
  processamento: "Processing",
  dispositivo: "Device",
  motorDeTranscricao: "Transcription engine",
  notaProcessamento: "Detected automatically on this machine. Nothing to configure.",
  dadosEPrivacidade: "Data and privacy",
  audiosETranscricoes: "Audio and transcripts",
  bancoDeVozes: "Voice database",
  notaPrivacidade:
    "Nothing leaves this machine. The audio, the transcript and the voice profiles stay in these files, and the app makes no outside requests.",
  sobre: "About",
  notaAtribuicoes:
    "Uses third-party models and libraries. The attributions below are required by their licenses; the full text is in ATRIBUICAO.md, in the app folder.",
  carregando: "Loading…",
};
