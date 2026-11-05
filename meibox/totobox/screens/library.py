"""Biblioteca: list of consoles, then the "lista turbo" (mockup C) of one console."""
import time

from .. import chrome, i18n
from .. import theme as T
from ..i18n import t
from ..stats import when

ROWS, ROW_H, LIST_X, LIST_Y, LIST_W = 11, 30, 14, 112, 360
COVER_X, COVER_Y, COVER_W, COVER_H = 439, 52, 170, 226
FILTERS = ["all", "fav", "never"]
LETTERS = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ"
COVER_DELAY = 0.12  # wait for the selection to settle before decoding a new cover


def letter_of(text):
    c = (text or "#")[0].upper()
    return c if "A" <= c <= "Z" else "#"


def folder_label(name):
    """'# PT-BR #' -> 'PT-BR' (ROM packs decorate folder names)."""
    return name.strip(" #") or name


def split_view(games, prefix):
    """Folders (with game counts) and games directly inside `prefix`, like ES shows them."""
    folders, direct = {}, []
    for g in games:
        rel = g["rel"]
        if not rel.startswith(prefix):
            continue
        rest = rel[len(prefix):]
        if "/" in rest:
            name = rest.split("/", 1)[0]
            folders[name] = folders.get(name, 0) + 1
        else:
            direct.append(g)
    items = [{"folder": True, "name": folder_label(n), "rel": prefix + n + "/", "count": c}
             for n, c in sorted(folders.items(), key=lambda kv: folder_label(kv[0]).casefold())]
    return items + direct


LIST_BG = (0, [([(0, (20, 14, 26, 247)), (0.56, (20, 14, 26, 237)), (1, (20, 14, 26, 64))], True,
                (0, 0, 640, 480))])


