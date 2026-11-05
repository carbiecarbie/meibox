"""Interface text in Portuguese and English (lang/pt.json, lang/en.json)."""
import json
import os
import time

LANG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lang")
_tables = {}
_lang = "pt"


def _load(lang):
    if lang not in _tables:
        with open(os.path.join(LANG_DIR, lang + ".json"), encoding="utf-8") as f:
            _tables[lang] = json.load(f)
    return _tables[lang]


def set_lang(lang):
    global _lang
    _lang = lang if os.path.exists(os.path.join(LANG_DIR, lang + ".json")) else "pt"


def lang():
    return _lang


def t(key, **kw):
    s = _load(_lang).get(key) or _load("pt").get(key) or key
    return s.format(**kw) if kw else s


def num(n):
    """12418 -> 12.418 (pt) or 12,418 (en)."""
    s = f"{n:,}"
    return s.replace(",", ".") if _lang == "pt" else s


def clock(ts=None, fmt12=False):
    tm = time.localtime(ts) if ts else time.localtime()
    if fmt12:
        return time.strftime("%I:%M %p", tm).lstrip("0")
    return time.strftime("%H:%M", tm)


def day_month(ts):
    return time.strftime("%d/%m" if _lang == "pt" else "%m/%d", time.localtime(ts))


def full_date(ts):
    return time.strftime("%d/%m/%Y" if _lang == "pt" else "%m/%d/%Y", time.localtime(ts))
