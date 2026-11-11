import { useRef } from "react";
import type { Cluster, Evento, Turno } from "../api/reunioes";
import { corDaVoz } from "../vozes/corDaVoz";
import { useTextos } from "../i18n/textos";
import "./FitaDeTempo.css";

/**
 * Fita de tempo (SKILL.md, elemento de assinatura): coluna vertical
 * representando a reuniao inteira, cada turno na cor de quem falou,
 * segmento com altura proporcional a duracao (minimo 0,14% para nao
 * sumir), disputas marcadas com um traco de 2px em --alerta.
 *
 * Clicavel: em vez de um alvo por turno (alguns turnos duram menos de 1s -
 * um botao por turno ficaria bem abaixo dos 44px de toque exigidos pela
 * skill), a fita INTEIRA e um unico <button>, alto o bastante para
 * qualquer alvo de toque real. O clique calcula a fracao vertical e salta
 * o transcript para o tempo correspondente - os segmentos coloridos sao
 * so a pista visual de onde clicar, nao alvos individuais.
 */
export function FitaDeTempo({
  turnos,
  clusters,
  eventos,
  indiceGaleria,
  duracaoTotal,
  aoClicar,
}: {
  turnos: Turno[];
  clusters: Record<string, Cluster>;
  eventos: Evento[];
  indiceGaleria: Map<string, number>;
  duracaoTotal: number;
  aoClicar: (tempo: number) => void;
}) {
  const t = useTextos().correcao;
  const ref = useRef<HTMLButtonElement>(null);

  function clicar(e: React.MouseEvent<HTMLButtonElement>) {
    const retangulo = ref.current?.getBoundingClientRect();
    if (!retangulo) return;
    const fracao = (e.clientY - retangulo.top) / retangulo.height;
    aoClicar(Math.max(0, Math.min(1, fracao)) * duracaoTotal);
  }

  const disputas = eventos.filter((e) => e.tipo === "disputa");

  return (
    <button
      ref={ref}
      type="button"
      className="fita-de-tempo"
      onClick={clicar}
      aria-label={t.fitaDeTempo}
    >
      {turnos.map(([inicio, fim, rotulo], i) => {
        const nome = clusters[rotulo]?.nome ?? rotulo;
        const altura = Math.max(((fim - inicio) / duracaoTotal) * 100, 0.14);
        const topo = (inicio / duracaoTotal) * 100;
        return (
          <span
            key={i}
            className="fita-de-tempo__segmento"
            style={{
              top: `${topo}%`,
              height: `${altura}%`,
              background: corDaVoz(nome, indiceGaleria),
            }}
          />
        );
      })}
      {disputas.map((evento, i) => (
        <span
          key={`disputa-${i}`}
          className="fita-de-tempo__disputa"
          style={{ top: `${(evento.tempo / duracaoTotal) * 100}%` }}
        />
      ))}
    </button>
  );
}
