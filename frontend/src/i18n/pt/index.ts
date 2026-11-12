/**
 * Catálogo em português - a REFERÊNCIA dos tipos: en/index.ts tem de ter
 * exatamente as mesmas chaves (o TypeScript recusa chave faltando ou
 * sobrando, e i18n/catalogos.test.ts confere de novo em tempo de teste).
 * Um arquivo por área da interface.
 */
import { comum } from "./comum";
import { erros } from "./erros";
import { formatos } from "./formatos";
import { perfil } from "./perfil";
import { detalhe } from "./detalhe";
import { correcao } from "./correcao";
import { lista } from "./lista";
import { pessoas } from "./pessoas";
import { revisao } from "./revisao";
import { conferir } from "./conferir";
import { trechos } from "./trechos";
import { nova } from "./nova";
import { processamento } from "./processamento";
import { termos } from "./termos";

export const pt = {
  comum,
  formatos,
  erros,
  perfil,
  detalhe,
  correcao,
  lista,
  pessoas,
  revisao,
  conferir,
  trechos,
  nova,
  processamento,
  termos,
};
