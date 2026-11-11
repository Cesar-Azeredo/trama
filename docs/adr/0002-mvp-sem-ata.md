# ADR 0002 — O MVP entrega transcrição identificada, sem ata

- **Data:** 2026-09-16
- **Situação:** aceito

## Contexto

`ata.py` funciona: gera ata em português via Ollama, em blocos, com
verificação textual de cada citação contra o transcript. Mas dois modelos
foram medidos na mesma reunião de 70 minutos:

| Modelo | Tempo | RAM | Qualidade |
|---|---|---|---|
| `llama3.1:8b` | 2,4 min | ~5 GB | insuficiente |
| `qwen3.8:27b-mlx` | ~20 min | ~18 GB | boa, com erros factuais |

E há um erro estrutural, reproduzido em 3 tentativas com 2 modelos e 3
prompts: o processamento em blocos não enxerga relações causais entre
blocos. A ata afirmou que o custo do ChatGPT "não foi avaliado" quando o
transcript traz a estimativa explícita — a pergunta e a resposta estavam em
blocos diferentes.

## Decisão

O MVP entrega o transcript com quem falou o quê. Sem ata.

## Alternativas descartadas

**Ata local como feature principal.** Exigiria ~18 GB de RAM no cliente.
Filtra o mercado duas vezes: empresa com dado sensível **e** com hardware de
estação de trabalho.

**Fine-tune de um modelo para atas.** Não ataca a causa. O modelo não erra
por falta de especialização em atas; erra por não ver o texto que está fora
da janela dele. Fine-tune produziria atas bem formatadas com o mesmo erro
factual.

**Ata via API na primeira versão.** Adia o MVP e abre a discussão de
confidencialidade antes de haver produto. Vira segunda conversa (ADR 0003).

## Consequências

- O produto não compete com Copilot, Gemini ou ChatGPT: ele alimenta a IA
  que a empresa já usa.
- Roda em qualquer máquina, porque não precisa de LLM local.
- A correção arquitetural da ata (extrair um índice de perguntas, decisões e
  pendências com timestamp numa primeira passada, e amarrar numa segunda)
  fica registrada aqui como caminho, não implementada.
