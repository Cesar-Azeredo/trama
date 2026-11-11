import { useEffect, useState } from "react";
import {
  excluirPessoa,
  lerParticipacao,
  type EstadoCelula,
  type Participacao,
  type PessoaComParticipacao,
  type ReuniaoDaGrade,
} from "../api/pessoas";
import { corDaVoz } from "../vozes/corDaVoz";
import { useIndiceGaleria, useRecarregarGaleria } from "../vozes/useIndiceGaleria";
import { perfilEmFormacao } from "../vozes/perfil";
import { formatarTitulo, numeroDaReuniao } from "../util/formatarReuniao";
import "./Pessoas.css";

const TEXTO_CELULA: Record<EstadoCelula | "ausente" | "sem_dados", string> = {
  confirmada: "presença confirmada",
  na_sala: "estava na sala, presença não confirmada",
  ausente: "ausente",
  sem_dados: "reunião ainda não processada",
};

/**
 * Uma celula de 24px por reuniao. Preenchida na cor da pessoa = presenca
 * confirmada na revisao (aprendendo a voz ou so nomeando - quanto foi
 * aprendido e a coluna "Voz aprendida", nao a grade); so contorno =
 * estava na sala sem confirmacao, ou num cluster ignorado; fundo
 * --superficie = ausente. Reuniao nao processada nao tem como dizer quem
 * estava la (servidor/pessoas.py) - ganha contorno tracejado neutro em vez
 * de fingir "ausente". A cor nunca e o unico portador: cada celula tem o
 * estado por escrito no nome acessivel e no title.
 */
function Celula({
  reuniao,
  estado,
  cor,
}: {
  reuniao: ReuniaoDaGrade;
  estado: EstadoCelula | undefined;
  cor: string;
}) {
  const tipo = !reuniao.processada ? "sem_dados" : (estado ?? "ausente");
  const rotulo = `${formatarTitulo(reuniao.id)}: ${TEXTO_CELULA[tipo]}`;
  const estilo =
    tipo === "confirmada"
      ? { background: cor, borderColor: cor }
      : tipo === "na_sala"
        ? { borderColor: cor }
        : undefined;
  return (
    <span
      className={`celula celula--${tipo}`}
      style={estilo}
      role="img"
      aria-label={rotulo}
      title={rotulo}
    />
  );
}

function formatarSegundos(s: number): string {
  return `${Math.round(s)} s`;
}

function ConfirmarExclusao({
  pessoa,
  excluindo,
  erro,
  aoConfirmar,
  aoCancelar,
}: {
  pessoa: PessoaComParticipacao;
  excluindo: boolean;
  erro: string | null;
  aoConfirmar: () => void;
  aoCancelar: () => void;
}) {
  return (
    <div className="confirmar-exclusao" role="alertdialog" aria-labelledby="confirmar-titulo">
      <p className="confirmar-exclusao__titulo" id="confirmar-titulo">
        Excluir a voz de {pessoa.nome}?
      </p>
      <p className="confirmar-exclusao__texto">
        Apaga o perfil de voz e tudo o que foi aprendido dela em cada
        reunião revisada ({pessoa.total_reunioes}{" "}
        {pessoa.total_reunioes === 1 ? "reunião" : "reuniões"}). Não dá para
        desfazer. As transcrições continuam com o nome de quem falou; só a voz
        sai do banco. Cópias de segurança antigas do banco (arquivos
        vozes.db.bak) não são alteradas.
      </p>
      <p className="confirmar-exclusao__texto">
        Se a voz de {pessoa.nome} for confirmada de novo numa revisão, ela
        volta a ser aprendida a partir dali.
      </p>
      <div className="confirmar-exclusao__acoes">
        <button
          type="button"
          className="confirmar-exclusao__sim"
          onClick={aoConfirmar}
          disabled={excluindo}
        >
          {excluindo ? "Excluindo…" : `Excluir a voz de ${pessoa.nome}`}
        </button>
        <button
          type="button"
          className="confirmar-exclusao__nao"
          onClick={aoCancelar}
          disabled={excluindo}
          autoFocus
        >
          Cancelar
        </button>
      </div>
      {erro && <p className="confirmar-exclusao__erro">{erro}</p>}
    </div>
  );
}

function Legenda() {
  return (
    <ul className="legenda-participacao" aria-label="Legenda">
      <li>
        <span className="celula celula--confirmada celula--legenda" aria-hidden="true" />
        presença confirmada na revisão
      </li>
      <li>
        <span className="celula celula--na_sala celula--legenda" aria-hidden="true" />
        estava na sala, não confirmada (ainda não revisada, ou cluster
        ignorado)
      </li>
      <li>
        <span className="celula celula--ausente" aria-hidden="true" />
        ausente
      </li>
      <li>
        <span className="celula celula--sem_dados" aria-hidden="true" />
        reunião ainda não processada
      </li>
    </ul>
  );
}

