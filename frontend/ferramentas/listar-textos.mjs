// ferramentas/listar-textos.mjs - Lista todos os textos de um catalogo
// (i18n/<idioma>), um por linha: "secao.chave = texto". Para revisar a
// traducao fora do codigo.
//
// Texto simples sai como esta. Funcao (texto com parametro, plural) sai
// duas vezes: a forma do codigo (o template, como esta escrito) e um
// exemplo com valores de amostra.
//
// Uso (de frontend/):  node ferramentas/listar-textos.mjs en > textos-en.txt
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const idioma = process.argv[2] ?? "en";
const SRC = resolve(dirname(fileURLToPath(import.meta.url)), "..", "src");

// Transpila i18n/ e util/numeros.ts (que alguns catalogos usam) para JS
// num diretorio temporario, e importa o catalogo pronto.
// Dentro de node_modules: os modulos transpilados resolvem "react" dali.
mkdirSync(join(SRC, "..", "node_modules", ".cache"), { recursive: true });
const destino = mkdtempSync(join(SRC, "..", "node_modules", ".cache", "catalogos-"));
function transpilar(rel) {
  const codigo = readFileSync(join(SRC, rel), "utf8");
  const js = ts.transpileModule(codigo, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText.replace(/from "(\.[^"]+)"/g, (_, alvo) => {
    // import de pasta ("./en") aponta para o index dela
    const pasta = existsSync(join(SRC, dirname(rel), alvo)) && statSync(join(SRC, dirname(rel), alvo)).isDirectory();
    return `from "${alvo}${pasta ? "/index" : ""}.js"`;
  });
  const saida = join(destino, rel.replace(/\.ts$/, ".js"));
  mkdirSync(dirname(saida), { recursive: true });
  writeFileSync(saida, js);
}
for (const pasta of ["i18n", "i18n/pt", "i18n/en"]) {
  for (const f of readdirSync(join(SRC, pasta))) {
    if (f.endsWith(".ts") && !f.endsWith(".test.ts")) transpilar(`${pasta}/${f}`);
  }
}
transpilar("util/numeros.ts");
// idioma.ts usa localStorage/navigator so com guarda; numeros.ts le o locale atual.
const { catalogo } = await import(pathToFileURL(join(destino, "i18n/textos.js")).href);
const { definirIdioma } = await import(pathToFileURL(join(destino, "i18n/idioma.js")).href);
definirIdioma(idioma);
const cat = catalogo(idioma);

// Valores de amostra para os exemplos de funcao, pelo nome do parametro.
const AMOSTRA = { n: 3, total: 3, min: 2, max: 5, status: 500, codigo: "codigo_x" };
function exemplo(fn) {
  const nomes = (fn.toString().match(/^\(?([^)=]*)\)?\s*=>/)?.[1] ?? "")
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);
  const args = nomes.map((p) =>
    p === "p" ? new Proxy({}, { get: (_, k) => `{${String(k)}}` }) : (AMOSTRA[p] ?? `{${p}}`),
  );
  try {
    const r = fn(...args);
    return Array.isArray(r) ? r.join("…") : String(r);
  } catch {
    return "(sem exemplo)";
  }
}

const linhas = [];
function percorrer(obj, prefixo) {
  for (const [chave, valor] of Object.entries(obj)) {
    const caminho = prefixo ? `${prefixo}.${chave}` : chave;
    if (typeof valor === "string") linhas.push(`${caminho} = ${valor.replace(/\n/g, "\\n")}`);
    else if (typeof valor === "function") {
      const forma = valor.toString().replace(/\s+/g, " ");
      linhas.push(`${caminho} = ${exemplo(valor).replace(/\n/g, "\\n")}    [codigo: ${forma}]`);
    } else if (Array.isArray(valor)) valor.forEach((v, i) => linhas.push(`${caminho}[${i}] = ${v}`));
    else if (valor && typeof valor === "object") percorrer(valor, caminho);
  }
}
percorrer(cat, "");

// Constantes auxiliares de um catalogo (fora do objeto exportado, usadas
// dentro das funcoes - ex.: rotulos de campo dos erros de glossario).
for (const f of readdirSync(join(SRC, "i18n", idioma))) {
  const fonte = readFileSync(join(SRC, "i18n", idioma, f), "utf8");
  for (const m of fonte.matchAll(/^const (\w+)(?::[^=]+)? = ([\s\S]*?);$/gm)) {
    const [, nome, valor] = m;
    const textos = [...valor.matchAll(/(?:(\w+): )?(["'`])((?:(?!\2).)*)\2/g)];
    for (const [, chave, , texto] of textos) {
      linhas.push(`(${f.replace(/\.ts$/, "")}) ${nome}${chave ? "." + chave : ""} = ${texto}`);
    }
  }
}
rmSync(destino, { recursive: true, force: true });
process.stdout.write(linhas.join("\n") + "\n");
