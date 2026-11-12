# CLAUDE.md

Instruções para agentes neste repositório. Estado do sistema:
`ARCHITECTURE.md`. Decisões e porquês: `docs/adr/` (uma por arquivo,
modelo em `0000-template.md`). Visual: `.claude/skills/identidade-trama/SKILL.md`.
Uso: `README.md` (inglês) e `docs/uso.md` (manual em português).

## O que é

**Trama** transcreve reuniões presenciais dizendo quem falou cada trecho,
100% na máquina de quem usa. É para empresas que não podem mandar áudio de
reunião para fora. O valor está em **quem falou o quê** — não em gravar,
não em resumir.

## Regras que não se negociam

1. **Nada sai da máquina.** Sem telemetria, analytics, CDN, fonte remota ou
   verificação de versão. Pacote que faz requisição de rede em tempo de
   execução não entra.
2. **O servidor escuta só em `127.0.0.1`.** Nunca `0.0.0.0`.
3. **Log nunca contém transcrição.** Em erro: id da reunião e tipo da falha.
4. **Caminho de arquivo nunca vem do cliente.** O cliente manda um id; o
   servidor resolve e valida que fica dentro da pasta de áudios. Rejeite
   `..`, barra e barra invertida.
5. **`subprocess` sempre com lista de argumentos**, nunca `shell=True`.
6. **SQL sempre parametrizado.**
7. **Migração de schema só com arquivo versionado** em `trama/migracoes/`
   (ADR 0006).
8. **Erro é código, não frase.** O servidor responde
   `{"codigo", "parametros"}` (`trama/erros.py`); o texto mora nos
   catálogos do frontend. Stack trace vai para o log local, nunca para a
   tela.
9. **Os dois catálogos de idioma andam juntos.** Todo texto novo entra em
   `frontend/src/i18n/pt/` e `en/` no mesmo commit (ADR 0026); código de
   erro sem texto nos dois derruba `tests/test_codigos_de_erro.py`.
10. **Nunca `dangerouslySetInnerHTML`.** O transcript é texto.
11. **Dado real nunca entra no git**: `vozes.db`, `audios/`, `termos.txt`,
    `.env`, `.m4a`, nome de pessoa real, vocabulário de empresa, trecho de
    reunião de verdade. O repositório é público. Exemplo é sempre fictício
    (`audios-demo/`, `termos.exemplo*.txt`).

## Idioma

- Código, identificadores, comentários, ADRs e `ARCHITECTURE.md` em
  **português**; identificador sem acento (`interacao`), texto que alguém
  lê com acento.
- `README.md` e a descrição do repositório em **inglês**.

## Onde fica cada coisa

- `trama/` — o pacote: biblioteca (`nucleo`, `pipeline`, `revisao`,
  `interacao`, `edicao`, `termos`, `erros`, `migracoes/`), servidor
  FastAPI (`trama/servidor/`) e linha de comando (`trama/cli/`).
- `frontend/` — React + TypeScript + Vite, sem biblioteca de componentes.
- `ferramentas/` — desenvolvimento e calibração (inclui `gerar_demo.py` e
  os roteiros fictícios); não fazem parte do app.
- `experimental/` — fora do produto (ata local, cadastro avulso).
- `audios-demo/pt` e `audios-demo/en` — três reuniões fictícias e um
  `vozes-demo.db` cada, gerados por `python ferramentas/gerar_demo.py`.
- `tests/` — uma suíte por arquivo, roda sozinha ou via `pytest`.
- `ganchos/` — gancho `commit-msg`.

Variáveis de ambiente: `TRAMA_AUDIOS` (pasta das reuniões, padrão
`audios`), `VOZES_DB` (banco de vozes), `TRAMA_TERMOS` (glossário, padrão
`termos.txt`), `TRAMA_PORTA` (padrão 8000), `TRAMA_PORTA_FRONTEND` (porta
do Vite, padrão 5173; o servidor só aceita Origin dela), `TRAMA_IDIOMA`
(`pt`/`en`: mensagens da linha de comando e `.txt` em disco; sem ela, o
idioma do sistema), `TRAMA_DEMO=1` (modo
demonstração, sem áudio), `HF_TOKEN` (modelos do pyannote).

## Como rodar

```bash
source .venv/bin/activate && pip install -e ".[dev]"
trama-verificar                                   # ffmpeg, pacotes, token
trama-processar audios/reuniao_NN/reuniao_NN.m4a --pessoas Ana,Bruno
trama-revisar audios/reuniao_NN/reuniao_NN.json
trama-servidor                                    # --dev recarrega

# demonstração (en: audios-demo/en e termos.exemplo.en.txt)
TRAMA_DEMO=1 TRAMA_AUDIOS=audios-demo/pt VOZES_DB=audios-demo/pt/vozes-demo.db \
  TRAMA_TERMOS=termos.exemplo.txt trama-servidor
cd frontend && npm run dev
```

## Antes de cada commit

- **Todas as suítes verdes, sempre. Nunca commit com teste vermelho** —
  nem "falha que não é minha": pare e avise.
  ```bash
  for f in tests/test_*.py; do python "$f" | tail -1; done
  ruff check . && ruff format --check .
  (cd frontend && npx oxlint && npm test && npm run build)
  ```
- Mudou comportamento: teste novo. Mudou arquitetura: `ARCHITECTURE.md`.
  Decisão com alternativa descartada: ADR. Mudou o que o usuário roda ou
  vê: `docs/uso.md` (e `README.md`, se muda a visão geral).
- **Push logo depois de cada commit**, sem esperar pedido. Push falhou:
  avise na hora. Nunca `--force` sem pedido explícito.
- **Commits sem coautor e sem assinatura** (nada de `Co-Authored-By` nem
  "Generated with"). O gancho `ganchos/commit-msg` remove as duas; ele só
  roda com `git config core.hooksPath ganchos` — confira no clone.
- Um comportamento por commit; mudança grande vira várias pequenas.

## Verificação visual

- **Playwright (ou qualquer navegador automatizado) só quando o usuário
  pedir.** Quem verifica a tela é o usuário, no navegador dele.
- O rigor fica na leitura: siga o fluxo real do código, confira a
  documentação da API em vez de confiar na memória sobre comportamento
  padrão de navegador, pense nos casos de falha antes.
- Ao terminar algo visual, diga **o que não foi verificado** no navegador.
  Nunca descreva como funcionando o que não foi provado.
- Movimento e resposta seguem a skill `apple-design` (de terceiro, não
  versionada — sem licença para redistribuir; origem em `skills-lock.json`):
  `npx skills add https://github.com/emilkowalski/skills --skill apple-design`.
  Se `.claude/skills/apple-design/SKILL.md` não existir, avise antes de
  mexer em interação.

## O que não fazer

- Fine-tuning de modelo de voz (obra derivada, dado biométrico — ADR 0003).
- Ata local como feature principal (ADR 0002).
- Autenticação, rate limit ou multiusuário: é um processo em localhost com
  um usuário (ADR 0030).
- Biblioteca de componentes pronta no frontend.
- Script Python solto na raiz.
