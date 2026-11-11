# ADR 0012 — Da skill `apple-design`, só movimento e resposta; material fica de fora

- **Data:** 2026-09-20
- **Situação:** aceito — com uma exceção registrada no ADR 0014 (barra de abas no celular)

## Contexto

`identidade-rec-meet/SKILL.md` delega explicitamente "movimento, gesto e
resposta" para a skill `apple-design` desde que foi escrita (ADR 0005). Só
que essa skill ficou **ausente do repositório durante os marcos 1 e 2
inteiros** — a referência apontava para uma pasta que não existia, e
nenhum agente notou nem avisou. Ela foi instalada de verdade só agora
(`npx skills add https://github.com/emilkowalski/skills --skill
apple-design`, conteúdo versionado em `.agents/skills/apple-design/`, ver
`CLAUDE.md`).

Lida pela primeira vez, a skill traz duas famílias de conteúdo bem
diferentes:

1. **Resposta e movimento** — feedback no pointer-down, springs
   interrompíveis (nunca CSS `@keyframes` fixo para gesto), transferência
   de velocidade entre arrastar e animar, projeção de momentum, caminhos
   simétricos de entrada/saída, reduced motion.
2. **Materiais e profundidade** — `backdrop-filter`, camadas translúcidas
   empilhadas, sombra proporcional à "espessura" da superfície, scrims
   para modais.

O item 2 colide de frente com regras já aceitas do produto: `identidade-
rec-meet/SKILL.md` proíbe sombra em qualquer forma, proíbe superfície
flutuante chamando atenção pra si, e resolve hierarquia por peso e posição,
não por camada ("se a solução foi envolver em um cartão, provavelmente
falta espaço" — regra de composição da skill). ADR 0005 já havia rejeitado
a estética de "cartão com sombra suave" como sinal de descuido, justamente
o oposto do que o produto precisa comunicar a um cliente corporativo.

## Decisão

Da skill `apple-design`, o rec-meet adota **só a parte de resposta e
movimento** (seções 1–11 e 14 da skill, na numeração de hoje): feedback
instantâneo no toque, springs interrompíveis para qualquer coisa
arrastável ou clicável, transição entre telas com caminho espacial
simétrico, projeção de momentum, reduced motion.

**Não adota** o vocabulário de material (seção 12: `backdrop-filter`,
translucidez em camada, sombra contextual, scrim). A identidade do
produto não tem superfície flutuante nem hierarquia por profundidade de
camada para esse vocabulário servir — ela já resolve o mesmo problema
(separar o que é estrutural do que é interativo) por peso tipográfico e
posição, que é uma decisão anterior e não está em revisão aqui.

## Alternativas descartadas

**Adotar a skill inteira, incluindo material.** Um cabeçalho com
`backdrop-filter` e conteúdo passando por baixo (o padrão que a skill
recomenda para nav/toolbar) seria exatamente a "superfície chamando
atenção pra si" que a identidade proíbe — mesmo que tecnicamente bonito,
quebraria a metáfora de página editorial que já é decisão tomada.

**Ignorar a skill inteira, ficando só com CSS `transition` simples.**
Descartada porque joga fora justamente o que a skill resolve bem e que o
app hoje não tem nenhum: interruptibilidade. Auditoria nesta revisão
achou **zero** ocorrência de `:active` em todo o CSS do frontend — nenhum
controle clicável responde ao toque antes do React re-renderizar depois
do evento.

## Consequências

- Transição entre telas, arrastar (se um dia existir, ex. reordenar
  Glossário), e feedback de toque usam spring com os parâmetros da tabela
  da skill (`damping`/`response`), nunca `@keyframes` de duração fixa.
- Nenhuma superfície nova do rec-meet ganha `backdrop-filter`, blur,
  translucidez em camada ou sombra. Se aparecer num PR futuro citando
  "a skill apple-design manda", a resposta é este ADR: manda só a parte
  de movimento.
- `prefers-reduced-motion` é obrigatório em qualquer spring/transição
  nova a partir de agora — não é um adicional posterior.
