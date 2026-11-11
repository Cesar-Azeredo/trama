import type { Catalogo } from "../textos";

export const revisao: Catalogo["revisao"] = {
  modos: {
    aprender: {
      rotulo: "Confirm and learn the voice",
      explicacao:
        "The name goes into the transcript and this voice becomes part of the person's profile.",
    },
    so_nomear: {
      rotulo: "Name only, don't learn",
      explicacao:
        "The name goes into the transcript, but no one's voice profile changes. Use it when the voice is almost entirely one person's, with passages from others.",
    },
    ignorar: {
      rotulo: "Ignore this cluster",
      explicacao:
        "The name isn't saved and no one's voice profile is updated with this cluster. Use it when the voice is too mixed to have a name.",
    },
  },
  abaixoDoLimiar: "below the threshold",
  comFolga: "comfortable margin",
  raspandoNoLimiar: "barely above the threshold",
  trechoEm: (segundos) => `passage at ${segundos}s`,
  limiarSimMin: (valor) => `threshold SIM_MIN = ${valor}`,
  segundosDeFala: (segundos) => `${segundos}s of speech`,
  quemE: "Who is this?",
  ignorado: "Ignored",
  nomeDaPessoa: "Person's name",
  oQueFazerCom: (label) => `What to do with ${label}`,
  ensinar: (segundos, pessoa) => `This will add ${segundos} to ${pessoa}'s learned voice.`,
  mover: (segundos, pessoa, para) =>
    `This will move ${segundos} of ${pessoa}'s voice to ${para}.`,
  remover: (segundos, pessoa) => `This will remove ${segundos} from ${pessoa}'s voice.`,
  perfilSome: (pessoa) => `${pessoa} will have no learned voice left and leaves the gallery.`,
  avisoLedgerTitulo: "This review changes the learned voice",
  salvando: "Saving…",
  confirmarESalvar: "Confirm and save",
  voltarERever: "Go back and review",
  carregandoReuniao: "Loading meeting…",
  naoProcessada: "This meeting hasn't been processed yet - there are no clusters to review.",
  titulo: (reuniao) => `Review ${reuniao}`,
  avisoLimiarAntigo: (simMin) =>
    `This meeting was processed before the threshold was saved per meeting. The threshold marked below is today's (SIM_MIN = ${simMin}), not necessarily the one in effect when it was processed.`,
  salvarRevisao: "Save review",
  nadaGravadoAteConfirmar: "Nothing is saved until you confirm here.",
};
