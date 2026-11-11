import { useMensagem, type Mensagem } from "../i18n/mensagem";
import { mensagemDe, textoDoAviso } from "../api/cliente";
import { useEffect, useMemo, useState } from "react";
import {
  carregarReuniao,
  enviarRevisao,
  previaRevisao,
  temResultadoProcessado,
  urlAudioTrecho,
  NOME_MAX_LEN,
  type Cluster,
  type EfeitoNoLedger,
  type DetalheReuniao,
  type Fala,
} from "../api/reunioes";
import { listarPessoas } from "../api/pessoas";
import { BotaoPlay } from "../componentes/BotaoPlay";
import { ConferirTermos } from "./ConferirTermos";
import { useReprodutor } from "../audio/useReprodutor";
import { useRecarregarGaleria } from "../vozes/useIndiceGaleria";
import { tituloDaReuniao } from "../util/formatarReuniao";
import { numero } from "../util/numeros";
import { useTextos, type Catalogo } from "../i18n/textos";
import "./Revisao.css";

const PREFIXO_DESCONHECIDO = "DESCONHECIDO";
const PREFIXO_IGNORADO = "IGNORADO";

function ehDesconhecido(nome: string): boolean {
  return nome.startsWith(PREFIXO_DESCONHECIDO);
}

function ehIgnorado(nome: string): boolean {
  return nome.startsWith(PREFIXO_IGNORADO);
}

/** Placeholder de maquina ("DESCONHECIDO_S0", "IGNORADO_SPEAKER_02") nunca
 * vira texto pre-preenchido no campo - quem revisa de novo um cluster
 * ignorado quer digitar o nome, nao apagar o rotulo antes. */
function sugestaoParaCluster(nome: string): string {
  return ehDesconhecido(nome) || ehIgnorado(nome) ? "" : nome;
}

/**
 * Tres decisoes por cluster:
 *   aprender   o nome vai para o transcript e a voz alimenta o perfil.
 *   so_nomear  o nome vai para o transcript; nenhum perfil muda (o
 *              --sem-aprender do revisao.py, por cluster). Para voz quase
 *              toda de uma pessoa, com trechos de outras.
 *   ignorar    sem nome e sem perfil - o "-" do revisao.py.
 */
type Modo = "aprender" | "so_nomear" | "ignorar";

/**
 * O modo em que um cluster reabre na revisao - a decisao ja tomada, nunca
 * "aprender" por padrao em cima dela: ignorado reabre ignorado; "so
 * nomear" reabre so nomeando, tanto com o campo sem_aprender quanto no
 * caso antigo (confirmado sem voz no ledger: reunioes revisadas com
 * --sem-aprender antes de o campo existir). Sem isso, "Editar revisão" e
 * salvar sem mexer aprenderia a voz de quem so tinha sido nomeado.
 */
function modoInicial(cluster: Cluster): Modo {
  if (ehIgnorado(cluster.nome)) return "ignorar";
  if (cluster.sem_aprender) return "so_nomear";
  if (cluster.confirmado && cluster.voz_aprendida === false && !ehDesconhecido(cluster.nome)) {
    return "so_nomear";
  }
  return "aprender";
}

/** Ordem das opcoes na tela; rotulo e explicacao de cada uma vem do
 * catalogo (useTextos().revisao.modos[valor]). */
const OPCOES_MODO: Modo[] = ["aprender", "so_nomear", "ignorar"];

type TextosRevisao = Catalogo["revisao"];

/**
 * Ate n trechos do cluster para ouvir na revisao. MESMO criterio de
 * revisao.py:selecionar_trechos - CLI e navegador tem que escolher os
 * mesmos trechos para a mesma reuniao:
 *
 *   1. Duracao entre DURACAO_MIN_TRECHO e DURACAO_MAX_TRECHO segundos -
 *      curto demais nao da pra ouvir a cadencia da voz; longo demais faz
 *      o cartao virar rolagem para uma decisao que deveria levar segundos.
 *   2. Espalhados no TEMPO (inicio, meio, fim), nunca so os mais longos -
 *      tres amostras de momentos diferentes dizem mais sobre a voz de
 *      alguem do que um trecho so, por mais longo que seja.
 *
 * Sem candidato na faixa ideal, cai para os mais proximos dela (ainda
 * em ordem cronologica) em vez de nao mostrar nada.
 */
const DURACAO_MIN_TRECHO = 4;
const DURACAO_MAX_TRECHO = 15;

