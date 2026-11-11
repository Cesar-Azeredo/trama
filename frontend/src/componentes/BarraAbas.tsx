import type { ReactNode } from "react";
import { secaoDaRota, type Rota, type Secao } from "../tema/useRota";
import { useTextos } from "../i18n/textos";
import "./BarraAbas.css";

/**
 * Barra de abas do celular (abaixo de 720px - ver BarraAbas.css). No
 * desktop ela nem aparece: a nav de texto do cabecalho continua sendo a
 * navegacao. As duas nunca estao visiveis ao mesmo tempo.
 *
 * Icone de traco + rotulo (ADR 0014): numa barra de quatro celulas
 * estreitas, o icone e o que da pra reconhecer de relance sem ler - e
 * funcional, nao decorativo. O rotulo continua escrito embaixo (cor e
 * forma nunca sao o unico portador de significado), e e ele o nome
 * acessivel do link; o SVG e aria-hidden.
 */

function Icone({ children }: { children: ReactNode }) {
  return (
    <svg
      className="barra-abas__icone"
      width="22"
      height="22"
      viewBox="0 0 22 22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

type ChaveDaAba = "novaCurta" | "reunioes" | "pessoas" | "perfil";

const ABAS: { secao: Secao; href: string; rotulo: ChaveDaAba; icone: ReactNode }[] = [
  {
    secao: "nova",
    href: "#/",
    rotulo: "novaCurta",
    icone: (
      <Icone>
        <circle cx="11" cy="11" r="8" />
        <path d="M11 7.5v7M7.5 11h7" />
      </Icone>
    ),
  },
  {
    secao: "reunioes",
    href: "#/reunioes",
    rotulo: "reunioes",
    icone: (
      <Icone>
        <path d="M8 6h10M8 11h10M8 16h10" />
        <path d="M4 6h.01M4 11h.01M4 16h.01" strokeWidth="2.2" />
      </Icone>
    ),
  },
  {
    secao: "pessoas",
    href: "#/pessoas",
    rotulo: "pessoas",
    icone: (
      <Icone>
        <circle cx="8" cy="8" r="3" />
        <path d="M2.5 18c.6-3 2.8-4.8 5.5-4.8s4.9 1.8 5.5 4.8" />
        <circle cx="15.5" cy="7.5" r="2.5" />
        <path d="M15 12.8c2.3.1 4 1.6 4.5 4.2" />
      </Icone>
    ),
  },
  {
    secao: "perfil",
    href: "#/perfil",
    rotulo: "perfil",
    icone: (
      <Icone>
        <circle cx="11" cy="11" r="8.5" />
        <circle cx="11" cy="9" r="2.8" />
        <path d="M5.6 17.1c1.2-2 3.1-3.1 5.4-3.1s4.2 1.1 5.4 3.1" />
      </Icone>
    ),
  },
];

export function BarraAbas({ rota }: { rota: Rota }) {
  const atual = secaoDaRota(rota);
  const t = useTextos().comum;
  return (
    <nav className="barra-abas" aria-label={t.secoes}>
      {ABAS.map((aba) => {
        const ativa = aba.secao === atual;
        return (
          <a
            key={aba.secao}
            href={aba.href}
            className={"barra-abas__aba" + (ativa ? " barra-abas__aba--ativa" : "")}
            aria-current={ativa ? "page" : undefined}
          >
            {aba.icone}
            <span className="barra-abas__rotulo">{t[aba.rotulo]}</span>
          </a>
        );
      })}
    </nav>
  );
}
