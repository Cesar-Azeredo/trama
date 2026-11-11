import { beforeEach, describe, expect, it } from "vitest";
import { definirIdioma } from "../i18n/idioma";

beforeEach(() => definirIdioma("pt"));
import type { ResumoReuniao } from "../api/reunioes";
import { casaBusca, ehPendente, grupos, normalizar, textoPessoas } from "./lista";

function reuniao(id: string, extra: Partial<ResumoReuniao> = {}): ResumoReuniao {
  return {
    id,
    estado: "completa",
    duracao_s: 60,
    pessoas: null,
    dinamica: null,
    interacao: null,
    revisada: true,
    acao_processar: null,
    data: null,
    data_origem: null,
    titulo: null,
    ...extra,
  } as ResumoReuniao;
}

describe("grupos", () => {
  it("fila e a revisar no topo, revisadas por mes da gravacao, sem data no fim", () => {
    const lista = [
      reuniao("reuniao_06", { estado: "nao_processada", revisada: false }),
      reuniao("reuniao_05", { revisada: false }),
      reuniao("reuniao_04", { data: "2026-11-03T13:00:00Z", data_origem: "gravacao" }),
      reuniao("reuniao_03", { data: "2026-10-20T13:00:00Z", data_origem: "gravacao" }),
      reuniao("reuniao_02", { data: "2026-11-10T13:00:00Z", data_origem: "gravacao" }),
      reuniao("reuniao_01", { data: "2026-09-01T13:00:00Z", data_origem: "arquivo" }),
    ];
    const g = grupos(lista);
    expect(g.map((x) => x.rotulo)).toEqual([
      "Na fila",
      "A revisar",
      "novembro de 2026",
      "outubro de 2026",
      "Sem data da gravação",
    ]);
    // dentro do mes, a mais nova primeiro
    expect(g[2].itens.map((r) => r.id)).toEqual(["reuniao_02", "reuniao_04"]);
    // data so do arquivo ("chegou em") nunca decide o mes
    expect(g[4].itens.map((r) => r.id)).toEqual(["reuniao_01"]);
  });

  it("mes no fuso da maquina: 00:30 UTC do dia 1 ainda e o mes anterior em Sao Paulo", () => {
    const g = grupos([
      reuniao("reuniao_01", { data: "2026-11-01T00:30:00Z", data_origem: "gravacao" }),
    ]);
    expect(g.map((x) => x.rotulo)).toEqual(["outubro de 2026"]);
  });

  it("grupo vazio nao aparece", () => {
    expect(grupos([])).toEqual([]);
  });
});

describe("ehPendente", () => {
  it("sem .json (nao processada, processando, interrompida) e fila", () => {
    for (const estado of ["nao_processada", "processando", "interrompido"] as const) {
      expect(ehPendente(reuniao("r", { estado }))).toBe(true);
    }
    expect(ehPendente(reuniao("r", { estado: "completa" }))).toBe(false);
    expect(ehPendente(reuniao("r", { estado: "incompleta" }))).toBe(false);
  });
});

describe("textoPessoas", () => {
  it("na ordem da barra, com as vozes sem pessoa contadas no fim", () => {
    const r = reuniao("r", {
      dinamica: [
        { pessoa: "DESCONHECIDO_S2", fala_pct: 40 },
        { pessoa: "Helena", fala_pct: 35 },
        { pessoa: "Diego", fala_pct: 25 },
      ],
    });
    expect(textoPessoas(r)).toBe("Helena, Diego, 1 voz não atribuída");
  });

  it("sem dinamica, usa a lista de pessoas", () => {
    expect(textoPessoas(reuniao("r", { pessoas: ["Ana", "IGNORADO_S1", "DESCONHECIDO_S3"] }))).toBe(
      "Ana, 2 vozes não atribuídas",
    );
  });
});

describe("busca na lista", () => {
  const r = reuniao("reuniao_07", {
    titulo: "Comitê de produto",
    pessoas: ["Clélia", "Diego", "DESCONHECIDO_S1"],
  });

  it("normalizar tira acento e caixa", () => {
    expect(normalizar("Comitê CLÉLIA")).toBe("comite clelia");
  });

  it("cada palavra tem de aparecer no titulo, no padrao ou nas pessoas", () => {
    expect(casaBusca(r, "clelia produto")).toBe(true);
    expect(casaBusca(r, "reunião 07")).toBe(true);
    expect(casaBusca(r, "clelia marketing")).toBe(false);
  });

  it("voz nao atribuida nao e pessoa: o rotulo cru nao casa", () => {
    expect(casaBusca(r, "desconhecido")).toBe(false);
  });

  it("busca vazia casa tudo", () => {
    expect(casaBusca(r, "   ")).toBe(true);
  });
});

describe("rotulosDaReuniao (falante.ts)", () => {
  it("uma voz sem pessoa: sem numero; duas ou mais: numeradas pelo rotulo cru", async () => {
    const { rotulosDaReuniao } = await import("./falante");
    const uma = rotulosDaReuniao(["Ana", "DESCONHECIDO_S1"]);
    expect(uma("DESCONHECIDO_S1")).toBe("voz não atribuída");
    expect(uma("Ana")).toBe("Ana");
    const duas = rotulosDaReuniao(["IGNORADO_SPEAKER_02", "Ana", "DESCONHECIDO_SPEAKER_00"]);
    expect(duas("DESCONHECIDO_SPEAKER_00")).toBe("voz não atribuída 1");
    expect(duas("IGNORADO_SPEAKER_02")).toBe("voz não atribuída 2");
  });
});

describe("grupos em inglês", () => {
  it("rótulos e mês no idioma escolhido", () => {
    definirIdioma("en");
    const g = grupos([
      reuniao("reuniao_02", { revisada: false }),
      reuniao("reuniao_01", { data: "2026-11-03T13:00:00Z", data_origem: "gravacao" }),
    ]);
    expect(g.map((x) => x.rotulo)).toEqual(["To review", "November 2026"]);
    expect(textoPessoas(reuniao("r", { pessoas: ["Ana", "IGNORADO_S1"] }))).toBe("Ana, 1 unassigned voice");
  });
});
