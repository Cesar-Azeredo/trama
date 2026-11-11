"""
ferramentas/roteiro_demo_en.py - Roteiro das reunioes de demonstracao em
ingles. Mesmo desenho do roteiro em portugues (roteiro_demo.py): reuniao 1
revisada e que ensina as vozes, reuniao 2 com nomes ja sugeridos pela
galeria (e duas pessoas novas), reuniao 3 a revisar, com uma voz que a
galeria nao conhece. Tudo ficticio.

Mesma notacao: (pessoa, texto, pausa_s); "~palavra" = duvida do Whisper;
"|" = silencio sem texto (lacuna); pausa negativa = entra por cima.

O produto ficticio "Orbit Board" aparece mal transcrito de dois jeitos:
"orbit bored" (o termos.exemplo.en.txt corrige) e "or bit board" (nenhuma
regra corrige - aparece como variacao parecida para conferir).
"""

PESSOAS = ["Alice", "Ben", "Chloe", "Daniel", "Emma", "Frank"]
DESCONHECIDA = "Grace"

REUNIOES = [
    {
        "id": "reuniao_01",
        "titulo": "Quarterly planning",
        "data": "2026-11-03T14:00:00Z",
        "revisar": True,
        "falas": [
            (
                "Alice",
                "Good morning, everyone. Let's start with the quarterly plan, because "
                "today's agenda is long and I want us to leave with three goals agreed.",
                0.0,
            ),
            (
                "Ben",
                "On the product side, the priority is still the orbit bored. Customers "
                "have been asking for report exports since August.",
                0.6,
            ),
            ("Chloe", "And support feels that every day.", -1.2),
            (
                "Chloe",
                "Half of last week's tickets were about exports. If we fix that, our "
                "response time drops by half.",
                0.3,
            ),
            (
                "Daniel",
                "I agree with the priority, but engineering is two people short until "
                "December. We can't promise exports and the new permissions screen in "
                "the same quarter.",
                0.8,
            ),
            ("Alice", "Uh-huh.", -3.0),
            (
                "Alice",
                "Then let's choose. Which of the two has more impact on the retention ~OKR?",
                0.5,
            ),
            (
                "Ben",
                "Exports, no doubt. Permissions were requested by two large customers, | "
                "but exports come up in almost every renewal conversation.",
                0.4,
            ),
            ("Daniel", "So permissions move to January.", -1.2),
            (
                "Daniel",
                "I prefer that. With a single delivery we can test it properly before "
                "releasing it to everyone.",
                0.2,
            ),
            (
                "Chloe",
                "Can I put together the list of customers who asked the most, so Ben can "
                "talk to them before closing the scope?",
                0.7,
            ),
            ("Ben", "Please do, that helps a lot. By Thursday?", 0.4),
            ("Chloe", "By Thursday.", 0.2),
            (
                "Alice",
                "Second goal: the ~NPS. We dropped four points last quarter and I want to "
                "understand why before setting a target.",
                0.9,
            ),
            (
                "Chloe",
                "Most of the low scores mention how slow the or bit board gets when a "
                "report is large. It's not a bug, it's loading time.",
                0.5,
            ),
            (
                "Daniel",
                "We can tackle that together with exports. It's the same query underneath, "
                "so speeding up one improves the other.",
                -1.1,
            ),
            (
                "Alice",
                "Great. So the second goal is to win back the four ~NPS points, with "
                "loading time as the indicator.",
                0.6,
            ),
            (
                "Ben",
                "For the third goal I suggest documentation. The sales team has been "
                "asking for new material since the launch.",
                0.8,
            ),
            (
                "Alice",
                "Agreed. Daniel, can you estimate exports before our next meeting?",
                0.5,
            ),
            (
                "Daniel",
                "I can give a rough estimate by Monday, and a firmer one once Ben closes "
                "the scope with the customers.",
                0.4,
            ),
            (
                "Alice",
                "Perfect. So we agreed: exports in the orbit bored, four ~NPS points and "
                "the documentation for sales. Thanks, everyone.",
                0.7,
            ),
        ],
    },
    {
        "id": "reuniao_02",
        "titulo": "Orbit Board review",
        "data": "2026-11-05T18:30:00Z",
        "revisar": True,
        "falas": [
            (
                "Ben",
                "Everyone, I talked to the six customers on Chloe's list. Five want the "
                "export as a spreadsheet, one wants a PDF.",
                0.0,
            ),
            (
                "Emma",
                "On the design side, a spreadsheet is simpler. A PDF means thinking about "
                "pagination, headers and the customer's logo.",
                0.6,
            ),
            (
                "Frank",
                "Same for engineering. The spreadsheet comes straight out of the query "
                "that already exists in the orbit bored.",
                0.5,
            ),
            ("Alice", "So we start with the spreadsheet and the PDF becomes a second step.", 0.4),
            (
                "Chloe",
                "Just one thing: the customer who asked for the PDF is our largest "
                "account. It's worth telling them first, so it doesn't look like we "
                "ignored them.",
                0.7,
            ),
            ("Ben", "I'll call them tomorrow.", -1.1),
            (
                "Ben",
                "And I'll show them the spreadsheet prototype, if Emma has something by then.",
                0.2,
            ),
            (
                "Emma",
                "I have a draft. It isn't pretty, | but it shows the columns and the date "
                "filter, which came up the most in the conversations.",
                0.5,
            ),
            ("Chloe", "Right.", -2.5),
            (
                "Frank",
                "About loading time: I measured it yesterday. A one-year report takes "
                "eleven seconds in the or bit board. The target I propose is three seconds.",
                0.9,
            ),
            ("Alice", "Is three seconds realistic?", 0.3),
            (
                "Frank",
                "With a new database index and a result cache, yes. I already tried the "
                "index on a copy and it went down to four.",
                0.3,
            ),
            (
                "Chloe",
                "That changes a lot for support. Slowness is the number one complaint in "
                "the low ~NPS scores.",
                0.6,
            ),
            (
                "Emma",
                "I'd also like to propose something on the screen: while it loads, show "
                "what has already arrived instead of an empty screen.",
                0.8,
            ),
            ("Frank", "We can, but it grows the scope. I'd leave it until after the index.", -1.3),
            (
                "Frank",
                "First the fast query, then we see if we still need partial loading.",
                0.3,
            ),
            (
                "Alice",
                "Agreed. Frank takes the index and the cache, Emma finishes the "
                "prototype, Ben calls the PDF customer.",
                0.6,
            ),
            ("Chloe", "And I'll update the support knowledge base when it ships.", 0.4),
            (
                "Alice",
                "Great. Next review next week, with the prototype and the new measurement.",
                0.5,
            ),
        ],
    },
    {
        "id": "reuniao_03",
        "titulo": "Release retrospective",
        "data": "2026-11-10T15:00:00Z",
        "revisar": False,
        "falas": [
            (
                "Daniel",
                "Let's do the retrospective of the first export release. Who wants to "
                "start with what worked?",
                0.0,
            ),
            (
                "Emma",
                "I'll start. Validating the prototype with customers before writing code "
                "saved us at least a week of rework.",
                0.6,
            ),
            (
                "Ben",
                "Agreed. And the call with the PDF customer went great. They understood "
                "the order and even helped us prioritize.",
                0.5,
            ),
            (
                "Grace",
                "From the data side, I want to note that the new index also sped up other "
                "reports that weren't even in scope.",
                0.8,
            ),
            ("Daniel", "Nice. And what didn't work?", 0.4),
            (
                "Ben",
                "The estimate. We said two weeks and it took three, because the date "
                "filter had cases nobody foresaw.",
                0.6,
            ),
            (
                "Grace",
                "Time zones, mostly. Reports for customers in other countries cut off the "
                "last day of the month.",
                -1.2,
            ),
            (
                "Daniel",
                "That has to become an automated test. It can't depend on someone "
                "remembering time zones next time.",
                0.4,
            ),
            (
                "Emma",
                "And I suggest bringing someone from data in at the start of the next "
                "project, not just at the end. | Grace would have caught the time zone "
                "issue in the first conversation.",
                0.7,
            ),
            ("Daniel", "Uh-huh.", -2.0),
            ("Grace", "Absolutely. Just call me.", 0.3),
            (
                "Daniel",
                "So we have three actions: a time zone test, data from the start, and "
                "estimates with room for edge cases.",
                0.6,
            ),
            (
                "Ben",
                "And a celebration, because loading time in the orbit bored dropped to "
                "three seconds.",
                0.5,
            ),
            ("Emma", "Well deserved.", -1.0),
            ("Daniel", "Absolutely. Thanks, everyone.", 0.4),
        ],
    },
]
