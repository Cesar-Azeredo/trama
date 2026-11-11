# ADR 0006 — Migrações de schema versionadas no vozes.db

- **Data:** 2026-09-16
- **Situação:** aceito

## Contexto

O ledger de contribuições introduziu `pessoas_legado` e `contribuicoes` com
uma migração feita à mão, disparada na primeira conexão, com backup de nome
improvisado (`vozes.db.bak-pre-contribuicoes-<timestamp>`).

Funcionou, mas: não há número de versão, não há caminho de volta, não há
como saber em que estado um banco está sem inspecionar tabelas. E o código
que fazia a migração ficou dias apenas na árvore de trabalho, com bancos já
migrados — se a árvore se perdesse, sobraria um banco novo sem código que o
entendesse.

## Decisão

Uma tabela `schema_version` com um inteiro, e arquivos de migração numerados
em `migracoes/NNN_descricao.py`, aplicados em ordem, cada um numa transação,
com backup automático antes da primeira aplicação de cada sessão.

## Alternativas descartadas

**Alembic.** Peso desproporcional para um SQLite local de três tabelas, e
traz SQLAlchemy junto.

**Continuar migrando à mão na conexão.** Foi o que criou o problema.

## Consequências

- A migração já aplicada (o ledger) vira a migração `001`, escrita de forma
  que reconhece um banco que já passou por ela e não refaz nada.
- O backup existente `vozes.db.bak-pre-contribuicoes-20260916T230132Z` é o
  ponto de restauração do estado pré-ledger. Não apagar.
- Todo schema novo (glossário do cliente, retenção, registro de aviso) entra
  como migração numerada.
