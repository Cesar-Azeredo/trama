import type { Catalogo } from "../textos";

export const nova: Catalogo["nova"] = {
  formatoNaoAceito: (extensoes) => `Format not accepted. Use ${extensoes}.`,
  maiorQueLimite: (mb) => `File is larger than the ${mb} MB limit.`,
  arrasteAqui: "Drag the meeting audio file here, or",
  escolhaUmArquivo: "choose a file",
  formatosAceitos: (extensoes, mb) => `${extensoes} — up to ${mb} MB`,
  explicacaoPessoas:
    "It's the biggest accuracy gain there is: it fixes how many speakers to look for and limits the comparison to who was there. Without marking anyone, the pipeline works the same, only worse.",
  carregandoPessoas: "Loading people…",
  pessoaNova: "+ New person",
  nomeDaPessoaNova: "New person's name",
  adicionar: "Add",
  cancelar: "Cancel",
  selecionadas: (n) => (n === 0 ? "none selected" : `${n} selected`),
  caractereDeControle:
    "The title has a control character (line break, tab...), which isn't allowed.",
  tituloNaoSalvo: (erro) =>
    `The audio was uploaded, but the title wasn't saved: ${erro} The meeting is in the queue, not processed - you can set the title in its details.`,
  passoAudio: "The audio",
  trocarArquivo: "Change file",
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