function espalharNoTempo(candidatos: Fala[], todos: Fala[], n: number): Fala[] {
  const inicioMin = Math.min(...todos.map((f) => f.inicio));
  const inicioMax = Math.max(...todos.map((f) => f.inicio));
  const largura = (inicioMax - inicioMin) / n || 1;

  const escolhidos: Fala[] = [];
  const usados = new Set<Fala>();
  for (let i = 0; i < n; i++) {
    const limiteInf = inicioMin + i * largura;
    const limiteSup = inicioMin + (i + 1) * largura;
    const doBucket = candidatos.filter(
      (f) => f.inicio >= limiteInf && f.inicio <= limiteSup && !usados.has(f),
    );
    if (doBucket.length > 0) {
      const escolha = doBucket[Math.floor(doBucket.length / 2)];
      escolhidos.push(escolha);
      usados.add(escolha);
    }
  }

  if (escolhidos.length < n) {
    const restantes = candidatos
      .filter((f) => !usados.has(f))
      .sort((a, b) => a.inicio - b.inicio);
    for (const f of restantes) {
      if (escolhidos.length >= n) break;
      escolhidos.push(f);
      usados.add(f);
    }
  }

  return escolhidos.sort((a, b) => a.inicio - b.inicio);
}

function selecionarTrechos(falas: Fala[], label: string, n = 3): Fala[] {
  const trechos = falas.filter((f) => f.cluster === label);
  if (trechos.length === 0) return [];

  const candidatos = trechos.filter((f) => {
    const duracao = f.fim - f.inicio;
    return duracao >= DURACAO_MIN_TRECHO && duracao <= DURACAO_MAX_TRECHO;
  });

  if (candidatos.length === 0) {
    const distanciaDaFaixa = (f: Fala) => {
      const duracao = f.fim - f.inicio;
      return duracao < DURACAO_MIN_TRECHO
        ? DURACAO_MIN_TRECHO - duracao
        : duracao - DURACAO_MAX_TRECHO;
    };
    return [...trechos]
      .sort((a, b) => distanciaDaFaixa(a) - distanciaDaFaixa(b))
      .slice(0, n)
      .sort((a, b) => a.inicio - b.inicio);
  }

  return espalharNoTempo(candidatos, trechos, n);
}

function descricaoSimilaridade(sim: number, simMin: number, t: TextosRevisao): string {
  if (sim < simMin) return t.abaixoDoLimiar;
  return sim - simMin > 0.1 ? t.comFolga : t.raspandoNoLimiar;
}

function TrechoTocavel({
  id,
  fala,
  reprodutor,
}: {
  id: string;
  fala: Fala;
  reprodutor: ReturnType<typeof useReprodutor>;
}) {
  const t = useTextos().revisao;
  const url = urlAudioTrecho(id, fala.inicio, fala.fim);
  const tocando = reprodutor.urlTocando === url;
  return (
    <div className="trecho-tocavel">
      <BotaoPlay
        tocando={tocando}
        aoClicar={() => reprodutor.alternar(url)}
        rotulo={t.trechoEm(fala.inicio.toFixed(0))}
      />
      <p className={"trecho-tocavel__texto" + (tocando ? " trecho-tocando" : "")}>
        {fala.texto}
      </p>
    </div>
  );
}

function BarraSimilaridade({
  sim,
  simMin,
}: {
  sim: number;
  simMin: number;
}) {
  const t = useTextos().revisao;
  const passou = sim >= simMin;
  return (
    <div className="barra-similaridade">
      <div className="barra-similaridade__trilho">
        <div
          className="barra-similaridade__preenchido"
          style={{
            width: `${Math.min(sim, 1) * 100}%`,
            background: passou ? "var(--tinta)" : "var(--alerta)",
          }}
        />
        <span
          className="barra-similaridade__limiar"
          style={{ left: `${Math.min(simMin, 1) * 100}%` }}
          title={t.limiarSimMin(numero(simMin, 2))}
        />
      </div>
      <span className="barra-similaridade__valor numeros">
        {numero(sim, 3)}
      </span>
      <span
        className={
          "barra-similaridade__descricao" +
          (passou ? "" : " barra-similaridade__descricao--falhou")
        }
      >
        {descricaoSimilaridade(sim, simMin, t)}
      </span>
    </div>
  );
}

/** Sentinela que servidor/revisao.py e revisao.py (CLI) ja tratam do mesmo
 * jeito: renomeia o cluster para IGNORADO_{label} e pula a etapa de
 * aprendizado. So existe na hora de montar o corpo da requisicao - na
 * tela, "ignorar" e um modo, e o nome digitado fica guardado. */
