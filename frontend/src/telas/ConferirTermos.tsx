import { useEffect, useState } from "react";
import {
  carregarReuniao,
  temResultadoProcessado,
  urlAudioTrecho,
  type DetalheReuniao,
} from "../api/reunioes";
import {
  adicionarTermo,
  DESCRICAO_MAX_LEN,
  lerTermosParaConferir,
  marcarRespondido,
  type TermoParaConferir,
} from "../api/termos";
import { BotaoPlay } from "../componentes/BotaoPlay";
import { PainelCorrecao } from "../componentes/PainelCorrecao";
import type { useReprodutor } from "../audio/useReprodutor";
import "./ConferirTermos.css";

type Resposta = "certo" | "corrigir" | null;

function ItemParaConferir({
  id,
  item,
  dados,
  reprodutor,
  aoResponder,
  aoRecarregar,
}: {
  id: string;
  item: TermoParaConferir;
  dados: DetalheReuniao;
  reprodutor: ReturnType<typeof useReprodutor>;
  aoResponder: (mensagem: string) => void;
  aoRecarregar: () => void;
}) {
  const [aberta, setAberta] = useState<Resposta>(null);
  const [descricao, setDescricao] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [corrigidoEmTodas, setCorrigidoEmTodas] = useState(false);
  const o = item.ocorrencia;
  const url = urlAudioTrecho(id, o.audio_inicio, o.audio_fim);
  const fala = temResultadoProcessado(dados) ? dados.falas[o.indice] : undefined;

  async function responder(acao: () => Promise<unknown>, mensagem: string) {
    setOcupado(true);
    setErro(null);
    try {
      await acao();
      aoResponder(mensagem);
    } catch (e) {
      setErro((e as Error).message);
      setOcupado(false);
    }
  }

  return (
    <li className="conferir__item">
      <div className="conferir__cabeca">
        <BotaoPlay
          tocando={reprodutor.urlTocando === url}
          aoClicar={() => reprodutor.alternar(url)}
          rotulo={`o trecho com ${item.forma}`}
        />
        <div>
          <p className="conferir__forma">
            {item.forma}{" "}
            <span className="conferir__vezes">
              {item.total} {item.total === 1 ? "vez" : "vezes"} nesta reunião
            </span>
          </p>
          <p
            className={
              "conferir__contexto" +
              (reprodutor.urlTocando === url ? " trecho-tocando" : "")
            }
          >
            …{o.antes}
            <strong>{o.trecho}</strong>
            {o.depois}…
          </p>
        </div>
      </div>

      {aberta === null && (
        <div className="conferir__respostas">
          <button
            type="button"
            className="conferir__botao"
            onClick={() => setAberta("certo")}
            disabled={ocupado}
          >
            Está certo
          </button>
          <button
            type="button"
            className="conferir__botao"
            onClick={() => setAberta("corrigir")}
            disabled={ocupado || !fala}
          >
            Corrigir para…
          </button>
          <button
            type="button"
            className="conferir__discreto"
            onClick={() =>
              responder(() => marcarRespondido(item.forma), `“${item.forma}” ignorado.`)
            }
            disabled={ocupado}
          >
            Ignorar
          </button>
        </div>
      )}

      {aberta === "certo" && (
        <form
          className="conferir__certo"
          onSubmit={(e) => {
            e.preventDefault();
            responder(
              () => adicionarTermo(item.forma, descricao),
              `“${item.forma}” agora é um termo da empresa.`,
            );
          }}
        >
          <label className="conferir__rotulo" htmlFor={`certo-${item.forma}`}>
            O que é {item.forma}? <span className="conferir__opcional">opcional</span>
          </label>
          <input
            id={`certo-${item.forma}`}
            className="conferir__campo"
            value={descricao}
            maxLength={DESCRICAO_MAX_LEN}
            autoFocus
            onChange={(e) => setDescricao(e.target.value)}
          />
          <div className="conferir__respostas">
            <button type="submit" className="conferir__botao" disabled={ocupado}>
              {ocupado ? "Gravando…" : "Confirmar"}
            </button>
            <button type="button" className="conferir__discreto" onClick={() => setAberta(null)}>
              Voltar
            </button>
          </div>
        </form>
      )}

      {aberta === "corrigir" && fala && (
        <PainelCorrecao
          embutido
          reuniaoId={id}
          indice={o.indice}
          fala={fala}
          inicio={o.posicao}
          fim={o.posicao + o.comprimento}
          topo={0}
          aoFechar={() => {
            if (corrigidoEmTodas) aoResponder(`“${item.forma}” corrigido.`);
            else setAberta(null);
          }}
          // So nesta fala: nas proximas reunioes a forma poderia ser certa
          // - guarda que ja foi respondida, para nao perguntar de novo.
          aoCorrigirFala={() =>
            responder(() => marcarRespondido(item.forma), `“${item.forma}” corrigido nesta fala.`)
          }
          aoCorrigirEmTodas={() => {
            setCorrigidoEmTodas(true);
            aoRecarregar();
          }}
        />
      )}

      {erro && (
        <p className="conferir__erro" role="alert">
          {erro}
        </p>
      )}
    </li>
  );
}

