# ARCHITECTURE.md

Como o sistema é hoje. Estado em 20 de setembro de 2026.
Por que é assim: `docs/adr/`. Como rodar: `docs/uso.md` (visão geral em
inglês: `README.md`).

O produto se chama **Trama** (ADR 0023), também por dentro: pacote
`trama`, variáveis `TRAMA_*`, chaves `trama:*` do `localStorage`, skill
`identidade-trama` (ADR 0027). As chaves antigas `rec-meet:*` são copiadas
para as novas na primeira abertura (`armazenamento/migrarChaves.ts`).

Este arquivo descreve o que existe. Quando o código mudar, ele muda junto —
um item aqui que não corresponde ao código é bug de documentação.

---

## Forma geral

```
áudio (.m4a do celular, sobre a mesa)
   ↓
pipeline Python (local, offline)
   ↓
reuniao_NN.json  ← fonte de verdade completa
   ↓                    ↘
reuniao_NN.txt      servidor local → navegador
```

O `.json` é o contrato. Tudo que a interface mostra sai dele: falas,
timestamps, similaridade, dinâmica, eventos, regiões sobrepostas, turnos
brutos, confiança da transcrição, lacunas sem texto. Nada é recalculado a
partir do áudio para exibir.

---

## Pipeline (existe, em produção de uso próprio)

### Módulos

Pacote `trama/` (ADR 0025). Nenhum script Python na raiz.

| Arquivo | Papel |
|---|---|
| `trama/nucleo.py` | embeddings de voz (pyannote) + banco SQLite dos perfis |
| `trama/pipeline.py` | pipeline completo, 5 etapas (`processar()`) |
| `trama/revisao.py` | correção humana + realimentação dos perfis (a mesma lógica para a CLI e para a tela) |
| `trama/interacao.py` | sobreposição, interrupção, apoio, dinâmica |
| `trama/edicao.py` | correção manual do texto de uma fala: guarda o original e as marcas de posição, desfaz, e reaplica as correções nas falas novas ao reprocessar (ADR 0016) |
| `trama/trechos.py` | trechos para conferir (ADR 0028): escolhe até 3 falas de confiança baixa e 2 lacunas, grava o texto escrito dentro da lacuna e "não dá para entender", e reaplica as respostas ao reprocessar, casando pelo tempo |
| `trama/temporarios.py` | a cópia WAV 16 kHz do áudio, numa pasta temporária própria (`trama-wav-…`, com o PID do dono): o pipeline apaga ao terminar (sucesso, falha ou cancelamento — o `SIGTERM` vira saída normal na CLI); o servidor varre as órfãs, de dono morto ou do formato antigo `tmpXXXX/<nome>_16k.wav`, ao terminar cada processamento e ao iniciar |
| `trama/termos.py` + `termos.txt` | correção determinística de vocabulário; casa sem diferenciar maiúscula nem acento (`sem_acento`, caractere a caractere, mesmo comprimento — as posições do casamento valem no texto original). `termos.txt` é dado do usuário, fora do git; versionado só `termos.exemplo.txt` |
| `trama/migracoes/` | migrações versionadas do `vozes.db` (ADR 0006) |
| `trama/servidor/` | API FastAPI local (ADR 0004) |
| `trama/cli/` | `trama-processar`, `trama-revisar`, `trama-verificar` (e `trama-servidor`, em `trama/servidor/app.py`) |
| `ferramentas/fase0.py` | só diarização + amostras de áudio por cluster |
| `ferramentas/amostras.py` | trechos de UM cluster já processado, espalhados no tempo, sem piso de duração - para ouvir contaminação que a revisão descarta |
| `ferramentas/colher_vozes.py` | galeria a partir de reuniões já rodadas (ADR 0011) |
| `ferramentas/calibrar.py` | varredura offline de limiares |
| `ferramentas/gerar_demo.py` | dados de demonstração em dois conjuntos (`audios-demo/pt`, `audios-demo/en`), pelas funções reais do pipeline; roteiros em `roteiro_demo.py` e `roteiro_demo_en.py` |
| `experimental/ata.py` | ata local via Ollama (fora do MVP, ver ADR 0002) |
| `experimental/cadastro_avulso.py` | galeria a partir de amostras dedicadas (descartado, ADR 0011) |

### As 5 etapas do `pipeline.py`

1. `nucleo.to_wav16k` — ffmpeg para WAV 16 kHz mono, numa pasta temporária
   própria que `pipeline.processar` apaga no fim (`trama/temporarios.py`;
   o campo `wav16k` do `.json` guarda o caminho, que deixa de existir)
2. `diarizar` — pyannote `speaker-diarization-community-1`, devolve a versão
   exclusiva **e** a não-exclusiva
   Quantos falantes procurar sai de `faixa_de_falantes`: `--falantes` fixa;
   senão `--min-falantes`/`--max-falantes` valem como faixa, mesmo com
   `--pessoas` (que aí só restringe a galeria comparada); sem nenhum dos
   dois, o número de nomes em `--pessoas` vira o número exato.
3. `identificar` — embedding médio por cluster, cosseno contra a galeria,
   imprime a matriz cluster × pessoa
4. `interacao.analisar` — usa a diarização **não-exclusiva**, que o pipeline
   normalmente descartaria
5. `transcrever` (Whisper large-v3 via MLX) → `alinhar` (palavra → falante,
   consolidado por frase, turnos com `GAP_TURNO = 2.0 s`) →
   `termos.aplicar_em_falas` → `edicao.preservar_edicoes` → `.txt` + `.json`

Correção feita à mão no Detalhe (ADR 0016) sobrevive ao reprocessamento:
`edicao.preservar_edicoes`, relendo o `.json` do disco depois da
transcrição (como o título), casa cada correção com a fala nova que tem
mais tempo em comum — metade de cada uma no mesmo trecho. Na fala casada,
o texto novo da máquina vira `edicao_manual.texto_original`. Correção sem
fala correspondente vai para `edicoes_sem_fala`, com um aviso, e volta se
um reprocessamento futuro achar a fala. `termos.aplicar_em_falas` pula
fala com `edicao_manual` — no `pipeline.py` e ao reaplicar o glossário.

Antes disso, `trechos.preservar` faz o mesmo com as respostas dos trechos
para conferir (ADR 0028): o texto escrito numa lacuna (`texto_manual`) e o
"não dá para entender" (`ininteligivel`, na lacuna ou na fala) vão para a
lacuna/fala nova com metade do tempo em comum. Texto de lacuna sem par vai
para `lacunas_sem_lugar`, com aviso, e volta num reprocessamento futuro.
Roda antes de `preservar_edicoes` para a lacuna respondida dentro de uma
fala corrigida viajar com ela. `montar_texto_txt` (o `.txt` do disco) e o
`.txt` baixado põem o texto da lacuna no ponto dela
(`trechos.texto_com_lacunas_escritas`); o texto da fala e as posições das
marcas nunca mudam.

`alinhar()` também grava, por fala, `confianca_media` (probabilidade média
das palavras) e `palavras_baixa_confianca` (abaixo de
`LIMIAR_PALAVRA_BAIXA_CONFIANCA`, só registro - nunca marca isolada na
tela), e devolve `lacunas_sem_texto` (trechos acima de `LIMIAR_LACUNA_S`
sem nenhum token, dentro de um turno ativo). Depende do resultado da
etapa 4: a checagem de "turno ativo" usa `analise["turnos_brutos"]`
(diarização **não-exclusiva**), não a exclusiva usada no resto do
alinhamento - a exclusiva força um falante por instante e, durante fala
sobreposta, pode alternar o desempate entre duas pessoas por artefato do
algoritmo, sem que nenhuma tenha parado de falar. Ver ADR 0010.

`alinhar()` grava ainda, por fala, `palavras_tempo`: `[posição,
comprimento, início, fim]` de cada palavra, com a posição em caracteres
dentro de `texto` (a mesma convenção das outras marcas). É o que permite
marcar, palavra por palavra, o trecho de uma fala que caiu numa região de
sobreposição. `termos.aplicar_em_falas` desloca as quatro listas com
posição (`palavras_divergentes`, `palavras_baixa_confianca`,
`palavras_tempo` e as lacunas); nas palavras que uma regra reescreve,
`palavras_tempo` funde num intervalo só, em vez de perder o horário. No
disco, `nucleo.json_para_disco` põe cada lista numérica numa linha (mesmo
JSON, só o espaço muda) — sem isso, quatro linhas por palavra.

