# ADR 0007 — Revisão grava em 4 fases: prepara arquivos, banco, confirma

- **Data:** 2026-09-18
- **Situação:** aceito

## Contexto

`POST /api/reunioes/{id}/revisao` (marco 1 etapa 6, ADR 0004) é a única
rota do app que escreve no `vozes.db`. O pedido original era: escreva
cada arquivo (`.txt` e `.json`) num temporário e renomeie por cima — o
mesmo padrão que `core.escrever_atomico` já usava.

Isso protege CADA arquivo individualmente contra ficar pela metade, mas
não decide a ORDEM entre gravar o banco e gravar os arquivos. A ordem que
já existia em `review.py` (CLI) grava no banco primeiro, arquivos depois
— decisão deliberada: `core.registrar_contribuicoes` é idempotente por
`(reuniao_id, cluster)`, então se a escrita do arquivo falhar depois do
banco já ter confirmado, repetir a revisão com a mesma resposta fecha
tudo sem dobrar peso. É a ordem que os testes de idempotência em
`tests/test_review.py` já validam.

Testando essa ordem para a rota HTTP ficou claro que "banco primeiro"
significa que uma falha especificamente na escrita do `.json` — depois
do banco já ter confirmado — deixa o banco atualizado e os arquivos
desatualizados. Uma inconsistência real, mesmo sendo segura para repetir.
O pedido era mais estrito: nenhuma falha, em qualquer ponto, pode deixar
nem o banco nem os arquivos pela metade.

## Decisão

`review.aplicar_e_gravar()` grava em quatro fases, nesta ordem:

1. Calcula tudo em MEMÓRIA (falas, clusters, dinâmica recalculada, o
   texto do `.txt` e do `.json`) — nada tocado em disco ou banco ainda.
2. PREPARA os dois arquivos em temporário
   (`core.preparar_escrita_atomica`) — grava o conteúdo novo ao lado do
   arquivo real, sem tocar nele. Se isso falhar (disco cheio, por
   exemplo), nem o banco nem os arquivos reais foram tocados.
3. Só agora grava no banco (`core.registrar_contribuicoes`). Se falhar,
   os temporários ficam órfãos (nunca confirmados) e os arquivos reais
   continuam exatamente como estavam.
4. Só com o banco confirmado, troca os temporários pelos arquivos reais
   (`core.confirmar_escrita_atomica`, um `os.replace` por arquivo) — a
   etapa com menor chance de falhar de toda a sequência.

`core.escrever_atomico` (usado por `run.py`, sem nada crítico por perto)
continua sendo a versão de um passo só: prepara e confirma na mesma
chamada.

## Alternativas descartadas

**Banco primeiro, arquivos depois (a ordem original do CLI).** Não
satisfaz "nenhuma falha deixa o banco à frente dos arquivos" — uma falha
na escrita do arquivo, depois do banco já ter confirmado, é exatamente
esse estado. Seguro para repetir (idempotente), mas não é o que foi
pedido.

**Uma transação só, banco e arquivos juntos.** SQLite e sistema de
arquivos não compartilham uma transação de verdade sem um protocolo de
commit em duas fases bem mais complexo do que o tamanho do problema
justifica (um SQLite local, três tabelas). Preparar os arquivos antes do
banco e confirmá-los só depois consegue a mesma garantia prática sem
esse custo.

**`core.registrar_contribuicoes` recebendo a conexão aberta e adiando o
commit.** Mudaria a assinatura de uma função do ledger só para servir a
esta ordem — o pedido explícito era não reimplementar nem mexer no
ledger além do necessário (ver `servidor/revisao.py`).

## Consequências

- Uma falha em qualquer uma das quatro fases nunca deixa nem o banco nem
  os arquivos pela metade — testado simulando falha na fase 2 (banco
  intocado, `test_revisao_falha_ao_preparar_arquivo_nao_toca_o_banco`) e
  na fase 4 (arquivo original intacto, banco já atualizado, retentativa
  idempotente fecha o arquivo,
  `test_revisao_falha_ao_confirmar_arquivo_nao_corrompe_original_e_retentativa_e_segura`).
- `run.py` (saída original do pipeline, sem banco por perto) não precisa
  dessa separação em fases — continua usando `core.escrever_atomico`.
- Qualquer nova escrita que precise coordenar banco + arquivo deve seguir
  o mesmo padrão: preparar os arquivos, só depois confirmar no banco, só
  depois confirmar os arquivos.
