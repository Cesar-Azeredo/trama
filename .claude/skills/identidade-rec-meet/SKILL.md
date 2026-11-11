---
name: identidade-rec-meet
description: Identidade visual do rec-meet (marca Trama) — paleta Trama em modo claro e escuro, tipografia, espaçamento, elementos de assinatura e a lista do que é proibido. Use ao criar ou revisar qualquer tela, componente ou estilo do frontend. Cobre superfície e composição; movimento, gesto e resposta ficam com a skill apple-design.
---

# Identidade visual do rec-meet

> **Marca Trama (ADR 0023).** O produto se chama Trama no que o usuário
> lê; o modo escuro inteiro é **derivado, a validar com o designer**.
>
> - **Papéis de cor:** `--acento` é o Verde (foco, régua da navegação,
>   botão principal, ação em texto). Erro, disputa e ação destrutiva usam
>   `--alerta`, um vermelho funcional que **não é da marca**. O Fio é só
>   fundo (`--destaque-fundo`), com texto em tinta por cima, nunca cor de
>   voz e nunca linha ou texto.
> - **Nenhum texto da interface promete ata** (ADR 0002). A "memória
>   entre reuniões" da marca é a galeria de vozes e os termos da empresa.
> - **Identificador interno não muda de nome:** chaves `rec-meet:*` do
>   `localStorage`, o nome desta skill, `REC_MEET_*`. Só o texto que o
>   usuário lê é "Trama".
> - O kit da marca mora em `docs/marca/`. No git só entram o guia de uso
>   e os SVGs mestres (`kit/01-mestres/`); o resto fica fora pelo `.gitignore`.

A metáfora é **página de transcrição editorial**: entrevista de revista,
script de peça. Não é dashboard, não é app de produtividade. O transcript é
o produto; a interface some em volta dele.

Duas regras resolvem a maioria das dúvidas:

1. **Se o elemento não é conteúdo, ele deve quase desaparecer.**
2. **Estado se comunica por peso e posição, não por etiqueta colorida.**
   Uma reunião completa não precisa de selo dizendo "completa": ela é a que
   está em tinta cheia. A incompleta tem o número apagado. A não processada
   ganha um botão, porque é trabalho pendente, não erro.

---

## Paleta Trama

Linho e Tinta, com o Verde Trama de ação (ADR 0023). As quatro cores da
marca são `#0E5A4A` Verde, `#E3A33B` Fio, `#14201C` Tinta e `#F4F0E6`
Linho; tudo o mais é derivado delas, menos o vermelho de alerta. Os dois
modos são a mesma identidade, não dois temas diferentes.

### Papéis de cor

| Token | Cor | Para quê | Nunca |
|---|---|---|---|
| `--acento` | Verde Trama | foco, régua da navegação, botão principal, ação em texto, estado ativo (play) | erro |
| `--alerta` | vermelho **funcional, fora da marca** | erro, campo inválido, disputa, ação destrutiva | ação comum |
| `--destaque` | Fio | **só fundo**, com texto em tinta por cima: trecho tocando, busca, termo selecionado | cor de voz; linha ou texto no claro (1,93:1 sobre o Linho) |

**O Fio nunca entra cheio sob texto.** O componente usa só
`--destaque-fundo`: o Fio misturado ao `--fundo` (40% no claro, 25% no
escuro — `--opacidade-destaque`), opaco, com o texto do próprio modo por
cima (corpo e tinta a 7:1 nos dois). Onde aparece:

- **trecho tocando** — a classe `.trecho-tocando` (`base.css`) na fala do
  Detalhe, no trecho da Revisão e no contexto do Conferir termos;
- **busca** — o `<mark>` da palavra buscada na Lista;
- **seleção de texto** — `::selection` global (é ela que abre o
  "Corrigir" no transcript).

Dentro do trecho tocando, letra na cor da voz e `--tinta-fraca` não
passam 4,5:1: a pista mostra a voz só no pontilhado (letra em
`--tinta-corpo`), e lacuna e lápis sobem para `--tinta-media` — a mesma
regra da faixa de sobreposição. `test_identidade.py` reprova
`var(--destaque)` cru ou fora de `background`.

O alerta é vermelhão, não carmim: em protanopia o carmim cai a ΔE 3–5 do
Verde, o vermelhão segura acima de 12. Erro precisa parecer erro, e o
ocre já tem outro papel.

