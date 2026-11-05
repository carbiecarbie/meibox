"""Game index: reads EmulationStation's files (read-only) into a small SQLite cache.

Systems are keyed by their <path>, because es_systems.cfg reuses names
(two systems are both called "snes"). Only systems that have at least one game
are kept. A system is rescanned when its folder, its gamelist.xml or
es_systems.cfg changed since the last scan.
"""
import json
import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET

ES_SYSTEMS = "/etc/emulationstation/es_systems.cfg"
EXCLUDED_SYSTEMS = {"/roms/tools"}  # Totobox itself lives there
SKIP_DIRS = {"images", "media", "downloaded_images", "snap", "snaps", "videos", "video", "manuals",
             "marquees", "screenshots", "boxart", "wheel", "saves", "states", "bios", "mgba", "imgs"}
MAX_DEPTH = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS systems (
  path TEXT PRIMARY KEY, name TEXT, fullname TEXT, command TEXT, emulators TEXT,
  sig TEXT, game_count INTEGER, fav_seeded INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS games (
  id INTEGER PRIMARY KEY, system_path TEXT, rel TEXT, name TEXT, sortkey TEXT, image TEXT,
  emulator TEXT, core TEXT, es_lastplayed TEXT, UNIQUE(system_path, rel));
CREATE INDEX IF NOT EXISTS games_by_system ON games(system_path, sortkey);
CREATE TABLE IF NOT EXISTS favorites (system_path TEXT, rel TEXT, PRIMARY KEY(system_path, rel));
"""


def norm_path(p):
    return os.path.normpath(p.rstrip("/")) if p else p


def parse_systems(cfg_path=ES_SYSTEMS):
    """List of dicts from es_systems.cfg, in file order."""
    root = ET.parse(cfg_path).getroot()
    out = []
    for s in root.findall("system"):
        path = norm_path((s.findtext("path") or "").strip())
        if not path:
            continue
        emulators = []
        for e in s.findall("emulators/emulator"):
            emulators.append([e.get("name"), [c.text.strip() for c in e.findall("cores/core") if c.text]])
        out.append({
            "path": path,
            "name": (s.findtext("name") or "").strip(),
            "fullname": (s.findtext("fullname") or s.findtext("name") or "").strip(),
            "extensions": set((s.findtext("extension") or "").split()),
            "command": (s.findtext("command") or "").strip(),
            "emulators": emulators,
        })
    return out


def scan_files(system_path, extensions, depth=0, prefix=""):
    """Relative paths of game files, like ES: matching extension, recursing into game folders."""
    found = []
    try:
        entries = sorted(os.scandir(system_path), key=lambda e: e.name)
    except OSError:
        return found
    for e in entries:
        if e.name.startswith("."):
            continue
        rel = prefix + e.name
        if e.is_dir(follow_symlinks=False):
            if depth < MAX_DEPTH and e.name.lower() not in SKIP_DIRS:
                found += scan_files(e.path, extensions, depth + 1, rel + "/")
        elif os.path.splitext(e.name)[1] in extensions:
            found.append(rel)
    return found


def parse_gamelist(gamelist_path):
    """{relative path: metadata} from a gamelist.xml. Missing or broken file -> {}."""
    meta = {}
    if not os.path.exists(gamelist_path):
        return meta
    try:
        root = ET.parse(gamelist_path).getroot()
    except ET.ParseError:
        return meta
    for g in root.iter("game"):
        p = (g.findtext("path") or "").strip()
        if not p:
            continue
        rel = os.path.normpath(p[2:] if p.startswith("./") else p).replace("\\", "/")
        meta[rel] = {
            "name": (g.findtext("name") or "").strip(),
            "sortname": (g.findtext("sortname") or "").strip(),
            "image": (g.findtext("image") or "").strip(),
            "emulator": (g.findtext("emulator") or "").strip() or None,
            "core": (g.findtext("core") or "").strip() or None,
            "favorite": (g.findtext("favorite") or "").strip().lower() == "true",
            "lastplayed": (g.findtext("lastplayed") or "").strip() or None,
        }
    return meta


def resolve_image(system_path, image):
    if not image:
        return ""
    if image.startswith("./"):
        image = image[2:]
    path = image if os.path.isabs(image) else os.path.join(system_path, image)
    return path if os.path.exists(path) else ""


def display_name(rel):
    return os.path.splitext(os.path.basename(rel))[0]


PACK_PREFIX = re.compile(r"^\s*\d+\s*=-\s*")  # ROM packs number their sortnames: "0002 =-  007 : NIGHTFIRE"


def sort_key(text):
    return PACK_PREFIX.sub("", text).casefold().strip()


def _mtime(p):
    try:
        return int(os.stat(p).st_mtime)
    except OSError:
        return 0


def signature(system, cfg_path):
    gl = os.path.join(system["path"], "gamelist.xml")
    return f"{_mtime(system['path'])}:{_mtime(gl)}:{_mtime(cfg_path)}"


class Index:
    def __init__(self, db_path, cfg_path=ES_SYSTEMS, roms_root="/roms/"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.executescript(SCHEMA)
        self.cfg_path = cfg_path
        self.roms_root = norm_path(roms_root) + os.sep

    def refresh(self, force=False, progress=None):
        """Rescan changed systems. Returns {"scanned": n, "seconds": t}."""
        t0 = time.time()
        systems = [s for s in parse_systems(self.cfg_path)
                   if s["path"] not in EXCLUDED_SYSTEMS and s["path"].startswith(self.roms_root)]
        seen, scanned = set(), 0
        for i, s in enumerate(systems):
            if s["path"] in seen:  # first definition wins, like ES
                continue
            seen.add(s["path"])
            sig = signature(s, self.cfg_path)
            row = self.db.execute("SELECT sig FROM systems WHERE path=?", (s["path"],)).fetchone()
            if row and row[0] == sig and not force:
                continue
            self._scan_system(s, sig)
            scanned += 1
            if progress:
                progress(i + 1, len(systems), s["fullname"])
        # drop systems that disappeared from the config
        known = {r[0] for r in self.db.execute("SELECT path FROM systems")}
        for gone in known - seen:
            self.db.execute("DELETE FROM systems WHERE path=?", (gone,))
            self.db.execute("DELETE FROM games WHERE system_path=?", (gone,))
        self.db.commit()
        return {"scanned": scanned, "seconds": round(time.time() - t0, 2)}

    def _scan_system(self, s, sig):
        files = scan_files(s["path"], s["extensions"]) if os.path.isdir(s["path"]) else []
        meta = parse_gamelist(os.path.join(s["path"], "gamelist.xml"))
        rows = []
        favs = []
        for rel in files:
            m = meta.get(rel, {})
            name = m.get("name") or display_name(rel)
            rows.append((s["path"], rel, name, sort_key(m.get("sortname") or name),
                         resolve_image(s["path"], m.get("image", "")), m.get("emulator"), m.get("core"),
                         m.get("lastplayed")))
            if m.get("favorite"):
                favs.append((s["path"], rel))
        self.db.execute("DELETE FROM games WHERE system_path=?", (s["path"],))
        self.db.executemany("INSERT INTO games (system_path, rel, name, sortkey, image, emulator, core, "
                            "es_lastplayed) VALUES (?,?,?,?,?,?,?,?)", rows)
        seeded = self.db.execute("SELECT fav_seeded FROM systems WHERE path=?", (s["path"],)).fetchone()
        if not (seeded and seeded[0]):
            self.db.executemany("INSERT OR IGNORE INTO favorites VALUES (?,?)", favs)
        self.db.execute("INSERT OR REPLACE INTO systems (path, name, fullname, command, emulators, sig, "
                        "game_count, fav_seeded) VALUES (?,?,?,?,?,?,?,1)",
                        (s["path"], s["name"], s["fullname"], s["command"], json.dumps(s["emulators"]),
                         sig, len(rows)))

    # ---- queries used by the screens ----
    def systems(self):
        """Systems with games, alphabetical by full name."""
        cur = self.db.execute("SELECT path, name, fullname, game_count FROM systems WHERE game_count > 0 "
                              "ORDER BY fullname COLLATE NOCASE")
        return [dict(zip(("path", "name", "fullname", "count"), r)) for r in cur]

    def system(self, path):
        r = self.db.execute("SELECT path, name, fullname, command, emulators FROM systems WHERE path=?",
                            (path,)).fetchone()
        if not r:
            return None
        return {"path": r[0], "name": r[1], "fullname": r[2], "command": r[3], "emulators": json.loads(r[4])}

    def games(self, system_path, only=None):
        """Games of a system, sorted. only: None | "favorites" | "never" (never_played set by caller)."""
        sql = ("SELECT g.id, g.rel, g.name, g.image, g.emulator, g.core, g.es_lastplayed, "
               "f.rel IS NOT NULL FROM games g LEFT JOIN favorites f "
               "ON f.system_path=g.system_path AND f.rel=g.rel WHERE g.system_path=?")
        if only == "favorites":
            sql += " AND f.rel IS NOT NULL"
        sql += " ORDER BY g.sortkey"
        keys = ("id", "rel", "name", "image", "emulator", "core", "es_lastplayed", "favorite")
        return [dict(zip(keys, r)) for r in self.db.execute(sql, (system_path,))]

    def game(self, system_path, rel):
        keys = ("id", "rel", "name", "image", "emulator", "core", "es_lastplayed", "favorite")
        r = self.db.execute("SELECT g.id, g.rel, g.name, g.image, g.emulator, g.core, g.es_lastplayed, "
                            "f.rel IS NOT NULL FROM games g LEFT JOIN favorites f ON f.system_path=g.system_path "
                            "AND f.rel=g.rel WHERE g.system_path=? AND g.rel=?", (system_path, rel)).fetchone()
        return dict(zip(keys, r)) if r else None

    def last_es_played(self):
        """(system_path, rel) of the game ES says was played last, or None."""
        r = self.db.execute("SELECT system_path, rel FROM games WHERE es_lastplayed IS NOT NULL "
                            "ORDER BY es_lastplayed DESC LIMIT 1").fetchone()
        return r

    def random_game(self, rng, systems=None):
        """Any game, uniformly, from the given consoles (default: all except Ports)."""
        if systems is None:
            where, args = "system_path NOT LIKE '%/ports'", []
        else:
            if not systems:
                return None
            where, args = f"system_path IN ({','.join('?' * len(systems))})", list(systems)
        n = self.db.execute(f"SELECT COUNT(*) FROM games WHERE {where}", args).fetchone()[0]
        if not n:
            return None
        return self.db.execute(f"SELECT system_path, rel FROM games WHERE {where} LIMIT 1 OFFSET ?",
                               args + [rng.randrange(n)]).fetchone()

    def toggle_favorite(self, system_path, rel):
        if self.db.execute("DELETE FROM favorites WHERE system_path=? AND rel=?", (system_path, rel)).rowcount:
            self.db.commit()
            return False
        self.db.execute("INSERT INTO favorites VALUES (?,?)", (system_path, rel))
        self.db.commit()
        return True

    def total_games(self):
        return self.db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
