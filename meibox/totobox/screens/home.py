"""Tela A, the welcome screen: the art, Mei's speech bubble and three cards."""
import time

from .. import chrome, i18n
from .. import theme as T
from ..i18n import t
from ..stats import es_time, when

CARD_Y, CARD_H = 320, 118
CARDS = [(14, 239), (263, 177), (450, 176)]  # x, width (grid 1.35fr 1fr 1fr, gap 10)
BUBBLE = (150, 46, 200)  # x, y, width
HOME_BG = [([(0, (20, 14, 26, 0)), (0.45, (20, 14, 26, 0)), (0.78, (20, 14, 26, 235)), (1, (20, 14, 26, 235))],
            False, (0, 0, 640, 480))]


def short_system(system):
    name = (system or {}).get("name", "")
    return name.upper() if 0 < len(name) <= 5 else (system or {}).get("fullname", "")


class Home:
    def __init__(self, app):
        self.app = app
        self.sel = 0
        self.notice = None
        self.refresh()

    def refresh(self):
        """Work out the "Continuar" game: Totobox's last session, else the last game ES opened."""
        self.cont = None
        last = self.app.stats.last()
        if last:
            game = self.app.index.game(last["system_path"], last["rel"])
            if game:
                self.cont = (self.app.index.system(last["system_path"]), game, last["ended"])
        if not self.cont:
            r = self.app.index.last_es_played()
            if r:
                game = self.app.index.game(*r)
                if game:
                    self.cont = (self.app.index.system(r[0]), game, es_time(game["es_lastplayed"]))
        systems = self.app.index.systems()
        self.n_systems, self.n_games = len(systems), sum(s["count"] for s in systems)
        self.line = None
        text = self.app.phrases.pick(self.context())
        if text:
            small = self._stopped_line() if self.cont and self.cont[1]["name"] in text else None
            self.line = (text, small)

    def context(self):
        """Values for the blanks in Mei's lines."""
        app = self.app
        fmt12 = app.settings["clock"] == "12"
        c = {"hora": i18n.clock(None, fmt12), "hora_n": time.localtime().tm_hour}
        temp = chrome.read_temp()
        if temp is not None:
            c["temp"] = f"{temp:.0f} °C"
            c["temp_n"] = temp
        if self.cont:
            c.update(jogo=self.cont[1]["name"], console=self.cont[0]["fullname"])
        days = app.stats.days_since_last()
        if days is not None:
            c["dias"] = days
        s = app.stats.summary()
        if s["top"] and s["seconds"] >= 3600:
            c["horas"] = int(s["top"]["seconds"] // 3600) or None
            c["jogo_top"] = s["top"]["name"]
        return c

    def _stopped_line(self):
        ended = self.cont[2]
        if not ended:
            return None
        return t("home.you_stopped", when=when(ended),
                 time=i18n.clock(ended, self.app.settings["clock"] == "12"))

    def after_game(self):
        self.refresh()

    def next_wake(self):
        return None

    def handle(self, a):
        self.notice = None
        if a in ("left", "right"):
            self.sel = (self.sel + (1 if a == "right" else -1)) % 3
        elif a == "a":
            if self.sel == 0:
                if self.cont:
                    return ("launch", self.cont[0], self.cont[1], {})
                return ("push", "library")
            if self.sel == 1:
                return ("push", "roulette")
            return ("push", "library")
        elif a == "b":
            return ("quit",)
        elif a == "select":
            return ("push", "ficha")
        elif a == "start":
            return ("push", "settings")
        return None

    # ---- drawing ----
    def draw(self, g):
        chrome.background(g, "home", 0, HOME_BG)
        chrome.topbar(g, self.app.status, self.app.mascot)
        self._bubble(g)
        for i, (x, w) in enumerate(CARDS):
            self._card(g, i, x, w)
        chrome.hints(g, [("A", t("hint.open")), ("SELECT", t("hint.ficha")), ("START", t("hint.settings")),
                         ("B", t("hint.exit"))])

    def _bubble(self, g):
        text, small = self.notice or self.line or self._default_line()
        x, y, w = BUBBLE
        lines = g.wrap(T.FONT_BOLD, 15, text, w - 24, 3)
        h = 14 + len(lines) * 19 + (18 if small else 0)

        def draw(gg):
            gg.rrect(x, y + 4, w, h, 14, (0, 0, 0), 90)       # drop shadow
            gg.rrect(x, y, w, h, 14, T.INK)
            from .. import sdl as S
            S.gfx.filledTrigonRGBA(gg.ren, x + w - 1 - gg.ox, y + 26 - gg.oy, x + w + 10 - gg.ox, y + 34 - gg.oy,
                                   x + w - 1 - gg.ox, y + 42 - gg.oy, *T.INK, 255)
            S.sdl.SDL_SetRenderDrawBlendMode(gg.ren, S.BLENDMODE_BLEND)
            for k, line in enumerate(lines):
                gg.text(x + 12, y + 8 + k * 19, line, T.FONT_BOLD, 15, T.DARK_TEXT)
            if small:
                gg.text(x + 12, y + 10 + len(lines) * 19, small, T.FONT_TEXT, 12, (107, 88, 112), max_w=w - 24)
        g.layer(("bubble", text, small), x, y, w + 12, h + 6, draw)

    def _default_line(self):
        return (t("home.fallback", n=i18n.num(self.n_games)), None)

    def _card(self, g, i, x, w):
        selected = i == self.sel
        y = CARD_Y - (4 if selected else 0)
        if selected:
            g.rrect(x - 4, y - 4, w + 8, CARD_H + 8, 15, T.CYAN, 60)
        g.rrect(x, y, w, CARD_H, 12, (42, 27, 46), 235)
        if selected:
            g.rframe(x, y, w, CARD_H, 12, T.GOLD)
        else:
            g.rframe(x, y, w, CARD_H, 12, (255, 255, 255), 20)
        if i == 0:
            tx = x + 12
            if self.cont:
                game = self.cont[1]
                cover = g.thumb(game["image"], 70, 94) if game["image"] else None
                if cover:
                    g.blit(cover[0], x + 12, y + 12, 70, 94)
                else:
                    g.rrect(x + 12, y + 12, 70, 94, 6, T.PLUM)
                tx = x + 92
                g.text(tx, y + 10, t("home.continue"), T.FONT_BOLD, 21, T.INK)
                g.text(tx, y + 40, game["name"], T.FONT_TEXT, 14, T.MUTED, max_w=w - (tx - x) - 10)
                g.text(tx, y + 60, " · ".join(p for p in (short_system(self.cont[0]), when(self.cont[2])) if p),
                       T.FONT_TEXT, 14, T.MUTED, max_w=w - (tx - x) - 10)
            else:
                g.text(tx, y + 10, t("home.choose"), T.FONT_BOLD, 21, T.INK)
                g.text(tx, y + 40, t("home.opens_library"), T.FONT_TEXT, 14, T.MUTED)
        elif i == 1:
            g.text(x + 12, y + 10, t("home.roulette"), T.FONT_BOLD, 21, T.INK)
            g.text(x + 12, y + 40, t("home.roulette_sub"), T.FONT_TEXT, 14, T.MUTED, max_w=w - 24)
            self._dice(g, x + 14, y + 66, 38)
        else:
            g.text(x + 12, y + 10, t("home.library"), T.FONT_BOLD, 21, T.INK)
            g.text(x + 12, y + 40, t("home.consoles", n=self.n_systems), T.FONT_TEXT, 14, T.MUTED)
            g.text(x + 12, y + 60, t("home.games", n=i18n.num(self.n_games)), T.FONT_TEXT, 14, T.MUTED)

    @staticmethod
    def _dice(g, x, y, s):
        g.rrect(x, y, s, s, 8, T.INK)
        r = max(3, s // 10)
        for px, py in ((0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)):
            g.rrect(x + int(px * s) - r, y + int(py * s) - r, 2 * r, 2 * r, r, T.PLUM)
