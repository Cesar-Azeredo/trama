import { localeAtual } from "../i18n/idioma";
import { textosAtuais } from "../i18n/textos";
import { numero } from "./numeros";

/** Compartilhado entre Lista e Detalhe - o id da pasta e a unica fonte do
 * numero/titulo exibido, nunca duas implementacoes que podem divergir. */

export function numeroDaReuniao(id: string): string {
  const m = id.match(/^reuniao_(\d+)$/);
  return m ? m[1] : id;
}

export function formatarTitulo(id: string): string {
  const m = id.match(/^reuniao_(\d+)$/);
  return m ? textosAtuais().formatos.tituloPadrao(m[1]) : id;
}

export function formatarTamanhoArquivo(bytes: number): string {
  return `${numero(bytes / 1024 / 1024, 1)} MB`;
}

/** Rotulo do botao/link "Processar" varia com o estado - "Processar" numa
 * reuniao que ja esta processando, ou que foi interrompida, afirmaria uma
 * acao que nao e a que esta acontecendo. "processando" vira link (so
 * acompanha o progresso de quem ja esta rodando); os outros dois disparam
 * a rota de verdade (Lista.tsx/Detalhe.tsx). */
export function rotuloBotaoProcessar(
  estado: "nao_processada" | "processando" | "interrompido",
): string {
  const t = textosAtuais().formatos;
  if (estado === "processando") return t.processando;
  if (estado === "interrompido") return t.tentarNovamente;
  return t.processar;
}

export function formatarDuracao(segundos: number): string {
  const s = Math.round(segundos);
  const h = Math.floor(s / 3600);
  const min = Math.floor((s % 3600) / 60);
  const seg = s % 60;
  const par = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${par(min)}:${par(seg)}` : `${min}:${par(seg)}`;
}

/**
 * Data da reuniao por extenso, no fuso da maquina (o .json guarda UTC).
 * Intl nativo do navegador - nada de rede, nada de biblioteca.
 *   gravacao -> "qua., 23 de set. de 2026, 09:40"
 *   arquivo  -> "chegou em 31 de ago. de 2026": e quando o ARQUIVO chegou,
 *               nao quando a reuniao aconteceu - nunca com cara de data
 *               da reuniao, e sem hora, que so sugeriria precisao falsa.
 * null quando nao ha data nenhuma.
 */
export function formatarDataReuniao(
  data: string | null,
  origem: "gravacao" | "arquivo" | null,
): string | null {
  if (!data) return null;
  const d = new Date(data);
  if (Number.isNaN(d.getTime())) return null;
  if (origem === "gravacao") {
    return new Intl.DateTimeFormat(localeAtual(), {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  }
  return textosAtuais().formatos.chegouEm(new Intl.DateTimeFormat(localeAtual(), {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(d));
}

/** O titulo que a pessoa deu, ou o padrao "Reuniao NN" - nunca string
 * vazia. */
export function tituloDaReuniao(id: string, titulo: string | null | undefined): string {
  return titulo || formatarTitulo(id);
}

/** Horario dentro da reuniao: "mm:ss", ou "h:mm:ss" depois da primeira hora. */
export function formatarTimestamp(segundos: number): string {
  const s = Math.floor(segundos);
  const h = Math.floor(s / 3600);
  const min = Math.floor((s % 3600) / 60);
  const seg = s % 60;
  const par = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${par(min)}:${par(seg)}` : `${par(min)}:${par(seg)}`;
}