class Library:
    def __init__(self, app):
        self.app = app
        self.mode = "systems"
        self.systems = app.index.systems()
        self.sys_sel = 0
        self.games, self.all_games = [], []
        self.sel = 0
        self.filter = "all"
        self.system = None
        self.folder = ""       # current folder inside the console ("" = top level)
        self.folder_sel = []   # selection to restore when going back up
        self.plays = {}
        self.sel_changed = time.monotonic()
        self.wake_at = None

    # ---- data ----
    def open_system(self, path):
        self.system = self.app.index.system(path)
        self.all_games = self.app.index.games(path)
        self.plays = self.app.stats.per_game(path)
        self.mode, self.sel, self.filter = "games", 0, "all"
        self.folder, self.folder_sel = "", []
        self._apply_filter()

    def _apply_filter(self, keep_rel=None):
        # Filters search the whole console (folders included); "all" browses folder by folder.
        if self.filter == "fav":
            self.games = [g for g in self.all_games if g["favorite"]]
        elif self.filter == "never":
            self.games = [g for g in self.all_games if g["rel"] not in self.plays and not g["es_lastplayed"]]
        else:
            self.games = split_view(self.all_games, self.folder)
        self.sel = 0
        if keep_rel:
            for i, g in enumerate(self.games):
                if g["rel"] == keep_rel:
                    self.sel = i
        self._touch()

    def after_game(self):
        """Refresh play counts after returning from a game; keep the selection."""
        if self.system:
            self.plays = self.app.stats.per_game(self.system["path"])

    def _touch(self):
        self.sel_changed = time.monotonic()

    # ---- input ----
    def handle(self, a):
        if self.mode == "systems":
            n = len(self.systems)
            if a in ("up", "down") and n:
                self.sys_sel = (self.sys_sel + (1 if a == "down" else -1)) % n
            elif a in ("left", "right") and n:
                self.sys_sel = max(0, min(n - 1, self.sys_sel + (ROWS if a == "right" else -ROWS)))
            elif a == "a" and n:
                self.open_system(self.systems[self.sys_sel]["path"])
            elif a == "b":
                return ("pop",)
            return None
        n = len(self.games)
        if a in ("up", "down") and n:
            self.sel = (self.sel + (1 if a == "down" else -1)) % n
            self._touch()
        elif a in ("left", "right") and n:
            self.sel = max(0, min(n - 1, self.sel + (ROWS if a == "right" else -ROWS)))
            self._touch()
        elif a in ("l1", "r1") and n:
            self._jump_letter(1 if a == "r1" else -1)
        elif a == "x" and n and not self.games[self.sel].get("folder"):
            g = self.games[self.sel]
            g["favorite"] = self.app.index.toggle_favorite(self.system["path"], g["rel"])
            if self.filter == "fav" and not g["favorite"]:
                self._apply_filter()
        elif a == "y":
            keep = self.games[self.sel]["rel"] if n else None
            self.filter = FILTERS[(FILTERS.index(self.filter) + 1) % len(FILTERS)]
            if self.filter != "all":
                self.folder, self.folder_sel = "", []
            self._apply_filter(keep)
        elif a == "a" and n:
            item = self.games[self.sel]
            if item.get("folder"):
                self.folder_sel.append(self.sel)
                self.folder = item["rel"]
                self._apply_filter()
                return None
            return ("launch", self.system, item, {})
        elif a == "b":
            if self.folder:
                parent = self.folder.rstrip("/").rsplit("/", 1)[0] + "/" if "/" in self.folder.rstrip("/") else ""
                self.folder = parent
                self._apply_filter()
                if self.folder_sel:
                    self.sel = min(self.folder_sel.pop(), max(0, len(self.games) - 1))
            else:
                self.mode = "systems"
        return None

    def _jump_letter(self, step):
        cur = letter_of(self.games[self.sel]["name"])
        i = self.sel
        if step > 0:
            while i < len(self.games) and letter_of(self.games[i]["name"]) == cur:
                i += 1
            self.sel = i if i < len(self.games) else 0
        else:
            # go to start of current group; if already there, to start of previous group
            while i > 0 and letter_of(self.games[i - 1]["name"]) == cur:
                i -= 1
            if i == self.sel:
                i = (i - 1) % len(self.games)
                prev = letter_of(self.games[i]["name"])
                while i > 0 and letter_of(self.games[i - 1]["name"]) == prev:
                    i -= 1
            self.sel = i
        self._touch()

    def next_wake(self):
        return self.wake_at

    # ---- drawing ----
    def draw(self, g):
        self.wake_at = None
        chrome.background(g, "list", 175, LIST_BG[1])
        chrome.topbar(g, self.app.status, self.app.mascot)
        if self.mode == "systems":
            self._draw_systems(g)
        else:
            self._draw_games(g)

    def _window(self, sel, n):
        top = max(0, min(sel - ROWS // 2, n - ROWS))
        return top, range(top, min(n, top + ROWS))

    @staticmethod
    def _folder_icon(g, x, y, w=20, h=15, color=T.GOLD):
        g.rrect(x, y, w * 0.45, h * 0.35, 2, color)
        g.rrect(x, y + h * 0.2, w, h * 0.8, 3, color)

    def _row(self, g, i, y, label, meta, selected, meta_color=T.MUTED, folder=False):
        if selected:
            g.rrect(LIST_X, y, LIST_W, ROW_H, 7, T.PLUM)
            g.rect(LIST_X, y + 3, 4, ROW_H - 6, T.CYAN)
        lx = LIST_X + 12
        if folder:
            self._folder_icon(g, lx, y + 8)
            lx += 28
        if meta == "★":
            g.star(LIST_X + LIST_W - 17, y + 15, 7, T.GOLD)
            mw = 16
        else:
            mw = g.text(LIST_X + LIST_W - 10, y + 8, meta, T.FONT_TEXT, 13, meta_color, align="right",
                        max_w=120) if meta else 0
        g.text(lx, y + 4, label, T.FONT_TEXT, 17, (T.GOLD if folder else T.INK) if selected else
               (T.GOLD if folder else T.SOFT), max_w=LIST_W - (lx - LIST_X) - 14 - (mw + 8 if mw else 0))

    def _draw_systems(self, g):
        total = sum(s["count"] for s in self.systems)
        g.text(14, 44, t("lib.title"), T.FONT_BOLD, 24, T.INK)
        g.text(14, 76, t("lib.summary", s=len(self.systems), g=i18n.num(total)), T.FONT_BOLD, 15, T.TEAL)
        _, rows = self._window(self.sys_sel, len(self.systems))
        for k, i in enumerate(rows):
            s = self.systems[i]
            self._row(g, i, LIST_Y + k * ROW_H, s["fullname"], i18n.num(s["count"]), i == self.sys_sel)
        if self.systems:
            s = self.systems[self.sys_sel]
            g.rrect(424, 120, 200, 150, 12, T.PANEL, 200)
            g.text(524, 150, i18n.num(s["count"]), T.FONT_BOLD, 44, T.GOLD, align="center")
            g.text(524, 205, t("lib.game_word" if s["count"] == 1 else "lib.games_word"), T.FONT_BOLD, 16, T.TEAL, align="center")
            g.text(524, 232, s["fullname"], T.FONT_BOLD, 15, T.INK, align="center", max_w=186)
        chrome.hints(g, [("A", t("hint.open")), ("B", t("hint.back"))])

    def _draw_games(self, g):
        g.layer(("head", self.system["path"], self.filter, self.folder, len(self.games), i18n.lang()),
                0, 40, 430, 64, self._draw_head)
        n = len(self.games)
        if not n:
            g.text(LIST_X + 12, LIST_Y + 8, t("lib.empty"), T.FONT_TEXT, 17, T.MUTED)
            chrome.hints(g, [("Y", t("hint.filter")), ("B", t("hint.back"))])
            return
        _, rows = self._window(self.sel, n)
        for k, i in enumerate(rows):
            game = self.games[i]
            if game.get("folder"):
                self._row(g, i, LIST_Y + k * ROW_H, game["name"], i18n.num(game["count"]), i == self.sel,
                          T.MUTED, folder=True)
                continue
            meta, color = self._meta(game)
            self._row(g, i, LIST_Y + k * ROW_H, game["name"], meta, i == self.sel, color)
        cur = letter_of(self.games[self.sel]["name"])
        g.layer(("alpha", cur), 380, LIST_Y - 4, 22, 340, lambda gg: self._draw_alpha(gg, cur))
        item = self.games[self.sel]
        if item.get("folder"):
            self._draw_folder_detail(g, item)
            chrome.hints(g, [("A", t("hint.open")), ("Y", t("hint.filter")), ("L1 R1", t("hint.letter")),
                             ("B", t("hint.back"))])
        else:
            self._draw_detail(g, item)
            chrome.hints(g, [("A", t("hint.play")), ("X", t("hint.fav")), ("Y", t("hint.filter")),
                             ("L1 R1", t("hint.letter")), ("B", t("hint.back"))])

    def _draw_folder_detail(self, g, item):
        g.rrect(COVER_X, COVER_Y, COVER_W, COVER_H, 10, T.PLUM, 220)
        self._folder_icon(g, COVER_X + 45, COVER_Y + 60, 80, 60)
        g.text(COVER_X + COVER_W // 2, COVER_Y + 140, i18n.num(item["count"]), T.FONT_BOLD, 30, T.GOLD,
               align="center")
        g.text(COVER_X + COVER_W // 2, COVER_Y + 180, t("lib.game_word" if item["count"] == 1 else "lib.games_word"), T.FONT_BOLD, 15, T.TEAL, align="center")
        g.rrect(424, 288, 200, 34, 8, T.PANEL, 205)
        g.text(524, 293, item["name"], T.FONT_BOLD, 15, T.INK, align="center", max_w=188)

    def _draw_alpha(self, g, cur):
        for k, ch in enumerate(LETTERS):
            on = ch == cur
            g.text(390, LIST_Y + k * 12.3 - (2 if on else 0), ch, T.FONT_BOLD, 13 if on else 10,
                   T.GOLD if on else T.MUTED, align="center")

    def _draw_head(self, g):
        s = self.system
        if self.folder:
            title = s["fullname"] + " › " + folder_label(self.folder.rstrip("/").rsplit("/", 1)[-1])
            count = sum(1 for x in self.all_games if x["rel"].startswith(self.folder))
        else:
            title, count = s["fullname"], len(self.all_games)
        w = g.text(14, 42, title, T.FONT_BOLD, 24, T.INK, max_w=320)
        g.text(14 + w + 8, 52, t("lib.games", n=i18n.num(count)), T.FONT_BOLD, 14, T.TEAL)
        x = 14
        for f in FILTERS:
            label = t("filter." + f)
            star = 14 if f == "fav" else 0
            tw = g.text_size(T.FONT_BOLD, 13, label)[0] + star
            on = f == self.filter
            g.rrect(x, 78, tw + 18, 21, 10, T.GOLD if on else T.CHIP)
            if star:
                g.star(x + 15, 88, 6, T.DARK_TEXT if on else T.GOLD)
            g.text(x + 9 + star, 80, label, T.FONT_BOLD, 13, T.DARK_TEXT if on else T.MUTED)
            x += tw + 24

    def _meta(self, game):
        plays, last = self.plays.get(game["rel"], (0, None))
        if game["favorite"]:
            return "★", T.GOLD
        if last and time.time() - last < 7 * 86400:
            return when(last), T.MUTED
        if plays:
            return t("meta.played", n=plays), T.MUTED
        if self.filter != "all" and "/" in game["rel"]:  # flat filtered view: say which folder it is in
            return folder_label(game["rel"].rsplit("/", 1)[0].rsplit("/", 1)[-1]), T.MUTED
        return "", T.MUTED

    def _draw_detail(self, g, game):
        cover = None
        if game["image"]:
            settled = time.monotonic() - self.sel_changed >= COVER_DELAY
            key = ("thumb", game["image"], COVER_W, COVER_H)
            if settled or key in g.images:
                cover = g.thumb(game["image"], COVER_W, COVER_H)
            else:
                self.wake_at = self.sel_changed + COVER_DELAY
        if cover:
            g.blit(cover[0], COVER_X, COVER_Y, COVER_W, COVER_H)
            g.rframe(COVER_X - 2, COVER_Y - 2, COVER_W + 4, COVER_H + 4, 10, T.GOLD)
        else:
            g.rrect(COVER_X, COVER_Y, COVER_W, COVER_H, 10, T.PLUM, 220)
            g.text(COVER_X + COVER_W // 2, COVER_Y + 96, t("lib.no_cover") if not game["image"] else "…",
                   T.FONT_BOLD, 15, T.MUTED, align="center")
        plays, last = self.plays.get(game["rel"], (0, None))  # Totobox's own sessions only
        line2 = []
        if plays:
            line2.append(t("detail.times1") if plays == 1 else t("detail.timesN", n=plays))
        if last:
            line2.append(when(last))
        g.rrect(424, 288, 200, 54 if line2 else 34, 8, T.PANEL, 205)
        g.text(524, 293, game["name"], T.FONT_BOLD, 15, T.INK, align="center", max_w=188)
        if line2:
            g.text(524, 315, " · ".join(line2), T.FONT_BOLD, 14, T.TEAL, align="center")
