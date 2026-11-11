import { describe, expect, it } from "vitest";
import { aparar } from "./selecaoNaFala";
import { faixasDaFala } from "./sobreposicao";

describe("aparar (selecao para corrigir)", () => {
  it("tira espaco e pontuacao das pontas - o clique duplo do Safari leva o espaco", () => {
    const texto = "o Aprovium, de novo";
    expect(aparar(texto, 1, 12)).toEqual([2, 10]); // " Aprovium, " -> "Aprovium"
  });

  it("selecao so de pontuacao vira vazia", () => {
    const [a, b] = aparar("isso, ali", 4, 6);
    expect(b).toBeLessThanOrEqual(a);
  });

  it("letra acentuada e numero sao palavra", () => {
    expect(aparar("(Órbita 2)", 0, 10)).toEqual([1, 9]);
  });
});

describe("faixasDaFala (trecho falado por cima)", () => {
  // [posicao, comprimento, inicio, fim] de "eu acho que sim"
  const palavras: [number, number, number, number][] = [
    [0, 2, 0.0, 0.3],
    [3, 4, 0.3, 0.8],
    [8, 3, 0.8, 1.1],
    [12, 3, 1.1, 1.5],
  ];

  it("palavras seguidas sob a mesma outra pessoa viram uma faixa so", () => {
    const regioes = [{ inicio: 0.3, fim: 1.2, falantes: ["Ana", "Bia"] }];
    expect(faixasDaFala(palavras, "Ana", regioes)).toEqual([{ inicio: 3, fim: 11, outra: "Bia" }]);
  });

  it("ponto medio, nao 'qualquer toque': palavra que so encosta na borda fica fora", () => {
    const regioes = [{ inicio: 0.75, fim: 1.0, falantes: ["Ana", "Bia"] }];
    expect(faixasDaFala(palavras, "Ana", regioes)).toEqual([{ inicio: 8, fim: 11, outra: "Bia" }]);
  });

  it("regiao so com quem fala nao e sobreposicao", () => {
    expect(faixasDaFala(palavras, "Ana", [{ inicio: 0, fim: 2, falantes: ["Ana"] }])).toEqual([]);
  });

  it("palavra fora da sobreposicao no meio quebra a faixa", () => {
    const regioes = [
      { inicio: 0.0, fim: 0.3, falantes: ["Ana", "Bia"] },
      { inicio: 1.1, fim: 1.5, falantes: ["Ana", "Bia"] },
    ];
    expect(faixasDaFala(palavras, "Ana", regioes)).toEqual([
      { inicio: 0, fim: 2, outra: "Bia" },
      { inicio: 12, fim: 15, outra: "Bia" },
    ]);
  });

  it("sem tempos por palavra ou sem regioes: nada", () => {
    expect(faixasDaFala(undefined, "Ana", [])).toEqual([]);
    expect(faixasDaFala(palavras, "Ana", undefined)).toEqual([]);
  });
});
