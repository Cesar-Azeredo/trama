import { describe, expect, it } from "vitest";
import { construirIndiceGaleria, corDaVoz, corDoTextoDaVoz } from "./corDaVoz";

const galeria = [
  { nome: "Helena", primeira_aparicao: "2026-11-03T13:00:00+00:00" },
  { nome: "Beatriz", primeira_aparicao: "2026-11-03T13:00:00+00:00" },
  { nome: "Paula", primeira_aparicao: "2026-11-05T17:30:00+00:00" },
];

describe("construirIndiceGaleria", () => {
  it("ordem de entrada na galeria, desempatada pelo nome", () => {
    const indice = construirIndiceGaleria(galeria);
    expect(indice.get("Beatriz")).toBe(0);
    expect(indice.get("Helena")).toBe(1);
    expect(indice.get("Paula")).toBe(2);
  });

  it("quem entra depois vai para o fim e ninguem troca de cor", () => {
    const antes = construirIndiceGaleria(galeria);
    const depois = construirIndiceGaleria([
      ...galeria,
      { nome: "Ana", primeira_aparicao: "2026-11-10T14:00:00+00:00" },
    ]);
    for (const [nome, i] of antes) expect(depois.get(nome)).toBe(i);
    expect(depois.get("Ana")).toBe(3);
  });

  it("sem data vai para o fim, nunca para o comeco", () => {
    const indice = construirIndiceGaleria([...galeria, { nome: "Aaron", primeira_aparicao: null }]);
    expect(indice.get("Aaron")).toBe(3);
    expect(indice.get("Beatriz")).toBe(0);
  });

  it("oito cores: a nona pessoa repete a primeira", () => {
    const muitas = Array.from({ length: 9 }, (_, i) => ({
      nome: `P${i}`,
      primeira_aparicao: `2026-01-0${i + 1}T00:00:00Z`,
    }));
    expect(construirIndiceGaleria(muitas).get("P8")).toBe(0);
  });
});

describe("corDaVoz e corDoTextoDaVoz", () => {
  const indice = construirIndiceGaleria(galeria);

  it("pessoa da galeria: a cor da posicao dela", () => {
    expect(corDaVoz("Helena", indice)).toBe("var(--voz-2)");
    expect(corDoTextoDaVoz("Helena", indice)).toBe("var(--voz-2)");
  });

  it("voz sem pessoa nunca ganha cor de voz", () => {
    expect(corDaVoz("DESCONHECIDO_S0", indice)).toBe("var(--tinta-tenue)");
    expect(corDoTextoDaVoz("IGNORADO_S1", indice)).toBe("var(--tinta-fraca)");
  });

  it("fora da galeria: cor por hash, estavel e dentro das oito", () => {
    const a = corDaVoz("Sofia", indice);
    expect(a).toBe(corDaVoz("Sofia", indice));
    expect(a).toMatch(/^var\(--voz-[1-8]\)$/);
  });
});
