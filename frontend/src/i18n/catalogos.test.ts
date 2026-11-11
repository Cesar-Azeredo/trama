import { describe, expect, it } from "vitest";
import { en } from "./en";
import { idiomaDoNavegador } from "./idioma";
import { pt } from "./pt";

/** Caminho de cada folha ("lista.titulo") e o tipo dela. */
function folhas(obj: Record<string, unknown>, prefixo = ""): Map<string, string> {
  const saida = new Map<string, string>();
  for (const [chave, valor] of Object.entries(obj)) {
    const caminho = prefixo ? `${prefixo}.${chave}` : chave;
    if (valor && typeof valor === "object") {
      for (const [k, v] of folhas(valor as Record<string, unknown>, caminho)) saida.set(k, v);
    } else {
      saida.set(caminho, typeof valor);
    }
  }
  return saida;
}

describe("catálogos", () => {
  const a = folhas(pt);
  const b = folhas(en);

  it("toda chave do português existe no inglês, e vice-versa", () => {
    expect([...a.keys()].filter((k) => !b.has(k))).toEqual([]);
    expect([...b.keys()].filter((k) => !a.has(k))).toEqual([]);
  });

  it("a mesma chave tem o mesmo tipo (texto ou função) nos dois", () => {
    expect([...a].filter(([k, t]) => b.get(k) !== t).map(([k]) => k)).toEqual([]);
  });

  it("nenhum texto vazio", () => {
    const vazios = [...folhas(pt), ...folhas(en)].filter(([, t]) => t === "string");
    const textos = (obj: Record<string, unknown>): string[] =>
      Object.values(obj).flatMap((v) =>
        typeof v === "string" ? [v] : v && typeof v === "object" ? textos(v as Record<string, unknown>) : [],
      );
    expect(vazios.length).toBeGreaterThan(0);
    expect([...textos(pt), ...textos(en)].filter((t) => t.trim() === "")).toEqual([]);
  });
});

describe("idioma do navegador", () => {
  it("português para qualquer variante pt, inglês para o resto", () => {
    expect(idiomaDoNavegador("pt-BR")).toBe("pt");
    expect(idiomaDoNavegador("pt-PT")).toBe("pt");
    expect(idiomaDoNavegador("en-US")).toBe("en");
    expect(idiomaDoNavegador("es")).toBe("en");
    expect(idiomaDoNavegador(undefined)).toBe("en");
  });
});
