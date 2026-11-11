import { useEffect, useRef, useState, type ReactNode } from "react";
import { buscarNasFalas, BUSCA_MAX_LEN, type ReuniaoEncontrada } from "../api/busca";
import { corDoTextoDaVoz } from "../vozes/corDaVoz";
import {
  listarReunioes,
  iniciarProcessamento,
  type ResumoReuniao,
} from "../api/reunioes";
import { useIndiceGaleria } from "../vozes/useIndiceGaleria";
import { BarraFala } from "../componentes/BarraFala";
import { ehVozSemPessoa } from "../util/falante";
import { ehPendente, grupos, casaBusca, textoPessoas } from "../util/lista";
import {
  numeroDaReuniao,
  tituloDaReuniao,
  formatarDataReuniao,
  formatarDuracao,
  rotuloBotaoProcessar,
} from "../util/formatarReuniao";
import "./Lista.css";

/**
 * Acao de processar da linha (marco 2, etapa 5). "processando" e link, nao
 * botao: outra reuniao ja esta rodando (so uma por vez, ver
 * servidor/processamento.py), entao clicar aqui e so ir acompanhar o
 * progresso - nunca chamar a rota de novo. "nao_processada"/"interrompido"
 * chamam POST /processar sem pessoas (a Lista nao tem campo pra isso,
 * mesma regra do formulario de Nova reuniao: vazio e valido, so funciona
 * pior).
 */
function AcaoProcessar({
  reuniao,
  acionando,
  erro,
  aoProcessar,
}: {
  reuniao: ResumoReuniao;
  acionando: boolean;
  erro: string | null;
  aoProcessar: (id: string) => void;
}) {
  if (
    reuniao.estado !== "nao_processada" &&
    reuniao.estado !== "processando" &&
    reuniao.estado !== "interrompido"
  ) {
    return null;
  }
  if (!reuniao.acao_processar) return null;

  return (
    <div className="linha-reuniao__acao">
      {reuniao.estado === "processando" ? (
        <a
          className="botao-processar"
          href={`#/reuniao/${reuniao.id}/processando`}
        >
          {rotuloBotaoProcessar(reuniao.estado)}
        </a>
      ) : (
        <button
          type="button"
          className="botao-processar"
          disabled={acionando}
          onClick={() => aoProcessar(reuniao.id)}
        >
          {acionando ? "Iniciando…" : rotuloBotaoProcessar(reuniao.estado)}
        </button>
      )}
      {erro && <span className="linha-reuniao__erro-acao">{erro}</span>}
    </div>
  );
}

/**
 * Coluna de dinamica resumida - so aparece em tela larga (Lista.css,
 * acima de 1440px; ADR 0015): quem mais interrompeu e quantas disputas.
 * Dado que existe, nunca inventado: reuniao sem dinamica nao ganha
 * coluna com zero (mesma regra da barra de fala - ausente e ausente).
 */
function ColunaDinamica({ reuniao }: { reuniao: ResumoReuniao }) {
  const i = reuniao.interacao;
  return (
    <div className="linha-reuniao__dinamica">
      {i && (
        <>
          <span>
            {i.mais_interrompeu ? (
              <>
                {i.mais_interrompeu.pessoa} interrompeu mais{" "}
                <span className="numeros">({i.mais_interrompeu.vezes}×)</span>
              </>
            ) : (
              "ninguém interrompeu"
            )}
          </span>
          <span>
            <span className="numeros">{i.disputas}</span>{" "}
            {i.disputas === 1 ? "disputa" : "disputas"}
          </span>
        </>
      )}
    </div>
  );
}

