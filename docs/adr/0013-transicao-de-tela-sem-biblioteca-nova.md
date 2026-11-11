# ADR 0013 — Transição entre telas: View Transitions nativa, sem biblioteca

- **Data:** 2026-09-21
- **Situação:** aceito

## Contexto

ADR 0012 decidiu adotar da skill `apple-design` só a parte de resposta e
movimento (springs interrompíveis, feedback no toque, caminho espacial
simétrico), nunca o vocabulário de material. Faltava decidir COMO
implementar a transição entre telas em si — hoje a troca de rota
(`tema/useRota.ts`) é um corte seco: `hashchange` dispara `setRota`, React
desmonta a árvore inteira e monta outra, sem nenhum estado intermediário.

A skill descreve o padrão em termos de springs com física de verdade
(damping, response, velocidade de gesto) — pensado para elementos
arrastáveis (sheet, drawer, cartão que se solta). A navegação aqui é
inteiramente por clique (nav de seção, link "voltar", linha da lista) —
nenhuma tela tem gesto de arrastar por trás. Springs com transferência de
velocidade de gesto (§5 da skill) não têm o que transferir quando não há
gesto nenhum.

## Decisão

Usar a **View Transitions API** nativa do navegador
(`document.startViewTransition`), não uma biblioteca de animação/spring
(Motion, React Spring, etc.). Continua **zero dependência de runtime**
além de `react`/`react-dom`, que já existiam.

Mecanismo (`tema/transicaoDeRota.ts`, `estilos/transicoes.css`):

- `.area-conteudo` (limite fixo em volta de todas as telas, sem
  rolagem própria) recebe `view-transition-name: conteudo`. Quem rola é
  outro elemento, `.area-conteudo__rolagem`, na largura inteira — nomear
  um elemento que também rola deixava a transição pendurada, e rolar o
  `<main>` (que tem `max-width` por tela) prendia o rolamento numa coluna
  no centro da janela. `.cabecalho` recebe seu próprio nome e nunca anima — a
  casca fica parada, só o conteúdo se move (identidade-rec-meet/SKILL.md:
  "a interface deve quase desaparecer"). Sem isso, o comportamento padrão
  da API anima a página inteira como uma captura só, arrastando a nav
  junto a cada clique.
  "Nunca anima" quer dizer: a captura antiga do cabeçalho fica escondida
  (`::view-transition-old(cabecalho) { display: none }`) e só a nova
  aparece, sem animação. Desligar a animação dos dois lados não basta —
  as duas capturas ficavam empilhadas e somadas (`mix-blend-mode:
  plus-lighter` padrão), e com o fundo transparente do cabeçalho as duas
  abas apareciam sublinhadas ao mesmo tempo.
- Três tipos de transição, decididos por um mapa estático de
  "profundidade" por rota (`PROFUNDIDADE` em `transicaoDeRota.ts`) contra
  `secaoDaRota()`: **"secao"** (Reuniões ↔ Pessoas ↔ Glossário ↔
  Configurações — crossfade sem direção, são lugares diferentes, não
  profundidades diferentes), **"avancar"** e **"voltar"** (hierarquia
  dentro de Reuniões — entram/saem em direções opostas, espelhando o
  mesmo caminho, princípio 7 da skill).
- `prefers-reduced-motion` e falta de suporte no navegador (Safari mais
  antigo) caem no MESMO caminho: `startViewTransition` simplesmente não é
  chamado, e a troca de rota volta a ser o corte seco de sempre. Nunca
  uma segunda implementação "modo reduzido" para manter.

## Alternativas descartadas

**Instalar uma biblioteca de spring (Motion/Framer Motion, React
Spring).** É o que a skill cita como referência web. Descartada por dois
motivos: (1) o app tem zero dependência de UI/motion hoje — CLAUDE.md já
trata cada dependência nova como decisão a registrar, e aqui a View
Transitions nativa faz o mesmo trabalho sem nenhuma; (2) a maquinaria mais
sofisticada de uma lib de spring (transferência de velocidade de gesto,
projeção de momentum) resolve um problema — interromper e redirecionar um
elemento arrastado — que não existe nesta navegação, cem por cento por
clique.

**Manter React montado nos dois lados (manter tela antiga + nova
simultâneas com CSS transition própria, sem View Transitions).**
Descartada por reimplementar à mão exatamente o que a API do navegador já
resolve — capturar o estado antigo, montar o novo, animar entre os dois —
com mais código e mais chance de vazar estado (dois `useEffect` de fetch
rodando ao mesmo tempo, por exemplo).

**Curva de easing custom por tipo de transição (spring simulado em JS).**
Descartada por enquanto: `cubic-bezier(0.32, 0.72, 0, 1)` (aproximação
comum de decaimento criticamente amortecido, sem overshoot) cobre o
princípio de "damping 1.0" da skill para transição disparada por clique,
sem precisar rodar física de mola a cada frame.

## Consequências

- Nenhuma dependência nova em `package.json`.
- Degrada sozinho: Safari antigo ou `prefers-reduced-motion` voltam ao
  corte seco original, nunca quebram.
- Se algum dia existir uma interação de arrastar de verdade (ex.:
  reordenar Glossário), ESSA é a hora de reabrir a discussão de uma
  biblioteca de spring — este ADR cobre só transição de tela por clique.
