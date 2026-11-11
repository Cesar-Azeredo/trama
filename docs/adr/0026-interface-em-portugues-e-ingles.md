# ADR 0026 — Interface em português e inglês, com catálogos tipados no build

- **Data:** 2026-11-11
- **Situação:** aceito

## Contexto

O Trama é um produto para empresas brasileiras, mas o repositório virou
portfólio público e a demonstração precisa ser lida por quem não fala
português. Até aqui, cada texto da interface estava escrito direto no JSX, e
o servidor mandava mensagens de erro prontas, em português, que a tela só
repetia.

## Decisão

- **Dois idiomas, Português e English**, escolhidos em Perfil >
  Configurações > Idioma. Sem escolha salva, vale o idioma do navegador
  (português para qualquer `pt-*`, inglês para o resto). A escolha fica no
  `localStorage`, como o tema (`frontend/src/i18n/idioma.ts`).
- **Catálogos em TypeScript, um por idioma e por área da interface**
  (`frontend/src/i18n/pt/*.ts`, `en/*.ts`). O de português é a referência
  do tipo: o inglês tem de ter exatamente as mesmas chaves, e a mesma chave
  é texto nos dois ou função nos dois. Plural e concordância moram dentro
  do catálogo, em funções. `i18n/catalogos.test.ts` confere a paridade de
  novo em tempo de teste.
- **Tudo no build**: os dois catálogos são importados estaticamente, nada é
  carregado da rede (CLAUDE.md, regra 1).
- **Datas e números pelo `Intl`** no idioma escolhido (`localeAtual()`,
  `util/numeros.ts`). Exceção deliberada: a ordem das cores de voz usa
  `pt-BR` fixo, para trocar de idioma nunca mudar a cor de ninguém.
- **O servidor manda código, não frase**: `{"codigo", "parametros"}`
  (`trama/erros.py`), para erros e para avisos (inclusive os gravados no
  `.json`). O texto de cada código está em `i18n/<idioma>/erros.ts`.
  `tests/test_codigos_de_erro.py` derruba código do servidor sem texto nos
  dois catálogos.
- **A transcrição baixada (`.txt`)** sai no idioma da interface
  (`?idioma=` na rota): cabeçalho, instruções para a IA e vocabulário. A
  fala das pessoas nunca é traduzida.
- **Identificadores continuam em português** (ADR 0025); só o texto que a
  pessoa lê muda.

## Alternativas descartadas

- **Biblioteca de i18n (i18next, FormatJS).** Resolve um problema maior que
  o nosso (pluralização de dezenas de idiomas, carregamento sob demanda) ao
  custo de dependência nova e de chaves em string sem tipo. Com dois
  idiomas, objetos tipados dão erro de compilação quando falta tradução, e
  `Intl` já está no navegador.
- **Catálogo em JSON.** Sem tipo e sem função: plural e parâmetros virariam
  mini-linguagem de interpolação dentro da string.
- **Servidor traduzindo (Accept-Language).** Espalharia texto de interface
  pelo Python e obrigaria o servidor a conhecer a escolha da tela; o
  código + parâmetros deixa o servidor neutro e o texto num lugar só.
- **Traduzir a fala.** Fora de questão: a transcrição é registro do que
  foi dito.

## Consequências

- Texto novo na tela entra nos dois catálogos ou o build falha.
- Mensagem que a tela guarda (erro, aviso, "feito") nunca é texto pronto:
  é uma `Mensagem` (`i18n/mensagem.ts`), função do catálogo resolvida no
  render. Trocar de idioma redesenha inclusive a mensagem que já está na
  tela. O que a API lança é `ErroDaApi`, que carrega a `Mensagem`.
- O servidor também não manda frase sobre o processamento: a etapa vai
  pelo número, e o que o pipeline acrescentou a ela (falantes, motor,
  termos) vai como dado. O título padrão ("Reunião NN"/"Meeting NN") é
  montado na tela, pelo id.
- O `.txt` que o pipeline grava em disco pela CLI continua em português.
- Há dois conjuntos de demonstração (`audios-demo/pt`, `audios-demo/en`) e
  dois glossários de exemplo, com a mesma estrutura.
