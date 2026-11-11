/** Cliente HTTP compartilhado por todos os modulos de api/. */

export const MENSAGEM_SERVIDOR_DESATUALIZADO =
  "O servidor está desatualizado. Reinicie o servidor e recarregue a página.";

/**
 * Mensagem em portugues para uma resposta de erro - nunca o texto cru do
 * FastAPI/Starlette em ingles.
 *
 * Toda rota do rec-meet que responde 404/405 de proposito manda `detail`
 * em portugues ("Reunião não encontrada."). "Not Found" / "Method Not
 * Allowed" em ingles so aparecem quando a ROTA nem existe no servidor que
 * esta rodando: o frontend foi atualizado e o servidor ainda roda o codigo
 * de antes (aconteceu: Pessoas, Glossario, Sobre e a revisao responderam
 * "Not Found" ate o servidor ser reiniciado). `detail` que nao e texto
 * (a lista de erros de validacao do FastAPI, 422) tambem nunca vai crua
 * para a tela.
 */
export function mensagemDeErro(status: number, corpo: unknown, padrao?: string): string {
  const detalhe =
    corpo && typeof corpo === "object" && "detail" in corpo
      ? (corpo as { detail: unknown }).detail
      : undefined;
  if (
    (status === 404 && detalhe === "Not Found") ||
    (status === 405 && detalhe === "Method Not Allowed")
  ) {
    return MENSAGEM_SERVIDOR_DESATUALIZADO;
  }
  if (typeof detalhe === "string" && detalhe) return detalhe;
  if (status === 422) {
    return "O servidor recusou os dados enviados. Recarregue a página e tente de novo.";
  }
  return padrao ?? `Falha ao falar com o servidor (${status}).`;
}

export async function buscarJson<T>(caminho: string): Promise<T> {
  const resposta = await fetch(caminho);
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    throw new Error(mensagemDeErro(resposta.status, corpo));
  }
  return resposta.json() as Promise<T>;
}

export async function enviarJson<T>(
  caminho: string,
  corpo: unknown,
  metodo: "POST" | "PUT" | "DELETE" = "POST",
): Promise<T> {
  const resposta = await fetch(caminho, {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  if (!resposta.ok) {
    const corpoErro = await resposta.json().catch(() => null);
    throw new Error(mensagemDeErro(resposta.status, corpoErro));
  }
  return resposta.json() as Promise<T>;
}
