# ADR 0029 — Apagar reunião apaga tudo, a voz aprendida primeiro

- **Data:** 2026-11-12
- **Situação:** aceito

## Contexto

Não havia como apagar uma reunião. Um upload errado, ou uma gravação que
ninguém vai processar, ficava na lista para sempre; o único recurso era
apagar a pasta à mão, que quem usa o app empacotado não tem como fazer.
E apagar só a pasta deixaria no `vozes.db` a voz que a reunião ensinou:
dado biométrico de uma reunião que já não existe, ainda pesando no
perfil de cada pessoa.

## Decisão

"Apagar reunião" (`DELETE /api/reunioes/{id}`, `servidor/reunioes.apagar`)
apaga a reunião inteira, com a mesma confirmação de excluir a voz de uma
pessoa: antes, a tela mostra quanto de voz cada pessoa perde
(`GET .../exclusao`, nada apagado), e quem fica sem voz nenhuma sai da
galeria.

Ordem deliberada:

1. **Ledger primeiro**, numa transação: as contribuições da reunião saem
   e o perfil de cada pessoa afetada é recalculado. Depois, `VACUUM`. Se
   falhar, nada foi apagado.
2. **Depois a pasta**: um `rename` atômico para um nome com ponto (que o
   padrão de id nunca aceita) a tira da lista, e então ela é removida.
3. A cópia WAV que o processamento deixa na pasta temporária do sistema,
   só se o caminho gravado no `.json` cair dentro dela.

Reunião sendo processada é recusada (409), sob a mesma trava que inicia
um processamento.

## Alternativas descartadas

- **Pasta primeiro, ledger depois.** Uma falha entre os dois deixaria voz
  aprendida de uma reunião que já sumiu — sem nenhuma tela de onde
  apagá-la.
- **Apagar só áudio, `.json` e `.txt`.** A pasta guarda também amostras,
  saída da fase 0, `meta.json` e caches com a duração e a data. Sobraria
  lixo com dado da reunião.
- **Lixeira (apagar depois de N dias).** Dado de reunião guardado sem a
  pessoa saber, num app que existe justamente para não espalhar áudio;
  e o vetor de voz continuaria no banco.
- **Manter a voz aprendida** ("a reunião sai, o aprendizado fica"). A
  confirmação passaria a dizer "apagar" para algo que não apaga tudo.

## Consequências

- Apagar é irreversível, e a tela diz isso.
- Os backups `vozes.db.bak-*` continuam com o vetor antigo, como na
  exclusão de pessoa (ARCHITECTURE.md, "Limite da exclusão").
- Se a pasta não puder ser removida depois do `rename`, ela fica
  escondida em `audios/` (`.apagando-…`), fora da lista e da busca.
- O pipeline continua deixando a cópia WAV na pasta temporária depois de
  processar; apagar a reunião a remove, mas reunião não apagada mantém a
  cópia até o sistema limpar a pasta temporária.
