/** Tela de Perfil e Configurações. */
export const perfil = {
  idioma: "Idioma",
  idiomaNota: "Só o texto do aplicativo muda. A fala das pessoas nunca é traduzida.",
  voce: "Você",
  seuNome: "Seu nome",
  voceNaGaleria: "Você na galeria de vozes (opcional)",
  nenhuma: "Nenhuma",
  foraDaGaleria: (nome: string) => `${nome} (fora da galeria)`,
  notaLocal: "Guardado só neste navegador. Não existe login: o app é de um usuário, nesta máquina.",
  configuracoes: "Configurações",
  aparencia: "Aparência",
  /** Uma chave por PreferenciaTema (tema/useTema.ts). */
  tema: {
    sistema: "Seguir o sistema",
    claro: "Claro",
    escuro: "Escuro",
  },
  termosDaEmpresa: "Termos da empresa",
  processamento: "Processamento",
  dispositivo: "Dispositivo",
  motorDeTranscricao: "Motor de transcrição",
  notaProcessamento: "Detectados nesta máquina, a cada transcrição. Não há o que escolher aqui.",
  dadosEPrivacidade: "Dados e privacidade",
  audiosETranscricoes: "Áudios e transcrições",
  bancoDeVozes: "Banco de vozes",
  notaPrivacidade:
    "Nada sai desta máquina. O áudio, a transcrição e os perfis de voz ficam nestes arquivos, e o app não faz nenhuma requisição para fora.",
  sobre: "Sobre",
  notaAtribuicoes:
    "Usa modelos e bibliotecas de terceiros. As atribuições abaixo são exigidas pelas licenças; o texto completo está em ATRIBUICAO.md, na pasta do app.",
  carregando: "Carregando…",
};