**Derivação.** Os tons de tinta são a Tinta misturada ao Linho (em Lab)
até o limiar de cada um; linhas e trilho, o Linho misturado à Tinta.
Cor nova entra pela mesma conta, nunca por olho.

Declare como variáveis CSS em `:root` e redefina no modo escuro. Nunca use
hex solto no componente.

### Modo claro

```css
:root {
  --fundo:        #F4F0E6;  /* Linho */
  --superficie:   #FAF8F4;  /* superfície elevada, cartão de revisão */
  --trilho:       #DBD9CF;  /* fundo de barra e medidor */

  --tinta:        #14201C;  /* Tinta: títulos, números */
  --tinta-corpo:  #1B2723;  /* corpo do transcript */
  --tinta-media:  #36403B;  /* texto de interface, duração */
  --tinta-fraca:  #656B65;  /* rótulos, nomes secundários — 4,80:1 */
  --tinta-tenue:  #797F78;  /* régua, ícone inativo, texto ≥24px — 3,60:1 */
  --tinta-apagada:#838780;  /* número de reunião incompleta, 30px — 3,21:1 */

  --linha:        #D6D4CB;  /* divisória de linha de lista */
  --linha-forte:  #14201C;  /* régua do cabeçalho, 2px */
  --borda:        #C2C2B9;  /* borda de controle secundário */

  --acento:       #0E5A4A;  /* Verde Trama — 7,15:1 */
  --acento-fundo: #164237;  /* hover e ativo */
  --alerta:       #A1331F;  /* vermelhão funcional — 6,13:1 */
  --alerta-fundo: #76311F;  /* hover */
  --destaque:     #E3A33B;  /* Fio — só fundo */
}
```

### Modo escuro

**Todo o escuro é derivado, a validar com o designer** (ADR 0023): o
guia da marca só define o claro. Fundo na Tinta; superfícies são a
Tinta misturada ao Linho; texto é o Linho misturado à Tinta, cada tom no
seu limiar medido sobre a superfície (o pior dos dois fundos).

```css
:root[data-tema="escuro"] {
  --fundo:        #14201C;  /* Tinta */
  --superficie:   #1C2823;
  --trilho:       #2A3530;

  --tinta:        #ECE9DF;  /* Linho, um passo abaixo */
  --tinta-corpo:  #E0DDD4;
  --tinta-media:  #B2B3AB;  /* 7,21:1 */
  --tinta-fraca:  #8F938B;  /* 4,88:1 */
  --tinta-tenue:  #7D837B;  /* 3,92:1 */
  --tinta-apagada:#6F766F;  /* 3,59:1 sobre o --fundo */

  --linha:        #2A3530;
  --linha-forte:  #ECE9DF;
  --borda:        #36403B;

  --acento:       #599D8B;  /* Verde Trama clareado na mesma matiz */
  --acento-fundo: #7DAF9E;
  --alerta:       #E06A4F;
  --alerta-fundo: #E88369;
  --destaque:     #E3A33B;
}
```

O escuro **não** é o claro invertido. O fundo é a Tinta (verde quase
preto), o acento clareia na mesma matiz, e as cores de voz sobem de
luminosidade — senão somem no fundo.

### Cores de falante

Oito cores dessaturadas, de luminosidade parecida, para que ninguém grite
mais alto que os outros — vinho, castanho, oliva, musgo, petróleo, azul,
anil, ameixa. A mesma ordem de matiz nos dois modos: a pessoa tem cor
análoga no claro e no escuro. Derivadas por busca (recozimento sobre
LCh) contra todas as travas abaixo, com croma entre 16 e 38 — abaixo de
16 a voz vira cinza e parece tinta; acima, grita. Atribuídas pela **ordem de entrada na galeria**: quem chega
entra no fim e ninguém troca de cor (a ordem alfabética, usada antes,
deslocava a cor de todo mundo a cada pessoa nova).

```css
:root {
  --voz-1: #835E62;  --voz-2: #744D19;
  --voz-3: #59553B;  --voz-4: #5A7234;
  --voz-5: #3C7384;  --voz-6: #1A5790;
  --voz-7: #6765A1;  --voz-8: #7C406D;
}
:root[data-tema="escuro"] {
  --voz-1: #CC7C93;  --voz-2: #D0AA9E;
  --voz-3: #97904F;  --voz-4: #9DC17F;
  --voz-5: #43A3C8;  --voz-6: #8FB7FA;
  --voz-7: #888EAC;  --voz-8: #CCABD5;
}
```

