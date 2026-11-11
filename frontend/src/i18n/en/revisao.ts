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
        "The name goes into the transcript, but no voice profile changes. Use it when the group is mostly one person, with bits of others mixed in.",
    },
    ignorar: {
      rotulo: "Ignore this voice group",
      explicacao:
        "No name is saved and no voice profile changes. Use it when the group is too mixed to name.",
    },
  },
  abaixoDoLimiar: "below the threshold",
  comFolga: "comfortable margin",
  raspandoNoLimiar: "barely above the threshold",
  trechoEm: (segundos) => `clip at ${segundos}s`,
  limiarSimMin: (valor) => `match threshold: ${valor}`,
  segundosDeFala: (segundos) => `${segundos}s of speech`,
  quemE: "Who is this?",
  ignorado: "Ignored",
  nomeDaPessoa: "Person's name",
  oQueFazerCom: (label) => `What to do with ${label}`,
  ensinar: (segundos, pessoa) => `This adds ${segundos} of audio to ${pessoa}'s voice profile.`,
  mover: (segundos, pessoa, para) =>
    `This moves ${segundos} of audio from ${pessoa}'s voice profile to ${para}'s.`,
  remover: (segundos, pessoa) => `This removes ${segundos} of audio from ${pessoa}'s voice profile.`,
  perfilSome: (pessoa) => `${pessoa} will have no voice data left and will be removed from the gallery.`,
  avisoLedgerTitulo: "This review changes the learned voice",
  salvando: "Saving…",
  confirmarESalvar: "Confirm and save",
  voltarERever: "Go back and review",
  carregandoReuniao: "Loading meeting…",
  naoProcessada: "This meeting hasn't been processed yet — there are no voice groups to review.",
  titulo: (reuniao) => `Review ${reuniao}`,
  avisoLimiarAntigo: (simMin) =>
    `This meeting was processed before the threshold was saved per meeting. The threshold marked below is today's (SIM_MIN = ${simMin}), not necessarily the one in effect when it was processed.`,
  salvarRevisao: "Save review",
  nadaGravadoAteConfirmar: "Nothing is saved until you confirm here.",
};