**Data e título da reunião.** `montar_saida` grava `data_reuniao` (UTC,
`...Z`) e `data_origem`: `"gravacao"` é o `creation_time` dos metadados do
áudio — o iPhone grava ali o início da gravação (conferido nas dez
reuniões reais) —, `"arquivo"` é só a data de modificação do arquivo, que
a tela mostra como "chegou em", nunca como data da reunião
(`nucleo.data_da_gravacao`, ffprobe com stdin fechado). O `titulo`, quando
existe, também vai no `.json`; numa reunião ainda sem `.json` (título dado
na Nova reunião), fica em `meta.json` na pasta dela até o `pipeline.py`
incorporar. `pipeline.preservar_metadados` mantém os dois ao reprocessar, como
o `reuniao_id` e a revisão. Para reunião sem esses campos no `.json` (ou
sem `.json`), o servidor lê a data do áudio com cache em
`.data_cache.json`, mesma chave (tamanho + mtime) do cache de duração. A
preservação é testada rodando o `trama.cli.processar.main()` inteiro duas vezes (só
diarização, identificação e transcrição trocadas por dublês), com os
clusters renumerados entre as rodadas e um título editado no meio da
segunda: `test_pipeline.py`, `test_reprocessar_reuniao_com_titulo...` e
`test_titulo_editado_durante_o_reprocessamento...`.

O prefixo de saída é o caminho do áudio sem extensão. Sem `--out`, os
arquivos caem ao lado do `.m4a`.

### Identificação: por cluster, não por trecho

O sistema não compara cada frase com a galeria. Ele junta 60–120 s de fala de
cada cluster, tira a média dos embeddings ponderada pela duração, e compara o
**cluster inteiro**. Um trecho de 2 s gera embedding instável; a média de um
cluster é dramaticamente mais estável.

Atribuição **gulosa**, não exclusiva: uma pessoa pode legitimamente ocupar
dois clusters. Abaixo de `SIM_MIN` ou com margem apertada, a saída é
`DESCONHECIDO_<label>` — o sistema não chuta.

### Banco de vozes (`vozes.db`, SQLite, não versionado)

| Tabela | Conteúdo |
|---|---|
| `pessoas` | perfil atual recalculado (chave: nome) |
| `pessoas_legado` | congelamento único do que existia antes do ledger |
| `contribuicoes` | ledger por (reuniao_id, cluster) |

Perfil atual = `pessoas_legado` + soma das contribuições. Isso torna a
revisão **idempotente** (revisar de novo não infla o peso) e **corrigível**
(mudar a pessoa de um cluster move a contribuição e recalcula os dois perfis).

`cadastro_avulso.py` e `colher_vozes.py` escrevem na base legada, não no ledger.

**Limitação conhecida: `pessoas_legado` não tem proveniência.** As colunas
são `nome`, `embedding`, `peso` e `migrado_em` (a data da migração do ADR
0006, não a data de criação do perfil). Não há `reuniao_id`, nem registro
de qual script escreveu (`colher_vozes.py`, `cadastro_avulso.py` ou uma versão antiga do
pipeline). Para qualquer pessoa cujo perfil já existisse antes do ledger
(16/set/2026), **não há como saber hoje de qual reunião ou amostra o peso
agregado veio** — só dá para verificar se o perfil *atual* é legítimo
comparando por cosseno contra uma amostra de áudio conhecida (como foi
feito para o caso do Rolando: `SPEAKER_01` de `reuniao_06`/`reuniao_07`,
0,97+ de similaridade). Isso não é uma lacuna recuperável — a informação
nunca foi capturada; é estrutural em como a base legada foi desenhada
(congela só o agregado, de propósito, porque não dá pra inventar
procedência que não existia no schema anterior ao ADR 0006).

### Calibração, e de onde cada número veio

| Variável | Valor | Origem |
|---|---|---|
| `SIM_MIN` | 0.60 | meio do vale entre o maior falso positivo e o menor acerto, em 20 identificações ao longo de 5 reuniões |
| `MARGEM_MIN` | 0.06 | padrão, nunca precisou ajuste |
| `MIN_SOBREPOSICAO` | 0.80 | ponto de inflexão da varredura do `calibrar.py` |
| `MIN_SOBREPOSICAO_APOIO` | 0.15 | limiar separado: um "uhum" de 0,4 s nunca passaria de 0,80 |
| `GAP_MESCLAGEM` | 0.5 | mantido apesar de p50 das pausas internas ser ~1,5 s |
| `LIMIAR_PALAVRA_BAIXA_CONFIANCA` | 0.5 | dado pela decisão, não medido - só registro (nunca vira marca isolada) |
| `LIMIAR_CONFIANCA_FALA` | 0.60 | decisão de produto (marca ~6% das falas), não descoberta na medição - a distribuição é unimodal e crescente, sem vale como a do `SIM_MIN`. Ver ADR 0010 |
| `MIN_PALAVRAS_CONFIANCA_FALA` | 4 | medido: sem piso, 23 de 45 falas marcadas eram bordões de 1-3 palavras sem média de verdade. Ver ADR 0010 |
| `LIMIAR_LACUNA_S` | 0.8 | dado pela decisão, não medido |
| `TOLERANCIA_LACUNA_S` | 0.05 | folga numérica de arredondamento, não parâmetro de ajuste |

Faixa observada de acerto: 0,834 a 0,972. Maior falso positivo: **0,489**
(Celso contra o `SPEAKER_02` da `reuniao_02`, reprocessada em 2026-09-24;
o cluster foi atribuído a Luciano com 0,871, margem de 0,382). Antes
dele, o maior era 0,434 (Celso contra o cluster do Ramiro, reuniao_09).
O vale entre o maior falso positivo e o menor acerto encolheu de 0,400
para 0,345, e o falso positivo ficou a 0,111 do `SIM_MIN`. `SIM_MIN` não
foi recalibrado por isso.

