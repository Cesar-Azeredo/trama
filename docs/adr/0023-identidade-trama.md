# ADR 0023 — Identidade Trama no lugar da paleta Arquivo, sem mudar a página editorial

- **Data:** 2026-11-10
- **Situação:** aceito. O modo escuro está **derivado, a validar com o
  designer** (ver Decisão, item 5).

## Contexto

Chegou o kit da marca do produto: nome **Trama**, símbolo de um fio que dá
uma volta sobre si mesmo e segue, palavra "trama" desenhada à mão (não é
fonte), quatro cores e uma sugestão de fonte. O kit mora em `docs/marca/`;
no git entram só o guia de uso e os SVGs mestres, o resto (PNG, PDF,
exportações) fica fora pelo `.gitignore`.

| Nome | HEX | Papel no guia da marca |
|---|---|---|
| Verde Trama | `#0E5A4A` | logo, ícone, botões principais |
| Fio (ocre) | `#E3A33B` | destacar falantes, trechos e marcações; nunca texto sobre branco |
| Tinta | `#14201C` | texto, logo escura |
| Linho | `#F4F0E6` | fundo claro, logo invertida |

Medido antes de decidir (WCAG 2.x, as mesmas funções de
`tests/test_paleta.py`):

- Tinta/Linho 14,73; Verde/Linho 7,15; Linho/Verde 7,15 — passam.
- **Fio/Linho 1,93** — não passa nem 3:1 de elemento não textual. Tinta
  sobre Fio, 7,64.
- **Verde/Tinta 2,06** — o Verde Trama não serve de acento no escuro.
- As vozes da paleta Arquivo ficam a ΔE2000 8,9 (voz-5) e 9,9 (voz-4) do
  Verde, no claro, e a 15,1 do Fio (voz-2), no escuro. A trava é 18.
- O guia só define o modo claro, não tem vermelho e sugere `system-ui`
  como alternativa de fonte.

## Decisão

A marca Trama substitui a paleta Arquivo, a marca de quatro barras e a
IBM Plex Sans. A metáfora do ADR 0005 — página de transcrição editorial —
continua.

1. **Nome.** "Trama" em todo texto que o usuário vê. Identificadores
   internos ficam como estão: repositório, pacote, chaves `rec-meet:*` do
   `localStorage`, nome da skill `identidade-rec-meet`, variáveis
   `REC_MEET_*`. Se o nome precisar mudar, só os textos visíveis mudam.
   *(Revisto no ADR 0027: os identificadores internos também viraram
   Trama.)*
2. **Fontes.** Figtree (SIL OFL) na interface, no lugar da IBM Plex Sans.
   Literata no transcript e IBM Plex Mono nos números continuam: a marca
   não fala desses dois papéis. Toda fonte empacotada leva o `OFL.txt`
   dela em `frontend/public/licencas/`. O fallback `system-ui` do guia não
   é adotado (ADR 0005).
3. **Papéis das cores.**
   - **Verde** (`--acento`): foco, régua da navegação, botão principal,
     ação em texto. No escuro, um verde derivado mais claro na mesma
     matiz, porque o Verde Trama dá 2,06:1 sobre a Tinta.
   - **Vermelho funcional** (`--alerta`): erro, disputa e ação destrutiva.
     **Não pertence à paleta da marca** e está documentado como tal: erro
     precisa parecer erro, e o ocre já tem outro papel. O tom é ajustado
     para conversar com o Verde e a Tinta, desde que passe os contrastes.
   - **Fio** (`--destaque`): só fundo de destaque (trecho tocando, busca,
     termo selecionado), sempre com texto em tinta por cima. Nunca cor de
     voz. Nunca linha nem texto no modo claro.
   - **Tinta e Linho**: a escala de tinta e as superfícies claras derivam
     deles. Os três tons fracos são recalculados, cada um no seu limiar
     (4,5:1, 3:1, 3:1).
4. **Vozes.** Oito cores novas, derivadas para conversar com a paleta,
   passando as mesmas travas de antes (ΔE ≥ 14 entre si, ≥ 6 com
   daltonismo simulado, 4,5:1 sobre o fundo) e a ≥ 18 de cada cor
   reservada: acento, alerta e destaque. O `test_paleta.py` passa a
   reservar as três.
5. **Modo escuro: derivado, a validar com o designer.** Fundo a partir da
   Tinta, texto a partir do Linho, acento e vozes clareados. O app já tem
   modo escuro e ele não some enquanto espera a validação. Quando o
   designer aprovar ou mudar, um ADR novo registra.
6. **Marca.** O símbolo e a palavra do kit, em SVG inline, nas cores do
   guia (Verde ou Tinta no claro, Linho no escuro, usando o arquivo
   invertido, que tem o traço mais fino). Ícone e favicon saem do kit.
7. **Narrativa.** Nenhum texto da interface promete ata (ADR 0002). A
   "memória entre reuniões" da marca é a galeria de vozes e os termos da
   empresa, que o produto já tem.

## Alternativas descartadas

**Fio como acento, no lugar do vermelhão.** 1,93:1 sobre o Linho: um
anel de foco ou uma régua em ocre some no modo claro.

**Ocre (Fio, ou um ocre escurecido) para erro e disputa.** Erro precisa
parecer erro. E o ocre já destaca trecho; a mesma cor dizendo "aqui" e
"errado" obrigaria a pessoa a adivinhar.

**Só as quatro cores da marca, sem vermelho.** Sem vermelho, o erro vira
verde (cor de ação) ou tinta (invisível como alerta).

**Figtree em tudo.** O guia sugere a Figtree para a interface; o corpo do
transcript é leitura longa, e a serifa da Literata é o que sustenta a
página editorial. Os números continuam em Plex Mono pelo `tabular-nums` e
pela mesma razão de antes.

**`system-ui` como alternativa.** Já descartado no ADR 0005: a mesma tela
com duas caras, e o cliente é majoritariamente Windows.

**Renomear também os identificadores internos.** O nome ainda pode
mudar. Mudar as chaves do `localStorage` apagaria o tema e o perfil
salvos de quem já usa; mudar o repositório e as variáveis não muda nada
para o usuário.

**Manter a marca de quatro barras nas cores das vozes.** O guia proíbe
mudar as cores da logo e substituir a palavra desenhada por texto
digitado.

**Esperar o designer para mexer no escuro.** O app já tem modo escuro;
deixá-lo com a paleta Arquivo enquanto o claro vira Trama faria os dois
modos parecerem dois produtos.

## Consequências

- Há uma cor fora da marca, o vermelho de alerta, e ela é tratada como
  regra funcional, não exceção estética.
- O escuro carrega o rótulo "a validar". Até lá, quem mexer nele segue a
  derivação descrita na skill.
- A margem das vozes no modo claro é estreita: com Verde e vermelho
  reservados, oito cores escuras o bastante para 4,5:1 chegam perto de
  ΔE 14. Uma nona voz, se um dia existir, provavelmente não cabe.
- A IBM Plex tem Reserved Font Name "Plex". As `.woff2` são subsets
  latinos como os que o próprio Google Fonts distribui com o nome, e a
  Plex Mono continua no app.
- Tokens, fontes e proibições continuam normativos em
  `.claude/skills/identidade-trama/SKILL.md`, reescrita junto com o
  código de cada etapa.
