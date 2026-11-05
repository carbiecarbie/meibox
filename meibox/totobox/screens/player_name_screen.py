"""Ajustes > Como a Mei te chama: arcade-style letters (up/down letter, left/right position, A saves, B erases)."""
from .. import chrome
from .. import theme as T
from ..i18n import t
from ..player_name import ALPHABET, MAX_LEN, NameEditor
from .settings_screen import SETTINGS_BG

BOX_W, BOX_H, GAP = 40, 56, 6
X0 = (640 - (MAX_LEN * BOX_W + (MAX_LEN - 1) * GAP)) // 2
Y0 = 196


class PlayerNameScreen:
    def __init__(self, app):
        self.app = app
        self.editor = NameEditor(app.settings["player_name"] or "")

    def refresh(self):
        pass

    def after_game(self):
        pass

    def next_wake(self):
        return None

    def handle(self, a):
        e = self.editor
        if a in ("up", "down"):
            e.change(-1 if a == "down" else 1)
        elif a in ("left", "right"):
            e.move(-1 if a == "left" else 1)
        elif a in ("a", "start"):
            self.app.settings["player_name"] = e.saved()
            return ("pop",)
        elif a == "b":
            if not e.erase():
                return ("pop",)
        return None

    def draw(self, g):
        e = self.editor
        chrome.background(g, "settings", 150, SETTINGS_BG)
        chrome.topbar(g, self.app.status, self.app.mascot)
        g.text(16, 50, t("pname.title"), T.FONT_BOLD, 28, T.INK)
        g.text(16, 88, t("pname.help"), T.FONT_BOLD, 15, T.MUTED)
        for i in range(MAX_LEN):
            x = X0 + i * (BOX_W + GAP)
            on = i == e.pos
            ch = e.letters[i] if i < len(e.letters) else None
            g.rrect(x, Y0, BOX_W, BOX_H, 8, T.PLUM if on else T.CHIP, 235)
            if on:
                g.rframe(x, Y0, BOX_W, BOX_H, 8, T.GOLD, thick=3)
            if ch and ch != " ":
                g.text(x + BOX_W // 2, Y0 + 6, ch, T.FONT_BOLD, 32, T.GOLD if on else T.INK, align="center")
            elif i <= len(e.letters):
                g.rect(x + 10, Y0 + BOX_H - 14, BOX_W - 20, 3, T.MUTED if not on else T.GOLD)
            if on:
                # the letters before and after, so up/down feel like a wheel
                cur = ch if ch else None
                k = ALPHABET.index(cur) if cur else 0
                up = ALPHABET[(k + 1) % len(ALPHABET)] if cur else "A"
                down = ALPHABET[(k - 1) % len(ALPHABET)] if cur else "Z"
                g.text(x + BOX_W // 2, Y0 - 34, "▲ " + (up if up != " " else "_"), T.FONT_BOLD, 16, T.MUTED,
                       align="center")
                g.text(x + BOX_W // 2, Y0 + BOX_H + 6, "▼ " + (down if down != " " else "_"), T.FONT_BOLD, 16,
                       T.MUTED, align="center")
        name = e.saved()
        msg = t("pname.preview", name=name) if name else t("pname.none")
        g.text(320, Y0 + BOX_H + 54, msg, T.FONT_BOLD, 20, T.TEAL, align="center", max_w=600)
        g.text(320, Y0 + BOX_H + 84, t("pname.limit", n=MAX_LEN), T.FONT_BOLD, 13, T.MUTED, align="center")
        chrome.hints(g, [("▲▼", t("hint.letter")), ("‹ ›", t("pname.position")), ("A", t("pname.save")),
                         ("B", t("pname.erase") if e.letters else t("hint.back"))])
