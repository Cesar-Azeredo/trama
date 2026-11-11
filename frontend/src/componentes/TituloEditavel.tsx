import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { salvarTitulo, TITULO_MAX_LEN } from "../api/reunioes";
import { formatarTitulo } from "../util/formatarReuniao";
import "./TituloEditavel.css";

/**
 * Titulo da reuniao, editavel na propria linha (Detalhe). Clicar no
 * titulo (um <button> de verdade - teclado e leitor de tela chegam nele)
 * troca por um campo: Enter grava, Esc cancela, sair do campo grava
 * tambem (perder o que foi digitado por um clique fora seria pior que
 * gravar). Campo vazio volta ao padrao "Reuniao NN".
 *
 * Gravacao atomica no servidor (reunioes.gravar_titulo); se o servidor
 * recusa, o campo continua aberto com o texto e a mensagem em portugues.
 */
export function TituloEditavel({
  id,
  titulo,
  aoMudar,
}: {
  id: string;
  titulo: string | null;
  aoMudar: (titulo: string | null) => void;
}) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(titulo ?? "");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const campoRef = useRef<HTMLInputElement>(null);
  const botaoRef = useRef<HTMLButtonElement>(null);
  const cancelouRef = useRef(false);

  useEffect(() => {
    if (editando) campoRef.current?.select();
  }, [editando]);

  function abrir() {
    setTexto(titulo ?? "");
    setErro(null);
    cancelouRef.current = false;
    setEditando(true);
  }

  function fechar() {
    setEditando(false);
    setErro(null);
    // O campo some do DOM - o foco volta para o titulo, nunca cai no body.
    requestAnimationFrame(() => botaoRef.current?.focus());
  }

  async function gravar() {
    if (salvando) return;
    if (texto.trim() === (titulo ?? "")) {
      fechar();
      return;
    }
    setSalvando(true);
    setErro(null);
    try {
      aoMudar(await salvarTitulo(id, texto));
      fechar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setSalvando(false);
    }
  }

  function aoTeclar(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      gravar();
    } else if (e.key === "Escape") {
      e.preventDefault();
      // O fechar tira o campo da tela e dispara o blur - que NAO pode
      // gravar o que acabou de ser cancelado.
      cancelouRef.current = true;
      fechar();
    }
  }

  if (!editando) {
    return (
      <h1 className="titulo-editavel">
        <button
          ref={botaoRef}
          type="button"
          className="titulo-editavel__botao"
          onClick={abrir}
          title="Clique para editar o título"
        >
          {titulo || formatarTitulo(id)}
        </button>
      </h1>
    );
  }

  return (
    <div className="titulo-editavel__edicao">
      <label className="so-leitor-de-tela" htmlFor={`titulo-${id}`}>
        Título da reunião
      </label>
      <input
        ref={campoRef}
        id={`titulo-${id}`}
        className="titulo-editavel__campo"
        value={texto}
        placeholder={formatarTitulo(id)}
        maxLength={TITULO_MAX_LEN}
        disabled={salvando}
        autoFocus
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={aoTeclar}
        onBlur={() => {
          if (!cancelouRef.current) gravar();
        }}
        aria-invalid={erro ? true : undefined}
        aria-describedby={`titulo-ajuda-${id}`}
      />
      <p className="titulo-editavel__ajuda" id={`titulo-ajuda-${id}`} role={erro ? "alert" : undefined}>
        {erro ?? "Enter grava, Esc cancela. Vazio volta para o nome padrão."}
      </p>
    </div>
  );
}
