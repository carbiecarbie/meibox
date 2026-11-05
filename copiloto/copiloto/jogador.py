"""Idioma e nome do jogador, lidos do banco do Meibox (só leitura).

Tabela `settings(key, value)` com valores em JSON: `lang` ("pt"/"en") e `player_name`.
Sem banco, sem tabela ou sem as chaves: português e sem nome.
"""
import json
import os
import sqlite3


def _ler_settings(banco):
    if not banco or not os.path.exists(banco):
        return {}
    try:
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True, timeout=1)
        try:
            linhas = con.execute(
                "SELECT key, value FROM settings WHERE key IN ('lang', 'player_name')").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return {}
    out = {}
    for k, v in linhas:
        try:
            out[k] = json.loads(v)
        except (TypeError, ValueError):
            out[k] = v
    return out


def normalizar_nome(nome):
    """Espaços limpos, até 12 letras. Tudo maiúsculo vira só a primeira maiúscula ("LULU" -> "Lulu",
    design 12.4); um nome já com maiúsculas e minúsculas fica como está."""
    nome = " ".join(str(nome or "").split())[:12].strip()
    if nome.isupper():
        nome = nome[:1] + nome[1:].lower()
    return nome


def ler(cfg):
    """Devolve (idioma, nome) seguindo a config: idioma auto|pt|en, nome_jogador vazio = Meibox."""
    s = None
    idioma = cfg.get("idioma", "auto")
    if idioma not in ("pt", "en"):
        s = _ler_settings(cfg.get("banco_meibox"))
        idioma = s.get("lang") if s.get("lang") in ("pt", "en") else "pt"
    nome = cfg.get("nome_jogador") or ""
    if not nome:
        if s is None:
            s = _ler_settings(cfg.get("banco_meibox"))
        nome = s.get("player_name") or ""
    return idioma, normalizar_nome(nome)
