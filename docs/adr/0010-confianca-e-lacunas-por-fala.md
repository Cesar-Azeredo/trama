# ADR 0010 — Confiança da fala e lacunas sem texto: sinalizar sem superinterpretar

- **Data:** 2026-09-20
- **Situação:** aceito

## Contexto

Os dois backends de ASR (`mlx_whisper` e `faster_whisper`) devolvem
`probability` por palavra - a confiança do decoder Whisper naquele token -
e `run.py:transcrever()` extraía e descartava esse número. Da mesma forma,
uma região de silêncio dentro de um turno já ativo (sem nenhum token do
Whisper cobrindo o intervalo) simplesmente desaparecia no texto colado das
palavras vizinhas: nem erro, nem marca, nem registro.

Nenhum dos dois é problema novo. São dois sinais que o pipeline já
calculava e jogava fora.

## Decisão

`run.py:alinhar()` agora grava, por fala:

- `confianca_media` - média de `probability` das palavras da fala. Ausente
  quando não há nenhuma palavra medida (dado antigo, backend hipotético
  sem o campo) - nunca `0.0`, que pareceria confiança mínima medida de
  verdade.
- `palavras_baixa_confianca` - palavras abaixo de `LIMIAR_PALAVRA_BAIXA_CONFIANCA`
  (0.5), no mesmo formato de `palavras_divergentes` (`posicao`/`comprimento`,
  trocando `falante` por `probabilidade`). Puro registro - nunca vira marca
  isolada na tela: uma palavra de baixa confiança sozinha (`"tá"`) deu
  falso positivo na medição, o mesmo padrão já visto no limiar de
  sobreposição (`MIN_SOBREPOSICAO`, ver `ARCHITECTURE.md`).

E, no nível da reunião:

- `lacunas_sem_texto` - trechos de silêncio acima de `LIMIAR_LACUNA_S`
  (0.8s) dentro de um turno ativo, com `inicio`, `fim`, `falante` e
  `posicao` (deslocamento em caracteres no `texto` da fala, para a tela
  inserir a marca no lugar exato do fluxo).

Na tela: a FALA inteira é marcada como baixa confiança quando
`confianca_media < LIMIAR_CONFIANCA_FALA` (0.60) **e** a fala tem pelo
menos `MIN_PALAVRAS_CONFIANCA_FALA` (4) palavras. Nunca a palavra
isolada. As lacunas aparecem inline como `"[som não transcrito]"`, sem
afirmar o que era (riso, gesto, respiração).

Todos os limiares são variável de ambiente, como o resto do pipeline.

## Por que `LIMIAR_CONFIANCA_FALA` foi calibrado diferente do `SIM_MIN`

`SIM_MIN` caiu no meio de um vale VAZIO nos dados: 16 identificações
separavam claramente acertos (0,83-0,95) de erros (0,26-0,36), sem nada no
meio. O limiar ali é uma medição objetiva de onde a separação acontece.

A distribuição de `confianca_media` por fala (693 falas, reuniao_07 +
reuniao_09) não tem vale nenhum - é unimodal e crescente:

```
p5=0.574  p10=0.672  p15=0.732  p25=0.787  p50=0.875

[0.0-0.1)    5     [0.5-0.6)   18
[0.1-0.2)    1     [0.6-0.7)   44
[0.2-0.3)    5     [0.7-0.8)  115
[0.3-0.4)    5     [0.8-0.9)  198
[0.4-0.5)    8     [0.9-1.0)  294
```

Não existe um "abaixo daqui é erro, acima é acerto" para descobrir. Marcar
em 0.60 é uma **decisão de produto**: sinaliza ~6% das falas (42 de 693 na
medição original), uma fração pequena o bastante para a marca continuar
significando alguma coisa quando o usuário a vê. Em 0.70 o volume triplica
(12,4%) sem um salto correspondente de defeito real - o mesmo efeito que
inflou "interrupção" quando `MIN_SOBREPOSICAO` estava baixo demais (132
eventos em 70 min, ver `ARCHITECTURE.md`). `SIM_MIN` descobre uma fronteira
que os dados já tinham; `LIMIAR_CONFIANCA_FALA` escolhe um ponto de corte
num gradiente contínuo, e isso precisa ficar registrado como o que é -
não fingir ser a mesma espécie de medição.

