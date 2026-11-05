"""Tela E, Ajustes: changes apply at once and are saved."""
from .. import chrome, i18n
from .. import theme as T
from ..i18n import t

SETTINGS_BG = [([(0, (20, 14, 26, 245)), (0.62, (20, 14, 26, 230)), (1, (20, 14, 26, 90))], True,
                 (0, 0, 640, 480))]

ROW_H = 38  # 9 rows + the gap before "exit" fit above the hint bar (y 450)
OPTIONS = [
    ("lang", ["pt", "en"]),
    ("player_name", None),
    ("sounds", [True, False]),
    ("phrases", ["both", "mine", "default"]),
    ("show_temp", [True, False]),
    ("clock", ["24", "12"]),
    ("roulette", None),
    ("refresh", None),
    ("exit", None),
]
LABELS = {"lang": "settings.lang", "player_name": "settings.player_name", "sounds": "settings.sounds", "phrases": "settings.phrases",
          "show_temp": "settings.temp", "clock": "settings.clock", "roulette": "settings.roulette",
          "refresh": "settings.refresh",
          "exit": "settings.exit"}


def value_label(key, value):
    if key == "lang":
        return t(f"settings.lang.{value}")
    if key == "sounds":
        return t("on" if value else "off")
    if key == "phrases":
        return t(f"settings.phrases.{value}")
    if key == "show_temp":
        return t("yes" if value else "no")
    if key == "clock":
        return t(f"clock.{value}")
    return ""


class SettingsScreen:
    def __init__(self, app):
        self.app = app
        self.sel = 0
        self.notice = None

    def after_game(self):
        pass

    def next_wake(self):
        return None

    def handle(self, a):
        key, values = OPTIONS[self.sel]
        if a in ("up", "down"):
            self.sel = (self.sel + (1 if a == "down" else -1)) % len(OPTIONS)
            self.notice = None
        elif a in ("left", "right") and values:
            cur = self.app.settings[key]
            i = values.index(cur) if cur in values else 0
            self.app.settings[key] = values[(i + (1 if a == "right" else -1)) % len(values)]
            self.app.apply_settings()
        elif a == "a" and key == "player_name":
            return ("push", "player_name")
        elif a == "a" and key == "roulette":
            return ("push", "roulette_systems")
        elif a == "a" and key == "refresh":
            n = self.app.refresh_index()
            self.notice = t("settings.refreshed", n=i18n.num(n))
        elif a == "a" and key == "exit":
            return ("quit",)
        elif a == "b":
            return ("pop",)
        return None

    def draw(self, g):
        chrome.background(g, "settings", 150, SETTINGS_BG)
        chrome.topbar(g, self.app.status, self.app.mascot)
        g.text(16, 50, t("settings.title"), T.FONT_BOLD, 28, T.INK)
        y = 86
        for i, (key, values) in enumerate(OPTIONS):
            on = i == self.sel
            if key == "exit":
                y += 10
            if on:
                g.rrect(16, y, 420, ROW_H - 2, 9, T.PLUM)
                g.rect(16, y + 4, 4, ROW_H - 10, T.CYAN)
            color = T.MAGENTA if key == "exit" else (T.INK if on else T.SOFT)
            g.text(30, y + 7, t(LABELS[key]), T.FONT_BOLD, 18, color)
            if key == "player_name":
                name = self.app.settings["player_name"]
                g.text(424, y + 8, (name or t("settings.player_name.none")) + (" ›" if on else ""), T.FONT_BOLD, 17,
                       T.GOLD if on else T.TEAL, align="right", max_w=200)
            if key == "roulette":
                chosen = self.app.settings["roulette_systems"]
                label = t("rsys.default") if chosen is None else t("rsys.count1" if len(chosen) == 1 else "rsys.count", n=len(chosen))
                g.text(424, y + 8, label + (" ›" if on else ""), T.FONT_BOLD, 17, T.GOLD if on else T.TEAL,
                       align="right")
            if values:
                label = value_label(key, self.app.settings[key])
                g.text(424, y + 8, ("‹ " if on else "") + label + (" ›" if on else ""), T.FONT_BOLD, 17,
                       T.GOLD if on else T.TEAL, align="right")
            y += ROW_H
        if self.notice:
            g.text(30, y + 6, self.notice, T.FONT_BOLD, 15, T.TEAL)
        key, values = OPTIONS[self.sel]
        if values:
            chrome.hints(g, [("‹ ›", t("hint.change")), ("B", t("hint.back"))])
        else:
            chrome.hints(g, [("A", t("hint.choose")), ("B", t("hint.back"))])
