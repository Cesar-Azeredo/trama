# ADR 0025 — Pacote `trama`, dado do usuário fora do git e demonstração sintética

- **Data:** 2026-11-11
- **Situação:** aceito

## Contexto

Até aqui o pipeline eram scripts soltos na raiz (`run.py`, `review.py`,
`core.py` e mais nove), e o servidor importava dois deles como biblioteca.
O projeto vai ganhar um repositório público novo, de portfólio, que nasce
de um retrato limpo deste. Três coisas impediam isso: a raiz misturava
produto, ferramenta de calibração e experimento; o `termos.txt` versionado
era vocabulário real da empresa; e os documentos e testes citavam pessoas,
termos e falas de reuniões reais.

## Decisão

- **Pacote `trama/`** com a biblioteca (`nucleo`, `pipeline`, `revisao`,
  `interacao`, `edicao`, `termos`, `migracoes/`), o servidor
  (`trama/servidor/`) e a linha de comando separada (`trama/cli/`:
  `trama-processar`, `trama-revisar`, `trama-servidor`, `trama-verificar`).
  O servidor importa a biblioteca, nunca um script. `pyproject.toml` no
  lugar do `requirements.txt`.
- **`ferramentas/`** para desenvolvimento e calibração (inclui
  `colher_vozes.py`, o jeito que o ADR 0011 defende de montar a galeria) e
  **`experimental/`** para o que está fora do produto (ata local, ADR 0002;
  cadastro por gravação avulsa, descartado pelo ADR 0011).
- **Dado do usuário fora do git**, no mesmo padrão de `audios/` e
  `vozes.db`: o `termos.txt` real sai do índice; versionado fica um
  `termos.exemplo.txt` genérico, que é o que as suítes validam.
- **Demonstração sintética**: `audios-demo/` com três reuniões fictícias e
  um `vozes-demo.db`, gerados por `ferramentas/gerar_demo.py` passando
  pelas funções reais do pipeline e da revisão. Sem áudio: em modo
  demonstração (`REC_MEET_DEMO=1`) o app avisa "Áudio não disponível na
  demonstração".
- Nomes, termos e falas reais nos documentos e testes trocados por
  fictícios que preservam o que cada exemplo demonstra (distância de
  edição, família de prefixo, comprimento, gênero gramatical).

## Alternativas descartadas

- **Layout `src/`.** Evita importar o pacote sem instalar, mas as suítes
  rodam por caminho (`python tests/test_x.py`) desde o começo do projeto,
  e com o pacote na raiz isso continua funcionando sem instalação.
- **Manter os scripts e só mover para uma pasta.** O servidor continuaria
  importando `main()` de linha de comando como biblioteca.
- **Anonimizar reuniões reais para a demonstração.** Texto de reunião
  real anonimizado ainda é conteúdo da empresa (CLAUDE.md, regra 3, no
  espírito); e voz não se anonimiza. Sintético não tem o que vazar.
- **Voz sintética (TTS) para a demonstração ter áudio.** Descartado: a
  demonstração mostraria uma identificação de voz que não é a do produto.
- **Reescrever o histórico deste repositório.** O repositório público
  nasce de um retrato limpo, com histórico próprio; este continua privado.

## Consequências

- `pip install -e ".[dev]"` passa a ser o primeiro passo; os comandos
  `trama-*` substituem `python run.py` etc.
- Os ADRs anteriores citam os nomes antigos de arquivo (`run.py`,
  `review.py`, `core.py`): são registro histórico e não foram editados.
- Quem roda a demonstração e revisa, ou edita o glossário, escreve nos
  arquivos versionados de `audios-demo/` e no `termos.exemplo.txt`;
  `git checkout` desfaz. As capturas (`npm run capturas`) só navegam.
