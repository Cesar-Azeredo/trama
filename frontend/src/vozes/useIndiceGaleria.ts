import { useContext } from "react";
import { GaleriaContexto } from "./GaleriaContext";

export function useIndiceGaleria(): Map<string, number> {
  return useContext(GaleriaContexto).indice;
}

/** Para quem muda a galeria (revisao, exclusao) avisar as outras telas. */
export function useRecarregarGaleria(): () => void {
  return useContext(GaleriaContexto).recarregar;
}
