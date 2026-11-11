# ADR 0024 — Código visível sob PolyForm Noncommercial 1.0.0

- **Data:** 2026-11-11
- **Situação:** aceito

## Contexto

O projeto vai virar um repositório público de portfólio, e o produto vai
ser vendido a empresas. As duas coisas puxam para lados opostos: o código
precisa ficar visível para quem avalia o trabalho, mas o uso comercial
precisa continuar sendo do autor, que pode licenciá-lo à parte.

## Decisão

O código do projeto sai sob a **PolyForm Noncommercial 1.0.0**, com
`Required Notice: Copyright 2026 Cesar Azeredo` no topo do `LICENSE`. Uso
comercial exige licença separada. A licença cobre só o código deste
repositório: modelos e bibliotecas de terceiros seguem as próprias
licenças, listadas em `ATRIBUICAO.md`.

## Alternativas descartadas

- **Sem licença (todos os direitos reservados).** Simples e suficiente
  para ler no GitHub, mas ninguém pode rodar nem estudar o código
  legalmente. Para portfólio, rodar a demonstração é parte do valor.
- **PolyForm Strict.** Proíbe também modificar e redistribuir; fecha mais
  do que o necessário para proteger o uso comercial.
- **Business Source License 1.1.** Vira código aberto numa data futura
  obrigatória. Não há intenção de abrir o código, e a restrição é sobre
  "produção", não sobre uso comercial.
- **Creative Commons BY-NC.** A própria Creative Commons desaconselha CC
  para software.
- **Elastic License 2.0.** Permite uso comercial interno; só proíbe
  oferecer como serviço gerenciado. Não protege a venda do produto.

## Consequências

- Não é "open source" pela definição da OSI; o README diz
  "source-available".
- Contribuição externa, se houver, precisa de acordo explícito de cessão
  para o autor continuar podendo licenciar comercialmente.
- O `pyproject.toml` declara a licença por identificador SPDX
  (`PolyForm-Noncommercial-1.0.0`).
