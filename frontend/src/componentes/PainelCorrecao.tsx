import { Fragment, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import {
  aplicarCorrecao,
  aplicarVariacoes,
  previaCorrecao,
  sugerirVariacoes,
  type PreviaCorrecao,
  type SugestaoVariacoes,
} from "../api/correcoes";
import { corrigirFala, type Fala, type FalaAlterada } from "../api/reunioes";
import { DESCRICAO_MAX_LEN, definirDescricao, TERMO_MAX_LEN } from "../api/termos";
import { useTextos } from "../i18n/textos";
import "./PainelCorrecao.css";

function formatarHorario(segundos: number): string {
  const s = Math.floor(segundos);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const par = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${par(m)}:${par(s % 60)}` : `${par(m)}:${par(s % 60)}`;
}

/**
 * Frase do catalogo com {marcador}: cada marcador vira o elemento dado
 * (numero ou trecho com estilo proprio), o resto continua texto. A frase
 * inteira vem do catalogo, na ordem do idioma - nunca pedacos colados.
 */
function preencher(modelo: string, partes: Record<string, ReactNode>): ReactNode[] {
  return modelo
    .split(/(\{[a-z]+\})/)
    .map((pedaco, i) => {
      const chave = pedaco.match(/^\{([a-z]+)\}$/)?.[1];
      return chave !== undefined && chave in partes ? (
        <Fragment key={i}>{partes[chave]}</Fragment>
      ) : (
        pedaco
      );
    });
}

/**
 * Depois de corrigir em todas: formas parecidas do mesmo termo (ADR 0020).
 * Nada e trocado sem marcar; cada caixa comeca desmarcada.
 */
function VariacoesParecidas({
  trecho,
  certo,
  aoCorrigir,
}: {
  trecho: string;
  certo: string;
  aoCorrigir: () => void;
}) {
  const t = useTextos().correcao;
  const [sugestao, setSugestao] = useState<SugestaoVariacoes | null>(null);
  const [marcadas, setMarcadas] = useState<Set<string>>(new Set());
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [feito, setFeito] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    sugerirVariacoes(trecho, certo)
      .then((s) => {
        if (!cancelado) setSugestao(s);
      })
      .catch((e: Error) => {
        if (!cancelado) setErro(e.message);
      });
    return () => {
      cancelado = true;
    };
  }, [trecho, certo]);

  function alternar(forma: string) {
    setMarcadas((atual) => {
      const nova = new Set(atual);
      if (nova.has(forma)) nova.delete(forma);
      else nova.add(forma);
      return nova;
    });
  }

  async function corrigirMarcadas() {
    if (!sugestao || marcadas.size === 0) return;
    setSalvando(true);
    setErro(null);
    try {
      const r = await aplicarVariacoes(certo, [...marcadas], sugestao.assinatura);
      setFeito(
        t.maisCorrigidos(r.total) +
          (r.aviso ? ` ${r.aviso}` : ""),
      );
      aoCorrigir();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSalvando(false);
    }
  }

  if (feito) {
    return (
      <p className="painel-correcao__feito" role="status">
        {feito}
      </p>
    );
  }
  if (erro && !sugestao) return <p className="painel-correcao__erro">{erro}</p>;
  if (!sugestao) return <p className="painel-correcao__nota">{t.procurandoParecidas}</p>;
  if (sugestao.variacoes.length === 0) return null;

  return (
    <fieldset className="painel-correcao__variacoes">
      <legend className="painel-correcao__titulo">{t.talvezTambem(certo)}</legend>
      <ul>
        {sugestao.variacoes.map((v) => (
          <li key={v.forma}>
            <label className="painel-correcao__variacao">
              <input
                type="checkbox"
                checked={marcadas.has(v.forma)}
                onChange={() => alternar(v.forma)}
              />
              <span>
                <span className="painel-correcao__forma">{v.forma}</span>{" "}
                <span className="painel-correcao__nota-inline">
                  {t.vezes(v.total)}
                  {v.baixa_confianca ? ` · ${t.jaTinhaDuvida}` : ""}
                </span>
              </span>
            </label>
            <ul className="painel-correcao__contextos">
              {v.ocorrencias.map((o, k) => (
                <li key={k}>
                  <a
                    className="numeros"
                    href={`#/reuniao/${o.id}/em/${Math.floor(o.inicio)}`}
                  >
                    {o.titulo}, {formatarHorario(o.inicio)}
                  </a>{" "}
                  …{o.antes}
                  <strong>{o.trecho}</strong>
                  {o.depois}…
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      {erro && (
        <p className="painel-correcao__erro" role="alert">
          {erro}
        </p>
      )}
      <div className="painel-correcao__acoes">
        <button
          type="button"
          className="painel-correcao__primario"
          disabled={marcadas.size === 0 || salvando}
          onClick={corrigirMarcadas}
        >
          {salvando
            ? t.corrigindo
            : marcadas.size === 0
              ? t.marqueAsQueSao
              : t.corrigirMarcadas(marcadas.size)}
        </button>
      </div>
    </fieldset>
  );
}

