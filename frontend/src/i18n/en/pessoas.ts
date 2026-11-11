import type { Catalogo } from "../textos";

export const pessoas: Catalogo["pessoas"] = {
  celula: {
    confirmada: "presence confirmed",
    na_sala: "in the room, presence not confirmed",
    ausente: "absent",
    sem_dados: "meeting not processed yet",
  },
  rotuloCelula: (reuniao, estado) => `${reuniao}: ${estado}`,
  segundos: (valor) => `${valor} s`,
  confirmarTitulo: (nome) => `Delete ${nome}'s voice?`,
  confirmarTexto: (n) =>
    `This deletes the voice profile and everything learned from it in each reviewed meeting (${n === 1 ? "1 meeting" : `${n} meetings`}). It can't be undone. Transcripts keep the speaker's name; only the voice leaves the database. Old database backups (vozes.db.bak files) are not changed.`,
  confirmarVolta: (nome) =>
    `If ${nome}'s voice is confirmed again in a review, it starts being learned again from there.`,
  excluindo: "Deleting…",
  excluirVozDe: (nome) => `Delete ${nome}'s voice`,
  cancelar: "Cancel",
  legenda: "Legend",
  legendaConfirmada: "presence confirmed in review",
  legendaNaSala: "in the room, not confirmed (not reviewed yet, or cluster ignored)",
  legendaAusente: "absent",
  legendaSemDados: "meeting not processed yet",
  vozExcluida: (nome) => `${nome}'s voice was deleted.`,
  vozExcluidaSemCompactar: (nome) =>
    `${nome}'s voice was deleted, but the database file couldn't be compacted right now - leftovers of the profile may stay in the file until the next deletion.`,
  carregando: "Loading people…",
  semPessoas:
    "No learned voices yet. The first one appears when you confirm who each voice is while reviewing a meeting.",
  colunaPessoa: "Person",
  colunaVoz: "Learned voice",
  colunaParticipacao: "Attendance by meeting",
  colunaAcoes: "Actions",
  perfilEmFormacao: "profile still forming",
  ultima: " · latest ",
  excluir: "Delete",
  explicacao:
    "There's no voice enrollment. Each person's profile is gathered from the meetings themselves, when you confirm in review who each voice is, and it gets steadier with every review. A standalone recording, made somewhere else on another device, sounds too different from the meeting room to serve as a baseline.",
};
