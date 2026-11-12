import { mensagemDe } from "../api/cliente";
import { mensagem, useMensagem, type Mensagem } from "../i18n/mensagem";
import { useEffect, useMemo, useState } from "react";
import {
  carregarReuniao,
  corrigirFala,
  escreverLacuna,
  lerTrechosParaConferir,
  marcarIninteligivel,
  temResultadoProcessado,
  TEXTO_FALA_MAX_LEN,
  urlAudioTrecho,
  type DetalheReuniao,
  type TrechoParaConferir,
} from "../api/reunioes";
import { BotaoPlay } from "../componentes/BotaoPlay";
import type { useReprodutor } from "../audio/useReprodutor";
import { useTextos } from "../i18n/textos";
import { rotulosDaReuniao } from "../util/falante";
import { formatarTimestamp } from "../util/formatarReuniao";
import "./ConferirTermos.css";
import "./ConferirTrechos.css";

function chaveDo(trecho: TrechoParaConferir) {
  return `${trecho.tipo}-${trecho.inicio}-${trecho.fim}`;
}

function TrechoParaResponder({
  id,
  trecho,
  rotulo,
  reprodutor,
  aoResponder,
}: {
  id: string;
  trecho: TrechoParaConferir;
  rotulo: (nome: string) => string;
  reprodutor: ReturnType<typeof useReprodutor>;
  /** null: "Pular" - nada gravado, nada a dizer. */
  aoResponder: (m: Mensagem | null) => void;
}) {
  const t = useTextos().trechos;
  const tDetalhe = useTextos().detalhe;
  const textoDe = useMensagem();
  // Fala: o campo abre com o texto transcrito, para corrigir; lacuna: vazio.
  const original = trecho.tipo === "fala" ? trecho.texto : "";
  const [texto, setTexto] = useState(original);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<Mensagem | null>(null);
  const url = urlAudioTrecho(id, trecho.audio_inicio, trecho.audio_fim);
  const tocando = reprodutor.urlTocando === url;
  const nome = rotulo(trecho.falante);
  const hora = formatarTimestamp(trecho.inicio);
  const campoId = `trecho-${chaveDo(trecho)}`;
  // Fala sem mudanca nao e correcao: o botao so acende quando ha o que gravar.
  const podeGravar = texto.trim() !== "" && texto.trim() !== original.trim();

  async function responder(acao: () => Promise<unknown>, m: Mensagem) {
    setOcupado(true);
    setErro(null);
    try {
      await acao();
      aoResponder(m);
    } catch (e) {
      setErro(mensagemDe(e));
      setOcupado(false);
    }
  }

  function gravar() {
    if (!podeGravar || ocupado) return;
    responder(
      () =>
        trecho.tipo === "fala"
          ? corrigirFala(id, trecho.indice, texto, trecho.inicio)
          : escreverLacuna(id, trecho.inicio, trecho.fim, texto),
      mensagem((c) => c.trechos.gravado),
    );
  }

  return (
    <li className="conferir__item">
      <div className="conferir__cabeca">
        <BotaoPlay
          tocando={tocando}
          aoClicar={() => reprodutor.alternar(url)}
          rotulo={t.oTrechoDe(nome, hora)}
        />
        <div>
          <p className="trechos__cabeca">
            {trecho.tipo === "fala" ? t.cabecaFala(nome, hora) : t.cabecaLacuna(nome, hora)}
          </p>
          <p className={"conferir__contexto" + (tocando ? " trecho-tocando" : "")}>
            {trecho.tipo === "fala" ? (
              trecho.texto
            ) : (
              <>
                {trecho.antes && <>…{trecho.antes}</>}
                <span className="trechos__lacuna" title={tDetalhe.tituloLacuna}>
                  {" "}
                  {tDetalhe.lacuna}{" "}
                </span>
                {trecho.depois && <>{trecho.depois}…</>}
              </>
            )}
          </p>
        </div>
      </div>

      <form
        className="conferir__certo"
        onSubmit={(e) => {
          e.preventDefault();
          gravar();
        }}
      >
        <label className="conferir__rotulo" htmlFor={campoId}>
          {trecho.tipo === "fala" ? t.oQueFoiDito : t.oQueFoiDitoAqui}
        </label>
        <textarea
          id={campoId}
          className="trechos__campo"
          value={texto}
          maxLength={TEXTO_FALA_MAX_LEN}
          rows={trecho.tipo === "fala" ? 3 : 2}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            // Enter grava, como na correcao da fala; Shift+Enter nao
            // existe aqui - fala e uma linha so (o servidor recusa quebra).
            if (e.key === "Enter" && !e.nativeEvent.isComposing) {
              e.preventDefault();
              gravar();
            }
          }}
        />
        <div className="conferir__respostas">
          <button type="submit" className="conferir__botao" disabled={ocupado || !podeGravar}>
            {ocupado ? t.gravando : t.gravar}
          </button>
          <button
            type="button"
            className="conferir__botao"
            disabled={ocupado}
            onClick={() =>
              responder(
                () => marcarIninteligivel(id, trecho),
                mensagem((c) => c.trechos.marcadoIninteligivel),
              )
            }
          >
            {t.naoDaParaEntender}
          </button>
          <button
            type="button"
            className="conferir__discreto"
            disabled={ocupado}
            onClick={() => aoResponder(null)}
          >
            {t.pular}
          </button>
        </div>
      </form>

      {erro && (
        <p className="conferir__erro" role="alert">
          {textoDe(erro)}
        </p>
      )}
    </li>
  );
}