/**
 * "Corrigir" de um trecho selecionado no transcript (Detalhe, ADR 0019).
 *
 * "Só nesta fala" e a correcao manual de fala (edicao.py). "Em todas as
 * reuniões e nas próximas" mostra antes onde trocaria (previa) e so grava
 * o que a pessoa viu. Nunca fala em "regra" nem em "glossário": para quem
 * usa, e corrigir uma palavra.
 *
 * Desktop: preso a selecao. Celular: folha que sobe de baixo (CSS).
 */
export function PainelCorrecao({
  reuniaoId,
  indice,
  fala,
  inicio,
  fim,
  topo,
  aoFechar,
  aoCorrigirFala,
  aoCorrigirEmTodas,
  embutido = false,
}: {
  /** Dentro de outro bloco (revisao de termos), em vez de preso a selecao. */
  embutido?: boolean;
  reuniaoId: string;
  indice: number;
  fala: Fala;
  /** posicao do trecho em fala.texto */
  inicio: number;
  fim: number;
  /** px, relativo ao transcript - onde o painel abre no desktop */
  topo: number;
  aoFechar: () => void;
  aoCorrigirFala: (alterada: FalaAlterada) => void;
  /** Depois de corrigir em todas: o transcript precisa ser relido. */
  aoCorrigirEmTodas: () => void;
}) {
  const t = useTextos().correcao;
  // Fixo na abertura: depois de "em todas" o Detalhe rele a reuniao, e o
  // mesmo intervalo de fala.texto ja traria o texto corrigido.
  const [trecho] = useState(() => fala.texto.slice(inicio, fim));
  const [textoDaFala] = useState(fala.texto);
  const [certo, setCerto] = useState(trecho);
  const [alcance, setAlcance] = useState<"fala" | "todas">("fala");
  const [descricao, setDescricao] = useState("");
  const [previa, setPrevia] = useState<PreviaCorrecao | null>(null);
  const [conferindo, setConferindo] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [feito, setFeito] = useState<string | null>(null);
  const campoRef = useRef<HTMLInputElement>(null);
  const id = useId();

  useEffect(() => {
    campoRef.current?.select();
  }, []);

  // A previa so existe para "em todas", e depende do certo (trecho que ja
  // esta escrito como o certo nao conta). Espera a pessoa parar de digitar.
  useEffect(() => {
    if (alcance !== "todas" || feito) return;
    setPrevia(null);
    setErro(null);
    if (!certo.trim() || certo.trim() === trecho) return;
    let cancelado = false;
    setConferindo(true);
    const espera = setTimeout(() => {
      previaCorrecao(trecho, certo)
        .then((p) => {
          if (!cancelado) setPrevia(p);
        })
        .catch((e: Error) => {
          if (!cancelado) setErro(e.message);
        })
        .finally(() => {
          if (!cancelado) setConferindo(false);
        });
    }, 300);
    return () => {
      cancelado = true;
      clearTimeout(espera);
    };
  }, [alcance, certo, trecho, feito]);

  const certoLimpo = certo.trim();
  const mudou = certoLimpo !== "" && certoLimpo !== trecho;
  const podeConfirmar =
    mudou && !salvando && (alcance === "fala" || (previa !== null && previa.total > 0));

  async function confirmar() {
    if (!podeConfirmar) return;
    setSalvando(true);
    setErro(null);
    try {
      if (alcance === "fala") {
        const novo = textoDaFala.slice(0, inicio) + certoLimpo + textoDaFala.slice(fim);
        const alterada = await corrigirFala(reuniaoId, indice, novo, fala.inicio);
        if (descricao.trim()) await definirDescricao(certoLimpo, descricao);
        aoCorrigirFala(alterada);
        aoFechar();
        return;
      }
      const r = await aplicarCorrecao({
        trecho,
        certo: certoLimpo,
        descricao,
        assinatura: previa!.assinatura,
      });
      setFeito(
        t.corrigidoEmTodas(r.total, r.aplicadas.length) +
          (r.aviso ? ` ${r.aviso}` : ""),
      );
      aoCorrigirEmTodas();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSalvando(false);
    }
  }

  function aoTeclar(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      aoFechar();
    }
  }

  const rotuloConfirmar =
    alcance === "fala"
      ? t.corrigir
      : previa && previa.total > 0
        ? t.corrigirEmLugares(previa.total)
        : t.corrigirEmTodas;

  return (
    <div
      className={"painel-correcao" + (embutido ? " painel-correcao--embutido" : "")}
      style={embutido ? undefined : { top: topo }}
      role="dialog"
      aria-labelledby={`${id}-titulo`}
      onKeyDown={aoTeclar}
    >
      <p className="painel-correcao__titulo" id={`${id}-titulo`}>
        {preencher(t.tituloPainel, {
          trecho: <span className="painel-correcao__trecho">{trecho}</span>,
        })}
      </p>

      {feito ? (
        <>
          <p className="painel-correcao__feito" role="status">
            {feito}
          </p>
          <VariacoesParecidas
            trecho={trecho}
            certo={certoLimpo}
            aoCorrigir={aoCorrigirEmTodas}
          />
          <div className="painel-correcao__acoes">
            <button type="button" className="painel-correcao__discreto" onClick={aoFechar}>
              {t.fechar}
            </button>
          </div>
        </>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            confirmar();
          }}
        >
          <label className="painel-correcao__rotulo" htmlFor={`${id}-certo`}>
            {t.oCertoE}
          </label>
          <input
            ref={campoRef}
            id={`${id}-certo`}
            className="painel-correcao__campo"
            value={certo}
            maxLength={TERMO_MAX_LEN}
            onChange={(e) => setCerto(e.target.value)}
          />

          <fieldset className="painel-correcao__alcance">
            <legend className="painel-correcao__rotulo">{t.ondeCorrigir}</legend>
            <label className="painel-correcao__opcao">
              <input
                type="radio"
                name={`${id}-alcance`}
                checked={alcance === "fala"}
                onChange={() => setAlcance("fala")}
              />
              {t.soNestaFala}
            </label>
            <label className="painel-correcao__opcao">
              <input
                type="radio"
                name={`${id}-alcance`}
                checked={alcance === "todas"}
                onChange={() => setAlcance("todas")}
              />
              {t.emTodas}
            </label>
          </fieldset>

          {alcance === "todas" && mudou && (
            <div className="painel-correcao__previa" aria-live="polite">
              {conferindo && <p className="painel-correcao__nota">{t.conferindo}</p>}
              {previa && previa.total === 0 && (
                <p className="painel-correcao__nota">
                  {t.naoAparece}
                </p>
              )}
              {previa && previa.total > 0 && (
                <details className="painel-correcao__onde">
                  <summary>
                    {preencher(t.aparece(previa.total, previa.reunioes.length), {
                      total: <span className="numeros">{previa.total}</span>,
                      reunioes: <span className="numeros">{previa.reunioes.length}</span>,
                    })}
                  </summary>
                  <ul>
                    {previa.reunioes.map((r) => (
                      <li key={r.id}>
                        <span className="painel-correcao__reuniao">{r.titulo}</span>
                        <ul>
                          {r.ocorrencias.map((o, k) => (
                            <li key={k}>
                              <a
                                className="numeros"
                                href={`#/reuniao/${r.id}/em/${Math.floor(o.inicio)}`}
                              >
                                {formatarHorario(o.inicio)}
                              </a>{" "}
                              …{o.antes}
                              <strong>{o.trecho}</strong>
                              {o.depois}…
                            </li>
                          ))}
                        </ul>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {previa?.aviso && <p className="painel-correcao__nota">{previa.aviso}</p>}
            </div>
          )}

          <label className="painel-correcao__rotulo" htmlFor={`${id}-descricao`}>
            {t.oQueEIsso} <span className="painel-correcao__opcional">{t.opcional}</span>
          </label>
          <input
            id={`${id}-descricao`}
            className="painel-correcao__campo"
            value={descricao}
            maxLength={DESCRICAO_MAX_LEN}
            placeholder={t.exemploDescricao}
            onChange={(e) => setDescricao(e.target.value)}
          />

          {erro && (
            <p className="painel-correcao__erro" role="alert">
              {erro}
            </p>
          )}

          <div className="painel-correcao__acoes">
            <button type="submit" className="painel-correcao__primario" disabled={!podeConfirmar}>
              {salvando ? t.corrigindo : rotuloConfirmar}
            </button>
            <button type="button" className="painel-correcao__discreto" onClick={aoFechar}>
              {t.cancelar}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
