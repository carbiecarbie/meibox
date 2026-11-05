"""User settings, stored in the Totobox database."""
import json

DEFAULTS = {
    "lang": "pt",            # pt | en
    "sounds": True,
    "phrases": "both",       # both | mine | default
    "show_temp": True,
    "clock": "24",           # 24 | 12
    "since": None,           # epoch of first use (the Ficha starts here)
    "recent_phrases": [],    # last shown, to avoid repeats
    "roulette_accepted": 0,
    "roulette_systems": None,  # None = every console except Ports; else a list of console paths
    "player_name": "",       # "Como a Mei te chama"; empty = no name (read by the copilot too)
}


class Settings:
    def __init__(self, db):
        self.db = db
        db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        self.values = dict(DEFAULTS)
        for k, v in db.execute("SELECT key, value FROM settings"):
            try:
                self.values[k] = json.loads(v)
            except ValueError:
                pass

    def __getitem__(self, key):
        return self.values.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.values[key] = value
        self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, json.dumps(value)))
        self.db.commit()
