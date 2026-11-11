import { beforeEach, describe, expect, it } from "vitest";
import { definirIdioma } from "../i18n/idioma";
import { mensagemDeErro, textoDoAviso } from "./cliente";

beforeEach(() => definirIdioma("pt"));

const erro = (codigo: string, parametros: Record<string, string | number> = {}) => ({
  detail: { codigo, parametros },
});

describe("mensagemDeErro", () => {
  it("o código vira a frase no idioma escolhido, com os parâmetros", () => {
    expect(mensagemDeErro(404, erro("reuniao_nao_encontrada"))).toBe("Reunião não encontrada.");
    expect(mensagemDeErro(400, erro("linha_nao_texto", { linha: 2, campo: "errado" }))).toBe(
      "Linha 2: o termo errado precisa ser texto.",
    );
    definirIdioma("en");
    expect(mensagemDeErro(404, erro("reuniao_nao_encontrada"))).toBe("Meeting not found.");
    expect(mensagemDeErro(400, erro("linha_nao_texto", { linha: 2, campo: "errado" }))).toBe(
      "Line 2: the wrong form must be text.",
    );
  });

  it("código que o catálogo não conhece não quebra a tela", () => {
    expect(mensagemDeErro(400, erro("codigo_novo"))).toBe("Erro do servidor (codigo_novo).");
  });

  it("rota inexistente (servidor desatualizado) e 422 nunca aparecem crus", () => {
    expect(mensagemDeErro(404, { detail: "Not Found" })).toContain("desatualizado");
    expect(mensagemDeErro(422, { detail: [{ msg: "field required" }] })).toContain("recusou");
  });

  it("servidor antigo, com frase pronta: mostra a frase", () => {
    expect(mensagemDeErro(400, { detail: "Texto antigo." })).toBe("Texto antigo.");
  });
});

describe("textoDoAviso", () => {
  it("código, texto de .json antigo, lista e ausência", () => {
    expect(textoDoAviso({ codigo: "edicoes_sem_fala", parametros: { n: 2 } })).toMatch(/^2 correção/);
    expect(textoDoAviso("aviso gravado antes dos códigos")).toBe("aviso gravado antes dos códigos");
    expect(
      textoDoAviso([
        { codigo: "correcao_existente_prevalece", parametros: { errado: "a", certo: "b" } },
        { codigo: "correcao_existente_prevalece", parametros: { errado: "c", certo: "d" } },
      ]),
    ).toContain('"c" para "d"');
    expect(textoDoAviso(null)).toBeNull();
  });
});
