"""
ferramentas/roteiro_demo.py - Roteiro das reunioes de demonstracao. Tudo
ficticio: empresa, pessoas, produto e falas.

Cada fala: (pessoa, texto, pausa_s), com a pausa contada do fim de quem
falava. Pausa negativa = a pessoa entra por cima: entre -0,8 e -2 s vira
interrupcao na analise (interacao.py); uma fala curta ("Uhum.") que entra
bem antes do fim vira apoio.
No texto:
  ~palavra  o Whisper teria duvidado dela (probabilidade baixa);
  |         um silencio dentro da fala, sem texto (vira lacuna).

O produto ficticio "Painel Órbita" aparece mal transcrito de dois jeitos:
"painel de orbita" (o termos.exemplo.txt corrige) e "painel da orbita"
(nenhuma regra corrige - aparece como variacao parecida para conferir).
"""

PESSOAS = ["Beatriz", "Diego", "Helena", "Marcos", "Paula", "Tiago"]
DESCONHECIDA = "Sofia"  # nao esta na galeria: vira voz desconhecida

REUNIOES = [
    {
        "id": "reuniao_01",
        "titulo": "Planejamento do trimestre",
        "data": "2026-11-03T13:00:00Z",
        "revisar": True,
        "falas": [
            (
                "Beatriz",
                "Bom dia, pessoal. Vamos começar pelo planejamento do trimestre, "
                "porque a pauta de hoje é longa e eu quero sair daqui com os três "
                "objetivos fechados.",
                0.0,
            ),
            (
                "Diego",
                "Do lado de produto, a prioridade continua sendo o painel de orbita. "
                "Os clientes pedem a exportação dos relatórios desde agosto.",
                0.6,
            ),
            ("Helena", "E o suporte sente isso todo dia.", -1.2),
            (
                "Helena",
                "Metade dos chamados da última semana era sobre exportação. "
                "Se a gente resolver isso, o tempo de resposta cai pela metade.",
                0.3,
            ),
            (
                "Marcos",
                "Eu concordo com a prioridade, mas a equipe de engenharia está com "
                "duas pessoas a menos até dezembro. Não dá para prometer a exportação "
                "e a nova tela de permissões no mesmo trimestre.",
                0.8,
            ),
            ("Beatriz", "Uhum.", -3.0),
            (
                "Beatriz",
                "Então vamos escolher. Qual das duas tem mais impacto no ~OKR de retenção?",
                0.5,
            ),
            (
                "Diego",
                "A exportação, sem dúvida. A tela de permissões é pedido de dois "
                "clientes grandes, | mas a exportação aparece em quase todas as "
                "conversas de renovação.",
                0.4,
            ),
            ("Marcos", "Então a permissão fica para janeiro.", -1.2),
            (
                "Marcos",
                "Eu prefiro assim. Com uma entrega só, a gente consegue testar direito "
                "antes de liberar para todo mundo.",
                0.2,
            ),
            (
                "Helena",
                "Posso montar a lista dos clientes que mais pediram, para o Diego "
                "conversar com eles antes de fechar o escopo?",
                0.7,
            ),
            ("Diego", "Pode, isso ajuda muito. Até quinta?", 0.4),
            ("Helena", "Até quinta.", 0.2),
            (
                "Beatriz",
                "Segundo objetivo: o ~NPS. A gente caiu quatro pontos no último "
                "trimestre e eu quero entender o porquê antes de definir a meta.",
                0.9,
            ),
            (
                "Helena",
                "Boa parte das notas baixas cita a lentidão do painel da orbita "
                "quando o relatório é grande. Não é bug, é tempo de carregamento.",
                0.5,
            ),
            (
                "Marcos",
                "Isso a gente consegue atacar junto com a exportação. É a mesma "
                "consulta por baixo, então otimizar uma melhora a outra.",
                -1.1,
            ),
            (
                "Beatriz",
                "Ótimo. Então o segundo objetivo é recuperar os quatro pontos de ~NPS, "
                "medindo o tempo de carregamento como indicador.",
                0.6,
            ),
            (
                "Diego",
                "Terceiro objetivo eu sugiro deixar para a documentação. O time de "
                "vendas pede material novo desde o lançamento.",
                0.8,
            ),
            (
                "Beatriz",
                "Concordo. Marcos, você consegue estimar a exportação até a próxima reunião?",
                0.5,
            ),
            (
                "Marcos",
                "Consigo uma estimativa grosseira até segunda, e uma mais firme depois "
                "que o Diego fechar o escopo com os clientes.",
                0.4,
            ),
            (
                "Beatriz",
                "Perfeito. Fechamos então: exportação no painel de orbita, quatro "
                "pontos de ~NPS e a documentação para vendas. Obrigada, pessoal.",
                0.7,
            ),
        ],
    },
    {
        "id": "reuniao_02",
        "titulo": "Revisão do Painel Órbita",
        "data": "2026-11-05T17:30:00Z",
        "revisar": True,
        "falas": [
            (
                "Diego",
                "Pessoal, conversei com os seis clientes da lista da Helena. Cinco "
                "querem a exportação em planilha, um quer em PDF.",
                0.0,
            ),
            (
                "Paula",
                "Do lado do design, planilha é mais simples. O PDF exige pensar em "
                "paginação, cabeçalho, logotipo do cliente.",
                0.6,
            ),
            (
                "Tiago",
                "E na engenharia também. A planilha sai direto da consulta que já "
                "existe no painel de orbita.",
                0.5,
            ),
            ("Beatriz", "Então começamos pela planilha e o PDF vira uma segunda etapa.", 0.4),
            (
                "Helena",
                "Só um cuidado: o cliente que pediu PDF é o maior da carteira. Vale "
                "avisar ele antes, para não parecer que a gente ignorou.",
                0.7,
            ),
            ("Diego", "Eu ligo para ele amanhã.", -1.1),
            (
                "Diego",
                "E aproveito para mostrar o protótipo da planilha, se a Paula tiver "
                "alguma coisa até lá.",
                0.2,
            ),
            (
                "Paula",
                "Tenho um rascunho. Não está bonito, | mas mostra as colunas e o "
                "filtro por período, que foi o que mais apareceu nas conversas.",
                0.5,
            ),
            ("Helena", "Isso.", -2.5),
            (
                "Tiago",
                "Sobre o tempo de carregamento: medi ontem. O relatório de um ano "
                "leva onze segundos no painel da orbita. A meta que eu proponho é "
                "três segundos.",
                0.9,
            ),
            ("Beatriz", "Três segundos é factível?", 0.3),
            (
                "Tiago",
                "Com um índice novo no banco e cache do resultado, sim. Eu já testei "
                "o índice numa cópia e caiu para quatro.",
                0.3,
            ),
            (
                "Helena",
                "Isso muda muito o suporte. Lentidão é a reclamação número um nas "
                "notas baixas do ~NPS.",
                0.6,
            ),
            (
                "Paula",
                "Eu queria propor uma coisa na tela também: enquanto carrega, mostrar "
                "o que já chegou em vez de uma tela vazia.",
                0.8,
            ),
            ("Tiago", "Dá, mas aumenta o escopo. Eu deixaria para depois do índice.", -1.3),
            (
                "Tiago",
                "Primeiro a consulta rápida, depois a gente vê se ainda precisa do "
                "carregamento parcial.",
                0.3,
            ),
            (
                "Beatriz",
                "Combinado. Tiago fica com o índice e o cache, Paula fecha o "
                "protótipo, Diego liga para o cliente do PDF.",
                0.6,
            ),
            ("Helena", "E eu atualizo a base de conhecimento do suporte quando sair.", 0.4),
            (
                "Beatriz",
                "Ótimo. Próxima revisão na semana que vem, com o protótipo e a medição nova.",
                0.5,
            ),
        ],
    },
    {
        "id": "reuniao_03",
        "titulo": "Retrospectiva da entrega",
        "data": "2026-11-10T14:00:00Z",
        "revisar": False,
        "falas": [
            (
                "Marcos",
                "Vamos fazer a retrospectiva da primeira entrega da exportação. "
                "Quem quer começar pelo que funcionou?",
                0.0,
            ),
            (
                "Paula",
                "Eu começo. Ter o protótipo validado com os clientes antes de "
                "codificar economizou pelo menos uma semana de retrabalho.",
                0.6,
            ),
            (
                "Diego",
                "Concordo. E a ligação para o cliente do PDF foi ótima. Ele "
                "entendeu a ordem e até ajudou a priorizar.",
                0.5,
            ),
            (
                "Sofia",
                "Do lado de dados, eu queria registrar que o índice novo também "
                "melhorou outros relatórios, que nem estavam no escopo.",
                0.8,
            ),
            ("Marcos", "Boa. E o que não funcionou?", 0.4),
            (
                "Diego",
                "A estimativa. A gente disse duas semanas e levou três, porque o "
                "filtro por período tinha casos que ninguém previu.",
                0.6,
            ),
            (
                "Sofia",
                "Fuso horário, principalmente. Relatório de cliente em outro país "
                "cortava o último dia do mês.",
                -1.2,
            ),
            (
                "Marcos",
                "Isso precisa virar teste automatizado. Não pode depender de alguém "
                "lembrar do fuso na próxima vez.",
                0.4,
            ),
            (
                "Paula",
                "E eu sugiro incluir alguém de dados no começo do próximo projeto, "
                "não só no fim. | A Sofia teria visto o problema do fuso na primeira "
                "conversa.",
                0.7,
            ),
            ("Marcos", "Uhum.", -2.0),
            ("Sofia", "Com certeza. É só me chamar.", 0.3),
            (
                "Marcos",
                "Então ficam três ações: teste de fuso horário, dados desde o começo "
                "e estimativa com folga para casos de borda.",
                0.6,
            ),
            (
                "Diego",
                "E uma comemoração, porque o tempo do painel de orbita caiu para três segundos.",
                0.5,
            ),
            ("Paula", "Isso merece.", -1.0),
            ("Marcos", "Merece mesmo. Obrigado, pessoal.", 0.4),
        ],
    },
]
