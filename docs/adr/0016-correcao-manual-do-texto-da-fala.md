# ADR 0016 — Corrigir o texto de uma fala à mão, guardando o original

- **Data:** 2026-11-10
- **Situação:** aceito

## Contexto

O glossário (`termos.txt`) corrige erros do Whisper por substituição
determinística em todas as reuniões. Ele não serve para erro que só é erro
num lugar: na busca por variações de "Tabela à Vista" (2026-11-10)
apareceram "questão à vista" (10, 21:31), "estão à vista" (13, 19:10), "uma
vista" (13, 19:19), "outra vista" (10, 1:22:57) e "sugestão é vista" (06,
04:53). Ouvidos, eram o termo; mas são frases que existem em português, e
uma regra estragaria texto certo em outras reuniões.

A fala tem marcas ancoradas em posição de caractere dentro de `texto`:
`palavras_divergentes`, `palavras_baixa_confianca`, `palavras_tempo` e as
`lacunas_sem_texto` da reunião. O glossário consegue deslocá-las porque
sabe exatamente o que trocou por o quê; um texto reescrito à mão não diz
onde cada palavra antiga foi parar.

## Decisão

A fala corrigida no Detalhe recebe o texto da pessoa em `texto` e guarda
tudo o que era antes em `edicao_manual` (`texto_original`, `editado_em` e
`marcas_originais`). As marcas de posição saem da fala — ausente é ausente —
e ficam só dentro do registro da edição, para "Voltar ao original"
devolver a fala exatamente como era. A lógica mora em `edicao.py` (raiz),
usada pelo servidor e pelo `run.py`.

Ao reprocessar, cada correção vai para a fala nova com mais tempo em
comum, se metade de cada uma for o mesmo trecho de áudio (o critério do
casamento de clusters). Correção que não casa nunca é descartada: vai para
`edicoes_sem_fala` no `.json`, com um aviso na tela, e volta sozinha se
um reprocessamento futuro achar a fala. O glossário pula fala corrigida,
no `run.py` e ao reaplicar.

## Alternativas descartadas

- **Recalcular as marcas depois da edição** (alinhar o texto novo com o
  antigo palavra por palavra). Daria uma posição plausível para a maioria
  das palavras e uma errada, sem aviso, para as reescritas — uma pista
  pontilhada na palavra errada é pior que nenhuma. Descartado também por
  pedido explícito.
- **Descartar as marcas de vez, sem guardar.** "Desfazer" devolveria o
  texto sem as pistas, faixas e lacunas que a fala tinha: desfazer que não
  desfaz. Guardar custa só bytes no `.json`.
- **Casar a correção pelo índice ou pelo texto ao reprocessar.** O índice
  muda quando a diarização divide o áudio de outro jeito; o texto muda
  quando o Whisper ou o glossário mudam. O tempo é o que identifica o
  trecho de áudio que a pessoa ouviu e corrigiu — a mesma escolha de
  `run.casar_clusters` para a revisão.
- **Perder a correção que não casou** (com aviso). Trabalho humano
  apagado por um reprocessamento é exatamente o que este projeto já evita
  para título, revisão e `reuniao_id`.
- **Uma regra de glossário por reunião.** Resolveria "questão à vista" na
  10 sem tocar as outras, mas casaria todas as ocorrências dentro da
  mesma reunião, inclusive as certas.

## Consequências

- A correção é a palavra final: nem o glossário nem o reprocessamento
  reescrevem por cima. Para voltar a valer o glossário numa fala corrigida,
  é preciso desfazer a correção.
- Fala corrigida não tem pista de atribuição por palavra, faixa de
  sobreposição, lacuna nem a marca "confiança baixa" (a confiança era do
  texto da máquina). `confianca_media` continua no `.json` — o
  `calibrar.py` mede o Whisper, não a pessoa.
- No reprocessamento, `texto_original` vira o texto da máquina da rodada
  nova, já com o glossário: "Voltar ao original" mostra a transcrição
  atual, não a de quando a correção foi feita.
- Correção sem fala correspondente não aparece no transcript, só no aviso;
  a tela ainda não tem onde mostrá-la.
