import { mensagemDe, textoDoAviso } from "../../api/cliente";
import { mensagem, useMensagem, type Mensagem } from "../../i18n/mensagem";
import { tituloDaReuniao } from "../../util/formatarReuniao";
import { useEffect, useId, useRef, useState } from "react";
import {
  aplicarCorrecao,
  previaCorrecao,
  type PreviaCorrecao,
} from "../../api/correcoes";
import {
  adicionarTermo,
  DESCRICAO_MAX_LEN,
  definirDescricao,
  lerTermosDaEmpresa,
  removerTermo,
  removerVariacao,
  TERMO_MAX_LEN,
  type TermoDaEmpresa,
} from "../../api/termos";
import { useTextos } from "../../i18n/textos";
import { numero } from "../../util/numeros";
import { ReaplicarNasReunioes } from "./ReaplicarNasReunioes";
import { Seta } from "../../componentes/Seta";

/** A mesma comparacao do servidor (glossario._chave_variacao): sem acento,
 * sem maiuscula e com o espacamento normalizado - "Chat  apt" e "chat APT"
 * sao a mesma variacao. */
function chaveDaVariacao(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

/**
 * "Adicionar variação": a mesma correção "em todas as reuniões e nas
 * próximas" do Detalhe (ADR 0019), pelo teclado - conferir antes onde
 * troca, e so entao corrigir.
 */
function AdicionarVariacao({
  termo,
  variacoes,
  aoTerminar,
}: {
  termo: string;
  variacoes: { errado: string }[];
  aoTerminar: (mensagem: Mensagem | null) => void;
}) {
  const [errado, setErrado] = useState("");
  const [previa, setPrevia] = useState<PreviaCorrecao | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<Mensagem | null>(null);
  const id = useId();
  const t = useTextos().termos;
  const textoDe = useMensagem();
  // A mesma variacao duas vezes no mesmo termo nunca entra - o servidor
  // tambem recusa; aqui so evita a ida e explica antes.
  const repetida = errado.trim()
    ? variacoes.find((v) => chaveDaVariacao(v.errado) === chaveDaVariacao(errado))
    : undefined;

  async function conferir() {
    if (repetida) return;
    setOcupado(true);
    setErro(null);
    try {
      setPrevia(await previaCorrecao(errado, termo));
    } catch (e) {
      setErro(mensagemDe(e));
    } finally {
      setOcupado(false);
    }
  }

  async function corrigir() {
    if (!previa) return;
    setOcupado(true);
    setErro(null);
    try {
      const r = await aplicarCorrecao({
        trecho: previa.trecho,
        certo: termo,
        descricao: "",
        assinatura: previa.assinatura,
      });
      // codigo + parametros, resolvido no render: muda com o idioma
      const { trecho } = previa;
      const aviso = r.aviso;
      aoTerminar(
        mensagem(
          (c) =>
            (r.total > 0
              ? c.termos.corrigidoEm(trecho, r.total)
              : c.termos.seraCorrigidoNasProximas(trecho)) +
            (aviso ? ` ${textoDoAviso(aviso, c) ?? ""}` : ""),
        ),
      );
    } catch (e) {
      setErro(mensagemDe(e));
      setPrevia(null);
    } finally {
      setOcupado(false);
    }
  }

  const aparece = previa ? t.apareceVezesEmReunioes(previa.total, previa.reunioes.length) : null;

  return (
    <form
      className="termos__variacao-nova"
      onSubmit={(e) => {
        e.preventDefault();
        if (repetida) return;
        if (previa) corrigir();
        else conferir();
      }}
    >
      <label className="perfil__rotulo-campo" htmlFor={`${id}-errado`}>
        {t.comoApareceErrado}
      </label>
      <input
        id={`${id}-errado`}
        className="perfil__input"
        value={errado}
        maxLength={TERMO_MAX_LEN}
        autoFocus
        onChange={(e) => {
          setErrado(e.target.value);
          setPrevia(null);
        }}
      />
      {repetida && (
        <p className="perfil__nota" role="status">
          {t.jaEVariacao(repetida.errado, termo)}
        </p>
      )}
      {previa && !repetida && (
        <div className="termos__previa" aria-live="polite">
          {previa.total === 0 ? (
            <p className="perfil__nota">{t.naoApareceEmNenhuma}</p>
          ) : (
            <details>
              <summary>
                {aparece?.[0]}
                <span className="numeros">{numero(previa.total)}</span>
                {aparece?.[1]}
                <span className="numeros">{numero(previa.reunioes.length)}</span>
                {aparece?.[2]}
              </summary>
              <ul>
                {previa.reunioes.flatMap((r) =>
                  r.ocorrencias.map((o, k) => (
                    <li key={`${r.id}-${k}`}>
                      <span className="termos__reuniao">{tituloDaReuniao(r.id, r.titulo)}</span> …
                      {o.antes}
                      <strong>{o.trecho}</strong>
                      {o.depois}…
                    </li>
                  )),
                )}
              </ul>
            </details>
          )}
          {previa.aviso ? <p className="perfil__nota">{textoDoAviso(previa.aviso)}</p> : null}
        </div>
      )}
      {erro && (
        <p className="perfil__status perfil__status--erro" role="alert">
          {textoDe(erro)}
        </p>
      )}
      <div className="perfil__acoes perfil__acoes--sem-regua">
        <button
          type="submit"
          className="perfil__botao-primario"
          disabled={ocupado || !errado.trim() || !!repetida}
        >
          {ocupado
            ? t.conferindo
            : !previa
              ? t.conferir
              : previa.total === 0
                ? t.adicionar
                : t.corrigirEm(previa.total)}
        </button>
        <button type="button" className="perfil__botao-discreto" onClick={() => aoTerminar(null)}>
          {t.cancelar}
        </button>
      </div>
    </form>
  );
}

function DescricaoDoTermo({
  termo,
  descricao,
  aoGravar,
}: {
  termo: string;
  descricao: string;
  aoGravar: () => void;
}) {
  const [valor, setValor] = useState(descricao);
  const [estado, setEstado] = useState<Mensagem | null>(null);
  const textoDe = useMensagem();
  // Sem descricao, o campo so existe depois do clique no link: um campo
  // aberto embaixo de cada termo parecia o app perguntando o que e cada
  // um, e confundia com a correcao de texto, que e o que importa.
  const [aberto, setAberto] = useState(descricao !== "");
  // Escape fechou o campo: o foco volta ao link, de onde a pessoa veio
  // (ref de callback - o link so existe depois do render que fecha).
  const focarLink = useRef(false);
  // Escape fecha o campo; se o navegador disparar blur no campo que sai
  // da tela, ele nao pode gravar o texto que acabou de ser desfeito.
  const cancelado = useRef(false);
  const id = useId();
  const t = useTextos().termos;

  async function gravar() {
    if (cancelado.current) {
      cancelado.current = false;
      return;
    }
    if (valor.trim() === descricao) {
      // Abriu e saiu sem escrever nada: volta a ser so o link.
      if (!descricao) setAberto(false);
      return;
    }
    setEstado(mensagem((c) => c.termos.salvando));
    try {
      await definirDescricao(termo, valor);
      setEstado(mensagem((c) => c.termos.salvo));
      aoGravar();
    } catch (e) {
      setEstado(mensagemDe(e));
    }
  }

  if (!aberto) {
    return (
      <button
        ref={(el) => {
          if (el && focarLink.current) {
            focarLink.current = false;
            el.focus();
          }
        }}
        type="button"
        className="termos__adicionar-descricao"
        onClick={() => {
          cancelado.current = false;
          setAberto(true);
        }}
        aria-label={t.adicionarDescricaoDe(termo)}
      >
        {t.adicionarDescricao}
      </button>
    );
  }

  return (
    <div className="termos__descricao">
      <label className="so-leitor-de-tela" htmlFor={id}>
        {t.descricaoDe(termo)}
      </label>
      <input
        id={id}
        className="glossario__campo termos__campo-descricao"
        value={valor}
        maxLength={DESCRICAO_MAX_LEN}
        // So quando abriu pelo link (termo sem descricao): com descricao,
        // o campo ja mostra o texto e nao rouba o foco ao carregar.
        autoFocus={descricao === ""}
        placeholder={t.descricaoExemplo}
        onChange={(e) => {
          setValor(e.target.value);
          setEstado(null);
        }}
        onBlur={gravar}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            gravar();
          } else if (e.key === "Escape") {
            // Desfaz o que foi digitado; sem descricao gravada, fecha e
            // devolve o foco ao link, de onde a pessoa veio.
            e.preventDefault();
            setValor(descricao);
            setEstado(null);
            if (!descricao) {
              cancelado.current = true;
              focarLink.current = true;
              setAberto(false);
            }
          }
        }}
      />
      {estado && (
        <span className="perfil__status" role="status">
          {textoDe(estado)}
        </span>
      )}
    </div>
  );
}