## A média por fala dilui em turno longo: limitação estrutural, não de limiar

Caso medido para testar o limiar: a fala de 0-8,4s da reuniao_07 (
"Bom dia, pessoal. Todo mundo aqui? **Já vou começar.** Eu acho que
dá tempo. Hoje a pauta é curta. Vamos.") é o mesmo turno já documentado em
`ARCHITECTURE.md`/ADR 0009 como erro de FRONTEIRA DE DIARIZAÇÃO - a
diarização deu o turno inteiro ao Celso, e a escuta confirma que "Já vou
começar." foi outra pessoa.

`confianca_media` dessa fala: **0,742** - acima do limiar, não marcada.
Mas as palavras individuais da frase errada já estavam abaixo do limiar de
palavra: `"Já"` (0,219), `"vou"` (0,113), `"começar."` (0,45). O dado
granular capturou exatamente o problema; a média da fala não, porque
~20 palavras boas do resto do turno de 6 frases diluem 3 palavras ruins.

Isto não é o limiar errado - nenhum valor de `LIMIAR_CONFIANCA_FALA` que
não destrua também o sinal em falas curtas resolveria isto (aumentar para
0,75 já marcaria 15%+ das falas). É uma propriedade estrutural da média
como estatística: **quanto mais longo o turno consolidado, menos a média
por fala enxerga um problema local**. A marca da fala é deliberadamente um
sinal mais grosso que `palavras_baixa_confianca` - não um substituto dele.
Esse é também o motivo de nunca ter sido cogitado "consertar" isto
ajustando o limiar: o defeito não está no ponto de corte, está em usar uma
média sobre um turno que pode ter minutos.

## `MIN_PALAVRAS_CONFIANCA_FALA`: por que fala curta não marca sozinha

Das 45 falas abaixo de 0,60 na medição final (reuniao_07 + reuniao_09), 23
tinham de uma a três palavras: `"Ok."`, `"Não."`, `"está"`, `"aqui"`,
`"Só"`, `"porque"`. Numa fala dessas não existe média de verdade - a
única palavra incerta É o valor inteiro, sem nada ao redor para diluir
(o oposto exato do problema da seção anterior). Marcar essas falas é
ruído previsível: o usuário vê a marca em `"está"` e aprende a ignorar a
marca, o que mata o sinal para os casos em que ela importa.

`MIN_PALAVRAS_CONFIANCA_FALA = 4` corta esse ruído: sobram 23 de 45 (contra
14 em 5 palavras e 7 em 6 - a maior perda de sinal está entre 3 e 4
palavras, não depois). As falas de 4 palavras que sobrevivem são frases
completas e plausivelmente problemáticas: `"É a planilha, né?"`,
`"Não entendi, qual prazo?"`, `"está escrito aqui, olha"` - exatamente o
tipo de caso que a marca deveria capturar.

## Turno cru vs. turno exibido, nas lacunas

Medição inicial de `lacunas_sem_texto` (reuniao_07: 126 ocorrências/153,9s;
reuniao_09: 182/218,3s) veio muito acima de uma medição anterior informal,
não versionada (83/101,7s e 76/87,4s). Antes de aceitar qualquer número,
foram descartadas duas hipóteses de dados diferentes:

- **ASR não-determinístico**: transcrever o mesmo `wav16k` duas vezes
  produziu os 5872 tokens byte-idênticos (palavra, timestamp e
  probabilidade) nas duas rodadas.
- **Diarização diferente**: `turnos` (turnos crus) do `.json`
  reprocessado bateu, campo a campo, com o arquivo anterior ao
  reprocessamento.

A diferença era de critério, não de dado: a checagem original usava a
diarização EXCLUSIVA (a mesma passada para `alinhar()`, que força um único
falante por instante) como referência de "turno ativo". Medido: ~40% das
lacunas cruzavam a fronteira entre dois turnos CRUS exclusivos do MESMO
rótulo - a diarização exclusiva, durante fala sobreposta, pode alternar o
desempate entre duas pessoas por artefato do algoritmo, sem que nenhuma
das duas tenha parado de falar de fato. `GAP_TURNO` (2,0s, calibrado para
não fragmentar parágrafo na tela) mesclava os dois turnos crus numa única
fala exibida, e o intervalo entre eles virava, incorretamente, uma
"lacuna dentro de turno ativo".

Corrigido usando a diarização NÃO-exclusiva mesclada por `GAP_MESCLAGEM`
(`analise["turnos_brutos"]`, o mesmo sinal que `interacao.py` já usa para
"quem estava falando" em todo o resto do módulo) como referência de "turno
ativo", em vez da exclusiva. `turno_cru_unico_cobre()` exige que um ÚNICO
turno dessa lista cubra o intervalo inteiro (tolerância de 0,05s,
`TOLERANCIA_LACUNA_S`, só para arredondamento entre os timestamps do
Whisper e os da diarização - não é parâmetro para ajustar quantas lacunas
aparecem). Resultado final: reuniao_07 71/81,7s, reuniao_09 90/100,2s -
não bate exato com a medição anterior (07 ficou ~15% abaixo, 09 ~18%
acima, sem viés numa direção só), porque o script original nunca foi
versionado e não há como reexecutá-lo - mas a direção e a magnitude da
correção (excluir fronteira de turno cru derrubou a contagem em ~44%)
confirmam que o mecanismo certo foi encontrado, não um ajuste que só
coincide com o número antigo.

## Alternativas descartadas

**Marcar a palavra isolada de baixa confiança na tela.** Já era prática
rejeitada (mesmo raciocínio de `palavras_divergentes`, ADR 0009): "tá" deu
falso positivo. `palavras_baixa_confianca` existe como dado, nunca como
marca própria.

**Escolher `LIMIAR_CONFIANCA_FALA` "no vale", como `SIM_MIN`.** Não existe
vale nos dados - forçar um criaria um número arbitrário disfarçado de
medição objetiva. Documentado explicitamente como decisão de produto em
vez disso.

**Usar a diarização exclusiva como referência de turno ativo nas
lacunas.** Testado primeiro, descartado por inflar a contagem em ~44%
contando fronteiras de exclusividade (artefato de desempate durante
sobreposição) como se fossem silêncio real.

**Marcar toda fala abaixo do limiar, sem piso de palavras.** Descartado:
55% das falas marcadas sem o piso eram bordões de 1-3 palavras onde a
"média" é uma única palavra sem contexto para diluir - ruído previsível,
não sinal.

## Consequências

- `.json` ganha, por fala: `confianca_media`, `palavras_baixa_confianca`.
  Por reunião: `lacunas_sem_texto`, `limiar_confianca_fala`,
  `min_palavras_confianca_fala`. Ausentes em reuniões de antes desta
  mudança - ausente é ausente, nunca `0` ou lista vazia inventada.
- `LIMIAR_CONFIANCA_FALA` e `MIN_PALAVRAS_CONFIANCA_FALA` são decisões de
  produto, não limiares "descobertos" - reavaliar se o volume de reuniões
  crescer e a proporção marcada parecer errada na prática, não só
  recalcular a mesma conta com mais dados.
- `palavras_baixa_confianca` continua existindo mesmo quando a fala não é
  marcada (turno longo diluindo, fala curta abaixo do piso) - é o dado que
  fica disponível para quem quiser investigar um caso específico, mesmo
  que a marca grossa da tela não tenha disparado.
- Reprocessamento necessário para reuniões existentes ganharem os campos
  novos (06, 04, 02 na fila, ver `ARCHITECTURE.md`).
