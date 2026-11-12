# ADR 0028 — Trechos para conferir, com o texto da lacuna dentro dela

- **Data:** 2026-11-12
- **Situação:** aceito

## Contexto

A tela já marca as falas de confiança baixa e os sons não transcritos
(`lacunas_sem_texto`, ADR 0010), mas ninguém é levado até eles: só quem
lê o transcript inteiro os encontra. A revisão já para a pessoa uma vez
por reunião (vozes, depois termos, ADR 0022) — é o momento de apontar
também onde vale ouvir, se a lista for curta.

Medido nas 13 reuniões reais antes de decidir:

- nenhuma lacuna passa de **2,0 s**; a mais longa de cada reunião fica
  entre 1,7 e 2,0 s. Um piso de 2 s daria zero; 1,5 s deixa 2 a 16 por
  reunião. Por duração, não dá para separar fala de riso;
- falas de confiança baixa são poucas (0 a 17 por reunião) e bem mais
  longas (até 25 s).

## Decisão

Terceira etapa da revisão, "Trechos para conferir" (`trama/trechos.py`):

- **Escolha:** até 3 falas de confiança baixa (a mesma regra da marca do
  Detalhe), as mais longas, mais até 2 lacunas de 1,5 s ou mais, as mais
  longas. No máximo 5. Fora sempre: fala corrigida à mão, trecho já
  respondido, lacuna dentro de uma das falas escolhidas.
- **Fala:** o campo abre com o texto transcrito; gravar é a correção
  manual que já existe (ADR 0016).
- **Lacuna:** o texto é gravado **dentro da própria lacuna**
  (`texto_manual`), nunca no texto da fala. A lacuna é um ponto de
  inserção que não ocupa caractere, então nenhuma marca de posição muda.
  O Detalhe mostra o texto no ponto da lacuna, em itálico; o `.txt`
  baixado e o do disco o põem na linha da fala, com o mesmo falante.
- **Reprocessamento:** cada resposta é casada com a lacuna nova pelo
  tempo (metade de cada uma no mesmo trecho, como as correções de fala).
  Texto sem par vai para `lacunas_sem_lugar`, com aviso, e volta se um
  reprocessamento futuro achar o trecho.
- **"Não dá para entender"** (`ininteligivel` na fala ou na lacuna): nunca
  perguntado de novo. **"Pular"** não grava nada.

## Alternativas descartadas

- **Lista única ordenada por duração.** Mostraria só falas: elas são
  sempre mais longas que qualquer lacuna.
- **Dividir a fala em duas e inserir uma fala nova entre elas** com o
  texto da lacuna. Funcionaria, mas obrigaria a dividir e deslocar todas
  as marcas de posição (divergências, baixa confiança, tempos por
  palavra, sobreposição), e a refazer isso a cada reprocessamento.
- **Gravar o texto no texto da fala** (como uma correção). Apagaria as
  marcas de posição da fala inteira (ADR 0016) por causa de um trecho de
  1,5 s.
- **Piso de 2 s para a lacuna.** Zero lacunas nas reuniões medidas.

## Consequências

- O `.json` ganha `texto_manual`, `escrito_em` e `ininteligivel` nas
  lacunas, `ininteligivel` nas falas e, quando há, `lacunas_sem_lugar`.
- Corrigir à mão a fala que contém uma lacuna escrita tira a lacuna (com
  o texto) da tela e do `.txt`, como as outras marcas; "Voltar ao
  original" devolve.
- "Não dá para entender" de uma lacuna que some no reprocessamento se
  perde (não há texto a guardar): o trecho pode voltar a ser perguntado.
- A busca nas falas não procura no texto escrito nas lacunas.
- Ainda não há como desfazer, pela tela, um texto de lacuna ou um "Não dá
  para entender".
