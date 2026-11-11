"""
ata.py - Ata de reuniao com LLM local (Ollama), com citacoes verificadas.

100% offline.

TRES DECISOES DE PROJETO

1. EM BLOCOS. Uma reuniao de 70 min vira ~20 mil tokens. O custo da atencao
   cresce com o quadrado do contexto, e modelos no Ollama truncam EM SILENCIO
   quando o texto passa da janela - a ata sai parecendo completa cobrindo so o
   comeco. Medido aqui: 30 linhas em 21s; o arquivo inteiro nao terminou em 60s.

2. CITACAO OBRIGATORIA. Toda decisao e toda tarefa vem acompanhada de um trecho
   literal do transcript. Isso nao e formalidade: e o que ancora o modelo no que
   foi realmente dito.

3. VERIFICACAO EM CODIGO, NAO NO PROMPT. Depois de gerar a ata, o script
   procura cada citacao no transcript original por comparacao de texto. Se nao
   achar, marca. Pedir "nao invente" no prompt e esperanca; conferir a string e
   verificacao.

   Isso existe por causa de erros reais observados:
   - o modelo escreveu que um custo "nao foi concluido na reuniao" quando havia
     numero explicito no transcript;
   - atribuiu a uma pessoa uma fala em que ela descrevia um caso hipotetico;
   - uma citacao com uma negacao ACRESCENTADA ("nao aprovamos" onde a fonte diz
     "aprovamos") passou como confirmada, porque so a SEMELHANCA de caracteres
     era alta. Por isso a verificacao distingue exata / so-formatacao /
     aproximada, e SO as duas primeiras contam como confirmadas - aproximada e
     apenas uma sugestao de trecho para revisao humana, nunca uma confirmacao.

Uso:
    python experimental/ata.py audios/reuniao_08/reuniao_08.json
    python experimental/ata.py audios/reuniao_08/reuniao_08.json --modelo llama3.1:8b
"""

import argparse
import difflib
import json
import re
import subprocess
import time
import unicodedata
from pathlib import Path

MODELO_PADRAO = "qwen3.8:27b-mlx"
LINHAS_POR_BLOCO = 30

# Semelhanca minima para considerar uma citacao encontrada. Nao exigimos
# identidade: o modelo normaliza pontuacao e as vezes corta a frase no meio.
SEMELHANCA_MIN = 0.82

# Citacao mais curta que isto gera falso positivo ("Pode ser", "Sim").
MIN_PALAVRAS_CITACAO = 4


PROMPT_BLOCO = """Você é secretário de reunião. Este é o trecho {i} de {n} de uma reunião de
trabalho, na ordem em que aconteceu. Cada linha traz o nome de quem falou.

Linhas marcadas [vozes sobrepostas] têm transcrição menos confiável — não
baseie decisão nem tarefa apenas nelas.

Extraia, SEMPRE nomeando quem disse o quê:

DISCUSSÃO
Duas a cinco frases sobre o que foi debatido e a posição de cada pessoa.
Registre discordâncias explicitamente.

DECISÕES
Uma linha por decisão, neste formato exato:
- DECISÃO: <o que ficou acordado> | QUEM: <nome> | CITAÇÃO: "<trecho literal>"
Frases como "então tá", "pode ser", "sai daqui com isso" indicam acordo.
Se não houver nenhuma, escreva: DECISÕES: nenhuma

TAREFAS
Uma linha por tarefa, neste formato exato:
- TAREFA: <o que fazer> | QUEM: <nome> | PRAZO: <prazo ou "não definido"> | CITAÇÃO: "<trecho literal>"
Se não houver nenhuma, escreva: TAREFAS: nenhuma

NÚMEROS E FATOS
Todo valor, prazo, quantidade ou nome de ferramenta citado, com a citação
literal. Se não houver, escreva: nenhum

EM ABERTO
Perguntas levantadas e não respondidas neste trecho.

REGRAS
- A CITAÇÃO tem de ser copiada literalmente do trecho, palavra por palavra.
- Não descreva emoção, tom de voz ou intenção. Só o conteúdo do que foi dito.
- Não atribua a alguém uma fala em que a pessoa cita outra ou descreve um caso
  hipotético.
- Se um número foi dito, registre o número. Nunca escreva que ficou indefinido
  se ele aparece no trecho.

TRECHO {i}/{n}:
{trecho}"""