**Provavelmente não é distância entre duas vozes puras.** O padrão é o
mesmo do `SPEAKER_02` da `reuniao_06` (ver "Verificação de pureza de
cluster" em Fronteiras): identidade dominante clara, segundo colocado
alto justamente em Celso. Se o cluster tiver trechos do Celso misturados,
o 0,489 mede em parte a voz do próprio Celso dentro do cluster, não o
quanto Luciano e Celso se parecem. Pendente de escuta: 10 trechos
espalhados exportados com `amostras.py` em
`audios/reuniao_02/amostras_SPEAKER_02/` (38 turnos no cluster, 21
abaixo de 2s). Até a escuta, vale como o maior falso positivo medido.
Os pares Ramiro/Celso e Luciano/Celso são o ponto mais fraco da galeria
e é onde um erro apareceria primeiro.

**Variação da mesma pessoa entre reuniões diferentes, mesmo aparelho e
mesma sala:** medido comparando o embedding do cluster de Celso, Luciano
e Amanda em pares de reuniões onde cada um aparece (reuniao_06/07/09,
mesmo iPhone, mesma sala, dias diferentes, posicionamento na mesa
provavelmente diferente) - vai de 0,843 (Amanda, 09×06) a 0,947 (Celso,
06×07). Essa variação é da MESMA ORDEM DE GRANDEZA que a distância entre
`SIM_MIN` (0,60) e o piso da faixa de acerto (0,834) - **é a fonte de
erro dominante do sistema, não a distinção entre pessoas diferentes**: o
maior falso positivo (0,434 na época desta medição; 0,489 depois, ver
acima) fica bem mais longe de `SIM_MIN` do que o
par mais fraco de mesma pessoa (0,843) fica do piso da própria faixa de
acerto. Motivou a decisão de não colher perfil de voz por gravação avulsa
fora da reunião - ver ADR 0011.

Todas configuráveis por variável de ambiente. Recalibração é offline:
`python ferramentas/calibrar.py <arquivo>.json --detalhe`.

### Desempenho medido

Uma máquina só: MacBook Pro M3 Max, 64 GB, MPS + mlx-whisper.

- Reunião de 70 min: cerca de 6 min de processamento, do começo ao fim.
- Embedding de voz, áudio de 70 min: 18 s no MPS contra 6 min 28 s no
  processador (`--device cpu`), 21× mais lento, na mesma máquina. Fonte:
  relatório do projeto de 5 de setembro de 2026, seção de performance.
- Ata local (`experimental/ata.py`, fora do produto), `reuniao_08`, 70 min,
  4 falantes: `llama3.1:8b` 2,4 min (qualidade insuficiente);
  `qwen3.8:27b-mlx` 19,6 min, ~18 GB de memória (qualidade boa). Detalhes
  em `docs/uso.md`.

Não testado: outros Macs, PC com GPU NVIDIA, máquina só com processador.
Memória mínima sugerida (16 GB) é estimativa, não medição.

### Testes

21 suítes, 416 casos. Cada arquivo roda sozinho com `python` (imprime
PASSOU/FALHOU por caso e sai com código de erro), e o `pytest` descobre as
mesmas funções `test_*` sem nenhuma mudança. As suítes do servidor dividem
a infraestrutura em `tests/servidor_apoio.py`.

| Suíte | Casos |
|---|---|
| `test_ata.py` | 29 |
| `test_codigos_de_erro.py` | 4 |
| `test_demo.py` | 5 |
| `test_gancho_commit_msg.py` | 5 |
| `test_identidade.py` | 19 |
| `test_interacao.py` | 22 |
| `test_migracoes.py` | 9 |
| `test_paleta.py` | 19 |
| `test_pipeline.py` | 72 |
| `test_review.py` | 24 |
| `test_servidor_apagar.py` | 7 |
| `test_servidor_pessoas.py` | 13 |
| `test_servidor_origem.py` | 5 |
| `test_servidor_processo.py` | 23 |
| `test_servidor_reunioes.py` | 46 |
| `test_servidor_revisao.py` | 17 |
| `test_servidor_termos.py` | 33 |
| `test_servidor_transcricao.py` | 15 |
| `test_servidor_trechos.py` | 10 |
| `test_temporarios.py` | 3 |
| `test_termos.py` | 36 |

Toda suíte chama `tests/_ambiente.py` antes de importar o projeto: tira do
ambiente as variáveis que o código lê (limiares, `VOZES_DB`,
`TRAMA_*`), para o resultado nunca depender do shell de quem roda, e
troca a pasta temporária por uma só da execução (`TMPDIR`, herdada pelos
subprocessos), apagada no fim — a varredura de cópias WAV órfãs nunca
roda na pasta temporária de quem usa a máquina.
Teste que sobe o servidor de verdade usa porta efêmera, nunca a 8000.

`test_pipeline`, `test_interacao` e `test_review` importam numpy/torch —
rode dentro do venv.

---

## Aplicativo (a construir)

### Forma

```
navegador (React + Vite + TypeScript)
        ↕  HTTP em 127.0.0.1
servidor local (FastAPI)
        ↓  importa os módulos existentes
pipeline.py / nucleo.py / revisao.py / interacao.py
        ↓
audios/  +  vozes.db
```

O servidor é casca fina. Nenhuma lógica de pipeline é reimplementada em
Python novo nem em TypeScript. Ver ADR 0004.

Sem autenticação, rate limit nem multiusuário (ADR 0030): uma pessoa, uma
máquina, a fronteira é a conta do sistema operacional mais o bind em
`127.0.0.1`. Para que só o próprio app fale com o servidor,
`servidor/origem.py` confere toda requisição antes da rota: `Host`
`127.0.0.1`/`localhost` na porta do servidor (DNS rebinding) e `Origin`
ausente ou dessas duas máquinas na porta do frontend
(`TRAMA_PORTA_FRONTEND`, padrão 5173) ou do servidor (upload enviado por
outro site aberto no mesmo navegador). Fora disso, 403 com código. O Vite
roda com `strictPort` nessa porta.

### Rotas previstas

| Rota | Papel | Marco |
|---|---|---|
| `GET /api/reunioes` | lista o que existe em `audios/` | 1 |
| `GET /api/reunioes/{id}` | devolve o `.json` da reunião | 1 |
| `GET /api/reunioes/{id}/audio?inicio=&fim=` | trecho recortado para a revisão | 1 |
| `POST /api/reunioes/{id}/revisao` | grava os nomes, realimenta os perfis | 1 |
| `POST /api/reunioes/{id}/revisao/previa` | o que a revisão tiraria de voz já aprendida, sem gravar | 3 |
| `GET /api/pessoas` | galeria cadastrada | 1 |
| `GET /api/busca?q=` | trecho da fala: por reunião, as falas com TODAS as palavras (sem acento, sem maiúscula), com quem falou, horário e as posições a destacar no texto original (`trama/servidor/busca.py`) | 3 |
| `PUT /api/reunioes/{id}/titulo` | título da reunião (até 120, sem caractere de controle; vazio volta a "Reunião NN"); no `.json`, ou no `meta.json` se ainda não há `.json`; escrita atômica | 3 |
| `PUT /api/reunioes/{id}/falas/{indice}` | texto de uma fala corrigido à mão (`edicao.py`, ADR 0016): corpo `{texto, inicio}`; `inicio` diferente do da fala naquele índice → 409 (reprocessada no meio); texto vazio, com quebra de linha ou acima de 5000 → 400. Grava `.json` e `.txt` (temporários antes de confirmar os dois). Devolve `{fala, lacunas_sem_texto}` | 3 |
| `DELETE /api/reunioes/{id}/falas/{indice}/edicao?inicio=` | desfaz a correção: texto transcrito e as marcas de posição de volta | 3 |
| `GET /api/reunioes/{id}/transcricao` | transcrição em `.txt` gerada na hora do `.json` (nunca o `.txt` do pipeline, que não tem título e fica velho depois de revisão/glossário): cabeçalho com título, data, duração e % de fala; uma linha `[mm:ss] Nome: texto` por fala; voz sem pessoa como na tela; sem marca de interface; no fim, "Vocabulário desta empresa" com os termos do glossário (lado certo sem artigo/preposição do começo, sem repetição) e a descrição de cada um, quando existe. `Content-Disposition` com `filename*` UTF-8 (`trama/servidor/transcricao.py`) | 3 |
| `POST /api/reunioes` | recebe o áudio, cria a pasta (não processa) | 2 |
| `POST /api/reunioes/{id}/processar` | dispara o `pipeline.py` como subprocess. Corpo `{pessoas, talvez_calados}`: das pessoas, quem "estava, mas talvez não tenha falado" vira a faixa de falantes que o pipeline já aceita junto com `--pessoas` — N pessoas e K marcadas dão `--min-falantes N-K --max-falantes N` (só o teto se K = N); sem marca, N exato (`processamento.argumentos_de_falantes`). As duas listas ficam no estado do processamento para o "Tentar novamente" | 2 |
| `POST /api/reunioes/{id}/cancelar` | mata o subprocess, preserva o áudio | 2 |
| `GET /api/reunioes/{id}/progresso` | SSE com as 5 etapas | 2 |
| `GET /api/termos` / `PUT /api/termos` | glossário (`termos.txt`) como lista ordenada de regra/texto, mais `descricoes` (`{termo: descrição}`, até 120 caracteres) guardadas no fim do mesmo arquivo como `#= termo => descrição` — comentário para o `pipeline.py` (ADR 0017); termo sem regra entra só no vocabulário (ADR 0018); PUT valida tudo antes e grava atômico; sem `descricoes` no corpo, mantém as gravadas | 3 |
| `POST /api/correcoes/previa` / `POST /api/correcoes` | corrigir um trecho selecionado em todas as reuniões e nas próximas (`trama/servidor/correcao.py`, ADR 0019): prévia com as ocorrências (reunião, fala, horário, contexto) e uma assinatura; a gravação insere a regra no `termos.txt` na posição que não deixa nenhuma regra mais geral capturar o trecho antes (aviso só se impossível) e aplica só ela, recusando com 409 se algo mudou | 3 |
| `POST /api/correcoes/variacoes` / `POST /api/correcoes/variacoes/aplicar` | depois de uma correção em todas: formas parecidas do termo, com até 3 contextos cada (critério no ADR 0020, sem dicionário), e a correção só das formas marcadas, com assinatura | 3 |
| `GET /api/reunioes/{id}/termos-para-conferir` | revisão de termos (ADR 0022): até 10 siglas e dúvidas repetidas, mais frequentes primeiro, cada uma com o trecho e o intervalo de áudio | 3 |
| `GET /api/reunioes/{id}/trechos-para-conferir` | trechos para conferir (ADR 0028): até 3 falas de confiança baixa e 2 lacunas de 1,5 s ou mais, as mais longas, na ordem da reunião, com o intervalo de áudio | 3 |
| `PUT /api/reunioes/{id}/lacunas` | `{inicio, fim, texto}`: o que foi dito numa lacuna, gravado dentro dela (achada pelo tempo; não achou → 409 `trecho_mudou`). Mesma validação do texto de fala. Grava `.json` e `.txt` | 3 |
| `PUT /api/reunioes/{id}/ininteligivel` | `{tipo, inicio, fim, indice?}`: "Não dá para entender" numa fala (com índice e início, como a correção) ou lacuna — nunca perguntada de novo | 3 |
| `POST /api/termos/respondido` | "Ignorar" (ou corrigido só numa fala): grava `#! forma` no `termos.txt`, nunca mais perguntada | 3 |
| `PUT /api/termos/descricao` | descrição de um termo ("O que é isso?"); vazia mantém o termo conhecido | 3 |
| `GET` / `POST` / `DELETE /api/termos/empresa` | Termos da empresa (ADR 0021): os termos agrupados (nome, descrição, variações), adicionar termo (só nome e descrição; sem regra vira `#= termo`), remover termo (com descrição e variações). A mesma variação no mesmo termo (sem diferenciar maiúscula, acento nem espaçamento) nunca é gravada duas vezes: `glossario.escrever` fica com a primeira, a única que dispara | 3 |
| `DELETE /api/termos/variacao?errado=` | para de corrigir uma variação; o que já foi corrigido nas reuniões continua | 3 |
| `GET /api/termos/reaplicar` / `POST /api/termos/reaplicar` | prévia (quantas substituições, em quais reuniões, e uma assinatura) e gravação do glossário salvo nas reuniões já processadas; POST só aceita a assinatura da prévia (409 se algo mudou) | 3 |
| `GET /api/sistema` | versão, dispositivo/motor detectados, caminhos dos dados, licenças do `ATRIBUICAO.md` (somente leitura) | 3 |
| `GET /api/reunioes/{id}/exclusao` | prévia de apagar a reunião: quanto de voz cada pessoa perde, quanto fica e se sai da galeria (`nucleo.perdas_ao_excluir_reuniao`) — nada apagado | 3 |
| `DELETE /api/reunioes/{id}` | apaga a reunião (ADR 0029): primeiro as contribuições dela no ledger, numa transação, com os perfis recalculados e `VACUUM`; depois a pasta inteira (rename atômico para `.apagando-…`, fora do padrão de id, e então remoção) e a cópia WAV temporária, só se o caminho cai na pasta temporária do sistema. Reunião processando → 409 (`processamento.com_reuniao_parada`, a mesma trava do processamento) | 3 |
| `DELETE /api/pessoas/{nome}` | exclusão de perfil de voz (LGPD): perfil, contribuições no ledger e base legada numa transação, depois `VACUUM` | 3 |
| `GET /api/pessoas/participacao` | voz aprendida e participação de cada pessoa, reunião a reunião (`trama/servidor/pessoas.py`) | 3 |

Em desenvolvimento o servidor sobe com `trama-servidor --dev`
(recarga do uvicorn, só `*.py`, sem `.venv`/`frontend`/`audios`/`tests`).
No frontend, `api/cliente.ts:mensagemDeErro` nunca deixa o texto padrão do
FastAPI em inglês chegar à tela: `404 "Not Found"`/`405 "Method Not
Allowed"` (rota que nem existe no servidor rodando) viram "O servidor está
desatualizado…"; toda 404 de propósito das rotas tem `detail` em
português.

O `id` da reunião é o nome da pasta (`reuniao_09`), validado contra
`^[a-z0-9_-]+$` antes de tocar o disco.

Todas as rotas do marco 1 e as quatro do marco 2 listadas acima já estão
implementadas (`trama/servidor/`) — falta só a parte de tela (Nova reunião,
tela de processamento, botões "Processar" da Lista ligados nas rotas).
O trecho de áudio é limitado a 120s (`DURACAO_MAXIMA_TRECHO_S` em
`trama/servidor/app.py`) — a revisão pede segundos, não a reunião inteira, e
sem teto um `fim` grande materializaria o áudio todo como WAV na memória
do servidor.

`POST /api/reunioes` aceita `.m4a`/`.mp3`/`.wav` até 500MB
(`trama/servidor/upload.py`), grava em streaming (nunca o upload inteiro na
memória) e só confirma o nome final se coube no limite inteiro. O nome
do arquivo enviado pelo cliente nunca vira caminho — só decide a
extensão aceita; o nome salvo em disco é sempre `reuniao_NN.<ext>`
gerado pelo servidor, com `NN` decidido por `mkdir` exclusivo (atômico
no SO, sem corrida entre dois uploads simultâneos).

`POST /api/reunioes/{id}/processar` e `POST /api/reunioes/{id}/cancelar`
disparam e param o `pipeline.py` como **subprocess** (nunca import — um
crash do pipeline não pode derrubar o servidor), com `--device`/`--asr`
detectados automaticamente (`processamento.detectar_device_e_asr()`:
MPS disponível usa `mps`+`mlx`, senão `cpu`+`faster` — a máquina do
cliente pode não ser Apple Silicon). Só um processamento por vez
(`trama/servidor/processamento.py`): uma segunda chamada enquanto outra
reunião está rodando recebe 409. Cancelar preserva o áudio no disco —
mesmo princípio de uma falha (ver abaixo): tentar de novo nunca pede
novo upload.

`GET /api/reunioes/{id}/progresso` é SSE: o estado do processamento
vive no SERVIDOR (memória do processo), não na conexão, então reabrir a
aba reconecta e recebe o estado atual imediatamente, sem perder
contexto. O progresso sai do stdout do `pipeline.py`, lido por uma única
thread do servidor (nunca duas conexões lendo o mesmo pipe). O servidor
roda o pipeline com `--progresso-json`, e cada etapa imprime, além da
frase "N/5  texto..." para quem lê o terminal, uma linha `@progresso
{"etapa", "total", "detalhe"}` (`pipeline._progresso`). O servidor lê só
essa (`processamento.ler_progresso`, que deixa passar só os campos
conhecidos: `falantes`, `min`, `max`, `termos`, `asr`) — nunca a frase,
que muda de idioma. A tela monta o texto da etapa no idioma dela.

Sobrevivência a reinício do servidor: um marcador (`.processando.json`,
na pasta da própria reunião) é gravado ao iniciar e apagado quando o
servidor **vê** o processamento terminar (sucesso, erro ou
cancelamento). Se o servidor cair no meio, o marcador sobra sem ninguém
cuidando dele; a inicialização seguinte tenta encerrar o processo órfão
(best-effort, nunca falha a subida do servidor por causa disso) e a
reunião aparece como `interrompido` — nunca fingindo `nao_processada`
(seria esconder que já foi tentada) ou `completa` (não há `.json`).

`POST /api/reunioes/{id}/revisao` é a ÚNICA rota que escreve no
`vozes.db`. Não reimplementa o ledger: `trama/servidor/revisao.py` chama
`revisao.decidir_contribuicao()` e `revisao.aplicar_e_gravar()` — as MESMAS
funções que `revisao.py` (CLI) usa, extraídas de lá para isto. Nenhum SQL
novo; a única escrita continua sendo `nucleo.registrar_contribuicoes()`.

Corpo: `{"nomes": {cluster_label: nome}}`. Nome vazio mantém o nome atual
do cluster (equivalente ao Enter em branco da CLI); `"-"` ignora o
cluster. Nome não-vazio é validado antes de tocar disco ou banco: no
máximo 80 caracteres, sem caractere de controle (`trama/servidor/revisao.py`,
`NOME_MAX_LEN`/`validar_nome`) — rejeitado com 400 em português.

`revisao.aplicar_e_gravar()` grava em quatro passos deliberados, para uma
falha em qualquer um nunca deixar nem o banco nem os arquivos pela
metade: (1) calcula falas/clusters/dinâmica em memória; (2) PREPARA
`.txt` e `.json` em arquivos temporários (`nucleo.preparar_escrita_atomica`)
sem tocar os arquivos reais nem o banco; (3) só então grava no banco
(`nucleo.registrar_contribuicoes`) — se falhar, os temporários ficam órfãos
e nada real mudou; (4) só com o banco confirmado, troca os temporários
pelos arquivos reais (`nucleo.confirmar_escrita_atomica`, um `os.replace`
atômico). `pipeline.py` usa a mesma escrita atômica de um passo só
(`nucleo.escrever_atomico`) para o `.json`/`.txt` que gera originalmente.

Toda reunião tem um campo `estado` explícito, nunca inferido no frontend a
partir de um campo ausente:

| Estado | Quando | Exemplo hoje |
|---|---|---|
| `completa` | `.json` tem `turnos` e `dinamica` (saída do `pipeline.py` atual) | `reuniao_06/07/08/09` |
| `incompleta` | `.json` existe, mas de schema anterior — falta `turnos`/`dinamica` | `reuniao_01/03/05` |
| `nao_processada` | sem `.json`, só áudio (e às vezes saída de `fase0.py`) — fila de trabalho, não erro | `reuniao_02/04` |
| `processando` | um marcador existe **e** bate com o job rodando agora em memória (mesmo servidor, sem reinício no meio) | só existe enquanto uma rota de processar/cancelar está ativa |
| `interrompido` | um marcador existe **sem** job correspondente em memória — o servidor reiniciou no meio de um processamento anterior | só aparece após uma queda |

`processando`/`interrompido` só existem por causa do marco 2
(`trama/servidor/processamento.py`) — cruzam o marcador em disco
(`.processando.json`) com o estado em memória do servidor
(`_estado_e_acao_sem_json` em `trama/servidor/reunioes.py`). O detalhe de uma
reunião `nao_processada`/`interrompido` mostra o que se sabe do arquivo
(nome, tamanho, duração via `ffprobe`). Um campo ausente no `.json` chega
ausente na resposta, nunca como `0` ou lista vazia.

`GET /api/reunioes` também traz `dinamica` (`[{pessoa, fala_pct}]`,
ordenado por `fala_pct` decrescente — a mesma ordem dos segmentos da barra
de tempo de fala, para o nome ao lado de cada segmento corresponder à cor
certa —, `None` se a reunião não tem dinâmica) e `acao_processar`
(`{disponivel, motivo}`, `None` quando há `.json` — `completa`/
`incompleta` — e presente nos três estados sem `.json`
`nao_processada`/`processando`/`interrompido`) para o botão "Processar" —
mesmo dicionário usado no detalhe (as duas rotas chamam a mesma
`_estado_e_acao_sem_json` em `trama/servidor/reunioes.py`), para nunca
divergirem. `motivo` é contexto sobre o ESTADO, não motivo de
`disponivel` ser falso — as duas perguntas não são a mesma:
`nao_processada` não tem nada para explicar (`motivo: None`, `disponivel:
true`); `interrompido` também tem `disponivel: true` (o botão dispara um
processamento novo — as pessoas da tentativa anterior não sobrevivem a
uma queda do servidor, só vivem em memória), mas vale explicar o que
aconteceu (`MOTIVO_INTERROMPIDA`); só `processando` tem `disponivel:
false` de verdade, porque só cabe um processamento por vez
(`MOTIVO_JA_PROCESSANDO`). Marco 2, etapa 5: os botões "Processar" da
Lista e do Detalhe chamam essas rotas de verdade agora (`Lista.tsx`,
`Detalhe.tsx`) — o caso `processando` vira link para a tela de
acompanhamento em vez de chamar a rota nova de novo.

`GET /api/reunioes/{id}` (completa/incompleta) também traz `sim_min`,
`margem_min` e `limiares_origem` (`"processamento"` ou `"atual"`), para a
tela de revisão marcar o limiar na barra de similaridade. `pipeline.py`
(`montar_saida()`) grava `sim_min`/`margem_min` no `.json` desde que a
reunião foi processada — a rota devolve esses valores quando presentes
(`limiares_origem: "processamento"`). Reuniões de antes dessa mudança (as
9 de produção, hoje) não têm esses campos: a rota devolve `run.SIM_MIN`/
`run.MARGEM_MIN` de hoje, mas marcados `limiares_origem: "atual"` — nunca
finge que o limiar de hoje era o do processamento original, porque não há
como recuperar isso retroativamente.

A duração de uma reunião `nao_processada` vem de `ffprobe`, um subprocess
por chamada — inviável se `GET /api/reunioes` o disparasse a cada
carregamento da lista, com dezenas de gravações na fila. O resultado fica
cacheado num arquivo oculto ao lado do áudio (`.duracao_cache.json`),
invalidado por tamanho+mtime do arquivo original.

`GET /api/reunioes/{id}` remove `clusters[*].embedding` da resposta. É
decisão de arquitetura, não detalhe de implementação: o vetor de voz é dado
biométrico, nenhuma tela do frontend precisa dele, e ele não deveria
deixar o servidor. Continua disponível para quem lê o `.json` direto do
disco (a revisão, que precisa dele para realimentar `nucleo.py`).

### Casca do aplicativo

`App.tsx` é dono do cabeçalho/nav (`componentes/Cabecalho.tsx`) — renderiza
UMA VEZ, fora do roteamento; cada tela devolve só conteúdo. Antes disso
cada tela importava e renderizava seu próprio `<Cabecalho>`, capado em
640px (a medida do transcript) — o motivo de a lista, o formulário e
tudo mais abrirem numa coluna estreita centralizada mesmo num monitor
grande.

Cabeçalho é sempre 100% da largura da janela. Conteúdo usa uma de duas
medidas (`tokens.css`, documentado em `identidade-trama/SKILL.md`):

Acima de 1440px de janela, as telas de dados viram container fluido
(margem de 48px, teto de 1680px) e ganham colunas — ADR 0015: dinâmica
resumida ao lado da lista de Reuniões (`interacao` em `GET
/api/reunioes`), Detalhe em três colunas (fita, transcript em 640px,
painel fixo com o resumo e o controle de interações), Pessoas na largura
toda, os dois passos da Nova reunião lado a lado, cartões da Revisão e
seções de Configurações em duas colunas. Entre 720px e 1440px, o layout
de antes; abaixo de 720px, o celular (ADR 0014). A medida de leitura do
transcript nunca cresce.

- `--medida-leitura` (640px) — só o corpo do transcript (Detalhe).
- `--medida-conteudo` (1040px) — Lista, Pessoas, Perfil.
- Nova reunião usa `--medida-leitura` (640px de conteúdo, centralizada):
  é um formulário curto, lido de cima para baixo. A fila e o estado das
  reuniões ficam em Reuniões, não numa lateral da tela inicial.

Revisão e a tela de Processamento continuam em 640px por enquanto —
questão em aberto, não decisão (são mais narrativa linear que lista ou
formulário largo).

Nav de seção (`Nova reunião`/`Reuniões`/`Pessoas`, à esquerda, nesta
ordem) mostra a seção atual por cor + régua de 2px embaixo, nunca
etiqueta colorida. O app abre na Nova reunião (`#/`).
`tema/useRota.ts:secaoDaRota()` mapeia cada rota pra uma seção; Detalhe,
Revisão e Processamento são hierarquia da seção Reuniões (drill-down),
não paradas irmãs. `Perfil` (à direita) guarda também as Configurações;
o Glossário e a Aparência (o tema) são seções dele, não abas nem botão
no cabeçalho. Endereços antigos (`#/nova`, `#/glossario`,
`#/configuracoes`, `#/ajustes`) ainda abrem a tela equivalente.

Abaixo de 720px, o cabeçalho mostra só a marca e a navegação vai para
uma barra de abas fixa embaixo (`componentes/BarraAbas.tsx`): Nova,
Reuniões, Pessoas, Perfil, com ícone de traço e rótulo, em material
translúcido — a única superfície flutuante do app (ADR 0014, exceção ao
ADR 0012). O conteúdo rola por baixo e ganha `padding-bottom` de
`--altura-abas` (inclui `env(safe-area-inset-bottom)`). É só layout: o
servidor continua em `127.0.0.1`.

A página nunca rola na horizontal: `#root` tem `overflow-x: clip` (não
`hidden`, que criaria um contêiner de rolagem e roubaria o `position:
sticky` da fita) e `.area-conteudo__rolagem` também corta no eixo x.
Sem `overscroll-behavior-x: none` no documento: desligaria o gesto de
voltar deslizando; só a grade de Pessoas contém o próprio gesto
(`contain`). Isso é proteção; cada tela resolve a própria causa — o que
passa da largura rola dentro do próprio bloco (a grade de participação
em Pessoas, que abaixo de 720px vira um bloco por pessoa) ou quebra a
linha (título, nome de arquivo, fala). O zoom do usuário continua livre.

Cor de voz (`vozes/corDaVoz.ts`): índice pela ordem de entrada na
galeria (`primeira_aparicao` de `GET /api/pessoas`, o mais cedo entre a
base legada e a primeira contribuição), desempatado pelo nome, módulo 8.
A paleta é travada por `tests/test_paleta.py` (distância perceptual entre
as vozes, com daltonismo simulado, e contra `--acento`/`--tinta-tenue`).
O índice é recarregado depois de uma revisão e de uma exclusão
(`GaleriaContext.recarregar`) — antes era lido só ao abrir o app, e quem
entrava na galeria depois caía no hash de reserva, podendo repetir a cor
de outra pessoa.

Tema (`tema/useTema.ts`) e perfil local (`perfil/perfilLocal.ts`) são
estado de módulo com `useSyncExternalStore`, não de componente: valem
para o app inteiro mesmo com a tela de Perfil fechada. `main.tsx` chama
`iniciarTema()` uma vez, e é ele quem acompanha o sistema em tempo real
quando a preferência é "seguir o sistema".

Troca de rota anima via View Transitions API nativa do navegador —
zero dependência nova (ADR 0013). `tema/transicaoDeRota.ts` decide entre
três tipos antes de `useRota.ts` aplicar a mudança de estado:
`"secao"` (crossfade, entre seções irmãs), `"avancar"`/`"voltar"`
(entram/saem em direções opostas, espelhando o mesmo caminho — hierarquia
dentro de Reuniões, por um mapa estático de profundidade). O cabeçalho
tem `view-transition-name` próprio e nunca anima — só `.area-conteudo`
se move (`estilos/transicoes.css`). Dentro dela, `.area-conteudo__rolagem`
é quem rola, na largura inteira da janela; o `<main>` de cada tela só
limita a largura de leitura e não rola (`estilos/base.css`, `App.tsx`).
Sem suporte no navegador ou com `prefers-reduced-motion`, a troca volta a ser instantânea — o mesmo
`aplicar()` de sempre, nunca um segundo caminho "modo reduzido" pra
manter.

### Idioma da interface (ADR 0026)

Português e inglês. `frontend/src/i18n/idioma.ts` guarda a escolha
(`localStorage`, padrão = idioma do navegador) e dá o `locale` do `Intl`;
`i18n/textos.ts` entrega o catálogo do idioma atual (`useTextos()` no
React, `textosAtuais()` fora dele). Catálogos em `i18n/pt/<area>.ts` e
`i18n/en/<area>.ts`, um por área da interface; o de português é a
referência do tipo, e `i18n/catalogos.test.ts` confere a paridade.

Erros e avisos do servidor chegam como `{"codigo", "parametros"}`
(`trama/erros.py`); `api/cliente.ts` (`mensagemDeErro`, `textoDoAviso`)
devolve o texto de `i18n/<idioma>/erros.ts`. Aviso gravado como texto num
`.json` antigo aparece como está. `tests/test_codigos_de_erro.py` liga os
dois lados. Nenhuma tela guarda mensagem como texto: o estado guarda uma
`Mensagem` (`i18n/mensagem.ts`, função do catálogo) e resolve no render
com `useMensagem()`; as funções de `api/` lançam `ErroDaApi`, que carrega
a `Mensagem` (`mensagemDe(e)` no `catch`). A transcrição baixada recebe `?idioma=` (`servidor/transcricao.py`,
`TEXTOS`); a fala nunca é traduzida.

### Telas

1. **Nova reunião** (`#/`, tela inicial) — coluna única de 640px com
   dois passos (o áudio; quem estava na sala, como botões de alternar
   com as pessoas da galeria e "+ Pessoa nova"), título opcional e
   "Transcrever". Com alguém selecionado, aparece "Estava, mas talvez não
   tenha falado": uma caixa por pessoa selecionada (desmarcar a pessoa
   tira a marca), para quem só ouviu ou entrou calado — sem isso, cada
   pessoa vira um falante a mais, e forçar um grupo para quem não falou
   divide outra pessoa em dois. Vai para `talvez_calados` no processar.
   O título é salvo logo depois do upload, antes de
   processar; se o servidor recusar, a reunião fica na fila e a tela diz.
