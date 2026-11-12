import { mensagemDe, textoDoAviso } from "../api/cliente";
import { useMensagem, type Mensagem } from "../i18n/mensagem";
import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  carregarReuniao,
  iniciarProcessamento,
  temResultadoProcessado,
  urlAudioTrecho,
  type DetalheReuniao,
  type DinamicaPessoa,
  type Evento,
  type Fala,
  type FalaAlterada,
  type LacunaSemTexto,
} from "../api/reunioes";
import { FalaEditavel } from "../componentes/FalaEditavel";
import { PainelCorrecao } from "../componentes/PainelCorrecao";
import { selecaoNaFala } from "../util/selecaoNaFala";
import { FitaDeTempo } from "../componentes/FitaDeTempo";
import { TituloEditavel } from "../componentes/TituloEditavel";
import { useReprodutor } from "../audio/useReprodutor";
import { useIndiceGaleria } from "../vozes/useIndiceGaleria";
import { corDaVoz, corDoTextoDaVoz } from "../vozes/corDaVoz";
import { ehVozSemPessoa, rotulosDaReuniao } from "../util/falante";
import { faixasDaFala, type FaixaSobreposicao } from "../util/sobreposicao";
import {
  formatarDataReuniao,
  formatarDuracao,
  formatarTamanhoArquivo,
  formatarTimestamp,
  rotuloBotaoProcessar,
  tituloDaReuniao,
} from "../util/formatarReuniao";
import { ConfirmarApagarReuniao } from "../componentes/ConfirmarApagarReuniao";
import { numero } from "../util/numeros";
import { useIdioma } from "../i18n/idioma";
import { useTextos } from "../i18n/textos";
import "./Detalhe.css";
import { Seta } from "../componentes/Seta";

/** Mesmo criterio de contagem usado em pipeline.py para medir a distribuicao
 * (split por espaco em branco) - so precisa bater no MESMO limiar
 * (min_palavras_confianca_fala), nao numa tokenizacao linguistica. */
function contarPalavras(texto: string): number {
  return texto.trim().split(/\s+/).filter(Boolean).length;
}

// ---- preferencia de mostrar interacoes (localStorage, junto do tema) -----

const CHAVE_MOSTRAR_EVENTOS = "trama:mostrar-eventos";

function lerPreferenciaMostrarEventos(): boolean {
  try {
    return localStorage.getItem(CHAVE_MOSTRAR_EVENTOS) === "true";
  } catch {
    return false; // desligado por padrao - ler limpo e o estado normal
  }
}

function salvarPreferenciaMostrarEventos(valor: boolean) {
  try {
    localStorage.setItem(CHAVE_MOSTRAR_EVENTOS, String(valor));
  } catch {
    // preferencia e conveniencia - falha ao salvar nao pode quebrar o toggle
  }
}

// ---- agrupar falas em blocos por falante consecutivo --------------------

interface GrupoFala {
  falante: string;
  inicio: number;
  falas: Fala[];
}

function agruparPorTurno(falas: Fala[]): GrupoFala[] {
  const grupos: GrupoFala[] = [];
  for (const fala of falas) {
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.falante === fala.falante) {
      ultimo.falas.push(fala);
    } else {
      grupos.push({ falante: fala.falante, inicio: fala.inicio, falas: [fala] });
    }
  }
  return grupos;
}

// ---- anexar eventos (apoio/interrupcao/disputa) a fala especifica --------

interface EventoAnexado extends Evento {
  /** O tempo do evento nao caiu dentro de NENHUMA fala de quem falava -
   * foi anexado a mais proxima. "Durante esta fala" vira "perto desta
   * fala", e isso precisa aparecer na tela (~ antes do nome). */
  aproximado: boolean;
}

function distanciaAoIntervalo(tempo: number, fala: Fala): number {
  if (tempo < fala.inicio) return fala.inicio - tempo;
  if (tempo > fala.fim) return tempo - fala.fim;
  return 0;
}

/**
 * Para cada evento, acha a fala de QUEM FALAVA cujo [inicio, fim] contem
 * o tempo do evento - a granularidade honesta que temos, ja que nao ha
 * alinhamento palavra a palavra dentro de uma fala (ADR pendente: ver
 * decisao no PR que introduziu isto). Sem candidato exato (o tempo caiu
 * numa lacuna entre falas), usa a fala mais proxima e marca aproximado.
 *
 * Busca entre TODAS as falas da pessoa na reuniao, nao so as do bloco
 * atual - a pessoa pode ter varios blocos ao longo da conversa.
 */