function LinhaReuniao({
  reuniao,
  indiceGaleria,
  acionando,
  erroAcao,
  aoProcessar,
}: {
  reuniao: ResumoReuniao;
  indiceGaleria: Map<string, number>;
  acionando: boolean;
  erroAcao: string | null;
  aoProcessar: (id: string) => void;
}) {
  const apagado = reuniao.estado !== "completa";

  return (
    <li className="linha-reuniao">
      <span
        className={
          "linha-reuniao__numero numeros" +
          (apagado ? " linha-reuniao__numero--apagado" : "")
        }
      >
        {numeroDaReuniao(reuniao.id)}
      </span>

      <div className="linha-reuniao__corpo">
        <a className="linha-reuniao__link" href={`#/reuniao/${reuniao.id}`}>
          <div className="linha-reuniao__topo">
            <span className="linha-reuniao__titulo">
              {tituloDaReuniao(reuniao.id, reuniao.titulo)}
            </span>
            {reuniao.duracao_s !== null && (
              <span className="linha-reuniao__duracao numeros">
                {formatarDuracao(reuniao.duracao_s)}
              </span>
            )}
          </div>
          {formatarDataReuniao(reuniao.data, reuniao.data_origem) && (
            <div className="linha-reuniao__data numeros">
              {formatarDataReuniao(reuniao.data, reuniao.data_origem)}
            </div>
          )}

          {reuniao.estado === "completa" && (
            <BarraFala
              dinamica={reuniao.dinamica}
              indiceGaleria={indiceGaleria}
            />
          )}

          {reuniao.estado === "incompleta" && (
            <div className="linha-reuniao__sem-dinamica">
              <span className="linha-reuniao__sem-dinamica-traco" />
              <span className="linha-reuniao__sem-dinamica-legenda">
                sem dinâmica
              </span>
            </div>
          )}

          {textoPessoas(reuniao) && (
            <div className="linha-reuniao__pessoas">{textoPessoas(reuniao)}</div>
          )}
        </a>

        <AcaoProcessar
          reuniao={reuniao}
          acionando={acionando}
          erro={erroAcao}
          aoProcessar={aoProcessar}
        />
        {!ehPendente(reuniao) && !reuniao.revisada && (
          <div className="linha-reuniao__acao">
            <a className="botao-processar" href={`#/reuniao/${reuniao.id}/revisar`}>
              Revisar
            </a>
          </div>
        )}
      </div>

      <ColunaDinamica reuniao={reuniao} />
    </li>
  );
}

/** Ponto entre o rotulo do grupo e a contagem ("Setembro de 2026 · 3") -
 * sem ele o numero colava no ano. Fora do nome acessivel: o leitor de
 * tela diria "ponto" no meio do rotulo. */
function SeparadorContagem() {
  return <span aria-hidden="true">·</span>;
}

/** Trecho com as palavras buscadas em <mark> - por posicao (servidor/
 * busca.py), como texto: nunca HTML (CLAUDE.md, regra 9). */
function TrechoComDestaque({ texto, destaques }: { texto: string; destaques: [number, number][] }) {
  const partes: ReactNode[] = [];
  let cursor = 0;
  destaques.forEach(([ini, fim], i) => {
    if (ini > cursor) partes.push(texto.slice(cursor, ini));
    partes.push(
      <mark key={i} className="trecho-busca__marca">
        {texto.slice(ini, fim)}
      </mark>,
    );
    cursor = fim;
  });
  if (cursor < texto.length) partes.push(texto.slice(cursor));
  return <>{partes}</>;
}

/**
 * Resultado da busca DENTRO das falas (GET /api/busca): por reuniao, o
 * trecho com a palavra em destaque, quem falou e o horario. Clicar abre o
 * Detalhe ja rolado naquela fala (#/reuniao/<id>/em/<segundos>).
 */
function ResultadosNaFala({
  resultados,
  reunioes,
  indiceGaleria,
}: {
  resultados: ReuniaoEncontrada[];
  reunioes: ResumoReuniao[];
  indiceGaleria: Map<string, number>;
}) {
  const total = resultados.reduce((n, r) => n + r.total, 0);
  return (
    <section className="grupo-reunioes" aria-labelledby="grupo-na-fala">
      <h2 className="grupo-reunioes__rotulo" id="grupo-na-fala">
        Na fala <SeparadorContagem /> <span className="numeros">{total}</span>
      </h2>
      {resultados.map((r) => {
        const reuniao = reunioes.find((x) => x.id === r.id);
        return (
          <div key={r.id} className="trechos-reuniao">
            <p className="trechos-reuniao__titulo">
              {tituloDaReuniao(r.id, reuniao?.titulo)}
            </p>
            <ul className="trechos-reuniao__lista">
              {r.trechos.map((t, i) => (
                <li key={i}>
                  <a className="trecho-busca" href={`#/reuniao/${r.id}/em/${t.inicio}`}>
                    <span className="trecho-busca__quem">
                      <span style={{ color: corDoTextoDaVoz(t.falante, indiceGaleria) }}>
                        {ehVozSemPessoa(t.falante) ? "voz não atribuída" : t.falante}
                      </span>{" "}
                      <span className="numeros">{formatarDuracao(t.inicio)}</span>
                    </span>
                    <span className="trecho-busca__texto">
                      <TrechoComDestaque texto={t.texto} destaques={t.destaques} />
                    </span>
                  </a>
                </li>
              ))}
            </ul>
            {r.total > r.trechos.length && (
              <p className="trechos-reuniao__mais">
                e mais {r.total - r.trechos.length}{" "}
                {r.total - r.trechos.length === 1 ? "fala" : "falas"} nesta reunião
              </p>
            )}
          </div>
        );
      })}
    </section>
  );
}

