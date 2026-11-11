import type { Catalogo } from "../textos";
import { numero } from "../../util/numeros";

export const termos: Catalogo["termos"] = {
  explicacao:
    "Company names, acronyms and products, spelled correctly. The misspellings listed under each one are fixed automatically in every new transcript. Descriptions go along with the downloaded transcript (.txt), so anyone — or any AI — reading it has context.",
  carregandoTermos: "Loading terms…",
  removerTermo: "Remove term",
  removerOTermo: (termo) => `Remove the term ${termo}`,
  removido: (termo) => `“${termo}” removed.`,
  corrige: "Fixes:",
  pararDeCorrigir: (errado) => `Stop fixing ${errado}`,
  pararDeCorrigirDica: "Stop fixing (what was already fixed stays)",
  naoSeraMaisCorrigido: (errado) => `“${errado}” will no longer be fixed.`,
  adicionarVariacao: "+ Add variant",
  adicionarTermo: "Add term",
  nomeDoTermo: "Term name",
  nomeDoTermoExemplo: "Name, spelled correctly (e.g., MQX)",
  oQueE: "What it is",
  oQueEExemplo: "What is it? (optional)",
  adicionando: "Adding…",
  adicionado: (termo) => `“${termo}” added.`,

  adicionarDescricao: "+ Add description",
  adicionarDescricaoDe: (termo) => `Add description for ${termo}`,
  descricaoDe: (termo) => `Description of ${termo}`,
  descricaoExemplo: "Description (e.g., project approval tool)",
  salvando: "Saving…",
  salvo: "Saved.",

  comoApareceErrado: "How it shows up misspelled",
  jaEVariacao: (errado, termo) => `“${errado}” is already a variant of ${termo}.`,
  naoApareceEmNenhuma: "Doesn't appear in any processed meeting. It applies to future ones.",
  apareceVezesEmReunioes: (vezes, reunioes) => [
    "Appears ",
    ` ${vezes === 1 ? "time" : "times"} in `,
    ` ${reunioes === 1 ? "meeting" : "meetings"}`,
  ],
  conferindo: "Checking…",
  conferir: "Check",
  adicionar: "Add",
  corrigirEm: (n) => `Fix in ${numero(n)} ${n === 1 ? "place" : "places"}`,
  corrigidoEm: (trecho, n) => `“${trecho}” fixed in ${numero(n)} ${n === 1 ? "place" : "places"}.`,
  seraCorrigidoNasProximas: (trecho) => `“${trecho}” will be fixed in future meetings.`,
  cancelar: "Cancel",

  aplicarNasProcessadas: "Apply to meetings already processed",
  salveAntes: "Save first — the fix uses what is saved.",
  mostraAntes:
    "Shows first how many replacements would be made, and in which meetings. Nothing changes until you confirm.",
  nadaFoiAlterado: "Nothing was changed.",
  aplicadoEm: (n) => `Applied to ${numero(n)} ${n === 1 ? "meeting" : "meetings"}.`,
  nadaACorrigir: "Nothing to fix: the meetings already processed match the company terms.",
  fechar: "Close",
  substituicoesEmReunioes: (total, reunioes) => [
    "",
    ` ${total === 1 ? "replacement" : "replacements"} in `,
    ` ${reunioes === 1 ? "meeting" : "meetings"}`,
  ],
  notaReescreve:
    "Rewrites the transcript of these meetings (.json and .txt). Highlights and markers stay in the right place.",
  aplicando: "Applying…",
  aplicar: "Apply",
};
