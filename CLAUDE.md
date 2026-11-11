# CLAUDE.md

Instruções operacionais para agentes trabalhando neste repositório.
Estado do sistema: `ARCHITECTURE.md`. Decisões e porquês: `docs/adr/`.
Uso externo: `README.md` (inglês, visão geral) e `docs/uso.md` (português,
manual de uso).

## O que é

`rec-meet` transcreve reuniões presenciais identificando quem falou cada
trecho. Roda 100% local. O produto em construção é um aplicativo para vender
a empresas que não podem mandar áudio de reunião para fora.

O valor está em **quem falou o quê**. Não em gravar, não em resumir.

## Regras que não se negociam

1. **Nada sai da máquina.** Sem telemetria, sem analytics, sem CDN, sem fonte
   remota, sem verificação de versão. Se um pacote novo faz requisição de
   rede em tempo de execução, ele não entra.
2. **O servidor escuta só em `127.0.0.1`.** Nunca `0.0.0.0`. Um bind errado
   expõe as gravações da empresa para a rede inteira do escritório.
3. **Log nunca contém conteúdo de transcrição.** Em erro, registre o id da
   reunião e o tipo da falha. Nunca a fala das pessoas.
4. **Caminho de arquivo nunca vem do cliente.** O cliente manda um id; o
   servidor resolve o caminho e valida que o resultado está dentro de
   `audios/`. Rejeite qualquer coisa com `..`, barra ou barra invertida.
5. **`subprocess` sempre com lista de argumentos.** Nunca `shell=True`. Vale
   para o código novo como já vale para o `pipeline.py`.
6. **SQL sempre parametrizado.** O nome digitado na revisão vai para o
   `vozes.db`.
7. **Nenhuma migração de schema sem arquivo de migração versionado.**
   Ver ADR 0006.
8. **Erro para o usuário é código, não frase.** O servidor responde
   `{"codigo", "parametros"}` (`trama/erros.py`); o texto, em português e
   em inglês, mora nos catálogos do frontend (`frontend/src/i18n/*/erros.ts`).
   Código novo no servidor sem texto nos dois catálogos derruba
   `tests/test_codigos_de_erro.py`. Stack trace vai para o log local, nunca
   para a tela.
9. **Nunca `dangerouslySetInnerHTML`.** O transcript é texto.

## Regras de estilo

- Código, nomes de arquivo, variáveis e comentários **em português**, sem
  acento e sem cedilha nos identificadores (`interacao`, `sobreposicao`).
  Isso vale só para o IDENTIFICADOR (nome de variável, função, arquivo).
  Qualquer string que o usuário lê leva acentuação normal — texto de
  interface (nos catálogos de `frontend/src/i18n/`), texto que sai no
  terminal para quem roda a CLI. "Sem acento no identificador" nunca é desculpa
  para "sem acento no conteúdo da string" - já vazou pra tela por engano
  (mensagem de erro do servidor sem acento nenhum, replicando o nome do
  identificador em vez do texto que o usuário deveria ler).
- Visual: siga `.claude/skills/identidade-rec-meet/SKILL.md`. Não é
  sugestão. Movimento e resposta: skill `apple-design`.
- Um comportamento por vez. Mudança grande vira várias pequenas, cada uma
  validada antes da próxima.

## Dependência externa: skill `apple-design`

A skill de movimento e resposta (`apple-design`, de terceiro) **não é
versionada aqui**: não tem licença declarada que permita redistribuir. O
`skills-lock.json` na raiz registra de onde ela vem. Para instalar
(ferramenta de quem desenvolve, nunca do produto entregue - não é
requisição de rede em tempo de execução do app, regra 1):

```bash
npx skills add https://github.com/emilkowalski/skills --skill apple-design
```

Antes de criar ou revisar qualquer tela, componente ou interação, confirme
que `.claude/skills/apple-design/SKILL.md` existe e é legível. Se não
existir, avise - a referência em `identidade-rec-meet/SKILL.md` já ficou
apontando para uma pasta inexistente por dois marcos inteiros sem que
ninguém notasse.

## Como rodar

