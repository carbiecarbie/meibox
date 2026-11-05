"""Play sessions recorded by Totobox itself (the Ficha starts from zero)."""
import time

from . import i18n

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY, system_path TEXT, rel TEXT, name TEXT, started REAL, ended REAL,
  via_roulette INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS sessions_by_game ON sessions(system_path, rel);
"""
MIN_PLAY_S = 60      # shorter sessions add time but are not counted as a play
MARATHON_S = 2 * 3600
OWL_HOURS = range(2, 6)


def night_score(ts):
    """Minutes after 6:00, so 3:39 at night counts as later than 23:50."""
    tm = time.localtime(ts)
    return ((tm.tm_hour - 6) % 24) * 60 + tm.tm_min


class Stats:
    def __init__(self, db):
        self.db = db
        db.executescript(SCHEMA)
        cols = {r[1] for r in db.execute("PRAGMA table_info(sessions)")}
        if "via_roulette" not in cols:
            db.execute("ALTER TABLE sessions ADD COLUMN via_roulette INTEGER DEFAULT 0")

    def add(self, system_path, rel, name, started, ended, via_roulette=False):
        self.db.execute("INSERT INTO sessions (system_path, rel, name, started, ended, via_roulette) "
                        "VALUES (?,?,?,?,?,?)", (system_path, rel, name, started, ended, int(via_roulette)))
        self.db.commit()

    def per_game(self, system_path):
        """{rel: (plays, last_ended)} for one system."""
        cur = self.db.execute("SELECT rel, SUM(ended - started >= ?), MAX(ended) FROM sessions "
                              "WHERE system_path=? GROUP BY rel", (MIN_PLAY_S, system_path))
        return {r[0]: (r[1] or 0, r[2]) for r in cur}

    def last(self):
        r = self.db.execute("SELECT system_path, rel, name, ended FROM sessions ORDER BY ended DESC LIMIT 1"
                            ).fetchone()
        return dict(zip(("system_path", "rel", "name", "ended"), r)) if r else None

    def summary(self):
        """Everything the Ficha shows."""
        rows = self.db.execute("SELECT system_path, rel, name, started, ended, via_roulette FROM sessions"
                               ).fetchall()
        s = {"seconds": 0, "plays": 0, "sessions": len(rows), "top": None, "longest": 0, "latest": None,
             "per_system": [], "owl": False, "marathon": False, "roulette": 0, "first": None}
        if not rows:
            return s
        per_game, per_system = {}, {}
        for system_path, rel, name, start, end, via in rows:
            d = max(0, end - start)
            s["seconds"] += d
            s["plays"] += d >= MIN_PLAY_S
            s["longest"] = max(s["longest"], d)
            s["roulette"] += bool(via)
            s["first"] = min(s["first"] or start, start)
            g = per_game.setdefault((system_path, rel), [name, 0])
            g[1] += d
            per_system[system_path] = per_system.get(system_path, 0) + d
            if d >= MIN_PLAY_S:
                if s["latest"] is None or night_score(start) > night_score(s["latest"][0]):
                    s["latest"] = (start, name)
                if time.localtime(start).tm_hour in OWL_HOURS:
                    s["owl"] = True
            if d >= MARATHON_S:
                s["marathon"] = True
        (sp, rel), (name, secs) = max(per_game.items(), key=lambda kv: kv[1][1])
        s["top"] = {"system_path": sp, "rel": rel, "name": name, "seconds": secs}
        s["per_system"] = sorted(per_system.items(), key=lambda kv: -kv[1])[:5]
        return s

    def days_since_last(self, now=None):
        last = self.last()
        if not last:
            return None
        return int(((now or time.time()) - last["ended"]) // 86400)


def when(ts, now=None):
    """Short relative day: hoje, ontem, há 3 dias, 12/10."""
    if not ts:
        return ""
    now = now or time.time()
    d0 = time.localtime(now)
    midnight = time.mktime((d0.tm_year, d0.tm_mon, d0.tm_mday, 0, 0, 0, 0, 0, -1))
    if ts >= midnight:
        return i18n.t("when.today")
    days = int((midnight - ts) // 86400) + 1
    if days == 1:
        return i18n.t("when.yesterday")
    if days < 7:
        return i18n.t("when.days", n=days)
    return i18n.day_month(ts)


def duration(secs):
    """'6 h 12 min', '45 min', '2 h'."""
    m = int(secs // 60)
    h, m = divmod(m, 60)
    if h and m:
        return f"{h} h {m:02d}"
    if h:
        return f"{h} h"
    return f"{m} min"


def es_time(stamp):
    """ES lastplayed '20261103T195652' -> epoch seconds (local time)."""
    try:
        return time.mktime(time.strptime(stamp, "%Y%m%dT%H%M%S"))
    except (TypeError, ValueError):
        return None
