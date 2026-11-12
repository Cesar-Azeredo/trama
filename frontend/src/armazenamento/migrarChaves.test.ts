import { describe, expect, it } from "vitest";
import { migrarChaves } from "./migrarChaves";

function memoria(inicial: Record<string, string>) {
  const dados = new Map(Object.entries(inicial));
  return {
    dados,
    getItem: (k: string) => dados.get(k) ?? null,
    setItem: (k: string, v: string) => void dados.set(k, v),
    removeItem: (k: string) => void dados.delete(k),
  };
}

describe("migrarChaves", () => {
  it("copia cada chave antiga para a nova e apaga a antiga", () => {
    const a = memoria({
      "rec-meet:tema": "escuro",
      "rec-meet:idioma": "en",
      "rec-meet:perfil": '{"nome":"Ana","pessoa":null}',
      "rec-meet:mostrar-eventos": "true",
    });
    migrarChaves(a);
    expect(Object.fromEntries(a.dados)).toEqual({
      "trama:tema": "escuro",
      "trama:idioma": "en",
      "trama:perfil": '{"nome":"Ana","pessoa":null}',
      "trama:mostrar-eventos": "true",
    });
  });

  it("nunca sobrescreve uma escolha ja feita com o nome novo", () => {
    const a = memoria({ "rec-meet:tema": "escuro", "trama:tema": "claro" });
    migrarChaves(a);
    expect(Object.fromEntries(a.dados)).toEqual({ "trama:tema": "claro" });
  });

  it("rodar de novo nao muda nada", () => {
    const a = memoria({ "rec-meet:idioma": "pt" });
    migrarChaves(a);
    migrarChaves(a);
    expect(Object.fromEntries(a.dados)).toEqual({ "trama:idioma": "pt" });
  });

  it("deixa em paz o que nao e do app", () => {
    const a = memoria({ "outra:coisa": "x" });
    migrarChaves(a);
    expect(Object.fromEntries(a.dados)).toEqual({ "outra:coisa": "x" });
  });
});