**Contraste contra o fundo não basta.** A paleta anterior passava 4,5:1 e
ainda assim tinha pares indistinguíveis numa barrinha de 3 px (voz-1 e
voz-7 a ΔE2000 8,1; em deuteranopia, voz-4 e voz-5 a 1,6). Toda cor de voz
nova precisa passar, nos dois modos, o que `tests/test_paleta.py` trava:

- ΔE2000 ≥ 14 entre quaisquer duas vozes (hoje: 14,6 no claro, 15,4 no
  escuro);
- ΔE2000 ≥ 6 entre quaisquer duas simulando deuteranopia e protanopia
  (hoje: 6,7 no claro, 6,2 no escuro; na paleta de 2026-09, 1,1);
- ΔE2000 ≥ 18 de cada papel de cor — `--acento`, `--alerta` e
  `--destaque`: uma pessoa nunca pode parecer ação, erro ou destaque — e
  ≥ 12 do `--tinta-tenue`, o tom de desconhecido;
- 4,5:1 contra `--fundo` e `--superficie` (o nome do falante é texto de
  11 px).

Oito cores dessaturadas e de mesma luminosidade têm teto: acima de ~15 de
distância mínima, só abrindo mão de "dessaturado" ou de "mesma
luminosidade". Com três papéis reservados, o claro fica no limite: uma
nona voz provavelmente não cabe. A voz-5 do escuro foi baixada a croma
32 para não virar ciano vivo (azul saturado é proibido), ao custo de
margem no daltonismo (6,2 contra 7,4). Por isso a cor nunca carrega o significado sozinha — o
nome vem sempre escrito ao lado.

**Sobreposição no texto.** Com "Mostrar interações" ligado, o trecho de
uma fala dito enquanto outra pessoa falava junto ganha fundo na cor
dessa outra pessoa a 20% (`--opacidade-sobreposicao`). É a única cor de
fundo no transcript, e só texto em `--tinta-corpo` fica em cima dela: a
letra colorida de uma pista não passa 4,5:1 sobre a faixa, então dentro
dela a pista mostra a cor só no pontilhado.

Voz sem pessoa (`DESCONHECIDO_*`, ainda não identificada, ou `IGNORADO_*`,
ignorada na revisão) nunca aparece com o rótulo de máquina: é **"voz não
atribuída"**, em minúsculas e peso normal — numerada ("voz não atribuída
1", "2") só quando a reunião tem mais de uma. Nas marcas que não são
texto (fita de tempo, barra de fala) ela é `--tinta-tenue`; como texto
(margem do transcript, marca de evento), `--tinta-fraca`, porque o tenue
não passa 4,5:1 em 11 px.

### Escolha do modo

Três opções: seguir o sistema operacional (`prefers-color-scheme`, o
padrão), claro ou escuro. A escolha mora em **Perfil › Configurações ›
Aparência**, não no cabeçalho: o cabeçalho é só navegação, e a
aparência é trocada raramente, não a cada visita. "Seguir o sistema" é
a ausência de escolha salva, e continua acompanhando o sistema em tempo
real.

A preferência de tema e o perfil local (nome de quem usa e, se quiser,
qual pessoa da galeria é ela) ficam em `localStorage`. São as únicas
coisas que o app guarda no navegador, e nenhuma delas é dado de
reunião.

---

## Tipografia

Três famílias, empacotadas em `.woff2` no repositório. **Nunca** Google
Fonts por CDN nem `system-ui` — o app roda offline e a mesma tela não pode
mudar de cara entre macOS e Windows.

| Papel | Família | Onde |
|---|---|---|
| Corpo do transcript | **Literata** | a fala das pessoas, títulos |
| Interface | **Figtree** | botões, rótulos, nomes |
| Números | **IBM Plex Mono** | timestamps, duração, similaridade |

A Figtree é a sugestão do guia da marca Trama (ADR 0023), só na
interface: Semibold (600) para destaque, Regular (400) para o resto. O
guia não fala do transcript nem dos números, e eles continuam como
estavam. A alternativa `system-ui` do guia **não** vale (ADR 0005). O
subset latin não tem as setas ← → (caem na fonte do sistema); em texto
novo, prefira ícone SVG de traço a seta digitada.

Cada `.woff2` leva o `OFL-*.txt` da família em `frontend/public/licencas/`
(obrigação da licença), travado em `tests/test_identidade.py`.

Todo número que o usuário compara entre linhas leva
`font-variant-numeric: tabular-nums`.

### Escala

