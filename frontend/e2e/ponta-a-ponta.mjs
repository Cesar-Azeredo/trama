// e2e/ponta-a-ponta.mjs - Teste de ponta a ponta, num Chromium sem janela,
// so com os dados de demonstracao: navegacao entre as secoes, a revisao
// inteira (vozes, termos e trechos para conferir) e apagar uma reuniao.
//
// Nunca toca audios/ nem vozes.db reais: copia audios-demo/pt, o
// vozes-demo.db e o termos.exemplo.txt para uma pasta temporaria (o teste
// apaga e grava coisas), sobe o servidor e o Vite em portas proprias e, no
// fim, encerra so os processos que ele mesmo subiu e apaga a copia.
// Qualquer resposta 403 ou 5xx, erro de console ou da pagina reprova - e
// assim que a conferencia de Host/Origin pelo proxy do Vite (ADR 0030)
// fica verificada a cada execucao.
//
// Uso (de frontend/, com o pacote trama instalado no Python do PATH):
//     npm run e2e
// Portas: TRAMA_E2E_PORTA_API (8795) e TRAMA_E2E_PORTA_WEB (5195).
import { spawn } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const RAIZ = resolve(FRONTEND, "..");
const PORTA_API = process.env.TRAMA_E2E_PORTA_API ?? "8795";
const PORTA_WEB = process.env.TRAMA_E2E_PORTA_WEB ?? "5195";
const BASE = `http://127.0.0.1:${PORTA_WEB}`;
const PYTHON = process.env.PYTHON ?? "python";

// --- dados: copia temporaria da demonstracao em portugues -----------------

const DADOS = mkdtempSync(join(tmpdir(), "trama-e2e-"));
for (const item of readdirSync(join(RAIZ, "audios-demo", "pt"))) {
  if (item.startsWith("reuniao_")) {
    cpSync(join(RAIZ, "audios-demo", "pt", item), join(DADOS, item), { recursive: true });
  }
}
cpSync(join(RAIZ, "audios-demo", "pt", "vozes-demo.db"), join(DADOS, "vozes.db"));
cpSync(join(RAIZ, "termos.exemplo.txt"), join(DADOS, "termos.txt"));

const AMBIENTE = {
  ...process.env,
  TRAMA_DEMO: "1",
  TRAMA_AUDIOS: DADOS,
  VOZES_DB: join(DADOS, "vozes.db"),
  TRAMA_TERMOS: join(DADOS, "termos.txt"),
  TRAMA_PORTA: PORTA_API,
  TRAMA_PORTA_FRONTEND: PORTA_WEB,
  TRAMA_IDIOMA: "pt",
};

// --- processos ---------------------------------------------------------------

const filhos = [];
function subir(comando, args, cwd) {
  const p = spawn(comando, args, { cwd, env: AMBIENTE, stdio: ["ignore", "pipe", "pipe"] });
  let log = "";
  p.stdout.on("data", (d) => (log += d));
  p.stderr.on("data", (d) => (log += d));
  p.log = () => log;
  filhos.push(p);
  return p;
}

async function esperar(url) {
  for (let i = 0; i < 150; i++) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      // ainda subindo
    }
    await new Promise((ok) => setTimeout(ok, 200));
  }
  throw new Error(`nao respondeu: ${url}`);
}

// --- passos ------------------------------------------------------------------

const resultados = [];
const problemas = [];

async function passo(nome, fn) {
  const inicio = Date.now();
  try {
    await fn();
    resultados.push({ nome, ok: true, ms: Date.now() - inicio });
  } catch (e) {
    resultados.push({ nome, ok: false, ms: Date.now() - inicio, erro: e.message.split("\n")[0] });
  }
}

function confirmar(condicao, mensagem) {
  if (!condicao) throw new Error(mensagem);
}

// Troca de tela e so mudanca de hash: o networkidle volta antes do render.
async function telaPronta(pagina, hash) {
  await pagina.waitForFunction(
    (h) =>
      location.hash === h &&
      document.querySelector("main") &&
      !/Carregando/.test(document.querySelector("main").innerText),
    hash,
  );
}

async function navegacao(pagina) {
  await pagina.goto(`${BASE}/#/`, { waitUntil: "networkidle" });
  for (const [secao, hash, conteudo] of [
    ["Reuniões", "#/reunioes", "Retrospectiva da entrega"],
    ["Pessoas", "#/pessoas", "Beatriz"],
    ["Perfil", "#/perfil", "Configurações"],
    ["Nova reunião", "#/", "Quem estava na sala"],
  ]) {
    await pagina.locator("header").getByRole("link", { name: secao, exact: true }).click();
    await telaPronta(pagina, hash);
    await pagina.locator('header [aria-current="page"]', { hasText: secao }).waitFor();
    await pagina.locator("main").getByText(conteudo).first().waitFor();
  }
  await pagina.goto(`${BASE}/#/reuniao/reuniao_01`);
  await telaPronta(pagina, "#/reuniao/reuniao_01");
  await pagina.locator(".transcript .linha-fala").first().waitFor();
}

