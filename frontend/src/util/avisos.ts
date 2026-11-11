/**
 * Canal unico de avisos curtos para o <Aviso> do App (componentes/Aviso.tsx).
 * Quem avisa nao precisa saber onde o aviso aparece - um so lugar na tela,
 * uma so regiao para o leitor de tela.
 */
type Ouvinte = (texto: string) => void;

const ouvintes = new Set<Ouvinte>();

export function avisar(texto: string): void {
  ouvintes.forEach((ouvir) => ouvir(texto));
}

export function ouvirAvisos(ouvir: Ouvinte): () => void {
  ouvintes.add(ouvir);
  return () => {
    ouvintes.delete(ouvir);
  };
}
