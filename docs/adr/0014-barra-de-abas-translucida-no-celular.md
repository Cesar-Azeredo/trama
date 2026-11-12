# ADR 0014 — No celular, a navegação é uma barra de abas translúcida com ícone

- **Data:** 2026-09-24
- **Situação:** aceito

## Contexto

Abaixo de ~720px de largura, a nav de texto do cabeçalho não cabe:
"Nova reunião" quebrava em duas linhas e a última aba era empurrada para
fora da tela. Quatro destinos (Nova, Reuniões, Pessoas, Perfil) numa
faixa de ~360px não cabem como texto corrido com o espaçamento da
identidade.

Três regras aceitas colidem com a solução padrão de celular, que é uma
barra de abas fixa embaixo:

1. ADR 0012 — nenhuma superfície do Trama ganha `backdrop-filter`,
   blur ou translucidez.
2. `identidade-trama/SKILL.md`, Composição — "navegação de seção é
   texto, nunca aba com fundo".
3. `identidade-trama/SKILL.md`, Proibido — "ícone decorativo".

Isto é só layout responsivo. O app continua rodando no Mac com o
servidor em `127.0.0.1` (CLAUDE.md, regra 2); abrir pelo celular de
verdade exigiria expor o servidor na rede, o que não foi feito nem é
decidido aqui.

## Decisão

Abaixo de 720px, o cabeçalho mostra só a marca e a navegação vira uma
barra fixa embaixo, com quatro abas de ícone de traço e rótulo, em
material translúcido com desfoque. É a única superfície flutuante do
app, e por isso a única exceção às três regras acima.

- **ADR 0012:** entra fundo semitransparente (`--fundo` a 78%) com
  `backdrop-filter: blur(20px)` e o conteúdo rolando por baixo. Não
  entram sombra (a identidade proíbe em qualquer forma, e esta exceção
  não a cobre), `saturate()` (avivaria as cores de voz, dessaturadas de
  propósito) nem a borda clara "de luz"; a separação continua sendo a
  régua de 1px em `--linha`.
- **"Nav é texto":** o rótulo continua escrito em cada aba, e o estado
  atual continua sendo cor (`--tinta` cheio) mais régua de 2px — só que
  em cima da aba, porque a barra encosta na borda de baixo. Nunca fundo
  nem pílula na aba ativa.
- **"Sem ícone decorativo":** o ícone aqui é funcional. Numa célula de
  ~90px, ele é o que se reconhece de relance sem ler, e continua ao lado
  de um rótulo escrito (cor e forma nunca são o único portador de
  significado). O SVG é `aria-hidden`; o nome acessível é o rótulo.

## Alternativas descartadas

**Barra opaca embaixo.** Resolveria o espaço sem exceção ao ADR 0012,
mas consome uma faixa fixa da tela, e o conteúdo some atrás de uma
parede em vez de continuar visível por baixo. O pedido foi explícito
pelo material translúcido; a barra opaca continua existindo como
fallback (sem suporte a `backdrop-filter`, ou com
`prefers-reduced-transparency`).

**Nav de texto com rolagem horizontal no cabeçalho.** Mantém a regra
"nav é texto" ao pé da letra, mas esconde abas fora da tela, justamente
o defeito que motivou a mudança.

**Menu hambúrguer.** Esconde os quatro destinos atrás de um toque a
mais, para um app com só quatro.

## Consequências

- A exceção é desta barra e só dela. Nenhuma outra superfície ganha
  translucidez, blur ou sombra citando este ADR.
- O conteúdo ganha `padding-bottom` igual à altura da barra
  (`--altura-abas`, incluindo `env(safe-area-inset-bottom)`), e quem
  calcula altura pelo viewport desconta a barra (`FitaDeTempo.css`).
- `index.html` passa a declarar `viewport-fit=cover`; sem isso
  `env(safe-area-inset-bottom)` é sempre 0.
- Na transição de tela, a barra tem nome próprio (`abas`) e o mesmo
  tratamento do cabeçalho: a captura antiga escondida, a nova parada.
  Risco não verificado: a captura da View Transition pode não reproduzir
  o `backdrop-filter`, e a barra ficaria sem desfoque durante os 150ms
  da troca.
