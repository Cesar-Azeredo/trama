# Trama — Guia de uso da marca

## 1. A logo

**A ideia:** um fio que dá uma volta sobre si mesmo e segue em frente. A volta é a memória (o app lembra o que foi dito em reuniões anteriores), o cruzamento por cima e por baixo é a própria trama de um tecido, e a cauda mais longa à direita é a conversa que continua.

**Versões**

| Versão | Quando usar | Arquivo |
|---|---|---|
| Horizontal (principal) | Site, documentos, apresentações, assinaturas de e-mail | `03-horizontal/` |
| Empilhada | Espaços quadrados ou estreitos: perfis, crachás, camisetas | `04-empilhado/` |
| Símbolo | Ícone do app, favicon, avatar, quando o nome já aparece por perto | `02-simbolo/` |
| Palavra | Quando o símbolo já aparece na mesma tela ou peça | `05-palavra/` |
| Símbolo pequeno | Só para 16–32 px: tem o fio mais grosso e o cruzamento mais aberto | `01-mestres/trama-simbolo-pequeno*.svg` |

Os arquivos em `01-mestres/` são a fonte original de tudo. Para telas, use SVG ou PNG. Para gráfica, use os PDFs de `07-impressao/`.

## 2. Área de respiro

Mantenha livre, em volta da logo, um espaço igual à **altura do "a" da palavra trama**. Na versão só com o símbolo, use **⅓ da largura do símbolo**. O espaço cresce e diminui junto com a logo.

## 3. Tamanho mínimo

| Versão | Tela | Impressão |
|---|---|---|
| Horizontal | 96 px de largura | 25 mm de largura |
| Empilhada | 64 px de largura | 18 mm de largura |
| Símbolo | 16 px (usar o arquivo pequeno abaixo de 32 px) | 6 mm |

## 4. Cores

| Nome | HEX | RGB | Uso |
|---|---|---|---|
| **Verde Trama** | `#0E5A4A` | 14 90 74 | Cor principal da logo, ícone do app, botões principais |
| **Fio** (ocre) | `#E3A33B` | 227 163 59 | Acento: destacar falantes, trechos e marcações na interface. Nunca na logo nem em texto sobre branco |
| **Tinta** | `#14201C` | 20 32 28 | Textos e versão escura da logo |
| **Linho** | `#F4F0E6` | 244 240 230 | Fundos claros e logo invertida |

**Contraste:** Verde sobre branco 8,1:1 · Verde sobre Linho 7,2:1 · Tinta sobre Linho 14,7:1 · Fio sobre Tinta 7,6:1. Todos passam no nível AA para texto. Fio sobre branco (2,2:1) não passa e serve só como cor de destaque, nunca para texto.

**Impressão:** os valores CMYK e Pantone devem ser definidos com a gráfica a partir do HEX, conferindo numa escala física. Não use conversões automáticas sem prova.

**Combinações aprovadas:** Verde sobre branco ou Linho · Linho sobre Verde · Linho sobre Tinta · Tinta sobre branco · preto ou branco puro quando a peça for de uma cor só.

## 5. Tipografia

A palavra "trama" foi desenhada à mão e não é uma fonte. Nunca a substitua digitando o nome.

Para a interface e os materiais, a sugestão é a **Figtree** (Google Fonts, licença livre). Ela é geométrica e amigável como a logo, mas não compete com ela. Use Semibold para títulos e Regular ou Medium para textos. Se ela não estiver disponível, use `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.

## 6. O que não fazer

Não estique nem achate a logo. Não gire nem espelhe o símbolo: ele tem direção, e a conversa segue para a direita. Não mude as cores fora da paleta. Não aplique sombra, contorno, degradê ou efeitos. Não feche o espaço do cruzamento. Não mude a posição ou o tamanho entre símbolo e palavra. Não coloque a logo sobre fotos agitadas sem uma área calma ou um fundo sólido.

## 7. Notas de entrega

- **Testes feitos:** leitura em 16, 24, 32 e 64 px; versão de uma cor; invertida (com o traço cerca de 6% mais fino para compensar o efeito ótico do claro sobre escuro); comparação com a categoria de comunicação e reuniões, que é dominada por azul, balão de fala e onda sonora.
- **Pendências:** definição de CMYK e Pantone com a gráfica. Os e-mails e domínios nos mockups são apenas ilustrativos.
- **Arquivos editáveis:** os SVGs abrem no Figma, Illustrator e Inkscape. As partes das letras já estão unidas, e o símbolo é feito de dois contornos (o fio de baixo e o de cima).