function anexarEventosAsFalas(
  falas: Fala[],
  eventos: Evento[],
): Map<Fala, EventoAnexado[]> {
  const porFalante = new Map<string, Fala[]>();
  for (const f of falas) {
    const lista = porFalante.get(f.falante) ?? [];
    lista.push(f);
    porFalante.set(f.falante, lista);
  }

  const mapa = new Map<Fala, EventoAnexado[]>();
  for (const evento of eventos) {
    const falasDaPessoa = porFalante.get(evento.falava);
    if (!falasDaPessoa || falasDaPessoa.length === 0) continue;

    let alvo = falasDaPessoa.find(
      (f) => evento.tempo >= f.inicio && evento.tempo <= f.fim,
    );
    let aproximado = false;
    if (!alvo) {
      aproximado = true;
      alvo = falasDaPessoa.reduce((melhor, f) =>
        distanciaAoIntervalo(evento.tempo, f) <
        distanciaAoIntervalo(evento.tempo, melhor)
          ? f
          : melhor,
      );
    }

    const lista = mapa.get(alvo) ?? [];
    lista.push({ ...evento, aproximado });
    mapa.set(alvo, lista);
  }
  return mapa;
}

// ---- agrupar lacunas de fala sem texto por fala que as contem ------------

/**
 * Diferente de anexarEventosAsFalas: uma lacuna e SEMPRE contida por
 * construcao no [inicio, fim] de exatamente uma fala (ela so existe DENTRO
 * de um turno ja ativo - ver pipeline.py:alinhar) - contencao exata, sem
 * fallback por proximidade.
 */
function agruparLacunasPorFala(
  falas: Fala[],
  lacunas: LacunaSemTexto[],
): Map<Fala, LacunaSemTexto[]> {
  const mapa = new Map<Fala, LacunaSemTexto[]>();
  for (const lacuna of lacunas) {
    const alvo = falas.find(
      (f) => lacuna.inicio >= f.inicio && lacuna.fim <= f.fim,
    );
    if (!alvo) continue;
    const lista = mapa.get(alvo) ?? [];
    lista.push(lacuna);
    mapa.set(alvo, lista);
  }
  return mapa;
}

const RANQUE_SEVERIDADE: Record<Evento["tipo"], number> = {
  apoio: 0,
  interrupcao: 1,
  disputa: 2,
};

/**
 * Agrupa os eventos de UMA fala por pessoa E tipo - nunca so por pessoa.
 * Agrupando so por pessoa, duas interrupcoes e um apoio da mesma pessoa
 * viravam um grupo de 3 rotulado pelo tipo mais severo ("interrupção
 * ·3"): o rotulo mentia. Agora cada grupo tem um tipo so, e a contagem e
 * de ocorrencias DAQUELE tipo.
 *
 * Ordem: pessoas na ordem em que entraram na fala; dentro da mesma
 * pessoa, do tipo mais severo pro menos, para as linhas dela ficarem
 * juntas e a mais importante primeiro.
 */
function agruparEventos(
  eventos: EventoAnexado[],
): { entrante: string; tipo: Evento["tipo"]; lista: EventoAnexado[] }[] {
  const porEntrante = new Map<string, Map<Evento["tipo"], EventoAnexado[]>>();
  for (const e of eventos) {
    const porTipo = porEntrante.get(e.entrante) ?? new Map();
    const lista = porTipo.get(e.tipo) ?? [];
    lista.push(e);
    porTipo.set(e.tipo, lista);
    porEntrante.set(e.entrante, porTipo);
  }
  return [...porEntrante.entries()].flatMap(([entrante, porTipo]) =>
    [...porTipo.entries()]
      .sort(([a], [b]) => RANQUE_SEVERIDADE[b] - RANQUE_SEVERIDADE[a])
      .map(([tipo, lista]) => ({ entrante, tipo, lista })),
  );
}

/**
 * Marginalia dos eventos de UMA fala: um item por pessoa e tipo
 * (agruparEventos), repeticoes numa contagem "·N" ao lado da palavra do
 * tipo - a palavra aparece sempre, a contagem nunca a substitui. Detalhe
 * de cada ocorrencia no title.
 *
 * Duas linhas, as duas alinhadas a direita dentro dos 92px da margem:
 * nome na primeira (na cor da voz), tipo e contagem na segunda. Numa
 * linha so, "BEATRIZ interrupção ·3" nao cabe em 92px, e escapar pela
 * esquerda passaria por baixo da fita de tempo, escondendo o nome. Nome
 * longo demais corta com reticencias (nome completo no title); o tipo
 * nunca corta.
 */
