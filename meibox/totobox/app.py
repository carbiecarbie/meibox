"""Main loop: a stack of screens, drawn only when something changed; games get the screen."""
import json
import os
import resource
import time

from . import chrome, i18n, launcher
from . import theme as T
from .gfx import Gfx
from .i18n import t
from .index import Index
from .input import Input
from .phrases import Phrases
from .screens.ficha import Ficha
from .screens.home import Home
from .screens.library import Library
from .screens.player_name_screen import PlayerNameScreen
from .screens.roulette import Roulette
from .screens.roulette_systems import RouletteSystems
from .screens.settings_screen import SettingsScreen
from .settings import Settings
from .sound import Sounds
from .stats import Stats

STATUS_REFRESH_MS = 5000
SCREEN_BUSY = 3  # exit code: the display could not be opened
FAILED_FAST_S = 3
SCREENS = {"library": Library, "roulette": Roulette, "ficha": Ficha, "settings": SettingsScreen,
           "roulette_systems": RouletteSystems, "player_name": PlayerNameScreen}
ACTION_SOUND = {"up": "move", "down": "move", "left": "move", "right": "move", "l1": "move", "r1": "move",
                "a": "meow", "b": "back"}


def rss_mb():
    out = {}
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith(("VmRSS", "VmHWM")):
                k, v = line.split(":")
                out[k] = int(v.split()[0]) // 1024
    return out