export function Lista() {
  const [reunioes, setReunioes] = useState<ResumoReuniao[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [acionando, setAcionando] = useState<string | null>(null);
  const [erroAcao, setErroAcao] = useState<{ id: string; mensagem: string } | null>(
    null,
  );
  const indiceGaleria = useIndiceGaleria();
  const [busca, setBusca] = useState("");
  const [naFala, setNaFala] = useState<ReuniaoEncontrada[] | null>(null);
  const [erroNaFala, setErroNaFala] = useState<string | null>(null);
  const consultaAtual = useRef(0);

  // Busca nas falas (servidor): a partir de 2 caracteres, 250ms depois da
  // ultima tecla - nunca uma requisicao por letra. So vale a resposta da
  // ULTIMA consulta: uma resposta atrasada de "ma" nunca sobrescreve a
  // de "matriz".
  useEffect(() => {
    const q = busca.trim();
    const minha = ++consultaAtual.current;
    if (q.length < 2) {
      setNaFala(null);
      setErroNaFala(null);
      return;
    }
    const espera = window.setTimeout(() => {
      buscarNasFalas(q)
        .then((r) => {
          if (minha === consultaAtual.current) {
            setNaFala(r);
            setErroNaFala(null);
          }
        })
        .catch((e: Error) => {
          if (minha === consultaAtual.current) setErroNaFala(e.message);
        });
    }, 250);
    return () => window.clearTimeout(espera);
  }, [busca]);

  useEffect(() => {
    let cancelado = false;
    listarReunioes()
      .then((dados) => {
        if (!cancelado) setReunioes(dados);
      })
      .catch((e: Error) => {
        if (!cancelado) setErro(e.message);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  async function processar(id: string) {
    setAcionando(id);
    setErroAcao(null);
    try {
      await iniciarProcessamento(id, []);
      window.location.hash = `#/reuniao/${id}/processando`;
    } catch (e) {
      setErroAcao({ id, mensagem: (e as Error).message });
      setAcionando(null);
    }
  }

  const encontradas = (reunioes ?? []).filter((r) => casaBusca(r, busca));

  return (
    <main className="tela-lista">
      {erro && <p className="tela-lista__erro">{erro}</p>}
      {!erro && reunioes === null && (
        <p className="tela-lista__estado">Carregando reuniões…</p>
      )}
      {!erro && reunioes !== null && reunioes.length === 0 && (
        <p className="tela-lista__estado">
          Nenhuma reunião encontrada em audios/.
        </p>
      )}
      {!erro && reunioes !== null && reunioes.length > 0 && (
        <>
          <div className="tela-lista__topo">
            <label className="so-leitor-de-tela" htmlFor="busca-reunioes">
              Buscar
            </label>
            <input
              id="busca-reunioes"
              type="search"
              className="tela-lista__busca"
              placeholder="Título, pessoa ou trecho da fala"
              maxLength={BUSCA_MAX_LEN}
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
            <p className="tela-lista__contagem numeros" aria-live="polite">
              {busca.trim()
                ? `${encontradas.length} de ${reunioes.length}`
                : `${reunioes.length} ${reunioes.length === 1 ? "reunião" : "reuniões"}`}
            </p>
          </div>
          {encontradas.length === 0 && naFala !== null && naFala.length === 0 && (
            <p className="tela-lista__estado">Nenhuma reunião com “{busca.trim()}”.</p>
          )}
          {erroNaFala && <p className="tela-lista__erro">{erroNaFala}</p>}
          {grupos(encontradas).map((g) => (
            <section
              key={g.chave}
              className="grupo-reunioes"
              aria-labelledby={g.rotulo ? `grupo-${g.chave}` : undefined}
            >
              {g.rotulo && (
                <h2 className="grupo-reunioes__rotulo" id={`grupo-${g.chave}`}>
                  {g.rotulo} <SeparadorContagem />{" "}
                  <span className="numeros">{g.itens.length}</span>
                </h2>
              )}
              <ul className="lista-reunioes">
                {g.itens.map((r) => (
                  <LinhaReuniao
                    key={r.id}
                    reuniao={r}
                    indiceGaleria={indiceGaleria}
                    acionando={acionando === r.id}
                    erroAcao={erroAcao?.id === r.id ? erroAcao.mensagem : null}
                    aoProcessar={processar}
                  />
                ))}
              </ul>
            </section>
          ))}
          {naFala !== null && naFala.length > 0 && (
            <ResultadosNaFala
              resultados={naFala}
              reunioes={reunioes}
              indiceGaleria={indiceGaleria}
            />
          )}
        </>
      )}
    </main>
  );
}
