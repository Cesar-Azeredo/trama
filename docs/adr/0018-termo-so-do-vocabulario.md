# ADR 0018 — Termo pode entrar no vocabulário sem regra no glossário

- **Data:** 2026-11-10
- **Situação:** aceito. Supera em parte o ADR 0017 (só o que acontece com
  descrição de termo sem regra); superado em parte pelo ADR 0021
  (descrição vazia mantém o termo; tirar é "Remover termo").

## Contexto

Pelo ADR 0017, o vocabulário do `.txt` baixado era feito só dos termos das
regras ativas, e a descrição de um termo que nenhuma regra usa era
descartada ao salvar. Na primeira descrição pedida de verdade, isso falhou:
"MQX" (empresa que fornece o servidor) e "Aprovion" (ferramenta de aprovação
de projetos) não têm regra ativa. O Whisper já escreve "MQX" certo em 15 das
31 ocorrências, e a decisão sobre quais variantes viram regra ainda está
aberta. Mesmo assim, a empresa quer que a IA que ler o arquivo saiba o que
os dois são.

## Decisão

Uma linha `#= termo => descrição` define um termo do vocabulário mesmo sem
regra. O vocabulário traz os termos das regras, na ordem do arquivo, e
depois os que só têm descrição. Esvaziar a descrição de um termo sem regra
o tira do vocabulário. Remover a última regra de um termo com descrição não
apaga a descrição: o termo continua no vocabulário.

## Alternativas descartadas

- **Regra de identidade** (`MQX => MQX`). Ela poria o termo no vocabulário,
  mas apareceria na tela como uma correção que não corrige nada, e entraria
  no prompt do Whisper sem ninguém ter decidido isso.
- **Exigir regra antes da descrição.** Obriga a decidir uma substituição
  para poder explicar um nome que já sai certo.

## Consequências

- A consequência do ADR 0017 "descrição de um termo que nenhuma regra usa
  mais sai na próxima vez que o glossário é salvo" deixa de valer.
- Na tela, a lista "O que cada termo é" mostra também os termos só do
  vocabulário. A descrição deles se edita ali, mas ainda não dá para
  acrescentar um termo novo sem regra pela tela; por enquanto, isso se faz
  com uma linha `#=` no `termos.txt`.
- Os termos só do vocabulário não vão para o prompt do Whisper
  (`termos.prompt_whisper`, que usa o lado certo das regras ativas).
