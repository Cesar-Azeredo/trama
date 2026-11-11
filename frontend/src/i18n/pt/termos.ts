import { numero } from "../../util/numeros";

/**
 * Termos da empresa e "Aplicar às reuniões já processadas" (Perfil).
 * As chaves que devolvem três pedaços são frases com dois números em
 * <span className="numeros">: [antes do 1º, entre os dois, depois do 2º].
 * O plural fica aqui dentro, a frase inteira num lugar só.
 */
export const termos = {
  explicacao:
    "Nomes, siglas e produtos da empresa, escritos do jeito certo. As formas erradas embaixo de cada um são corrigidas sozinhas em toda transcrição nova. O que é cada termo vai junto da transcrição baixada (.txt), para quem ler entender.",
  carregandoTermos: "Carregando termos…",
  removerTermo: "Remover termo",
  removerOTermo: (termo: string) => `Remover o termo ${termo}`,
  removido: (termo: string) => `“${termo}” removido.`,
  corrige: "Corrige:",
  pararDeCorrigir: (errado: string) => `Parar de corrigir ${errado}`,
  pararDeCorrigirDica: "Parar de corrigir (o que já foi corrigido continua)",
  naoSeraMaisCorrigido: (errado: string) => `“${errado}” não será mais corrigido.`,
  adicionarVariacao: "+ Adicionar variação",
  adicionarTermo: "Adicionar termo",
  nomeDoTermo: "Nome do termo",
  nomeDoTermoExemplo: "Nome, do jeito certo (ex.: MQX)",
  oQueE: "O que é",
  oQueEExemplo: "O que é? (opcional)",
  adicionando: "Adicionando…",
  adicionado: (termo: string) => `“${termo}” adicionado.`,

  // Descrição de um termo
  adicionarDescricao: "+ Adicionar descrição",
  adicionarDescricaoDe: (termo: string) => `Adicionar descrição de ${termo}`,
  descricaoDe: (termo: string) => `Descrição de ${termo}`,
  descricaoExemplo: "Descrição (ex.: ferramenta de aprovação de projetos)",
  salvando: "Salvando…",
  salvo: "Salvo.",

  // Adicionar variação
  comoApareceErrado: "Como aparece escrito errado",
  jaEVariacao: (errado: string, termo: string) => `“${errado}” já é uma variação de ${termo}.`,
  naoApareceEmNenhuma: "Não aparece em nenhuma reunião processada. Vale para as próximas.",
  apareceVezesEmReunioes: (vezes: number, reunioes: number): [string, string, string] => [
    "Aparece ",
    ` ${vezes === 1 ? "vez" : "vezes"} em `,
    ` ${reunioes === 1 ? "reunião" : "reuniões"}`,
  ],
  conferindo: "Conferindo…",
  conferir: "Conferir",
  adicionar: "Adicionar",
  corrigirEm: (n: number) => `Corrigir em ${numero(n)} ${n === 1 ? "lugar" : "lugares"}`,
  corrigidoEm: (trecho: string, n: number) =>
    `“${trecho}” corrigido em ${numero(n)} ${n === 1 ? "lugar" : "lugares"}.`,
  seraCorrigidoNasProximas: (trecho: string) => `“${trecho}” será corrigido nas próximas reuniões.`,
  cancelar: "Cancelar",

  // Aplicar às reuniões já processadas
  aplicarNasProcessadas: "Aplicar às reuniões já processadas",
  salveAntes: "Salve antes - a correção usa o que está gravado.",
  mostraAntes:
    "Mostra antes quantas substituições seriam feitas, e em quais reuniões. Nada muda até você confirmar.",
  nadaFoiAlterado: "Nada foi alterado.",
  aplicadoEm: (n: number) => `Aplicado em ${numero(n)} ${n === 1 ? "reunião" : "reuniões"}.`,
  nadaACorrigir:
    "Nada a corrigir: as reuniões já processadas estão de acordo com os termos da empresa.",
  fechar: "Fechar",
  substituicoesEmReunioes: (total: number, reunioes: number): [string, string, string] => [
    "",
    ` ${total === 1 ? "substituição" : "substituições"} em `,
    ` ${reunioes === 1 ? "reunião" : "reuniões"}`,
  ],
  notaReescreve:
    "Reescreve o texto (.json e .txt) dessas reuniões. As marcas de posição (pista de palavra, confiança baixa, trecho sem texto) acompanham a correção.",
  aplicando: "Aplicando…",
  aplicar: "Aplicar",
};
