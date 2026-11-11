// ferramentas/capturas.mjs - Capturas de tela para o README, so com os
// dados de demonstracao (audios-demo/), nos modos claro e escuro.
//
// Sobe o servidor em modo demonstracao (127.0.0.1, porta propria) e o
// Vite apontando para ele, abre cada tela num Chromium sem janela e grava
// docs/capturas/<tela>-<modo>.png. So navega: nada e gravado nos dados de
// demonstracao.
//
// Uso (de frontend/, com o .venv da raiz ativo e o pacote instalado):
//     npm run capturas
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const RAIZ = resolve(FRONTEND, "..");
const SAIDA = resolve(RAIZ, "docs", "capturas");
const PORTA_API = "8765";
const PORTA_WEB = "5199";
const BASE = `http://127.0.0.1:${PORTA_WEB}`;

const TELAS = [
  { nome: "lista", hash: "#/reunioes" },
  { nome: "detalhe", hash: "#/reuniao/reuniao_01" },
  { nome: "revisao", hash: "#/reuniao/reuniao_03/revisar" },
  { nome: "pessoas", hash: "#/pessoas" },
  { nome: "perfil", hash: "#/perfil" },
  { nome: "nova-reuniao", hash: "#/" },
];
const MODOS = [
  { nome: "claro", esquema: "light" },
  { nome: "escuro", esquema: "dark" },
];
const LARGURA = 1440;
const ALTURA = 900;

function subir(comando, args, opcoes) {
  const processo = spawn(comando, args, { stdio: ["ignore", "pipe", "pipe"], ...opcoes });
  processo.stderr.on("data", (d) => process.stderr.write(d));
  return processo;
}

async function esperar(url, tentativas = 100) {
  for (let i = 0; i < tentativas; i++) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {
      // ainda subindo
    }
    await new Promise((ok) => setTimeout(ok, 200));
  }
  throw new Error(`nao respondeu: ${url}`);
}

const ambiente = {
  ...process.env,
  REC_MEET_DEMO: "1",
  REC_MEET_AUDIOS: resolve(RAIZ, "audios-demo"),
  VOZES_DB: resolve(RAIZ, "audios-demo", "vozes-demo.db"),
  REC_MEET_TERMOS: resolve(RAIZ, "termos.exemplo.txt"),
  REC_MEET_PORTA: PORTA_API,
};
const servidor = subir("python", ["-m", "trama.servidor.app"], { cwd: RAIZ, env: ambiente });
const vite = subir(
  "npx",
  ["vite", "--host", "127.0.0.1", "--port", PORTA_WEB, "--strictPort"],
  { cwd: FRONTEND, env: ambiente },
);

try {
  await esperar(`http://127.0.0.1:${PORTA_API}/api/sistema`);
  await esperar(BASE);
  mkdirSync(SAIDA, { recursive: true });
  const navegador = await chromium.launch();
  for (const modo of MODOS) {
    const contexto = await navegador.newContext({
      viewport: { width: LARGURA, height: ALTURA },
      deviceScaleFactor: 2,
      colorScheme: modo.esquema,
      reducedMotion: "reduce",
    });
    const pagina = await contexto.newPage();
    for (const tela of TELAS) {
      await pagina.goto(`${BASE}/${tela.hash}`, { waitUntil: "networkidle" });
      await pagina.evaluate(() => document.fonts.ready);
      const arquivo = resolve(SAIDA, `${tela.nome}-${modo.nome}.png`);
      await pagina.screenshot({ path: arquivo });
      console.log(`  ${tela.nome}-${modo.nome}.png`);
    }
    await contexto.close();
  }
  await navegador.close();
} finally {
  vite.kill();
  servidor.kill();
}
