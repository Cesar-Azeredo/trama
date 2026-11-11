import type { ReactNode } from "react";
import { secaoDaRota, type Rota, type Secao } from "../tema/useRota";
import { useTextos } from "../i18n/textos";
import { Marca } from "./Marca";
import "./Cabecalho.css";

/**
 * Item de nav de secao (SKILL.md, Composicao: "navegacao de secao e
 * texto, nunca aba com fundo"). Estado atual por peso + regua de 2px
 * embaixo - nunca pilula nem fundo colorido (regra 2 da identidade).
 */
function ItemNav({
  href,
  secao,
  atual,
  children,
}: {
  href: string;
  secao: Secao;
  atual: Secao;
  children: ReactNode;
}) {
  const ativo = secao === atual;
  return (
    <a
      className={
        "cabecalho__item" + (ativo ? " cabecalho__item--ativo" : "")
      }
      href={href}
      aria-current={ativo ? "page" : undefined}
    >
      {children}
    </a>
  );
}

/**
 * Casca do aplicativo (nao mais uma tela chamando outra): App.tsx
 * renderiza isto UMA VEZ, fora do roteamento - cada tela devolve so
 * conteudo. O cabecalho/nav e sempre 100% da largura da janela (antes
 * vinha capado em 640px, a mesma medida do transcript).
 *
 * Tres secoes, nesta ordem: Nova reuniao (a tela inicial, #/),
 * Reunioes, Pessoas. A direita, Perfil - que tambem guarda as
 * Configuracoes (Aparencia, Glossario, Processamento, Dados, Sobre). O
 * botao de tema saiu daqui: o tema e escolhido em Perfil > Aparencia
 * (SKILL.md, "Escolha do modo"). Ver secaoDaRota em tema/useRota.ts
 * para como cada rota mapeia pra uma secao.
 */
export function Cabecalho({ rota }: { rota: Rota }) {
  const secao = secaoDaRota(rota);
  const t = useTextos().comum;

  return (
    <header className="cabecalho">
      <div className="cabecalho__esquerda">
        <a className="cabecalho__marca" href="#/">
          <Marca />
        </a>
        <nav className="cabecalho__nav" aria-label={t.secoes}>
          <ItemNav href="#/" secao="nova" atual={secao}>
            {t.novaReuniao}
          </ItemNav>
          <ItemNav href="#/reunioes" secao="reunioes" atual={secao}>
            {t.reunioes}
          </ItemNav>
          <ItemNav href="#/pessoas" secao="pessoas" atual={secao}>
            {t.pessoas}
          </ItemNav>
        </nav>
      </div>
      <div className="cabecalho__direita">
        <ItemNav href="#/perfil" secao="perfil" atual={secao}>
          {t.perfil}
        </ItemNav>
      </div>
    </header>
  );
}
