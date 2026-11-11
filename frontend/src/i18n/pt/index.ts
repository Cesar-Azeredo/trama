/**
 * Catálogo em português - a REFERÊNCIA dos tipos: en/index.ts tem de ter
 * exatamente as mesmas chaves (o TypeScript recusa chave faltando ou
 * sobrando, e i18n/catalogos.test.ts confere de novo em tempo de teste).
 * Um arquivo por área da interface.
 */
import { comum } from "./comum";
import { formatos } from "./formatos";
import { perfil } from "./perfil";

export const pt = {
  comum,
  formatos,
  perfil,
};
