import {
  useEffect,
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import {
  enviarAudio,
  iniciarProcessamento,
  EXTENSOES_AUDIO_PERMITIDAS,
  TAMANHO_MAXIMO_AUDIO_BYTES,
  NOME_MAX_LEN,
  TITULO_MAX_LEN,
  salvarTitulo,
} from "../api/reunioes";
import { listarPessoas, type Pessoa } from "../api/pessoas";
import { corDaVoz } from "../vozes/corDaVoz";
import { useIndiceGaleria } from "../vozes/useIndiceGaleria";
import { formatarTamanhoArquivo } from "../util/formatarReuniao";
import "./NovaReuniao.css";

function validarArquivo(arquivo: File): string | null {
  const nome = arquivo.name.toLowerCase();
  if (!EXTENSOES_AUDIO_PERMITIDAS.some((ext) => nome.endsWith(ext))) {
    return `Formato não aceito. Use ${EXTENSOES_AUDIO_PERMITIDAS.join(", ")}.`;
  }
  if (arquivo.size > TAMANHO_MAXIMO_AUDIO_BYTES) {
    return `Arquivo maior que o limite de ${Math.round(
      TAMANHO_MAXIMO_AUDIO_BYTES / 1024 / 1024,
    )} MB.`;
  }
  return null;
}

/** Passo numerado da tela ("01 O áudio", "02 Quem estava na
 * sala"). `extra` fica a direita do titulo (o contador de selecionadas). */
function Passo({
  numero,
  titulo,
  idTitulo,
  extra,
  children,
}: {
  numero: string;
  titulo: string;
  idTitulo: string;
  extra?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="passo" aria-labelledby={idTitulo}>
      <div className="passo__topo">
        <h2 className="passo__titulo" id={idTitulo}>
          <span className="passo__numero numeros">{numero}</span>
          {titulo}
        </h2>
        {extra}
      </div>
      {children}
    </section>
  );
}

/**
 * Area de escolha do arquivo. Nunca a estetica de "borda tracejada
 * arredondada com icone de nuvem" - resolvido com tipografia e uma regua
 * (borda superior em --linha-forte, o mesmo peso do cabecalho), como o
 * resto do app (SKILL.md: sem icone decorativo, sem gradiente, raio de
 * borda maximo 2px). O <label> inteiro e clicavel e recebe o drop; o
 * <input type="file"> real fica dentro dele, visualmente oculto mas
 * focavel - :focus-within no label mostra o foco do teclado.
 */
function AreaArquivo({
  arquivo,
  arrastando,
  aoEscolher,
  aoArrastarSobre,
  aoSairDoArrasto,
  aoSoltar,
}: {
  arquivo: File | null;
  arrastando: boolean;
  aoEscolher: (arquivo: File) => void;
  aoArrastarSobre: (e: DragEvent<HTMLLabelElement>) => void;
  aoSairDoArrasto: () => void;
  aoSoltar: (e: DragEvent<HTMLLabelElement>) => void;
}) {
  return (
    <label
      className={
        "area-arquivo" + (arrastando ? " area-arquivo--arrastando" : "")
      }
      onDragOver={aoArrastarSobre}
      onDragLeave={aoSairDoArrasto}
      onDrop={aoSoltar}
    >
      {/* Oculto mas focavel: o <label> inteiro e o alvo de clique e de
          drop; o input real precisa continuar alcancavel por teclado. */}
      <input
        type="file"
        className="so-leitor-de-tela"
        accept={EXTENSOES_AUDIO_PERMITIDAS.join(",")}
        onChange={(e) => {
          const escolhido = e.target.files?.[0];
          if (escolhido) aoEscolher(escolhido);
          e.target.value = "";
        }}
      />
      {arquivo ? (
        <div className="area-arquivo__escolhido">
          <p className="area-arquivo__nome">{arquivo.name}</p>
          <p className="area-arquivo__tamanho numeros">
            {formatarTamanhoArquivo(arquivo.size)}
          </p>
        </div>
      ) : (
        <>
          <p className="area-arquivo__instrucao">
            Arraste o áudio da reunião aqui, ou{" "}
            <span className="area-arquivo__link">escolha um arquivo</span>
          </p>
          <p className="area-arquivo__formatos numeros">
            {EXTENSOES_AUDIO_PERMITIDAS.join(" · ")} — até{" "}
            {Math.round(TAMANHO_MAXIMO_AUDIO_BYTES / 1024 / 1024)} MB
          </p>
        </>
      )}
    </label>
  );
}

/**
 * Botao de alternar de uma pessoa. aria-pressed e o estado de verdade
 * (leitor de tela anuncia "pressionado"); o visual so o espelha.
 *
 * O nome aparece duas vezes no DOM: o visivel, e uma copia invisivel em
 * 600 (::after com attr(data-nome), ver NovaReuniao.css) que reserva a
 * largura do texto em negrito. Sem isso, selecionar (400 -> 600) alarga
 * o botao e empurra todos os seguintes da linha - a fileira inteira
 * "pula" a cada toque. A cor da barrinha vem de corDaVoz; quem ainda nao
 * tem voz na galeria (pessoa nova) fica em --tinta-tenue, o mesmo tom de
 * falante nao identificado (SKILL.md).
 */
function BotaoPessoa({
  nome,
  cor,
  selecionada,
  aoAlternar,
}: {
  nome: string;
  cor: string;
  selecionada: boolean;
  aoAlternar: () => void;
}) {
  return (
    <button
      type="button"
      className={
        "botao-pessoa" + (selecionada ? " botao-pessoa--selecionada" : "")
      }
      aria-pressed={selecionada}
      onClick={aoAlternar}
    >
      <span
        className="botao-pessoa__cor"
        style={{ background: cor }}
        aria-hidden="true"
      />
      <span className="botao-pessoa__nome" data-nome={nome}>
        {nome}
      </span>
    </button>
  );
}

function SeletorPessoas({
  galeria,
  novas,
  selecionadas,
  aoAlternar,
  aoAdicionarNova,
}: {
  galeria: string[] | null;
  novas: string[];
  selecionadas: string[];
  aoAlternar: (nome: string) => void;
  aoAdicionarNova: (nome: string) => void;
}) {
  const indiceGaleria = useIndiceGaleria();
  const [digitando, setDigitando] = useState(false);
  const [entrada, setEntrada] = useState("");
  const botaoNovaRef = useRef<HTMLButtonElement>(null);

  function fecharCampo() {
    setDigitando(false);
    setEntrada("");
    // O campo some do DOM - sem devolver o foco, ele cairia no <body> e
    // quem usa teclado perderia o lugar.
    requestAnimationFrame(() => botaoNovaRef.current?.focus());
  }

  function adicionar() {
    const nome = entrada.trim();
    if (!nome) return;
    aoAdicionarNova(nome);
    fecharCampo();
  }

  function aoTeclar(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      adicionar();
    } else if (e.key === "Escape") {
      e.preventDefault();
      fecharCampo();
    }
  }

  return (
    <>
      <p className="seletor-pessoas__explicacao">
        É o maior ganho de precisão que existe: fixa quantos falantes
        procurar e restringe a comparação a quem estava lá. Sem marcar
        ninguém, o pipeline funciona igual, só que pior.
      </p>
      {galeria === null && (
        <p className="seletor-pessoas__estado">Carregando pessoas…</p>
      )}
      <div className="seletor-pessoas">
        {(galeria ?? []).map((nome) => (
          <BotaoPessoa
            key={nome}
            nome={nome}
            cor={corDaVoz(nome, indiceGaleria)}
            selecionada={selecionadas.includes(nome)}
            aoAlternar={() => aoAlternar(nome)}
          />
        ))}
        {novas.map((nome) => (
          <BotaoPessoa
            key={nome}
            nome={nome}
            cor="var(--tinta-tenue)"
            selecionada={selecionadas.includes(nome)}
            aoAlternar={() => aoAlternar(nome)}
          />
        ))}
        {!digitando && (
          <button
            ref={botaoNovaRef}
            type="button"
            className="botao-pessoa botao-pessoa--nova"
            onClick={() => setDigitando(true)}
          >
            + Pessoa nova
          </button>
        )}
      </div>
      {digitando && (
        <div className="seletor-pessoas__nova">
          <label className="seletor-pessoas__rotulo-nova" htmlFor="nova-pessoa">
            Nome da pessoa nova
          </label>
          <div className="seletor-pessoas__linha">
            <input
              id="nova-pessoa"
              type="text"
              className="seletor-pessoas__input"
              value={entrada}
              onChange={(e) => setEntrada(e.target.value)}
              onKeyDown={aoTeclar}
              maxLength={NOME_MAX_LEN}
              autoFocus
            />
            <button
              type="button"
              className="seletor-pessoas__botao"
              onClick={adicionar}
              disabled={!entrada.trim()}
            >
              Adicionar
            </button>
            <button
              type="button"
              className="seletor-pessoas__botao seletor-pessoas__botao--discreto"
              onClick={fecharCampo}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function textoSelecionadas(n: number): string {
  if (n === 0) return "nenhuma selecionada";
  return n === 1 ? "1 selecionada" : `${n} selecionadas`;
}

// ---- tela ------------------------------------------------------------------

export function NovaReuniao() {
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [erroArquivo, setErroArquivo] = useState<string | null>(null);
  const [arrastando, setArrastando] = useState(false);
  const [pessoasGaleria, setPessoasGaleria] = useState<Pessoa[] | null>(null);
  const [novas, setNovas] = useState<string[]>([]);
  const [selecionadas, setSelecionadas] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);
  const [progresso, setProgresso] = useState(0);
  const [erroEnvio, setErroEnvio] = useState<string | null>(null);
  const [titulo, setTitulo] = useState("");

  useEffect(() => {
    let cancelado = false;
    listarPessoas()
      .then((lista) => {
        if (!cancelado) setPessoasGaleria(lista);
      })
      .catch(() => {
        // Sem galeria, ainda da para marcar gente pelo "+ Pessoa nova" -
        // a tela nao trava por isso.
        if (!cancelado) setPessoasGaleria([]);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const galeria =
    pessoasGaleria === null
      ? null
      : pessoasGaleria
          .map((p) => p.nome)
          .sort((a, b) => a.localeCompare(b, "pt-BR"));

  function escolherArquivo(novoArquivo: File) {
    const erro = validarArquivo(novoArquivo);
    if (erro) {
      setErroArquivo(erro);
      setArquivo(null);
      return;
    }
    setErroArquivo(null);
    setArquivo(novoArquivo);
  }

  function alternar(nome: string) {
    setSelecionadas((atual) =>
      atual.includes(nome) ? atual.filter((n) => n !== nome) : [...atual, nome],
    );
  }

  /** Nome que ja existe (na galeria ou entre as novas, sem diferenciar
   * maiuscula) seleciona o existente - nunca dois botoes pra mesma pessoa
   * so porque alguem digitou "celso" em vez de "Celso". */
  function adicionarNova(nome: string) {
    const existente = [...(galeria ?? []), ...novas].find(
      (n) => n.toLowerCase() === nome.toLowerCase(),
    );
    const alvo = existente ?? nome;
    if (!existente) setNovas((atual) => [...atual, nome]);
    setSelecionadas((atual) => (atual.includes(alvo) ? atual : [...atual, alvo]));
  }

  async function transcrever() {
    if (!arquivo) return;
    // Mesma regra do servidor (reunioes.validar_titulo), conferida ANTES de
    // subir o audio - para nao descobrir o problema depois de 500 MB.
    if (/[\x00-\x1f\x7f]/.test(titulo)) {
      setErroEnvio("O título tem um caractere de controle (quebra de linha, tabulação...), que não é permitido.");
      return;
    }
    setEnviando(true);
    setErroEnvio(null);
    setProgresso(0);

    let criado;
    try {
      criado = await enviarAudio(arquivo, setProgresso);
    } catch (e) {
      setErroEnvio((e as Error).message);
      setEnviando(false);
      return;
    }

    if (titulo.trim()) {
      try {
        await salvarTitulo(criado.id, titulo);
      } catch (e) {
        // O audio ja subiu: a reuniao existe, na fila. Nunca fingir que o
        // titulo foi salvo, nem processar como se tivesse sido.
        setErroEnvio(
          `O áudio foi enviado, mas o título não foi salvo: ${(e as Error).message} ` +
            "A reunião ficou na fila, sem processar - dá para dar o título no detalhe dela.",
        );
        setEnviando(false);
        return;
      }
    }

    try {
      await iniciarProcessamento(criado.id, selecionadas);
      window.location.hash = `#/reuniao/${criado.id}/processando`;
    } catch {
      // O audio foi salvo mesmo que o processamento nao tenha comecado
      // agora (ex.: outra reuniao ja processando) - segue para o
      // Detalhe, que mostra o estado real em vez de fingir sucesso.
      window.location.hash = `#/reuniao/${criado.id}`;
    }
  }

  return (
    <main className="tela-nova">
      <h1 className="tela-nova__titulo">Nova reunião</h1>

      <div className="tela-nova__passos">
      <Passo numero="01" titulo="O áudio" idTitulo="passo-audio">
        <AreaArquivo
          arquivo={arquivo}
          arrastando={arrastando}
          aoEscolher={escolherArquivo}
          aoArrastarSobre={(e) => {
            e.preventDefault();
            setArrastando(true);
          }}
          aoSairDoArrasto={() => setArrastando(false)}
          aoSoltar={(e) => {
            e.preventDefault();
            setArrastando(false);
            const solto = e.dataTransfer.files?.[0];
            if (solto) escolherArquivo(solto);
          }}
        />
        {erroArquivo && <p className="tela-nova__erro">{erroArquivo}</p>}
        {arquivo && !enviando && (
          <button
            type="button"
            className="tela-nova__trocar"
            onClick={() => setArquivo(null)}
          >
            Trocar arquivo
          </button>
        )}
      </Passo>

      <Passo
        numero="02"
        titulo="Quem estava na sala"
        idTitulo="passo-pessoas"
        extra={
          <span className="passo__contador" aria-live="polite">
            {textoSelecionadas(selecionadas.length)}
          </span>
        }
      >
        <SeletorPessoas
          galeria={galeria}
          novas={novas}
          selecionadas={selecionadas}
          aoAlternar={alternar}
          aoAdicionarNova={adicionarNova}
        />
      </Passo>
      </div>

      {enviando && (
        <div className="barra-envio-bloco">
          <div
            className="barra-envio"
            role="progressbar"
            aria-valuenow={Math.round(progresso * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Progresso do envio"
          >
            <div
              className="barra-envio__preenchido"
              style={{ width: `${progresso * 100}%` }}
            />
          </div>
          <span className="barra-envio__valor numeros">
            {Math.round(progresso * 100)}%
          </span>
        </div>
      )}

      <div className="tela-nova__campo-titulo">
        <label className="tela-nova__rotulo-titulo" htmlFor="nova-titulo">
          Título <span className="tela-nova__opcional">(opcional)</span>
        </label>
        <input
          id="nova-titulo"
          className="tela-nova__input-titulo"
          value={titulo}
          maxLength={TITULO_MAX_LEN}
          disabled={enviando}
          placeholder="Ex.: Comitê de produto"
          onChange={(e) => setTitulo(e.target.value)}
        />
        <p className="tela-nova__ajuda-titulo">
          Sem título, a reunião fica com o nome padrão: “Reunião” e o
          número dela. Dá para mudar depois, no detalhe.
        </p>
      </div>

      <div className="tela-nova__rodape">
        <button
          type="button"
          className="botao-transcrever"
          disabled={!arquivo || enviando}
          onClick={transcrever}
        >
          {enviando ? "Enviando…" : "Transcrever"}
        </button>
        <span className="tela-nova__rodape-nota">
          Cerca de 6 minutos por hora de áudio. Nada sai desta máquina.
        </span>
      </div>
      {erroEnvio && <p className="tela-nova__erro">{erroEnvio}</p>}
    </main>
  );
}
