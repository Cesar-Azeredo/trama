import { createContext, useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { listarPessoas } from "../api/pessoas";
import { construirIndiceGaleria } from "./corDaVoz";

/**
 * Indice de cor por pessoa (ver corDaVoz.ts), buscado uma vez e
 * compartilhado entre as telas - sem isso, cada tela repetiria a chamada
 * a GET /api/pessoas e cada uma poderia acabar com um indice diferente.
 *
 * `recarregar` existe porque a galeria MUDA com o app aberto: uma
 * revisao pode colocar gente nova nela, e a exclusao (tela Pessoas) tira.
 * Antes, o indice era lido so ao abrir o app - quem entrava na galeria
 * depois ficava fora dele ate recarregar a pagina, caia no hash de
 * reserva e podia sair na mesma cor de outra pessoa.
 */
interface Galeria {
  indice: Map<string, number>;
  recarregar: () => void;
}

export const GaleriaContexto = createContext<Galeria>({
  indice: new Map(),
  recarregar: () => {},
});

export function GaleriaProvider({ children }: { children: ReactNode }) {
  const [indice, setIndice] = useState<Map<string, number>>(new Map());
  const [versao, setVersao] = useState(0);
  const recarregar = useCallback(() => setVersao((v) => v + 1), []);

  useEffect(() => {
    let cancelado = false;
    listarPessoas()
      .then((pessoas) => {
        if (!cancelado) setIndice(construirIndiceGaleria(pessoas));
      })
      // So estabiliza a cor entre reunioes - se falhar, corDaVoz cai no
      // hash de reserva. Nao precisa propagar erro para a tela.
      .catch((e: Error) => console.error("Falha ao carregar galeria:", e));
    return () => {
      cancelado = true;
    };
  }, [versao]);

  return (
    <GaleriaContexto.Provider value={{ indice, recarregar }}>
      {children}
    </GaleriaContexto.Provider>
  );
}
