# Trama — guia de uso

Manual de quem roda o Trama no dia a dia, em português. Visão geral do
projeto (em inglês): [README](../README.md). Arquitetura:
[ARCHITECTURE.md](../ARCHITECTURE.md).

O aplicativo se chama **Trama** (marca em ADR 0023): e o nome que aparece
na interface, no titulo da pagina e nas mensagens do servidor. `rec-meet`
continua como nome interno - das variaveis `REC_MEET_*` e das chaves do
navegador.

Kit da marca (guia de uso e SVGs mestres): [`docs/marca/`](marca/kit/guia-de-uso.md).

Pipeline para transcrever reunioes gravadas identificando quem falou o que,
usando diarizacao de falantes (pyannote) + transcricao (Whisper) + uma galeria
de perfis de voz que melhora a cada reuniao confirmada. Alem da transcricao,
mede a dinamica da conversa (sobreposicao, interrupcao, tempo de fala) e pode
gerar uma ata em portugues com um LLM local.

## Como funciona

1. **`cli/verificar.py`** - verifica o ambiente antes da primeira execucao
   (Python, ffmpeg, token do Hugging Face, acesso aos modelos). Roda em
   segundos, evita descobrir um problema de acesso depois de 20 minutos de
   diarizacao.
2. **`fase0.py`** - valida so a diarizacao (sem transcrever). Corta amostras
   de audio de cada cluster de falante para voce ouvir e confirmar se a
   separacao ficou boa.
3. **`cadastro_avulso.py`** ou **`colher_vozes.py`** - cadastram a voz de cada pessoa.
   - `cadastro_avulso.py`: cadastro a partir de amostras de audio dedicadas.
   - `colher_vozes.py`: cadastro a partir dos clusters de uma reuniao ja rodada
     no `fase0.py` (nao precisa gravar amostra separada).
4. **`pipeline.py`** - pipeline completo: converte o audio, diariza, identifica os
   falantes pela voz (contra a galeria), transcreve e mede a dinamica da
   conversa, gerando um `.txt` legivel e um `.json` com os dados completos.
   Usa dois modulos de apoio:
   - **`termos.py`** + **`termos.txt`** - corrige vocabulario do dominio no
     transcript (nomes de ferramentas, jargao) por substituicao deterministica
     - a regra casa sem diferenciar maiuscula nem acento ("o Claudio" pega
     "o Cláudio") e o texto que entra e sempre o escrito na regra -
     porque o `initial_prompt` do Whisper so influencia os primeiros segundos
     do audio.
   - **`interacao.py`** - a partir da diarizacao NAO-exclusiva (que o pipeline
     normalmente descarta), mede sobreposicao de fala, interrupcao e apoio
     ("uhum", "sim"), e consolida a dinamica de cada falante (tempo de fala,
     quem interrompeu quem).
5. **`revisao.py`** - correcao humana: voce confirma ou corrige o nome de cada
   cluster (nao cada fala). Cada confirmacao realimenta o perfil de voz da
   pessoa, entao a proxima reuniao sai melhor.
6. **`calibrar.py`** - le os turnos ja gravados no `.json` do `pipeline.py` e
   reprocessa a analise de interacao com varios limiares, para escolher
   `MIN_SOBREPOSICAO` e `GAP_MESCLAGEM` com base no seu proprio audio em vez
   de aceitar o padrao do codigo.
7. **`ata.py`** - gera uma ata em portugues a partir do `.json`/`.txt` do
   `pipeline.py`, 100% offline via [Ollama](https://ollama.com/). Processa em
   blocos (uma reuniao inteira estoura a janela de contexto do modelo) e
   exige citacao literal do transcript para cada decisao e tarefa; depois de
   gerar, o script confere cada citacao contra o transcript original por
   comparacao de texto e marca as que nao encontrou.

## Requisitos

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) instalado e no PATH (`ffmpeg`/`ffprobe`)
- Um token de acesso do Hugging Face com aceite dos termos dos modelos
  `pyannote/speaker-diarization-community-1` e
  `pyannote/wespeaker-voxceleb-resnet34-LM`, exportado como `HF_TOKEN`
- Backend de transcricao:
  - `mlx-whisper` (padrao, requer Mac com Apple Silicon)
  - ou `faster-whisper` (`--asr faster`, funciona em qualquer plataforma)
