import { beforeEach, describe, expect, it } from "vitest";
import { definirIdioma } from "../i18n/idioma";
import { catalogo } from "../i18n/textos";
import { ErroDaApi, mensagemDe, mensagemDeErro, mensagemDoAviso, textoDoAviso } from "./cliente";

beforeEach(() => definirIdioma("pt"));

const pt = catalogo("pt");
const en = catalogo("en");
const erro = (codigo: string, parametros: Record<string, string | number> = {}) => ({
  detail: { codigo, parametros },
});

describe("mensagemDeErro", () => {
  it("guarda o código, não o texto: a MESMA mensagem sai em cada idioma", () => {
    const m = mensagemDeErro(400, erro("linha_nao_texto", { linha: 2, campo: "errado" }));
    expect(m.texto(pt)).toBe("Linha 2: o termo errado precisa ser texto.");
    expect(m.texto(en)).toBe("Line 2: the wrong form must be text.");
    expect(mensagemDeErro(404, erro("reuniao_nao_encontrada")).texto(en)).toBe("Meeting not found.");
  });

  it("código que o catálogo não conhece não quebra a tela", () => {
    expect(mensagemDeErro(400, erro("codigo_novo")).texto(pt)).toBe("Erro do servidor (codigo_novo).");
  });

  it("rota inexistente (servidor desatualizado) e 422 nunca aparecem crus", () => {
    expect(mensagemDeErro(404, { detail: "Not Found" }).texto(pt)).toContain("desatualizado");
    expect(mensagemDeErro(422, { detail: [{ msg: "field required" }] }).texto(en)).toContain(
      "rejected",
    );
  });

  it("servidor antigo, com frase pronta: mostra a frase", () => {
    expect(mensagemDeErro(400, { detail: "Texto antigo." }).texto(en)).toBe("Texto antigo.");
  });
});

describe("ErroDaApi e mensagemDe", () => {
  it("o catch guarda a Mensagem do erro da API, que troca de idioma depois", () => {
    const e = new ErroDaApi(mensagemDeErro(404, erro("pessoa_nao_encontrada")));
    const m = mensagemDe(e);
    expect(m.texto(pt)).toBe("Esta pessoa não está na galeria.");
    expect(m.texto(en)).toBe("This person is not in the gallery.");
  });

  it("erro que não é da API (rede, navegador) mostra o texto que veio", () => {
    expect(mensagemDe(new TypeError("Failed to fetch")).texto(pt)).toBe("Failed to fetch");
  });
});

describe("avisos", () => {
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

  it("aviso guardado como Mensagem acompanha o idioma", () => {
    const m = mensagemDoAviso({ codigo: "motivo_ja_processando", parametros: {} })!;
    expect(m.texto(pt)).toBe("Esta reunião está sendo processada agora.");
    expect(m.texto(en)).toBe("This meeting is being processed right now.");
    expect(mensagemDoAviso(null)).toBeNull();
  });
});
