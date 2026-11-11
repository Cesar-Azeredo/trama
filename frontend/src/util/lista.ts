/**
 * Logica pura da tela de Lista (telas/Lista.tsx): agrupamento das reunioes,
 * busca por titulo e pessoas, texto de quem estava. Sem React e sem DOM -
 * testada em util/lista.test.ts.
 */
import type { ResumoReuniao } from "../api/reunioes";
import { localeAtual } from "../i18n/idioma";
import { textosAtuais } from "../i18n/textos";
import { ehVozSemPessoa, ordemDaBarra, textoVozesSemPessoa } from "./falante";
import { formatarTitulo, tituloDaReuniao } from "./formatarReuniao";

/**
 * Nomes na mesma ordem da barra (componentes/BarraFala: pessoas por
 * fala_pct, vozes sem pessoa no fim) quando ela existe - nunca a ordem
 * alfabetica de 'pessoas' ao lado de uma barra ordenada por peso, senao o
 * nome ao lado de cada segmento nao bate com a cor daquele segmento.
 *
 * "IGNORADO_SPEAKER_02"/"DESCONHECIDO_S0" nunca aparecem crus: viram
 * "1 voz nao atribuida" no fim - o mesmo lugar dos segmentos neutros.
 */
export function textoPessoas(reuniao: ResumoReuniao): string {
  const todos = reuniao.dinamica
    ? ordemDaBarra(reuniao.dinamica).map((d) => d.pessoa)
    : (reuniao.pessoas ?? []);
  const pessoas = todos.filter((n) => !ehVozSemPessoa(n));
  const semPessoa = todos.length - pessoas.length;
  const partes = [...pessoas];
  if (semPessoa > 0) partes.push(textoVozesSemPessoa(semPessoa));
  return partes.join(", ");
}

/** Ainda sem .json - fica no grupo "Na fila", sempre no topo. */
export function ehPendente(reuniao: ResumoReuniao): boolean {
  return (
    reuniao.estado === "nao_processada" ||
    reuniao.estado === "processando" ||
    reuniao.estado === "interrompido"
  );
}

/** Mes por extenso no idioma escolhido ("novembro de 2026", "November 2026"). */
function nomeDoMes(d: Date): string {
  return new Intl.DateTimeFormat(localeAtual(), { month: "long", year: "numeric" }).format(d);
}

/**
 * "Na fila" (sem .json: nao processada, processando, interrompida) e "A
 * revisar" (processada, com algum cluster sem decisao) no topo; as
 * revisadas - o estado normal, sem marca por linha - agrupadas por MES da
 * reuniao ("setembro de 2026"), do mais novo para o mais velho, no fuso da
 * maquina.
 *
 * Mes so pela data da GRAVACAO. Uma revisada cuja data e so a do arquivo
 * ("chegou em") iria para o mes em que o arquivo foi copiado, que nao diz
 * nada sobre quando a reuniao aconteceu - vai para "Sem data da gravação",
 * no fim. Grupo vazio nao aparece.
 */
export function grupos(reunioes: ResumoReuniao[]) {
  const fila = reunioes.filter(ehPendente);
  const aRevisar = reunioes.filter((r) => !ehPendente(r) && !r.revisada);
  const revisadas = reunioes.filter((r) => !ehPendente(r) && r.revisada);

  const comData = revisadas
    .filter((r) => r.data && r.data_origem === "gravacao")
    .sort((a, b) => b.data!.localeCompare(a.data!));
  const semData = revisadas.filter((r) => !(r.data && r.data_origem === "gravacao"));
  const meses: { chave: string; rotulo: string | null; itens: ResumoReuniao[] }[] = [];
  for (const r of comData) {
    const d = new Date(r.data!);
    const chave = `mes-${d.getFullYear()}-${d.getMonth()}`;
    let grupo = meses.find((m) => m.chave === chave);
    if (!grupo) {
      grupo = { chave, rotulo: nomeDoMes(d), itens: [] };
      meses.push(grupo);
    }
    grupo.itens.push(r);
  }
  const t = textosAtuais().formatos;
  return [
    { chave: "fila", rotulo: t.grupoFila, itens: fila },
    { chave: "a-revisar", rotulo: t.grupoARevisar, itens: aRevisar },
    ...meses,
    { chave: "sem-data", rotulo: t.grupoSemData, itens: semData },
  ].filter((g) => g.itens.length > 0);
}

/** Sem acento e sem maiuscula: "Clelia" acha "Clélia", "comite" acha
 * "Comitê". */
export function normalizar(texto: string): string {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/**
 * Busca no cliente, por titulo (o dado ou o padrao "Reuniao NN") e pelas
 * pessoas da reuniao. Cada palavra digitada tem de aparecer em algum
 * desses campos ("celso produto" acha a reuniao "Comitê de produto" em que
 * o Celso estava). Voz nao atribuida nao e pessoa - nao entra.
 */
export function casaBusca(r: ResumoReuniao, busca: string): boolean {
  const palavras = normalizar(busca).split(/\s+/).filter(Boolean);
  if (palavras.length === 0) return true;
  const nomes = (r.dinamica ? r.dinamica.map((d) => d.pessoa) : (r.pessoas ?? []))
    .filter((n) => !ehVozSemPessoa(n));
  const alvo = normalizar(
    [tituloDaReuniao(r.id, r.titulo), formatarTitulo(r.id), ...nomes].join(" "),
  );
  return palavras.every((p) => alvo.includes(p));
}
