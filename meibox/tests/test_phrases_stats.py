import os
import random
import sqlite3
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from totobox import i18n, phrases, stats  # noqa: E402
from totobox.settings import Settings  # noqa: E402


class PhrasesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.default = os.path.join(self.tmp.name, "default")
        self.user = os.path.join(self.tmp.name, "user")
        os.makedirs(self.default)
        os.makedirs(self.user)
        with open(os.path.join(self.default, "frases-pt.txt"), "w", encoding="utf-8") as f:
            f.write("# comentário\nlembrete: Vai jogar {jogo}?\npiada: Piada padrão.\ncalor: Tô a {temp}!\n"
                    "tipoerrado: ignorada\nsorteio: Hoje é dia de {jogo}!\n")
        with open(os.path.join(self.user, "frases-pt.txt"), "w", encoding="utf-8") as f:
            f.write("piada: Piada minha.\n")
        self.settings = Settings(sqlite3.connect(":memory:"))

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, seed=1):
        return phrases.Phrases(self.settings, "pt", self.default, self.user, random.Random(seed))

    def test_parse_skips_comments_and_unknown_types(self):
        p = self.make()
        self.assertEqual(sorted(t for t, _ in p.lines), ["calor", "lembrete", "piada", "piada", "sorteio"])

    def test_blanks_must_be_filled(self):
        p = self.make()
        for _ in range(20):
            line = p.pick({"hora_n": 10})
            self.assertNotIn("{", line)
            self.assertNotIn("Vai jogar", line)  # no game -> no lembrete

    def test_context_and_no_repeats(self):
        p = self.make()
        seen = [p.pick({"hora_n": 10, "jogo": "Doom II", "temp": "72 °C", "temp_n": 72}) for _ in range(4)]
        self.assertEqual(len(set(seen)), 4)  # four different lines before repeating
        self.assertIn("Vai jogar Doom II?", seen)
        self.assertIn("Tô a 72 °C!", seen)

    def test_modes(self):
        self.settings["phrases"] = "mine"
        self.assertEqual([t for _, t in self.make().lines], ["Piada minha."])
        self.settings["phrases"] = "default"
        self.assertNotIn("Piada minha.", [t for _, t in self.make().lines])

    def test_only_type(self):
        self.assertEqual(self.make().pick({"jogo": "Crystalis"}, only_type="sorteio"), "Hoje é dia de Crystalis!")


class StatsTest(unittest.TestCase):
    def setUp(self):
        i18n.set_lang("pt")
        self.s = stats.Stats(sqlite3.connect(":memory:"))
        base = time.mktime((2026, 11, 3, 20, 0, 0, 0, 0, -1))
        self.s.add("/roms/gba", "doom2.zip", "Doom II", base, base + 3 * 3600)              # marathon
        self.s.add("/roms/gba", "doom2.zip", "Doom II", base + 86400, base + 86400 + 600)
        night = time.mktime((2026, 11, 4, 3, 39, 0, 0, 0, -1))
        self.s.add("/roms/mame2003", "tmnt2.zip", "Turtles", night, night + 900, via_roulette=True)
        self.s.add("/roms/snes", "x.zip", "Quick", base, base + 20)                          # not a play

    def test_summary(self):
        r = self.s.summary()
        self.assertEqual(r["plays"], 3)
        self.assertEqual(r["top"]["name"], "Doom II")
        self.assertTrue(r["marathon"])
        self.assertTrue(r["owl"])
        self.assertEqual(r["roulette"], 1)
        self.assertEqual(r["latest"][1], "Turtles")
        self.assertEqual(r["per_system"][0][0], "/roms/gba")

    def test_duration_and_when(self):
        self.assertEqual(stats.duration(6 * 3600 + 12 * 60), "6 h 12")
        self.assertEqual(stats.duration(45 * 60), "45 min")
        now = time.mktime((2026, 11, 4, 12, 0, 0, 0, 0, -1))
        self.assertEqual(stats.when(now - 3600, now), "hoje")
        self.assertEqual(stats.when(now - 20 * 3600, now), "ontem")
        i18n.set_lang("en")
        self.assertEqual(stats.when(now - 3 * 86400, now), "3 days ago")
        i18n.set_lang("pt")


class I18nTest(unittest.TestCase):
    def test_both_languages_have_the_same_keys(self):
        import json
        pt = json.load(open(os.path.join(i18n.LANG_DIR, "pt.json"), encoding="utf-8"))
        en = json.load(open(os.path.join(i18n.LANG_DIR, "en.json"), encoding="utf-8"))
        self.assertEqual(set(pt), set(en))

    def test_numbers(self):
        i18n.set_lang("pt")
        self.assertEqual(i18n.num(15058), "15.058")
        i18n.set_lang("en")
        self.assertEqual(i18n.num(15058), "15,058")
        i18n.set_lang("pt")


if __name__ == "__main__":
    unittest.main()
