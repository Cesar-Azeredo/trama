"""
servidor/transcricao.py - transcricao da reuniao em texto puro, para baixar.

Gerada NA HORA a partir do .json, nunca copiada do .txt do pipeline: o
.txt nao tem titulo, nao tem a porcentagem de fala, e fica desatualizado
depois de uma revisao feita pela tela ou de reaplicar o glossario (as
duas regravam o .json; so a revisao regrava o .txt).

Texto limpo, para colar numa IA: nenhuma marca de interface (sobreposicao,
confianca baixa, lacuna) - so quem falou, quando e o que. Voz sem pessoa
sai como na tela ("voz nao atribuida", numerada quando ha mais de uma),
nunca o rotulo de maquina (DESCONHECIDO_/IGNORADO_).

Nada daqui vai para o log: e o conteudo da reuniao (CLAUDE.md, regra 3).
"""

import re
import unicodedata
from datetime import datetime
from urllib.parse import quote

MESES = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

# Recusados em nome de arquivo no Windows (o mais restritivo dos tres) - o
# arquivo pode ir para um pendrive ou uma pasta compartilhada.
_PROIBIDO_EM_NOME = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
NOME_ARQUIVO_MAX = 150


def eh_voz_sem_pessoa(nome):
    return nome.startswith(("DESCONHECIDO", "IGNORADO"))


def rotulos_da_reuniao(nomes):
    """
    Mesma regra de frontend/src/util/falante.ts (rotulosDaReuniao): pessoa
    fica como esta; voz sem pessoa vira "voz não atribuída", numerada na
    ordem do rotulo cru so quando ha mais de uma - o arquivo e a tela
    chamam a mesma voz pelo mesmo nome.
    """
    sem_pessoa = sorted({n for n in nomes if eh_voz_sem_pessoa(n)})
    mapa = {
        n: ("voz não atribuída" if len(sem_pessoa) == 1 else f"voz não atribuída {i + 1}")
        for i, n in enumerate(sem_pessoa)
    }
    return lambda nome: mapa.get(nome) or ("voz não atribuída" if eh_voz_sem_pessoa(nome) else nome)


def _todos_os_nomes(dados):
    """Os mesmos conjuntos que o Detalhe junta para numerar as vozes."""
    nomes = [c.get("nome", "") for c in (dados.get("clusters") or {}).values()]
    nomes += [f.get("falante", "") for f in dados.get("falas") or []]
    nomes += list((dados.get("dinamica") or {}).keys())
    for e in dados.get("eventos") or []:
        nomes += [e.get("entrante", ""), e.get("falava", "")]
    return [n for n in nomes if n]


def titulo_da_reuniao(id, titulo):
    """O titulo dado, ou o padrao da tela (formatarTitulo): "Reunião NN"."""
    if titulo:
        return titulo
    m = re.fullmatch(r"reuniao_(\d+)", id)
    return f"Reunião {m.group(1)}" if m else id


