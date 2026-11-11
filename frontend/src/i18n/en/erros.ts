import type { Parametros } from "../pt/erros";
import type { Catalogo } from "../textos";

const CAMPO_GLOSSARIO: Record<string, string> = {
  errado: "the wrong form",
  certo: "the correct form",
  comentario: "the comment",
};
const CAMPO_CORRECAO: Record<string, string> = { trecho: "The passage", certo: "The correct form" };
const REAPLICAR = 'Use "Apply to meetings already processed" in Company terms to finish.';

export const erros: Catalogo["erros"] = {
  servidorDesatualizado: "The server is out of date. Restart the server and reload the page.",
  dadosRecusados: "The server rejected the data sent. Reload the page and try again.",
  falhaComServidor: (status) => `The server returned an error (${status}).`,
  falhaDeRedeNoEnvio: "Network error while uploading the audio.",
  codigoDesconhecido: (codigo) => `Server error (${codigo}).`,

  porCodigo: {
    intervalo_invalido: () =>
      "Invalid range: the end must be after the start, and the start can't be negative.",
    trecho_longo_demais: (p: Parametros) =>
      `A ${p.pedido}s clip was requested; the maximum for review is ${p.maximo}s.`,
    sem_audio_na_demonstracao: () => "Audio is not available in the demo.",
    sem_transcricao_para_baixar: () =>
      "This meeting hasn't been processed yet — there is no transcript to download.",
    busca_longa_demais: (p: Parametros) => `The search is longer than ${p.maximo} characters.`,
    nome_invalido: () => "Invalid name.",
    sem_clusters_para_revisar: () =>
      "This meeting hasn't been processed yet — there are no voice groups to review.",
    falha_salvar_audio: () => "Could not save the uploaded audio.",
    id_invalido: () => "Invalid meeting id.",
    reuniao_nao_encontrada: () => "Meeting not found.",
    sem_audio_para_processar: () => "No audio found for this meeting.",
    ja_processando: (p: Parametros) =>
      `Another meeting is already being processed (${p.id}). Wait for it to finish before starting another.`,
    nada_para_cancelar: () => "This meeting is not being processed right now.",
    audio_nao_encontrado: () => "Audio file not found for this meeting.",
    falha_recortar_audio: () => "Could not cut the audio.",
    fala_mudou: () =>
      "The transcript changed since the page was opened (the meeting was reprocessed). Reload the page and correct it again.",
    falha_gravar_correcao_fala: () =>
      "Could not save the correction. The previous text is still there — try again.",
    falha_gravar_titulo: () => "Could not save the title. The previous one is still there — try again.",
    pessoa_nao_encontrada: () => "This person is not in the gallery.",
    falha_excluir_pessoa: () => "Could not delete the profile. Nothing was removed — try again.",
    falha_gravar_revisao: () => "Could not save the review. It is safe to repeat — try again.",
    falha_gravar_glossario: () =>
      "Could not save the glossary. The previous file is still intact — try again.",
    falha_gravar_termos: () => "Could not save. The terms are as they were — try again.",
    falha_gravar_resposta: () => "Could not save the answer. Try again.",
    falha_gravar_descricao: () => "Could not save the description. Try again.",
    mudou_desde_conferencia: () =>
      "A meeting changed since the check. Check again before correcting.",
    correcao_parcial: (p: Parametros) =>
      `The correction applies to future meetings, but it was not applied to all the processed ones (${p.corrigidas} corrected). ${REAPLICAR}`,
    falha_gravar_correcao: () => "Could not save the correction. Nothing was changed — try again.",
    mudou_desde_sugestao: () =>
      "A meeting changed since the suggestion. Correct it again to see the updated suggestions.",
    correcoes_parciais: (p: Parametros) =>
      `The corrections apply to future meetings, but they were not applied to all the processed ones (${p.corrigidas} corrected). ${REAPLICAR}`,
    falha_gravar_correcoes: () => "Could not save the corrections. Nothing was changed — try again.",
    mudou_desde_previa: () =>
      "The glossary or a meeting changed since the preview. Check the preview again before applying.",
    falha_reaplicar: (p: Parametros) =>
      `Could not finish applying the glossary. Already applied: ${p.feitas}. The others are as they were — you can try again.`,
    extensao_invalida: (p: Parametros) => `Unsupported extension. Use one of these formats: ${p.formatos}.`,
    arquivo_grande_demais: (p: Parametros) => `The file is larger than the ${p.maximo_mb} MB limit.`,
    selecione_trecho: () => "Select the passage that is wrong.",
    escreva_certo: () => "Type the correct form.",
    correcao_longa_demais: (p: Parametros) =>
      `${CAMPO_CORRECAO[p.campo] ?? p.campo} is longer than ${p.maximo} characters.`,
    correcao_com_seta: () => "The text cannot contain =>.",
    trecho_com_cerquilha: () => "The passage cannot start with #.",
    trecho_ja_certo: () => "The passage is already written that way.",
    selecione_palavra: () => "Select at least one word.",
    marque_pelo_menos_uma: () => "Check at least one.",
    titulo_nao_texto: () => "The title must be text.",
    titulo_com_controle: () =>
      "The title has a control character (line break, tab...), which is not allowed.",
    titulo_longo_demais: (p: Parametros) =>
      `The title has ${p.tamanho} characters; the maximum is ${p.maximo}.`,
    fala_vazia: () =>
      'The segment text cannot be empty. To go back to the transcribed text, use "Revert to original".',
    fala_com_controle: () => "The text cannot have a line break or a control character.",
    fala_longa_demais: (p: Parametros) =>
      `The text has ${p.tamanho} characters; the maximum is ${p.maximo}.`,
    nome_longo_demais: (p: Parametros) =>
      `The name has ${p.tamanho} characters; the maximum is ${p.maximo}.`,
    nome_com_controle: () => "The name contains a control character, which is not allowed.",
    forma_invalida: () => "Invalid form.",
    linha_nao_texto: (p: Parametros) =>
      `Line ${p.linha}: ${CAMPO_GLOSSARIO[p.campo] ?? p.campo} must be text.`,
    linha_com_quebra: (p: Parametros) =>
      `Line ${p.linha}: ${CAMPO_GLOSSARIO[p.campo] ?? p.campo} cannot have a line break.`,
    linha_longa_demais: (p: Parametros) =>
      `Line ${p.linha}: ${CAMPO_GLOSSARIO[p.campo] ?? p.campo} is longer than ${p.maximo} characters.`,
    linha_formato_invalido: (p: Parametros) => `Line ${p.linha}: invalid format.`,
    errado_vazio: (p: Parametros) => `Line ${p.linha}: the wrong form cannot be empty.`,
    errado_com_cerquilha: (p: Parametros) =>
      `Line ${p.linha}: the wrong form cannot start with # (the line would become a comment).`,
    errado_com_seta: (p: Parametros) => `Line ${p.linha}: the wrong form cannot contain =>.`,
    comentario_com_seta: (p: Parametros) => `Line ${p.linha}: a comment with => would be read as a rule.`,
    linha_tipo_desconhecido: (p: Parametros) => `Line ${p.linha}: unknown type.`,
    descricoes_formato_invalido: () => "Invalid format for the descriptions.",
    descricao_nao_texto: (p: Parametros) => `The description of ${p.termo} must be text.`,
    descricao_sem_termo: () => "A description has no term.",
    termo_invalido: (p: Parametros) =>
      `The term ${p.termo} cannot have a line break or be longer than ${p.maximo} characters.`,
    termo_repetido: (p: Parametros) => `The term ${p.termo} appears twice.`,
    descricao_com_quebra: (p: Parametros) => `The description of ${p.termo} cannot have a line break.`,
    descricao_longa_demais: (p: Parametros) =>
      `The description of ${p.termo} is longer than ${p.maximo} characters.`,
    termo_com_seta: (p: Parametros) => `The term ${p.termo} contains => and cannot have a description.`,
    glossario_formato_invalido: () => "Invalid format.",
    glossario_longo_demais: (p: Parametros) => `The glossary is longer than ${p.maximo} lines.`,
    termo_vazio: () => "The term cannot be empty.",
    escreva_nome_do_termo: () => "Type the name of the term.",
    motivo_ja_processando: () =>
      "This meeting is being processed right now.",
    motivo_interrompida: () =>
      "The previous processing was interrupted (the server restarted midway). The audio is still saved — you can try again.",
    processamento_falhou: () =>
      "Processing failed. Check the server log for details and try again.",
    correcao_existente_prevalece: (p: Parametros) =>
      `In part of the text, the existing correction from "${p.errado}" to "${p.certo}" will keep applying instead of this one.`,
    edicoes_sem_fala: (p: Parametros) =>
      Number(p.n) === 1
        ? "1 hand correction couldn't find its segment in this transcript (the audio was split differently). Its text was not lost: it is saved in the meeting file, and comes back on its own if a future reprocessing finds the segment."
        : `${p.n} hand corrections couldn't find their segments in this transcript (the audio was split differently). Their text was not lost: it is saved in the meeting file, and comes back on its own if a future reprocessing finds the segments.`,
    arquivo_sem_turnos: () =>
      "File without the raw turns (made by an older version of the pipeline): dynamics, interruption matrix, events and overlap regions could NOT be recalculated with the corrected names and may be out of date. No values were guessed: the old values were kept as they were.",
  },
};
