# ADR 0027 — Trama também por dentro: variáveis, chaves e skill

- **Data:** 2026-11-12
- **Situação:** aceito; revê o item 1 do ADR 0023

## Contexto

O ADR 0023 trocou o nome visível para Trama e deixou `rec-meet` nos
identificadores internos, para não apagar preferências salvas nem quebrar
comandos de quem já rodava o app. Depois disso o pacote virou `trama`
(ADR 0025) e o repositório público já nasceu `trama`. Sobraram dois nomes
para a mesma coisa: quem lê o código encontrava `REC_MEET_AUDIOS` ao lado
de `trama-servidor`, e a skill de identidade com o nome antigo.

## Decisão

- Variáveis de ambiente `REC_MEET_*` viram `TRAMA_*` (`TRAMA_DEMO`,
  `TRAMA_AUDIOS`, `TRAMA_TERMOS`, `TRAMA_PORTA`). Sem leitura da variável
  antiga: o app ainda não tem instalação de terceiros, e manter os dois
  nomes seria código para sempre por causa de um único usuário.
- Chaves do `localStorage` `rec-meet:*` viram `trama:*`. Aqui há o que
  perder (tema, idioma, perfil, "mostrar interações"), então
  `frontend/src/armazenamento/migrarChaves.ts` copia cada chave antiga para
  a nova na primeira abertura — sem sobrescrever uma escolha já feita com o
  nome novo — e apaga a antiga. É o primeiro import de `main.tsx`, porque
  os módulos de preferência leem o `localStorage` ao carregar. O
  `index.html`, que pinta o tema antes de qualquer módulo, aceita a chave
  antiga como reserva. `tests/test_identidade.py` garante que a chave
  antiga só aparece nesses lugares.
- A skill `identidade-rec-meet` vira `identidade-trama`.

## Alternativas descartadas

- **Manter os identificadores antigos** (o que o ADR 0023 decidiu): custo
  zero, mas deixa o nome antigo em todo arquivo que alguém abre primeiro.
- **Ler `REC_MEET_*` como reserva de `TRAMA_*`**: compatível, mas é um
  segundo caminho de configuração sem ninguém que precise dele.
