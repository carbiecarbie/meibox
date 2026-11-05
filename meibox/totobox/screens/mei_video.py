"""Easter egg: the directional half of the Konami code (up up down down left right left right)
plays a short clip of Mei playing.

The clip (assets/meibox/mei-brincando.meiv, built by tools/make_mei_video.py) is a pack of
small JPEGs. Only the packed file (~1.2 MB) stays in memory while this screen is open, and
only one frame at a time is decoded into a texture. Everything is freed when the screen closes.
"""
import ctypes as C
import struct
import time

from .. import chrome
from .. import sdl as S
from .. import theme as T
from ..i18n import t
from .home import HOME_BG

KONAMI = ("up", "up", "down", "down", "left", "right", "left", "right")
DIRECTIONS = {"up", "down", "left", "right"}
LOOPS = 3                       # closes by itself after this many plays
VIDEO_X, VIDEO_W = 185, 270     # 216x384 scaled to the full screen height
DIM = 175                       # darkens the Meibox art on the sides


def load_clip(path):
    """(fps, w, h, bytearray, [(offset, size)]) from a MEIV file."""
    with open(path, "rb") as f:
        data = bytearray(f.read())
    if data[:4] != b"MEIV":
        raise ValueError("not a MEIV file")
    fps, count, w, h = struct.unpack_from("<4H", data, 4)
    sizes = struct.unpack_from(f"<{count}I", data, 12)
    frames, off = [], 12 + 4 * count
    for size in sizes:
        frames.append((off, size))
        off += size
    if off > len(data):
        raise ValueError("truncated MEIV file")
    return fps, w, h, data, frames


class KonamiWatcher:
    """Remembers the last directional presses; any other button starts over."""

    def __init__(self):
        self.recent = []

    def feed(self, action):
        if action not in DIRECTIONS:
            self.recent = []
            return False
        self.recent = (self.recent + [action])[-len(KONAMI):]
        if tuple(self.recent) == KONAMI:
            self.recent = []
            return True
        return False


class MeiVideo:
    def __init__(self, app):
        self.app = app
        self.fps, self.w, self.h, self.data, self.frames = load_clip(T.MEI_VIDEO)
        self.buf = (C.c_char * len(self.data)).from_buffer(self.data)
        self.base = C.addressof(self.buf)
        self.tex = None
        self.shown = -1      # frame index inside the clip
        self.shown_n = -1    # frame count since the start, across loops
        self.t0 = time.monotonic()

    def refresh(self):
        pass

    def after_game(self):
        pass

    def _index(self):
        return int((time.monotonic() - self.t0) * self.fps)

    def done(self):
        return self._index() >= LOOPS * len(self.frames)

    def next_wake(self):
        # next frame after the one on screen; the app closes the screen once done() is true
        return self.t0 + (self.shown_n + 1) / self.fps

    def handle(self, a):
        # Arrows are ignored: the last "right" of the code may still be held and repeating.
        if a in DIRECTIONS:
            return None
        return ("pop",)

    def close(self):
        if self.tex:
            S.sdl.SDL_DestroyTexture(self.tex)
            self.tex = None
        self.buf = None
        self.data = None

    def _frame_texture(self, g):
        n = min(self._index(), LOOPS * len(self.frames) - 1)
        self.shown_n = n
        i = n % len(self.frames)
        if i != self.shown or not self.tex:
            off, size = self.frames[i]
            rw = S.sdl.SDL_RWFromConstMem(self.base + off, size)
            tex = S.img.IMG_LoadTexture_RW(g.ren, rw, 1) if rw else None
            if tex:
                if self.tex:
                    S.sdl.SDL_DestroyTexture(self.tex)
                self.tex, self.shown = tex, i
        return self.tex

    def draw(self, g):
        self._sides(g)  # a few rects and cached texts; no full-screen layer left behind after closing
        tex = self._frame_texture(g)
        if tex:
            g.blit(tex, VIDEO_X, 0, VIDEO_W, 480)

    @staticmethod
    def _sides(g):
        chrome.background(g, "home", 0, HOME_BG)  # same cached texture as the home screen: no extra memory
        g.rect(0, 0, 640, 480, (8, 2, 14), DIM)
        for x, color in ((VIDEO_X - 6, T.MAGENTA), (VIDEO_X + VIDEO_W + 2, T.CYAN)):
            g.rect(x, 0, 4, 480, color)
        cx = VIDEO_X // 2
        for dx in (3, 2, 1):
            g.text(cx + dx, 170 + dx, t("egg.title"), T.FONT_BOLD, 52, T.SHADOW, align="center")
        g.text(cx, 170, t("egg.title"), T.FONT_BOLD, 52, T.GOLD, align="center")
        g.text(cx, 236, t("egg.sub"), T.FONT_BOLD, 22, T.MAGENTA, align="center")
        w = 24 + g.text_size(T.FONT_BOLD, 15, t("hint.back"))[0]
        x = cx - w // 2
        g.rrect(x, 300, 19, 19, 9, T.INK)
        g.text(x + 10, 302, "B", T.FONT_BOLD, 12, T.BG, align="center")
        g.text(x + 24, 300, t("hint.back"), T.FONT_BOLD, 15, T.MUTED)
