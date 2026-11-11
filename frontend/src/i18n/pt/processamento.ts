/** Tela de processamento (telas/ProcessamentoReuniao.tsx, util/etapasProcessamento.ts). */
export const processamento = {
  /** As 5 etapas na ordem do pipeline. O português também é o texto que
   * pipeline.py imprime - util/etapasProcessamento.ts compara com ele. */
  etapas: [
    "Convertendo áudio para 16 kHz mono",
    "Diarizando (quem falou quando)",
    "Identificando as pessoas pela voz",
    "Analisando sobreposição e interrupções",
    "Transcrevendo — a etapa mais demorada",
  ],
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
