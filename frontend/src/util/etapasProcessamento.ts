/**
 * Rotulos FIXOS das 5 etapas - o que a tela de processamento mostra,
 * sempre a mesma independente do audio. O texto EXATO que pipeline.py imprime (que
 * pode variar - "N falantes", contagem de termos do dominio) aparece a
 * parte, como atividade ao vivo da etapa atual - ver `rotuloAoVivo`.
 *
 * Nenhuma barra de progresso linear: as 5 etapas NAO tem duracao igual
 * (transcricao sozinha leva mais que as outras quatro juntas) - uma
 * barra proporcional a "etapa atual / 5" mentiria sobre quanto falta.
 */
export const ETAPAS = [
  "Convertendo áudio para 16 kHz mono",
  "Diarizando (quem falou quando)",
  "Identificando as pessoas pela voz",
  "Analisando sobreposição e interrupções",
  "Transcrevendo — a etapa mais demorada",
];

