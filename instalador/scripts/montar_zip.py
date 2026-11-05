#!/usr/bin/env python3
"""Monta o ZIP da release: o que a pessoa copia para o cartão SD.

Uso: python scripts/montar_zip.py [--repo PASTA] [--saida PASTA]
  --repo   raiz do repositório Meibox, com meibox/ e copiloto/ (padrão: a pasta acima de
           instalador/ quando roda dentro do repositório; senão ../meibox)
  --saida  onde gravar Meibox-<versão>.zip (padrão: dist/ ao lado deste projeto)

Dentro do ZIP (uma pasta Meibox-<versão>/):
  LEIA-ME.txt, READ-ME.txt, PARA-SUA-IA.md
  tools/Instalar Meibox.sh                 -> aparece em Options > Tools
  totobox/chave-da-ia.txt                  -> onde a pessoa cola a chave (opcional)
  totobox/instalador/...                   -> instalador + Meibox + Copiloto (sem testes)
"""
import argparse
import os
import re
import sys
import zipfile

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # r36s-instalador ou instalador/
CARTAO = os.path.join(AQUI, "cartao")
TEXTOS = os.path.join(AQUI, "zip")

MEIBOX = ["totobox", "assets", "lang", "frases", "device"]
COPILOTO = ["copiloto", "assets", "mei_copiloto.py", "device"]
FORA = {"__pycache__", ".pytest_cache", "dev-run.sh", "menu-test.sh"}
TEXTO = {".sh", ".py", ".txt", ".md", ".json", ".gptk", ".service", ".nft", ".cfg", ".csv"}


def versao():
    with open(os.path.join(CARTAO, "totobox", "instalador", "instalar.sh"), encoding="utf-8") as f:
        return re.search(r"^VERSAO=(\S+)", f.read(), re.M).group(1)


def achar_repo():
    pai = os.path.dirname(AQUI)
    if os.path.isdir(os.path.join(pai, "meibox")) and os.path.isdir(os.path.join(pai, "copiloto")):
        return pai
    return os.path.join(pai, "meibox")


def arquivos(base, itens):
    """(caminho no disco, caminho relativo) de cada arquivo dos itens, sem lixo de dev."""
    for item in itens:
        origem = os.path.join(base, item)
        if os.path.isfile(origem):
            yield origem, item
            continue
        if not os.path.isdir(origem):
            sys.exit(f"faltou {origem}")
        for raiz, pastas, nomes in os.walk(origem):
            pastas[:] = sorted(p for p in pastas if p not in FORA)
            for nome in sorted(nomes):
                if nome in FORA or nome.endswith(".pyc"):
                    continue
                caminho = os.path.join(raiz, nome)
                yield caminho, os.path.relpath(caminho, base).replace(os.sep, "/")


def gravar(z, origem, destino):
    info = zipfile.ZipInfo(destino, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3  # Unix, para valer a permissão abaixo
    executavel = destino.endswith(".sh") or destino.endswith(".py")
    info.external_attr = (0o100755 if executavel else 0o100644) << 16
    with open(origem, "rb") as f:
        dados = f.read()
    if os.path.splitext(destino)[1] in TEXTO:
        dados = dados.replace(b"\r\n", b"\n")  # roda em Linux: só LF
    z.writestr(info, dados)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=achar_repo())
    p.add_argument("--saida", default=os.path.join(AQUI, "dist"))
    a = p.parse_args()
    v = versao()
    raiz = f"Meibox-{v}"
    os.makedirs(a.saida, exist_ok=True)
    zip_path = os.path.join(a.saida, f"{raiz}.zip")
    inst = os.path.join(CARTAO, "totobox", "instalador")
    modelo = os.path.join(CARTAO, "totobox", "chave-da-ia.txt")
    with zipfile.ZipFile(zip_path, "w") as z:
        for nome in ("LEIA-ME.txt", "READ-ME.txt", "PARA-SUA-IA.md"):
            gravar(z, os.path.join(TEXTOS, nome), f"{raiz}/{nome}")
        gravar(z, os.path.join(CARTAO, "tools", "Instalar Meibox.sh"), f"{raiz}/tools/Instalar Meibox.sh")
        gravar(z, modelo, f"{raiz}/totobox/chave-da-ia.txt")
        gravar(z, modelo, f"{raiz}/totobox/instalador/chave-da-ia.modelo.txt")
        for nome in ("abrir.sh", "instalar.sh", "chave.py", "teclas.gptk"):
            gravar(z, os.path.join(inst, nome), f"{raiz}/totobox/instalador/{nome}")
        for parte, itens in (("meibox", MEIBOX), ("copiloto", COPILOTO)):
            for origem, rel in arquivos(os.path.join(a.repo, parte), itens):
                gravar(z, origem, f"{raiz}/totobox/instalador/{parte}/{rel}")
    with zipfile.ZipFile(zip_path) as z:
        n = len(z.namelist())
    print(f"{zip_path}  ({n} arquivos, {os.path.getsize(zip_path) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