function MarcaEventos({
  eventos,
  indiceGaleria,
  rotulo,
}: {
  eventos: EventoAnexado[];
  indiceGaleria: Map<string, number>;
  rotulo: (nome: string) => string;
}) {
  const t = useTextos().detalhe;
  return (
    <div className="linha-fala__eventos">
      {agruparEventos(eventos).map(({ entrante, tipo, lista }) => {
        const aproximado = lista.some((e) => e.aproximado);
        const titulo = [
          rotulo(entrante),
          ...lista.map((e) =>
            t.ocorrenciaEvento(formatarTimestamp(e.tempo), t.tipoEvento[e.tipo], e.aproximado),
          ),
        ].join("\n");
        return (
          <span
            key={`${entrante}|${tipo}`}
            className="evento-marca"
            title={titulo}
          >
            <span className="evento-marca__linha-nome">
              {aproximado && (
                <span className="evento-marca__til" aria-hidden="true">
                  ~
                </span>
              )}
              <span
                className={
                  "evento-marca__nome" +
                  (ehVozSemPessoa(entrante) ? " evento-marca__nome--sem-pessoa" : "")
                }
                style={{ color: corDoTextoDaVoz(entrante, indiceGaleria) }}
              >
                {rotulo(entrante)}
              </span>
            </span>
            <span
              className={`evento-marca__tipo evento-marca__tipo--${tipo}`}
            >
              {t.tipoEvento[tipo]}
              {lista.length > 1 && ` ·${lista.length}`}
            </span>
          </span>
        );
      })}
    </div>
  );
}

/**
 * Marca a FALA inteira, nunca uma palavra isolada (ver
 * PalavraBaixaConfianca em api/reunioes.ts - uma palavra de baixa
 * confianca sozinha, como "tá", deu falso positivo na medição). So texto
 * discreto, sem cor de estado (SKILL.md: erro/estado nao usa
 * vermelho/amarelo saturado) - peso e posicao, igual ao resto da marginalia.
 */
function MarcaConfiancaBaixa({ confianca }: { confianca: number }) {
  const t = useTextos().detalhe;
  return (
    <span
      className="marca-confianca-baixa"
      title={t.tituloConfiancaBaixa(numero(Math.round(confianca * 100)))}
    >
      {t.confiancaBaixa}
    </span>
  );
}

/**
 * Fala corrigida a mao (FalaEditavel, ADR 0016): marca discreta na margem,
 * no mesmo tratamento das outras marcas da fala. O texto transcrito fica no
 * title - e "Voltar ao original" mora dentro da edicao.
 */
function MarcaEditada({ textoOriginal }: { textoOriginal: string }) {
  const t = useTextos().detalhe;
  return (
    <span
      className="marca-editada"
      title={t.tituloEditada(textoOriginal)}
    >
      {t.editadoAMao}
    </span>
  );
}

/**
 * Toca a fala usando a mesma rota de audio da Revisao (urlAudioTrecho) -
 * sem botao fixo por paragrafo (998 turnos), so aparece no hover/foco da
 * linha (ver .linha-fala:hover/:focus-within em Detalhe.css). Fica sempre
 * no DOM, so visualmente oculto, para o Tab alcancar.
 */
function BotaoTocarFala({
  tocando,
  aoClicar,
  rotulo,
}: {
  tocando: boolean;
  aoClicar: () => void;
  rotulo: string;
}) {
  const t = useTextos().comum;
  return (
    <button
      type="button"
      className="botao-tocar-fala"
      onClick={aoClicar}
      aria-label={tocando ? t.pausar(rotulo) : t.tocar(rotulo)}
      aria-pressed={tocando}
    >
      {tocando ? (
        <svg width="9" height="9" viewBox="0 0 14 14" aria-hidden="true">
          <rect x="2" y="1" width="4" height="12" fill="currentColor" />
          <rect x="8" y="1" width="4" height="12" fill="currentColor" />
        </svg>
      ) : (
        <svg width="9" height="9" viewBox="0 0 14 14" aria-hidden="true">
          <path d="M2 1 L13 7 L2 13 Z" fill="currentColor" />
        </svg>
      )}
    </button>
  );
}

/**
 * Corpo da fala com as marcas inline, todas ancoradas por posicao em
 * CARACTERES dentro de "texto" (pipeline.py:alinhar grava todas no mesmo
 * sistema de coordenadas):
 *
 *  - palavra divergente: sublinhado pontilhado na cor da voz de quem pode
 *    ter dito aquilo (e a letra na mesma cor, fora de faixa). O
 *    pontilhado diz "pista", nao "correcao": a cor sozinha dependeria de
 *    quem enxerga cor (SKILL.md), e a atribuicao por palavra e menos
 *    confiavel bem onde isto mais aparece (sobreposicao de fala).
 *  - faixa de sobreposicao (so com "Mostrar interacoes"): fundo na cor da
 *    OUTRA pessoa, em --opacidade-sobreposicao, nas palavras ditas
 *    enquanto ela tambem falava (util/sobreposicao.ts). Diz "aqui outra
 *    pessoa falava junto" - nunca de quem sao as palavras dentro dela.
 *  - lacuna sem texto: insercao (nao substitui nenhum caractere) marcando
 *    um trecho sem token do Whisper dentro do turno. Nunca afirma o que
 *    era (riso, gesto) - so a omissao. Sempre fora da faixa.
 *
 * Contraste sobre a faixa (calculado em tests/test_paleta.py): so texto
 * em --tinta-corpo fica em cima dela. A palavra de pista dentro de uma
 * faixa troca a letra para --tinta-corpo e mantem o pontilhado na cor da
 * voz - letra na cor da voz sobre a faixa nao passa 4,5:1 no modo claro.
 */
