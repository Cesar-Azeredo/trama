/**
 * Erros e avisos do servidor, por codigo (trama/erros.py). O servidor manda
 * {codigo, parametros}; o texto mora aqui. tests/test_codigos_de_erro.py
 * (Python) confere que todo codigo que o servidor usa existe neste arquivo
 * e no en/erros.ts.
 */
export type Parametros = Record<string, string | number>;

const CAMPO_GLOSSARIO: Record<string, string> = {
  errado: "o termo errado",
  certo: "o termo certo",
  comentario: "o comentário",
};
const CAMPO_CORRECAO: Record<string, string> = { trecho: "O trecho", certo: "O certo" };
const REAPLICAR = 'Use "Aplicar às reuniões já processadas" em Termos da empresa para terminar.';

export const erros = {
  // cliente (sem codigo do servidor)
  servidorDesatualizado: "O servidor está desatualizado. Reinicie o servidor e recarregue a página.",
  dadosRecusados: "O servidor recusou os dados enviados. Recarregue a página e tente de novo.",
  falhaComServidor: (status: number) => `Falha ao falar com o servidor (${status}).`,
  falhaDeRedeNoEnvio: "Falha de rede ao enviar o áudio.",
  codigoDesconhecido: (codigo: string) => `Erro do servidor (${codigo}).`,

  porCodigo: {
    intervalo_invalido: () =>
      "Intervalo inválido: 'fim' tem que ser maior que 'inicio', e 'inicio' não pode ser negativo.",
    trecho_longo_demais: (p: Parametros) =>
      `Trecho de ${p.pedido}s pedido; o máximo para revisão é ${p.maximo}s.`,
    sem_audio_na_demonstracao: () => "Áudio não disponível na demonstração.",
    sem_transcricao_para_baixar: () =>
      "Esta reunião ainda não foi processada - não há transcrição para baixar.",
    busca_longa_demais: (p: Parametros) => `A busca passa de ${p.maximo} caracteres.`,
    nome_invalido: () => "Nome inválido.",
    sem_clusters_para_revisar: () =>
      "Esta reunião ainda não foi processada - não há grupos de voz para revisar.",
    falha_salvar_audio: () => "Não foi possível salvar o áudio enviado.",
    id_invalido: () => "Id de reunião inválido.",
    reuniao_nao_encontrada: () => "Reunião não encontrada.",
    sem_audio_para_processar: () => "Nenhum áudio encontrado para esta reunião.",
    ja_processando: (p: Parametros) =>
      `Já existe uma reunião sendo processada (${p.id}). Espere terminar antes de iniciar outra.`,
    nada_para_cancelar: () => "Esta reunião não está sendo processada agora.",
    audio_nao_encontrado: () => "Arquivo de áudio não encontrado para esta reunião.",
    falha_recortar_audio: () => "Não foi possível recortar o áudio.",
    fala_mudou: () =>
      "A transcrição mudou desde que a página foi aberta (a reunião foi reprocessada). Recarregue a página e corrija de novo.",
    falha_gravar_correcao_fala: () =>
      "Não foi possível gravar a correção. O texto anterior continua - tente de novo.",
    falha_gravar_titulo: () => "Não foi possível gravar o título. O anterior continua - tente de novo.",
    trecho_mudou: () =>
      "Este trecho mudou desde que a página foi aberta (a reunião foi reprocessada ou a fala foi corrigida). Recarregue a página.",
    falha_gravar_trecho: () => "Não foi possível gravar. Nada mudou - tente de novo.",
    pessoa_nao_encontrada: () => "Esta pessoa não está na galeria.",
    falha_excluir_pessoa: () => "Não foi possível excluir o perfil. Nada foi apagado - tente de novo.",
    falha_gravar_revisao: () =>
      "Não foi possível gravar a revisão. A operação é segura para repetir - tente de novo.",
    falha_gravar_glossario: () =>
      "Não foi possível gravar o glossário. O arquivo anterior continua intacto - tente de novo.",
    falha_gravar_termos: () => "Não foi possível gravar. Os termos continuam como estavam - tente de novo.",
    falha_gravar_resposta: () => "Não foi possível gravar a resposta. Tente de novo.",
    falha_gravar_descricao: () => "Não foi possível gravar a descrição. Tente de novo.",
    mudou_desde_conferencia: () =>
      "Alguma reunião mudou desde a conferência. Confira de novo antes de corrigir.",
    correcao_parcial: (p: Parametros) =>
      `A correção vale para as próximas reuniões, mas não foi aplicada a todas as já processadas (${p.corrigidas} corrigidas). ${REAPLICAR}`,
    falha_gravar_correcao: () => "Não foi possível gravar a correção. Nada foi trocado - tente de novo.",
    mudou_desde_sugestao: () =>
      "Alguma reunião mudou desde a sugestão. Corrija de novo para ver as sugestões atualizadas.",
    correcoes_parciais: (p: Parametros) =>
      `As correções valem para as próximas reuniões, mas não foram aplicadas a todas as já processadas (${p.corrigidas} corrigidas). ${REAPLICAR}`,
    falha_gravar_correcoes: () => "Não foi possível gravar as correções. Nada foi trocado - tente de novo.",
    mudou_desde_previa: () =>
      "O glossário ou alguma reunião mudou desde a prévia. Confira a prévia de novo antes de aplicar.",
    falha_reaplicar: (p: Parametros) =>
      `Não foi possível terminar de aplicar o glossário. Já aplicadas: ${p.feitas}. As outras continuam como estavam - pode tentar de novo.`,
    // upload
    extensao_invalida: (p: Parametros) => `Extensão não suportada. Use um dos formatos: ${p.formatos}.`,
    arquivo_grande_demais: (p: Parametros) => `Arquivo maior que o limite de ${p.maximo_mb} MB.`,
    // correcao de termo
    selecione_trecho: () => "Selecione o trecho que está errado.",
    escreva_certo: () => "Escreva como é o certo.",
    correcao_longa_demais: (p: Parametros) =>
      `${CAMPO_CORRECAO[p.campo] ?? p.campo} passa de ${p.maximo} caracteres.`,
    correcao_com_seta: () => "O texto não pode conter =>.",
    trecho_com_cerquilha: () => "O trecho não pode começar com #.",
    trecho_ja_certo: () => "O trecho já está escrito assim.",
    selecione_palavra: () => "Selecione pelo menos uma palavra.",
    marque_pelo_menos_uma: () => "Marque pelo menos uma.",
    // titulo, fala, nome
    titulo_nao_texto: () => "O título precisa ser texto.",
    titulo_com_controle: () =>
      "O título tem um caractere de controle (quebra de linha, tabulação...), que não é permitido.",
    titulo_longo_demais: (p: Parametros) =>
      `O título tem ${p.tamanho} caracteres; o máximo é ${p.maximo}.`,
    fala_vazia: () =>
      'O texto da fala não pode ficar vazio. Para voltar ao texto transcrito, use "Voltar ao original".',
    fala_com_controle: () => "O texto não pode ter quebra de linha nem caractere de controle.",
    fala_longa_demais: (p: Parametros) => `O texto tem ${p.tamanho} caracteres; o máximo é ${p.maximo}.`,
    nome_longo_demais: (p: Parametros) => `Nome tem ${p.tamanho} caracteres; o máximo é ${p.maximo}.`,
    nome_com_controle: () => "Nome contém caractere de controle, não permitido.",
    // glossario
    forma_invalida: () => "Forma inválida.",
    linha_nao_texto: (p: Parametros) =>
      `Linha ${p.linha}: ${CAMPO_GLOSSARIO[p.campo] ?? p.campo} precisa ser texto.`,
    linha_com_quebra: (p: Parametros) =>
      `Linha ${p.linha}: ${CAMPO_GLOSSARIO[p.campo] ?? p.campo} não pode ter quebra de linha.`,
    linha_longa_demais: (p: Parametros) =>
      `Linha ${p.linha}: ${CAMPO_GLOSSARIO[p.campo] ?? p.campo} passa de ${p.maximo} caracteres.`,
    linha_formato_invalido: (p: Parametros) => `Linha ${p.linha}: formato inválido.`,
    errado_vazio: (p: Parametros) => `Linha ${p.linha}: o termo errado não pode ficar vazio.`,
    errado_com_cerquilha: (p: Parametros) =>
      `Linha ${p.linha}: o termo errado não pode começar com # (a linha viraria comentário).`,
    errado_com_seta: (p: Parametros) => `Linha ${p.linha}: o termo errado não pode conter =>.`,
    comentario_com_seta: (p: Parametros) => `Linha ${p.linha}: comentário com => seria lido como regra.`,
    linha_tipo_desconhecido: (p: Parametros) => `Linha ${p.linha}: tipo desconhecido.`,
    descricoes_formato_invalido: () => "Formato inválido das descrições.",
    descricao_nao_texto: (p: Parametros) => `A descrição de ${p.termo} precisa ser texto.`,
    descricao_sem_termo: () => "Uma descrição ficou sem o termo.",
    termo_invalido: (p: Parametros) =>
      `O termo ${p.termo} não pode ter quebra de linha nem passar de ${p.maximo} caracteres.`,
    termo_repetido: (p: Parametros) => `O termo ${p.termo} aparece duas vezes.`,
    descricao_com_quebra: (p: Parametros) => `A descrição de ${p.termo} não pode ter quebra de linha.`,
    descricao_longa_demais: (p: Parametros) =>
      `A descrição de ${p.termo} passa de ${p.maximo} caracteres.`,
    termo_com_seta: (p: Parametros) => `O termo ${p.termo} tem => e não pode receber descrição.`,
    glossario_formato_invalido: () => "Formato inválido.",
    glossario_longo_demais: (p: Parametros) => `O glossário passa de ${p.maximo} linhas.`,
    termo_vazio: () => "O termo não pode ficar vazio.",
    escreva_nome_do_termo: () => "Escreva o nome do termo.",
    // processamento
    motivo_ja_processando: () =>
      "Esta reunião está sendo processada agora.",
    motivo_interrompida: () =>
      "O processamento anterior foi interrompido (o servidor foi reiniciado no meio). O áudio continua salvo - pode tentar de novo.",
    processamento_falhou: () =>
      "O processamento falhou. Verifique o log do servidor para detalhes e tente novamente.",
    // avisos
    correcao_existente_prevalece: (p: Parametros) =>
      `Em parte do texto, a correção já existente de "${p.errado}" para "${p.certo}" vai continuar valendo no lugar desta.`,
    edicoes_sem_fala: (p: Parametros) =>
      `${p.n} correção(ões) feita(s) à mão não encontraram a fala correspondente nesta transcrição (o áudio foi dividido de outro jeito). O texto delas não se perdeu: ficou guardado no arquivo da reunião, e volta sozinho se um reprocessamento futuro achar a fala.`,
    lacunas_sem_lugar: (p: Parametros) =>
      `${p.n} texto(s) escrito(s) à mão num som não transcrito não encontraram o mesmo ponto nesta transcrição. O texto não se perdeu: ficou guardado no arquivo da reunião, e volta sozinho se um reprocessamento futuro achar o trecho.`,
    arquivo_sem_turnos: () =>
      "Arquivo sem os turnos brutos (gerado por uma versão antiga do pipeline): dinâmica, matriz de interrupções, eventos e regiões sobrepostas NÃO puderam ser recalculados com os nomes corrigidos e podem estar desatualizados. Nada foi inventado: os valores antigos foram mantidos como estavam.",
  } as Record<string, (p: Parametros) => string>,
};