- [Ollama](https://ollama.com/) instalado e rodando, apenas se for usar
  `ata.py` (ata local). Ver [Calibracao da ata local](#calibracao-da-ata-local)
  antes de escolher o modelo.

Instale as dependencias Python e crie o seu glossario a partir do exemplo
(o `termos.txt` real fica fora do git - e vocabulario da sua empresa; sem
ele, o app roda com o glossario vazio):

```bash
pip install -e ".[dev]"
cp termos.exemplo.txt termos.txt
```

## Uso tipico

```bash
export HF_TOKEN=seu_token_aqui

# 1. Verificar o ambiente (opcional, mas recomendado na primeira vez)
trama-verificar

# 2. Validar a diarizacao (opcional, mas recomendado na primeira vez)
python ferramentas/fase0.py reuniao.m4a --max-falantes 6

# 3. Cadastrar as vozes a partir dos clusters da fase0
python ferramentas/colher_vozes.py reuniao_fase0/fase0.json SPEAKER_00=Joao SPEAKER_01=Maria

# 4. Rodar o pipeline completo numa reuniao nova
trama-processar reuniao2.m4a --pessoas Joao,Maria,Pedro
#    --pessoas sozinho: um falante por nome (3 aqui). Se alguem estava na
#    sala mas talvez nao tenha falado, passe uma faixa - ela vale, e
#    --pessoas so restringe a comparacao de voz a esses nomes:
trama-processar reuniao2.m4a --pessoas Joao,Maria,Pedro --min-falantes 2 --max-falantes 3

# 5. Revisar e corrigir os nomes (realimenta os perfis de voz)
trama-revisar audios/reuniao_02/reuniao_02.json

# 6. Calibrar os limiares de interacao com o audio real
python ferramentas/calibrar.py audios/reuniao_02/reuniao_02.json --detalhe

# 7. Gerar a ata (opcional, requer Ollama rodando)
python experimental/ata.py audios/reuniao_02/reuniao_02.json
```

Sem galeria cadastrada, `pipeline.py` ainda funciona e gera a saida com rotulos
genericos (`SPEAKER_XX`) no lugar dos nomes.

## Aplicativo (servidor + frontend)

**Idioma:** a interface fala português ou inglês - Perfil > Configurações >
Idioma. Sem escolha, segue o idioma do navegador. A transcrição baixada
(.txt) sai no idioma escolhido; a fala das pessoas nunca é traduzida.

Marco 1: ler e revisar reunioes ja processadas pela tela, em vez da linha
de comando. Precisa de **duas abas de terminal** abertas ao mesmo tempo,
uma para o servidor e outra para o frontend - nenhuma delas fecha
sozinha, cada uma fica rodando e imprimindo log.

**Aba 1 - servidor** (a partir da raiz do projeto):

```bash
source .venv/bin/activate
trama-servidor --dev
```

Escuta em **http://127.0.0.1:8000**, so a API (`/api/...`). `python -m
servidor.app --dev` funciona igual - os dois sao equivalentes, nenhum
precisa de `PYTHONPATH`.

**`--dev` recarrega o servidor sozinho** quando qualquer `.py` do projeto
muda (`nucleo.py`, `pipeline.py`, `trama/servidor/`...). Sem ele, o servidor continua
rodando o codigo de quando foi aberto: toda rota nova responde 404 ate
alguem reiniciar - e a tela mostra "O servidor está desatualizado.
Reinicie o servidor e recarregue a página." Mudanca em `.json`, `.txt` ou
`audios/` nunca recarrega nada.

Cuidado com `--dev` durante um processamento iniciado pela tela: salvar um
`.py` nesse meio reinicia o servidor, e ao subir ele encerra o `pipeline.py` que
ficou orfao (o audio continua salvo; a reuniao aparece como interrompida e
da para tentar de novo). Para usar o app sem estar mexendo no codigo, rode
sem `--dev`.

**Aba 2 - frontend:**

```bash
cd frontend
npm install   # so na primeira vez
npm run dev
```

Escuta em **http://localhost:5173** (a porta padrao do Vite - se estiver
ocupada, ele avisa e sobe noutra). Abra essa URL no navegador; o Vite
encaminha as chamadas `/api/...` para a aba 1 (`vite.config.ts`), entao
nao precisa abrir a porta 8000 diretamente.

As duas abas precisam continuar abertas enquanto voce usa o app - feche
com `Ctrl+C` em cada uma quando terminar.

## Estrutura de `audios/`

Cada reuniao processada fica na sua propria pasta, `audios/reuniao_NN/`, com
tudo que pertence a ela junto:

```
audios/
└── reuniao_08/
    ├── reuniao_08.m4a       # audio original
    ├── reuniao_08.json      # dados completos (falas, dinamica, regioes sobrepostas)
    ├── reuniao_08.txt       # transcript legivel
    ├── reuniao_08_ata.md    # ata gerada pelo ata.py (se houver)
    └── fase0/               # amostras de audio por cluster, do fase0.py
```

O `.txt` e o que o `pipeline.py` gerou; para levar a transcricao para outro
lugar (colar numa IA, mandar por e-mail), use **Baixar transcricao (.txt)**
no detalhe da reuniao: o arquivo sai do `.json` na hora, com titulo, data,
duracao, quem participou e a revisao/glossario mais recentes.

Erro que o glossario nao deve corrigir em todas as reunioes (uma frase
que existe em portugues, mas que naquela fala era outra coisa) se corrige
na propria fala, no detalhe da reuniao: o lapis no fim do texto abre a
fala inteira para editar. Enter grava, Esc cancela.

Para um termo errado (um nome, uma sigla), selecione a palavra no texto e
use **Corrigir**: escreva o certo e escolha "So nesta fala" ou "Em todas
as reunioes e nas proximas" - antes de confirmar, o app mostra quantas
vezes e onde a troca vai acontecer. "O que e isso?" vira a descricao do
termo no vocabulario do `.txt`. Depois de corrigir em todas, o app mostra
formas parecidas do mesmo termo ("Talvez estas tambem sejam Aprovion"), cada
uma com o trecho em volta; so as marcadas sao corrigidas.

Na revisao, depois de salvar as vozes, vem **Termos para conferir**: ate 10
siglas e palavras em que a transcricao duvidou varias vezes, cada uma com o
trecho para ouvir e tres respostas - "Esta certo", "Corrigir para..." e
"Ignorar". Nenhuma e obrigatoria, e uma resposta dada nao e perguntada de
novo, nem nas proximas reunioes. A fala fica marcada como "editado a mao", o texto
transcrito continua guardado ("Voltar ao original"), e a correcao
sobrevive ao reprocessamento e ao glossario.

No fim do `.txt` baixado vem o **Vocabulario desta empresa**: os termos
da empresa, para a IA que ler o arquivo interpretar o que a transcricao
automatica errou. Em Perfil > **Termos da empresa**, cada termo tem o nome
certo, a descricao (curta, vai junto no vocabulario; termo sem descricao
mostra so o link "+ Adicionar descricao") e as formas erradas que ele ja
corrige, cada uma com um x para parar de corrigir. A mesma forma nunca
entra duas vezes no mesmo termo, sem diferenciar maiuscula nem acento. "Adicionar termo" pede so nome e descricao - serve para um termo
que a transcricao ainda nao errou. "Adicionar variacao" e a mesma correcao
"em todas as reunioes", com a previa antes.

Tudo fica no `termos.txt`, sem mudar o formato `errado => certo` que o
`pipeline.py` le: as descricoes e os termos sem correcao vao no fim, em linhas
`#= termo => descricao` (ou `#= termo`), que para ele sao comentario.

Nem toda reuniao tem todos os arquivos (por exemplo, `fase0/` so existe se
`fase0.py` foi rodado antes do `pipeline.py`).

## Variaveis de ambiente

| Variavel              | Padrao                                     | Descricao                                          |
|------------------------|---------------------------------------------|-----------------------------------------------------|
| `HF_TOKEN`             | -                                            | Token do Hugging Face para baixar os modelos        |
| `DIAR_MODEL`           | `pyannote/speaker-diarization-community-1`  | Modelo de diarizacao                                |
| `SIM_MIN`              | `0.60` (calibrado neste ambiente, ver abaixo) | Limiar de similaridade para aceitar um nome         |
| `MARGEM_MIN`           | `0.06`                                       | Margem minima entre 1o e 2o colocado                |
| `VOZES_DB`             | `vozes.db`                                   | Caminho do banco SQLite com os perfis de voz        |
| `REC_MEET_PORTA`       | `8000`                                       | Porta do servidor local (o endereco e sempre `127.0.0.1`) |
| `MIN_SOBREPOSICAO`     | `0.80`                                       | Duracao minima de sobreposicao para contar disputa  |
| `GAP_MESCLAGEM`        | `0.5`                                        | Pausa maxima para juntar dois segmentos do mesmo falante num turno |

`SIM_MIN`/`MARGEM_MIN` sao usados pelo `pipeline.py`; `MIN_SOBREPOSICAO`/
`GAP_MESCLAGEM` pelo `interacao.py` (e reproduzidos pelo `calibrar.py`). Use o
`calibrar.py` para validar os dois ultimos contra o seu proprio audio antes de
mudar o padrao do codigo.

## Calibracao

O padrao de `SIM_MIN` (0.60) reflete a calibracao ja observada NESTE ambiente
(ver numeros abaixo) - continua configuravel por variavel de ambiente para
quem calibrar num audio/mic diferente. Calibre com os numeros que aparecem
nas suas proprias reunioes (o `pipeline.py` imprime a matriz de similaridade
cluster x pessoa a cada execucao) antes de mudar o padrao do codigo.

Calibracao observada neste ambiente:

- `SIM_MIN=0.60`
- Base: 12 identificacoes ao longo de 3 reunioes reais (`reuniao_01`,
  `reuniao_03`, `reuniao_05`)
- Faixa de acerto observada: 0.832 a 0.935
- Maior falso positivo: 0.357
- Hardware: microfone interno do MacBook, posicionado na mesa

## Calibração da análise de interação

- `MIN_SOBREPOSICAO=0.80`, escolhido pelo ponto de inflexão da varredura do
  `calibrar.py` (a contagem de disputa fica travada em 77 até 0,60 e começa a
  cair em 0,80). Base: `reuniao_08`, 70 min, 4 falantes, 355 sobreposições
  brutas, p50=0,51s e p75=0,98s — ou seja, o volume das sobreposições está na
  faixa de transição normal de turno, não de fala simultânea.
- `GAP_MESCLAGEM=0.5` mantido apesar de a mediana das pausas internas ser
  1,43s. Aumentar para 0,80 reduz os turnos de 726 para 598, mas não altera a
  contagem de interrupção (51→52) e transfere eventos de interrupção para
  disputa (65→77). A fragmentação existe e não distorce as métricas.
- Validação: as três disputas mais longas (02:31 Luciano x Celso, 41:51 Amanda
  x Ramiro, 59:39 Ramiro x Amanda) foram confirmadas no áudio — fala
  simultânea real nos três casos, com a direção correta.

## Calibracao da ata local

`ata.py` roda 100% offline via Ollama. Dois modelos testados na mesma reuniao
(`reuniao_08`, 70 min, 4 falantes):

| Modelo               | Tempo    | Qualidade  | RAM       |
|----------------------|----------|------------|-----------|
| `llama3.1:8b`        | 2,4 min  | insuficiente | -       |
| `qwen3.8:27b-mlx`     | 19,6 min | boa        | ~18 GB    |

Conclusao: gerar ata localmente exige uma maquina forte (o modelo que produz
qualidade aceitavel precisa de ~18 GB de RAM e leva quase 20 minutos por
reuniao). Para um produto, o padrao deveria ser usar a API de LLM do proprio
cliente, com `ata.py`/Ollama como alternativa offline para quem tem hardware
para isso.

## Testes

`tests/` tem 15 suites, 367 testes no total. Cada arquivo roda com `python`, imprime PASSOU/FALHOU por caso e
sai com codigo de erro se algo falhar. As suites ignoram as variaveis de
ambiente de calibracao do seu shell (`SIM_MIN`, `MIN_SOBREPOSICAO`...):
testam sempre o padrao do codigo.

| Suite                     | O que cobre                                                        | Testes |
|---------------------------|---------------------------------------------------------------------|--------|
| `tests/test_pipeline.py`  | quebra de frase, juncao de texto, atribuicao INDEPENDENTE cluster->pessoa (`pipeline.identificar`), normalizacao de segmentos | 69 |
| `tests/test_interacao.py` | sobreposicao, interrupcao, apoio e dinamica (`interacao.py`)        | 22 |
| `tests/test_termos.py`    | correcao de vocabulario (`termos.py`)                               | 33 |
| `tests/test_ata.py`       | verificacao de citacoes da ata (`ata.py`)                           | 29 |
| `tests/test_review.py`    | ledger de contribuicoes de voz, idempotencia e migracao (`nucleo.py`/`revisao.py`) | 22 |
| `tests/test_migracoes.py` | migracoes versionadas do `vozes.db` (`trama/migracoes/`)                  | 9 |
| `tests/test_servidor_*.py` | rotas da API em seis suites por area: reunioes, pessoas, transcricao, revisao, processo, termos (`trama/servidor/`) | 140 |
| `tests/test_gancho_commit_msg.py` | o gancho `ganchos/commit-msg` tira coautor e assinatura | 5 |
| `tests/test_paleta.py`    | cores de voz distintas entre si e dos papeis de cor, com daltonismo simulado; contraste dos papeis, dos tons de tinta e do texto sobre o destaque (`tokens.css`) | 19 |
| `tests/test_identidade.py` | toda fonte empacotada tem o OFL dela em `public/licencas/`; nenhum texto de tela promete ata; `--tinta-apagada` so no numero da reuniao; `lang="pt-BR"`; Fio so como fundo; papel de cada fonte; logotipo e favicon nas cores da marca; nome "Trama" na interface | 17 |

Rodar uma suite:

```bash
python tests/test_interacao.py
```

Rodar todas:

```bash
for f in tests/test_*.py; do python "$f"; done
```

`tests/test_pipeline.py`, `tests/test_interacao.py` e `tests/test_review.py`
importam `numpy`/`torch` - rode dentro do venv do projeto se estiver fora
dele.

## Atribuicao de terceiros

Este projeto usa modelos e bibliotecas de terceiros (pyannote,
wespeaker-voxceleb, Whisper) sob licencas que exigem atribuicao. Ver
[`ATRIBUICAO.md`](../ATRIBUICAO.md) para as licencas, citacoes obrigatorias e os
pontos que precisam de revisao juridica antes de qualquer uso comercial
(a licenca do embedding de falante e as implicacoes de LGPD sobre os perfis
de voz, em particular).

## Notas

- A galeria de vozes fica num banco SQLite local (`vozes.db` por padrao) -
  nao versione esse arquivo, ele contem embeddings de voz das pessoas.
- Cadastre ou colete (`colher_vozes.py`) amostras de voz na mesma sala e com o
  mesmo microfone das reunioes reais: o embedding captura o canal acustico
  junto com a voz.

## Aprendizado dos perfis de voz (ledger de contribuicoes)

Cada correcao no `revisao.py` fica registrada individualmente por
reuniao+cluster (tabela `contribuicoes`), nao mais somada direto no perfil
agregado. Isso torna a revisao **idempotente** (revisar a mesma reuniao de
novo com a mesma resposta nao infla o peso) e **corrigivel** (mudar a pessoa
de um cluster move a contribuicao de um perfil para o outro, recalculando os
dois).

O que ja estava no banco (`pessoas`) antes desta mudanca e preservado numa
tabela separada, `pessoas_legado`, congelada UMA UNICA VEZ na primeira
conexao apos a atualizacao - o perfil atual de cada pessoa passa a ser
`pessoas_legado + soma das contribuicoes de reuniao`. Nada do que ja existia
e perdido, mas tambem nao ha como saber retroativamente de qual reuniao
antiga veio cada segundo de fala ja acumulado - o banco antigo so guardava a
media, nao a procedencia.

**Backup automatico:** a primeira vez que qualquer script conectar a um
`vozes.db` que ainda nao tem a tabela `contribuicoes`, o banco inteiro e
copiado para `vozes.db.bak-pre-contribuicoes-<timestamp-UTC>` antes de
qualquer alteracao de schema. **Para restaurar:** pare tudo e copie esse
arquivo de volta por cima do `vozes.db` atual (`cp vozes.db.bak-pre-contribuicoes-AAAAMMDDThhmmssZ vozes.db`).

Cadastro manual (`cadastro_avulso.py`/`colher_vozes.py`) continua funcionando como antes -
ele atualiza a base legada (nao o ledger), entao um cadastro novo nao se
perde no proximo recalculo de uma contribuicao de reuniao.
