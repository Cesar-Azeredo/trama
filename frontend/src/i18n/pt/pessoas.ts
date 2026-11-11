/** Tela Pessoas (telas/Pessoas.tsx). */
export const pessoas = {
  celula: {
    confirmada: "presença confirmada",
    na_sala: "estava na sala, presença não confirmada",
    ausente: "ausente",
    sem_dados: "reunião ainda não processada",
  },
  rotuloCelula: (reuniao: string, estado: string) => `${reuniao}: ${estado}`,
  segundos: (valor: string) => `${valor} s`,
  confirmarTitulo: (nome: string) => `Excluir a voz de ${nome}?`,
  confirmarTexto: (n: number) =>
    `Apaga o perfil de voz e tudo o que foi aprendido dela em cada reunião revisada (${n === 1 ? "1 reunião" : `${n} reuniões`}). Não dá para desfazer. As transcrições continuam com o nome de quem falou; só a voz sai do banco. Cópias de segurança antigas do banco (arquivos vozes.db.bak) não são alteradas.`,
  confirmarVolta: (nome: string) =>
    `Se a voz de ${nome} for confirmada de novo numa revisão, ela volta a ser aprendida a partir dali.`,
  excluindo: "Excluindo…",
  excluirVozDe: (nome: string) => `Excluir a voz de ${nome}`,
  cancelar: "Cancelar",
  legenda: "Legenda",
  legendaConfirmada: "presença confirmada na revisão",
  legendaNaSala: "estava na sala, não confirmada (ainda não revisada, ou grupo de voz ignorado)",
  legendaAusente: "ausente",
  legendaSemDados: "reunião ainda não processada",
  vozExcluida: (nome: string) => `A voz de ${nome} foi excluída.`,
  vozExcluidaSemCompactar: (nome: string) =>
    `A voz de ${nome} foi excluída, mas o arquivo do banco não pôde ser compactado agora - restos do perfil podem continuar no arquivo até a próxima exclusão.`,
  carregando: "Carregando pessoas…",
  semPessoas:
    "Nenhuma voz aprendida ainda. A primeira aparece quando você confirmar quem é cada voz na revisão de uma reunião.",
  colunaPessoa: "Pessoa",
  colunaVoz: "Voz aprendida",
  colunaParticipacao: "Participação por reunião",
  colunaAcoes: "Ações",
  perfilEmFormacao: "perfil em formação",
  ultima: " · última ",
  excluir: "Excluir",
  explicacao:
    "Não existe cadastro de voz. O perfil de cada pessoa é colhido das próprias reuniões, quando você confirma na revisão quem é cada voz, e fica mais estável a cada revisão. Uma gravação avulsa, feita em outro lugar e com outro aparelho, soa diferente demais da sala de reunião para servir de base.",
};
