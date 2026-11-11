import { mensagemDe } from "../../api/cliente";
import { mensagem, useMensagem, type Mensagem } from "../../i18n/mensagem";
import { useState } from "react";
import {
  previaReaplicacao,
  reaplicarGlossario,
  type PreviaReaplicacao,
} from "../../api/termos";
import { useTextos } from "../../i18n/textos";
import { formatarTitulo } from "../../util/formatarReuniao";
import { numero } from "../../util/numeros";

/**
 * Reaplica os termos da empresa SALVOS (o termos.txt inteiro) nas reunioes ja processadas (.json e .txt),
 * pela mesma funcao do pipeline.py. Dois passos: previa (quantas substituicoes,
 * em quais reunioes) e so depois grava - com a assinatura da previa, para
 * nunca gravar algo diferente do que a pessoa viu.
 */
export function ReaplicarNasReunioes({ desabilitado }: { desabilitado: boolean }) {
  const [previa, setPrevia] = useState<PreviaReaplicacao | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; mensagem: Mensagem } | null>(null);
  const textoDe = useMensagem();
  const t = useTextos().termos;

  async function verPrevia() {
    setOcupado(true);
    setAviso(null);
    try {
      setPrevia(await previaReaplicacao());
    } catch (e) {
      setAviso({ tipo: "erro", mensagem: mensagemDe(e) });
    } finally {
      setOcupado(false);
    }
  }

  async function aplicar() {
    if (!previa) return;
    setOcupado(true);
    setAviso(null);
    try {
      const r = await reaplicarGlossario(previa.assinatura);
      setPrevia(null);
      const n = r.aplicadas.length;
      setAviso({
        tipo: "ok",
        mensagem: mensagem((c) => (n === 0 ? c.termos.nadaFoiAlterado : c.termos.aplicadoEm(n))),
      });
    } catch (e) {
      setAviso({ tipo: "erro", mensagem: mensagemDe(e) });
      setPrevia(null);
    } finally {
      setOcupado(false);
    }
  }

  const substituicoes = previa
    ? t.substituicoesEmReunioes(previa.total, previa.reunioes.length)
    : null;

  return (
    <div className="reaplicar">
      {!previa && (
        <>
          <button
            type="button"
            className="perfil__botao-secundario"
            onClick={verPrevia}
            disabled={desabilitado || ocupado}
          >
            {ocupado ? t.conferindo : t.aplicarNasProcessadas}
          </button>
          <p className="perfil__nota">
            {desabilitado ? t.salveAntes : t.mostraAntes}
          </p>
        </>
      )}

      {previa && previa.total === 0 && (
        <div className="reaplicar__previa">
          <p className="perfil__texto">{t.nadaACorrigir}</p>
          <button type="button" className="perfil__botao-discreto" onClick={() => setPrevia(null)}>
            {t.fechar}
          </button>
        </div>
      )}

      {previa && previa.total > 0 && (
        <div className="reaplicar__previa" role="alertdialog" aria-labelledby="reaplicar-titulo">
          <p className="reaplicar__titulo" id="reaplicar-titulo">
            {substituicoes?.[0]}
            <span className="numeros">{numero(previa.total)}</span>
            {substituicoes?.[1]}
            <span className="numeros">{numero(previa.reunioes.length)}</span>
            {substituicoes?.[2]}
          </p>
          <ul className="reaplicar__lista">
            {previa.reunioes.map((r) => (
              <li key={r.id}>
                <span className="reaplicar__reuniao">{formatarTitulo(r.id)}</span>{" "}
                <span className="numeros">{numero(r.substituicoes)}</span> —{" "}
                {Object.entries(r.por_termo)
                  .map(([termo, n]) => `${termo} ×${numero(n)}`)
                  .join(", ")}
              </li>
            ))}
          </ul>
          <p className="perfil__nota">{t.notaReescreve}</p>
          <div className="perfil__acoes perfil__acoes--sem-regua">
            <button
              type="button"
              className="perfil__botao-primario"
              onClick={aplicar}
              disabled={ocupado}
            >
              {ocupado ? t.aplicando : t.aplicar}
            </button>
            <button
              type="button"
              className="perfil__botao-discreto"
              onClick={() => setPrevia(null)}
              disabled={ocupado}
              autoFocus
            >
              {t.cancelar}
            </button>
          </div>
        </div>
      )}

      {aviso && (
        <p
          className={"perfil__status" + (aviso.tipo === "erro" ? " perfil__status--erro" : "")}
          role="status"
        >
          {textoDe(aviso.mensagem)}
        </p>
      )}
    </div>
  );
}
