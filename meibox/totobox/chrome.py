"""Parts shared by every screen: background, top bar (logo, battery, temp, clock), button hints."""
import glob
import os
import time

from . import theme as T



def read_battery():
    for d in glob.glob("/sys/class/power_supply/*"):
        try:
            if open(os.path.join(d, "type")).read().strip() != "Battery":
                continue
            cap = int(open(os.path.join(d, "capacity")).read().strip())
            status = open(os.path.join(d, "status")).read().strip()
            return cap, status == "Charging"
        except (OSError, ValueError):
            continue
    return None, False


def read_temp():
    try:
        return int(open("/sys/class/thermal/thermal_zone0/temp").read().strip()) / 1000
    except (OSError, ValueError):
        return None


class Status:
    """Battery/temperature/clock, refreshed every 5 s."""

    def __init__(self, settings=None):
        self.settings = settings
        self.t = 0
        self.value = (None, False, None, "")

    def invalidate(self):
        self.t = 0

    def get(self):
        if time.monotonic() - self.t > 5:
            from . import i18n
            fmt12 = bool(self.settings and self.settings["clock"] == "12")
            show_temp = not self.settings or self.settings["show_temp"]
            cap, charging = read_battery()
            self.value = (cap, charging, read_temp() if show_temp else None, i18n.clock(None, fmt12))
            self.t = time.monotonic()
        return self.value

    def changed_soon(self):
        return max(0.0, 5 - (time.monotonic() - self.t))


def background(g, key, dim, fades):
    """Art + darkening + gradients, pre-composed into one texture per screen style."""
    def build(gg):
        def draw(x):
            x.clear(T.BG)
            art = x.image(T.BACKGROUND)
            if art:
                x.blit(art[0], 0, 0, 640, 480)
            if dim:
                x.rect(0, 0, 640, 480, (0, 0, 0), dim)
            for stops, horizontal, rect in fades:
                tex = x.gradient(stops, 256, horizontal)
                x.blit(tex[0], *rect)
                from . import sdl as S
                S.sdl.SDL_DestroyTexture(tex[0])
        return gg.render_to_texture(draw)
    tex = g.made_texture(("bg", key), build)
    g.blit(tex[0], 0, 0, 640, 480)


def topbar(g, status, mascot_path):
    g.layer(("top", status.get(), mascot_path), 0, 0, 640, 44, lambda gg: _topbar(gg, status, mascot_path))


def _topbar(g, status, mascot_path):
    fade = g.made_texture("topfade", lambda gg: gg.gradient([(0, (20, 14, 26, 217)), (1, (20, 14, 26, 0))], 64,
                                                            False))
    g.blit(fade[0], 0, 0, 640, 44)
    m = g.image(mascot_path) if mascot_path else None
    x = 14
    if m:
        g.blit(m[0], x, 6, 28, 28)
        x += 34
    for dx in (3, 2, 1):
        g.text(x + dx, 7 + dx, T.NAME, T.FONT_BOLD, 22, T.SHADOW)
    g.text(x, 7, T.NAME, T.FONT_BOLD, 22, T.GOLD)
    cap, charging, temp, clock = status.get()
    rx = 626
    rx -= g.text(rx, 11, clock, T.FONT_BOLD, 16, T.INK, align="right") + 14
    if temp is not None:
        color = T.MAGENTA if temp >= 80 else T.GOLD if temp >= 70 else T.TEAL
        rx -= g.text(rx, 11, f"{temp:.0f} °C", T.FONT_BOLD, 16, color, align="right") + 14
    if cap is not None:
        g.text(rx, 11, ("+" if charging else "") + f"{cap}%", T.FONT_BOLD, 16, T.INK, align="right")


def hints(g, items):
    """items: [(button label, text)]. Drawn as small pills on a dark bar."""
    g.layer(("hints", tuple(items)), 0, 450, 640, 30, lambda gg: _hints(gg, items))


def _hints(g, items):
    g.rect(0, 450, 640, 30, (16, 11, 20), 210)
    x = 14
    for label, text in items:
        w = g.text_size(T.FONT_BOLD, 12, label)[0]
        pill = max(19, w + 10)
        g.rrect(x, 455, pill, 19, 9 if pill == 19 else 5, T.INK)
        g.text(x + pill // 2, 457, label, T.FONT_BOLD, 12, T.BG, align="center")
        x += pill + 5
        x += g.text(x, 456, text, T.FONT_BOLD, 14, T.MUTED) + 18
