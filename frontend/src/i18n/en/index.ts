/** English catalog - same keys as pt/index.ts (the type enforces it). */
import type { Catalogo } from "../textos";
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

export const en: Catalogo = {
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
