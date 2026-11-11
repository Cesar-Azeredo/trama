# ADR 0017 — Descrição de termo guardada no termos.txt, como comentário marcado

- **Data:** 2026-11-10
- **Situação:** aceito; superado em parte pelo ADR 0018 (descrição de termo sem regra)

## Contexto

O `.txt` baixado ganhou, no fim, o "Vocabulário desta empresa": os termos
do glossário, para a IA que ler o arquivo interpretar o que o Whisper
errou. Uma lista de palavras soltas não diz o que "Tabela à Vista" é; uma
descrição curta por termo ("painel de métricas do gestor") diz.

A descrição tinha de ficar junto do `termos.txt`, sem quebrar o formato
`errado => certo` que o `run.py` lê, e sem mudar as linhas que já existem.
Várias regras levam ao mesmo termo (14 para "ChatGPT"), e as regras de
concordância põem artigo no lado certo ("da Tabela à Vista").

## Decisão

As descrições ficam numa seção no fim do próprio `termos.txt`, uma por
linha, no formato `#= termo => descrição`. Para o `termos.carregar`, linha
começada por `#` é comentário: o `run.py` não muda nada. A seção é a única
parte que a tela reescreve; sem nenhuma descrição, ela não existe e o
arquivo fica exatamente como era.

A descrição é do **termo**, não da regra: o lado certo sem a palavra de
ligação do começo (`o`, `da`, `na`...), sem repetição.
"da Tabela à Vista", "na Tabela à Vista" e "Tabela à Vista" são um termo
só, com um campo só.

## Alternativas descartadas

- **Descrição na mesma linha da regra** (`errado => certo # descrição`).
  O `termos.carregar` leria `certo # descrição` como o texto da
  substituição e escreveria o comentário dentro do transcript. Quebra o
  formato.
- **Arquivo separado** (`termos_descricoes.json`). Funciona, mas são dois
  arquivos que precisam andar juntos (copiar o glossário para outra máquina
  e esquecer um perde as descrições), e um termo renomeado no
  `termos.txt` à mão deixa a descrição órfã num arquivo que ninguém olha.
- **Descrição por regra.** Catorze campos para "ChatGPT", com o mesmo
  texto, e a dúvida de qual vale quando divergem.
- **Lado certo literal no vocabulário.** Fica "da Tabela à Vista", "na
  Tabela à Vista" e "Tabela à Vista" como se fossem três coisas, e "o
  Claude" em vez de "Claude".

## Consequências

- Uma linha que alguém escreva à mão começando com `#= ` é lida como
  descrição, não como comentário comum.
- Termo que só existe dentro de uma regra de contexto continua como frase
  ("extensao do Claude"): tirar só a palavra de ligação do começo não
  separa o termo do contexto.
- Descrição de um termo que nenhuma regra usa mais sai na próxima vez que
  o glossário é salvo pela tela.
- A lista de palavras de ligação existe em dois lugares
  (`servidor/glossario.py` e `Glossario.tsx`) e tem de mudar junto.