/**
 * "Trechos para conferir" (ADR 0028): a terceira etapa da revisao, depois
 * das vozes e dos termos. Ate 3 falas de confianca baixa e 2 sons nao
 * transcritos, no maximo 5; cada um toca e tem um campo para escrever o
 * que foi dito. Fala usa a correcao manual que ja existe; o texto de uma
 * lacuna fica gravado dentro dela. "Não dá para entender" nunca volta;
 * "Pular" nao grava nada.
 */
export function ConferirTrechos({
  id,
  reprodutor,
  aoConcluir,
}: {
  id: string;
  reprodutor: ReturnType<typeof useReprodutor>;
  aoConcluir: () => void;
}) {
  const t = useTextos().trechos;
  const [itens, setItens] = useState<TrechoParaConferir[] | null>(null);
  const [dados, setDados] = useState<DetalheReuniao | null>(null);
  const [erro, setErro] = useState<Mensagem | null>(null);
  const [ultima, setUltima] = useState<Mensagem | null>(null);
  const textoDe = useMensagem();

  useEffect(() => {
    let cancelado = false;
    Promise.all([lerTrechosParaConferir(id), carregarReuniao(id)])
      .then(([lista, d]) => {
        if (cancelado) return;
        // Nada a conferir: a etapa nao existe para esta reuniao.
        if (lista.length === 0) {
          aoConcluir();
          return;
        }
        setItens(lista);
        setDados(d);
      })
      .catch((e: unknown) => {
        // Falha aqui nao pode prender a pessoa na revisao: as vozes ja
        // foram gravadas.
        if (!cancelado) setErro(mensagemDe(e));
      });
    return () => {
      cancelado = true;
    };
    // aoConcluir muda a cada render da Revisao; so o id importa aqui
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Os mesmos nomes do Detalhe: "voz não atribuída" numerada igual.
  const rotulo = useMemo(() => {
    if (!dados || !temResultadoProcessado(dados)) return rotulosDaReuniao([]);
    return rotulosDaReuniao([
      ...Object.values(dados.clusters).map((c) => c.nome),
      ...dados.falas.map((f) => f.falante),
      ...Object.keys(dados.dinamica ?? {}),
      ...(dados.eventos ?? []).flatMap((e) => [e.entrante, e.falava]),
    ]);
  }, [dados]);

  if (erro) {
    return (
      <section className="conferir">
        <p className="conferir__erro">{textoDe(erro)}</p>
        <button type="button" className="conferir__botao" onClick={aoConcluir}>
          {t.irParaReuniao}
        </button>
      </section>
    );
  }
  if (itens === null || dados === null) {
    return <p className="conferir__nota">{t.procurando}</p>;
  }

  return (
    <section className="conferir" aria-labelledby="trechos-titulo">
      <h2 className="conferir__titulo" id="trechos-titulo">
        {t.titulo}
      </h2>
      <p className="conferir__nota">{t.nota}</p>
      {ultima && (
        <p className="conferir__feito" role="status">
          {textoDe(ultima)}
        </p>
      )}
      {itens.length === 0 ? (
        <p className="conferir__nota">{t.tudoRespondido}</p>
      ) : (
        <ul className="conferir__lista">
          {itens.map((trecho) => (
            <TrechoParaResponder
              key={chaveDo(trecho)}
              id={id}
              trecho={trecho}
              rotulo={rotulo}
              reprodutor={reprodutor}
              aoResponder={(m) => {
                setUltima(m);
                setItens((atual) => atual!.filter((i) => chaveDo(i) !== chaveDo(trecho)));
              }}
            />
          ))}
        </ul>
      )}
      <div className="conferir__rodape">
        <button type="button" className="botao-salvar-revisao" onClick={aoConcluir}>
          {itens.length === 0 ? t.irParaReuniao : t.concluir}
        </button>
      </div>
    </section>
  );
}
