# ADR 0008 — Trechos de revisão: 4–15s espalhados, não os mais longos

- **Data:** 2026-09-18
- **Situação:** aceito

## Contexto

`review.py` (CLI) escolhia os 3 trechos com mais CARACTERES DE TEXTO de
cada cluster para mostrar na revisão. No terminal, a linha era truncada
em 90 caracteres — o problema nunca apareceu ali. Na tela de revisão do
navegador (marco 1, etapa 5), o mesmo critério produzia cartões com uma
fala de vários minutos, e o cartão virava várias telas de rolagem para
uma decisão que deveria levar segundos.

## Decisão

Até 3 trechos por cluster, escolhidos por dois critérios:

1. **Duração entre 4 e 15 segundos** — curto demais não dá para ouvir a
   cadência da voz; longo demais é o problema original.
2. **Espalhados no TEMPO**: um de cada terço da participação da pessoa na
   reunião (início, meio, fim), não os primeiros que aparecerem nem os
   mais longos. Três amostras de momentos diferentes da conversa dizem
   mais sobre a voz de alguém do que um trecho só, por mais longo que
   seja — a pessoa muda de tom, ritmo e volume ao longo de uma reunião de
   uma hora.

Sem candidato na faixa ideal (cluster só tem falas muito curtas ou muito
longas), cai para as mais próximas da faixa, mantendo a ordem
cronológica — nunca fica sem nenhuma amostra.

O texto de cada trecho aparece limitado a 2 linhas na tela, com
reticências (`-webkit-line-clamp`) — ele serve só para localizar o
momento; quem decide é o áudio, tocado pelo botão de play.

## Duplicação consciente

A lógica existe em DOIS lugares, sem compartilhar código:
`review.selecionar_trechos()` (Python, `review.py`) e
`selecionarTrechos()` (TypeScript, `frontend/src/telas/Revisao.tsx`). Não
há como compartilhar uma implementação entre um script Python e uma tela
React sem introduzir uma terceira peça (um serviço, um arquivo de dados
gerado) que custaria mais do que resolve para uma função deste tamanho.

Isso é **dívida técnica aceita, não um descuido**: as duas implementações
têm que continuar idênticas em critério (faixa de duração, espalhamento,
fallback) porque `review.py` (CLI) e a tela de revisão precisam escolher
os MESMOS trechos para a MESMA reunião. Mudar uma sem mudar a outra faz o
produto divergir de si mesmo — o CLI mostraria uma amostra, a tela outra,
para a mesma pessoa na mesma reunião.

**Quem mexer nisto daqui a seis meses:** os dois arquivos têm comentários
apontando um para o outro (`review.py:selecionar_trechos` cita
`Revisao.tsx:selecionarTrechos` e vice-versa). Se você mudar a faixa de
duração, o número de trechos ou a regra de espalhamento num lado, mude no
outro na MESMA alteração — os testes de um lado não pegam uma divergência
do outro, porque são linguagens diferentes e suítes diferentes
(`tests/test_review.py` só exercita o Python).

## Alternativas descartadas

**Manter o critério antigo (mais texto) só na tela, com um limite de
caracteres.** Cortar o texto não cortava o ÁUDIO por trás — o trecho
tocável continuaria sendo os mesmos minutos longos, só escondendo o
texto na tela. O problema real era a seleção, não a exibição.

**Só os mais longos dentro da faixa 4–15s, sem espalhar no tempo.**
Resolveria o tamanho do cartão, mas não a qualidade da amostra: três
trechos consecutivos do mesmo intervalo de 40s da reunião valem menos
para reconhecer uma voz do que três de momentos diferentes.

## Consequências

- Qualquer mudança neste critério precisa ser feita nos dois arquivos na
  mesma alteração.
- O fallback (sem candidato ideal) garante que a revisão nunca fica sem
  nenhuma amostra para ouvir, mesmo num cluster atípico (só "uhum"s
  curtos, por exemplo).
- Verificado contra `reuniao_09` real: o cartão do Celso, que antes trazia
  um monólogo de vários minutos, passou a trazer três trechos de 12,7s,
  6,6s e 8,9s em 682s, 2362s e 3720s da reunião.