| Uso | Tamanho | Entrelinha | Tracking |
|---|---|---|---|
| Número da reunião | 30 px Plex Mono 400 | 1 | 0 |
| Título de tela | 34 px Literata 600 | 1.1 | −0.02em |
| Título de linha | 19 px Literata 600 | 1.2 | −0.01em |
| Corpo do transcript | 16 px Literata 400 | 1.62 | 0 |
| Texto de interface | 13 px Figtree 400 | 1.5 | 0 |
| Metadado de linha | 11.5 px Figtree 400 | 1.4 | 0 |
| Rótulo de seção | 10–11 px Plex Mono 400 | — | +0.14em, caixa alta |
| Nome do falante | 11 px Figtree 600 | — | +0.10em, caixa alta |

Tracking é específico do tamanho: negativo no grande, zero no corpo,
positivo no pequeno. Nunca um valor único para tudo.

Medida do transcript: **640 px**, nunca mais.

### Medida de leitura nunca cresce; o que cresce é o número de colunas

`--medida-leitura` (640 px) é a largura do **texto corrido** — o
transcript — em qualquer janela. Texto longo em linha larga não se lê, e
isso não muda porque o monitor é maior.

Telas de **dados** (Reuniões, Pessoas, Revisão, Perfil, Nova reunião):

- **de 720 a 1440 px de janela:** teto de `--medida-conteudo` (1040 px);
  a Nova reunião e a Revisão, em 640 px;
- **acima de 1440 px:** container fluido, margem de 48 px de cada lado
  (`--margem-fluida`), teto de 1680 px (`--largura-fluida-max`) — e o
  espaço a mais vira **colunas** (a dinâmica ao lado da lista, o painel
  ao lado do transcript, cartões em duas colunas), nunca linha de texto
  mais longa. Ver ADR 0015.

O cabeçalho e a navegação são sempre 100% da largura da janela — é o que
os separa de ser "conteúdo".

Não é sugestão de largura mínima: os 640 px do transcript não são a
largura do app inteiro por acidente de CSS compartilhado — foi exatamente
esse acidente que motivou a régua ficar explícita aqui.

---

## Elementos de assinatura

São três, e eles são o que diferencia este produto de qualquer lista de
arquivos: a marca, que identifica o produto, e dois que não são enfeite —
carregam dado real.

### A marca

O logotipo Trama (ADR 0023): o fio que dá uma volta e segue, mais a
palavra "trama" desenhada à mão, na versão horizontal, inline em
`Marca.tsx` com os caminhos copiados sem alteração do kit
(`docs/marca/kit/01-mestres/`).

- **Tamanho:** 32 px de altura, ~105 px de largura (o guia pede no
  mínimo 96). Largura fixa pela proporção do `viewBox`, nunca esticada.
- **Cor:** `--cor-marca` — Verde Trama sobre o Linho no claro; Linho
  sobre a Tinta no escuro, com o desenho **invertido** do kit (traço ~6%
  mais fino). Nunca `--acento`, nunca cor de voz, nunca Fio.
- **Nunca** digitar "Trama" no lugar do desenho, esticar, girar,
  espelhar, aplicar sombra, contorno ou gradiente.
- **Favicon:** o `favicon.svg` do kit (símbolo pequeno, Verde), sem
  alteração.

A marca não carrega mais as cores das vozes: a barra de tempo de fala e
a fita continuam sendo os elementos de assinatura que mostram dado.

### A barra de tempo de fala (na lista)

Uma faixa horizontal de 5 px em cada linha de reunião, dividida na
proporção de `fala_pct` de cada pessoa, na cor de cada voz. Vem de
`dinamica` no `.json`.

Reunião sem `dinamica` não ganha barra falsa nem barra zerada: ganha uma
linha de 1 px em `--linha` com a legenda `sem dinâmica`. Ausente é ausente.

### A fita de tempo (no detalhe)

Coluna vertical de 30 px representando a reunião inteira, cada turno na cor
de quem falou, vinda de `turnos`. Segmento com altura proporcional à
duração, mínimo 0,14% para não sumir. Disputas marcadas com traço horizontal
de 2 px em `--alerta`, extravasando a largura. Clicável: salta o transcript
para aquele ponto.

---

## Composição

- **Espaçamento em múltiplos de 4.** Entre falas do transcript, 26 px.
  Dentro de um agrupamento, 4 a 22 px.
- **Nome do falante na margem esquerda** do transcript, largura fixa de
  92 px, alinhado à direita, timestamp embaixo. Rubrica de peça.
