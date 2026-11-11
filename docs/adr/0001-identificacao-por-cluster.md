# ADR 0001 — Identificar o falante por cluster, não por trecho

- **Data:** 2026-08-31 (registrado retroativamente em 2026-09-16)
- **Situação:** aceito

## Contexto

O plano original comparava cada frase transcrita com a galeria de vozes. Um
trecho de 2 segundos gera embedding instável: o mesmo falante produz vetores
bem diferentes de frase para frase.

## Decisão

Comparar o cluster inteiro. A diarização agrupa a fala em clusters; o
pipeline junta 60–120 s de cada um, tira a média dos embeddings ponderada
pela duração, e compara essa média com a galeria por cosseno.

## Alternativas descartadas

**Por trecho.** Instável, e multiplicaria as decisões de revisão por cem.

**Algoritmo húngaro para a atribuição.** Foi implementado e removido: ele
proíbe por construção que uma pessoa ocupe dois clusters, e por isso deu o
nome de Rolando a um cluster que era do Ramiro. Uma pessoa pode
legitimamente ocupar dois clusters quando a diarização a divide. A
atribuição é gulosa.

## Consequências

- A revisão humana pede 3 a 6 decisões por reunião, não trezentas.
- Faixa de acerto observada: 0,834 a 0,972 em 20 identificações.
- Um cluster que mistura duas pessoas (fala cruzada) recebe um nome só e
  não há como corrigir sem mexer na captação.
