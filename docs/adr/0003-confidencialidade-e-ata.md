# ADR 0003 — Confidencialidade: três níveis, sem promessa falsa

- **Data:** 2026-09-16
- **Situação:** aceito

## Contexto

O argumento de venda é que a empresa não precisa mandar áudio de reunião
para fora. Quando a ata entrar, algum texto precisa chegar a um LLM. Surgiu
a pergunta: dá para oferecer segurança no uso da chave de API do cliente?

A chave em si dá para proteger: se o app roda na máquina do cliente e a
chave nunca passa pela nossa infraestrutura, isso é propriedade da
arquitetura, não promessa. O que **não** dá para prometer é que o provedor
não veja o texto que recebeu. Nenhuma configuração impede isso.

## Decisão

Três níveis explícitos, com o trade-off na mão do cliente:

1. **Sem ata** — transcrição identificada. Nada sai. É o MVP.
2. **Ata com a chave do cliente** — o áudio e os perfis de voz nunca saem;
   só texto sai, para um fornecedor com quem a empresa já tem contrato,
   sob os termos dela. Endpoint configurável, para quem roda Azure OpenAI no
   próprio tenant e não adiciona fornecedor nenhum à cadeia.
3. **Ata local via Ollama** — nada sai. Exige ~18 GB de RAM. É o nível
   premium, para quem tem a dor e compra a máquina junto.

## Alternativas descartadas

**Prometer confidencialidade com API de terceiro.** Seria mentira.
"Não treina com seus dados" é diferente de "não tem acesso aos seus dados".

**Só ata local.** Elimina o cliente que aceita o trade-off e tem o contrato
com o provedor.

## Consequências

- A chave vai no Keychain do macOS ou no Credential Manager do Windows.
  Nunca em arquivo texto, nunca em log.
- Antes de enviar, o app mostra exatamente o que vai sair e registra num log
  local o quê e quando. Trilha de auditoria é argumento de venda.
- Reduzir a superfície: mandar o índice extraído em vez do transcript bruto,
  e anonimizar nomes antes do envio, remapeando na volta.
- Não somos operador dos dados biométricos em nenhum dos três níveis.