2. **Lista** (`#/reunioes`) — reuniões, estado, duração, pessoas, botão
   "Processar" ligado à rota de verdade (marco 2, etapa 5). Três grupos:
   "Na fila" (não processada, processando, interrompida), "A revisar"
   (processada com algum cluster sem decisão, com o link "Revisar" na
   linha) e as revisadas — o estado normal, sem marca por linha —
   agrupadas por mês da gravação ("setembro de 2026"), no fuso da
   máquina; revisada com data só do arquivo vai para "Sem data da
   gravação", nunca para o mês em que o arquivo foi copiado. Cada linha
   mostra título e data. Busca no cliente por título (o dado ou "Reunião
   NN") e pessoas, sem acento e sem maiúscula; cada palavra digitada tem
   de aparecer. A partir de 2 caracteres, também nas falas, no servidor
   (`GET /api/busca`): seção "Na fala" com o trecho, a palavra em
   destaque (`<mark>`, como texto), quem falou e o horário; o clique abre
   `#/reuniao/<id>/em/<segundos>`, o Detalhe já rolado naquela fala.
   Medido nas dez reuniões reais: ~80–90 ms na primeira busca (lê e
   normaliza os dez `.json`), ~1,5–3 ms depois (cache em memória por
   tamanho + mtime de cada `.json`); resposta de até ~36 KB com o limite
   de 20 trechos por reunião.
   `revisada` (em `GET /api/reunioes` e no detalhe) é verdadeiro quando
   todo cluster tem decisão: `confirmado` no `.json` ou contribuição no
   ledger (reunião revisada por versão antiga do `revisao.py`, sem o
   campo).
   Rótulo de máquina (`IGNORADO_*`, `DESCONHECIDO_*`) nunca aparece cru:
   vira "1 voz não atribuída" depois dos nomes, e o segmento dele na
   barra de fala vai para o fim, em `--tinta-tenue` (`util/falante.ts`).
   No Detalhe, a margem do transcript, as marcas de evento, as pistas de
   palavra e o resumo de dinâmica mostram "voz não atribuída" (numerada
   quando há mais de uma na reunião, `util/falante.ts:rotulosDaReuniao`).
   `corDaVoz` devolve `--tinta-tenue` para essas vozes (marcas);
   `corDoTextoDaVoz`, `--tinta-fraca` (texto).
3. **Detalhe** (`#/reuniao/<id>`) — título editável na própria linha
   (`componentes/TituloEditavel.tsx`: clique abre o campo, Enter grava,
   Esc cancela, sair do campo grava), data da reunião embaixo. Com
   "Mostrar interações", as
   palavras ditas enquanto outra pessoa também falava ganham uma faixa de
   fundo na cor dela, a 20% (`--opacidade-sobreposicao`,
   `util/sobreposicao.ts`): palavra cujo ponto médio cai numa região de
   `regioes_sobrepostas` com outra pessoa. Diz "aqui outra pessoa falava
   junto", nunca de quem são as palavras (isso é o pontilhado). Só texto
   em `--tinta-corpo` fica sobre a faixa — a pista troca a letra para ele
   e mantém o pontilhado na cor da voz; `tests/test_paleta.py` mede.
   Precisa de `palavras_tempo` (reunião processada a partir de
   2026-09-25). Revisada: "Revisada" discreto e o
   link secundário "Editar revisão"; a revisar: botão "Revisar" em
   destaque. Nos dois casos, ao lado, o link discreto "Baixar transcrição
   (.txt)" (`GET /api/reunioes/{id}/transcricao`, nome
   `AAAA-MM-DD Título.txt`; sem data quando só se sabe a data do arquivo).
   Texto de uma fala corrigível na própria linha
   (`componentes/FalaEditavel.tsx`, ADR 0016) pelo lápis no fim do texto,
   que aparece no hover/foco da linha como o botão de tocar. Clique duplo
   é só seleção do navegador (ADR 0019): selecionar um trecho de uma fala
   mostra "Corrigir" (`componentes/PainelCorrecao.tsx`), com "O certo é",
   "Só nesta fala" / "Em todas as reuniões e nas próximas" (com a prévia
   de onde trocaria) e "O que é isso?". Depois de "Em todas", "Talvez
   estas também sejam X" (ADR 0020): caixas desmarcadas, uma por forma. Enter grava, Esc cancela,
   sair grava. Fala corrigida: "editado à mão" na margem (o transcrito no
   `title`), sem as marcas de posição nem "confiança baixa", e "Voltar
   ao original" dentro da edição. Transcript identificado, fita de tempo
   da reunião inteira, marginália com a dinâmica. É a tela que o usuário
   lê. Para os três estados sem `.json`, mostra o que se sabe do arquivo
   e o mesmo botão "Processar" da Lista.
