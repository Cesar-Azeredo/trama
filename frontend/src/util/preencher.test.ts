import { isValidElement } from "react";
import { describe, expect, it } from "vitest";
import { catalogo } from "../i18n/textos";
import { preencher } from "./preencher";

/** Texto que a tela mostraria: cada marcador trocado pelo valor dado. */
function comoTexto(partes: unknown[]): string {
  return partes
    .map((p) => (isValidElement(p) ? String((p.props as { children: unknown }).children) : String(p)))
    .join("");
}

describe("preencher (marcadores {x} das frases do catalogo)", () => {
  it("troca cada marcador pelo elemento dado - por isso o catalogo escreve {total} sem $", () => {
    for (const idioma of ["pt", "en"] as const) {
      const modelo = catalogo(idioma).correcao.aparece(3, 2);
      expect(modelo).toContain("{total}");
      const texto = comoTexto(preencher(modelo, { total: "3", reunioes: "2" }));
      expect(texto).not.toContain("{");
      expect(texto).toBe(idioma === "pt" ? "Aparece 3 vezes em 2 reuniões" : "Appears 3 times in 2 meetings");
    }
  });

  it("marcador sem valor fica como esta; texto sem marcador passa intacto", () => {
    expect(comoTexto(preencher("a {x} b", {}))).toBe("a {x} b");
    expect(comoTexto(preencher("sem marcador", { x: "1" }))).toBe("sem marcador");
  });
});
