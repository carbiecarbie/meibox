"""Drawing layer on top of SDL2's GPU renderer.

Screens never keep texture pointers: they ask Gfx by key every frame, and Gfx
caches. That makes it safe to tear everything down while a game runs and bring
it back afterwards.
"""
import ctypes as C
import hashlib
import os
from collections import OrderedDict

from . import sdl as S

W, H = 640, 480


class _LRU(OrderedDict):
    def __init__(self, cap, free):
        super().__init__()
        self.cap, self.free = cap, free

    def get(self, key):
        if key in self:
            self.move_to_end(key)
            return self[key]
        return None

    def put(self, key, value):
        self[key] = value
        self.move_to_end(key)
        while len(self) > self.cap:
            _, old = self.popitem(last=False)
            self.free(old)

    def clear_all(self):
        while self:
            _, v = self.popitem()
            self.free(v)


def _read_opaque(ren, w, h):
    """Read the current render target; alpha forced to 255 so saved PNGs look like the screen."""
    buf = C.create_string_buffer(w * h * 4)
    S.sdl.SDL_RenderReadPixels(ren, None, S.PIXELFORMAT_ABGR8888, buf, w * 4)
    raw = bytearray(buf.raw)
    raw[3::4] = bytes([255]) * (w * h)
    C.memmove(buf, bytes(raw), len(raw))
    return buf