PROMPT_ATA = """Você recebe notas de uma reunião de trabalho, extraídas em ordem cronológica
de {n} trechos. Consolide numa ata profissional em português.

Use exatamente estes cabeçalhos:

## Resumo executivo
Três a cinco frases: objetivo da reunião, a tensão central do debate e onde
ela parou.

## Assuntos tratados
Um bloco por tema, com subtítulo em negrito. Sob cada tema, explique o que foi
discutido e a posição de cada participante. Registre as discordâncias — são a
parte mais útil de uma ata. Agrupe por assunto, não por ordem de fala.

## Decisões
Numeradas. Cada uma termina com a citação entre aspas, copiada das notas.
Se as notas registram acordo sobre algo, é decisão, mesmo que informal.
NÃO escreva "nenhuma decisão" se houver qualquer acordo nas notas.

## Tarefas e responsáveis
Tabela: Responsável | Tarefa | Prazo | Citação.
Prazo não dito = "não definido". Responsável não claro = "a definir".

## Números e compromissos citados
Todo valor, prazo e quantidade que apareceu, com a citação. Esta seção existe
porque número é o que mais se perde numa ata — e o que mais importa depois.

## Pontos em aberto
Questões levantadas e não resolvidas.

REGRAS
- Unifique itens repetidos entre trechos.
- Preserve as CITAÇÕES exatamente como estão nas notas. Não reescreva.
- Nomeie as pessoas. Ata sem nomes não serve.
- Não descreva emoção, tom de voz ou intenção de ninguém. Uma ata que diz
  "respondeu com nervosismo" gera conflito e não pode ser verificada.
- Não atribua a alguém fala em que a pessoa cita outra ou fala de hipótese.
- Se as notas trazem um número, ele PRECISA aparecer na ata. Nunca escreva que
  algo ficou indefinido se há número nas notas.
- Não escreva título próprio: comece direto no primeiro cabeçalho.

NOTAS DOS {n} TRECHOS:
{notas}"""


# --------------------------------------------------------------------------
# Ollama
# --------------------------------------------------------------------------


