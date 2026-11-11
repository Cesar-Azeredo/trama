/** Tela de processamento (telas/ProcessamentoReuniao.tsx). */
export const processamento = {
  /** As 5 etapas na ordem do pipeline - o servidor manda o NUMERO da etapa
   * atual (1 a 5), nunca o texto do stdout. */
  etapas: [
    "Convertendo áudio para 16 kHz mono",
    "Diarizando (quem falou quando)",
    "Identificando as pessoas pela voz",
    "Analisando sobreposição e interrupções",
    "Transcrevendo — a etapa mais demorada",
  ],
  /** O que o pipeline acrescentou a etapa atual, vindo como dado
   * (servidor/processamento.py: detalhe_da_etapa). */
  aoVivoFalantes: (n: number) => `${n} falantes`,
  aoVivoEntre: (min: number, max: number) => `entre ${min} e ${max} falantes`,
  aoVivoPeloMenos: (min: number) => `pelo menos ${min} falantes`,
  aoVivoAte: (max: number) => `até ${max} falantes`,
  aoVivoMotor: (asr: string) => `com ${asr}`,
  aoVivoTermos: (n: number) => (n === 1 ? "1 termo do domínio" : `${n} termos do domínio`),
  concluida: "concluída",
  conectando: "Conectando…",
  decorrido: (duracao: string) => `Decorrido: ${duracao}`,
  cancelar: "Cancelar",
  legendaCancelar: "Mantém o áudio salvo - dá para tentar de novo.",
  confirmarCancelar:
    "Cancelar o processamento?\n\nO áudio continua salvo - você pode tentar de novo depois, sem subir o arquivo outra vez.",
  cancelado:
    "Processamento cancelado. O áudio continua salvo - você pode tentar novamente quando quiser.",
  verReuniao: "Ver reunião",
  falhou: "O processamento falhou. Tente novamente.",
  tentando: "Tentando…",
  verificando: "Verificando…",
  naoEstaProcessando:
    "Esta reunião não está sendo processada agora. Volte para a lista para iniciar ou tentar de novo.",
  verLista: "Ver lista de reuniões",
};