class Gfx:
    def __init__(self, thumb_dir):
        self.thumb_dir = thumb_dir
        os.makedirs(thumb_dir, exist_ok=True)
        self.win = self.ren = None

    # ---- lifecycle ----
    def open(self):
        S.load()
        S.sdl.SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"1")
        if S.sdl.SDL_Init(S.INIT_VIDEO | S.INIT_GAMECONTROLLER | S.INIT_EVENTS) != 0:
            raise RuntimeError("SDL_Init: " + S.error())
        S.sdl.SDL_ShowCursor(0)
        self.win = S.sdl.SDL_CreateWindow(b"Meibox", 0, 0, W, H, S.WINDOW_FULLSCREEN | S.WINDOW_SHOWN)
        if not self.win:
            raise RuntimeError("SDL_CreateWindow: " + S.error())
        flags = S.RENDERER_TARGETTEXTURE | (1 if os.environ.get("TOTOBOX_SOFTWARE")  # SDL_RENDERER_SOFTWARE
                                            else S.RENDERER_ACCELERATED | S.RENDERER_PRESENTVSYNC)
        self.ren = S.sdl.SDL_CreateRenderer(self.win, -1, flags)
        if not self.ren:
            raise RuntimeError("SDL_CreateRenderer: " + S.error())
        S.sdl.SDL_SetRenderDrawBlendMode(self.ren, S.BLENDMODE_BLEND)
        S.img.IMG_Init(1 | 2 | 8)  # JPG | PNG | WEBP
        S.ttf.TTF_Init()
        destroy = S.sdl.SDL_DestroyTexture
        self.fonts = {}
        self.texts = _LRU(200, lambda t: destroy(t[0]))
        self.images = _LRU(20, lambda t: destroy(t[0]) if t else None)
        # generated textures (backgrounds, gradients); only a few full-screen ones are kept
        self.made = _LRU(6, lambda t: destroy(t[0]))
        self.fits = {}
        self.layers = _LRU(24, lambda t: destroy(t[0]))
        self.ox = self.oy = 0
        # Layers hold premultiplied colour (drawn with normal blending onto transparent),
        # so they are composited with ONE / ONE_MINUS_SRC_ALPHA.
        self.premul = S.sdl.SDL_ComposeCustomBlendMode(2, 6, 1, 2, 6, 1)

    def close(self):
        """Release the screen, fonts and textures so a game can take over the display."""
        if not self.ren:
            return
        self.texts.clear_all()
        self.images.clear_all()
        self.layers.clear_all()
        self.made.clear_all()
        for f in self.fonts.values():
            S.ttf.TTF_CloseFont(f)
        self.fonts.clear()
        S.sdl.SDL_DestroyRenderer(self.ren)
        S.sdl.SDL_DestroyWindow(self.win)
        self.ren = self.win = None
        S.ttf.TTF_Quit()
        S.img.IMG_Quit()
        S.sdl.SDL_Quit()

    # ---- primitives ----
    def clear(self, rgb):
        S.sdl.SDL_SetRenderDrawColor(self.ren, *rgb, 255)
        S.sdl.SDL_RenderClear(self.ren)

    def present(self):
        S.sdl.SDL_RenderPresent(self.ren)

    def rect(self, x, y, w, h, rgb, a=255):
        S.sdl.SDL_SetRenderDrawColor(self.ren, *rgb, a)
        S.sdl.SDL_RenderFillRect(self.ren, C.byref(S.Rect(int(x - self.ox), int(y - self.oy), int(w), int(h))))

    def rrect(self, x, y, w, h, r, rgb, a=255):
        x, y = x - self.ox, y - self.oy
        S.gfx.roundedBoxRGBA(self.ren, int(x), int(y), int(x + w - 1), int(y + h - 1), int(r), *rgb, a)
        S.sdl.SDL_SetRenderDrawBlendMode(self.ren, S.BLENDMODE_BLEND)  # SDL2_gfx may change it

    def rframe(self, x, y, w, h, r, rgb, a=255, thick=2):
        x, y = x - self.ox, y - self.oy
        for i in range(thick):
            S.gfx.roundedRectangleRGBA(self.ren, int(x + i), int(y + i), int(x + w - 1 - i), int(y + h - 1 - i),
                                       int(max(r - i, 0)), *rgb, a)
        S.sdl.SDL_SetRenderDrawBlendMode(self.ren, S.BLENDMODE_BLEND)

    def star(self, cx, cy, r, rgb, a=255):
        """Five-point star (the device fonts have no ★ glyph)."""
        import math
        cx, cy = cx - self.ox, cy - self.oy
        xs, ys = [], []
        for k in range(10):
            rad = r if k % 2 == 0 else r * 0.45
            ang = -math.pi / 2 + k * math.pi / 5
            xs.append(int(round(cx + rad * math.cos(ang))))
            ys.append(int(round(cy + rad * math.sin(ang))))
        vx, vy = (C.c_int16 * 10)(*xs), (C.c_int16 * 10)(*ys)
        S.gfx.filledPolygonRGBA(self.ren, vx, vy, 10, *rgb, a)
        S.sdl.SDL_SetRenderDrawBlendMode(self.ren, S.BLENDMODE_BLEND)

    def blit(self, tex, x, y, w=None, h=None, alpha=255, src=None):
        if not tex:
            return
        if w is None:
            w, h = S.texture_size(tex)
        S.sdl.SDL_SetTextureAlphaMod(tex, alpha)
        S.sdl.SDL_RenderCopy(self.ren, tex, C.byref(src) if src else None,
                             C.byref(S.Rect(int(x - self.ox), int(y - self.oy), int(w), int(h))))

    def layer(self, key, x, y, w, h, draw):
        """Draw a w*h region once into a cached texture, then just copy it every frame.

        draw(gfx) uses normal screen coordinates; key must change whenever the content does.
        """
        t = self.layers.get(key)
        if t is None:
            tex = S.sdl.SDL_CreateTexture(self.ren, S.PIXELFORMAT_ABGR8888, S.TEXTUREACCESS_TARGET, w, h)
            S.sdl.SDL_SetTextureBlendMode(tex, S.BLENDMODE_BLEND)
            S.sdl.SDL_SetRenderTarget(self.ren, tex)
            S.sdl.SDL_SetRenderDrawColor(self.ren, 0, 0, 0, 0)
            S.sdl.SDL_RenderClear(self.ren)
            self.ox, self.oy = x, y
            try:
                draw(self)
            finally:
                self.ox = self.oy = 0
                S.sdl.SDL_SetRenderTarget(self.ren, None)
            S.sdl.SDL_SetTextureBlendMode(tex, self.premul)
            t = (tex, w, h)
            self.layers.put(key, t)
        self.blit(t[0], x, y, w, h)

    # ---- text ----
    def font(self, path, size):
        key = (path, size)
        f = self.fonts.get(key)
        if f is None:
            f = S.ttf.TTF_OpenFont(path.encode(), size)
            if not f:
                raise RuntimeError(f"TTF_OpenFont {path}: {S.error()}")
            self.fonts[key] = f
        return f

    def text_size(self, path, size, s):
        w, h = C.c_int(), C.c_int()
        S.ttf.TTF_SizeUTF8(self.font(path, size), s.encode(), C.byref(w), C.byref(h))
        return w.value, h.value

    def fit(self, path, size, s, max_w):
        """Shorten s with an ellipsis until it fits max_w pixels (cached)."""
        key = (path, size, s, max_w)
        hit = self.fits.get(key)
        if hit is None:
            hit = self._fit(path, size, s, max_w)
            if len(self.fits) > 4000:
                self.fits.clear()
            self.fits[key] = hit
        return hit

    def _fit(self, path, size, s, max_w):
        if self.text_size(path, size, s)[0] <= max_w:
            return s
        lo, hi = 0, len(s)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.text_size(path, size, s[:mid].rstrip() + "…")[0] <= max_w:
                lo = mid
            else:
                hi = mid - 1
        return s[:lo].rstrip() + "…"

    def wrap(self, path, size, s, max_w, max_lines=3):
        """Split s into lines that fit max_w; the last line gets an ellipsis if needed."""
        words, lines, cur = s.split(), [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if self.text_size(path, size, trial)[0] <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines - 1] + [self.fit(path, size, " ".join(lines[max_lines - 1:]), max_w)]
        return lines

    def text(self, x, y, s, path, size, rgb, align="left", max_w=None, alpha=255):
        """Draw text; returns its width. align: left | right | center."""
        if not s:
            return 0
        if max_w:
            s = self.fit(path, size, s, max_w)
        key = (path, size, s, rgb)
        t = self.texts.get(key)
        if t is None:
            surf = S.ttf.TTF_RenderUTF8_Blended(self.font(path, size), s.encode(), S.Color(*rgb, 255))
            if not surf:
                return 0
            tex = S.sdl.SDL_CreateTextureFromSurface(self.ren, surf)
            S.sdl.SDL_FreeSurface(surf)
            t = (tex, *S.texture_size(tex))
            self.texts.put(key, t)
        tex, w, h = t
        if align == "right":
            x -= w
        elif align == "center":
            x -= w // 2
        self.blit(tex, x, y, w, h, alpha)
        return w

    # ---- images ----
    def image(self, path):
        """Full-size image texture, cached. Returns (tex, w, h) or None."""
        t = self.images.get(("img", path))
        if t is None and ("img", path) not in self.images:
            tex = S.img.IMG_LoadTexture(self.ren, path.encode()) if path and os.path.exists(path) else None
            t = (tex, *S.texture_size(tex)) if tex else None
            self.images.put(("img", path), t)
        return t

    def thumb(self, path, w, h):
        """Cover cropped to w*h ("cover" fit), saved once to the thumbnail cache."""
        key = ("thumb", path, w, h)
        t = self.images.get(key)
        if t is not None or key in self.images:
            return t
        t = None
        if path and os.path.exists(path):
            st = os.stat(path)
            name = hashlib.sha1(f"{path}|{st.st_mtime_ns}|{w}x{h}".encode()).hexdigest() + ".png"
            cached = os.path.join(self.thumb_dir, name)
            tex = S.img.IMG_LoadTexture(self.ren, cached.encode()) if os.path.exists(cached) else None
            if not tex:
                tex = self._make_thumb(path, w, h, cached)
            t = (tex, w, h) if tex else None
        self.images.put(key, t)
        return t

    def _make_thumb(self, path, w, h, out):
        src = S.img.IMG_LoadTexture(self.ren, path.encode())
        if not src:
            return None
        sw, sh = S.texture_size(src)
        scale = max(w / sw, h / sh)
        cw, ch = int(w / scale), int(h / scale)
        crop = S.Rect((sw - cw) // 2, (sh - ch) // 2, cw, ch)
        target = S.sdl.SDL_CreateTexture(self.ren, S.PIXELFORMAT_ABGR8888, S.TEXTUREACCESS_TARGET, w, h)
        S.sdl.SDL_SetRenderTarget(self.ren, target)
        S.sdl.SDL_SetRenderDrawColor(self.ren, 0, 0, 0, 255)
        S.sdl.SDL_RenderClear(self.ren)
        S.sdl.SDL_RenderCopy(self.ren, src, C.byref(crop), None)
        buf = _read_opaque(self.ren, w, h)
        S.sdl.SDL_SetRenderTarget(self.ren, None)
        S.sdl.SDL_DestroyTexture(src)
        surf = S.sdl.SDL_CreateRGBSurfaceWithFormatFrom(buf, w, h, 32, w * 4, S.PIXELFORMAT_ABGR8888)
        if surf:
            S.img.IMG_SavePNG(surf, out.encode())
            S.sdl.SDL_FreeSurface(surf)
        return target

    # ---- generated textures ----
    def made_texture(self, key, build):
        """Texture built once by build(gfx) -> (tex, w, h); rebuilt after close/open."""
        t = self.made.get(key)
        if t is None:
            t = build(self)
            self.made.put(key, t)
        return t

    def gradient(self, stops, length, horizontal):
        """1-pixel-thick gradient texture. stops: [(pos 0..1, (r,g,b,a)), ...]."""
        px = bytearray()
        for i in range(length):
            p = i / max(length - 1, 1)
            for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
                if p0 <= p <= p1:
                    k = (p - p0) / max(p1 - p0, 1e-6)
                    px += bytes(int(a + (b - a) * k) for a, b in zip(c0, c1))
                    break
        w, h = (length, 1) if horizontal else (1, length)
        buf = (C.c_char * len(px)).from_buffer(px)
        surf = S.sdl.SDL_CreateRGBSurfaceWithFormatFrom(buf, w, h, 32, w * 4, S.PIXELFORMAT_ABGR8888)
        tex = S.sdl.SDL_CreateTextureFromSurface(self.ren, surf)
        S.sdl.SDL_FreeSurface(surf)
        S.sdl.SDL_SetTextureBlendMode(tex, S.BLENDMODE_BLEND)
        return (tex, w, h)

    def render_to_texture(self, draw):
        """Render draw(gfx) into a new 640x480 texture (used to pre-compose backgrounds)."""
        target = S.sdl.SDL_CreateTexture(self.ren, S.PIXELFORMAT_ABGR8888, S.TEXTUREACCESS_TARGET, W, H)
        S.sdl.SDL_SetRenderTarget(self.ren, target)
        draw(self)
        S.sdl.SDL_SetRenderTarget(self.ren, None)
        return (target, W, H)

    def screenshot(self, out):
        buf = _read_opaque(self.ren, W, H)
        surf = S.sdl.SDL_CreateRGBSurfaceWithFormatFrom(buf, W, H, 32, W * 4, S.PIXELFORMAT_ABGR8888)
        S.img.IMG_SavePNG(surf, out.encode())
        S.sdl.SDL_FreeSurface(surf)
