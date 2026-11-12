import type { Catalogo } from "../textos";

export const nova: Catalogo["nova"] = {
  formatoNaoAceito: (extensoes) => `Format not accepted. Use ${extensoes}.`,
  maiorQueLimite: (mb) => `File is larger than the ${mb} MB limit.`,
  arrasteAqui: "Drop the meeting audio here, or",
  escolhaUmArquivo: "choose a file",
  formatosAceitos: (extensoes, mb) => `${extensoes} — up to ${mb} MB`,
  explicacaoPessoas:
    "This is the single biggest accuracy boost: it tells the system how many speakers to look for, and only compares voices against these people. If you skip it, everything still works — just less accurately.",
  carregandoPessoas: "Loading people…",
  pessoaNova: "+ New person",
  nomeDaPessoaNova: "New person's name",
  adicionar: "Add",
  cancelar: "Cancel",
  selecionadas: (n) => (n === 0 ? "none selected" : `${n} selected`),
  caractereDeControle:
    "The title has a control character (line break, tab...), which isn't allowed.",
  tituloNaoSalvo: (erro) =>
    `The audio was uploaded, but the title wasn't saved: ${erro} The meeting is in the queue, not processed — you can set the title in its details.`,
  passoAudio: "The audio",
  trocarArquivo: "Change file",
  talvezNaoFalou: "Was there, but may not have spoken",
  talvezNaoFalouNota:
    "Mark anyone who only listened or stayed quiet. Otherwise each selected person becomes a voice to look for, and a voice that isn't there splits someone else's in two.",
  passoPessoas: "Who was in the room",
  progressoDoEnvio: "Upload progress",
  titulo: "Title",
  opcional: "(optional)",
  exemploTitulo: "E.g. Product committee",
  ajudaTitulo:
    "Without a title, the meeting gets the default name: “Meeting” and its number. You can change it later, in its details.",
  enviando: "Uploading…",
  transcrever: "Transcribe",
  notaRodape: "About 6 minutes per hour of audio. Nothing leaves this machine.",
};
