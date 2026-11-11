import { beforeEach, describe, expect, it } from "vitest";
import { definirIdioma } from "../i18n/idioma";

beforeEach(() => definirIdioma("pt"));
import {
  formatarDataReuniao,
  formatarDuracao,
  formatarTamanhoArquivo,
  formatarTitulo,
  numeroDaReuniao,
  rotuloBotaoProcessar,
  tituloDaReuniao,
} from "./formatarReuniao";

describe("formatarDuracao", () => {
  it("minutos:segundos abaixo de uma hora, com zero a esquerda", () => {
    expect(formatarDuracao(0)).toBe("0:00");
    expect(formatarDuracao(65)).toBe("1:05");
    expect(formatarDuracao(59.6)).toBe("1:00");
  });

  it("horas:minutos:segundos a partir de uma hora", () => {
    expect(formatarDuracao(3600)).toBe("1:00:00");
    expect(formatarDuracao(4212)).toBe("1:10:12");
  });
});

describe("formatarDataReuniao", () => {
  it("data da gravacao por extenso, no fuso da maquina", () => {
    const t = formatarDataReuniao("2026-11-03T13:00:00Z", "gravacao")!;
    expect(t).toContain("3 de nov");
    expect(t).toContain("10:00"); // 13:00 UTC = 10:00 em Sao Paulo
  });

  it("data do arquivo nunca tem cara de data da reuniao: 'chegou em', sem hora", () => {
    const t = formatarDataReuniao("2026-08-31T15:00:00Z", "arquivo")!;
    expect(t.startsWith("chegou em ")).toBe(true);
    expect(t).not.toMatch(/\d{2}:\d{2}/);
  });

  it("sem data ou data invalida: null", () => {
    expect(formatarDataReuniao(null, "gravacao")).toBeNull();
    expect(formatarDataReuniao("ontem", "gravacao")).toBeNull();
  });
});

describe("titulo e numero", () => {
  it("o id da pasta e a unica fonte do numero", () => {
    expect(numeroDaReuniao("reuniao_07")).toBe("07");
    expect(formatarTitulo("reuniao_07")).toBe("Reunião 07");
    expect(formatarTitulo("outra")).toBe("outra");
  });

  it("titulo dado pela pessoa, senao o padrao - nunca vazio", () => {
    expect(tituloDaReuniao("reuniao_02", "Revisão do Painel")).toBe("Revisão do Painel");
    expect(tituloDaReuniao("reuniao_02", "")).toBe("Reunião 02");
    expect(tituloDaReuniao("reuniao_02", null)).toBe("Reunião 02");
  });
});

describe("rotulos", () => {
  it("tamanho em MB com uma casa", () => {
    expect(formatarTamanhoArquivo(37 * 1024 * 1024)).toBe("37,0 MB");
  });

  it("o botao de processar diz o que vai acontecer", () => {
    expect(rotuloBotaoProcessar("nao_processada")).toBe("Processar");
    expect(rotuloBotaoProcessar("processando")).toBe("Processando…");
    expect(rotuloBotaoProcessar("interrompido")).toBe("Tentar novamente");
  });
});

describe("em inglês", () => {
  beforeEach(() => definirIdioma("en"));

  it("título padrão, data, 'chegou em' e tamanho no idioma escolhido", () => {
    expect(formatarTitulo("reuniao_07")).toBe("Meeting 07");
    expect(formatarDataReuniao("2026-11-03T13:00:00Z", "gravacao")).toContain("Nov 3, 2026");
    expect(formatarDataReuniao("2026-08-31T15:00:00Z", "arquivo")!.startsWith("arrived on ")).toBe(true);
    expect(formatarTamanhoArquivo(1.5 * 1024 * 1024)).toBe("1.5 MB");
    expect(rotuloBotaoProcessar("interrompido")).toBe("Try again");
  });

  it("em português o decimal é com vírgula", () => {
    definirIdioma("pt");
    expect(formatarTamanhoArquivo(1.5 * 1024 * 1024)).toBe("1,5 MB");
  });
});
