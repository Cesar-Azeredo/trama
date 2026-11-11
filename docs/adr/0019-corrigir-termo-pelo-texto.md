# ADR 0019 — Corrigir um termo selecionando no texto, com a ordem das regras resolvida sozinha

- **Data:** 2026-11-10
- **Situação:** aceito

## Contexto

Até aqui, um termo errado só se corrigia em todas as reuniões editando o
glossário (`errado → certo`) em Perfil, depois apertando "Aplicar às
reuniões já processadas". Isso funcionava para quem conhece o arquivo. O
cliente do app não conhece: ele precisa corrigir sozinho, pela tela, em
segundos, sem saber que existe "regra", "glossário" nem ordem de regras.

As regras rodam na ordem do arquivo. Uma regra mais geral antes de uma mais
específica faz a específica nunca disparar ("tabula da vista" antes de
"do tabula da vista"). Quem mantinha o arquivo sabia disso; quem usa a
tela não deveria precisar saber.

O clique duplo abria a edição da fala inteira (ADR 0016), mas é também o
gesto natural de selecionar uma palavra — justamente o que o fluxo novo
precisa.

## Decisão

- **Selecionar um trecho de uma fala mostra o botão "Corrigir".** O
  painel pede "O certo é", o alcance ("Só nesta fala" ou "Em todas as
  reuniões e nas próximas") e, opcionalmente, "O que é isso?" (a
  descrição do termo no vocabulário do `.txt`). "Em todas" mostra antes
  quantas vezes e onde a troca aconteceria.
- **"Só nesta fala"** é a correção manual de fala que já existe (ADR 0016).
- **"Em todas"** grava a regra `trecho => certo` no `termos.txt` e aplica
  **só ela** nas reuniões já processadas, pela mesma rotina do reaplicar,
  com a mesma assinatura da prévia. Regras salvas e ainda não aplicadas
  não entram de carona.
- **A posição da regra é escolhida pelo servidor**
  (`servidor/correcao.posicionar`): antes da primeira regra que capturaria
  o trecho dela (mais geral), e depois de toda regra que ela capturaria
  (mais específica). Mesmo trecho já com regra: troca o certo no lugar. Só
  quando as duas exigências se contradizem há aviso, e aí a regra fica
  depois das específicas — nada que já funcionava para de funcionar.
- **Clique duplo volta a ser só seleção do navegador.** A edição da fala
  inteira fica no lápis.

## Alternativas descartadas

- **Avisar sobre a ordem e deixar a pessoa resolver.** Quem usa não sabe
  que existe ordem, e não deveria precisar saber (decisão do usuário).
- **Aplicar o glossário inteiro depois da correção.** Trocaria também o que
  estava salvo e ainda não aplicado (as regras de "Tabela à Vista", por
  exemplo), sem a pessoa ter visto.
- **Manter o clique duplo abrindo a edição e usar outro gesto para
  corrigir um termo** (clique com Alt, menu de contexto). Gestos escondidos,
  que ninguém descobre; e o clique duplo continuaria brigando com a
  seleção.
- **Reordenar regras existentes para resolver o conflito.** Mexer na ordem
  de regras que já funcionam muda resultado de reunião que ninguém pediu
  para mudar.

## Consequências

- Pelo teclado, num texto que não é editável, não há como selecionar um
  trecho: "Só nesta fala" continua pelo lápis, e "Em todas" pela tela de
  termos ("adicionar variação").
- O painel nunca fala em "regra" nem em "glossário", inclusive no aviso de
  conflito.
- Se a gravação falhar no meio das reuniões, a correção já vale para as
  próximas; a mensagem manda terminar pelo botão de reaplicar.
