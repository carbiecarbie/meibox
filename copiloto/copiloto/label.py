"""O `label` do RetroArch: "<system_id>__<nome do arquivo>" -> console legível, jogo limpo, região.

O system_id vem do campo `systemid` do .info do núcleo (ex.: super_nes, game_boy_advance).
O nome vem da playlist ou do arquivo da ROM sem extensão, com marcas como "(USA)" e "[!]".
"""
import os
import re
import unicodedata

CONSOLES = {
    "super_nes": "Super Nintendo",
    "nes": "NES",
    "game_boy": "Game Boy",
    "game_boy_color": "Game Boy Color",
    "game_boy_advance": "Game Boy Advance",
    "nintendo_64": "Nintendo 64",
    "nintendo_ds": "Nintendo DS",
    "virtual_boy": "Virtual Boy",
    "pokemon_mini": "Pokémon Mini",
    "mega_drive": "Mega Drive",
    "sega_genesis": "Mega Drive",
    "master_system": "Master System",
    "game_gear": "Game Gear",
    "sega_cd": "Sega CD",
    "sega_32x": "Sega 32X",
    "sega_saturn": "Sega Saturn",
    "dreamcast": "Dreamcast",
    "playstation": "PlayStation",
    "playstation_portable": "PSP",
    "pc_engine": "PC Engine",
    "pc_fx": "PC-FX",
    "neo_geo_pocket": "Neo Geo Pocket",
    "neogeo": "Neo Geo",
    "fb_alpha": "Arcade",
    "mame": "Arcade",
    "atari_2600": "Atari 2600",
    "atari_5200": "Atari 5200",
    "atari_7800": "Atari 7800",
    "atari_lynx": "Atari Lynx",
    "atari_st": "Atari ST",
    "wonderswan": "WonderSwan",
    "colecovision": "ColecoVision",
    "intellivision": "Intellivision",
    "msx": "MSX",
    "commodore_amiga": "Amiga",
    "commodore_c64": "Commodore 64",
    "dos": "DOS",
    "zx_spectrum": "ZX Spectrum",
    "3do": "3DO",
    "vectrex": "Vectrex",
    "odyssey2": "Odyssey²",
    "pico8": "PICO-8",
}

# Palavras que marcam a região/versão dentro dos parênteses do nome (padrão No-Intro).
_REGIOES = ("USA", "Europe", "Japan", "World", "Brazil", "Australia", "Korea", "China",
            "Asia", "France", "Germany", "Spain", "Italy", "Canada", "Netherlands", "Sweden")
_MARCAS = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
_EXTENSOES = {".zip", ".7z", ".sfc", ".smc", ".gba", ".gb", ".gbc", ".nes", ".md", ".bin",
              ".gen", ".sms", ".gg", ".n64", ".z64", ".v64", ".pce", ".chd", ".cue", ".iso"}


def separar(label):
    """Devolve (system_id, nome_bruto). Sem "__" o label todo é o nome."""
    label = (label or "").strip()
    sysid, sep, nome = label.partition("__")
    if not sep:
        return "", label
    return sysid.strip().lower(), nome.strip()


def console_legivel(system_id):
    if not system_id:
        return ""
    return CONSOLES.get(system_id, system_id.replace("_", " ").title())


def limpar_nome(nome):
    """Tira caminho, extensão e as marcas entre () e [] ("(USA)", "[!]", "(En,Fr,De)")."""
    nome = os.path.basename(nome.replace("\\", "/"))
    raiz, ext = os.path.splitext(nome)
    if ext.lower() in _EXTENSOES:
        nome = raiz
    limpo = re.sub(r"\s+", " ", _MARCAS.sub("", nome)).strip(" -_")
    return limpo or nome.strip()


def regiao(nome):
    """Primeiro grupo entre parênteses que cita uma região conhecida, ex.: "USA, Australia"."""
    for grupo in re.findall(r"\(([^)]*)\)", nome or ""):
        partes = [p.strip() for p in grupo.split(",")]
        if any(p in _REGIOES for p in partes):
            return grupo.strip()
    return ""


def interpretar(label):
    """label -> dict com console, system_id, jogo (limpo), regiao e bruto."""
    sysid, bruto = separar(label)
    return {
        "system_id": sysid,
        "console": console_legivel(sysid),
        "jogo": limpar_nome(bruto) if bruto else "",
        "regiao": regiao(bruto),
        "bruto": bruto,
    }


_PROIBIDOS_EXFAT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def nome_arquivo(texto, limite=80):
    """Nome seguro para exFAT, mantendo acentos (pasta de guias, lida pelo usuário no PC)."""
    s = _PROIBIDOS_EXFAT.sub("", texto or "")
    s = re.sub(r"\s+", " ", s).strip().rstrip(". ")
    s = s[:limite].rstrip(". ")
    return s or "Sem nome"


def nome_ascii(texto, limite=60):
    """Nome só com letras, números e hífens (arquivo da dica, design 5.7)."""
    s = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return s[:limite].strip("-") or "jogo"
