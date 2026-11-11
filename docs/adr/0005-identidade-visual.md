# ADR 0005 — Identidade visual: transcrição editorial

- **Data:** 2026-09-16
- **Situação:** aceito

## Contexto

O produto é vendido para empresas que confiam dados sensíveis a ele.
Interface que parece gerada por IA — cartão arredondado com sombra suave,
fundo cinza-azulado, Inter, ícone decorativo, gradiente — comunica descuido
justamente onde a venda depende de parecer sério.

## Decisão

A metáfora é página de transcrição editorial: entrevista de revista, script
de peça. O transcript é o produto; a interface some em volta dele.

Tokens, fontes e a lista do que é proibido: `.claude/skills/identidade-rec-meet/SKILL.md`.
Movimento, resposta e gesto: skill `apple-design`.

## Alternativas descartadas

**Dashboard.** O usuário lê uma reunião, não monitora métricas.

**Biblioteca de componentes pronta.** É a origem da aparência genérica:
todo produto que usa fica com a mesma cara.

**Fonte do sistema (`system-ui`).** Vira San Francisco no Mac e Segoe UI no
Windows — o mesmo código com duas aparências. O cliente corporativo é
majoritariamente Windows. As fontes são empacotadas com o app.

## Consequências

- Fontes em `.woff2` no repositório, servidas localmente. Nunca Google Fonts
  por CDN: o app roda offline.
- A fita vertical de tempo é derivada dos turnos reais do `.json`, não é
  enfeite: serve de navegação e mostra a forma da reunião.
- Toda tela nova passa pela skill. Deriva visual é regressão.
