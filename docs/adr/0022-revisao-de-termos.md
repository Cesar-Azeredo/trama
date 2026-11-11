# ADR 0022 — Revisão de termos depois das vozes, sem IA e com memória

- **Data:** 2026-11-10
- **Situação:** aceito

## Contexto

Os termos errados de uma reunião (siglas, nomes de produto) só eram
encontrados se alguém lesse o transcript inteiro. A revisão já para a
pessoa uma vez por reunião, para as vozes: é o momento natural de apontar
também os termos — se a lista for curta. Uma etapa que pede trinta
respostas vira trabalho, e a pessoa passa a pular.

O critério literal ("palavras em `palavras_baixa_confianca` que se repetem,
mais siglas") foi medido nas 13 reuniões reais antes de implementar: 24 a
115 itens por reunião, quase todos "e", "o", "eu", "que", "então". O
Whisper marca baixa confiança em palavra curta o tempo todo.

## Decisão

Depois de "Salvar revisão" (vozes gravadas), a etapa "Termos para
conferir" (`servidor/conferir.py`):

- **Siglas:** 2 a 5 letras maiúsculas.
- **Dúvidas repetidas:** palavra de 4 letras ou mais, marcada em
  `palavras_baixa_confianca` 2 vezes ou mais nesta reunião, em pelo menos
  metade das vezes em que aparece aqui, e presente em no máximo 4
  reuniões (palavra comum aparece em todas).
- **Fora sempre:** nomes da galeria, termos da empresa (e cada palavra
  deles), formas que já têm correção, formas já respondidas.
- **No máximo 10, os mais frequentes primeiro.** Sem nenhum, a etapa não
  aparece.
- **Cada item** toca o trecho (a palavra com 3 s de folga, dentro da fala)
  e tem três respostas: "Está certo" (vira termo da empresa, com descrição
  opcional), "Corrigir para…" (o painel do ADR 0019, com alcance) e
  "Ignorar". Nenhuma é obrigatória.
- **Memória nos termos da empresa:** "Está certo" vira termo conhecido
  (`#= forma`); corrigir em todas vira correção; "Ignorar" e corrigir só
  naquela fala viram `#! forma` no fim do `termos.txt`, comentário para o
  `run.py`. Nada respondido volta, nesta reunião nem nas próximas.

Medido com memória, processando as reuniões em ordem: 2 a 10 itens por
reunião. A primeira revisada é a mais pesada (IA, CRM, API, TI aparecem
uma vez e somem), aceito como o custo de construir a memória.

## Alternativas descartadas

- **O critério literal.** 24 a 115 itens, quase todos palavra comum.
- **Um dicionário de português para tirar as comuns.** Teria de vir de
  fora (CLAUDE.md, regra 1); a frequência entre as reuniões já resolve.
- **Memória num arquivo separado, ou no `.json` de cada reunião.** "Nunca
  perguntar de novo, nem nas próximas" é sobre a empresa, não sobre a
  reunião; e o vocabulário dela já mora no `termos.txt`.
- **Mostrar todos e paginar.** A etapa só ajuda se for curta.

## Consequências

- Palavra errada que o Whisper escreveu com confiança, e que não é sigla,
  não aparece aqui ("Aprovium" sem marca de dúvida). Ela se corrige pelo
  texto, e as variações parecidas (ADR 0020) pegam as irmãs.
- Ainda não há tela para desfazer um "Ignorar": hoje, só tirando a linha
  `#!` do `termos.txt`.
- Uma falha ao buscar os termos nunca prende a pessoa na revisão: as vozes
  já estão gravadas, e o botão leva à reunião.
