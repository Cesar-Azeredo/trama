import "./Seta.css";

/* Seta de traco, no lugar dos caracteres "<-" e "->": a Figtree do
   subset latino nao tem U+2190/U+2192, e o caractere caia numa fonte do
   sistema, com outro peso e outra altura. Herda a cor do texto. */
export function Seta({ direcao }: { direcao: "esquerda" | "direita" }) {
  return (
    <svg
      className={`seta seta--${direcao}`}
      width="12"
      height="12"
      viewBox="0 0 12 12"
      aria-hidden="true"
    >
      <path
        d="M1.5 6 H10.5 M6.5 2 L10.5 6 L6.5 10"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
