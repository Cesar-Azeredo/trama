# ADR 0004 — Servidor FastAPI local, no mesmo repositório

- **Data:** 2026-09-16
- **Situação:** aceito

## Contexto

O frontend precisa ler os `.json`, tocar trechos do `.m4a` e escrever no
`vozes.db`. Navegador não alcança o disco, e a revisão é código Python.

Existiu um protótipo de frontend feito por um modelo local, em outra conta
do GitHub. Foi descartado por inconsistência entre tipos, camada de dados e
telas.

## Decisão

FastAPI local escutando em `127.0.0.1`, importando os módulos que já existem
(`run.py`, `core.py`, `review.py`), dentro do mesmo repositório, em
`frontend/` e `servidor/`.

## Alternativas descartadas

**Ler os `.json` direto no navegador.** Não alcança o áudio nem o banco.

**Repositório separado para o frontend.** O `.json` é o contrato e ainda vai
mudar muito. No mesmo repositório, uma mudança no `run.py` e a mudança
correspondente na tela entram no mesmo commit. Separar depois é fácil.

**Reaproveitar o protótipo antigo.** A base visual era aproveitável, mas a
direção visual mudou (ADR 0005) e a arquitetura de dados também.

**Electron ou Tauri.** Empacotamento é problema de distribuição, não de
construção. Decidir depois, quando houver o que distribuir.

## Consequências

- O servidor é casca fina: nenhuma lógica de pipeline reimplementada.
- Bind em `127.0.0.1` é requisito de segurança, não preferência.
- O marco 2 (executar o pipeline) acrescenta uma rota e uma tela; não muda
  a arquitetura.