4. **Revisão** (`#/reuniao/<id>/revisar`) — um cartão por cluster com três
   trechos tocáveis. Quatro decisões por reunião, não trezentas. É o
   coração do produto. Cada cartão tem três decisões:
   - **Confirmar e aprender a voz** (padrão): nome no transcript e
     contribuição no ledger.
   - **Só nomear, sem aprender**: nome no transcript, nenhum perfil muda
     (`sem_aprender` no corpo da rota; o `--sem-aprender` do `revisao.py`,
     só que por cluster). Para um cluster majoritariamente de uma pessoa
     com trechos de outras (ver "Fronteiras conhecidas") — o transcript
     fica com o nome certo sem contaminar o perfil.
   - **Ignorar este cluster** (o `"-"` do CLI): sem nome e sem
     contribuição. Um cluster já ignorado abre de novo em "ignorar".

   Ignorar ou só nomear um cluster que já tinha ensinado uma voz numa
   revisão anterior **remove** essa contribuição do ledger (quem diz que
   a voz não serve não pode deixá-la valendo), e confirmar outro nome no
   mesmo cluster a **move**. E confirmar pela primeira vez **ensina** voz
   nova. Nada disso é gravado sem a pessoa ver — nem a voz nova: reabrir
   a `reuniao_01` (revisada só nomeando, antes de a tela saber disso) e
   salvar sem mexer ensinou 293 s de voz sem aviso:
   "Salvar revisão" pede primeiro `POST .../revisao/previa` (a mesma
   decisão, `trama/servidor/revisao.planejar`, sem gravar) e mostra "isso vai
   remover 64 s da voz de Luciano", "isso vai ensinar 110 s da voz de
   Celso" — inclusive quando o perfil some da galeria — antes de
   confirmar. O `revisao.py` segue a mesma regra e
   pergunta `[s/N]`. Rótulo de máquina (`DESCONHECIDO_*`, `IGNORADO_*`)
   nunca vira perfil (`revisao.decidir_contribuicao`).
   Depois de gravar as vozes, a segunda etapa, **"Termos para conferir"**
   (`telas/ConferirTermos.tsx`, `trama/servidor/conferir.py`, ADR 0022): siglas
   e palavras em que a transcrição duvidou várias vezes, fora nomes da
   galeria, termos da empresa e o que já foi respondido; no máximo 10.
   Cada uma toca o trecho e tem "Está certo", "Corrigir para…" (o painel
   de correção, embutido) e "Ignorar". Sem nenhum item, passa direto à
   etapa seguinte.
   A terceira etapa, **"Trechos para conferir"**
   (`telas/ConferirTrechos.tsx`, `trama/trechos.py`, ADR 0028): até 3 falas
   de confiança baixa e 2 sons não transcritos, no máximo 5, cada um com
   play e um campo para escrever o que foi dito. Fala: o campo abre com o
   texto transcrito e grava pela correção manual (`PUT .../falas/{i}`).
   Lacuna: o texto fica dentro dela; no Detalhe aparece no ponto da
   lacuna, em itálico (`.lacuna-escrita`), com o `title` "escrito à mão".
   "Não dá para entender" grava e não pergunta de novo; "Pular" não grava.
   Sem nenhum item, volta direto ao Detalhe.
   **Apagar reunião** (`componentes/ConfirmarApagarReuniao.tsx`, ADR 0029):
   link discreto no Detalhe, ao lado de "Baixar transcrição" (e abaixo do
   "Processar" numa reunião sem transcrição). Abre a confirmação na
   própria tela, com o foco em "Cancelar" e a régua de `--alerta` de
   excluir pessoa (`componentes/ConfirmarExclusao.css`, compartilhado):
   quanto de voz cada pessoa perde e quem sai da galeria; sem a prévia
   carregada, o botão de apagar fica desligado. Apagada, volta para a
   lista e recarrega o índice de cor da galeria.

