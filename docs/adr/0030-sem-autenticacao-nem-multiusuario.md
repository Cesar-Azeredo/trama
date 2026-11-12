# ADR 0030 — Sem autenticação, sem rate limit, sem multiusuário

- **Data:** 2026-11-12
- **Situação:** aceito

## Contexto

Até aqui isto era só uma regra do `CLAUDE.md` ("é um processo em
localhost com um usuário"), sem o porquê registrado. O antigo
`CLAUDE.md` apontava para o ADR 0005, que é sobre identidade visual.

O Trama roda inteiro na máquina de quem usa: o servidor FastAPI escuta só
em `127.0.0.1` (ADR 0004), e quem abre o app é a mesma pessoa que tem os
arquivos. Tudo o que o servidor guarda está em disco, legível pelo usuário
do sistema operacional: `audios/` (áudio, `.json`, `.txt`), `vozes.db` e
`termos.txt`.

## Decisão

O servidor não tem login, senha, token, sessão, JWT, papéis, rate limit
nem noção de mais de um usuário. Cada instalação é de uma pessoa, numa
máquina. Quem precisa que outra pessoa veja uma reunião leva o `.txt`
baixado; não há compartilhamento pelo app.

A fronteira de segurança é a da máquina e da conta do sistema operacional,
mais o bind em `127.0.0.1`. Nada que o servidor fizesse protegeria além
dela.

## Alternativas descartadas

- **Senha local para abrir o app.** Não protege nada: quem está logado na
  conta lê `audios/` e `vozes.db` direto do disco, sem passar pelo
  servidor. Seria uma porta trancada ao lado de uma parede aberta, e mais
  uma senha para a pessoa esquecer, sem como recuperar sem um servidor
  fora da máquina.
- **Multiusuário (contas, permissões por reunião).** Exige servidor
  compartilhado, ou seja, áudio de reunião saindo da máquina de quem
  gravou — o contrário do produto. A empresa que precisa disso já não é
  o público do Trama.
- **Rate limit.** Protege um servidor exposto contra abuso de terceiros.
  Aqui só a própria pessoa chama a API; o único recurso caro, o
  processamento, já é limitado a um por vez (`processamento.py`).
- **Token por sessão entre o navegador e o servidor.** Contra outro
  processo da mesma conta, não adianta: ele lê o token do mesmo jeito que
  lê os arquivos.

## Consequências

- Quem tem acesso à conta do sistema operacional tem acesso a tudo. Para
  um pedido de proteção maior, a resposta é a do sistema: disco
  criptografado (FileVault, BitLocker), conta com senha, bloqueio de tela.
- Se um dia o app precisar ser aberto de outra máquina (um servidor
  compartilhado na empresa), esta decisão cai inteira: aí autenticação
  deixa de ser opcional, e o bind em `127.0.0.1` também muda. Isso pede um
  ADR novo que supere este, nunca uma exceção pontual.
- **Premissa a garantir:** só o próprio app fala com o servidor. O bind em
  `127.0.0.1` impede outra máquina, mas não uma página de outro site aberta
  no mesmo navegador. Conferido em 2026-11-12 (FastAPI 0.162):
  - pedidos com corpo JSON e `DELETE` passam por preflight de CORS, que o
    servidor não habilita (405, sem `Access-Control-Allow-Origin`), e o
    navegador os bloqueia; JSON enviado como `text/plain` para fugir do
    preflight é recusado (422);
  - o upload de áudio (`POST /api/reunioes`, multipart) é pedido simples,
    sem preflight: outra página consegue **enviar** um arquivo, que vira
    uma reunião na fila, mesmo sem ler a resposta;
  - uma página que troque o próprio domínio para `127.0.0.1` (DNS
    rebinding) faz pedidos que o navegador trata como da mesma origem, e
    aí lê e apaga.

  A proteção que cabe nesta decisão é conferir a origem, não autenticar.
  **Feita em 2026-11-12** (`trama/servidor/origem.py`, um middleware antes
  de toda rota): `Host` tem de ser `127.0.0.1` ou `localhost` na porta do
  servidor (`TRAMA_PORTA`), o que fecha o rebinding; `Origin`, quando vem,
  tem de ser `http://127.0.0.1` ou `http://localhost` na porta do
  frontend (`TRAMA_PORTA_FRONTEND`, padrão 5173) ou na do próprio
  servidor, o que fecha o upload. O resto leva 403 com código
  (`host_recusado`, `origem_recusada`), sem tocar disco nem banco. O Vite
  passou a exigir a porta dele (`strictPort`): subir noutra porta
  silenciosamente faria toda chamada levar 403.
