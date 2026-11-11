/** Cliente HTTP compartilhado por todos os modulos de api/. */
import { mensagem, type Mensagem } from "../i18n/mensagem";
import { textosAtuais, type Catalogo } from "../i18n/textos";

/** Erro ou aviso do servidor: codigo + parametros (trama/erros.py). O
 * texto, no idioma escolhido, sai do catalogo (i18n/<idioma>/erros.ts). */
export interface CodigoComParametros {
  codigo: string;
  parametros?: Record<string, string | number>;
}

function ehCodigo(valor: unknown): valor is CodigoComParametros {
  return !!valor && typeof valor === "object" && typeof (valor as { codigo?: unknown }).codigo === "string";
}

export function textoDoCodigo(c: CodigoComParametros, catalogo: Catalogo = textosAtuais()): string {
  const t = catalogo.erros;
  const texto = t.porCodigo[c.codigo];
  return texto ? texto(c.parametros ?? {}) : t.codigoDesconhecido(c.codigo);
}

/**
 * Aviso para a tela: codigo (servidor atual), texto (.json gravado antes
 * dos codigos - mostrado como esta), ou lista dos dois. null quando nao ha.
 */
export function textoDoAviso(aviso: unknown, catalogo: Catalogo = textosAtuais()): string | null {
  if (!aviso) return null;
  if (typeof aviso === "string") return aviso;
  if (Array.isArray(aviso)) {
    const textos = aviso.map((a) => textoDoAviso(a, catalogo)).filter((a): a is string => !!a);
    return textos.length ? textos.join(" ") : null;
  }
  return ehCodigo(aviso) ? textoDoCodigo(aviso, catalogo) : null;
}

/** Aviso do servidor (codigo, texto antigo ou lista) guardado como
 * Mensagem - resolvido no render, no idioma da hora. */
export function mensagemDoAviso(aviso: unknown): Mensagem | null {
  return aviso ? mensagem((t) => textoDoAviso(aviso, t) ?? "") : null;
}

/**
 * Erro das rotas da API: carrega a Mensagem (codigo + parametros), nao o
 * texto - a tela guarda `erro.mensagem` e resolve no render. `message`
 * (o texto no idioma da hora) so serve para log e para quem nao conhece a
 * classe.
 */
export class ErroDaApi extends Error {
  readonly mensagem: Mensagem;

  constructor(m: Mensagem) {
    super(m.texto(textosAtuais()));
    this.name = "ErroDaApi";
    this.mensagem = m;
  }
}

/** A Mensagem de qualquer erro pego num catch: a da API, ou o texto do
 * erro do navegador como veio (nao ha codigo para traduzir). */
export function mensagemDe(e: unknown): Mensagem {
  if (e instanceof ErroDaApi) return e.mensagem;
  const texto = e instanceof Error ? e.message : String(e);
  return mensagem(() => texto);
}

/**
 * Mensagem para uma resposta de erro, no idioma da interface - nunca o
 * texto cru do FastAPI/Starlette.
 *
 * Toda rota do Trama que responde erro de proposito manda `detail` como
 * {codigo, parametros}. "Not Found" / "Method Not Allowed" em ingles so
 * aparecem quando a ROTA nem existe no servidor que esta rodando: o
 * frontend foi atualizado e o servidor ainda roda o codigo de antes
 * (aconteceu: Pessoas, Glossario, Sobre e a revisao responderam "Not
 * Found" ate o servidor ser reiniciado). `detail` de validacao do
 * FastAPI (422, uma lista) tambem nunca vai crua para a tela.
 */
export function mensagemDeErro(status: number, corpo: unknown, padrao?: Mensagem): Mensagem {
  const detalhe =
    corpo && typeof corpo === "object" && "detail" in corpo
      ? (corpo as { detail: unknown }).detail
      : undefined;
  if (
    (status === 404 && detalhe === "Not Found") ||
    (status === 405 && detalhe === "Method Not Allowed")
  ) {
    return mensagem((t) => t.erros.servidorDesatualizado);
  }
  if (ehCodigo(detalhe)) return mensagem((t) => textoDoCodigo(detalhe, t));
  // servidor de antes dos codigos: o texto pronto que ele mandou
  if (typeof detalhe === "string" && detalhe) return mensagem(() => detalhe);
  if (status === 422) return mensagem((t) => t.erros.dadosRecusados);
  return padrao ?? mensagem((t) => t.erros.falhaComServidor(status));
}

export async function buscarJson<T>(caminho: string): Promise<T> {
  const resposta = await fetch(caminho);
  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    throw new ErroDaApi(mensagemDeErro(resposta.status, corpo));
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
    throw new ErroDaApi(mensagemDeErro(resposta.status, corpoErro));
  }
  return resposta.json() as Promise<T>;
}
