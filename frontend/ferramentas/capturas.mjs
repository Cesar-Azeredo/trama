// ferramentas/capturas.mjs - Capturas de tela para o README, so com os
// dados de demonstracao, nos modos claro e escuro e nos dois idiomas:
// interface e demonstracao em ingles em docs/capturas/ (as do README),
// em portugues em docs/capturas/pt/.
//
// Sobe o servidor em modo demonstracao (127.0.0.1, porta propria) e o
// Vite apontando para ele, abre cada tela num Chromium sem janela e grava
// <saida>/<tela>-<modo>.png. O servidor sobe de novo para cada idioma (os
// dados vem do ambiente); a interface entra no idioma pelo localStorage,
// como a escolha em Perfil faria. So navega: nada e gravado nos dados de
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
const CONJUNTOS = [
  { idioma: "en", saida: resolve(RAIZ, "docs", "capturas"), termos: "termos.exemplo.en.txt" },
  { idioma: "pt", saida: resolve(RAIZ, "docs", "capturas", "pt"), termos: "termos.exemplo.txt" },
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

function ambienteDo(conjunto) {
  return {
    ...process.env,
    TRAMA_DEMO: "1",
    TRAMA_AUDIOS: resolve(RAIZ, "audios-demo", conjunto.idioma),
    VOZES_DB: resolve(RAIZ, "audios-demo", conjunto.idioma, "vozes-demo.db"),
    TRAMA_TERMOS: resolve(RAIZ, conjunto.termos),
    TRAMA_PORTA: PORTA_API,
  };
}

async function capturar(navegador, conjunto) {
  mkdirSync(conjunto.saida, { recursive: true });
  for (const modo of MODOS) {
    const contexto = await navegador.newContext({
      viewport: { width: LARGURA, height: ALTURA },
      deviceScaleFactor: 2,
      colorScheme: modo.esquema,
      reducedMotion: "reduce",
      locale: conjunto.idioma === "pt" ? "pt-BR" : "en-US",
    });
    await contexto.addInitScript((idioma) => {
      localStorage.setItem("trama:idioma", idioma);
    }, conjunto.idioma);
    const pagina = await contexto.newPage();
    for (const tela of TELAS) {
      await pagina.goto(`${BASE}/${tela.hash}`, { waitUntil: "networkidle" });
      await pagina.evaluate(() => document.fonts.ready);
      await pagina.screenshot({ path: resolve(conjunto.saida, `${tela.nome}-${modo.nome}.png`) });
      console.log(`  ${conjunto.idioma}/${tela.nome}-${modo.nome}.png`);
    }
    await contexto.close();
  }
}

const vite = subir("npx", ["vite", "--host", "127.0.0.1", "--port", PORTA_WEB, "--strictPort"], {
  cwd: FRONTEND,
  env: { ...process.env, TRAMA_PORTA: PORTA_API },
});
let servidor = null;
try {
  await esperar(BASE);
  const navegador = await chromium.launch();
  for (const conjunto of CONJUNTOS) {
    servidor = subir("python", ["-m", "trama.servidor.app"], { cwd: RAIZ, env: ambienteDo(conjunto) });
    await esperar(`http://127.0.0.1:${PORTA_API}/api/sistema`);
    await capturar(navegador, conjunto);
    servidor.kill();
    await new Promise((ok) => servidor.once("exit", ok));
    servidor = null;
  }
  await navegador.close();
} finally {
  vite.kill();
  servidor?.kill();
}
