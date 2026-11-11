import { useEffect, useRef, useState } from "react";
import {
  cancelarProcessamento,
  carregarReuniao,
  conectarProgresso,
  iniciarProcessamento,
  temResultadoProcessado,
  type DetalheEtapa,
  type EstadoProcessamento,
} from "../api/reunioes";
import { textoDoAviso } from "../api/cliente";
import { formatarDuracao, tituloDaReuniao } from "../util/formatarReuniao";
import { useTextos } from "../i18n/textos";
import "./ProcessamentoReuniao.css";

/**
 * O que o pipeline acrescentou a etapa atual ("- N falantes" na 2, motor e
 * termos do dominio na 5) chega como DADO (servidor/processamento.py:
 * detalhe_da_etapa) e vira texto aqui, no idioma da tela. Etapa sem
 * acrescimo: nada.
 */
function textoDoDetalhe(
  d: DetalheEtapa,
  t: ReturnType<typeof useTextos>["processamento"],
): string | null {
  const partes: string[] = [];
  if (d.falantes !== undefined) partes.push(t.aoVivoFalantes(d.falantes));
  else if (d.min !== undefined && d.max !== undefined) partes.push(t.aoVivoEntre(d.min, d.max));
  else if (d.min !== undefined) partes.push(t.aoVivoPeloMenos(d.min));
  else if (d.max !== undefined) partes.push(t.aoVivoAte(d.max));
  if (d.asr) partes.push(t.aoVivoMotor(d.asr) + (d.termos ? ` (${t.aoVivoTermos(d.termos)})` : ""));
  return partes.length ? partes.join(" ") : null;
}