def _data_local(data_iso, fuso=None):
    """UTC do .json para o fuso da maquina (o mesmo que a tela usa)."""
    if not data_iso:
        return None
    try:
        d = datetime.fromisoformat(data_iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(fuso)


def _data_por_extenso(d, com_hora):
    texto = f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    return f"{texto}, {d:%H:%M}" if com_hora else texto


def _duracao_por_extenso(segundos):
    s = int(round(segundos))
    if s < 60:
        return f"{s} s"
    h, minutos = divmod(round(s / 60), 60)
    if h == 0:
        return f"{minutos} min"
    return f"{h} h {minutos:02d} min" if minutos else f"{h} h"


def _horario(segundos, com_hora):
    s = max(0, int(segundos))
    h, resto = divmod(s, 3600)
    m, seg = divmod(resto, 60)
    return f"{h}:{m:02d}:{seg:02d}" if com_hora else f"{m:02d}:{seg:02d}"


def _texto_numa_linha(texto):
    return " ".join((texto or "").split())


TITULO_VOCABULARIO = "Vocabulário desta empresa"
INSTRUCAO_VOCABULARIO = (
    "Esta transcrição foi feita automaticamente. Alguns termos podem ter "
    "sido transcritos errado; use esta lista para interpretar. Antes de "
    "escrever a ata, liste os termos que parecem errados ou fora de "
    "contexto e pergunte o que significam."
)


def montar_texto(id, dados, fuso=None, vocabulario=None):
    """
    O conteudo do arquivo. `dados` e o que reunioes.carregar devolve: o
    .json com "titulo", "data" e "data_origem" ja resolvidos (inclusive a
    data lida do audio, para reuniao antiga sem data no .json). `fuso` so
    existe para o teste
    fixar o fuso; em uso, None = fuso da maquina.

    `vocabulario`: [(termo, descricao ou None)] do glossario
    (glossario.vocabulario) - vira a secao final, para a IA que ler o
    arquivo saber como a empresa escreve os proprios termos. Vazio ou None:
    sem secao.
    """
    rotulo = rotulos_da_reuniao(_todos_os_nomes(dados))
    falas = dados.get("falas") or []
    duracao = max((f["fim"] for f in falas), default=0.0)

    linhas = [titulo_da_reuniao(id, dados.get("titulo"))]

    d = _data_local(dados.get("data"), fuso)
    if d and dados.get("data_origem") == "gravacao":
        linhas.append(f"Data: {_data_por_extenso(d, com_hora=True)}")
    elif d:
        # Data de modificacao do arquivo, nao da reuniao - a tela diz
        # "chegou em"; aqui tambem nunca se passa por data da reuniao.
        linhas.append(
            "Data: não registrada na gravação "
            f"(arquivo recebido em {_data_por_extenso(d, com_hora=False)})"
        )
    if falas:
        linhas.append(f"Duração: {_duracao_por_extenso(duracao)}")

    dinamica = dados.get("dinamica") or {}
    if dinamica:
        linhas.append("Participantes (parcela do tempo de fala):")
        ordem = sorted(dinamica.items(), key=lambda item: -(item[1].get("fala_pct") or 0))
        for nome, info in ordem:
            pct = info.get("fala_pct")
            sufixo = f": {round(pct)}%" if pct is not None else ""
            linhas.append(f"- {rotulo(nome)}{sufixo}")
    elif falas:
        # Reuniao de schema antigo, sem dinamica: quem falou, sem inventar
        # porcentagem.
        vistos = list(dict.fromkeys(rotulo(f["falante"]) for f in falas))
        linhas.append(f"Participantes: {', '.join(vistos)}")

    linhas.append("")
    com_hora = duracao >= 3600
    for f in falas:
        texto = _texto_numa_linha(f.get("texto"))
        if not texto:
            continue
        linhas.append(f"[{_horario(f['inicio'], com_hora)}] {rotulo(f['falante'])}: {texto}")

    if vocabulario:
        linhas += ["", TITULO_VOCABULARIO, INSTRUCAO_VOCABULARIO]
        linhas += [
            f"- {termo}: {descricao}" if descricao else f"- {termo}"
            for termo, descricao in vocabulario
        ]

    return "\n".join(linhas) + "\n"


def _nome_limpo(texto):
    texto = _PROIBIDO_EM_NOME.sub(" ", texto)
    texto = " ".join(texto.split())
    # Ponto ou espaco no fim: o Windows corta em silencio; no inicio, vira
    # arquivo oculto no Mac/Linux.
    return texto.strip(" .")[:NOME_ARQUIVO_MAX].strip(" .")


def nome_do_arquivo(id, dados, fuso=None):
    """
    "2026-11-04 Reunião 13.txt". Sem data quando a reuniao so tem a data
    do arquivo (data_origem "arquivo"): ela nao e a data da reuniao, e no
    nome do arquivo passaria por uma.
    """
    titulo = (
        _nome_limpo(titulo_da_reuniao(id, dados.get("titulo")))
        or _nome_limpo(titulo_da_reuniao(id, None))
        or "Reunião"
    )
    d = _data_local(dados.get("data"), fuso)
    if d and dados.get("data_origem") == "gravacao":
        return f"{d:%Y-%m-%d} {titulo}.txt"
    return f"{titulo}.txt"


def content_disposition(nome):
    """
    attachment com o nome em UTF-8 (RFC 6266/5987) e um substituto ASCII
    para quem nao entende filename* - "Reunião" vira "Reuniao".
    """
    ascii_ = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    ascii_ = ascii_.replace('"', "").replace("\\", "") or "transcricao.txt"
    return f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nome, safe='')}"
