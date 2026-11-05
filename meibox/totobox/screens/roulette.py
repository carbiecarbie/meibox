"""Sortear: covers spin and slow down until Mei lands on a game."""
import math
import random
import time

from .. import chrome
from .. import theme as T
from ..i18n import t
from .home import short_system

STRIP = 14          # games on the strip; the winner is the last one
SPACING, CW, CH = 132, 112, 150
SPIN_S = 2.6
Y = 150


def ease_out(p):
    return 1 - (1 - p) ** 3


class Roulette:
    def __init__(self, app, rng=None):
        self.app = app
        self.rng = rng or random.Random()
        self.start()

    def start(self):
        self.items = self._pick_items()
        self.loaded = 0
        self.state = "loading" if self.items else "empty"
        self.t0 = None
        self.last_tick = -1
        self.line = None

    def _pick_items(self):
        """The winner is one uniform draw; the games spinning before it prefer ones with a cover.

        Consoles with almost no covers (SNES, Super Famicom) still fill the strip with
        coverless games, and a console with very few games repeats them.
        """
        idx = self.app.index
        pool = self.app.settings["roulette_systems"]
        first = idx.random_game(self.rng, pool)
        if not first:
            return []
        winner = (idx.system(first[0]), idx.game(*first))
        with_cover, without, seen = [], [], {first}
        for _ in range(STRIP * 6):
            if len(with_cover) >= STRIP - 1:
                break
            r = idx.random_game(self.rng, pool)
            if not r or r in seen:
                continue
            seen.add(r)
            game = idx.game(*r)
            if game:
                (with_cover if game["image"] else without).append((idx.system(r[0]), game))
        fillers = (with_cover + without)[:STRIP - 1]
        while len(fillers) < STRIP - 1:  # tiny pool: repeat what there is
            fillers.append(fillers[len(fillers) % max(1, len(fillers))] if fillers else winner)
        self.rng.shuffle(fillers)
        return fillers + [winner]

    @property
    def winner(self):
        return self.items[-1] if self.items else None

    def after_game(self):
        pass

    def next_wake(self):
        return time.monotonic() if self.state in ("loading", "spinning") else None

    def handle(self, a):
        if a == "b":
            return ("pop",)
        if self.state != "landed":
            return None
        if a == "a":
            self.app.settings["roulette_accepted"] = (self.app.settings["roulette_accepted"] or 0) + 1
            return ("launch", self.winner[0], self.winner[1], {"via_roulette": True})
        if a == "y":
            self.start()
        return None

    def draw(self, g):
        chrome.background(g, "roulette", 165, [])
        chrome.topbar(g, self.app.status, self.app.mascot)
        g.text(320, 52, t("roulette.title"), T.FONT_BOLD, 26, T.GOLD, align="center")
        if self.state == "empty":
            g.rrect(90, 200, 460, 80, 14, T.PANEL, 220)
            for k, line in enumerate(g.wrap(T.FONT_BOLD, 18, t("roulette.empty"), 430, 2)):
                g.text(320, 214 + k * 24, line, T.FONT_BOLD, 18, T.INK, align="center")
            chrome.hints(g, [("B", t("hint.back"))])
            return
        if self.state == "loading":
            # decode two covers per frame, then spin
            for _ in range(2):
                if self.loaded < len(self.items):
                    game = self.items[self.loaded][1]
                    if game["image"]:
                        g.thumb(game["image"], CW, CH)
                    self.loaded += 1
            g.text(320, 230, t("roulette.shuffling"), T.FONT_BOLD, 22, T.INK, align="center")
            g.rrect(220, 270, 200, 10, 5, T.CHIP)
            g.rrect(220, 270, max(10, 200 * self.loaded // len(self.items)), 10, 5, T.GOLD)
            if self.loaded >= len(self.items):
                self.state, self.t0 = "spinning", time.monotonic()
            chrome.hints(g, [("B", t("hint.back"))])
            return
        target = len(self.items) - 1
        if self.state == "spinning":
            p = min(1.0, (time.monotonic() - self.t0) / SPIN_S)
            pos = ease_out(p) * target
            if int(pos) != self.last_tick:
                self.last_tick = int(pos)
                self.app.sound("tick")
            if p >= 1:
                self.state = "landed"
                game = self.winner[1]
                self.line = self.app.phrases.pick({"jogo": game["name"]}, only_type="sorteio") or game["name"]
                self.app.sound("ding")
        else:
            pos = target
        for i, (system, game) in enumerate(self.items):
            dx = (i - pos) * SPACING
            if abs(dx) > 400:
                continue
            centre = abs(dx) < SPACING / 2
            scale = 1.0 + 0.18 * max(0.0, 1 - abs(dx) / SPACING)
            w, h = int(CW * scale), int(CH * scale)
            x, y = int(320 + dx - w / 2), int(Y + (CH - h) / 2)
            alpha = int(255 * max(0.35, 1 - abs(dx) / 420))
            cover = g.thumb(game["image"], CW, CH) if game["image"] else None
            if cover:
                g.blit(cover[0], x, y, w, h, alpha)
            else:
                g.rrect(x, y, w, h, 8, T.PLUM, alpha)
                for k, line in enumerate(g.wrap(T.FONT_BOLD, 13, game["name"], w - 12, 4)):
                    g.text(x + w // 2, y + 20 + k * 17, line, T.FONT_BOLD, 13, T.INK, align="center")
            if centre and self.state == "landed":
                g.rframe(x - 3, y - 3, w + 6, h + 6, 10, T.GOLD, thick=3)
        # pointer
        from .. import sdl as S
        S.gfx.filledTrigonRGBA(g.ren, 310, Y - 26, 330, Y - 26, 320, Y - 10, *T.GOLD, 255)
        S.sdl.SDL_SetRenderDrawBlendMode(g.ren, S.BLENDMODE_BLEND)
        if self.state == "landed":
            system, game = self.winner
            g.rrect(70, 352, 500, 84, 14, T.INK)
            lines = g.wrap(T.FONT_BOLD, 19, self.line, 470, 2)
            for k, line in enumerate(lines):
                g.text(320, 360 + k * 24, line, T.FONT_BOLD, 19, T.DARK_TEXT, align="center")
            g.text(320, 362 + len(lines) * 24, short_system(system), T.FONT_BOLD, 13, (107, 88, 112),
                   align="center")
            chrome.hints(g, [("A", t("hint.play")), ("Y", t("hint.again")), ("B", t("hint.back"))])
        else:
            chrome.hints(g, [("B", t("hint.back"))])
