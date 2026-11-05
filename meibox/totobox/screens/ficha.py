"""Tela D, the Ficha: what Meibox has recorded about the player, ready to post."""
import os
import time

from .. import chrome, i18n
from .. import theme as T
from ..i18n import t
from ..stats import duration

FICHA_DIR = "/roms/totobox/fichas"
# Optional footer text on the saved image (e.g. your site), first line of this file.
FOOTER_FILE = "/roms/totobox/rodape-ficha.txt"
DIM = 170
BAR_W = 118


def footer_text(path=None):
    """First line of rodape-ficha.txt (up to 40 characters), or empty."""
    try:
        with open(path or FOOTER_FILE, encoding="utf-8-sig") as f:
            return f.readline().strip()[:40]
    except OSError:
        return ""


class Ficha:
    def __init__(self, app):
        self.app = app
        self.s = app.stats.summary()
        self.notice = None
        self.notice_until = 0

    def after_game(self):
        self.s = self.app.stats.summary()

    def next_wake(self):
        return self.notice_until if self.notice else None

    def handle(self, a):
        if a == "b":
            return ("pop",)
        if a == "start":
            self.save()
        return None

    def save(self):
        g = self.app.gfx
        folder = FICHA_DIR
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            folder = os.path.join(self.app.state, "fichas")
            os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, time.strftime("ficha-%Y%m%d-%H%M.png"))
        try:
            g.clear(T.BG)
            self.draw(g, export=True)
            g.screenshot(path)
            self.notice = t("ficha.saved", path=path)
            self.app.sound("ding")
        except Exception:  # noqa: BLE001 - shown to the user, never fatal
            self.notice = t("ficha.save_failed")
        self.notice_until = time.monotonic() + 4

    def draw(self, g, export=False):
        if self.notice and time.monotonic() > self.notice_until:
            self.notice = None
        chrome.background(g, "ficha", DIM, [])
        chrome.topbar(g, self.app.status, self.app.mascot)
        s = self.s
        since = self.app.settings["since"] or time.time()
        days = max(1, int((time.time() - since) // 86400) + 1)
        m = g.image(self.app.mascot) if self.app.mascot else None
        if m:
            g.blit(m[0], 16, 46, 58, 58)
        name = self.app.settings["player_name"]
        title = t("ficha.title", name=name) if name else t("ficha.title_noname")
        for dx in (2, 1):
            g.text(86 + dx, 48 + dx, title, T.FONT_BOLD, 30, T.SHADOW, max_w=530)
        g.text(86, 48, title, T.FONT_BOLD, 30, T.GOLD, max_w=530)
        g.text(86, 84, t("ficha.since1" if days == 1 else "ficha.since", date=i18n.full_date(since), days=days),
               T.FONT_BOLD, 14, T.TEAL)
        if not s["sessions"]:
            g.rrect(60, 180, 520, 110, 14, T.PANEL, 210)
            for k, line in enumerate(g.wrap(T.FONT_BOLD, 19, t("ficha.empty"), 480, 3)):
                g.text(320, 205 + k * 26, line, T.FONT_BOLD, 19, T.INK, align="center")
        else:
            self._tiles(g, s)
            self._bars(g, s)
        if not export:
            if self.notice:
                g.rect(0, 450, 640, 30, T.PLUM, 240)
                g.text(320, 456, self.notice, T.FONT_BOLD, 14, T.GOLD, align="center", max_w=620)
            else:
                chrome.hints(g, [("START", t("hint.save")), ("B", t("hint.back"))])
        else:
            extra = footer_text()
            g.text(624, 456, T.NAME + (" · " + extra if extra else ""), T.FONT_BOLD, 13, T.MUTED, align="right")

    def _tile(self, g, x, y, w, h, value, label, value_size=28):
        g.rrect(x, y, w, h, 10, T.PLUM, 210)
        g.text(x + 10, y + 4, value, T.FONT_BOLD, value_size, T.INK, max_w=w - 20)
        g.text(x + 10, y + h - 21, label, T.FONT_BOLD, 13, T.MUTED, max_w=w - 20)

    def _tiles(self, g, s):
        x0, y0, cw, gap = 16, 116, 161, 8
        total = s["seconds"] / 3600
        self._tile(g, x0, y0, cw, 62, f"{total:.0f} h" if total >= 1 else duration(s["seconds"]), t("ficha.total"))
        self._tile(g, x0 + cw + gap, y0, cw, 62, i18n.num(s["plays"]), t("ficha.plays"))
        y = y0 + 62 + gap
        top = s["top"]
        g.rrect(x0, y, 2 * cw + gap, 74, 10, T.PLUM, 210)
        game = self.app.index.game(top["system_path"], top["rel"])
        cover = g.thumb(game["image"], 44, 58) if game and game["image"] else None
        tx = x0 + 10
        if cover:
            g.blit(cover[0], x0 + 10, y + 8, 44, 58)
            tx = x0 + 64
        g.text(tx, y + 10, top["name"], T.FONT_BOLD, 21, T.INK, max_w=2 * cw + gap - (tx - x0) - 10)
        g.text(tx, y + 44, t("ficha.top", t=duration(top["seconds"])), T.FONT_BOLD, 13, T.MUTED,
               max_w=2 * cw + gap - (tx - x0) - 10)
        y += 74 + gap
        self._tile(g, x0, y, cw, 62, duration(s["longest"]), t("ficha.longest"), 22)
        if s["latest"]:
            fmt12 = self.app.settings["clock"] == "12"
            self._tile(g, x0 + cw + gap, y, cw, 62, i18n.clock(s["latest"][0], fmt12),
                       t("ficha.latest", game=s["latest"][1]), 22)

    def _bars(self, g, s):
        x, y, w = 362, 116, 262
        n = len(s["per_system"])
        h = 34 + n * 24 + 46
        g.rrect(x, y, w, h, 10, T.PANEL, 190)
        g.text(x + 12, y + 8, t("ficha.per_console"), T.FONT_BOLD, 14, T.MUTED)
        top = s["per_system"][0][1] if n else 1
        for k, (path, secs) in enumerate(s["per_system"]):
            sy = y + 34 + k * 24
            system = self.app.index.system(path) or {"name": "?", "fullname": "?"}
            label = system["name"].upper() if len(system["name"]) <= 6 else system["fullname"]
            g.text(x + 12, sy, label, T.FONT_BOLD, 13, T.INK, max_w=66)
            bw = max(8, int(BAR_W * secs / top))
            g.rrect(x + 84, sy + 3, bw, 12, 6, T.GOLD)
            g.rrect(x + 84, sy + 3, max(6, bw // 2), 12, 6, T.MAGENTA)
            g.text(x + w - 12, sy, duration(secs), T.FONT_BOLD, 13, T.TEAL, align="right")
        bx, by = x + 12, y + 34 + n * 24 + 8
        for badge in self._badges(s):
            bw = g.text_size(T.FONT_BOLD, 12, badge)[0] + 16
            if bx + bw > x + w - 8:
                bx, by = x + 12, by + 24
            g.rrect(bx, by, bw, 20, 10, T.CHIP)
            g.text(bx + 8, by + 2, badge, T.FONT_BOLD, 12, T.GOLD)
            bx += bw + 6

    @staticmethod
    def _badges(s):
        out = []
        for n in (500, 100, 10):
            if s["plays"] >= n:
                out.append(t("badge.plays", n=n))
                break
        if s["owl"]:
            out.append(t("badge.owl"))
        if s["marathon"]:
            out.append(t("badge.marathon"))
        if s["roulette"]:
            out.append(t("badge.roulette", n=s["roulette"]))
        return out
