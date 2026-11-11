import { useEffect, useState, type ReactNode } from "react";
import { listarPessoas } from "../api/pessoas";
import { lerSistema, type Licenca, type Sistema } from "../api/sistema";
import { NOME_MAX_LEN } from "../api/reunioes";
import { salvarPerfil, usePerfilLocal } from "../perfil/perfilLocal";
import {
  definirPreferenciaTema,
  usePreferenciaTema,
  type PreferenciaTema,
} from "../tema/useTema";
import { TermosDaEmpresa } from "./perfil/TermosDaEmpresa";
import { definirIdioma, IDIOMAS, NOME_DO_IDIOMA, useIdioma } from "../i18n/idioma";
import { useTextos } from "../i18n/textos";
import "./Perfil.css";

function Secao({
  id,
  rotulo,
  classe,
  children,
}: {
  id: string;
  rotulo: string;
  classe?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={"perfil__secao" + (classe ? ` ${classe}` : "")}
      aria-labelledby={id}
    >
      <h3 className="perfil__rotulo" id={id}>
        {rotulo}
      </h3>
      {children}
    </section>
  );
}

/** Quem usa o app nesta maquina. Salva a cada mudanca - e local, nao ha
 * "enviar" (perfil/perfilLocal.ts). */
function Voce() {
  const perfil = usePerfilLocal();
  const t = useTextos().perfil;
  const [galeria, setGaleria] = useState<string[] | null>(null);

  useEffect(() => {
    let cancelado = false;
    listarPessoas()
      .then((lista) => {
        if (!cancelado)
          setGaleria(
            lista.map((p) => p.nome).sort((a, b) => a.localeCompare(b, "pt-BR")),
          );
      })
      .catch(() => {
        if (!cancelado) setGaleria([]);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  // Pessoa escolhida antes e depois excluida da galeria continua visivel
  // como opcao - sumir com a escolha em silencio mentiria sobre o que esta
  // salvo.
  const opcoes =
    galeria && perfil.pessoa && !galeria.includes(perfil.pessoa)
      ? [...galeria, perfil.pessoa]
      : (galeria ?? []);

  return (
    <div className="perfil__campos">
      <div className="perfil__campo">
        <label className="perfil__rotulo-campo" htmlFor="perfil-nome">
          {t.seuNome}
        </label>
        <input
          id="perfil-nome"
          className="perfil__input"
          value={perfil.nome}
          maxLength={NOME_MAX_LEN}
          onChange={(e) => salvarPerfil({ ...perfil, nome: e.target.value })}
        />
      </div>
      <div className="perfil__campo">
        <label className="perfil__rotulo-campo" htmlFor="perfil-pessoa">
          {t.voceNaGaleria}
        </label>
        <select
          id="perfil-pessoa"
          className="perfil__input"
          value={perfil.pessoa ?? ""}
          disabled={galeria === null}
          onChange={(e) =>
            salvarPerfil({ ...perfil, pessoa: e.target.value || null })
          }
        >
          <option value="">{t.nenhuma}</option>
          {opcoes.map((nome) => (
            <option key={nome} value={nome}>
              {galeria?.includes(nome) ? nome : t.foraDaGaleria(nome)}
            </option>
          ))}
        </select>
      </div>
      <p className="perfil__nota">{t.notaLocal}</p>
    </div>
  );
}

/** O rotulo de cada opcao vem do catalogo (perfil.tema), no render. */
const OPCOES_TEMA: PreferenciaTema[] = ["sistema", "claro", "escuro"];

/**
 * Radio nativo (a semantica de "um de tres" e do navegador e do teclado:
 * setas trocam a opcao), com o input visualmente oculto e o <label> no
 * mesmo visual de botao de alternar da Nova reuniao.
 *
 * O grupo NAO tem <legend>: o nome dele para leitor de tela vem do titulo
 * da secao ("Aparência", h3 id=perfil-aparencia) por aria-labelledby. Um
 * <legend> "visualmente oculto" apareceu na tela, duplicando o titulo - o
 * legend tem renderizacao especial dentro do fieldset e nao da para
 * confiar que o recorte de "so para leitor de tela" vale nele em todo
 * navegador. Sem segundo texto, nao ha o que duplicar.
 */
function Aparencia() {
  const preferencia = usePreferenciaTema();
  const t = useTextos().perfil;
  return (
    <div className="perfil__opcoes" role="radiogroup" aria-labelledby="perfil-aparencia">
      {OPCOES_TEMA.map((valor) => (
        <label
          key={valor}
          className={
            "perfil__opcao" +
            (preferencia === valor ? " perfil__opcao--selecionada" : "")
          }
        >
          <input
            type="radio"
            name="tema"
            className="so-leitor-de-tela"
            value={valor}
            checked={preferencia === valor}
            onChange={() => definirPreferenciaTema(valor)}
          />
          <span className="perfil__opcao-texto" data-texto={t.tema[valor]}>
            {t.tema[valor]}
          </span>
        </label>
      ))}
    </div>
  );
}

/**
 * Idioma da interface (i18n/idioma.ts): mesmo grupo de opcoes da Aparencia.
 * O nome de cada idioma aparece nele mesmo ("English" tambem na interface
 * em portugues) - e o que a pessoa procura quando nao entende a tela.
 */
function Idioma() {
  const atual = useIdioma();
  return (
    <div className="perfil__opcoes" role="radiogroup" aria-labelledby="perfil-idioma">
      {IDIOMAS.map((idioma) => (
        <label
          key={idioma}
          lang={idioma === "pt" ? "pt-BR" : "en"}
          className={"perfil__opcao" + (atual === idioma ? " perfil__opcao--selecionada" : "")}
        >
          <input
            type="radio"
            name="idioma"
            className="so-leitor-de-tela"
            value={idioma}
            checked={atual === idioma}
            onChange={() => definirIdioma(idioma)}
          />
          <span className="perfil__opcao-texto" data-texto={NOME_DO_IDIOMA[idioma]}>
            {NOME_DO_IDIOMA[idioma]}
          </span>
        </label>
      ))}
    </div>
  );
}

const NOME_DEVICE: Record<string, string> = {
  mps: "Apple Silicon (MPS)",
  cpu: "CPU",
};
const NOME_ASR: Record<string, string> = {
  mlx: "mlx-whisper",
  faster: "faster-whisper",
};

function Linha({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <>
      <dt className="perfil__dt">{rotulo}</dt>
      <dd className="perfil__dd">{children}</dd>
    </>
  );
}

/** "Licenca"/"Fonte" como o ATRIBUICAO.md escreve (sem acento) - o
 * rotulo exibido e o nosso, com acento; so o valor vem do arquivo. */
function itemDaLicenca(licenca: Licenca, rotulo: string): string | null {
  return (
    licenca.itens.find((i) => i.rotulo.toLowerCase() === rotulo)?.texto ?? null
  );
}

function useSistema(): { dados: Sistema | null; erro: string | null } {
  const [dados, setDados] = useState<Sistema | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => {
    let cancelado = false;
    lerSistema()
      .then((d) => {
        if (!cancelado) setDados(d);
      })
      .catch((e: Error) => {
        if (!cancelado) setErro(e.message);
      });
    return () => {
      cancelado = true;
    };
  }, []);
  return { dados, erro };
}

export function Perfil() {
  const { dados: sistema, erro: erroSistema } = useSistema();
  const textos = useTextos();
  const t = textos.perfil;

  const carregandoSistema = !sistema && !erroSistema && (
    <p className="perfil__vazio">{t.carregando}</p>
  );
  const falhaSistema = erroSistema && <p className="perfil__erro">{erroSistema}</p>;

  return (
    <main className="tela-perfil">
      <h1 className="tela-perfil__titulo">{textos.comum.perfil}</h1>

      <Secao id="perfil-voce" rotulo={t.voce}>
        <Voce />
      </Secao>

      <h2 className="tela-perfil__subtitulo">{t.configuracoes}</h2>

      {/* Mesma ordem do DOM em qualquer largura; acima de 1440px o
          Termos da empresa (a secao longa) ocupa a coluna da direita inteira e as
          outras quatro empilham na esquerda (Perfil.css, ADR 0015). */}
      <div className="perfil__configuracoes">
      <Secao id="perfil-aparencia" rotulo={t.aparencia}>
        <Aparencia />
      </Secao>

      <Secao id="perfil-idioma" rotulo={t.idioma}>
        <Idioma />
        <p className="perfil__nota">{t.idiomaNota}</p>
      </Secao>

      <Secao id="perfil-termos" rotulo={t.termosDaEmpresa} classe="perfil__secao--glossario">
        <TermosDaEmpresa />
      </Secao>

      <Secao id="perfil-processamento" rotulo={t.processamento}>
        {carregandoSistema}
        {falhaSistema}
        {sistema && (
          <>
            <dl className="perfil__dl">
              <Linha rotulo={t.dispositivo}>
                {NOME_DEVICE[sistema.device] ?? sistema.device}
              </Linha>
              <Linha rotulo={t.motorDeTranscricao}>
                {NOME_ASR[sistema.asr] ?? sistema.asr}
              </Linha>
            </dl>
            <p className="perfil__nota">{t.notaProcessamento}</p>
          </>
        )}
      </Secao>

      <Secao id="perfil-dados" rotulo={t.dadosEPrivacidade}>
        {carregandoSistema}
        {falhaSistema}
        {sistema && (
          <dl className="perfil__dl">
            <Linha rotulo={t.audiosETranscricoes}>
              <span className="perfil__caminho numeros">{sistema.pasta_audios}</span>
            </Linha>
            <Linha rotulo={t.bancoDeVozes}>
              <span className="perfil__caminho numeros">{sistema.banco_vozes}</span>
            </Linha>
          </dl>
        )}
        <p className="perfil__texto">{t.notaPrivacidade}</p>
      </Secao>

      <Secao id="perfil-sobre" rotulo={t.sobre}>
        {carregandoSistema}
        {falhaSistema}
        {sistema && (
          <>
            <p className="perfil__texto">
              Trama <span className="numeros">{sistema.versao}</span>
            </p>
            <p className="perfil__texto">{t.notaAtribuicoes}</p>
            <ul className="perfil__licencas">
              {sistema.licencas.map((l) => {
                const licenca = itemDaLicenca(l, "licenca");
                const fonte = itemDaLicenca(l, "fonte");
                return (
                  <li key={l.nome} className="perfil__licenca">
                    <span className="perfil__licenca-nome">{l.nome}</span>
                    {licenca && (
                      <span className="perfil__licenca-texto">{licenca}</span>
                    )}
                    {fonte && (
                      <span className="perfil__caminho numeros">{fonte}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </Secao>
      </div>
    </main>
  );
}