async function revisao(pagina) {
  await pagina.goto(`${BASE}/#/reuniao/reuniao_03/revisar`);
  await telaPronta(pagina, "#/reuniao/reuniao_03/revisar");

  // vozes: salvar pede a previa; "Confirmar e salvar" so quando muda voz
  await pagina.getByRole("button", { name: "Salvar revisão" }).click();
  const confirmarESalvar = pagina.getByRole("button", { name: "Confirmar e salvar" });
  const termos = pagina.getByRole("heading", { name: "Termos para conferir" });
  await Promise.race([confirmarESalvar.waitFor(), termos.waitFor()]);
  if (await confirmarESalvar.isVisible()) await confirmarESalvar.click();

  // termos: ignorar o primeiro, concluir
  await termos.waitFor();
  const itens = pagina.locator(".conferir__item");
  const antes = await itens.count();
  confirmar(antes > 0, "nenhum termo para conferir na demonstracao");
  await itens.first().getByRole("button", { name: "Ignorar" }).click();
  await pagina.locator(".conferir__feito").waitFor();
  confirmar((await itens.count()) === antes - 1, "o termo ignorado continuou na lista");
  await pagina
    .getByRole("button", { name: antes > 1 ? "Concluir" : "Ir para a reunião" })
    .click();

  // trechos: escrever na lacuna, "nao da para entender" na fala
  await pagina.getByRole("heading", { name: "Trechos para conferir" }).waitFor();
  const lacuna = itens.filter({ has: pagina.locator(".trechos__lacuna") }).first();
  await lacuna.locator("textarea").fill("e isso entra no projeto");
  await lacuna.getByRole("button", { name: "Gravar", exact: true }).click();
  await pagina.locator(".conferir__feito").waitFor();
  await itens.first().getByRole("button", { name: "Não dá para entender" }).click();
  await pagina.getByRole("button", { name: "Ir para a reunião" }).click();

  // de volta ao Detalhe: revisada, com o texto escrito no ponto da lacuna
  await telaPronta(pagina, "#/reuniao/reuniao_03");
  await pagina.locator(".lacuna-escrita", { hasText: "e isso entra no projeto" }).waitFor();
  await pagina.locator(".tela-detalhe__estado-revisada").waitFor();
  const resto = await pagina.evaluate(async () =>
    (await fetch("/api/reunioes/reuniao_03/trechos-para-conferir")).json(),
  );
  confirmar(resto.itens.length === 0, "trecho respondido voltou a ser perguntado");
}

async function apagarReuniao(pagina) {
  await pagina.goto(`${BASE}/#/reuniao/reuniao_02`);
  await telaPronta(pagina, "#/reuniao/reuniao_02");
  await pagina.getByRole("button", { name: "Apagar reunião" }).click();
  // a confirmacao diz quanto de voz cada pessoa perde antes de liberar
  const sim = pagina.locator(".confirmar-exclusao__sim");
  await pagina.waitForFunction(() => !document.querySelector(".confirmar-exclusao__sim")?.disabled);
  const perdas = await pagina.locator(".confirmar-exclusao__lista li").allInnerTexts();
  confirmar(perdas.length > 0, "a confirmacao nao mostrou a voz que sai do banco");
  confirmar(perdas.some((p) => /perde \d+ s de voz/.test(p)), `perdas sem numero: ${perdas}`);
  await sim.click();
  await telaPronta(pagina, "#/reunioes");
  await pagina.locator("main").getByText("Planejamento do trimestre").waitFor();
  confirmar(
    (await pagina.locator("main").getByText("Revisão do Painel Órbita").count()) === 0,
    "a reuniao apagada continua na lista",
  );
  confirmar(!existsSync(join(DADOS, "reuniao_02")), "a pasta da reuniao continua no disco");
}

// --- execucao ----------------------------------------------------------------

const inicio = Date.now();
let navegador;
try {
  const servidor = subir(PYTHON, ["-m", "trama.servidor.app"], RAIZ);
  const vite = subir(process.execPath, [join(FRONTEND, "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1"], FRONTEND);
  try {
    await esperar(`http://127.0.0.1:${PORTA_API}/api/sistema`);
    await esperar(BASE);
  } catch (e) {
    console.error(servidor.log(), vite.log());
    throw e;
  }

  navegador = await chromium.launch();
  const contexto = await navegador.newContext({
    viewport: { width: 1280, height: 900 },
    reducedMotion: "reduce",
    locale: "pt-BR",
  });
  await contexto.addInitScript(() => localStorage.setItem("trama:idioma", "pt"));
  const pagina = await contexto.newPage();
  pagina.setDefaultTimeout(10_000);
  pagina.on("response", (r) => {
    if (r.status() === 403 || r.status() >= 500) {
      problemas.push(`${r.status()} ${r.request().method()} ${r.url()}`);
    }
  });
  pagina.on("console", (m) => m.type() === "error" && problemas.push(`console: ${m.text()}`));
  pagina.on("pageerror", (e) => problemas.push(`pagina: ${e.message}`));

  await passo("navegacao entre as secoes", () => navegacao(pagina));
  await passo("revisao: vozes, termos e trechos para conferir", () => revisao(pagina));
  await passo("apagar reuniao, com a confirmacao", () => apagarReuniao(pagina));
} finally {
  await navegador?.close();
  for (const p of filhos) p.kill();
  rmSync(DADOS, { recursive: true, force: true });
}

for (const r of resultados) {
  console.log(`${r.ok ? "PASSOU" : "FALHOU"}  ${r.nome} (${(r.ms / 1000).toFixed(1)} s)${r.erro ? "\n        " + r.erro : ""}`);
}
for (const p of problemas) console.log(`PROBLEMA  ${p}`);
const ok = resultados.length === 3 && resultados.every((r) => r.ok) && problemas.length === 0;
console.log(`\n${resultados.filter((r) => r.ok).length}/3 passaram, ${problemas.length} problema(s), ${((Date.now() - inicio) / 1000).toFixed(1)} s no total`);
process.exit(ok ? 0 : 1);
