# ADR 0009 — Atribuição por palavra: pista com pontilhado, não correção

- **Data:** 2026-09-19
- **Situação:** aceito

## Contexto

`run.py:alinhar()` atribui cada palavra ao falante com maior sobreposição
temporal contra a diarização exclusiva (`dono()`), e só depois consolida
por FRASE: todas as palavras de uma frase vão para quem "ganhou" o voto
ponderado por duração. A atribuição por palavra, antes desta mudança, era
descartada nesse segundo passo — sobrescrita pelo vencedor e nunca gravada
em lugar nenhum.

Isso incomodava a leitura: dentro do bloco de uma pessoa, uma interjeição
curta de outra (apoio, interrupção, disputa) desaparecia no texto — a
frase inteira saía com um único dono, mesmo quando o alinhamento por
palavra via, naquele instante, alguém diferente.

## Decisão

Cada fala grava um campo novo, só quando existe divergência:

```json
"palavras_divergentes": [
  {"posicao": 39, "comprimento": 2, "falante": "Celso"}
]
```

`posicao`/`comprimento` são deslocamento e tamanho em CARACTERES dentro do
próprio `texto` da fala — a tela só faz uma fatia de string, sem
re-tokenizar. Fala sem divergência não ganha a chave (nem lista vazia);
reunião de antes deste campo simplesmente não tem nenhuma — ausente é
ausente.

Na tela (`Detalhe.tsx`), a palavra divergente aparece na cor da voz de
quem pode ter dito aquilo, com um sublinhado pontilhado
(`.palavra-divergente`). O resto do corpo continua em `--tinta-corpo`.

**Por que é pista, não correção.** A atribuição por palavra é MENOS
confiável exatamente onde ela mais aparece: sobreposição de fala, onde o
Whisper já transcreve com incerteza e o encaixe temporal com a diarização
fica mais grosseiro. O dado que existe é "quem tinha mais sobreposição de
tempo com esta palavra", não uma verificação acústica de quem realmente
falou. Ele pode estar certo, mas não é prova — trocar a cor do texto sem
mais nada apresentaria um palpite como se fosse fato apurado.

**Por que o pontilhado.** Dois motivos, não um:

1. A cor sozinha dependeria de quem enxerga cor para entender o sinal — e
   é exatamente a regra de acessibilidade do projeto (SKILL.md: "cor nunca
   é o único portador de significado"). O pontilhado é o segundo canal.
2. Ele também comunica ALGO DIFERENTE da cor: a cor diz QUEM (a pista); o
   pontilhado diz QUE TIPO DE AFIRMAÇÃO é essa — um traço tracejado, não
   uma marcação sólida, sinaliza "isto é um palpite medido, não uma
   correção aplicada". Um sublinhado sólido, ou preencher o fundo da
   palavra, teria o peso visual de uma correção de fato.

## O que o caso medido da reuniao_09 mostra sobre o limite disto

Um usuário reportou, na fala da Amanda às 44,4–55,3s, que a frase inteira
depois do primeiro "?" era do Celso — mas só 4 palavras espalhadas
apareceram pontilhadas. Medição (ver conversa/commit): o alinhamento por
palavra JÁ concordava com a Amanda para quase toda a janela, porque é
isso que a diarização (bruta e exclusiva) já dizia — um turno contínuo
dela de ~9 segundos, com só um blip curto do Celso no meio. Documentado
em `ARCHITECTURE.md`, "Fronteiras conhecidas".

Isto expõe o limite estrutural da feature: **divergência aqui é um sinal
de DESACORDO INTERNO entre duas granularidades da MESMA diarização** (a
palavra vota diferente da frase), não um sinal de desacordo com a
realidade. Quando a diarização erra o mapa de quem-fala-quando por um
trecho inteiro, a atribuição por palavra e a votação por frase erram
JUNTAS, concordando uma com a outra — e uma marca que existe para
sinalizar desacordo não tem o que sinalizar quando as duas partes que ela
compara já concordam, ainda que erradas. A tela fica muda exatamente no
caso que mais importaria avisar.

Achado relacionado, menor: parte das divergências medidas antes desta
mudança vinha de um bug separado em `dono()` para tokens de duração zero
(comum no Whisper) — o desempate por proximidade empatava e vencia por
ordem de lista, um artefato, não uma medição. Corrigido separadamente
(`dono_do_instante`, contenção estrita do instante); reduziu as
divergências da `reuniao_09` de 290 para 269, das quais só 8 (antes 29)
vêm de token de duração zero. Não é a causa do caso acima — é um problema
diferente, de precisão da medição, não de cegueira estrutural.

## Alternativas descartadas

**Aplicar a atribuição por palavra como correção de fato** (substituir o
falante da palavra na dinâmica/exportação, não só colorir na tela). Uma
medição sabidamente menos confiável na sobreposição não deveria virar
fato silencioso em nenhuma estrutura de dados — só uma pista visual,
descartável, no lugar onde um humano já está lendo e pode julgar.

**Mostrar um número de confiança em vez de uma marca binária.** Não existe
essa métrica no pipeline: o Whisper aqui não devolve confiança por
palavra, só timestamps; a única coisa medida é sobreposição de duração
contra a diarização. Uma barra de confiança seria inventada.

**Não mostrar nada, confiar sempre no voto da frase.** Descartaria
silenciosamente exatamente o sinal que motivou o pedido original —
apoios, interrupções e disputas curtas embutidas no meio da fala de
outra pessoa.

**Destacar com fundo colorido em vez de pontilhado.** Proibido pela
SKILL.md (etiqueta colorida gritante) e teria o peso visual de uma
correção — o oposto do que a pista deveria comunicar.

## Consequências

- A feature ajuda a notar interjeições locais dentro de um trecho onde a
  diarização, no geral, está certa. Ela NÃO é uma rede de segurança contra
  a diarização atribuir um turno inteiro à pessoa errada — nesse caso ela
  fica muda, porque as duas granularidades que ela compara herdam o mesmo
  erro de origem. Ver `ARCHITECTURE.md`, "Fronteiras conhecidas".
- Qualquer detector futuro de "diarização errou o turno inteiro" precisa
  de um sinal diferente deste (por exemplo, comparar o embedding do turno
  inteiro contra a galeria, não votar palavra a palavra) — fora do escopo
  desta decisão.
- `posicao`/`comprimento` em caracteres exigem que qualquer transformação
  de texto posterior ao alinhamento (hoje, só `termos.aplicar_em_falas`)
  mantenha as posições em sincronia com o texto - ver
  `termos._aplicar_uma_regra_com_divergencias`.