- **Cabeçalho separado por régua de 2 px** em `--linha-forte`. Linhas de
  lista separadas por 1 px em `--linha`. Essa diferença de peso é o que
  organiza a página.
- **Navegação de seção é texto, nunca aba com fundo.** Nova reunião,
  Reuniões, Pessoas no cabeçalho (Perfil à direita): a seção atual se
  distingue por peso de cor (`--tinta` cheio vs. `--tinta-fraca`) e uma régua de 2 px em `--acento` embaixo do item — mesma
  aplicação da regra 2 deste documento (estado por peso e posição, nunca
  etiqueta colorida). Nunca pílula, nunca fundo, nunca sublinhado colorido
  fora do peso de `--tinta`/`--acento` já definidos.
  Exceção única (ADR 0014): abaixo de 720px a navegação vira uma barra
  de abas fixa embaixo, com ícone de traço + rótulo e material
  translúcido. O rótulo continua escrito e o estado continua sendo cor +
  régua de 2px (em cima da aba). Nenhuma outra superfície herda isso.
- **Raio de borda: 2 px**, só em controle. Superfície é retangular. Única
  exceção: o botão de play, circular de 44 px.
- **Sombra: nenhuma.**
- **Hierarquia por peso e espaço**, não por caixa. Se a solução foi envolver
  em um cartão, provavelmente falta espaço.
- **Alvo de toque: 44 px** de altura mínima em qualquer controle.

---

## Proibido

Cada item é o que faz uma interface parecer gerada, não desenhada.

- `border-radius` maior que 2 px em superfície.
- `box-shadow` de qualquer tipo.
- Gradiente, em qualquer lugar. Inclusive no favicon.
- Inter, Roboto, Arial, Helvetica, `system-ui`, `-apple-system`.
- Cinza azulado (`#F9FAFB`, `#F3F4F6`, a família slate/zinc do Tailwind).
- Azul, verde, vermelho e amarelo saturados, e qualquer verde que não seja
  o `--acento`. Erro usa `--alerta`; sucesso usa tinta, nunca o verde (o
  verde é ação, não "deu certo").
- Fio (`--destaque`) como texto, linha, borda ou cor de voz.
- Texto de interface que promete ata (ADR 0002, ADR 0023).
- Emoji na interface. Ícone é SVG de traço, inline, herdando cor do texto.
- Ícone decorativo. Se não é clicável nem transmite estado, sai. (O ícone da barra de
  abas do celular é funcional, ao lado do rótulo — ADR 0014.)
- Etiqueta colorida para comunicar estado quando peso e posição resolvem.
- Barra lateral colorida à esquerda de cartão.
- Biblioteca de componentes pronta (shadcn/ui, Material, Chakra, Ant).
- Animação de entrada em conteúdo que só está sendo exibido.
- Skeleton pulsante. Durante carga, texto dizendo o que está acontecendo.
- Texto centralizado em bloco com mais de uma linha.
- Caixa alta em frase. Só em rótulo de uma ou duas palavras.
- Qualquer arquivo que sobrou de template (`vite.svg`, `react.svg`,
  `App.css` padrão, o texto de boas-vindas do Vite).

---

## Acessibilidade, verificada no desenho

- Contraste 4.5:1 no texto, 3:1 acima de 24 px, **nos dois modos**. Toda cor
  nova é conferida em claro e em escuro antes de entrar.
- Os três tons fracos de tinta **não são intercambiáveis** — cada um passa
  num limiar diferente e serve só para o que o limiar permite:
  - `--tinta-fraca` passa 4,5:1 — pode em qualquer texto.
  - `--tinta-tenue` passa 3:1 — só em texto de 24 px ou mais, ou em algo
    que não é texto (régua, ícone inativo).
  - `--tinta-apagada` passa 3:1 — só no número de reunião (30 px), travado
    em `tests/test_identidade.py`. Nunca
    em texto corrido, nunca em rótulo, por menor que pareça o texto.
- `<button>`, `<a href>`, `<input>` + `<label>` de verdade. Nunca `onClick`
  em `div` ou `span` — o Tab pula.
- `aria-label` em botão só de ícone, sempre.
- Foco visível: contorno de 2 px em `--acento`, com 2 px de afastamento.
  Nunca `outline: none` sem substituto.
- Cor nunca é o único portador de significado. O falante tem cor **e** nome
  escrito; a barra de fala tem cor **e** a lista de nomes ao lado.
- Navegável por teclado inteira, incluindo os botões de play da revisão.
