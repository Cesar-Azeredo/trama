# ADR 0020 — Sugerir variações parecidas de um termo sem dicionário

- **Data:** 2026-11-10
- **Situação:** aceito

## Contexto

O Whisper escreve o mesmo nome de vários jeitos ("Aprovion", "aprovium",
"a Provium", "aprovio", "Rovio"; "MQX", "MKX", "VQX"). Depois que a pessoa
corrige um deles em todas as reuniões (ADR 0019), o app deve apontar os
outros — sem trocar nada por conta própria e sem sugerir palavra comum do
português, que é o falso positivo que faria a pessoa parar de confiar na
lista.

O app não pode baixar nada (CLAUDE.md, regra 1). Não há dicionário de
português no Python nem no macOS. "Palavra comum" tem de vir de algum lugar
que já está na máquina.

## Decisão

Candidato: 1 a n+1 palavras seguidas de uma fala (n = palavras do trecho
corrigido), comparado "colado" (sem acento, sem maiúscula, sem espaço nem
pontuação) com o trecho e com o certo.

- **Parecido:** distância de edição Damerau-Levenshtein de no máximo 1
  letra até 5 letras, 2 de 6 a 9, 3 acima; ou a mesma chave de som do
  português (v/b, c/k/q, s/z/ç, h mudo, letra dobrada, final -m/-n,
  -e/-i, -o/-u). "MKX" e "MQX" têm a mesma chave.
- **Palavra comum, sem dicionário:** a medida é a das próprias reuniões.
  Uma palavra que aparece em 5 ou mais das reuniões processadas é comum;
  uma de 5 letras ou mais que começa como uma palavra comum também
  ("aprovou" e "aprovem" são da família de "aprovação"). Candidato em que
  todas as palavras são comuns fica de fora — a não ser que o Whisper
  tenha marcado dúvida nele (`palavras_baixa_confianca`) em algum lugar. Aí
  a forma entra com todas as ocorrências, porque a correção troca todas.
- **Mais de uma palavra** só quando a junção é o que torna parecido ("a
  Provium" → "aprovium"): no máximo 1 letra de distância, mais parecida que
  cada palavra sozinha, e sem conter o próprio termo ("o MKX",
  "tabela à vista. O").
- **Fora sempre:** o que a própria correção já casa, o que já tem
  correção, nome da galeria, termo conhecido, fala corrigida à mão.
- **Ordem:** dúvida do Whisper primeiro, depois a mais parecida, depois a
  mais frequente. No máximo 15.

Nas reuniões reais: "aprovium → Aprovion" sugere "aprovio" (5 vezes, uma com
dúvida) e "a Provium"; "MKX → MQX" sugere "VQX". Nenhuma conjugação de
"aprovar", nenhum "vale" ou "vários".

## Alternativas descartadas

- **Dicionário de português embutido.** Teria de vir de fora (licença,
  tamanho, versão) e ainda não saberia que "Aprovion" é da empresa e
  "aprovação" é comum.
- **Só a distância de edição.** Sugere "aprovou", "aprovem", "aprova" —
  palavras certas — para "Aprovion".
- **Só palavras em `palavras_baixa_confianca`.** O Whisper escreve "MKX"
  com confiança: a dúvida dele ordena, mas não basta como filtro.
- **Uma caixa por ocorrência, em vez de por forma.** A correção vale para
  as próximas reuniões, e lá não há ocorrência para marcar: o que se
  decide é a forma.

## Consequências

- Forma distante demais e sem o mesmo som fica de fora ("Rovio" para
  "Aprovion": 3 letras numa palavra de 8). A pessoa corrige pelo texto
  quando encontrar.
- Nome de produto que começa como uma palavra comum só aparece se o
  Whisper tiver duvidado dele.
- O custo é varrer todas as falas: cerca de 2 a 3 segundos para um termo
  de uma palavra nas 13 reuniões, perto de 8 para três palavras.