5. **Processamento** (`#/reuniao/<id>/processando`) — acompanha o SSE das
   5 etapas; cai para "ocioso" se não há job correspondente rodando.
6. **Pessoas** (`#/pessoas`) — tabela ordenada por voz aprendida: cor +
   nome ("perfil em formação" abaixo de 120s, `vozes/perfil.ts`),
   segundos de voz com barra proporcional à maior, grade de participação
   (uma célula por reunião: preenchida = presença confirmada na revisão,
   aprendendo a voz ou só nomeando; contorno = estava na sala sem
   confirmação — cluster não revisado, ou cluster ignorado, usando quem
   o pipeline tinha identificado nele; fundo = ausente; tracejada =
   reunião não processada, sem como saber quem estava), total de
   reuniões e a última. Quanto de voz foi aprendido é a coluna própria,
   não a grade. Excluir com confirmação na própria tela.
   **Cluster ignorado:** desde 2026-09-24 a revisão guarda
   `nome_antes_de_ignorar`. Para os ignorados antes disso, a grade
   reconstrói a mesma decisão do `pipeline.py` a partir dos `scores` e
   limiares gravados no `.json` (primeiro colocado acima de `sim_min`,
   com `margem_min` sobre o segundo) — nunca um palpite abaixo do
   limiar. **Limite:** as pessoas marcadas no upload de uma reunião
   ainda não processada só vivem na memória do processamento.
   **Limite da exclusão:** apaga do `vozes.db` (inclusive das páginas
   livres, via `VACUUM`), mas não dos backups `vozes.db.bak-*` que as
   migrações e as cópias manuais deixam ao lado dele, nem o nome das
   transcrições. Para um pedido de exclusão sob LGPD, esses backups
   precisam ser tratados à parte.
