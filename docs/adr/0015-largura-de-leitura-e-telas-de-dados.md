# ADR 0015 — Largura de leitura é para texto corrido; telas de dados usam o espaço com colunas

- **Data:** 2026-09-24
- **Situação:** aceito

## Contexto

Todas as telas tinham um teto fixo: 640px (transcript, Revisão, Nova
reunião) ou 1040px (`--medida-conteudo`: Reuniões, Pessoas, Perfil). Num
monitor largo, o conteúdo ficava numa coluna estreita no centro e sobrava
espaço vazio dos dois lados. No Detalhe, o resumo da dinâmica ficava
empilhado em cima do transcript e empurrava a leitura para baixo da dobra.

A regra "duas larguras, nunca uma terceira" (`identidade-rec-meet/SKILL.md`)
misturava duas coisas diferentes:

- a **medida de leitura**, que é uma propriedade do texto corrido (linha
  longa demais não se lê) e não depende da janela;
- o **teto das telas de dados** (listas, tabelas, formulários), que só
  existia para a tela não ir de ponta a ponta.

## Decisão

A largura de leitura (640px) vale para **texto corrido** e continua
valendo nele em qualquer janela. Telas de **dados** usam o espaço a mais
com **mais colunas**, nunca esticando linhas de texto.

Três faixas de janela:

- **abaixo de 720px:** celular (ADR 0014);
- **de 720px a 1440px:** o layout de antes, inalterado;
- **acima de 1440px:** container fluido, margem lateral de 48px
  (`--margem-fluida`) e teto de 1680px (`--largura-fluida-max`), com:
  - Reuniões: lista na largura toda, barra de fala maior e uma coluna com
    a dinâmica resumida (quem mais interrompeu, número de disputas);
  - Detalhe: três colunas — fita, transcript em 640px, painel fixo à
    direita com o resumo da dinâmica e o controle de interações;
  - Pessoas: tabela na largura toda, mais espaço para a grade;
  - Nova reunião: os dois passos lado a lado, Transcrever embaixo;
  - Revisão: cartões de cluster em duas colunas;
  - Perfil: Configurações em duas colunas.

## Alternativas descartadas

**Só aumentar o `max-width` de cada tela.** Resolveria o espaço vazio,
mas esticaria linha de texto — título, nome, parágrafo de explicação,
transcript — exatamente o que a medida de leitura existe para impedir.

**Manter o teto de 1040px e centralizar.** É o comportamento que motivou
a mudança: em 2560px, mais da metade da tela vazia, e no Detalhe o resumo
empurrando a leitura para baixo.

**Container fluido sem teto.** Num monitor ultralargo as colunas se
afastariam tanto que a leitura de uma linha da tabela (nome → grade →
última reunião) viraria um movimento de cabeça. 1680px é o teto.

## Consequências

- A regra da skill deixa de ser "duas larguras, nunca uma terceira" e
  passa a ser: **a medida de leitura nunca cresce; o que cresce é o
  número de colunas**, e só acima de 1440px.
- Toda tela nova de dados precisa dizer o que ganha acima de 1440px (uma
  coluna a mais, uma grade), não só um `max-width` maior.
- O Detalhe passa a usar uma grade com áreas nomeadas, com o painel em
  cima até 1440px e à direita acima disso — mesma ordem de DOM nos dois
  layouts, sem duplicar o painel. Quando a reunião tem avisos de versão
  antiga, eles ficam acima do painel (antes o controle de interações vinha
  antes dos avisos).
- As media queries novas usam a sintaxe de intervalo (`width > 1440px`),
  que o build do Vite já gerava para as antigas.
