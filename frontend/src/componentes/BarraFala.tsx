import type { ResumoReuniao } from "../api/reunioes";
import { corDaVoz } from "../vozes/corDaVoz";
import { ehVozSemPessoa, ordemDaBarra } from "../util/falante";
import "./BarraFala.css";

/**
 * Barra de tempo de fala (SKILL.md, elemento de assinatura): 5px, segmentos
 * proporcionais a fala_pct, na cor de cada voz. A cor nunca e o unico
 * portador de significado - a lista de nomes fica ao lado, na MESMA ordem
 * dos segmentos (maior fala_pct primeiro, como o servidor ja devolve) -
 * e essa correspondencia que sustenta a acessibilidade da barra.
 */
export function BarraFala({
  dinamica,
  indiceGaleria,
}: {
  dinamica: ResumoReuniao["dinamica"];
  indiceGaleria: Map<string, number>;
}) {
  if (!dinamica) return null;
  // Voz sem pessoa (DESCONHECIDO_/IGNORADO_) vai pro fim, em --tinta-tenue
  // (SKILL.md: o tom de falante nao identificado) - nunca uma cor de voz
  // por hash, que poderia repetir a de uma pessoa de verdade.
  const itens = ordemDaBarra(dinamica);
  return (
    <div
      className="barra-fala"
      role="img"
      aria-label={`Tempo de fala: ${itens
        .map(
          (d) =>
            `${ehVozSemPessoa(d.pessoa) ? "voz não atribuída" : d.pessoa} ${Math.round(d.fala_pct)}%`,
        )
        .join(", ")}`}
    >
      {itens.map((d) => (
        <span
          key={d.pessoa}
          className="barra-fala__segmento"
          style={{
            width: `${d.fala_pct}%`,
            background: ehVozSemPessoa(d.pessoa)
              ? "var(--tinta-tenue)"
              : corDaVoz(d.pessoa, indiceGaleria),
          }}
        />
      ))}
    </div>
  );
}