7. **Perfil** (`#/perfil`) — nome de quem usa e, opcionalmente, qual
   pessoa da galeria é ela (só `localStorage`, sem login). Dentro,
   Configurações: Aparência (sistema/claro/escuro), Termos da empresa
   (`perfil/TermosDaEmpresa.tsx`, ADR 0021: o `termos.txt` visto por termo —
   nome, "O que é?" e as variações já corrigidas, cada uma com ×; "Adicionar
   termo" e "Adicionar variação", esta com a mesma prévia da correção pelo
   texto; cada ação grava na hora; comentários e regras comentadas ficam no
   arquivo, invisíveis e intactos; "Aplicar às reuniões já processadas" reescreve `.json` e
   `.txt` pela mesma `termos.aplicar_em_falas` do `pipeline.py`, depois de
   mostrar quantas substituições e onde), Processamento e Dados e privacidade (somente leitura,
   de `GET /api/sistema`), Sobre (versão e licenças).

### Marcos

1. **Concluído.** Ler e revisar, a partir dos `.json` que já existem no
   disco. As cinco rotas de leitura+escrita, as quatro telas (Lista,
   Detalhe, Revisão, e o estado `nao_processada` como fila de trabalho)
   e a única rota que grava no `vozes.db` (`POST
   /api/reunioes/{id}/revisao`, ADR 0007) estão implementadas e
   verificadas contra dado real (cópia de `vozes.db`/`reuniao_09`).
2. **Concluído.** Backend completo e verificado contra o `pipeline.py` real
   (upload, disparo/cancelamento/progresso por SSE, recuperação de queda
   do servidor). Nova reunião, tela de processamento e os botões
   "Processar" (Lista e Detalhe) chamando as rotas de verdade. Casca de
   aplicativo (cabeçalho/nav únicos, duas larguras) e as três áreas
   novas como estrutura (Pessoas/Glossário/Configurações, sem conteúdo
   ainda).
3. Conteúdo de Pessoas (galeria com exclusão LGPD), Glossário (edição de
   `termos.txt`) e Configurações; estados vazios reais das três áreas;
   retenção, exportar, aviso.
   Apagar uma reunião (pasta, áudio e a voz que ela ensinou) existe desde
   2026-11-12 (ADR 0029), no Detalhe, em qualquer estado.

---

## Fronteiras conhecidas

**Fala cruzada.** ~3% de cada reunião em que duas vozes se misturam no sinal.
A informação não está lá. O sistema localiza e marca com
`[vozes sobrepostas]`; nenhum ajuste de software recupera.

**Interrupção.** Só com timing não dá para separar "A cedeu porque foi
interrompido" de "A estava terminando e B antecipou". Serve para comparar
pessoas na mesma reunião, não como acusação. Disputa (fala simultânea
sustentada) é bem definida e verificável.

**Diarização pode atribuir um turno inteiro à pessoa errada.** Não é
sobreposição (a diarização não registrou ninguém mais falando no trecho) nem
erro de consolidação por frase (o alinhamento palavra a palavra já
concordava com a diarização — errada). É a segmentação/identificação de
quem-fala-quando confundindo as duas vozes por um trecho contínuo. Nenhum
ajuste no alinhamento ou na votação por frase corrige isso, porque os dois
já estavam de acordo com uma origem errada. Dois casos medidos, não um -
já é padrão, não anedota:

- `reuniao_09`, 44,4–55,3s: diarização (bruta e exclusiva) deu turno
  contínuo para a Amanda; a escuta confirma que a fala depois da primeira
  interrogação era do Celso.
- `reuniao_07`, 0–1,1s (a primeira frase da reunião): diarização deu o
  turno inteiro para o Celso, unânime também no alinhamento por palavra
  (nenhuma divergência para a votação apagar); a escuta confirma que
  "Bom dia, pessoal" foi o Luciano. No mesmo bloco de fala exibido,
  a frase seguinte ("Já vou começar.") é um erro DIFERENTE — voto por
  duração escondendo um sinal real que o alinhamento por palavra via
  (ver ADR 0009) - os dois problemas coexistindo na mesma tela.

A escuta continua sendo a única verificação confiável de quem falou.

**Margem estreita no voto por frase.** `alinhar()` decide o dono de uma
frase inteira por voto ponderado na duração das palavras (ver ADR 0009) -
quem falou mais tempo na frase leva todas as palavras dela. Medido: a
margem entre o vencedor e o segundo colocado é estreita em 5% de todas as
frases votadas, e em 35% das frases que já têm alguma
`palavras_divergentes` registrada. Uma margem estreita não é
necessariamente erro (quem fala mais numa frase normalmente é mesmo o
dono dela), mas é onde um pequeno viés de segmentação - a diarização
atrasando ou adiantando alguns décimos o início real de uma fala - teria
mais chance de trocar o vencedor do voto.

