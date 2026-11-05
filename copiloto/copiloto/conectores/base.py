"""Interface dos conectores de IA.

Cada conector tem:
  dica(sistema, ficha, texto, imagem_png, tempo_max) -> RespostaDica   (fala + onde)
  ficha(sistema, pedido, busca_web, tempo_max)     -> RespostaFicha
e levanta ErroIA com um `codigo` que vira frase da Mei (mensagens.py).
"""
import json
import os
import re
from dataclasses import dataclass, field

# Códigos usados por mensagens.py
SEM_INTERNET, SEM_CHAVE, CHAVE_RECUSADA = "sem_internet", "sem_chave", "chave_recusada"
DEMOROU, SEM_CREDITO, RECUSOU, VAZIO = "demorou", "sem_credito", "recusou", "vazio"


class ErroIA(Exception):
    def __init__(self, codigo, detalhe=""):
        super().__init__(f"{codigo}: {detalhe}" if detalhe else codigo)
        self.codigo = codigo
        self.detalhe = detalhe


@dataclass
class RespostaDica:
    fala: str
    onde: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    tokens_cache: int = 0
    tentativas: int = 1


@dataclass
class RespostaFicha:
    texto: str
    com_pesquisa: bool
    buscas: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    fontes: list = field(default_factory=list)


def ler_chave(caminho):
    """Lê a chave de um arquivo. Nunca registra nem devolve o conteúdo em mensagens de erro."""
    try:
        with open(os.path.expanduser(caminho), encoding="utf-8") as f:
            chave = f.read().strip()
    except OSError:
        raise ErroIA(SEM_CHAVE, f"arquivo ausente ({caminho})") from None
    if not chave:
        raise ErroIA(SEM_CHAVE, f"arquivo vazio ({caminho})")
    return chave


def interpretar_json(texto):
    """{fala, onde} a partir da resposta. Tolera ```json, texto em volta e "onde" faltando."""
    texto = (texto or "").strip()
    if not texto:
        raise ErroIA(VAZIO, "resposta sem texto")
    cerca = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    if cerca:
        texto = cerca.group(1).strip()
    dados = None
    try:
        dados = json.loads(texto)
    except ValueError:
        m = re.search(r"\{.*\}", texto, re.S)
        if m:
            try:
                dados = json.loads(m.group(0))
            except ValueError:
                pass
    if not isinstance(dados, dict):
        # Sem JSON: usa o texto como fala (melhor que perder a dica).
        if texto.lstrip().startswith("{"):
            raise ErroIA(VAZIO, "JSON quebrado")
        return texto, ""
    fala = str(dados.get("fala") or "").strip()
    if not fala:
        raise ErroIA(VAZIO, "JSON sem 'fala'")
    return fala, str(dados.get("onde") or "").strip()


def criar(nome, cfg):
    """Conector pelo nome, carregando só o módulo dele (o SDK da Anthropic é pesado).
    Nome vazio = nenhuma IA configurada: devolve None."""
    if not nome:
        return None
    forn = cfg["fornecedores"].get(nome)
    if forn is None:
        raise ValueError(f"fornecedor desconhecido na config: {nome}")
    if nome == "anthropic":
        from .anthropic_ import ConectorAnthropic
        return ConectorAnthropic(forn, cfg.get("pasta_vendor"))
    if nome == "openai_compat" or forn.get("tipo") == "openai_compat":
        from .openai_compat import ConectorOpenAICompat
        return ConectorOpenAICompat(forn)
    raise ValueError(f"fornecedor sem conector: {nome}")