export function Pessoas() {
  const [dados, setDados] = useState<Participacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  const [confirmando, setConfirmando] = useState<string | null>(null);
  const [excluindo, setExcluindo] = useState(false);
  const [erroExclusao, setErroExclusao] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const indiceGaleria = useIndiceGaleria();
  const recarregarGaleria = useRecarregarGaleria();

  useEffect(() => {
    let cancelado = false;
    lerParticipacao()
      .then((d) => {
        if (!cancelado) setDados(d);
      })
      .catch((e: Error) => {
        if (!cancelado) setErro(e.message);
      });
    return () => {
      cancelado = true;
    };
  }, [versao]);

  async function excluir(nome: string) {
    setExcluindo(true);
    setErroExclusao(null);
    try {
      const r = await excluirPessoa(nome);
      setConfirmando(null);
      setAviso(
        r.removidos.compactado
          ? `A voz de ${nome} foi excluída.`
          : `A voz de ${nome} foi excluída, mas o arquivo do banco não pôde ser compactado agora - restos do perfil podem continuar no arquivo até a próxima exclusão.`,
      );
      recarregarGaleria();
      setVersao((v) => v + 1);
    } catch (e) {
      setErroExclusao((e as Error).message);
    } finally {
      setExcluindo(false);
    }
  }

  const maiorVoz = dados
    ? Math.max(1, ...dados.pessoas.map((p) => p.peso_s))
    : 1;

  return (
    <main className="tela-pessoas">
      <h1 className="tela-pessoas__titulo">Pessoas</h1>

      {aviso && (
        <p className="tela-pessoas__aviso" role="status">
          {aviso}
        </p>
      )}
      {erro && <p className="tela-pessoas__erro">{erro}</p>}
      {!erro && dados === null && (
        <p className="tela-pessoas__estado">Carregando pessoas…</p>
      )}
      {dados && dados.pessoas.length === 0 && (
        <p className="tela-pessoas__estado">
          Nenhuma voz aprendida ainda. A primeira aparece quando você
          confirmar quem é cada voz na revisão de uma reunião.
        </p>
      )}

      {dados && dados.pessoas.length > 0 && (
        <>
          <div className="tabela-pessoas__rolagem">
            <table className="tabela-pessoas" role="table">
              <thead className="tabela-pessoas__cabecalho" role="rowgroup">
                <tr role="row">
                  <th scope="col" role="columnheader" className="tabela-pessoas__th">Pessoa</th>
                  <th scope="col" role="columnheader" className="tabela-pessoas__th">Voz aprendida</th>
                  <th scope="col" role="columnheader" className="tabela-pessoas__th">
                    <span className="so-leitor-de-tela">Participação por reunião</span>
                    <span className="grade grade--cabecalho" aria-hidden="true">
                      {dados.reunioes.map((r) => (
                        <span key={r.id} className="grade__numero numeros">
                          {numeroDaReuniao(r.id)}
                        </span>
                      ))}
                    </span>
                  </th>
                  <th scope="col" role="columnheader" className="tabela-pessoas__th">Reuniões</th>
                  <th scope="col" role="columnheader" className="tabela-pessoas__th">
                    <span className="so-leitor-de-tela">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {dados.pessoas.map((p) => {
                  const cor = corDaVoz(p.nome, indiceGaleria);
                  return (
                    <tr key={p.nome} role="row" className="tabela-pessoas__linha">
                      <th scope="row" role="rowheader" className="tabela-pessoas__pessoa">
                        <span className="tabela-pessoas__nome">
                          <span
                            className="tabela-pessoas__cor"
                            style={{ background: cor }}
                            aria-hidden="true"
                          />
                          {p.nome}
                        </span>
                        {perfilEmFormacao(p.peso_s) && (
                          <span className="tabela-pessoas__formacao">
                            perfil em formação
                          </span>
                        )}
                      </th>
                      <td role="cell" className="tabela-pessoas__voz">
                        <span className="numeros">{formatarSegundos(p.peso_s)}</span>
                        <span className="barra-voz" aria-hidden="true">
                          <span
                            className="barra-voz__preenchido"
                            style={{ width: `${(p.peso_s / maiorVoz) * 100}%` }}
                          />
                        </span>
                      </td>
                      <td role="cell" className="tabela-pessoas__grade">
                        {/* Numeros da reuniao repetidos em cada bloco - so
                            aparecem no celular, onde o cabecalho da tabela
                            some (Pessoas.css). */}
                        <span className="grade grade--numeros-bloco" aria-hidden="true">
                          {dados.reunioes.map((r) => (
                            <span key={r.id} className="grade__numero numeros">
                              {numeroDaReuniao(r.id)}
                            </span>
                          ))}
                        </span>
                        <span className="grade">
                          {dados.reunioes.map((r) => (
                            <Celula
                              key={r.id}
                              reuniao={r}
                              estado={p.participacao[r.id]}
                              cor={cor}
                            />
                          ))}
                        </span>
                      </td>
                      <td role="cell" className="tabela-pessoas__reunioes">
                        <span className="numeros">{p.total_reunioes}</span>
                        {p.ultima && (
                          <>
                            {" · última "}
                            <a
                              className="tabela-pessoas__link"
                              href={`#/reuniao/${p.ultima}`}
                            >
                              {numeroDaReuniao(p.ultima)}
                            </a>
                          </>
                        )}
                      </td>
                      <td role="cell" className="tabela-pessoas__acao">
                        <button
                          type="button"
                          className="tabela-pessoas__excluir"
                          onClick={() => {
                            setAviso(null);
                            setErroExclusao(null);
                            setConfirmando(p.nome);
                          }}
                          aria-label={`Excluir a voz de ${p.nome}`}
                        >
                          Excluir
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {confirmando && dados.pessoas.some((p) => p.nome === confirmando) && (
            <ConfirmarExclusao
              pessoa={dados.pessoas.find((p) => p.nome === confirmando)!}
              excluindo={excluindo}
              erro={erroExclusao}
              aoConfirmar={() => excluir(confirmando)}
              aoCancelar={() => {
                setConfirmando(null);
                setErroExclusao(null);
              }}
            />
          )}

          <Legenda />
        </>
      )}

      <p className="tela-pessoas__explicacao">
        Não existe cadastro de voz. O perfil de cada pessoa é colhido das
        próprias reuniões, quando você confirma na revisão quem é cada voz, e
        fica mais estável a cada revisão. Uma gravação avulsa, feita em outro
        lugar e com outro aparelho, soa diferente demais da sala de reunião
        para servir de base.
      </p>
    </main>
  );
}