**Decisão: não mexer nisso agora.** A consolidação por frase é o NÚCLEO
do pipeline - qualquer mudança na função de voto se propaga por toda fala
já processada, e o ganho de corrigir os casos de margem estreita é
incerto (não há, hoje, medição de quantos desses 5%/35% são de fato
atribuição errada, só de que a margem é pequena). Mexer no núcleo por
ganho incerto, com trabalho mais barato pendente (reprocessar 06, 04, 02),
não compensa agora. Revisitar quando houver evidência de erro de verdade
nesses casos - por exemplo, escuta manual de uma amostra das frases de
margem estreita - não só a margem em si.

**Reprocessar preserva a revisão, casando cluster por trecho de áudio.**
`pipeline.preservar_revisao` casa cada cluster novo com um cluster da rodada
anterior pela sobreposição no tempo dos turnos crus — nunca pelo nome
sugerido (que pode ser justamente o que a revisão corrigiu) nem pelo
número do label (a diarização renumera). Casa se o tempo em comum passa
de metade da fala dos dois, e se o cluster novo não tem mais de 20% de
fala de outro cluster antigo com o casado calado (fala sobreposta não
conta como mistura — contá-la reprovava a `reuniao_02` casada consigo
mesma). Cluster casado herda a decisão inteira: nome dado na revisão,
`confirmado`, `sem_aprender` (só nomear, gravado no cluster desde
2026-09-24) e ignorado (com `nome_antes_de_ignorar`). Cluster sem par
fica "A revisar". O ledger é indexado por `(reuniao_id, label)`: na mesma
gravação do `.json`, `nucleo.remapear_contribuicoes` leva cada contribuição
para o label novo do mesmo trecho; contribuição de cluster antigo sem par
continua valendo para a pessoa, com o label `orfao-…`. Verificado contra
as dez reuniões reais: cada uma casa consigo mesma e com os turnos
deslocados em até 0,5 s e renumerados. Execução anterior sem `turnos`
(schema antigo) cai no casamento por nome, sem remapear.

**Reprocessar o mesmo áudio pode não dar exatamente o mesmo resultado.**
Não medido a fundo ainda (fila de trabalho), mas um dado concreto surgiu
investigando a calibração de `lacunas_sem_texto` (ADR 0010): diarização e
ASR são cada um, isoladamente, determinísticos aqui - o mesmo `wav16k`
transcrito duas vezes produziu os 5872 tokens (palavra, timestamp,
probabilidade) byte-idênticos, e os turnos crus de um `.json` reprocessado
bateram campo a campo com o arquivo anterior. Mesmo assim, entre três
reprocessamentos completos da `reuniao_07` nesta sessão, a contagem de
`falas` variou 278 → 277 (~0,4%) - uma diferença pequena o bastante para
não ter mudado nenhuma decisão tomada aqui, mas que mostra que a variação
entre execuções completas não é só da diarização (o problema originalmente
suspeitado): alguma etapa do pipeline completo (conversão de áudio,
carregamento do modelo, ou o próprio ASR fora do cenário "mesmo wav já em
memória") introduz uma diferença mínima que não aparece testando cada
etapa isolada. Fica para quando a variação entre execuções for medida de
verdade.

**Canal acústico.** O embedding captura a sala e o microfone junto com a voz.
Toda a calibração vem de iPhone 15 Pro Max sobre a mesa. Trocar de aparelho
pode degradar; não medido.

**Verificação de pureza de cluster por embedding médio tem ponto cego.**
`nucleo.embed_segments` usa no máximo 120s por cluster, priorizando os
trechos mais longos (`MAX_SPEECH_PER_CLUSTER`). Um cluster majoritariamente
de uma pessoa, com intrusão de outra em trechos curtos, mede como limpo —
a intrusão fica fora da amostra por construção, não por engano. Medido na
`reuniao_06`, `SPEAKER_02`: 0,890 contra Luciano e 0,330 contra Celso,
usando 121s de 341s do cluster, numa faixa que a escuta indica misturada
com o Celso. A escuta continua sendo a única verificação confiável de
pureza — o cosseno médio confirma identidade dominante, não pureza.

**Confirmação empírica (mesma reunião, reprocessada).** A matriz deu
0,893 contra Luciano e 0,332 contra Celso - virtualmente igual à medição
anterior, então o ponto cego não é ruído de uma execução isolada. Com
`amostras.py` (exporta trechos de UM cluster espalhados pela reunião
inteira, SEM o piso de 4s que a revisão usa - ver "Módulos" acima), 10
trechos do `SPEAKER_02` foram ouvidos, incluindo os abaixo de 4s que a
amostragem normal descarta: 4 de 10 tinham intrusão de outra pessoa
(Celso, Rolando), mesmo a matriz mostrando "acerto claro" (0,893, margem
de 0,50 sobre o segundo colocado). O cluster foi ignorado na revisão
(opção "Ignorar este cluster" na tela, ver "Telas" acima) para não
contaminar nenhum perfil - similaridade alta não é garantia de pureza, e
a métrica não tem como saber a diferença.

**Oito cores de voz.** A paleta tem oito cores (`--voz-1` a `--voz-8`),
conferidas entre si em `tests/test_paleta.py`; a cor sai da ordem de
entrada na galeria, módulo 8 (`vozes/corDaVoz.ts`). Com mais de oito
pessoas na galeria, as cores se repetem: a nona tem a cor da primeira. Isso
só atrapalha de verdade quando duas pessoas da mesma cor estão na MESMA
reunião — aí transcript, fita de tempo e barra de fala não as separam pela
cor, só pelo nome. Limite conhecido, não resolvido: as saídas (mais cores
perdem a distância perceptual medida; escolher a cor por reunião quebra a
cor estável por pessoa) ficam para quando aparecer o caso real.

**Ata local.** Perde relações que atravessam blocos. Fora do MVP, ADR 0002.

## Ideias futuras

Registradas para não se perder. **Nada aqui está implementado**, e nenhuma
é compromisso: quando uma entrar, vira tarefa (e ADR, se tiver
alternativa descartada).

### Juntar partes da mesma reunião

Uma reunião às vezes vira duas gravações: o gravador parou e voltou, ou a
reunião foi gravada em partes. Hoje elas aparecem como reuniões separadas.

- **Nunca automático.** O app só *sugere* ("estas duas parecem partes da
  mesma reunião") e a pessoa decide. Juntar errado mistura duas reuniões
  diferentes, e isso é pior que deixar separado.
- **Critério para sugerir:** uma termina e a outra começa em até
  **2 minutos**, no **mesmo dia**, com **pelo menos uma pessoa em
  comum**. Início pela data da gravação (`data_reuniao`, só com
  `data_origem: "gravacao"`) e fim por início + duração do áudio.
- **Nos dados atuais, três pares passariam** (conferido em 2026-09-25,
  com a duração real de cada áudio):

  | Par | Fim da primeira → início da segunda | Intervalo | Pessoas em comum |
  |---|---|---|---|
  | 01 e 02 | dia A, 09:39:10 → 09:39:39 | 28 s | Amanda, Celso, Luciano, Ramiro |
  | 04 e 05 | dia B, 08:50:46 → 08:51:58 | 72 s | Amanda, Celso |
  | 06 e 07 | dia C, 10:39:27 → 10:39:44 | 16 s | Celso, Luciano, Rolando |

  Nenhum outro par consecutivo é do mesmo dia.
- **A dinâmica das partes pode ser somada**, porque a identidade é por
  pessoa da galeria, não por gravação: o "Celso" da parte 1 e o da
  parte 2 são a mesma pessoa, mesmo com rótulos de cluster diferentes em
  cada diarização. Tempo de fala, interrupções e apoios somam por pessoa.
  Vozes não atribuídas (`DESCONHECIDO_*`, `IGNORADO_*`) não têm como ser
  casadas entre as partes e ficariam separadas.

### Dúvidas sobre termos na ata

Quando existir ata (hoje fora do MVP, ADR 0002), ela traz uma seção de
**dúvidas sobre termos fora de contexto**: palavras que a ata não soube
interpretar, mesmo com o "Vocabulário desta empresa" do `.txt`. A
instrução do vocabulário já pede isso à IA que ler o arquivo ("antes de
escrever a ata, liste os termos que parecem errados ou fora de contexto e
pergunte o que significam").

- As respostas alimentam os **mesmos termos da empresa** do `termos.txt`
  (descrição de um termo conhecido, ou correção com alcance), pelo mesmo
  caminho da tela — nunca um segundo cadastro de termos.
- Uma dúvida respondida nunca volta, nem nessa ata nem nas próximas, como
  as respostas da revisão de termos.