/**
 * Termos da empresa (ADR 0021): o termos.txt visto por termo - o nome
 * certo, o que ele e, e as formas erradas ja corrigidas. Cada mudanca
 * grava na hora; nunca fala em "regra". O que ja foi corrigido nas
 * reunioes continua como esta ao remover.
 */
export function TermosDaEmpresa() {
  const [termos, setTermos] = useState<TermoDaEmpresa[] | null>(null);
  const [erroCarga, setErroCarga] = useState<Mensagem | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "erro"; mensagem: Mensagem } | null>(null);
  const textoDe = useMensagem();
  const [variacaoAberta, setVariacaoAberta] = useState<string | null>(null);
  const [novoTermo, setNovoTermo] = useState("");
  const [novaDescricao, setNovaDescricao] = useState("");
  const [adicionando, setAdicionando] = useState(false);
  const id = useId();
  const tx = useTextos().termos;

  function recarregar() {
    lerTermosDaEmpresa()
      .then(setTermos)
      .catch((e: unknown) => setErroCarga(mensagemDe(e)));
  }

  useEffect(recarregar, []);

  async function executar(acao: () => Promise<TermoDaEmpresa[]>, ok: Mensagem) {
    setAviso(null);
    try {
      setTermos(await acao());
      setAviso({ tipo: "ok", mensagem: ok });
    } catch (e) {
      setAviso({ tipo: "erro", mensagem: mensagemDe(e) });
    }
  }

  async function adicionar() {
    if (!novoTermo.trim()) return;
    const termoNovo = novoTermo.trim();
    setAdicionando(true);
    await executar(
      () => adicionarTermo(novoTermo, novaDescricao),
      mensagem((c) => c.termos.adicionado(termoNovo)),
    );
    setNovoTermo("");
    setNovaDescricao("");
    setAdicionando(false);
  }

  if (erroCarga) return <p className="perfil__erro">{textoDe(erroCarga)}</p>;
  if (termos === null) return <p className="perfil__vazio">{tx.carregandoTermos}</p>;

  return (
    <div className="termos">
      <p className="perfil__texto">{tx.explicacao}</p>

      <ul className="termos__lista">
        {termos.map((t) => (
          <li key={t.termo} className="termos__item">
            <div className="termos__cabeca">
              <span className="termos__nome">{t.termo}</span>
              <button
                type="button"
                className="perfil__botao-discreto"
                onClick={() =>
                  executar(
                    () => removerTermo(t.termo),
                    mensagem((c) => c.termos.removido(t.termo)),
                  )
                }
                aria-label={tx.removerOTermo(t.termo)}
              >
                {tx.removerTermo}
              </button>
            </div>
            {/* key com a descricao: gravada (ou mudada por outra acao), o
                campo recomeca do valor do servidor */}
            <DescricaoDoTermo
              key={`${t.termo}::${t.descricao}`}
              termo={t.termo}
              descricao={t.descricao}
              aoGravar={recarregar}
            />
            {t.variacoes.length > 0 && (
              <p className="termos__variacoes">
                <span className="termos__rotulo-variacoes">{tx.corrige}</span>{" "}
                {t.variacoes.map((v, k) => (
                  <span key={v.errado} className="termos__variacao">
                    {v.errado}
                    {v.certo !== t.termo && (
                      <span className="termos__certo-contexto">
                        <Seta direcao="direita" />
                        {v.certo}
                      </span>
                    )}
                    <button
                      type="button"
                      className="termos__remover-variacao"
                      onClick={() =>
                        executar(
                          () => removerVariacao(v.errado),
                          mensagem((c) => c.termos.naoSeraMaisCorrigido(v.errado)),
                        )
                      }
                      aria-label={tx.pararDeCorrigir(v.errado)}
                      title={tx.pararDeCorrigirDica}
                    >
                      ×
                    </button>
                    {k < t.variacoes.length - 1 ? ", " : ""}
                  </span>
                ))}
              </p>
            )}
            {variacaoAberta === t.termo ? (
              <AdicionarVariacao
                termo={t.termo}
                variacoes={t.variacoes}
                aoTerminar={(m) => {
                  setVariacaoAberta(null);
                  if (m) {
                    setAviso({ tipo: "ok", mensagem: m });
                    recarregar();
                  }
                }}
              />
            ) : (
              <button
                type="button"
                className="glossario__adicionar"
                onClick={() => setVariacaoAberta(t.termo)}
              >
                {tx.adicionarVariacao}
              </button>
            )}
          </li>
        ))}
      </ul>

      <form
        className="termos__novo"
        onSubmit={(e) => {
          e.preventDefault();
          adicionar();
        }}
      >
        <p className="perfil__rotulo-campo">{tx.adicionarTermo}</p>
        <label className="so-leitor-de-tela" htmlFor={`${id}-nome`}>
          {tx.nomeDoTermo}
        </label>
        <input
          id={`${id}-nome`}
          className="perfil__input"
          value={novoTermo}
          maxLength={TERMO_MAX_LEN}
          placeholder={tx.nomeDoTermoExemplo}
          onChange={(e) => setNovoTermo(e.target.value)}
        />
        <label className="so-leitor-de-tela" htmlFor={`${id}-descricao`}>
          {tx.oQueE}
        </label>
        <input
          id={`${id}-descricao`}
          className="perfil__input"
          value={novaDescricao}
          maxLength={DESCRICAO_MAX_LEN}
          placeholder={tx.oQueEExemplo}
          onChange={(e) => setNovaDescricao(e.target.value)}
        />
        <div className="perfil__acoes perfil__acoes--sem-regua">
          <button
            type="submit"
            className="perfil__botao-primario"
            disabled={!novoTermo.trim() || adicionando}
          >
            {adicionando ? tx.adicionando : tx.adicionarTermo}
          </button>
        </div>
      </form>

      {aviso && (
        <p
          className={"perfil__status" + (aviso.tipo === "erro" ? " perfil__status--erro" : "")}
          role="status"
        >
          {textoDe(aviso.mensagem)}
        </p>
      )}

      <ReaplicarNasReunioes desabilitado={false} />
    </div>
  );
}
