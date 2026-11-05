"""Configuração: config.json do usuário por cima dos padrões (design 12.3).

Caminhos com ~ são expandidos. Chaves desconhecidas são mantidas (para quem
quiser acrescentar coisas), e dicionários são mesclados em profundidade.
"""
import copy
import json
import os

CAMINHO_PADRAO = "~/.config/mei-copiloto/config.json"

PADROES = {
    # Sem IA escolhida de fábrica: cada um escolhe o fornecedor e põe a própria chave (veja o README).
    # Exemplos: openai_compat + gpt-6.1-terra, ou anthropic + claude-haiku-5-5 (dicas) / claude-sonnet-5-5 (ficha).
    "dicas": {"fornecedor": "", "modelo": "", "esforco": "low"},
    "ficha": {"fornecedor": "", "modelo": "", "busca_web": True, "max_buscas": 5, "esforco": "medium"},
    "fornecedores": {
        "anthropic": {"chave": "~/.config/mei-copiloto/chaves/anthropic"},
        "openai_compat": {"url": "https://api.openai.com/v1",
                          "chave": "~/.config/mei-copiloto/chaves/openai"},
    },
    "limite_por_dia": 200,
    "fichas_por_dia": 10,
    "tempo_maximo_s": 15,
    "tempo_ficha_s": 90,
    "salvar_dicas": True,
    "pasta_dicas": "/roms/totobox/dicas",
    "pasta_guias": "/roms/totobox/guias",
    "idioma": "auto",            # auto (segue o Meibox) | pt | en
    "nome_jogador": "",          # vazio = lê do Meibox; senão usa este nome
    "linhas_diario": 5,
    "ampliar": 2,                # ampliação da foto mandada à IA (vizinho mais próximo)
    "aviso": True,               # SHOW_MSG pelo RetroArch durante a pesquisa (network_cmd_enable)
    "aviso_porta": 55355,
    "aviso_intervalo_s": 3.3,
    "carregar_sdk": "primeiro_uso",  # primeiro_uso (26 MB parado; 1ª dica do boot +13 s) | inicio
    # internos (normalmente não mudam)
    "porta": 4404,
    "pasta_estado": "~/.local/share/mei-copiloto/state",
    "pasta_assets": "~/.local/share/mei-copiloto/assets",
    "pasta_vendor": "~/.local/share/mei-copiloto/vendor",
    "banco_meibox": "~/.local/share/totobox/data/totobox.db",
}

_CAMPOS_CAMINHO = ("pasta_dicas", "pasta_guias", "pasta_estado", "pasta_assets",
                   "pasta_vendor", "banco_meibox")


def _mesclar(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _mesclar(base[k], v)
        else:
            base[k] = v
    return base


def expandir(caminho):
    return os.path.expanduser(caminho) if isinstance(caminho, str) else caminho


def carregar(caminho=None):
    """Lê a config. Arquivo ausente = só padrões. JSON quebrado gera ValueError com a linha."""
    caminho = expandir(caminho or os.environ.get("MEI_CONFIG") or CAMINHO_PADRAO)
    cfg = copy.deepcopy(PADROES)
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            try:
                _mesclar(cfg, json.load(f))
            except json.JSONDecodeError as e:
                raise ValueError(f"config.json inválido (linha {e.lineno}): {e.msg}") from e
    for campo in _CAMPOS_CAMINHO:
        cfg[campo] = expandir(cfg[campo])
    for forn in cfg["fornecedores"].values():
        if isinstance(forn, dict) and "chave" in forn:
            forn["chave"] = expandir(forn["chave"])
    return cfg
