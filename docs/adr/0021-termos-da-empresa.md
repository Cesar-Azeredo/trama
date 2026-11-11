# ADR 0021 — "Termos da empresa": o glossário visto por termo, não por regra

- **Data:** 2026-11-10
- **Situação:** aceito. Supera em parte o ADR 0018 (o que descrição vazia
  significa).

## Contexto

A tela "Glossário" em Perfil mostrava o `termos.txt` como ele é: uma lista
de regras `errado → certo`, editada na própria linha e salva de uma vez.
Para quem mantém o arquivo, é o modelo certo. Para o cliente do app, que
precisa corrigir sozinho e em segundos, "regra" e "ordem de regra" são
detalhe de implementação: o que ele conhece é o termo ("Aprovion") e as
formas erradas dele ("aprovium", "a Provium").

Pelo ADR 0018, esvaziar a descrição de um termo sem regra o tirava do
vocabulário. A revisão de termos ("Está certo", sem descrição) e o
"Adicionar termo" sem descrição precisam de um termo conhecido **sem**
descrição.

## Decisão

- **A tela vira "Termos da empresa".** Cada item é um termo: o nome certo,
  "O que é?" (a descrição, gravada ao sair do campo) e "Corrige: aprovium ×,
  a Provium ×", as variações já corrigidas, cada uma removível. "Adicionar
  termo" pede nome e descrição; "Adicionar variação" é a correção "em todas
  as reuniões e nas próximas" do ADR 0019 (conferir antes, depois
  corrigir) — o caminho dela pelo teclado. Cada ação grava na hora.
- **O agrupamento é o do vocabulário:** o lado certo de cada regra sem a
  palavra de ligação do começo (ADR 0017). "do tabula da vista → da Gestão
  à Vista" é uma variação de "Tabela à Vista", mostrada com o "→ da Gestão
  à Vista" porque o certo dela leva o artigo.
- **O formato do `termos.txt` não muda.** Termo conhecido sem descrição e
  sem regra é `#= termo` (sem a seta). Descrição vazia mantém o termo;
  tirar um termo é a ação explícita "Remover termo", que leva a descrição e
  todas as variações dele.
- **Remover não desfaz.** O que já foi corrigido nas reuniões continua como
  está: a remoção só vale para as transcrições seguintes e para o botão de
  aplicar às já processadas.

## Alternativas descartadas

- **Manter o editor de regras ao lado da tela nova.** Duas telas para o
  mesmo arquivo, e a ordem das regras de novo exposta a quem não deveria
  precisar saber dela.
- **Remover uma variação desfazendo as trocas nas reuniões.** A troca é
  texto reescrito: não há como saber, depois, quais "Aprovion" eram
  "aprovium" — e a correção manual de fala já preserva o que importa.
- **Descrição vazia continuando a apagar o termo (ADR 0018).** Um campo
  que a pessoa limpa sem querer não pode apagar um termo inteiro.

## Consequências

- O GET/PUT `/api/termos`, com o arquivo como lista de regra/texto,
  continua no servidor, mas nenhuma tela usa mais.
- Comentários, linhas em branco e regras comentadas do `termos.txt`
  continuam invisíveis e intactos.
- Não há como renomear um termo pela tela. Hoje, isso se faz removendo e
  adicionando de novo.
