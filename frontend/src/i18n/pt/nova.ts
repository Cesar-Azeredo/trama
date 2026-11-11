/** Tela de Nova reunião (telas/NovaReuniao.tsx). */
export const nova = {
  formatoNaoAceito: (extensoes: string) => `Formato não aceito. Use ${extensoes}.`,
  maiorQueLimite: (mb: string) => `Arquivo maior que o limite de ${mb} MB.`,
  arrasteAqui: "Arraste o áudio da reunião aqui, ou",
  escolhaUmArquivo: "escolha um arquivo",
  formatosAceitos: (extensoes: string, mb: string) => `${extensoes} — até ${mb} MB`,
  explicacaoPessoas:
    "É o maior ganho de precisão que existe: fixa quantos falantes procurar e restringe a comparação a quem estava lá. Sem marcar ninguém, tudo funciona igual, só que com menos precisão.",
  carregandoPessoas: "Carregando pessoas…",
  pessoaNova: "+ Pessoa nova",
  nomeDaPessoaNova: "Nome da pessoa nova",
  adicionar: "Adicionar",
  cancelar: "Cancelar",
  selecionadas: (n: number) =>
    n === 0 ? "nenhuma selecionada" : n === 1 ? "1 selecionada" : `${n} selecionadas`,
  caractereDeControle:
    "O título tem um caractere de controle (quebra de linha, tabulação...), que não é permitido.",
  tituloNaoSalvo: (erro: string) =>
    `O áudio foi enviado, mas o título não foi salvo: ${erro} A reunião ficou na fila, sem processar - dá para dar o título no detalhe dela.`,
  passoAudio: "O áudio",
  trocarArquivo: "Trocar arquivo",
  passoPessoas: "Quem estava na sala",
  progressoDoEnvio: "Progresso do envio",
  titulo: "Título",
  opcional: "(opcional)",
  exemploTitulo: "Ex.: Comitê de produto",
  ajudaTitulo:
    "Sem título, a reunião fica com o nome padrão: “Reunião” e o número dela. Dá para mudar depois, no detalhe.",
  enviando: "Enviando…",
  transcrever: "Transcrever",
  notaRodape: "Cerca de 6 minutos por hora de áudio. Nada sai desta máquina.",
};
