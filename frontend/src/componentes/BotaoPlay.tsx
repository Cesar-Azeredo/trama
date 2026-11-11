import "./BotaoPlay.css";

/**
 * O play e a UNICA excecao de border-radius da skill: circular, 44px.
 * Icone SVG de traco/preenchimento inline, herda a cor do texto.
 */
export function BotaoPlay({
  tocando,
  aoClicar,
  rotulo,
}: {
  tocando: boolean;
  aoClicar: () => void;
  rotulo: string;
}) {
  return (
    <button
      type="button"
      className="botao-play"
      onClick={aoClicar}
      aria-label={tocando ? `Pausar ${rotulo}` : `Tocar ${rotulo}`}
      aria-pressed={tocando}
    >
      {tocando ? (
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          <rect x="2" y="1" width="4" height="12" fill="currentColor" />
          <rect x="8" y="1" width="4" height="12" fill="currentColor" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          <path d="M2 1 L13 7 L2 13 Z" fill="currentColor" />
        </svg>
      )}
    </button>
  );
}
