"""
servidor/sistema.py - o que a tela de Perfil mostra como informacao, nunca
como controle: versao, dispositivo e motor de transcricao detectados, onde
ficam os dados, e as licencas de terceiros (ATRIBUICAO.md).

Tudo somente leitura. Os caminhos saem daqui para a tela (o usuario
precisa saber onde estao as gravacoes da empresa); nenhum caminho entra
por aqui (CLAUDE.md, regra 4).
"""

import os
from pathlib import Path

from trama import nucleo
from trama.servidor import processamento, reunioes

RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_ATRIBUICAO = RAIZ / "ATRIBUICAO.md"

# Fonte unica da versao exibida em Perfil > Sobre. Nao existia versao
# nenhuma antes desta tela; 0.3.0-dev = marco 3 em construcao.
VERSAO = "0.3.0-dev"

# Modo demonstracao (TRAMA_DEMO=1): os dados de audios-demo/<idioma> nao tem
# audio - sao reunioes ficticias geradas por ferramentas/gerar_demo.py. A
# tela avisa em vez de tentar tocar, e a rota de audio responde o codigo
# sem_audio_na_demonstracao.
DEMONSTRACAO = os.environ.get("TRAMA_DEMO") == "1"


def licencas():
    """
    ATRIBUICAO.md -> [{"nome", "itens": [{"rotulo", "texto"}]}], um por
    secao "## " que declara "- Licenca:". So os itens de lista "- Rotulo: texto" (com as linhas de
    continuacao indentadas juntadas) - citacao BibTeX e paragrafo solto
    ficam de fora: a tela mostra o que cada licenca exige atribuir, nao o
    arquivo inteiro. O texto sai cru; a tela renderiza como texto, nunca
    como HTML (CLAUDE.md, regra 9).
    """
    if not CAMINHO_ATRIBUICAO.exists():
        return []
    secoes = []
    atual = None
    item = None
    for linha in CAMINHO_ATRIBUICAO.read_text(encoding="utf-8").splitlines():
        if linha.startswith("## "):
            atual = {"nome": linha[3:].strip(), "itens": []}
            secoes.append(atual)
            item = None
        elif atual is not None and linha.startswith("- "):
            rotulo, sep, texto = linha[2:].partition(":")
            item = (
                {"rotulo": rotulo.strip(), "texto": texto.strip()}
                if sep
                else {"rotulo": "", "texto": linha[2:].strip()}
            )
            atual["itens"].append(item)
        elif item is not None and linha.startswith("  ") and linha.strip():
            item["texto"] = f"{item['texto']} {linha.strip()}".strip()
        else:
            item = None
    # So o que e ATRIBUICAO de terceiro: secao que declara uma licenca. O
    # arquivo pode ter anotacao interna (secao sem "- Licenca:") -
    # nota de quem escreveu, nunca texto de tela de produto.
    return [s for s in secoes if any(i["rotulo"].lower() == "licenca" for i in s["itens"])]


def resumo():
    device, asr = processamento.detectar_device_e_asr()
    return {
        "versao": VERSAO,
        "device": device,
        "asr": asr,
        "pasta_audios": str(Path(reunioes.PASTA_AUDIOS).resolve()),
        "banco_vozes": str(Path(nucleo.DB_PATH).resolve()),
        "licencas": licencas(),
        "demonstracao": DEMONSTRACAO,
    }
