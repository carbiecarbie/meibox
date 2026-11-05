#!/usr/bin/env python3
"""Ajudante do instalador do Meibox: a chave da IA e os ajustes iniciais.

Nunca imprime a chave. Comandos:
  chave.py ler <arquivo>                  -> imprime "openai" ou "anthropic"
                                             (saída 1: arquivo sem chave; 2: chave não reconhecida)
  chave.py guardar <arquivo> <confdir> <modelo-do-arquivo>
                                          -> grava a chave em <confdir>/chaves/<fornecedor> (600),
                                             ajusta o fornecedor e o modelo em <confdir>/config.json
                                             e devolve o arquivo do cartão ao texto de modelo
  chave.py ajustar <confdir>              -> com uma chave já guardada, escolhe o modelo
                                             (só onde ainda não há fornecedor)
  chave.py apagar <confdir>               -> apaga as chaves guardadas
  chave.py idioma <totobox.db> <pt|en>    -> põe o idioma do Meibox, só se ainda não houver um
"""
import json
import os
import re
import sqlite3
import sys

# Modelos padrão de quem põe a chave pelo cartão (os mesmos do README).
PADROES = {
    "openai": {"fornecedor": "openai_compat",
               "dicas": "gpt-6.1-terra", "ficha": "gpt-6.1-terra"},
    "anthropic": {"fornecedor": "anthropic",
                  "dicas": "claude-haiku-5-5", "ficha": "claude-sonnet-5-5"},
}
ARQUIVO_CHAVE = {"openai": "openai", "anthropic": "anthropic"}  # nome em <confdir>/chaves/
FORMATO = re.compile(r"^sk-[A-Za-z0-9_\-]{20,}$")


def ler_chave(caminho):
    """(fornecedor, chave), (None, None) sem chave, ("?", None) com algo que não é uma chave."""
    try:
        with open(caminho, "rb") as f:
            bruto = f.read(64 * 1024)
    except OSError:
        return None, None
    texto = bruto.decode("utf-8", "replace").lstrip("﻿")
    for linha in texto.splitlines():
        linha = linha.strip().strip("\"'").strip()
        if not linha or linha.startswith("#"):
            continue
        if not FORMATO.match(linha):
            return "?", None
        return ("anthropic" if linha.startswith("sk-ant-") else "openai"), linha
    return None, None


def gravar_privado(caminho, texto):
    os.makedirs(os.path.dirname(caminho), mode=0o700, exist_ok=True)
    tmp = caminho + ".novo"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(texto)
    os.chmod(tmp, 0o600)
    os.replace(tmp, caminho)


def ajustar_config(confdir, fornecedor, so_vazio=False):
    """Põe o fornecedor e o modelo em dicas e ficha. Se a pessoa já usava esse fornecedor,
    mantém o modelo que ela escolheu. so_vazio: só preenche o que ainda não foi escolhido."""
    caminho = os.path.join(confdir, "config.json")
    with open(caminho, encoding="utf-8") as f:
        config = json.load(f)
    padrao = PADROES[fornecedor]
    for secao in ("dicas", "ficha"):
        bloco = config.setdefault(secao, {})
        if so_vazio and bloco.get("fornecedor"):
            continue
        if bloco.get("fornecedor") != padrao["fornecedor"] or not bloco.get("modelo"):
            bloco["fornecedor"] = padrao["fornecedor"]
            bloco["modelo"] = padrao[secao]
    tmp = caminho + ".novo"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.chmod(tmp, os.stat(caminho).st_mode & 0o777)
    os.replace(tmp, caminho)


def guardar(arquivo, confdir, modelo):
    fornecedor, chave = ler_chave(arquivo)
    if fornecedor is None:
        return 1
    if chave is None:
        return 2
    gravar_privado(os.path.join(confdir, "chaves", ARQUIVO_CHAVE[fornecedor]), chave)
    ajustar_config(confdir, fornecedor)
    with open(modelo, "rb") as f:
        texto_modelo = f.read()
    with open(arquivo, "wb") as f:  # tira a chave do cartão
        f.write(texto_modelo)
    print(fornecedor)
    return 0


def ajustar(confdir):
    """Chave já guardada no aparelho (posta pelo SSH): escolhe o modelo se ainda não houver."""
    pasta = os.path.join(confdir, "chaves")
    for fornecedor in ("openai", "anthropic"):
        caminho = os.path.join(pasta, ARQUIVO_CHAVE[fornecedor])
        if os.path.isfile(caminho) and os.path.getsize(caminho) > 0:
            ajustar_config(confdir, fornecedor, so_vazio=True)
            print(fornecedor)
            return 0
    return 1


def apagar(confdir):
    pasta = os.path.join(confdir, "chaves")
    for nome in ARQUIVO_CHAVE.values():
        try:
            os.remove(os.path.join(pasta, nome))
        except FileNotFoundError:
            pass
    return 0


def idioma(db, lingua):
    if lingua not in ("pt", "en"):
        return 2
    os.makedirs(os.path.dirname(db), exist_ok=True)
    con = sqlite3.connect(db)
    try:
        con.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        con.execute("INSERT OR IGNORE INTO settings VALUES ('lang', ?)", (json.dumps(lingua),))
        con.commit()
    finally:
        con.close()
    return 0


def main(args):
    if len(args) == 2 and args[0] == "ler":
        fornecedor, chave = ler_chave(args[1])
        if fornecedor is None:
            return 1
        if chave is None:
            return 2
        print(fornecedor)
        return 0
    if len(args) == 4 and args[0] == "guardar":
        return guardar(args[1], args[2], args[3])
    if len(args) == 2 and args[0] == "ajustar":
        return ajustar(args[1])
    if len(args) == 2 and args[0] == "apagar":
        return apagar(args[1])
    if len(args) == 3 and args[0] == "idioma":
        return idioma(args[1], args[2])
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
