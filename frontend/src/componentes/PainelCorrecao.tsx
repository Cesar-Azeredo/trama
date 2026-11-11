import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
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
import "./PainelCorrecao.css";

function formatarHorario(segundos: number): string {
  const s = Math.floor(segundos);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const par = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${par(m)}:${par(s % 60)}` : `${par(m)}:${par(s % 60)}`;
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
        `Mais ${r.total} ${r.total === 1 ? "lugar corrigido" : "lugares corrigidos"}.` +
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
  if (!sugestao) return <p className="painel-correcao__nota">Procurando formas parecidas…</p>;
  if (sugestao.variacoes.length === 0) return null;

  return (
    <fieldset className="painel-correcao__variacoes">
      <legend className="painel-correcao__titulo">Talvez estas também sejam {certo}</legend>
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
                  {v.total} {v.total === 1 ? "vez" : "vezes"}
                  {v.baixa_confianca ? " · a transcrição já tinha dúvida" : ""}
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
            ? "Corrigindo…"
            : marcadas.size === 0
              ? "Marque as que são"
              : `Corrigir ${marcadas.size === 1 ? "a marcada" : `as ${marcadas.size} marcadas`}`}
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
    const t = setTimeout(() => {
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
      clearTimeout(t);
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
        `Corrigido em ${r.total} ${r.total === 1 ? "lugar" : "lugares"}` +
          (r.aplicadas.length > 1 ? `, em ${r.aplicadas.length} reuniões` : "") +
          ". Vale também para as próximas reuniões." +
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
      ? "Corrigir"
      : previa && previa.total > 0
        ? `Corrigir em ${previa.total} ${previa.total === 1 ? "lugar" : "lugares"}`
        : "Corrigir em todas";

  return (
    <div
      className={"painel-correcao" + (embutido ? " painel-correcao--embutido" : "")}
      style={embutido ? undefined : { top: topo }}
      role="dialog"
      aria-labelledby={`${id}-titulo`}
      onKeyDown={aoTeclar}
    >
      <p className="painel-correcao__titulo" id={`${id}-titulo`}>
        Corrigir “<span className="painel-correcao__trecho">{trecho}</span>”
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
              Fechar
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
            O certo é
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
            <legend className="painel-correcao__rotulo">Onde corrigir</legend>
            <label className="painel-correcao__opcao">
              <input
                type="radio"
                name={`${id}-alcance`}
                checked={alcance === "fala"}
                onChange={() => setAlcance("fala")}
              />
              Só nesta fala
            </label>
            <label className="painel-correcao__opcao">
              <input
                type="radio"
                name={`${id}-alcance`}
                checked={alcance === "todas"}
                onChange={() => setAlcance("todas")}
              />
              Em todas as reuniões e nas próximas
            </label>
          </fieldset>

          {alcance === "todas" && mudou && (
            <div className="painel-correcao__previa" aria-live="polite">
              {conferindo && <p className="painel-correcao__nota">Conferindo as reuniões…</p>}
              {previa && previa.total === 0 && (
                <p className="painel-correcao__nota">
                  Não aparece em nenhuma reunião processada. Vale para as próximas.
                </p>
              )}
              {previa && previa.total > 0 && (
                <details className="painel-correcao__onde">
                  <summary>
                    Aparece <span className="numeros">{previa.total}</span>{" "}
                    {previa.total === 1 ? "vez" : "vezes"} em{" "}
                    <span className="numeros">{previa.reunioes.length}</span>{" "}
                    {previa.reunioes.length === 1 ? "reunião" : "reuniões"}
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
            O que é isso? <span className="painel-correcao__opcional">opcional</span>
          </label>
          <input
            id={`${id}-descricao`}
            className="painel-correcao__campo"
            value={descricao}
            maxLength={DESCRICAO_MAX_LEN}
            placeholder="ex.: ferramenta de aprovação de projetos"
            onChange={(e) => setDescricao(e.target.value)}
          />

          {erro && (
            <p className="painel-correcao__erro" role="alert">
              {erro}
            </p>
          )}

          <div className="painel-correcao__acoes">
            <button type="submit" className="painel-correcao__primario" disabled={!podeConfirmar}>
              {salvando ? "Corrigindo…" : rotuloConfirmar}
            </button>
            <button type="button" className="painel-correcao__discreto" onClick={aoFechar}>
              Cancelar
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
