import { defineConfig } from "vitest/config";

// Testes so da logica pura (src/**/*.test.ts): sem DOM, sem React.
// Fuso fixo: agrupamento por mes e data por extenso dependem do fuso da
// maquina, e o teste nao pode depender de onde roda.
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
    env: { TZ: "America/Sao_Paulo" },
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.ts", "src/main.tsx"],
      reporter: ["text-summary", "text"],
    },
  },
});