class App:
    def __init__(self, home, script=None, shot_dir=None, game_timeout=None, report=None):
        self.t0 = float(os.environ.get("TOTOBOX_T0", time.time()))
        self.home = home
        self.data = os.path.join(home, "data")
        self.cache = os.path.join(home, "cache")
        self.state = os.path.join(home, "state")
        for d in (self.data, self.cache, self.state):
            os.makedirs(d, exist_ok=True)
        self.gfx = Gfx(os.path.join(self.cache, "covers"))
        self.index = Index(os.path.join(self.data, "totobox.db"))
        self.stats = Stats(self.index.db)
        self.settings = Settings(self.index.db)
        if not self.settings["since"]:
            self.settings["since"] = time.time()
        i18n.set_lang(self.settings["lang"])
        self.phrases = Phrases(self.settings, i18n.lang())
        self.status = chrome.Status(self.settings)
        self.input = Input()
        self.sounds = Sounds(self.cache)
        self.mascot = None
        self.stack = []
        self.modal = None
        self.running = True
        self.script = list(script or [])
        self.shot_dir = shot_dir
        self.game_timeout = game_timeout
        self.report_path = report
        self.report = {"draws": 0, "draw_ms": [], "launches": []}

    @property
    def screen(self):
        return self.stack[-1]

    # ---- startup ----
    def start(self):
        try:
            self.gfx.open()
        except RuntimeError as e:  # another program holds the screen (EmulationStation did not let go)
            with open(os.path.join(self.state, "screen-busy.txt"), "w") as f:
                f.write(str(e) + "\n")
            raise SystemExit(SCREEN_BUSY)
        self._splash()
        self.input.open()
        self.report["controllers"] = self.input.info
        if self.settings["sounds"]:
            self.sounds.open()
        if os.path.exists(T.MASCOT):
            self.mascot = T.MASCOT
        else:
            self.report["mascot_error"] = "missing " + T.MASCOT
        first_run = self.index.total_games() == 0
        self.report["index"] = self.index.refresh(progress=self._progress if first_run else None)
        self.report["index"]["games"] = self.index.total_games()
        self.stack = [Home(self)]

    def _splash(self):
        """First frame as early as possible, so opening from the menu is not a long black screen."""
        g = self.gfx
        chrome.background(g, "list", 115, [])
        g.text(320, 210, T.NAME, T.FONT_BOLD, 44, T.GOLD, align="center")
        g.present()
        self.report["splash_s"] = round(time.time() - self.t0, 3)

    def _progress(self, i, n, name):
        g = self.gfx
        chrome.background(g, "list", 115, [])
        chrome.topbar(g, self.status, self.mascot)
        g.text(320, 200, t("progress"), T.FONT_BOLD, 26, T.INK, align="center")
        g.rrect(170, 246, 300, 14, 7, T.CHIP)
        g.rrect(170, 246, max(14, int(300 * i / n)), 14, 7, T.GOLD)
        g.text(320, 270, name, T.FONT_BOLD, 15, T.TEAL, align="center", max_w=400)
        g.present()

    def refresh_index(self):
        self.index.refresh(force=True, progress=self._progress)
        for s in self.stack:
            if hasattr(s, "refresh"):
                s.refresh()
        return self.index.total_games()

    def apply_settings(self):
        i18n.set_lang(self.settings["lang"])
        self.phrases.load(i18n.lang())
        self.status.invalidate()
        self.gfx.layers.clear_all()
        if self.settings["sounds"] and not self.sounds.ok:
            self.sounds.open()
        elif not self.settings["sounds"] and self.sounds.ok:
            self.sounds.close()

    def sound(self, name):
        if self.settings["sounds"]:
            self.sounds.play(name)

    # ---- loop ----
    def draw(self):
        t0 = time.perf_counter()
        self.gfx.clear(T.BG)
        self.screen.draw(self.gfx)
        if self.modal:
            self._draw_modal()
        self.report["draws"] += 1
        self.report["draw_ms"].append((time.perf_counter() - t0) * 1000)

    def run(self):
        self.start()
        dirty, first = True, True
        last_status = time.monotonic()
        while self.running:
            if dirty:
                self.draw()
                self.gfx.present()
                dirty = False
                if first:
                    self.report["first_frame_s"] = round(time.time() - self.t0, 3)
                    first = False
            if self.script:
                dirty = self._script_step() or dirty
                continue
            wake = self.screen.next_wake()
            wait = STATUS_REFRESH_MS
            if wake:
                wait = max(0, min(wait, int((wake - time.monotonic()) * 1000)))
            actions, quit_ = self.input.poll(wait)
            if quit_:
                self.running = False
            for a in actions:
                self._handle(a)
                dirty = True
            if wake and time.monotonic() >= wake:
                dirty = True
            if time.monotonic() - last_status >= STATUS_REFRESH_MS / 1000:
                last_status = time.monotonic()
                dirty = True
        self.finish()

    def _script_step(self):
        item = self.script.pop(0)
        if item.startswith("wait:"):
            end = time.monotonic() + int(item[5:]) / 1000
            while time.monotonic() < end:  # keep animating while waiting
                wake = self.screen.next_wake()
                if wake and wake <= time.monotonic():
                    self.draw()
                    self.gfx.present()
                else:
                    time.sleep(0.01)
            return True
        if item.startswith("shot:"):
            self.draw()
            self.gfx.screenshot(os.path.join(self.shot_dir or self.state, item[5:] + ".png"))
            self.gfx.present()
            return False
        if item == "mem":
            self.report.setdefault("mem", []).append(rss_mb())
            return False
        if item == "quit":
            self.running = False
            return False
        if item.startswith("push:"):
            self.stack.append(SCREENS[item[5:]](self))
            return True
        if item.startswith("open:"):          # dev: open a console by path
            if not isinstance(self.screen, Library):
                self.stack.append(Library(self))
            self.screen.open_system(item[5:])
            return True
        if item.startswith("pick:"):          # dev: select the first game whose name starts with this
            for i, game in enumerate(self.screen.games):
                if game["name"].lower().startswith(item[5:].lower()):
                    self.screen.sel = i
                    self.screen._touch()
                    break
            return True
        if item.startswith("set:"):           # dev: set:lang=en
            k, v = item[4:].split("=", 1)
            self.settings[k] = {"true": True, "false": False}.get(v, v)
            self.apply_settings()
            return True
        self._handle(item)
        return True

    def _handle(self, action):
        if self.modal:
            text, on_yes = self.modal
            if action == "a":
                self.modal = None
                on_yes()
            elif action == "b":
                self.modal = None
            return
        self.sound(ACTION_SOUND.get(action, ""))
        result = self.screen.handle(action)
        if not result:
            return
        kind = result[0]
        if kind == "quit":
            self.modal = (t("modal.exit"), self.stop)
        elif kind == "pop":
            if len(self.stack) > 1:
                self.stack.pop()
                if hasattr(self.screen, "refresh"):
                    self.screen.refresh()
            else:
                self.modal = (t("modal.exit"), self.stop)
        elif kind == "push":
            self.stack.append(SCREENS[result[1]](self))
        elif kind == "launch":
            self.launch(result[1], result[2], **(result[3] if len(result) > 3 else {}))

    def stop(self):
        self.running = False

    def _draw_modal(self):
        g = self.gfx
        g.rect(0, 0, 640, 480, (0, 0, 0), 150)
        g.rrect(120, 170, 400, 130, 14, T.PLUM)
        g.rframe(120, 170, 400, 130, 14, T.GOLD)
        g.text(320, 195, self.modal[0], T.FONT_BOLD, 20, T.INK, align="center", max_w=380)
        g.text(320, 245, t("modal.yesno"), T.FONT_BOLD, 17, T.TEAL, align="center")

    # ---- games ----
    def launch(self, system, game, via_roulette=False):
        rom = os.path.join(system["path"], game["rel"])
        cmd = launcher.build_command(system["command"], rom, system["emulators"], game["emulator"], game["core"])
        g = self.gfx
        self.draw()
        g.rect(0, 0, 640, 480, (0, 0, 0), 170)
        g.text(320, 215, t("launching", name=game["name"]), T.FONT_BOLD, 22, T.GOLD, align="center", max_w=600)
        g.present()
        time.sleep(0.25 if self.sounds.ok else 0)  # let the "miau" finish
        self.sounds.close()
        self.input.close()
        self.gfx.close()
        started = time.time()
        code, secs = launcher.run(cmd, os.path.join(self.state, "last-game.log"), self.game_timeout)
        self.gfx.open()
        self.input.open()
        if self.settings["sounds"]:
            self.sounds.open()
        self.report["launches"].append({"game": game["name"], "command": cmd, "exit": code,
                                        "seconds": round(secs, 1)})
        if secs < FAILED_FAST_S and code != 0:
            line = self.phrases.pick({"jogo": game["name"]}, only_type="erro") or t("game_failed")
            if hasattr(self.stack[0], "notice"):
                self.stack[0].notice = (line, None)
            return
        self.stats.add(system["path"], game["rel"], game["name"], started, time.time(), via_roulette)
        for s in self.stack:
            s.after_game()

    def finish(self):
        self.report["mem_end"] = rss_mb()
        ru = resource.getrusage(resource.RUSAGE_SELF)
        self.report["cpu_s"] = round(ru.ru_utime + ru.ru_stime, 2)
        ms = sorted(self.report.pop("draw_ms"))
        if ms:
            self.report["draw_ms"] = {"avg": round(sum(ms) / len(ms), 2), "p50": round(ms[len(ms) // 2], 2),
                                      "p90": round(ms[int(len(ms) * 0.9)], 2), "max": round(ms[-1], 2)}
        self.sounds.close()
        self.input.close()
        self.gfx.close()
        if self.report_path:
            with open(self.report_path, "w") as f:
                json.dump(self.report, f, indent=1, ensure_ascii=False)
