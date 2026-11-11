import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import {
  corrigirFala,
  desfazerCorrecaoFala,
  TEXTO_FALA_MAX_LEN,
  type Fala,
  type FalaAlterada,
} from "../api/reunioes";
import { useTextos } from "../i18n/textos";
import "./FalaEditavel.css";

/**
 * Texto de uma fala, corrigivel na propria linha (Detalhe, ADR 0016).
 *
 * A edicao da fala inteira abre pelo lapis no fim do texto, que aparece no
 * hover/foco da linha como o de tocar (e e o caminho pelo teclado). Clique
 * duplo NAO abre nada: e o gesto do navegador de selecionar uma palavra, e
 * a selecao e o que mostra o "Corrigir" de um trecho (Detalhe,
 * PainelCorrecao, ADR 0019). data-indice e como a selecao acha a fala.
 *
 * Igual ao titulo (TituloEditavel): Enter grava, Esc cancela, sair do
 * campo grava. Fala ja corrigida ganha "Voltar ao original" na edicao.
 * Gravacao atomica no servidor; se ele recusa, o campo continua aberto
 * com o texto e a mensagem em portugues.
 */
export function FalaEditavel({
  reuniaoId,
  indice,
  fala,
  aoMudar,
  tocando = false,
  children,
}: {
  reuniaoId: string;
  indice: number;
  fala: Fala;
  aoMudar: (alterada: FalaAlterada) => void;
  /** Fala tocando agora: fundo de Fio (.trecho-tocando, base.css). Nao vale
   *  durante a edicao - ali o campo ja e o destaque. */
  tocando?: boolean;
  /** O texto como a tela mostra (com as marcas) quando nao esta editando. */
  children: ReactNode;
}) {
  const t = useTextos().correcao;
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(fala.texto);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const campoRef = useRef<HTMLTextAreaElement>(null);
  const lapisRef = useRef<HTMLButtonElement>(null);
  const encerrandoRef = useRef(false);
  // Ref, nao so o estado: um blur logo depois do Enter ainda ve o
  // `salvando` antigo e gravaria duas vezes.
  const salvandoRef = useRef(false);

  // Altura do campo acompanha o texto - fala longa nao vira uma linha com
  // barra de rolagem.
  function ajustarAltura() {
    const campo = campoRef.current;
    if (!campo) return;
    campo.style.height = "auto";
    campo.style.height = `${campo.scrollHeight}px`;
  }

  useLayoutEffect(() => {
    if (!editando) return;
    ajustarAltura();
    const campo = campoRef.current;
    if (!campo) return;
    campo.focus();
    campo.setSelectionRange(campo.value.length, campo.value.length);
  }, [editando]);

  useEffect(() => {
    if (!editando) setTexto(fala.texto);
  }, [fala.texto, editando]);

  function abrir() {
    setTexto(fala.texto);
    setErro(null);
    encerrandoRef.current = false;
    setEditando(true);
  }

  function fechar() {
    encerrandoRef.current = true;
    setEditando(false);
    setErro(null);
    // O campo some do DOM - o foco volta para o lapis da fala, nunca cai
    // no body.
    requestAnimationFrame(() => lapisRef.current?.focus());
  }

  async function executar(acao: () => Promise<FalaAlterada>) {
    if (salvandoRef.current) return;
    salvandoRef.current = true;
    setSalvando(true);
    setErro(null);
    try {
      aoMudar(await acao());
      fechar();
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      salvandoRef.current = false;
      setSalvando(false);
    }
  }

  function gravar() {
    if (encerrandoRef.current) return;
    if (texto.trim() === fala.texto) {
      fechar();
      return;
    }
    executar(() => corrigirFala(reuniaoId, indice, texto, fala.inicio));
  }

  function voltarAoOriginal() {
    executar(() => desfazerCorrecaoFala(reuniaoId, indice, fala.inicio));
  }

  function aoTeclar(e: KeyboardEvent<HTMLTextAreaElement>) {
    // isComposing: Enter que confirma um acento/IME nao e "gravar".
    if (e.key === "Enter" && !e.nativeEvent.isComposing) {
      e.preventDefault();
      gravar();
    } else if (e.key === "Escape") {
      e.preventDefault();
      // fechar() tira o campo da tela e dispara o blur - que NAO pode
      // gravar o que acabou de ser cancelado.
      fechar();
    }
  }

  // Sair da edicao (clique fora, Tab para fora) grava - mas ir do campo
  // para o "Voltar ao original" nao e sair.
  function aoSairDoBloco(e: FocusEvent<HTMLDivElement>) {
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    gravar();
  }

  if (!editando) {
    return (
      <p
        className={"linha-fala__texto fala-editavel" + (tocando ? " trecho-tocando" : "")}
        data-indice={indice}
      >
        {children}
        <button
          ref={lapisRef}
          type="button"
          className="botao-corrigir-fala"
          onClick={abrir}
          aria-label={t.editarFala}
          title={t.tituloEditarFala}
        >
          <svg width="12" height="12" viewBox="0 0 14 14" aria-hidden="true">
            <path
              d="M9.5 1.5 L12.5 4.5 L4.5 12.5 L1.5 12.5 L1.5 9.5 Z M8 3 L11 6"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.2"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </p>
    );
  }

  const idCampo = `fala-${indice}`;
  return (
    <div className="linha-fala__texto fala-editavel__edicao" onBlur={aoSairDoBloco}>
      <label className="so-leitor-de-tela" htmlFor={idCampo}>
        {t.textoDaFala}
      </label>
      <textarea
        ref={campoRef}
        id={idCampo}
        className="fala-editavel__campo"
        value={texto}
        rows={1}
        maxLength={TEXTO_FALA_MAX_LEN}
        disabled={salvando}
        onChange={(e) => {
          setTexto(e.target.value);
          ajustarAltura();
        }}
        onKeyDown={aoTeclar}
        aria-invalid={erro ? true : undefined}
        aria-describedby={`${idCampo}-ajuda`}
      />
      <div className="fala-editavel__rodape">
        <p
          className="fala-editavel__ajuda"
          id={`${idCampo}-ajuda`}
          role={erro ? "alert" : undefined}
        >
          {erro ?? t.ajudaFala}
        </p>
        {fala.edicao_manual && (
          <button
            type="button"
            className="fala-editavel__original"
            disabled={salvando}
            // Safari no Mac nao da foco a botao clicado: sem isto o campo
            // perde o foco, o blur grava o texto e o desfazer chega tarde.
            onMouseDown={(e) => e.preventDefault()}
            onClick={voltarAoOriginal}
            title={t.textoTranscrito(fala.edicao_manual.texto_original)}
          >
            {t.voltarAoOriginal}
          </button>
        )}
      </div>
    </div>
  );
}
