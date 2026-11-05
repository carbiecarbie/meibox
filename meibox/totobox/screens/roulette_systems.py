"""Ajustes > Sortear entre: pick which consoles the roulette draws from."""
from .. import chrome, i18n
from .. import theme as T
from ..i18n import t
from .settings_screen import SETTINGS_BG

ROWS, ROW_H, TOP = 9, 36, 96


def default_pool(systems):
    """Without a choice, the roulette uses every console except Ports."""
    return [s["path"] for s in systems if not s["path"].endswith("/ports")]


class RouletteSystems:
    def __init__(self, app):
        self.app = app
        self.systems = app.index.systems()
        chosen = app.settings["roulette_systems"]
        self.chosen = set(chosen) if chosen is not None else set(default_pool(self.systems))
        self.sel = 0

    def refresh(self):
        pass

    def after_game(self):
        pass

    def next_wake(self):
        return None

    def _save(self):
        paths = [s["path"] for s in self.systems if s["path"] in self.chosen]
        self.app.settings["roulette_systems"] = paths

    def handle(self, a):
        n = len(self.systems) + 1  # row 0 = "all"
        if a in ("up", "down"):
            self.sel = (self.sel + (1 if a == "down" else -1)) % n
        elif a in ("left", "right"):
            self.sel = max(0, min(n - 1, self.sel + (ROWS if a == "right" else -ROWS)))
        elif a == "a":
            if self.sel == 0:
                every = {s["path"] for s in self.systems}
                self.chosen = set() if self.chosen == every else every
            else:
                path = self.systems[self.sel - 1]["path"]
                self.chosen.symmetric_difference_update({path})
            self._save()
        elif a == "b":
            return ("pop",)
        return None

    def draw(self, g):
        chrome.background(g, "settings", 150, SETTINGS_BG)
        chrome.topbar(g, self.app.status, self.app.mascot)
        g.text(16, 46, t("rsys.title"), T.FONT_BOLD, 26, T.INK)
        total = sum(s["count"] for s in self.systems if s["path"] in self.chosen)
        g.text(16, 76, t("rsys.summary", c=len(self.chosen), g=i18n.num(total)), T.FONT_BOLD, 14, T.TEAL)
        rows = [(t("rsys.all"), None, len(self.chosen) == len(self.systems))]
        rows += [(s["fullname"], s["count"], s["path"] in self.chosen) for s in self.systems]
        top = max(0, min(self.sel - ROWS // 2, len(rows) - ROWS))
        for k, i in enumerate(range(top, min(len(rows), top + ROWS))):
            label, count, on = rows[i]
            y = TOP + 10 + k * ROW_H
            if i == self.sel:
                g.rrect(16, y, 460, ROW_H - 4, 8, T.PLUM)
                g.rect(16, y + 4, 4, ROW_H - 12, T.CYAN)
            # checkbox
            g.rframe(30, y + 7, 18, 18, 4, T.GOLD if on else T.MUTED)
            if on:
                g.rrect(34, y + 11, 10, 10, 2, T.GOLD)
            g.text(58, y + 5, label, T.FONT_BOLD, 17, T.INK if i == self.sel else T.SOFT, max_w=330)
            if count is not None:
                g.text(466, y + 8, i18n.num(count), T.FONT_BOLD, 14, T.MUTED, align="right")
        chrome.hints(g, [("A", t("rsys.toggle")), ("B", t("hint.back"))])
