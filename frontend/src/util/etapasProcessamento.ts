import { processamento } from "../i18n/pt/processamento";

/**
 * Rotulos FIXOS das 5 etapas - o que a tela de processamento mostra,
 * sempre a mesma independente do audio. O texto EXATO que pipeline.py imprime (que
 * pode variar - "N falantes", contagem de termos do dominio) aparece a
 * parte, como atividade ao vivo da etapa atual - ver `rotuloAoVivo`.
 *
 * Nenhuma barra de progresso linear: as 5 etapas NAO tem duracao igual
 * (transcricao sozinha leva mais que as outras quatro juntas) - uma
 * barra proporcional a "etapa atual / 5" mentiria sobre quanto falta.
 *
 * SEMPRE em portugues, qualquer que seja o idioma da tela: e com este
 * texto que o rotulo ao vivo (impresso em portugues pelo pipeline) e
 * comparado. A tela EXIBE a traducao da mesma posicao
 * (useTextos().processamento.etapas[i]).
 */
export const ETAPAS: readonly string[] = processamento.etapas;