function TextoComMarcas({
  fala,
  lacunas,
  faixas,
  indiceGaleria,
  rotulo,
}: {
  fala: Fala;
  lacunas: LacunaSemTexto[];
  faixas: FaixaSobreposicao[];
  indiceGaleria: Map<string, number>;
  rotulo: (nome: string) => string;
}) {
  const t = useTextos().detalhe;
  const divergentes = fala.palavras_divergentes ?? [];
  if (divergentes.length === 0 && lacunas.length === 0 && faixas.length === 0) {
    return <>{fala.texto}</>;
  }

  // Fronteiras de todos os trechos; cada pedaco entre duas fronteiras tem
  // no maximo uma faixa e uma pista por cima.
  const n = fala.texto.length;
  const fronteiras = new Set<number>([0, n]);
  for (const f of faixas) fronteiras.add(f.inicio).add(Math.min(f.fim, n));
  for (const d of divergentes) fronteiras.add(d.posicao).add(Math.min(d.posicao + d.comprimento, n));
  for (const l of lacunas) fronteiras.add(Math.min(l.posicao, n));
  const pontos = [...fronteiras].filter((x) => x >= 0 && x <= n).sort((a, b) => a - b);

  const partes: ReactNode[] = [];
  const lacunasEm = (p: number) => lacunas.filter((l) => Math.min(l.posicao, n) === p);
  pontos.forEach((ini, k) => {
    for (const l of lacunasEm(ini)) {
      // Escrito por quem ouviu (trechos para conferir, ADR 0028): o texto
      // no ponto da lacuna, em itálico - é fala, mas não da máquina.
      partes.push(
        l.texto_manual !== undefined ? (
          <span
            key={`l${ini}-${partes.length}`}
            className="lacuna-escrita"
            title={t.tituloLacunaEscrita}
          >
            {" "}{l.texto_manual}{" "}
          </span>
        ) : (
          <span
            key={`l${ini}-${partes.length}`}
            className="marca-lacuna"
            title={t.tituloLacuna}
          >
            {" "}{t.lacuna}{" "}
          </span>
        ),
      );
    }
    const fim = pontos[k + 1];
    if (fim === undefined || fim <= ini) return;
    const pedaco = fala.texto.slice(ini, fim);
    const faixa = faixas.find((f) => ini >= f.inicio && fim <= f.fim);
    const div = divergentes.find(
      (d) => ini >= d.posicao && fim <= d.posicao + d.comprimento,
    );
    let conteudo: ReactNode = pedaco;
    if (div) {
      conteudo = (
        <span
          className="palavra-divergente"
          style={{ "--cor-pista": corDoTextoDaVoz(div.falante, indiceGaleria) } as CSSProperties}
          title={t.tituloPista(rotulo(div.falante))}
        >
          {pedaco}
        </span>
      );
    }
    if (faixa) {
      conteudo = (
        <span
          className="faixa-sobreposicao"
          style={{ "--cor-faixa": corDaVoz(faixa.outra, indiceGaleria) } as CSSProperties}
          title={t.tituloSobreposicao(rotulo(faixa.outra))}
        >
          {conteudo}
        </span>
      );
    }
    partes.push(<Fragment key={`t${ini}`}>{conteudo}</Fragment>);
  });
  return <>{partes}</>;
}

