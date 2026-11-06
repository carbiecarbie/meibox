#!/usr/bin/env python3
"""Monta o ZIP da release: o que a pessoa copia para o cartão SD.

Uso: python scripts/montar_zip.py [--repo PASTA] [--saida PASTA] [--cores PASTA] [--fontes]
  --repo   raiz do repositório Meibox, com meibox/ e copiloto/ (padrão: a pasta acima de
           instalador/ quando roda dentro do repositório; senão ../meibox)
  --saida  onde gravar Meibox-<versão>.zip (padrão: dist/ ao lado deste projeto)
  --cores  pasta com os emuladores recompilados (snes9x, mgba e gpsp _libretro.so), que não
           vão para o git (padrão: cores/ ao lado deste projeto)
  --fontes também monta Meibox-<versão>-fontes-dos-emuladores.zip: o código-fonte exato de cada
           emulador (baixado do GitHub do libretro) e os scripts de compilação. Vai na release,
           ao lado do ZIP, como pedem a GPL (gpSP) e a MPL (mGBA).

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

CORES = ["snes9x_libretro.so", "mgba_libretro.so", "gpsp_libretro.so"]
FONTES = {  # projeto do libretro: commit compilado (ver desempenho/licencas/LEIA-ME.txt)
    "snes9x": "fae2fea08f74180759ef540ee94259213f503480",
    "mgba": "7a12d6d4b9acb14c0ae62c9166b6a2f3d08007f6",
    "gpsp": "5819380c2ffb0900219d700a382ee68c464ebb99",
}
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


def montar_fontes(repo, saida, versao):
    """Código-fonte de cada commit compilado + scripts de compilação, num ZIP à parte."""
    import urllib.request
    caminho = os.path.join(saida, f"Meibox-{versao}-fontes-dos-emuladores.zip")
    raiz = f"Meibox-{versao}-fontes-dos-emuladores"
    with zipfile.ZipFile(caminho, "w") as z:
        gravar(z, os.path.join(CARTAO, "totobox", "instalador", "desempenho", "licencas", "LEIA-ME.txt"),
               f"{raiz}/LEIA-ME.txt")
        for nome in os.listdir(os.path.join(CARTAO, "totobox", "instalador", "desempenho", "licencas")):
            if nome != "LEIA-ME.txt":
                gravar(z, os.path.join(CARTAO, "totobox", "instalador", "desempenho", "licencas", nome),
                       f"{raiz}/licencas/{nome}")
        for script in ("build-core.sh", "build-all.sh"):
            gravar(z, os.path.join(repo, "desempenho", "device", "build", script), f"{raiz}/compilacao/{script}")
        for projeto, commit in FONTES.items():
            url = f"https://codeload.github.com/libretro/{projeto}/tar.gz/{commit}"
            print(f"baixando {projeto} {commit[:7]}...")
            with urllib.request.urlopen(url, timeout=120) as r:
                dados = r.read()
            info = zipfile.ZipInfo(f"{raiz}/{projeto}-{commit[:7]}.tar.gz", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED  # já é comprimido
            z.writestr(info, dados)
    print(f"{caminho}  ({os.path.getsize(caminho) / 1e6:.1f} MB)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=achar_repo())
    p.add_argument("--saida", default=os.path.join(AQUI, "dist"))
    p.add_argument("--cores", default=os.path.join(AQUI, "cores"))
    p.add_argument("--fontes", action="store_true")
    a = p.parse_args()
    for c in CORES:
        if not os.path.isfile(os.path.join(a.cores, c)):
            sys.exit(f"faltou o emulador {c} em {a.cores} (copie do aparelho; ver instalador/README.md)")
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
        desemp = os.path.join(inst, "desempenho")
        for origem, rel in arquivos(desemp, ["desempenho.py", "regras.json", "licencas"]):
            gravar(z, origem, f"{raiz}/totobox/instalador/desempenho/{rel}")
        for c in CORES:
            gravar(z, os.path.join(a.cores, c), f"{raiz}/totobox/instalador/desempenho/cores/{c}")
    with zipfile.ZipFile(zip_path) as z:
        n = len(z.namelist())
    print(f"{zip_path}  ({n} arquivos, {os.path.getsize(zip_path) / 1e6:.1f} MB)")
    if a.fontes:
        montar_fontes(a.repo, a.saida, v)


if __name__ == "__main__":
    main()
