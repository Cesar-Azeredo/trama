/** Tela de revisão das vozes (telas/Revisao.tsx). */
export const revisao = {
  modos: {
    aprender: {
      rotulo: "Confirmar e aprender a voz",
      explicacao:
        "O nome vai para o transcript e esta voz passa a fazer parte do perfil da pessoa.",
    },
    so_nomear: {
      rotulo: "Só nomear, sem aprender",
      explicacao:
        "O nome vai para o transcript, mas o perfil de voz de ninguém muda. Use quando a voz é quase toda de uma pessoa, com trechos de outras.",
    },
    ignorar: {
      rotulo: "Ignorar este cluster",
      explicacao:
        "O nome não é gravado e o perfil de voz de ninguém é atualizado com este cluster. Use quando a voz estiver misturada demais para ter um nome.",
    },
  },
  abaixoDoLimiar: "abaixo do limiar",
  comFolga: "com folga",
  raspandoNoLimiar: "raspando no limiar",
  trechoEm: (segundos: string) => `trecho de ${segundos}s`,
  limiarSimMin: (valor: string) => `limiar SIM_MIN = ${valor}`,
  segundosDeFala: (segundos: string) => `${segundos}s de fala`,
  quemE: "Quem é?",
  ignorado: "Ignorado",
  nomeDaPessoa: "Nome da pessoa",
  oQueFazerCom: (label: string) => `O que fazer com ${label}`,
  ensinar: (segundos: string, pessoa: string) =>
    `Isso vai ensinar ${segundos} da voz de ${pessoa}.`,
  mover: (segundos: string, pessoa: string, para: string) =>
    `Isso vai mover ${segundos} da voz de ${pessoa} para ${para}.`,
  remover: (segundos: string, pessoa: string) =>
    `Isso vai remover ${segundos} da voz de ${pessoa}.`,
  perfilSome: (pessoa: string) => `${pessoa} fica sem voz aprendida e sai da galeria.`,
  avisoLedgerTitulo: "Esta revisão muda a voz aprendida",
  salvando: "Salvando…",
  confirmarESalvar: "Confirmar e salvar",
  voltarERever: "Voltar e rever",
  carregandoReuniao: "Carregando reunião…",
  naoProcessada: "Esta reunião ainda não foi processada - não há clusters para revisar.",
  titulo: (reuniao: string) => `Revisar ${reuniao}`,
  avisoLimiarAntigo: (simMin: string) =>
    `Esta reunião foi processada antes de o limiar ser gravado por reunião. O limiar marcado abaixo é o de hoje (SIM_MIN = ${simMin}), não necessariamente o que estava em vigor quando ela foi processada.`,
  salvarRevisao: "Salvar revisão",
  nadaGravadoAteConfirmar: "Nada é gravado até confirmar aqui.",
};
