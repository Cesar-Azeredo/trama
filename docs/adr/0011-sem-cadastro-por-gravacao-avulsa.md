# ADR 0011 — Não colher perfil de voz por gravação avulsa fora da reunião

- **Data:** 2026-09-20
- **Situação:** aceito

## Contexto

Cogitou-se um cadastro de voz por gravação avulsa: a pessoa manda um áudio
de casa (por WhatsApp, antes da primeira reunião), e o app aprende a voz
dela sem depender de uma reunião já processada. Resolveria um problema
real - hoje alguém só entra na galeria depois de aparecer numa reunião
(`harvest.py`) ou de gravar uma amostra dedicada seguindo a "regra de
ouro" de `enroll.py` (mesma sala, mesmo microfone, mesma posição da
reunião real), o que na prática significa recriar a condição de uma
reunião só para cadastrar uma pessoa.

Antes de construir qualquer coisa, medimos quanto a condição acústica
**sozinha** (sem trocar de pessoa) já move o embedding. `reuniao_06`,
`reuniao_07` e `reuniao_09` foram gravadas com o MESMO aparelho, em dias
diferentes, com posicionamento na mesa provavelmente diferente.
Comparamos o cluster de Celso, Luciano e Amanda contra si mesmos entre
essas reuniões (só leitura dos `.json` já processados, nada gravado).

## Medição

| Par | Cosseno |
|---|---|
| Celso, reuniao_06×07 | 0,9466 |
| Celso, reuniao_09×07 | 0,9133 |
| Celso, reuniao_09×06 | 0,8948 |
| Luciano, reuniao_09×07 | 0,9186 |
| Amanda, reuniao_09×06 | 0,8430 |

Faixa: **0,843 a 0,947, só variando dia e posição na mesa - mesmo
aparelho, mesma sala.**

Para contexto, a calibração de identificação (ADR 0001, `run.py`) já
registrava: faixa de acerto 0,834–0,972; maior falso positivo 0,434
(Ramiro×Celso). O par mais fraco desta medição (Amanda, 0,843) fica a
menos de 1 ponto percentual do PISO da faixa de acerto (0,834) - muito
mais perto dele do que o maior falso positivo (0,434) fica de `SIM_MIN`
(0,60, uma distância de 0,166). Ou seja: **variar só o dia e a posição na
mesa, com o mesmo aparelho, já produz uma queda do tamanho da margem
inteira do sistema.** Não é ruído desprezível - é a fonte de erro
dominante, maior que a distinção entre pessoas diferentes. Registrado em
`ARCHITECTURE.md`, seção de calibração.

## Decisão

Não construir cadastro de voz por gravação avulsa (áudio de casa, enviado
por mensagem, antes da primeira reunião). O canal acústico de uma
gravação de celular perto da boca, em outro ambiente, é uma mudança MAIOR
do que "mesmo aparelho, sala diferente, dia diferente" - e essa mudança
menor já consome quase toda a margem entre acerto e erro. Não há base
para supor que uma mudança maior deixaria margem sobrando.

O caminho que continua sendo o certo é colher o perfil DA PRÓPRIA
REUNIÃO (`harvest.py`) ou de uma amostra dedicada gravada nas MESMAS
condições (`enroll.py`, que já documenta essa exigência na própria
"regra de ouro do cadastro" - esta medição é a evidência quantitativa que
faltava atrás de uma regra que até aqui era só uma advertência sem número
por trás).

## Alternativas descartadas

**Colher de qualquer áudio que a pessoa mandar, aceitando a perda de
precisão.** Descartado: a medição mostra que a perda não é uma
degradação suave - é a diferença entre "dentro da faixa de acerto" e "na
fronteira do falso positivo". O produto vende justamente identificação
confiável (CLAUDE.md: "O valor está em quem falou o quê"); um cadastro
que empurra parte das pessoas para "confira manualmente" já na primeira
reunião mina essa proposta de valor central.

**Pedir a gravação de casa mas orientar a pessoa a imitar a condição da
reunião (celular longe da boca, não perto).** Descartado por não ser
verificável, nem realista pedir a um usuário leigo que replique uma
condição acústica que ele nunca viu. E mesmo replicando aproximadamente,
esta medição ("mesmo aparelho, dia e posição diferentes") nem inclui a
variável de aparelho/microfone diferente - tipicamente a maior fonte de
variação de canal acústico (ver ARCHITECTURE.md, "Canal acústico").

## O teste que reabriria esta decisão

Gravar a MESMA pessoa com o celular perto da boca (simulando um áudio de
WhatsApp), em outro ambiente, e comparar o embedding contra o cluster
dela numa reunião real de mesa. Se o cosseno ficar consistentemente
acima do piso da faixa de acerto (hoje 0,834) mesmo nessa condição mais
adversa, a decisão pode ser revisitada. Sem esse teste, não há dado que
sustente a mudança.

## Consequências

- Cadastro de voz continua exigindo reunião processada (`harvest.py`) ou
  amostra dedicada nas mesmas condições acústicas (`enroll.py`).
- Uma pessoa nova só entra na galeria depois de participar de uma
  reunião - custo de setup conhecido e aceito, não resolvido por este ADR.
- A variação entre dias (0,843–0,947, mesmo aparelho) fica registrada em
  `ARCHITECTURE.md` como a fonte de erro dominante do sistema - qualquer
  trabalho futuro de precisão deveria mirar nisso antes de otimizar a
  distinção entre pessoas diferentes, que já tem folga confortável.