```bash
source .venv/bin/activate   # a partir da raiz do repositório
pip install -e ".[dev]"   # uma vez; instala o pacote trama e os comandos

# pipeline (uma reunião, ~6 min para 70 min de áudio)
trama-processar audios/reuniao_NN/reuniao_NN.m4a \
  --pessoas Nome1,Nome2 --device mps --asr mlx

# revisão dos nomes (realimenta os perfis de voz)
trama-revisar audios/reuniao_NN/reuniao_NN.json

# servidor local (127.0.0.1:8000)
trama-servidor            # --dev recarrega quando um .py muda

# demonstração: reuniões e vozes fictícias, sem áudio (audios-demo/)
python ferramentas/gerar_demo.py    # regera a partir de ferramentas/roteiro_demo.py
REC_MEET_DEMO=1 REC_MEET_AUDIOS=audios-demo VOZES_DB=audios-demo/vozes-demo.db \
  REC_MEET_TERMOS=termos.exemplo.txt trama-servidor

# testes: cada suíte roda sozinha, ou todas com pytest
for f in tests/test_*.py; do python "$f" | tail -1; done
pytest -q
```

Onde fica cada coisa:
- `trama/` - o pacote: biblioteca (`nucleo`, `pipeline`, `revisao`,
  `interacao`, `edicao`, `termos`, `migracoes/`), servidor
  (`trama/servidor/`) e linha de comando (`trama/cli/`).
- `ferramentas/` - desenvolvimento e calibração; não fazem parte do app.
- `experimental/` - fora do produto (ata local, cadastro avulso).
- Nenhum script Python na raiz.

## Verificação visual (frontend)

Não use Playwright (nem qualquer navegador automatizado) para conferir
uma mudança visual, a menos que o usuário peça explicitamente ou
autorize depois de você perguntar. Já custou tempo caro nesta base e
travou no meio de uma captura de tela. Quem valida visualmente é o
usuário, no próprio navegador — não é um passo que o agente pula, é um
passo que muda de dono.

Isso não reduz o rigor exigido; muda onde ele mora:

- Leia a lógica com cuidado — o fluxo real de execução, não "parece
  certo" numa passada de olho.
- Confira a documentação da API que está usando. Não confie em memória
  para comportamento padrão de browser (ex.: o que uma folha de estilo
  nativa anima por padrão) - foi exatamente esse tipo de suposição que
  causou a régua da nav se deslocando na transição de tela.
- Pense nos casos de falha antes de escrever, não depois de quebrar.
- Se algo genuinamente precisa de medição pra não sair quebrado, pergunte
  antes: "isso aqui eu preciso instrumentar, autoriza?" - a decisão de
  gastar esse tempo é do usuário, caso a caso, não automática.

Ao terminar algo visual, diga explicitamente o que **não** foi verificado
no navegador de verdade. "Implementei X, não verifiquei no navegador" é a
frase certa. Nunca descreva como funcionando o que não foi provado.

## Antes de terminar qualquer tarefa

- Os testes passam? Rode. Não presuma.
- Mudou comportamento? Escreveu teste para ele?
- Mudou arquitetura? Atualizou `ARCHITECTURE.md`?
- Tomou decisão técnica com alternativa descartada? Escreveu um ADR?
- Mudou o que o usuário roda ou vê? Atualizou o `docs/uso.md` (e o
  `README.md`, se muda a visão geral)?
- Rodou `git status`? Trabalho não commitado é trabalho que se perde. Já
  aconteceu neste projeto: o ledger de contribuições existiu apenas na
  árvore de trabalho por dias, com o banco já migrado.
- Fez push? **Todo commit vai para o `origin` logo em seguida**, sem
  esperar pedido. Commit que fica só na máquina é trabalho que pode se
  perder do mesmo jeito. Continua valendo a ordem: suítes passando,
  commit, push. Se o push falhar (rede, conflito, rejeição), avise na
  hora; nunca force (`--force`) sem pedido explícito.
- Commits **sem coautor e sem assinatura**: nenhuma linha
  `Co-Authored-By`, nenhum "Generated with Claude Code". O gancho
  `ganchos/commit-msg` remove as duas mesmo quando a configuração
  `attribution` do Claude Code não é respeitada. Ele só roda se o clone
  tiver `git config core.hooksPath ganchos` (configuração local, não vem
  com o repositório): confira antes do primeiro commit.

## O que não fazer

- Não faça fine-tuning de modelo de voz. Cria obra derivada e questão de
  dado biométrico sob LGPD que hoje não existe. Ver ADR 0003.
- Não trate a ata local como feature principal. Ver ADR 0002.
- Não adicione autenticação, rate limit, JWT ou multiusuário. Isso é um
  processo em localhost com um usuário. Ver ADR 0005.
- Não instale biblioteca de componentes pronta no frontend.
- Não commite `vozes.db`, `audios/`, `termos.txt`, `.env` ou qualquer `.m4a`.
  O glossário real é dado da empresa; versionado só o `termos.exemplo.txt`.
