import { Lista } from "./telas/Lista";
import { Detalhe } from "./telas/Detalhe";
import { Revisao } from "./telas/Revisao";
import { NovaReuniao } from "./telas/NovaReuniao";
import { ProcessamentoReuniao } from "./telas/ProcessamentoReuniao";
import { Pessoas } from "./telas/Pessoas";
import { Perfil } from "./telas/Perfil";
import { Cabecalho } from "./componentes/Cabecalho";
import { BarraAbas } from "./componentes/BarraAbas";
import { Aviso } from "./componentes/Aviso";
import { GaleriaProvider } from "./vozes/GaleriaContext";
import { useRota, type Rota } from "./tema/useRota";

/**
 * Dono da casca: cabecalho + nav renderizam UMA VEZ aqui, fora do
 * roteamento. Cada tela abaixo devolve so conteudo - nenhuma importa
 * nem renderiza <Cabecalho> por conta propria (era assim antes: cinco
 * copias, cada uma decidindo sua propria largura, o motivo de o
 * cabecalho ter ficado capado em 640px).
 *
 * .area-conteudo (base.css) e quem tem view-transition-name;
 * .area-conteudo__rolagem, dentro dela, e quem rola. Testado na
 * pratica: dar o nome da transicao pro MESMO elemento que tambem rola
 * sozinho deixa a View Transition instavel (a transicao fica pendurada,
 * "ready" nunca resolve). Um elemento so pra ser capturado (limite
 * fixo, sem rolagem propria) e outro so pra rolar resolve.
 *
 * Quem rola NAO e o <main> de cada tela: cada <main> tem max-width
 * proprio (820px no Detalhe, 640px na Revisao), entao o rolamento
 * ficava preso numa coluna no meio da janela - barra de rolagem na
 * borda da coluna, faixa morta dos lados. O elemento que rola tem que
 * ocupar a largura inteira; a largura de leitura fica com o <main>.
 *
 * key por rota: o elemento que rola persiste entre telas, e sem remontar
 * a posicao de rolagem de uma tela vazaria pra proxima (abrir uma
 * reuniao ja no meio do transcript porque a lista estava rolada). Com a
 * key, cada tela nasce no topo - igual a quando cada <main> rolava
 * sozinho.
 */
function chaveDaRota(rota: Rota): string {
  return "id" in rota ? `${rota.tipo}/${rota.id}` : rota.tipo;
}

function App() {
  const rota = useRota();
  return (
    <GaleriaProvider>
      <Cabecalho rota={rota} />
      <div className="area-conteudo">
        <div className="area-conteudo__rolagem" key={chaveDaRota(rota)}>
        {rota.tipo === "detalhe" && <Detalhe id={rota.id} em={rota.em} key={rota.id} />}
        {rota.tipo === "revisao" && <Revisao id={rota.id} key={rota.id} />}
        {rota.tipo === "processando" && (
          <ProcessamentoReuniao id={rota.id} key={rota.id} />
        )}
        {rota.tipo === "nova" && <NovaReuniao />}
        {rota.tipo === "pessoas" && <Pessoas />}
        {rota.tipo === "perfil" && <Perfil />}
        {rota.tipo === "lista" && <Lista />}
        </div>
      </div>
      <BarraAbas rota={rota} />
      <Aviso />
    </GaleriaProvider>
  );
}

export default App;
