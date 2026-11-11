import { useEffect, useState } from "react";
import { ouvirAvisos } from "../util/avisos";
import "./Aviso.css";

/** Quanto tempo o aviso fica na tela. */
const DURACAO_MS = 3000;
/** Igual a transicao de opacidade em Aviso.css: o texto so sai depois. */
const SAIDA_MS = 150;

/**
 * Aviso curto, um por vez, renderizado uma vez pelo App. Aparece quando
 * alguem chama avisar() (util/avisos.ts) e some sozinho. role="status":
 * o leitor de tela anuncia sem roubar o foco.
 */
export function Aviso() {
  const [texto, setTexto] = useState("");
  const [visivel, setVisivel] = useState(false);

  useEffect(() => {
    let esconder: number | undefined;
    let limpar: number | undefined;
    const parar = ouvirAvisos((novo) => {
      window.clearTimeout(esconder);
      window.clearTimeout(limpar);
      setTexto(novo);
      setVisivel(true);
      esconder = window.setTimeout(() => {
        setVisivel(false);
        limpar = window.setTimeout(() => setTexto(""), SAIDA_MS);
      }, DURACAO_MS);
    });
    return () => {
      parar();
      window.clearTimeout(esconder);
      window.clearTimeout(limpar);
    };
  }, []);

  return (
    <p className={"aviso" + (visivel ? " aviso--visivel" : "")} role="status">
      {texto}
    </p>
  );
}