const MARCADOR_IGNORAR = "-";

function CartaoCluster({
  id,
  label,
  cluster,
  falas,
  simMin,
  nomeEscolhido,
  modo,
  aoMudarNome,
  aoMudarModo,
  reprodutor,
}: {
  id: string;
  label: string;
  cluster: Cluster;
  falas: Fala[];
  simMin: number;
  nomeEscolhido: string;
  modo: Modo;
  aoMudarNome: (nome: string) => void;
  aoMudarModo: (modo: Modo) => void;
  reprodutor: ReturnType<typeof useReprodutor>;
}) {
  const t = useTextos().revisao;
  const ignorado = modo === "ignorar";
  const candidatos = Object.entries(cluster.scores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);
  const explicacao = t.modos[modo].explicacao;

  return (
    <div className="cartao-cluster">
      <div className="cartao-cluster__cabecalho">
        <span className="cartao-cluster__rotulo">{label}</span>
        <span className="cartao-cluster__fala-s numeros">
          {t.segundosDeFala(cluster.fala_s.toFixed(0))}
        </span>
      </div>

      <BarraSimilaridade sim={cluster.sim} simMin={simMin} />

      {candidatos.length > 0 && (
        <p className="cartao-cluster__candidatos">
          {candidatos
            .map(([nome, score]) => `${nome} ${numero(score, 3)}`)
            .join(" · ")}
        </p>
      )}

      <div className="cartao-cluster__trechos">
        {selecionarTrechos(falas, label).map((f, i) => (
          <TrechoTocavel key={i} id={id} fala={f} reprodutor={reprodutor} />
        ))}
      </div>

      <label className="cartao-cluster__campo">
        <span className="cartao-cluster__campo-rotulo">{t.quemE}</span>
        <input
          type="text"
          className="cartao-cluster__input"
          list="galeria-pessoas"
          value={ignorado ? "" : nomeEscolhido}
          onChange={(e) => aoMudarNome(e.target.value)}
          placeholder={
            ignorado
              ? t.ignorado
              : ehDesconhecido(cluster.nome) || ehIgnorado(cluster.nome)
                ? t.nomeDaPessoa
                : cluster.nome
          }
          maxLength={NOME_MAX_LEN}
          disabled={ignorado}
        />
      </label>

      {/* Radio nativo: "um de tres" com semantica e teclado (setas) do
          navegador (mesmo name = grupo de radio de verdade). O nome digitado nao e apagado ao escolher "ignorar" -
          voltar para outra opcao devolve o que estava la. */}
      {/* Sem <legend> visualmente oculto (ver Perfil.tsx:Aparencia - apareceu
          na tela): o nome do grupo para leitor de tela vai em aria-label. */}
      <div
        className="cartao-cluster__modos"
        role="radiogroup"
        aria-label={t.oQueFazerCom(label)}
      >
        {OPCOES_MODO.map((valor) => (
          <label key={valor} className="cartao-cluster__modo">
            <input
              type="radio"
              name={`modo-${label}`}
              value={valor}
              checked={modo === valor}
              onChange={() => aoMudarModo(valor)}
            />
            {t.modos[valor].rotulo}
          </label>
        ))}
      </div>
      <p className="cartao-cluster__modo-explicacao">{explicacao}</p>
    </div>
  );
}

function segundos(s: number): string {
  return `${Math.round(s)} s`;
}

/** Uma frase por efeito, com o numero - "Isso vai ensinar 110 s da voz de
 * Celso.", "Isso vai remover 64 s da voz de Luciano." Nenhuma voz entra
 * nem sai do banco sem a pessoa ver e confirmar. */
function fraseDoEfeito(e: EfeitoNoLedger, t: TextosRevisao): string {
  if (e.tipo === "ensinar") {
    return t.ensinar(segundos(e.peso_s), e.pessoa);
  }
  const base =
    e.tipo === "mover"
      ? t.mover(segundos(e.peso_s), e.pessoa, e.para ?? "")
      : t.remover(segundos(e.peso_s), e.pessoa);
  // Duas frases inteiras, cada uma traduzida por si - so o espaco entre elas.
  return e.perfil_some ? `${base} ${t.perfilSome(e.pessoa)}` : base;
}

