import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from totobox.screens import roulette  # noqa: E402


class FakeIndex:
    """Two consoles like the R36S pack: SNES with almost no covers, GBA with covers everywhere."""

    def __init__(self):
        self.games = {}
        for i in range(1332):
            self.games[("/roms/snes", f"s{i}.zip")] = "cover.png" if i < 3 else ""
        for i in range(1081):
            self.games[("/roms/gba", f"g{i}.zip")] = "cover.png"
        self.games[("/roms/alg", "only.zip")] = ""

    def random_game(self, rng, systems=None):
        keys = [k for k in self.games if systems is None or k[0] in systems]
        return rng.choice(sorted(keys)) if keys else None

    def game(self, path, rel):
        return {"rel": rel, "name": rel, "image": self.games[(path, rel)], "emulator": None, "core": None}

    def system(self, path):
        return {"path": path, "name": path.rsplit("/", 1)[-1], "fullname": path}


class FakeApp:
    def __init__(self, systems):
        self.index = FakeIndex()
        self.settings = {"roulette_systems": systems, "roulette_accepted": 0}


def make(systems, seed=3):
    return roulette.Roulette(FakeApp(systems), random.Random(seed))


class RouletteTest(unittest.TestCase):
    def test_console_without_covers_still_spins(self):  # the SNES / Super Famicom bug
        r = make(["/roms/snes"])
        self.assertEqual(r.state, "loading")
        self.assertEqual(len(r.items), roulette.STRIP)
        self.assertTrue(all(s["path"] == "/roms/snes" for s, _ in r.items))

    def test_single_game_console(self):
        r = make(["/roms/alg"])
        self.assertEqual(len(r.items), roulette.STRIP)
        self.assertEqual(r.winner[1]["rel"], "only.zip")

    def test_nothing_checked(self):
        self.assertEqual(make([]).state, "empty")

    def test_winner_is_not_biased_towards_covers(self):
        # with SNES (no covers) + GBA (covers), SNES should still win about half the time
        wins = sum(make(["/roms/snes", "/roms/gba"], seed=s).winner[0]["path"] == "/roms/snes" for s in range(200))
        self.assertGreater(wins, 70)


if __name__ == "__main__":
    unittest.main()
