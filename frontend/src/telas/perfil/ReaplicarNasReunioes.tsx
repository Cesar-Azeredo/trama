import { useState } from "react";
import {
  previaReaplicacao,
  reaplicarGlossario,
  type PreviaReaplicacao,
} from "../../api/termos";
import { formatarTitulo } from "../../util/formatarReuniao";

/**
 * Reaplica os termos da empresa SALVOS (o termos.txt inteiro) nas reunioes ja processadas (.json e .txt),
 * pela mesma funcao do pipeline.py. Dois passos: previa (quantas substituicoes,
 * em quais reunioes) e so depois grava - com a assinatura da previa, para
 * nunca gravar algo diferente do que a pessoa viu.
 */
export function ReaplicarNasReunioes({ desabilitado }: { desabilitado: boolean }) {
  const [previa, setPrevia] = useState<PreviaReaplicacao | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [mensagem, setMensagem] = useState<{ tipo: "ok" | "erro"; texto: string } | null>(
    null,
  );

  async function verPrevia() {
    setOcupado(true);
    setMensagem(null);
    try {
      setPrevia(await previaReaplicacao());
    } catch (e) {
      setMensagem({ tipo: "erro", texto: (e as Error).message });
    } finally {
      setOcupado(false);
    }
  }

  async function aplicar() {
    if (!previa) return;
    setOcupado(true);
    setMensagem(null);
    try {
      const r = await reaplicarGlossario(previa.assinatura);
      setPrevia(null);
      setMensagem({
        tipo: "ok",
        texto:
          r.aplicadas.length === 0
            ? "Nada foi alterado."
            : `Aplicado em ${r.aplicadas.length} ${r.aplicadas.length === 1 ? "reunião" : "reuniões"}.`,
      });
    } catch (e) {
      setMensagem({ tipo: "erro", texto: (e as Error).message });
      setPrevia(null);
    } finally {
      setOcupado(false);
    }
  }

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
            {ocupado ? "Conferindo…" : "Aplicar às reuniões já processadas"}
          </button>
          <p className="perfil__nota">
            {desabilitado
              ? "Salve antes - a correção usa o que está gravado."
              : "Mostra antes quantas substituições seriam feitas, e em quais reuniões. Nada muda até você confirmar."}
          </p>
        </>
      )}

      {previa && previa.total === 0 && (
        <div className="reaplicar__previa">
          <p className="perfil__texto">
            Nada a corrigir: as reuniões já processadas estão de acordo com os
            termos da empresa.
          </p>
          <button type="button" className="perfil__botao-discreto" onClick={() => setPrevia(null)}>
            Fechar
          </button>
        </div>
      )}

      {previa && previa.total > 0 && (
        <div className="reaplicar__previa" role="alertdialog" aria-labelledby="reaplicar-titulo">
          <p className="reaplicar__titulo" id="reaplicar-titulo">
            <span className="numeros">{previa.total}</span>{" "}
            {previa.total === 1 ? "substituição" : "substituições"} em{" "}
            <span className="numeros">{previa.reunioes.length}</span>{" "}
            {previa.reunioes.length === 1 ? "reunião" : "reuniões"}
          </p>
          <ul className="reaplicar__lista">
            {previa.reunioes.map((r) => (
              <li key={r.id}>
                <span className="reaplicar__reuniao">{formatarTitulo(r.id)}</span>{" "}
                <span className="numeros">{r.substituicoes}</span> —{" "}
                {Object.entries(r.por_termo)
                  .map(([termo, n]) => `${termo} ×${n}`)
                  .join(", ")}
              </li>
            ))}
          </ul>
          <p className="perfil__nota">
            Reescreve o texto (.json e .txt) dessas reuniões. As marcas de
            posição (pista de palavra, confiança baixa, trecho sem texto)
            acompanham a correção.
          </p>
          <div className="perfil__acoes perfil__acoes--sem-regua">
            <button
              type="button"
              className="perfil__botao-primario"
              onClick={aplicar}
              disabled={ocupado}
            >
              {ocupado ? "Aplicando…" : "Aplicar"}
            </button>
            <button
              type="button"
              className="perfil__botao-discreto"
              onClick={() => setPrevia(null)}
              disabled={ocupado}
              autoFocus
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {mensagem && (
        <p
          className={"perfil__status" + (mensagem.tipo === "erro" ? " perfil__status--erro" : "")}
          role="status"
        >
          {mensagem.texto}
        </p>
      )}
    </div>
  );
}