def ollama(modelo, prompt, num_ctx=8192, num_predict=1500, timeout=600, tentativas=2):
    """
    num_ctx explicito porque o padrao truncaria em silencio.

    num_predict e essencial: sem teto, o modelo pode entrar em loop de
    repeticao. Observado aqui: 19.155 tokens gerados antes de estourar um
    timeout de 10 min, num pedido de ~200 palavras.
    """
    corpo = json.dumps(
        {
            "model": modelo,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "temperature": 0.15,
                "repeat_penalty": 1.15,
            },
        }
    )
    ultimo = ""
    for tentativa in range(1, tentativas + 1):
        r = subprocess.run(
            [
                "curl",
                "-s",
                "--max-time",
                str(timeout),
                "http://localhost:11434/api/generate",
                "-H",
                "Content-Type: application/json",
                "-d",
                corpo,
            ],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            try:
                d = json.loads(r.stdout)
            except json.JSONDecodeError:
                ultimo = f"resposta nao-JSON: {r.stdout[:200]}"
            else:
                if "error" in d:
                    ultimo = f"erro do Ollama: {d['error']}"
                else:
                    return d.get("response", "").strip()
        elif r.returncode == 28:
            ultimo = f"timeout de {timeout}s"
        elif r.returncode == 7:
            ultimo = "conexao recusada (o Ollama nao esta rodando)"
        else:
            ultimo = f"curl saiu com {r.returncode}: {r.stderr[:200]}"
        if tentativa < tentativas:
            print(f"      ! {ultimo} - tentando de novo", flush=True)
            time.sleep(3)
    raise SystemExit(
        f"\nFalhou apos {tentativas} tentativas: {ultimo}\n\n"
        "Reinicie o Ollama:\n"
        "  pkill ollama && ollama serve > /tmp/ollama.log 2>&1 &"
    )


# --------------------------------------------------------------------------
# carregamento
# --------------------------------------------------------------------------


def em_sobreposicao(ini, fim, regioes, min_fracao=0.25):
    dur = max(fim - ini, 1e-6)
    coberto = sum(max(0.0, min(fim, r["fim"]) - max(ini, r["inicio"])) for r in regioes)
    return (coberto / dur) >= min_fracao


def carregar(caminho):
    """
    Aceita .json (preferido) ou .txt.

    Do JSON aproveitamos a dinamica e, principalmente, as regioes sobrepostas:
    marcar as falas de transcricao duvidosa evita que o modelo construa uma
    decisao sobre texto que provavelmente esta errado.
    """
    p = Path(caminho)
    if p.suffix != ".json":
        return p.read_text(encoding="utf-8").splitlines(), {}

    d = json.loads(p.read_text(encoding="utf-8"))
    regioes = d.get("regioes_sobrepostas", [])
    linhas = []
    for f in d.get("falas", []):
        m = int(f["inicio"])
        marca = (
            "  [vozes sobrepostas]"
            if regioes and em_sobreposicao(f["inicio"], f["fim"], regioes)
            else ""
        )
        linhas.append(
            f"[{m // 3600:02d}:{(m % 3600) // 60:02d}:{m % 60:02d}] "
            f"{f['falante']}: {f['texto']}{marca}"
        )
    return linhas, d.get("dinamica", {})


def blocos(linhas, n):
    saida, atual = [], []
    for linha in linhas:
        if linha.strip():
            atual.append(linha)
        if len(atual) >= n:
            saida.append("\n".join(atual))
            atual = []
    if atual:
        saida.append("\n".join(atual))
    return saida


def limpar(texto):
    """Remove raciocinio em voz alta de modelos que pensam antes de responder."""
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


# --------------------------------------------------------------------------
# verificacao de citacoes - o coracao do modulo
# --------------------------------------------------------------------------


def normalizar(t):
    """Minusculas, sem acento, sem pontuacao, espacos colapsados."""
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def extrair_citacoes(texto):
    """
    Tudo entre aspas retas ou curvas, com pelo menos MIN_PALAVRAS_CITACAO.

    CUIDADO AO MEXER NA REGEX: o filtro de tamanho tem de ficar em Python, nao
    dentro do padrao. Com `{10,400}` na regex, uma citacao curta como
    "Pode ser" falha o minimo e o pareamento das aspas DESALINHA - passa a
    casar da aspa que fecha uma citacao ate a que abre a seguinte, capturando o
    texto do meio. O sintoma sao "citacoes" comecando com ), ; ou |.
    """
    brutas = re.findall(r'"([^"\n]*)"', texto)
    brutas += re.findall(r"\u201c([^\u201d\n]*)\u201d", texto)

    vistas, saida = set(), []
    for c in brutas:
        c = c.strip()
        if len(c) < 10 or len(c) > 400:
            continue
        if len(c.split()) < MIN_PALAVRAS_CITACAO:
            continue
        # Rede de seguranca: citacao de fala nao comeca com pontuacao de
        # estrutura, e ' | ' e separador de tabela, nao conteudo falado.
        if c[0] in ")];|,.:" or " | " in c:
            continue
        chave = normalizar(c)
        if chave and chave not in vistas:
            vistas.add(chave)
            saida.append(c)
    return saida


def verificar_citacoes(citacoes, transcript, limiar=SEMELHANCA_MIN):
    """
    Procura cada citacao no transcript. Comparacao textual, deterministica -
    nao passa por LLM nenhum.

    TRES categorias, e so DUAS contam como confirmadas:

      exata       a citacao aparece caractere por caractere no transcript.
      formatacao  so casa depois de normalizar (acento/pontuacao/espaco/
                  caixa) - a diferenca e cosmetica, o conteudo e o mesmo.
      aproximada  NAO casa nem normalizado. NUNCA e promovida a confirmada,
                  so serve de sugestao de onde olhar. Semelhanca de
                  caracteres (difflib) NAO distingue "aprovamos" de "nao
                  aprovamos", nem "40" de "42": uma negacao ou um numero
                  trocado muda o sentido sem derrubar a semelhanca textual.
                  Foi exatamente isso que passou como "confirmada" antes
                  desta funcao existir: a citacao com "nao" acrescentado
                  batia >0.82 de similaridade contra a fonte sem a negacao.

    Retorna (confirmadas, aproximadas):
      confirmadas = [(citacao, tipo)]              tipo em {"exata", "formatacao"}
      aproximadas = [(citacao, melhor_semelhanca, trecho_mais_parecido)]
    """
    alvo_norm = normalizar(transcript)
    confirmadas, aproximadas = [], []

    for c in citacoes:
        if c in transcript:
            confirmadas.append((c, "exata"))
            continue

        q = normalizar(c)
        if not q:
            continue
        if q in alvo_norm:
            confirmadas.append((c, "formatacao"))
            continue

        # Nao achou nem normalizado: procura so o trecho mais PARECIDO, para
        # o rodape sugerir onde conferir manualmente. Isto e so uma dica -
        # jamais conta como citacao confirmada.
        melhor, melhor_trecho, passo = 0.0, "", max(len(q) // 4, 1)
        sm = difflib.SequenceMatcher(autojunk=False)
        sm.set_seq2(q)
        for i in range(0, max(len(alvo_norm) - len(q), 0) + 1, passo):
            janela = alvo_norm[i : i + len(q)]
            sm.set_seq1(janela)
            if sm.real_quick_ratio() < 0.5 or sm.quick_ratio() < 0.5:
                continue
            r = sm.ratio()
            if r > melhor:
                melhor, melhor_trecho = r, janela

        aproximadas.append((c, melhor, melhor_trecho))

    return confirmadas, aproximadas


def rodape_verificacao(citacoes, confirmadas, aproximadas):
    """
    Monta o rodape de verificacao a partir do resultado de
    verificar_citacoes(). Funcao pura - nao chama Ollama nem imprime nada -
    para poder ser testada sem depender do resto do pipeline.

    Encontrar uma citacao no transcript so confirma que aquele TEXTO existe
    ali; nao confirma que a decisao ou o responsavel apontados pela ata
    estejam corretos, nem que nenhuma citacao tenha sido inventada em outro
    lugar do documento. Por isso o aviso de contexto aparece sempre que ha
    pelo menos uma citacao, nao so quando algo parece suspeito.
    """
    if not citacoes:
        return [
            "",
            "## Verificação de citações",
            "",
            "**Nenhuma citação foi extraída da ata** - nada pôde ser "
            "verificado automaticamente por comparação de texto. Isso "
            "não significa que a ata esteja correta: confira decisões, "
            "tarefas e responsáveis diretamente no transcript antes de "
            "circular.",
        ]

    exatas = sum(1 for _, t in confirmadas if t == "exata")
    formatacao = len(confirmadas) - exatas

    linhas = [
        "",
        "## Verificação de citações",
        "",
        f"{len(confirmadas)} de {len(citacoes)} citações foram "
        "localizadas no transcript por comparação automática de texto "
        f"({exatas} literais, {formatacao} com diferença apenas de "
        "formatação/acentuação/pontuação).",
        "",
        "A localização de uma citação não comprova que a decisão ou o "
        "responsável indicados estejam corretos - confira o contexto "
        "no transcript antes de circular.",
    ]

    if not confirmadas:
        linhas += [
            "",
            "**Nenhuma citação pôde ser confirmada como literal "
            "no transcript.** Não trate o conteúdo desta ata como "
            "aprovado só porque citações foram extraídas dela - "
            "confira manualmente antes de circular.",
        ]

    if aproximadas:
        linhas += [
            "",
            "**Trechos que NÃO foram localizados no transcript "
            "(nem literalmente, nem após normalizar formatação).** "
            "Não foi possível confirmar como fala literal - pode ser "
            "paráfrase do modelo, erro de transcrição, ou uma "
            "diferença de sentido (negação, número, nome) que a "
            "semelhança de texto não distingue. Precisam ser "
            "conferidos manualmente no transcript antes de qualquer "
            "decisão baseada neles:",
            "",
        ]
        linhas += [f'- ({s:.2f}) "{c}"' for c, s, _ in aproximadas]

    return linhas


# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", help=".json (preferido) ou .txt do pipeline.py")
    ap.add_argument("--modelo", default=MODELO_PADRAO)
    ap.add_argument("--linhas", type=int, default=LINHAS_POR_BLOCO)
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--sem-verificacao", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    linhas, dinamica = carregar(args.transcript)
    if not linhas:
        raise SystemExit("Transcript vazio.")
    texto_completo = "\n".join(linhas)

    partes = blocos(linhas, args.linhas)
    print(f"{len(linhas)} linhas -> {len(partes)} blocos   modelo: {args.modelo}")

    t0, notas = time.time(), []
    for i, parte in enumerate(partes, 1):
        ini = time.time()
        r = limpar(
            ollama(
                args.modelo,
                PROMPT_BLOCO.format(trecho=parte, i=i, n=len(partes)),
                num_ctx=args.ctx,
                num_predict=1500,
            )
        )
        notas.append(f"### trecho {i} de {len(partes)}\n{r}")
        resta = (time.time() - t0) / i * (len(partes) - i)
        print(
            f"  bloco {i}/{len(partes)}  {time.time() - ini:.0f}s   (faltam ~{resta / 60:.1f} min)",
            flush=True,
        )

    juntas = "\n\n".join(notas)
    est = len(juntas) // 4
    print(f"  consolidando {len(notas)} notas (~{est} tokens)...", flush=True)
    if est > 28000:
        print("      ! notas grandes; se a ata sair incompleta, use --linhas 45", flush=True)

    ata = limpar(
        ollama(
            args.modelo,
            PROMPT_ATA.format(notas=juntas, n=len(partes)),
            num_ctx=max(args.ctx, 32768),
            num_predict=8000,
            timeout=1800,
        )
    )

    faltando = [
        h
        for h in ("## Decisões", "## Tarefas e responsáveis", "## Pontos em aberto")
        if h not in ata
    ]
    if faltando:
        print(f"\n  ! ATA INCOMPLETA - faltam: {', '.join(faltando)}")
        print("    O modelo bateu no teto de tokens. Tente --linhas 45.")

    # ---- verificacao ----
    rodape = []
    if not args.sem_verificacao:
        cit = extrair_citacoes(ata)
        print(f"\n  Verificando {len(cit)} citacoes contra o transcript...", flush=True)
        confirmadas, aproximadas = verificar_citacoes(cit, texto_completo)
        print(f"    {len(confirmadas)} confirmadas, {len(aproximadas)} nao localizadas")
        for c, s, _ in aproximadas:
            print(f"      ! ({s:.2f}) {c[:80]}")

        rodape = rodape_verificacao(cit, confirmadas, aproximadas)

    cab = [f"# Ata - {Path(args.transcript).stem}", ""]
    if dinamica:
        cab += [
            "**Participantes** (tempo de fala): "
            + ", ".join(
                f"{n} {d['fala_pct']:.0f}%"
                for n, d in sorted(dinamica.items(), key=lambda kv: -kv[1]["fala_s"])
            ),
            "",
        ]
    cab += (
        [ata]
        + rodape
        + [
            "",
            "---",
            "",
            f"Gerado localmente por {args.modelo} em "
            f"{(time.time() - t0) / 60:.1f} min, a partir de {len(partes)} blocos.",
            "Ata gerada por LLM. As citações foram verificadas automaticamente; o "
            "resto do texto não. Confira decisões e responsáveis no transcript "
            "antes de circular.",
        ]
    )

    destino = (
        Path(args.out)
        if args.out
        else Path(args.transcript).with_name(Path(args.transcript).stem + "_ata.md")
    )
    destino.write_text("\n".join(cab), encoding="utf-8")

    print(f"\nTempo total: {(time.time() - t0) / 60:.1f} min")
    print(f"Ata: {destino}")


if __name__ == "__main__":
    main()
