"""Palette and fonts. Meibox look: vaporwave collage of Mei (photos cut out), purple + neon pink/cyan, gold title."""
import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(APP_DIR, "assets")

BG = (31, 25, 39)
PANEL = (20, 14, 26)
PLUM = (64, 40, 62)
CHIP = (46, 36, 54)
MAGENTA = (192, 85, 154)
TEAL = (123, 196, 184)
CYAN = (141, 227, 214)
GOLD = (230, 181, 74)
INK = (243, 235, 221)
MUTED = (179, 164, 184)
SOFT = (217, 206, 220)
SHADOW = (26, 16, 32)
DARK_TEXT = (42, 27, 46)

# Fonts chosen by the user on 04/11 (option 2): Baloo 2 Bold for titles and labels, Nunito Bold for text.
# Both SIL OFL 1.1, licences next to them in assets/fonts. Env vars still override for tests.
FONTS = os.path.join(ASSETS, "fonts")
FONT_BOLD = os.environ.get("TOTOBOX_FONT_BOLD", os.path.join(FONTS, "Baloo2-Bold.ttf"))
FONT_TEXT = os.environ.get("TOTOBOX_FONT_TEXT", os.path.join(FONTS, "Nunito-Bold.ttf"))

NAME = "MEIBOX"
BACKGROUND = os.path.join(ASSETS, "meibox", "fundo-meibox.jpg")
MASCOT = os.path.join(ASSETS, "meibox", "mascote-mei.png")  # Mei's face sticker, made in tools/meibox_studio.html
MEI_VIDEO = os.path.join(ASSETS, "meibox", "mei-brincando.meiv")  # Konami easter egg, tools/make_mei_video.py
