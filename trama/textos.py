"""
textos.py - O que a linha de comando escreve, em portugues e ingles
(trama/idioma.py escolhe). Os dois idiomas tem exatamente as mesmas chaves
(tests/test_idioma.py confere). Parametros entre chaves, preenchidos por
idioma.t(); texto sem parametro nunca passa por format.

Nao entra aqui: log do servidor ("[processamento] ..."), que e para quem
depura, nem a fala das pessoas, que nunca e traduzida.
"""

TEXTOS = {
    "pt": {
        # --- pipeline: etapas (a frase do terminal; o servidor le a linha
        # "@progresso", nunca esta - pipeline._progresso)
        "etapa_1": "1/5  Convertendo áudio para 16 kHz mono...",
        "etapa_2": "2/5  Diarizando (quem falou quando){faixa}...",
        "faixa_exata": " - {n} falantes",
        "faixa_entre": " - entre {min} e {max} falantes",
        "faixa_min": " - pelo menos {min} falantes",
        "faixa_max": " - até {max} falantes",
        "etapa_3": "3/5  Identificando as pessoas pela voz...",
        "etapa_4": "\n4/5  Analisando sobreposição e interrupções...",
        "etapa_5": "\n5/5  Transcrevendo com {asr}{termos}...",
        "etapa_5_termos": " ({n} termos do domínio)",
        # --- pipeline: relatorio no terminal
        "similaridade": "\n  Similaridade cluster x pessoa (cosseno):",
        "dinamica": "\n  Dinâmica da reunião:",
        "colunas_dinamica": "PESSOA|FALA|%|TURNOS|MÉDIA|INTERR.|SOFREU|APOIOS",
        "quem_interrompeu": "\n  Quem interrompeu quem:",
        "disputas": (
            "\n  {n} trecho(s) de disputa ({total}s no total) - é onde a transcrição "
            "fica menos confiável:"
        ),
        "identificacao": "\n  Resultado da identificação:",
        "linha_identificacao": (
            "    {label:<8} -> {nome:<18} sim={sim}  margem={margem}  fala={fala}s"
        ),
        "galeria_vazia": "     (galeria vazia - a saída sai com SPEAKER_XX)",
        "revisao_herdada": (
            "     revisão anterior: {herdados} de {total} clusters herdaram a decisão; "
            "o resto fica a revisar"
        ),
        "lacunas_sem_lugar": (
            "     ! {n} texto(s) escrito(s) em lacuna sem lacuna correspondente nesta "
            "transcrição - guardados em lacunas_sem_lugar no .json"
        ),
        "edicoes_sem_fala": (
            "     ! {n} correção(ões) manual(is) sem fala correspondente nesta "
            "transcrição - guardadas em edicoes_sem_fala no .json"
        ),
        # --- termos.py
        "termos_linha_ignorada": "  ! {caminho}:{n} ignorada (falta '=>'): {linha}",
        "termos_aplicadas": "\n  Correções de vocabulário aplicadas:",
        "termos_muito_alto": "  <- muito alto, confira a regra",
        "termos_sem_uso": "  {n} regra(s) sem uso nesta reunião: {lista}",
        # --- nucleo.py
        "embedding_erro": "      ! erro ao extrair embedding: {erro}",
        "embedding_sem_trecho": "      ! nenhum trecho com duração mínima de {min}s",
        # --- revisao.py
        "reuniao_id_novo": (
            "  ! arquivo antigo sem identificador estável de reunião - atribuído agora "
            "({id}...). Revisões deste arquivo passam a ser idempotentes a partir desta "
            "execução; o que já foi aprendido antes não pode ser reconciliado "
            "retroativamente."
        ),
        # --- trama-processar
        "ajuda_pessoas": "Quem estava na sala: Joao,Maria,Pedro",
        "ajuda_falantes": "Número exato de falantes",
        "ajuda_device": "No Mac, teste os dois: MPS nem sempre é mais rápido",
        "ajuda_idioma_fala": "Idioma da fala, para o Whisper (não o das mensagens: TRAMA_IDIOMA)",
        "ajuda_termos": "Arquivo de vocabulário do domínio (errado => certo)",
        "ajuda_sem_termos": "Desliga a correção de vocabulário",
        "ajuda_out": "Prefixo dos arquivos de saída",
        "pronto": "\nPronto:\n  {txt}\n  {json}",
        "agora_rode": "\nAgora rode:  trama-revisar {json}",
        # --- trama-revisar
        "ajuda_sem_aprender": "Corrige o texto mas não atualiza os perfis de voz",
        "pessoas_cadastradas": "\nPessoas já cadastradas: {lista}",
        "nenhuma": "(nenhuma)",
        "instrucoes_revisao": (
            "\nEnter = aceitar   |   digitar nome = corrigir   |   '-' = ignorar cluster\n"
        ),
        "cluster_sugerido": (
            "  {label}   sugerido: {nome}   sim={sim}  margem={margem}  fala={fala}s"
        ),
        "candidatos": "    candidatos: {lista}",
        "quem_e": "    Quem é? [{nome}] ",
        "efeito_ensina": "ensina {s} s da voz de {pessoa}",
        "efeito_move": "move {s} s da voz de {pessoa} para {para}",
        "efeito_remove": "remove {s} s da voz de {pessoa}",
        "efeito_perfil_some": " - o perfil deixa de existir",
        "muda_voz": "\nIsto muda a voz aprendida:",
        "confirmar": "Confirmar? [s/N] ",
        "resposta_sim": "s",
        "nada_gravado": "Nada foi gravado.",
        "falha_perfis": (
            "\nFalha ao atualizar os perfis de voz: {erro}\n"
            "Nada foi gravado (nem o TXT/JSON corrigidos). O arquivo continua como "
            "antes - rode trama-revisar de novo com as mesmas respostas quando o "
            "problema for resolvido."
        ),
        "atualizando_perfis": "\nAtualizando perfis de voz:",
        "fala_acumulada": "  {nome:<18} fala acumulada: {s}s",
        "sem_turnos": (
            "\n  ! arquivo antigo sem 'turnos' brutos - dinâmica/eventos/matriz/regiões "
            "não foram recalculados (ver dados['avisos'])."
        ),
        "corrigido": "\nCorrigido: {caminho}",
        # --- trama-verificar
        "rotulo_ok": "OK",
        "rotulo_falhou": "FALHOU",
        "rotulo_aviso": "AVISO",
        "secao_sistema": "\n--- Sistema ---",
        "python_antigo": "O trama precisa de Python 3.12 ou mais novo.",
        "ffmpeg_ok": "ffmpeg encontrado",
        "ffmpeg_falta": "ffmpeg não encontrado",
        "ffprobe_ok": "ffprobe encontrado",
        "ffprobe_falta": "ffprobe ausente (o fase0 só perde a checagem de qualidade do áudio)",
        "sem_venv": (
            "Você não está num virtualenv. Recomendado: "
            "python -m venv .venv && source .venv/bin/activate"
        ),
        "secao_pacotes": "\n--- Pacotes Python ---",
        "nao_instalado": "{nome} não instalado",
        "pyannote_antigo": "pyannote.audio {versao} é antigo",
        "pyannote_dica": (
            "O community-1 exige a versão 4 ou superior.\npip install -U 'pyannote.audio>=4.0'"
        ),
        "asr_ok": "{modulo} disponível  (use {flag})",
        "sem_asr": (
            "Nenhum motor de transcrição instalado. O fase0 funciona sem ele; o "
            "trama-processar não."
        ),
        "secao_apple": "\n--- Apple Silicon ---",
        "mps_ok": "MPS disponível (mas teste contra --device cpu antes de confiar)",
        "mps_falta": "MPS indisponível - vai rodar em CPU, o que costuma ser aceitável",
        "secao_token": "\n--- Token Hugging Face ---",
        "token_da_variavel": "variável HF_TOKEN",
        "token_do_cache": "cache do hf auth login",
        "sem_token": "Nenhum token encontrado",
        "sem_token_dica": "export HF_TOKEN=hf_xxxxx     (ou rode: hf auth login)",
        "token_formato": "O token não começa com 'hf_'. Confirme se copiou o valor certo.",
        "token_presente": "Token presente ({origem}, termina em ...{fim})",
        "autenticado": "Autenticado como '{nome}'",
        "token_invalido": "Token inválido ou revogado ({erro})",
        "token_novo": "Crie outro em huggingface.co/settings/tokens",
        "secao_modelos": "\n--- Acesso aos modelos ---",
        "sem_token_modelos": "Sem token, não dá para checar acesso aos modelos.",
        "modelo_diarizacao": "pipeline de diarização",
        "modelo_embedding": "modelo de embedding de voz",
        "acesso_negado": "{repo} - acesso não liberado",
        "acesso_dica": (
            "Abra https://huggingface.co/{repo}\nlogado na MESMA conta do token, e aceite "
            "os termos."
        ),
        "ambiente_pronto": "Ambiente pronto. Próximo passo:\n",
        "resolva": "Resolva os itens marcados como FALHOU antes de continuar.",
        # --- .txt gravado em disco (pipeline.montar_texto_txt)
        "txt_conferir": "<- conferir",
        "txt_vozes_sobrepostas": "[vozes sobrepostas]",
    },
    "en": {
        "etapa_1": "1/5  Converting audio to 16 kHz mono...",
        "etapa_2": "2/5  Diarizing (who spoke when){faixa}...",
        "faixa_exata": " - {n} speakers",
        "faixa_entre": " - between {min} and {max} speakers",
        "faixa_min": " - at least {min} speakers",
        "faixa_max": " - up to {max} speakers",
        "etapa_3": "3/5  Identifying people by voice...",
        "etapa_4": "\n4/5  Analyzing overlap and interruptions...",
        "etapa_5": "\n5/5  Transcribing with {asr}{termos}...",
        "etapa_5_termos": " ({n} domain terms)",
        "similaridade": "\n  Cluster x person similarity (cosine):",
        "dinamica": "\n  Meeting dynamics:",
        "colunas_dinamica": "PERSON|SPEECH|%|TURNS|AVG|INTERR.|WAS INT|BACKCH.",
        "quem_interrompeu": "\n  Who interrupted whom:",
        "disputas": (
            "\n  {n} crosstalk passage(s) ({total}s in total) - where the transcript "
            "is least reliable:"
        ),
        "identificacao": "\n  Identification result:",
        "linha_identificacao": (
            "    {label:<8} -> {nome:<18} sim={sim}  margin={margem}  speech={fala}s"
        ),
        "galeria_vazia": "     (empty gallery - output will use SPEAKER_XX)",
        "revisao_herdada": (
            "     previous review: {herdados} of {total} clusters inherited the decision; "
            "the rest is left to review"
        ),
        "lacunas_sem_lugar": (
            "     ! {n} text(s) written in untranscribed audio with no matching gap in "
            "this transcript - kept in lacunas_sem_lugar in the .json"
        ),
        "edicoes_sem_fala": (
            "     ! {n} hand correction(s) with no matching segment in this transcript "
            "- kept in edicoes_sem_fala in the .json"
        ),
        "termos_linha_ignorada": "  ! {caminho}:{n} ignored (missing '=>'): {linha}",
        "termos_aplicadas": "\n  Vocabulary corrections applied:",
        "termos_muito_alto": "  <- very high, check the rule",
        "termos_sem_uso": "  {n} rule(s) unused in this meeting: {lista}",
        "embedding_erro": "      ! error extracting embedding: {erro}",
        "embedding_sem_trecho": "      ! no segment with the minimum duration of {min}s",
        "reuniao_id_novo": (
            "  ! old file without a stable meeting id - assigned now ({id}...). Reviews "
            "of this file are idempotent from this run on; what was learned before "
            "can't be reconciled retroactively."
        ),
        "ajuda_pessoas": "Who was in the room: Joao,Maria,Pedro",
        "ajuda_falantes": "Exact number of speakers",
        "ajuda_device": "On a Mac, try both: MPS isn't always faster",
        "ajuda_idioma_fala": "Language spoken, for Whisper (not the messages': TRAMA_IDIOMA)",
        "ajuda_termos": "Domain vocabulary file (wrong => right)",
        "ajuda_sem_termos": "Turns off vocabulary correction",
        "ajuda_out": "Prefix of the output files",
        "pronto": "\nDone:\n  {txt}\n  {json}",
        "agora_rode": "\nNow run:  trama-revisar {json}",
        "ajuda_sem_aprender": "Fixes the text but doesn't update the voice profiles",
        "pessoas_cadastradas": "\nPeople already registered: {lista}",
        "nenhuma": "(none)",
        "instrucoes_revisao": (
            "\nEnter = accept   |   type a name = correct   |   '-' = ignore cluster\n"
        ),
        "cluster_sugerido": (
            "  {label}   suggested: {nome}   sim={sim}  margin={margem}  speech={fala}s"
        ),
        "candidatos": "    candidates: {lista}",
        "quem_e": "    Who is it? [{nome}] ",
        "efeito_ensina": "teaches {s} s of {pessoa}'s voice",
        "efeito_move": "moves {s} s of {pessoa}'s voice to {para}",
        "efeito_remove": "removes {s} s of {pessoa}'s voice",
        "efeito_perfil_some": " - the profile ceases to exist",
        "muda_voz": "\nThis changes the learned voice:",
        "confirmar": "Confirm? [y/N] ",
        "resposta_sim": "y",
        "nada_gravado": "Nothing was saved.",
        "falha_perfis": (
            "\nFailed to update the voice profiles: {erro}\n"
            "Nothing was saved (not even the corrected TXT/JSON). The file is as it "
            "was - run trama-revisar again with the same answers once the problem "
            "is solved."
        ),
        "atualizando_perfis": "\nUpdating voice profiles:",
        "fala_acumulada": "  {nome:<18} total speech: {s}s",
        "sem_turnos": (
            "\n  ! old file without raw 'turnos' - dynamics/events/matrix/regions were "
            "not recalculated (see dados['avisos'])."
        ),
        "corrigido": "\nCorrected: {caminho}",
        "rotulo_ok": "OK",
        "rotulo_falhou": "FAILED",
        "rotulo_aviso": "WARNING",
        "secao_sistema": "\n--- System ---",
        "python_antigo": "Trama needs Python 3.12 or newer.",
        "ffmpeg_ok": "ffmpeg found",
        "ffmpeg_falta": "ffmpeg not found",
        "ffprobe_ok": "ffprobe found",
        "ffprobe_falta": "ffprobe missing (fase0 only loses the audio quality check)",
        "sem_venv": (
            "You're not in a virtualenv. Recommended: "
            "python -m venv .venv && source .venv/bin/activate"
        ),
        "secao_pacotes": "\n--- Python packages ---",
        "nao_instalado": "{nome} not installed",
        "pyannote_antigo": "pyannote.audio {versao} is too old",
        "pyannote_dica": (
            "community-1 requires version 4 or newer.\npip install -U 'pyannote.audio>=4.0'"
        ),
        "asr_ok": "{modulo} available  (use {flag})",
        "sem_asr": (
            "No transcription engine installed. fase0 works without one; trama-processar doesn't."
        ),
        "secao_apple": "\n--- Apple Silicon ---",
        "mps_ok": "MPS available (but test against --device cpu before trusting it)",
        "mps_falta": "MPS unavailable - it will run on CPU, which is usually acceptable",
        "secao_token": "\n--- Hugging Face token ---",
        "token_da_variavel": "HF_TOKEN variable",
        "token_do_cache": "hf auth login cache",
        "sem_token": "No token found",
        "sem_token_dica": "export HF_TOKEN=hf_xxxxx     (or run: hf auth login)",
        "token_formato": "The token doesn't start with 'hf_'. Check you copied the right value.",
        "token_presente": "Token present ({origem}, ends in ...{fim})",
        "autenticado": "Authenticated as '{nome}'",
        "token_invalido": "Invalid or revoked token ({erro})",
        "token_novo": "Create another one at huggingface.co/settings/tokens",
        "secao_modelos": "\n--- Model access ---",
        "sem_token_modelos": "Without a token, model access can't be checked.",
        "modelo_diarizacao": "diarization pipeline",
        "modelo_embedding": "voice embedding model",
        "acesso_negado": "{repo} - access not granted",
        "acesso_dica": (
            "Open https://huggingface.co/{repo}\nlogged in to the SAME account as the "
            "token, and accept the terms."
        ),
        "ambiente_pronto": "Environment ready. Next step:\n",
        "resolva": "Fix the items marked FAILED before continuing.",
        "txt_conferir": "<- check",
        "txt_vozes_sobrepostas": "[overlapping voices]",
    },
}
