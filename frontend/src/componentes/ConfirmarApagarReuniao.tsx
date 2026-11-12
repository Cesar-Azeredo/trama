import { useEffect, useState } from "react";
import { mensagemDe } from "../api/cliente";
import { apagarReuniao, previaApagarReuniao, type PerdaDeVoz } from "../api/reunioes";
import { useRecarregarGaleria } from "../vozes/useIndiceGaleria";
import { useMensagem, type Mensagem } from "../i18n/mensagem";
import { useTextos } from "../i18n/textos";
import { numero } from "../util/numeros";
import "./ConfirmarExclusao.css";

/**
 * Confirmacao de "Apagar reunião", na propria tela - o mesmo cuidado de
 * excluir a voz de uma pessoa (Pessoas.tsx): diz antes quanto de voz
 * aprendida cada pessoa perde (GET .../exclusao, nada apagado), com o foco
 * em "Cancelar". Apagada, volta para a lista de reunioes.
 */
export function ConfirmarApagarReuniao({
  id,
  titulo,
  aoCancelar,
}: {
  id: string;
  titulo: string;
  aoCancelar: () => void;
}) {
  const t = useTextos().detalhe;
  const textoDe = useMensagem();
  const recarregarGaleria = useRecarregarGaleria();
  const [perdas, setPerdas] = useState<PerdaDeVoz[] | null>(null);
  const [apagando, setApagando] = useState(false);
  const [erro, setErro] = useState<Mensagem | null>(null);

  useEffect(() => {
    let cancelado = false;
    previaApagarReuniao(id)
      .then((p) => {
        if (!cancelado) setPerdas(p);
      })
      .catch((e: unknown) => {
        if (!cancelado) setErro(mensagemDe(e));
      });
    return () => {
      cancelado = true;
    };
  }, [id]);

  async function apagar() {
    setApagando(true);
    setErro(null);
    try {
      await apagarReuniao(id);
      // Alguem pode ter saido da galeria - o indice de cor precisa saber.
      recarregarGaleria();
      window.location.hash = "#/reunioes";
    } catch (e) {
      setErro(mensagemDe(e));
      setApagando(false);
    }
  }

  const segundos = (s: number) => t.segundos(numero(Math.round(s)));

  return (
    <div className="confirmar-exclusao" role="alertdialog" aria-labelledby="apagar-titulo">
      <p className="confirmar-exclusao__titulo" id="apagar-titulo">
        {t.apagarTitulo(titulo)}
      </p>
      <p className="confirmar-exclusao__texto">{t.apagarTexto}</p>
      {perdas === null && !erro && (
        <p className="confirmar-exclusao__texto">{t.apagarCalculando}</p>
      )}
      {perdas !== null && perdas.length === 0 && (
        <p className="confirmar-exclusao__texto">{t.apagarSemVoz}</p>
      )}
      {perdas !== null && perdas.length > 0 && (
        <>
          <p className="confirmar-exclusao__texto">{t.apagarPerdas}</p>
          <ul className="confirmar-exclusao__lista">
            {perdas.map((p) => (
              <li key={p.pessoa}>
                {p.perfil_some
                  ? t.apagarPerdeTudo(p.pessoa, segundos(p.peso_s))
                  : t.apagarPerde(p.pessoa, segundos(p.peso_s), segundos(p.restante_s))}
              </li>
            ))}
          </ul>
          <p className="confirmar-exclusao__texto">{t.apagarBackups}</p>
        </>
      )}
      <div className="confirmar-exclusao__acoes">
        <button
          type="button"
          className="confirmar-exclusao__sim"
          onClick={apagar}
          // Sem a previa, a pessoa nao viu o que perde - nao apaga.
          disabled={apagando || perdas === null}
        >
          {apagando ? t.apagando : t.apagarReuniao}
        </button>
        <button
          type="button"
          className="confirmar-exclusao__nao"
          onClick={aoCancelar}
          disabled={apagando}
          autoFocus
        >
          {t.cancelar}
        </button>
      </div>
      {erro && (
        <p className="confirmar-exclusao__erro" role="alert">
          {textoDe(erro)}
        </p>
      )}
    </div>
  );
}