/**
 * "Termos para conferir" (ADR 0022): a segunda etapa da revisao, depois
 * das vozes. O app aponta sozinho siglas e palavras em que a transcricao
 * duvidou varias vezes; cada uma toca, e tem tres respostas. Nenhuma e
 * obrigatoria. Resposta dada nunca volta - nem aqui, nem nas proximas
 * reunioes (fica nos termos da empresa).
 */
export function ConferirTermos({
  id,
  reprodutor,
  aoConcluir,
}: {
  id: string;
  reprodutor: ReturnType<typeof useReprodutor>;
  aoConcluir: () => void;
}) {
  const [itens, setItens] = useState<TermoParaConferir[] | null>(null);
  const [dados, setDados] = useState<DetalheReuniao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ultima, setUltima] = useState<string | null>(null);

  function recarregarReuniao() {
    carregarReuniao(id)
      .then(setDados)
      .catch((e: Error) => setErro(e.message));
  }

  useEffect(() => {
    let cancelado = false;
    Promise.all([lerTermosParaConferir(id), carregarReuniao(id)])
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
      .catch((e: Error) => {
        // Falha aqui nao pode prender a pessoa na revisao: as vozes ja
        // foram gravadas.
        if (!cancelado) setErro(e.message);
      });
    return () => {
      cancelado = true;
    };
    // aoConcluir muda a cada render da Revisao; so o id importa aqui
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (erro) {
    return (
      <section className="conferir">
        <p className="conferir__erro">{erro}</p>
        <button type="button" className="conferir__botao" onClick={aoConcluir}>
          Ir para a reunião
        </button>
      </section>
    );
  }
  if (itens === null || dados === null) {
    return <p className="conferir__nota">Procurando termos para conferir…</p>;
  }

  return (
    <section className="conferir" aria-labelledby="conferir-titulo">
      <h2 className="conferir__titulo" id="conferir-titulo">
        Termos para conferir
      </h2>
      <p className="conferir__nota">
        As vozes estão salvas. Estas palavras podem ter sido transcritas
        errado - ouça e responda as que quiser. Nada aqui é obrigatório, e
        uma resposta dada não é perguntada de novo.
      </p>
      {ultima && (
        <p className="conferir__feito" role="status">
          {ultima}
        </p>
      )}
      {itens.length === 0 ? (
        <p className="conferir__nota">Tudo respondido.</p>
      ) : (
        <ul className="conferir__lista">
          {itens.map((item) => (
            <ItemParaConferir
              key={item.forma}
              id={id}
              item={item}
              dados={dados}
              reprodutor={reprodutor}
              aoRecarregar={recarregarReuniao}
              aoResponder={(mensagem) => {
                setUltima(mensagem);
                setItens((atual) => atual!.filter((i) => i.forma !== item.forma));
              }}
            />
          ))}
        </ul>
      )}
      <div className="conferir__rodape">
        <button type="button" className="botao-salvar-revisao" onClick={aoConcluir}>
          {itens.length === 0 ? "Ir para a reunião" : "Concluir"}
        </button>
      </div>
    </section>
  );
}
