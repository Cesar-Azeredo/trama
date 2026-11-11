import { useCallback, useEffect, useRef, useState } from "react";
import { AVISO_SEM_AUDIO, emDemonstracao } from "../api/sistema";
import { avisar } from "../util/avisos";

/**
 * Um unico clipe tocando por vez no app inteiro - clicar em outro trecho
 * para o anterior, em vez de sobrepor audios. Clicar de novo no mesmo
 * trecho pausa.
 *
 * Em modo demonstracao (REC_MEET_DEMO=1) nao ha audio: o clique avisa
 * "Áudio não disponível na demonstração." em vez de tentar tocar. Se o
 * clique chegar antes de /api/sistema responder, o audio falha (404) e o
 * aviso sai pelo erro.
 */
export function useReprodutor() {
  const [urlTocando, setUrlTocando] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const demonstracaoRef = useRef(false);

  useEffect(() => {
    let vivo = true;
    void emDemonstracao().then((demo) => {
      if (vivo) demonstracaoRef.current = demo;
    });
    return () => {
      vivo = false;
    };
  }, []);

  const alternar = useCallback(
    (url: string) => {
      audioRef.current?.pause();
      if (urlTocando === url) {
        audioRef.current = null;
        setUrlTocando(null);
        return;
      }
      if (demonstracaoRef.current) {
        audioRef.current = null;
        setUrlTocando(null);
        avisar(AVISO_SEM_AUDIO);
        return;
      }
      const falhou = () => {
        setUrlTocando(null);
        void emDemonstracao().then((demo) => {
          if (demo) avisar(AVISO_SEM_AUDIO);
        });
      };
      const audio = new Audio(url);
      audio.addEventListener("ended", () => setUrlTocando(null));
      audio.addEventListener("error", falhou);
      audioRef.current = audio;
      setUrlTocando(url);
      audio.play().catch(falhou);
    },
    [urlTocando],
  );

  return { urlTocando, alternar };
}