function ResumoDinamica({
  dinamica,
  indiceGaleria,
  rotulo,
}: {
  dinamica: Record<string, DinamicaPessoa>;
  indiceGaleria: Map<string, number>;
  rotulo: (nome: string) => string;
}) {
  const t = useTextos().detalhe;
  const pessoas = Object.entries(dinamica).sort(
    (a, b) => b[1].fala_pct - a[1].fala_pct,
  );
  return (
    <div className="resumo-dinamica">
      {pessoas.map(([nome, d]) => (
        <div className="resumo-dinamica__pessoa" key={nome}>
          <span
            className="resumo-dinamica__marca"
            style={{ background: corDaVoz(nome, indiceGaleria) }}
          />
          <span className="resumo-dinamica__nome">{rotulo(nome)}</span>
          <span className="resumo-dinamica__stat numeros">
            {t.pctDaFala(numero(Math.round(d.fala_pct)))}
          </span>
          {d.interrompeu > 0 && (
            <span className="resumo-dinamica__stat numeros">
              {t.interrompeu(d.interrompeu)}
            </span>
          )}
          {d.foi_interrompido > 0 && (
            <span className="resumo-dinamica__stat numeros">
              {t.foiInterrompido(d.foi_interrompido)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

/** Trecho selecionado numa fala, com onde desenhar o botao/painel. */
interface SelecaoTela {
  indice: number;
  inicio: number;
  fim: number;
  x: number;
  topo: number;
  base: number;
}

export function Detalhe({ id, em }: { id: string; em?: number }) {
  const t = useTextos().detalhe;
  // O .txt sai no idioma da interface (cabecalho e instrucoes; a fala nunca).
  const idioma = useIdioma();
  const tc = useTextos().comum;
  const textoDe = useMensagem();
  const [dados, setDados] = useState<DetalheReuniao | null>(null);
  const [erro, setErro] = useState<Mensagem | null>(null);
  const [mostrarEventos, setMostrarEventos] = useState(lerPreferenciaMostrarEventos);
  const [acionando, setAcionando] = useState(false);
  const [confirmandoApagar, setConfirmandoApagar] = useState(false);
  const [erroProcessar, setErroProcessar] = useState<Mensagem | null>(null);
  const indiceGaleria = useIndiceGaleria();
  const transcriptRef = useRef<HTMLDivElement>(null);
  const reprodutor = useReprodutor();
  // Trecho selecionado no transcript (uma fala so) e o painel "Corrigir"
  // aberto para ele (ADR 0019). Posicoes em px relativas ao transcript.
  const [selecao, setSelecao] = useState<SelecaoTela | null>(null);
  const [painel, setPainel] = useState<SelecaoTela | null>(null);

  useEffect(() => {
    let cancelado = false;
    carregarReuniao(id)
      .then((d) => {
        if (!cancelado) setDados(d);
      })
      .catch((e: unknown) => {
        if (!cancelado) setErro(mensagemDe(e));
      });
    return () => {
      cancelado = true;
    };
  }, [id]);

  const eventosPorFala = useMemo(() => {
    if (!dados || !temResultadoProcessado(dados) || !dados.eventos) {
      return new Map<Fala, EventoAnexado[]>();
    }
    return anexarEventosAsFalas(dados.falas, dados.eventos);
  }, [dados]);

  // Posicao de cada fala em dados.falas - a rota de correcao e por indice,
  // e o transcript percorre as falas agrupadas por turno.
  const indicePorFala = useMemo(() => {
    if (!dados || !temResultadoProcessado(dados)) return new Map<Fala, number>();
    return new Map(dados.falas.map((f, i) => [f, i] as [Fala, number]));
  }, [dados]);

  // A selecao muda por mouse, teclado ou toque - selectionchange cobre os
  // tres. Espera a selecao parar de mudar antes de mostrar o botao; com o
  // painel aberto, a selecao e o painel que mandam.
  useEffect(() => {
    let espera: ReturnType<typeof setTimeout> | undefined;
    function aoMudarSelecao() {
      clearTimeout(espera);
      espera = setTimeout(() => {
        if (painel) return;
        const container = transcriptRef.current;
        const textos = dados && temResultadoProcessado(dados) ? dados.falas : null;
        const s = textos ? selecaoNaFala((i) => textos[i]?.texto) : null;
        if (!s || !container || !container.contains(s.elemento)) {
          setSelecao(null);
          return;
        }
        const r = window.getSelection()!.getRangeAt(0).getBoundingClientRect();
        const c = container.getBoundingClientRect();
        const meio = (r.left + r.right) / 2 - c.left;
        setSelecao({
          indice: s.indice,
          inicio: s.inicio,
          fim: s.fim,
          // o botao nunca sai do transcript pelos lados
          x: Math.min(Math.max(meio, 60), Math.max(c.width - 60, 60)),
          topo: r.top - c.top,
          base: r.bottom - c.top,
        });
      }, 150);
    }
    document.addEventListener("selectionchange", aoMudarSelecao);
    return () => {
      clearTimeout(espera);
      document.removeEventListener("selectionchange", aoMudarSelecao);
    };
  }, [dados, painel]);

  function fecharPainel() {
    setPainel(null);
    setSelecao(null);
    window.getSelection()?.removeAllRanges();
  }

  function recarregar() {
    carregarReuniao(id)
      .then(setDados)
      .catch((e: unknown) => setErro(mensagemDe(e)));
  }

  function atualizarFala(indice: number, alterada: FalaAlterada) {
    setDados((d) =>
      d && temResultadoProcessado(d)
        ? {
            ...d,
            falas: d.falas.map((f, i) => (i === indice ? alterada.fala : f)),
            lacunas_sem_texto: alterada.lacunas_sem_texto ?? undefined,
          }
        : d,
    );
  }

  const lacunasPorFala = useMemo(() => {
    if (!dados || !temResultadoProcessado(dados) || !dados.lacunas_sem_texto) {
      return new Map<Fala, LacunaSemTexto[]>();
    }
    return agruparLacunasPorFala(dados.falas, dados.lacunas_sem_texto);
  }, [dados]);

  // Reuniao processada antes de palavras_tempo existir nao tem faixa de
  // sobreposicao - a legenda so aparece quando ha o que ela explica.
  const temTemposDePalavra =
    !!dados && temResultadoProcessado(dados) && dados.falas.some((f) => f.palavras_tempo?.length);

  // "IGNORADO_SPEAKER_02"/"DESCONHECIDO_S0" nunca aparecem crus: todo
  // nome exibido nesta tela passa por aqui (util/falante.ts).
  const rotulo = useMemo(() => {
    if (!dados || !temResultadoProcessado(dados)) return rotulosDaReuniao([]);
    return rotulosDaReuniao([
      ...Object.values(dados.clusters).map((c) => c.nome),
      ...dados.falas.map((f) => f.falante),
      ...Object.keys(dados.dinamica ?? {}),
      ...(dados.eventos ?? []).flatMap((e) => [e.entrante, e.falava]),
    ]);
  }, [dados]);

  async function processar() {
    setAcionando(true);
    setErroProcessar(null);
    try {
      await iniciarProcessamento(id, []);
      window.location.hash = `#/reuniao/${id}/processando`;
    } catch (e) {
      setErroProcessar(mensagemDe(e));
      setAcionando(false);
    }
  }

  function alternarMostrarEventos() {
    setMostrarEventos((atual) => {
      const novo = !atual;
      salvarPreferenciaMostrarEventos(novo);
      return novo;
    });
  }

  // Chegou pela busca (#/reuniao/<id>/em/<segundos>): assim que o
  // transcript esta na tela, rola ate a fala daquele instante - o mesmo
  // salto da fita de tempo. Uma vez por carga, nunca de novo a cada render.
  const saltouRef = useRef(false);
  useEffect(() => {
    if (em === undefined || saltouRef.current) return;
    if (!dados || !temResultadoProcessado(dados)) return;
    saltouRef.current = true;
    requestAnimationFrame(() => saltarPara(em));
    // saltarPara so le o DOM do transcript - nao entra nas dependencias.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dados, em]);

  function saltarPara(tempo: number) {
    const container = transcriptRef.current;
    if (!container) return;
    const alvos = container.querySelectorAll<HTMLElement>("[data-inicio]");
    let melhor: HTMLElement | undefined;
    let melhorDist = Infinity;
    for (const el of alvos) {
      const inicio = Number(el.dataset.inicio);
      const dist = Math.abs(inicio - tempo);
      if (dist < melhorDist) {
        melhorDist = dist;
        melhor = el;
      }
    }
    melhor?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const temEventos =
    dados !== null &&
    temResultadoProcessado(dados) &&
    !!dados.eventos &&
    dados.eventos.length > 0;

  return (
    <main className="tela-detalhe">
      <a className="tela-detalhe__voltar" href="#/reunioes">
        <Seta direcao="esquerda" />
        {tc.reunioes}
      </a>

      {erro && <p className="tela-detalhe__erro">{textoDe(erro)}</p>}
      {!erro && dados === null && (
        <p className="tela-detalhe__estado">{t.carregando}</p>
      )}

      {!erro && dados !== null && !temResultadoProcessado(dados) && (
        <div className="tela-detalhe__nao-processada">
          <TituloEditavel
            id={dados.id}
            titulo={dados.titulo}
            aoMudar={(titulo) => setDados({ ...dados, titulo })}
          />
          {dados.estado !== "nao_processada" && (
            <p className="tela-detalhe__estado-processamento">
              {textoDoAviso(dados.acao_processar.motivo)}
            </p>
          )}
          <dl className="tela-detalhe__ficha">
            <dt>{t.arquivo}</dt>
            <dd>{dados.audio_nome ?? "—"}</dd>
            <dt>{t.tamanho}</dt>
            <dd>
              {dados.audio_tamanho_bytes !== null
                ? formatarTamanhoArquivo(dados.audio_tamanho_bytes)
                : "—"}
            </dd>
            <dt>{t.duracao}</dt>
            <dd>
              {dados.duracao_s !== null
                ? formatarDuracao(dados.duracao_s)
                : "—"}
            </dd>
          </dl>
          {dados.estado === "processando" ? (
            <a
              className="botao-processar"
              href={`#/reuniao/${dados.id}/processando`}
            >
              {rotuloBotaoProcessar(dados.estado)}
            </a>
          ) : (
            <button
              type="button"
              className="botao-processar"
              disabled={acionando}
              onClick={processar}
            >
              {acionando ? t.iniciando : rotuloBotaoProcessar(dados.estado)}
            </button>
          )}
          {erroProcessar && (
            <p className="tela-detalhe__erro">{textoDe(erroProcessar)}</p>
          )}
          {/* Upload errado, ou ninguem vai processar: sem isto a reuniao
              ficava na fila para sempre. */}
          {!confirmandoApagar ? (
            <button
              type="button"
              className="tela-detalhe__apagar"
              onClick={() => setConfirmandoApagar(true)}
            >
              {t.apagarReuniao}
            </button>
          ) : (
            <ConfirmarApagarReuniao
              id={dados.id}
              titulo={tituloDaReuniao(dados.id, dados.titulo)}
              aoCancelar={() => setConfirmandoApagar(false)}
            />
          )}
        </div>
      )}

      {!erro && dados !== null && temResultadoProcessado(dados) && (
        <div className="tela-detalhe__corpo">
          <header className="tela-detalhe__cabecalho">
            <div className="tela-detalhe__titulo-bloco">
              <TituloEditavel
                id={dados.id}
                titulo={dados.titulo}
                aoMudar={(titulo) => setDados({ ...dados, titulo })}
              />
              {formatarDataReuniao(dados.data, dados.data_origem) && (
                <p className="tela-detalhe__data numeros">
                  {formatarDataReuniao(dados.data, dados.data_origem)}
                </p>
              )}
            </div>
            {/* Revisao acontece uma vez, logo depois do processamento. Com
                todos os clusters decididos, "Revisada" e so o estado, sem
                acao principal; "Editar revisão" fica para corrigir depois.
                Com algum cluster sem decisao, "Revisar" e a acao da tela. */}
            {/* Baixar: link discreto, no tom de "Editar revisão", nos dois
                estados - a transcricao existe antes da revisao. O servidor
                gera o arquivo do .json na hora e da o nome (Content-
                Disposition); `download` so evita navegar para o texto. */}
            <div className="tela-detalhe__revisao">
              {dados.revisada ? (
                <>
                  <span className="tela-detalhe__estado-revisada">{t.revisada}</span>
                  <a
                    className="tela-detalhe__editar-revisao"
                    href={`#/reuniao/${dados.id}/revisar`}
                  >
                    {t.editarRevisao}
                  </a>
                </>
              ) : (
                <a className="tela-detalhe__revisar" href={`#/reuniao/${dados.id}/revisar`}>
                  {t.revisar}
                </a>
              )}
              <a
                className="tela-detalhe__editar-revisao"
                href={`/api/reunioes/${encodeURIComponent(dados.id)}/transcricao?idioma=${idioma}`}
                download
              >
                {t.baixarTranscricao}
              </a>
              <button
                type="button"
                className="tela-detalhe__apagar"
                aria-expanded={confirmandoApagar}
                onClick={() => setConfirmandoApagar(true)}
              >
                {t.apagarReuniao}
              </button>
            </div>
          </header>

          {confirmandoApagar && (
            <ConfirmarApagarReuniao
              id={dados.id}
              titulo={tituloDaReuniao(dados.id, dados.titulo)}
              aoCancelar={() => setConfirmandoApagar(false)}
            />
          )}

          {dados.avisos && dados.avisos.length > 0 && (
            <div className="tela-detalhe__avisos">
              {dados.avisos.map((aviso, i) => (
                <p key={i}>{textoDoAviso(aviso)}</p>
              ))}
            </div>
          )}

          {/* Grade de tres areas (Detalhe.css): ate 1440px o painel fica em
              cima, como sempre foi; acima disso, fita | transcript (640px)
              | painel fixo a direita, e a leitura comeca no topo da tela
              em vez de embaixo do resumo (ADR 0015). */}
          <div
            className={
              "tela-detalhe__layout" +
              (dados.turnos && dados.turnos.length > 0 ? "" : " tela-detalhe__layout--sem-fita")
            }
          >
            {(temEventos || dados.dinamica) && (
              <aside className="tela-detalhe__painel" aria-label={t.dinamicaDaReuniao}>
                {temEventos && (
                  <label className="tela-detalhe__toggle-eventos">
                    <input
                      type="checkbox"
                      checked={mostrarEventos}
                      onChange={alternarMostrarEventos}
                    />
                    {t.mostrarInteracoes}
                  </label>
                )}
                {temEventos && mostrarEventos && temTemposDePalavra && (
                  <p className="tela-detalhe__legenda-faixa">
                    <span className="tela-detalhe__amostra-faixa" aria-hidden="true" />
                    {t.legendaFaixa}
                  </p>
                )}
                {dados.dinamica && (
                  <ResumoDinamica
                    dinamica={dados.dinamica}
                    indiceGaleria={indiceGaleria}
                    rotulo={rotulo}
                  />
                )}
              </aside>
            )}
            {dados.turnos && dados.turnos.length > 0 && (
              <FitaDeTempo
                turnos={dados.turnos}
                clusters={dados.clusters}
                eventos={dados.eventos ?? []}
                indiceGaleria={indiceGaleria}
                duracaoTotal={dados.turnos[dados.turnos.length - 1][1]}
                aoClicar={saltarPara}
              />
            )}

            <div className="transcript" ref={transcriptRef}>
              {selecao && !painel && (
                <button
                  type="button"
                  className="botao-corrigir-selecao"
                  style={
                    {
                      left: selecao.x,
                      "--sel-topo": `${selecao.topo}px`,
                      "--sel-base": `${selecao.base}px`,
                    } as CSSProperties
                  }
                  // Sem isto o clique tiraria a selecao antes de abrir.
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => setPainel(selecao)}
                >
                  {t.corrigir}
                </button>
              )}
              {painel && dados.falas[painel.indice] && (
                <PainelCorrecao
                  key={`${painel.indice}-${painel.inicio}-${painel.fim}`}
                  reuniaoId={dados.id}
                  indice={painel.indice}
                  fala={dados.falas[painel.indice]}
                  inicio={painel.inicio}
                  fim={painel.fim}
                  topo={painel.base}
                  aoFechar={fecharPainel}
                  aoCorrigirFala={(alterada) => atualizarFala(painel.indice, alterada)}
                  aoCorrigirEmTodas={recarregar}
                />
              )}
              {agruparPorTurno(dados.falas).map((grupo, i) => (
                <div key={i} className="bloco-fala">
                  {grupo.falas.map((f, j) => {
                    const eventosDaFala = eventosPorFala.get(f);
                    const lacunasDaFala = lacunasPorFala.get(f) ?? [];
                    // Texto corrigido a mao: a confianca media era do texto
                    // da maquina - "vale conferir o áudio" ja foi feito.
                    const confiancaBaixa =
                      !f.edicao_manual &&
                      f.confianca_media !== undefined &&
                      dados.limiar_confianca_fala !== undefined &&
                      f.confianca_media < dados.limiar_confianca_fala &&
                      contarPalavras(f.texto) >=
                        (dados.min_palavras_confianca_fala ?? 0);
                    const urlFala = urlAudioTrecho(dados.id, f.inicio, f.fim);
                    return (
                      <div
                        key={j}
                        className="linha-fala"
                        data-inicio={f.inicio}
                      >
                        <div className="linha-fala__margem">
                          <BotaoTocarFala
                            tocando={reprodutor.urlTocando === urlFala}
                            aoClicar={() => reprodutor.alternar(urlFala)}
                            rotulo={t.falaDe(rotulo(grupo.falante), formatarTimestamp(f.inicio))}
                          />
                          {j === 0 && (
                            <>
                              <span
                                className={
                                  "linha-fala__nome" +
                                  (ehVozSemPessoa(grupo.falante)
                                    ? " linha-fala__nome--sem-pessoa"
                                    : "")
                                }
                                style={{
                                  color: corDoTextoDaVoz(grupo.falante, indiceGaleria),
                                }}
                                title={rotulo(grupo.falante)}
                              >
                                {rotulo(grupo.falante)}
                              </span>
                              <span className="linha-fala__timestamp numeros">
                                {formatarTimestamp(grupo.inicio)}
                              </span>
                            </>
                          )}
                          {mostrarEventos && eventosDaFala && (
                            <MarcaEventos
                              eventos={eventosDaFala}
                              indiceGaleria={indiceGaleria}
                              rotulo={rotulo}
                            />
                          )}
                          {confiancaBaixa && (
                            <MarcaConfiancaBaixa confianca={f.confianca_media!} />
                          )}
                          {f.edicao_manual && (
                            <MarcaEditada textoOriginal={f.edicao_manual.texto_original} />
                          )}
                        </div>
                        <FalaEditavel
                          reuniaoId={dados.id}
                          indice={indicePorFala.get(f)!}
                          fala={f}
                          aoMudar={(alterada) =>
                            atualizarFala(indicePorFala.get(f)!, alterada)
                          }
                          tocando={reprodutor.urlTocando === urlFala}
                        >
                          <TextoComMarcas
                            fala={f}
                            lacunas={lacunasDaFala}
                            faixas={
                              mostrarEventos
                                ? faixasDaFala(
                                    f.palavras_tempo,
                                    f.falante,
                                    dados.regioes_sobrepostas,
                                  )
                                : []
                            }
                            indiceGaleria={indiceGaleria}
                            rotulo={rotulo}
                          />
                        </FalaEditavel>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
