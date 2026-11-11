import type { Catalogo } from "../textos";

export const processamento: Catalogo["processamento"] = {
  etapas: [
    "Converting audio to 16 kHz mono",
    "Diarizing (who spoke when)",
    "Identifying people by voice",
    "Analyzing overlap and interruptions",
    "Transcribing — the longest step",
  ],
  aoVivoFalantes: (n) => `${n} speakers`,
  aoVivoEntre: (min, max) => `between ${min} and ${max} speakers`,
  aoVivoPeloMenos: (min) => `at least ${min} speakers`,
  aoVivoAte: (max) => `up to ${max} speakers`,
  aoVivoMotor: (asr) => `with ${asr}`,
  aoVivoTermos: (n) => (n === 1 ? "1 company term" : `${n} company terms`),
  concluida: "completed",
  conectando: "Connecting…",
  decorrido: (duracao) => `Elapsed: ${duracao}`,
  cancelar: "Cancel",
  legendaCancelar: "Keeps the audio saved - you can try again.",
  confirmarCancelar:
    "Cancel processing?\n\nThe audio stays saved - you can try again later, without uploading the file again.",
  cancelado:
    "Processing canceled. The audio stays saved - you can try again whenever you want.",
  verReuniao: "View meeting",
  falhou: "Processing failed. Try again.",
  tentando: "Trying…",
  verificando: "Checking…",
  naoEstaProcessando:
    "This meeting isn't being processed right now. Go back to the list to start it or try again.",
  verLista: "View meeting list",
};
