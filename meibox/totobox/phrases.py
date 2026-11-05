"""Mei's lines: templates with blanks, chosen to fit the moment.

File format (one per line):  type: text with {blanks}
Lines starting with # are comments. The default files ship with the app; the user's
own files live in /roms/totobox/frases-pt.txt (and -en), easy to edit from a PC.
"""
import os
import random
import re
import string

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIR = os.path.join(APP_DIR, "frases")
USER_DIR = "/roms/totobox"
TYPES = {"lembrete", "saudade", "madrugada", "manha", "tarde", "noite", "calor", "ficha", "piada", "sorteio", "erro"}
CONTEXT_WEIGHT = 3
RECENT = 10
_LINE = re.compile(r"^\s*([a-z]+)\s*:\s*(.+?)\s*$")


def parse(text):
    out = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = _LINE.match(raw)
        if m and m.group(1) in TYPES:
            out.append((m.group(1), m.group(2)))
    return out


def blanks(template):
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def time_type(hour):
    if hour < 6:
        return "madrugada"
    if hour < 12:
        return "manha"
    if hour < 18:
        return "tarde"
    return "noite"


class Phrases:
    def __init__(self, settings, lang="pt", default_dir=DEFAULT_DIR, user_dir=USER_DIR, rng=None):
        self.settings = settings
        self.default_dir, self.user_dir = default_dir, user_dir
        self.rng = rng or random.Random()
        self.load(lang)

    def load(self, lang):
        self.lang = lang
        self.lines = []
        mode = self.settings["phrases"]
        sources = []
        if mode in ("both", "default"):
            sources.append(os.path.join(self.default_dir, f"frases-{lang}.txt"))
        if mode in ("both", "mine"):
            sources.append(os.path.join(self.user_dir, f"frases-{lang}.txt"))
        for path in sources:
            try:
                with open(path, encoding="utf-8") as f:
                    self.lines += parse(f.read())
            except OSError:
                pass

    def context_types(self, ctx):
        """Which line types fit right now. ctx keys: jogo, console, dias, hora, hora_n (0-23), temp, temp_n, horas, jogo_top."""
        types = {"piada", time_type(ctx.get("hora_n", 12))}
        if ctx.get("jogo"):
            types.add("lembrete")
        if (ctx.get("dias") or 0) >= 3:
            types.add("saudade")
        if (ctx.get("temp_n") or 0) >= 70:
            types.add("calor")
        if (ctx.get("horas") or 0) >= 1 and ctx.get("jogo_top"):
            types.add("ficha")
        return types

    def pick(self, ctx, only_type=None):
        """A filled-in line for this moment, or None if no line fits."""
        allowed = {only_type} if only_type else self.context_types(ctx)
        recent = list(self.settings["recent_phrases"] or [])
        pool, weights = [], []
        for typ, tpl in self.lines:
            if typ not in allowed or tpl in recent:
                continue
            if any(ctx.get(b) in (None, "") for b in blanks(tpl)):
                continue
            pool.append(tpl)
            weights.append(1 if typ == "piada" else CONTEXT_WEIGHT)
        if not pool:  # everything was shown recently: allow repeats rather than stay silent
            pool = [tpl for typ, tpl in self.lines if typ in allowed
                    and not any(ctx.get(b) in (None, "") for b in blanks(tpl))]
            weights = [1] * len(pool)
        if not pool:
            return None
        tpl = self.rng.choices(pool, weights)[0]
        self.settings["recent_phrases"] = ([tpl] + [r for r in recent if r != tpl])[:RECENT]
        return tpl.format(**{k: v for k, v in ctx.items() if v is not None})