function AvisoLedger({
  efeitos,
  salvando,
  aoConfirmar,
  aoVoltar,
}: {
  efeitos: EfeitoNoLedger[];
  salvando: boolean;
  aoConfirmar: () => void;
  aoVoltar: () => void;
}) {
  const t = useTextos().revisao;
  return (
    <div className="aviso-ledger" role="alertdialog" aria-labelledby="aviso-ledger-titulo">
      <p className="aviso-ledger__titulo" id="aviso-ledger-titulo">
        {t.avisoLedgerTitulo}
      </p>
      <ul className="aviso-ledger__lista">
        {efeitos.map((e) => (
          <li key={e.cluster}>
            <span className="aviso-ledger__cluster">{e.cluster}</span>{" "}
            {fraseDoEfeito(e, t)}
          </li>
        ))}
      </ul>
      <div className="aviso-ledger__acoes">
        <button
          type="button"
          className="botao-salvar-revisao"
          onClick={aoConfirmar}
          disabled={salvando}
        >
          {salvando ? t.salvando : t.confirmarESalvar}
        </button>
        <button
          type="button"
          className="aviso-ledger__voltar"
          onClick={aoVoltar}
          disabled={salvando}
          autoFocus
        >
          {t.voltarERever}
        </button>
      </div>
    </div>
  );
}

