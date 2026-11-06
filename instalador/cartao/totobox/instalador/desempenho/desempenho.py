#!/usr/bin/env python3
"""Desempenho dos jogos: o que foi medido no projeto desempenho/, aplicado no aparelho de quem instala.

Uso (como ark):
  desempenho.py conferir <pasta-do-pacote>   o que faria; não muda nada
  desempenho.py aplicar  <pasta-do-pacote>   aplica e guarda o necessário para desfazer
  desempenho.py remover                       desfaz (o gamelist volta no próximo início do ES)
  desempenho.py boot                          chamado antes do EmulationStation abrir: aplica ou
                                              desfaz a escolha de emulador por jogo no gamelist.xml

O que aplica:
  1. emuladores recompilados (snes9x e mGBA com PGO, gpSP novo), só os que abrem neste sistema;
     o original fica guardado;
  2. ajustes do RetroArch: vídeo sem thread por padrão e com thread nos jogos pesados
     (SNES com chip extra, lido do cabeçalho da ROM; GBA da lista medida, pelo código do jogo);
     nunca sobrescreve um ajuste que não seja deste programa;
  3. emulador por jogo (Star Fox no supafaust, F-Zero GP Legend no gpSP etc.), escrito no
     gamelist.xml antes de o ES abrir, porque o ES regrava esse arquivo ao sair.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

CASA = os.path.expanduser("~")
APP = os.path.join(CASA, ".local", "share", "meibox-desempenho")
if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "meibox-desempenho":
    # Cópia instalada (a que o passo de boot chama): a pasta dela é a do estado.
    APP = os.path.dirname(os.path.abspath(__file__))
    CASA = os.path.abspath(os.path.join(APP, "..", "..", ".."))
ESTADO = os.path.join(APP, "estado.json")
CORES = os.path.join(CASA, ".config", "retroarch", "cores")
AJUSTES = os.path.join(CASA, ".config", "retroarch", "config")
ES_SYSTEMS = ["/etc/emulationstation/es_systems.cfg", os.path.join(CASA, ".emulationstation", "es_systems.cfg")]
DROPIN = "/etc/systemd/system/emulationstation.service.d/05-meibox-desempenho.conf"
MARCA = "# meibox desempenho"
BACKUP_GL = ".antes-meibox-desempenho"

SNES_EXT = (".sfc", ".smc", ".swc", ".fig", ".bin")
GBA_EXT = (".gba", ".agb", ".bin")
CHIP = {0x0: "DSP", 0x1: "SuperFX", 0x2: "OBC1", 0x3: "SA-1", 0x4: "S-DD1",
        0x5: "S-RTC", 0xE: "outro", 0xF: "custom"}
CUSTOM = {0x00: "SPC7110", 0x01: "ST010/011", 0x02: "ST018", 0x10: "CX4"}


# ------------------------------------------------------------------ ROMs
def _pontos(rom, base):
    if base + 0x40 > len(rom):
        return -1, None
    h = rom[base:base + 0x40]
    s = 4 if ((h[0x1E] | h[0x1F] << 8) ^ (h[0x1C] | h[0x1D] << 8)) == 0xFFFF else 0
    modo = h[0x15]
    if (base == 0x7FC0 and modo & 1 == 0) or (base in (0xFFC0, 0x40FFC0) and modo & 1):
        s += 2
    if all(32 <= c < 127 for c in h[:21]):
        s += 1
    return s, h


def snes_cabecalho(rom, tamanho=None):
    """(título interno, chip extra ou None), do mesmo jeito que desempenho/device/bench/snes-chips.py.
    tamanho: o da ROM inteira, quando rom é só o começo dela (para ver o cabeçalho de copiadora)."""
    if (len(rom) if tamanho is None else tamanho) % 1024 == 512:
        rom = rom[512:]
    s, h, base = max((_pontos(rom, b) + (b,) for b in (0x7FC0, 0xFFC0, 0x40FFC0)), key=lambda t: t[0])
    if h is None:
        return None, None
    titulo = h[:21].decode("ascii", "replace").strip()
    t = h[0x16]
    if t & 0x0F < 3:
        return titulo, None
    nome = CHIP.get(t >> 4, f"?{t:02x}")
    if nome == "custom" and base >= 0x10:
        nome = CUSTOM.get(rom[base - 1], f"custom{rom[base - 1]:02x}")
    return titulo, nome


def ler_rom(caminho, extensoes, limite=None):
    """Bytes da ROM (solta ou primeiro arquivo certo dentro de um .zip); None se não der."""
    baixo = caminho.lower()
    try:
        if baixo.endswith(".zip"):
            with zipfile.ZipFile(caminho) as z:
                for n in z.namelist():
                    if n.lower().endswith(extensoes):
                        with z.open(n) as f:
                            return f.read(limite) if limite else f.read()
        elif baixo.endswith(extensoes):
            with open(caminho, "rb") as f:
                return f.read(limite) if limite else f.read()
    except (OSError, zipfile.BadZipFile, RuntimeError, EOFError):
        pass
    return None


def ler_snes(caminho):
    """(começo da ROM, tamanho total). Os cabeçalhos LoROM e HiROM ficam nos primeiros 64 KB;
    só uma ROM de mais de 4 MB (ExHiROM) precisa ser lida inteira."""
    baixo = caminho.lower()
    try:
        if baixo.endswith(".zip"):
            with zipfile.ZipFile(caminho) as z:
                for info in z.infolist():
                    if info.filename.lower().endswith(SNES_EXT):
                        tamanho = info.file_size
                        with z.open(info) as f:
                            return f.read(tamanho if tamanho > 0x400200 else 0x10200), tamanho
        elif baixo.endswith(SNES_EXT):
            tamanho = os.path.getsize(caminho)
            with open(caminho, "rb") as f:
                return f.read(tamanho if tamanho > 0x400200 else 0x10200), tamanho
    except (OSError, zipfile.BadZipFile, RuntimeError, EOFError):
        pass
    return None, 0


def gba_codigo(caminho):
    h = ler_rom(caminho, GBA_EXT, 0xC0)
    if not h or len(h) < 0xB0:
        return None
    return h[0xAC:0xB0].decode("ascii", "replace")


def roms_em(pasta, extensoes):
    """(caminho relativo à pasta do sistema, caminho completo), incluindo subpastas."""
    for raiz, pastas, nomes in os.walk(pasta):
        pastas[:] = sorted(p for p in pastas if not p.startswith("."))
        for n in sorted(nomes):
            if n.lower().endswith(extensoes + (".zip",)):
                cheio = os.path.join(raiz, n)
                yield os.path.relpath(cheio, pasta).replace(os.sep, "/"), cheio


# ------------------------------------------------------------------ EmulationStation
def sistemas(caminhos=None):
    """[{nome, pasta, emuladores: {emulador: [cores]}}] do es_systems.cfg."""
    for c in caminhos or ES_SYSTEMS:
        if os.path.exists(c):
            with open(c, encoding="utf-8", errors="replace") as f:
                texto = f.read()
            break
    else:
        return []
    saida = []
    for bloco in re.findall(r"<system>.*?</system>", texto, re.S):
        nome = re.search(r"<name>(.*?)</name>", bloco)
        pasta = re.search(r"<path>(.*?)</path>", bloco)
        if not nome or not pasta:
            continue
        emus = {}
        for m in re.finditer(r'<emulator name="(.*?)".*?</emulator>', bloco, re.S):
            emus[m.group(1)] = [c.strip() for c in re.findall(r"<core(?:\s[^>]*)?>(.*?)</core>", m.group(0))]
        saida.append({"nome": nome.group(1).strip(), "pasta": pasta.group(1).strip().rstrip("/"),
                      "emuladores": emus})
    return saida


def emulador_com(sistema, core):
    for emu, cores in sistema["emuladores"].items():
        if core in cores:
            return emu
    return None


def usa_core(sistema, core):
    return emulador_com(sistema, core) is not None


# ------------------------------------------------------------------ estado
def ler_estado():
    try:
        with open(ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def gravar_estado(estado):
    os.makedirs(APP, exist_ok=True)
    tmp = ESTADO + ".novo"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ESTADO)


def sha(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def abre_aqui(caminho):
    """O emulador carrega neste sistema? (num processo à parte, para um erro não derrubar este)."""
    try:
        r = subprocess.run([sys.executable, "-I", "-c", "import ctypes, sys; ctypes.CDLL(sys.argv[1])", caminho],
                           capture_output=True, timeout=20)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ------------------------------------------------------------------ plano
def planejar(pacote, lista_sistemas=None):
    """Tudo o que aplicar faria, sem mudar nada."""
    with open(os.path.join(pacote, "regras.json"), encoding="utf-8") as f:
        regras = json.load(f)
    sis = sistemas() if lista_sistemas is None else lista_sistemas
    plano = {"cores": [], "ajustes": [], "gamelist": [], "avisos": []}

    # 1. emuladores
    for destino, origem in regras["cores"].items():
        nosso = os.path.join(pacote, "cores", origem)
        atual = os.path.join(CORES, destino)
        if not os.path.exists(nosso):
            continue
        if not os.path.exists(atual):
            continue  # o sistema não usa esse core; não acrescenta nada novo
        item = {"core": destino, "origem": nosso, "sha": sha(nosso)}
        if sha(atual) == item["sha"]:
            item["situacao"] = "ja_esta"
        elif abre_aqui(nosso):
            item["situacao"] = "trocar"
        else:
            item["situacao"] = "nao_abre"
        plano["cores"].append(item)
    gpsp_novo = any(c["core"] == "gpsp_libretro.so" and c["situacao"] in ("trocar", "ja_esta")
                    for c in plano["cores"])

    # 2. ajustes de vídeo
    def ajuste(pasta_core, nome, thread):
        plano["ajustes"].append({"arquivo": os.path.join(AJUSTES, pasta_core, nome + ".cfg"),
                                 "thread": thread})
    for pasta_core in regras["padrao_sem_thread"]:
        ajuste(pasta_core, pasta_core, False)
    for pasta_core, pastas in regras["pasta_com_thread"].items():
        for p in pastas:
            ajuste(pasta_core, p, True)

    chips = set(regras["snes_chips_com_thread"])
    por_titulo = {k: v for k, v in regras["snes_core_por_titulo"].items() if not k.startswith("_")}
    chip_titulo = regras["snes_core_por_titulo"].get("_chip")
    gba_thread = set(regras["gba_com_thread"])
    gba_core = regras["gba_core_por_codigo"]
    vistos = set()
    for s in sis:
        pasta = s["pasta"]
        if not os.path.isdir(pasta) or pasta in vistos:
            continue
        if usa_core(s, "snes9x"):
            vistos.add(pasta)
            for rel, cheio in roms_em(pasta, SNES_EXT):
                rom, tamanho = ler_snes(cheio)
                if not rom:
                    continue
                titulo, chip = snes_cabecalho(rom, tamanho)
                if chip in chips:
                    ajuste("Snes9x", os.path.splitext(os.path.basename(rel))[0], True)
                core = por_titulo.get((titulo or "").upper())
                if core and chip == chip_titulo:
                    emu = emulador_com(s, core)
                    if emu and os.path.exists(os.path.join(CORES, core + "_libretro.so")):
                        plano["gamelist"].append({"gamelist": os.path.join(pasta, "gamelist.xml"),
                                                  "rom": rel, "emulador": emu, "core": core})
        elif usa_core(s, "mgba") or usa_core(s, "mgba_rumble"):
            vistos.add(pasta)
            for rel, cheio in roms_em(pasta, GBA_EXT):
                codigo = gba_codigo(cheio)
                if not codigo:
                    continue
                if codigo[:3] in gba_thread:
                    ajuste("mGBA", os.path.splitext(os.path.basename(rel))[0], True)
                regra = gba_core.get(codigo[:3])
                if regra and gpsp_novo:
                    emu = emulador_com(s, regra["core"])
                    if emu:
                        plano["gamelist"].append({"gamelist": os.path.join(pasta, "gamelist.xml"),
                                                  "rom": rel, "emulador": emu, "core": regra["core"]})

    for a in plano["ajustes"]:
        if not os.path.exists(a["arquivo"]):
            a["situacao"] = "criar"
        else:
            with open(a["arquivo"], encoding="utf-8", errors="replace") as f:
                nosso = MARCA in f.read()
            a["situacao"] = "atualizar" if nosso else "manter_da_pessoa"
    return plano


# ------------------------------------------------------------------ aplicar / remover
def aplicar(pacote, plano=None):
    plano = plano or planejar(pacote)
    estado = ler_estado()
    backup = os.path.join(APP, "originais")
    os.makedirs(backup, exist_ok=True)
    cores = estado.get("cores", {})
    for c in plano["cores"]:
        if c["situacao"] != "trocar":
            continue
        atual = os.path.join(CORES, c["core"])
        guardado = os.path.join(backup, c["core"])
        if not os.path.exists(guardado):
            shutil.copy2(atual, guardado)
        tmp = atual + ".meibox-novo"
        shutil.copy2(c["origem"], tmp)
        os.replace(tmp, atual)
        cores[c["core"]] = {"sha": c["sha"], "original": guardado}
    estado["cores"] = cores

    ajustes = set(estado.get("ajustes", []))
    for a in plano["ajustes"]:
        if a["situacao"] == "manter_da_pessoa":
            continue
        os.makedirs(os.path.dirname(a["arquivo"]), exist_ok=True)
        with open(a["arquivo"], "w", encoding="utf-8") as f:
            f.write(f'{MARCA}: {"com" if a["thread"] else "sem"} thread de vídeo\n'
                    f'video_threaded = "{"true" if a["thread"] else "false"}"\n')
        ajustes.add(a["arquivo"])
    estado["ajustes"] = sorted(ajustes)

    estado["gamelist_desejado"] = plano["gamelist"]
    estado["gamelist_pendente"] = "aplicar"
    gravar_estado(estado)
    instalar_gancho()
    return plano


def remover():
    if not os.path.exists(ESTADO):
        return  # nunca foi aplicado
    estado = ler_estado()
    for nome, c in estado.get("cores", {}).items():
        atual = os.path.join(CORES, nome)
        if os.path.exists(c["original"]) and os.path.exists(atual) and sha(atual) == c["sha"]:
            tmp = atual + ".meibox-volta"
            shutil.copy2(c["original"], tmp)
            os.replace(tmp, atual)
    estado["cores"] = {}
    for arq in estado.get("ajustes", []):
        try:
            with open(arq, encoding="utf-8", errors="replace") as f:
                nosso = MARCA in f.read()
            if nosso:
                os.remove(arq)
        except OSError:
            pass
        try:
            os.rmdir(os.path.dirname(arq))
        except OSError:
            pass
    estado["ajustes"] = []
    estado["gamelist_desejado"] = []
    estado["gamelist_pendente"] = "remover"
    gravar_estado(estado)
    instalar_gancho()


def instalar_gancho():
    """Põe o desempenho.py fora do cartão e o passo antes do ES (drop-in do systemd)."""
    os.makedirs(APP, exist_ok=True)
    proprio = os.path.abspath(__file__)
    alvo = os.path.join(APP, "desempenho.py")
    if proprio != alvo:
        shutil.copy2(proprio, alvo)
    texto = ("# Meibox: escolhe o emulador por jogo no gamelist.xml antes de o EmulationStation abrir.\n"
             "# Some sozinho depois de uma remoção. Remover este arquivo desliga o passo.\n"
             "[Service]\n"
             f"ExecStartPre=-/usr/bin/python3 -I {alvo} boot\n")
    try:
        with open(DROPIN, encoding="utf-8") as f:
            if f.read() == texto:
                return
    except OSError:
        pass
    subprocess.run(["sudo", "-n", "mkdir", "-p", os.path.dirname(DROPIN)], check=True)
    subprocess.run(["sudo", "-n", "tee", DROPIN], input=texto.encode(), stdout=subprocess.DEVNULL, check=True)
    subprocess.run(["sudo", "-n", "systemctl", "daemon-reload"], check=True)


# ------------------------------------------------------------------ gamelist (com o ES fechado)
def _padrao_jogo(rom):
    return re.compile(r"(<game>(?:(?!</game>).)*?<path>\./" + re.escape(rom) + r"</path>.*?)(</game>)", re.S)


def gamelist_por(texto, rom, emulador, core):
    """Põe <emulator>/<core> no jogo (cria uma entrada mínima se não houver)."""
    pat = _padrao_jogo(rom)
    m = pat.search(texto)
    if not m:
        caminho = rom.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        pat = _padrao_jogo(caminho)
        m = pat.search(texto)
    if not m:
        caminho = rom.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if "</gameList>" not in texto:
            texto = '<?xml version="1.0"?>\n<gameList>\n</gameList>\n'
        texto = texto.replace("</gameList>", f"\t<game>\n\t\t<path>./{caminho}</path>\n\t</game>\n</gameList>", 1)
        m = pat.search(texto)
    corpo = re.sub(r"\s*<(emulator|core)>.*?</\1>", "", m.group(1))
    corpo = corpo.rstrip() + f"\n\t\t<emulator>{emulador}</emulator>\n\t\t<core>{core}</core>\n\t"
    return texto[:m.start()] + corpo + m.group(2) + texto[m.end():]


def gamelist_tirar(texto, rom, core):
    """Tira <emulator>/<core> do jogo, só se ainda for o core que este programa pôs."""
    for caminho in (rom, rom.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")):
        m = _padrao_jogo(caminho).search(texto)
        if m:
            if f"<core>{core}</core>" not in m.group(1):
                return texto
            corpo = re.sub(r"\s*<(emulator|core)>.*?</\1>", "", m.group(1))
            return texto[:m.start()] + corpo.rstrip() + "\n\t" + m.group(2) + texto[m.end():]
    return texto


def boot():
    estado = ler_estado()
    acao = estado.get("gamelist_pendente")
    if not acao:
        return 0
    feitos = estado.get("gamelist_feito", [])
    desejados = estado.get("gamelist_desejado", [])
    chave = lambda g: (g["gamelist"], g["rom"])
    quer = {chave(g): g for g in desejados}
    por_arquivo = {}
    for g in feitos:  # tira o que não é mais desejado
        if chave(g) not in quer or quer[chave(g)]["core"] != g["core"]:
            por_arquivo.setdefault(g["gamelist"], []).append(("tirar", g))
    for g in desejados:
        por_arquivo.setdefault(g["gamelist"], []).append(("por", g))
    for gl, ops in por_arquivo.items():
        try:
            if os.path.exists(gl):
                with open(gl, encoding="utf-8") as f:
                    texto = f.read()
                if not os.path.exists(gl + BACKUP_GL):
                    shutil.copy2(gl, gl + BACKUP_GL)
            else:
                texto = '<?xml version="1.0"?>\n<gameList>\n</gameList>\n'
            for op, g in ops:
                if op == "tirar":
                    texto = gamelist_tirar(texto, g["rom"], g["core"])
                else:
                    texto = gamelist_por(texto, g["rom"], g["emulador"], g["core"])
            tmp = gl + ".meibox-novo"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(texto)
            os.replace(tmp, gl)
        except OSError as e:
            print(f"gamelist {gl}: {e}", file=sys.stderr)
    estado["gamelist_feito"] = desejados
    estado["gamelist_pendente"] = None
    if acao == "remover":
        subprocess.run(["sudo", "-n", "rm", "-f", DROPIN])
        subprocess.run(["sudo", "-n", "systemctl", "daemon-reload"])
        shutil.rmtree(APP, ignore_errors=True)
        return 0
    gravar_estado(estado)
    return 0


# ------------------------------------------------------------------ saída
NOMES = {"snes9x_libretro.so": "snes9x", "mgba_libretro.so": "mGBA",
         "mgba_rumble_libretro.so": "mGBA (rumble)", "gpsp_libretro.so": "gpSP"}


def resumo(plano, lingua="pt"):
    pt = lingua != "en"
    trocar = [NOMES.get(c["core"], c["core"]) for c in plano["cores"] if c["situacao"] in ("trocar", "ja_esta")]
    nao = [NOMES.get(c["core"], c["core"]) for c in plano["cores"] if c["situacao"] == "nao_abre"]
    por_jogo = sum(1 for a in plano["ajustes"] if a["thread"] and a["situacao"] != "manter_da_pessoa")
    da_pessoa = sum(1 for a in plano["ajustes"] if a["situacao"] == "manter_da_pessoa")
    linhas = []
    if trocar:
        linhas.append(("- Emuladores mais rápidos: " if pt else "- Faster emulators: ") + ", ".join(trocar) + ".")
    if nao:
        linhas.append(("- Mantidos os originais (este sistema é antigo para eles): "
                       if pt else "- Kept the originals (this system is too old for them): ") + ", ".join(nao) + ".")
    linhas.append((f"- Ajustes de vídeo: resposta mais rápida no botão; {por_jogo} jogos pesados com folga extra."
                   if pt else f"- Video settings: quicker button response; {por_jogo} heavy games get extra headroom."))
    if plano["gamelist"]:
        linhas.append((f"- {len(plano['gamelist'])} jogos com um emulador mais leve (vale no próximo início)."
                       if pt else f"- {len(plano['gamelist'])} games on a lighter emulator (from the next start)."))
    if da_pessoa:
        linhas.append((f"- {da_pessoa} ajustes seus foram mantidos." if pt else f"- Kept {da_pessoa} of your own settings."))
    return "\n".join(linhas)


def main(args):
    if len(args) >= 2 and args[0] in ("conferir", "aplicar"):
        lingua = args[2] if len(args) > 2 else "pt"
        if args[0] == "conferir":
            plano = planejar(args[1])
        else:
            plano = aplicar(args[1])
        print(resumo(plano, lingua))
        return 0
    if args == ["remover"]:
        remover()
        return 0
    if args == ["boot"]:
        return boot()
    if args == ["instalado"]:
        return 0 if os.path.exists(ESTADO) else 1
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