function IconeConcluida() {
  const t = useTextos().processamento;
  return (
    <svg width="11" height="11" viewBox="0 0 14 14" role="img" aria-label={t.concluida}>
      <path
        d="M2 7.5 L5.5 11 L12 3"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ListaEtapas({ etapaAtual, detalhe }: { etapaAtual: number; detalhe: DetalheEtapa }) {
  const t = useTextos().processamento;
  const aoVivo = textoDoDetalhe(detalhe, t);
  return (
    <ol className="lista-etapas">
      {/* O servidor manda o NUMERO da etapa; o texto e sempre o do catalogo. */}
      {t.etapas.map((texto, i) => {
        const numero = i + 1;
        const concluida = numero < etapaAtual;
        const atual = numero === etapaAtual;
        return (
          <li
            key={numero}
            aria-current={atual ? "step" : undefined}
            className={
              "lista-etapas__item" +
              (concluida ? " lista-etapas__item--concluida" : "") +
              (atual ? " lista-etapas__item--atual" : "")
            }
          >
            {/* A marca e o que separa concluida de pendente (as duas no
                mesmo tom de texto): o check e lido como "concluída"; o
                numero fica oculto, a <ol> ja numera. A atual vai pelo
                aria-current. */}
            <span className="lista-etapas__marca">
              {concluida ? <IconeConcluida /> : <span aria-hidden="true">{numero}</span>}
            </span>
            <span className="lista-etapas__texto">
              {texto}
              {atual && aoVivo && <span className="lista-etapas__ao-vivo">{aoVivo}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

type EstadoTela =
  | { tipo: "carregando" }
  | { tipo: "ocioso" }
  | { tipo: "progresso"; dados: EstadoProcessamento };

export function ProcessamentoReuniao({ id }: { id: string }) {
  const t = useTextos().processamento;
  const comum = useTextos().comum;
  const formatos = useTextos().formatos;
  const [tela, setTela] = useState<EstadoTela>({ tipo: "carregando" });
  const [decorrido, setDecorrido] = useState(0);
  const [emAcao, setEmAcao] = useState(false);
  const [erroAcao, setErroAcao] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  // O titulo (dado na Nova reuniao, ou depois) - o progresso por SSE nao o
  // traz. Falha ao buscar so deixa o padrao "Reuniao NN".
  const [titulo, setTitulo] = useState<string | null>(null);
  useEffect(() => {
    let cancelado = false;
    carregarReuniao(id)
      .then((d) => {
        if (!cancelado) setTitulo(d.titulo);
      })
      .catch(() => {});
    return () => {
      cancelado = true;
    };
  }, [id]);

  function conectar() {
    esRef.current?.close();
    const es = conectarProgresso(id, (evento) => {
      if (evento.status === "ocioso") {
        setTela({ tipo: "ocioso" });
        es.close();
        return;
      }
      setTela({ tipo: "progresso", dados: evento });
      if (evento.status === "concluido") {
        es.close();
        window.location.hash = `#/reuniao/${id}/revisar`;
      } else if (evento.status !== "rodando") {
        es.close();
      }
    });
    esRef.current = es;
  }

  useEffect(() => {
    conectar();
    return () => esRef.current?.close();
    // conectar() so depende de `id`, recriada a cada render de proposito
    // (fecha a antiga antes de abrir a nova) - nao entra no array de deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Relogio de decorrido - proprio, TICANDO A CADA SEGUNDO, independente
  // de quando o SSE manda o proximo evento (que so chega quando a ETAPA
  // muda, podendo ficar minutos em silencio dentro da transcricao).
  useEffect(() => {
    if (tela.tipo !== "progresso" || tela.dados.status !== "rodando") return;
    const inicioMs = tela.dados.iniciado_em * 1000;
    const atualizar = () => setDecorrido((Date.now() - inicioMs) / 1000);
    atualizar();
    const intervalo = window.setInterval(atualizar, 1000);
    return () => window.clearInterval(intervalo);
  }, [tela]);

  async function cancelar() {
    const confirmado = window.confirm(t.confirmarCancelar);
    if (!confirmado) return;
    setEmAcao(true);
    setErroAcao(null);
    try {
      await cancelarProcessamento(id);
    } catch (e) {
      setErroAcao((e as Error).message);
    } finally {
      setEmAcao(false);
    }
  }

  async function tentarDeNovo(pessoas: string[]) {
    setEmAcao(true);
    setErroAcao(null);
    try {
      await iniciarProcessamento(id, pessoas);
      conectar();
    } catch (e) {
      setErroAcao((e as Error).message);
    } finally {
      setEmAcao(false);
    }
  }

  return (
    <main className="tela-processamento">
      <a className="tela-processamento__voltar" href="#/reunioes">
        ← {comum.reunioes}
      </a>
      <h1 className="tela-processamento__titulo">{tituloDaReuniao(id, titulo)}</h1>

      {tela.tipo === "carregando" && (
        <p className="tela-processamento__estado">{t.conectando}</p>
      )}

      {tela.tipo === "ocioso" && <TelaOciosa id={id} />}

      {tela.tipo === "progresso" && tela.dados.status === "rodando" && (
        <>
          <ListaEtapas etapaAtual={tela.dados.etapa} detalhe={tela.dados.detalhe} />
          <p className="tela-processamento__decorrido numeros">
            {t.decorrido(formatarDuracao(decorrido))}
          </p>
          <div className="tela-processamento__rodape">
            <button
              type="button"
              className="botao-cancelar"
              onClick={cancelar}
              disabled={emAcao}
            >
              {t.cancelar}
            </button>
            <span className="tela-processamento__legenda-cancelar">
              {t.legendaCancelar}
            </span>
          </div>
          {erroAcao && <p className="tela-processamento__erro">{erroAcao}</p>}
        </>
      )}

      {tela.tipo === "progresso" && tela.dados.status === "cancelado" && (
        <div className="tela-processamento__aviso">
          <p>{t.cancelado}</p>
          <a className="tela-processamento__link" href={`#/reuniao/${id}`}>
            {t.verReuniao}
          </a>
        </div>
      )}

      {tela.tipo === "progresso" && tela.dados.status === "erro" && (
        <div className="tela-processamento__aviso tela-processamento__aviso--erro">
          <p>
            {textoDoAviso(tela.dados.erro) ?? t.falhou}
          </p>
          <button
            type="button"
            className="botao-cancelar"
            onClick={() => tentarDeNovo(tela.dados.pessoas)}
            disabled={emAcao}
          >
            {emAcao ? t.tentando : formatos.tentarNovamente}
          </button>
          {erroAcao && <p className="tela-processamento__erro">{erroAcao}</p>}
        </div>
      )}
    </main>
  );
}

/**
 * Nada rodando para esta reuniao agora - ou nunca foi iniciada, ou ja
 * terminou e o slot de estado em memoria foi ocupado por outra reuniao
 * (so um processamento por vez). Confere o estado de verdade via
 * GET /api/reunioes/{id} para decidir o que mostrar, em vez de fingir
 * que "ocioso" so pode significar uma coisa.
 */
function TelaOciosa({ id }: { id: string }) {
  const t = useTextos().processamento;
  // O que mostrar, nao o texto pronto - o texto sai do catalogo na hora de
  // desenhar, para trocar junto com o idioma. O erro vem do servidor como
  // esta.
  const [mensagem, setMensagem] = useState<
    { tipo: "verificando" } | { tipo: "parada" } | { tipo: "erro"; texto: string }
  >({ tipo: "verificando" });

  useEffect(() => {
    let cancelado = false;
    carregarReuniao(id)
      .then((dados) => {
        if (cancelado) return;
        if (temResultadoProcessado(dados)) {
          window.location.hash = `#/reuniao/${id}/revisar`;
          return;
        }
        setMensagem({ tipo: "parada" });
      })
      .catch((e: Error) => {
        if (!cancelado) setMensagem({ tipo: "erro", texto: e.message });
      });
    return () => {
      cancelado = true;
    };
  }, [id]);

  return (
    <div className="tela-processamento__aviso">
      <p>
        {mensagem.tipo === "verificando"
          ? t.verificando
          : mensagem.tipo === "parada"
            ? t.naoEstaProcessando
            : mensagem.texto}
      </p>
      <a className="tela-processamento__link" href="#/reunioes">
        {t.verLista}
      </a>
    </div>
  );
}