export function Revisao({ id }: { id: string }) {
  const t = useTextos().revisao;
  const [dados, setDados] = useState<DetalheReuniao | null>(null);
  const [erro, setErro] = useState<Mensagem | null>(null);
  const textoDe = useMensagem();
  const [nomesGaleria, setNomesGaleria] = useState<string[]>([]);
  const [nomes, setNomes] = useState<Record<string, string>>({});
  const [modos, setModos] = useState<Record<string, Modo>>({});
  const [salvando, setSalvando] = useState(false);
  const [erroSalvar, setErroSalvar] = useState<Mensagem | null>(null);
  const [avisoLedger, setAvisoLedger] = useState<EfeitoNoLedger[] | null>(null);
  // Depois de gravar as vozes, a segunda etapa: termos para conferir (ADR
  // 0022). Sem nada a conferir, ConferirTermos volta direto ao Detalhe.
  const [etapa, setEtapa] = useState<"vozes" | "termos">("vozes");
  // O aviso descreve UMA decisao - mexer em qualquer nome ou modo depois
  // de ve-lo invalida o numero mostrado. Fecha, e o proximo "Salvar" pede
  // a previa de novo.
  useEffect(() => {
    setAvisoLedger(null);
  }, [nomes, modos]);
  const reprodutor = useReprodutor();
  const recarregarGaleria = useRecarregarGaleria();

  useEffect(() => {
    let cancelado = false;
    carregarReuniao(id)
      .then((d) => {
        if (cancelado) return;
        setDados(d);
        if (temResultadoProcessado(d)) {
          const iniciais: Record<string, string> = {};
          const modosIniciais: Record<string, Modo> = {};
          for (const [label, cluster] of Object.entries(d.clusters)) {
            iniciais[label] = sugestaoParaCluster(cluster.nome);
            // Revisar de novo nao desfaz um "ignorar" anterior sem a
            // pessoa escolher - salvar sem mexer mantem como estava.
            modosIniciais[label] = modoInicial(cluster);
          }
          setNomes(iniciais);
          setModos(modosIniciais);
        }
      })
      .catch((e: unknown) => {
        if (!cancelado) setErro(mensagemDe(e));
      });
    listarPessoas()
      .then((pessoas) => {
        if (!cancelado) setNomesGaleria(pessoas.map((p) => p.nome).sort());
      })
      .catch(() => {
        /* datalist so perde a lista de sugestoes - digitar continua livre */
      });
    return () => {
      cancelado = true;
    };
  }, [id]);

  const clustersOrdenados = useMemo(() => {
    if (!dados || !temResultadoProcessado(dados)) return [];
    return Object.entries(dados.clusters).sort(([a], [b]) =>
      a.localeCompare(b),
    );
  }, [dados]);

  function corpoDaRevisao() {
    const corpoNomes: Record<string, string> = {};
    const semAprender: string[] = [];
    for (const [label, nome] of Object.entries(nomes)) {
      const modo = modos[label] ?? "aprender";
      corpoNomes[label] = modo === "ignorar" ? MARCADOR_IGNORAR : nome;
      if (modo === "so_nomear") semAprender.push(label);
    }
    return { corpoNomes, semAprender };
  }

  /**
   * Dois passos sempre que a revisao muda a voz aprendida - ensinando voz
   * nova, tirando ou movendo: primeiro a previa (POST .../revisao/previa,
   * a MESMA decisao da gravacao, sem gravar), e so grava depois de a
   * pessoa ver o numero e confirmar. Sem efeito nenhum no ledger (so
   * nomes, ou reconfirmar o que ja estava), grava direto.
   */
  async function salvar() {
    setSalvando(true);
    setErroSalvar(null);
    const { corpoNomes, semAprender } = corpoDaRevisao();
    try {
      const efeitos = await previaRevisao(id, corpoNomes, semAprender);
      if (efeitos.length > 0) {
        setAvisoLedger(efeitos);
        setSalvando(false);
        return;
      }
    } catch (e) {
      setSalvando(false);
      setErroSalvar(mensagemDe(e));
      return;
    }
    gravar();
  }

  function gravar() {
    setSalvando(true);
    setErroSalvar(null);
    const { corpoNomes, semAprender } = corpoDaRevisao();
    enviarRevisao(id, corpoNomes, semAprender)
      .then(() => {
        // A revisao pode ter posto gente nova na galeria - ou tirado
        // alguem dela - e o indice de cor precisa saber.
        recarregarGaleria();
        // Vozes gravadas: segunda etapa, termos para conferir. Ela volta
        // para o Detalhe, que busca o .json de novo e mostra os nomes
        // corrigidos.
        setSalvando(false);
        setEtapa("termos");
        window.scrollTo(0, 0);
      })
      .catch((e: unknown) => {
        setSalvando(false);
        setErroSalvar(mensagemDe(e));
      });
  }

  return (
    <main className="tela-revisao">
      <a className="tela-revisao__voltar" href={`#/reuniao/${id}`}>
        ← {tituloDaReuniao(id, dados?.titulo)}
      </a>

      {erro && <p className="tela-revisao__erro">{textoDe(erro)}</p>}
      {!erro && dados === null && (
        <p className="tela-revisao__estado">{t.carregandoReuniao}</p>
      )}

      {!erro && dados !== null && !temResultadoProcessado(dados) && (
        <p className="tela-revisao__estado">
          {dados.estado === "nao_processada"
            ? t.naoProcessada
            : textoDoAviso(dados.acao_processar.motivo)}
        </p>
      )}

      {!erro && dados !== null && temResultadoProcessado(dados) && etapa === "termos" && (
        <>
          <h1 className="tela-revisao__titulo">
            {t.titulo(tituloDaReuniao(id, dados.titulo))}
          </h1>
          <ConferirTermos
            id={id}
            reprodutor={reprodutor}
            aoConcluir={() => {
              window.location.hash = `#/reuniao/${id}`;
            }}
          />
        </>
      )}

      {!erro && dados !== null && temResultadoProcessado(dados) && etapa === "vozes" && (
        <>
          <h1 className="tela-revisao__titulo">
            {t.titulo(tituloDaReuniao(id, dados.titulo))}
          </h1>

          {dados.limiares_origem === "atual" && (
            <p className="tela-revisao__aviso-limiar">
              {t.avisoLimiarAntigo(numero(dados.sim_min, 2))}
            </p>
          )}

          <datalist id="galeria-pessoas">
            {nomesGaleria.map((nome) => (
              <option key={nome} value={nome} />
            ))}
          </datalist>

          <div className="tela-revisao__cartoes">
            {clustersOrdenados.map(([label, cluster]) => (
              <CartaoCluster
                key={label}
                id={id}
                label={label}
                cluster={cluster}
                falas={dados.falas}
                simMin={dados.sim_min}
                nomeEscolhido={nomes[label] ?? ""}
                modo={modos[label] ?? "aprender"}
                aoMudarNome={(nome) =>
                  setNomes((atual) => ({ ...atual, [label]: nome }))
                }
                aoMudarModo={(modo) =>
                  setModos((atual) => ({ ...atual, [label]: modo }))
                }
                reprodutor={reprodutor}
              />
            ))}
          </div>

          {avisoLedger && (
            <AvisoLedger
              efeitos={avisoLedger}
              salvando={salvando}
              aoConfirmar={gravar}
              aoVoltar={() => setAvisoLedger(null)}
            />
          )}

          <div className="tela-revisao__rodape">
            <button
              type="button"
              className="botao-salvar-revisao"
              onClick={salvar}
              disabled={salvando || avisoLedger !== null}
            >
              {salvando ? t.salvando : t.salvarRevisao}
            </button>
            <span className="tela-revisao__rodape-legenda">
              {t.nadaGravadoAteConfirmar}
            </span>
            {erroSalvar && (
              <span className="tela-revisao__rodape-erro">{textoDe(erroSalvar)}</span>
            )}
          </div>
        </>
      )}
    </main>
  );
}
