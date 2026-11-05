"""'Como a Mei te chama': arcade name editor (capitals, accents, 12-letter limit, saving)."""
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from totobox.player_name import ALPHABET, MAX_LEN, NameEditor, to_editable, to_saved  # noqa: E402
from totobox.settings import Settings  # noqa: E402


def type_name(e, word):
    """Types a word letter by letter with up/down only, like on the device."""
    for ch in word:
        if e.current() is None:
            e.change(1)  # new slot starts at A
        target = ALPHABET.index(ch)
        while e.letters[e.pos] != ch:
            cur = ALPHABET.index(e.letters[e.pos])
            e.change(1 if (target - cur) % len(ALPHABET) <= len(ALPHABET) // 2 else -1)
        e.move(1)


class TestSaving(unittest.TestCase):
    def test_capitalization(self):
        self.assertEqual(to_saved(list("LULU")), "Lulu")
        self.assertEqual(to_saved(list("ANA LUIZA")), "Ana luiza")  # only the first letter (design 12.4)

    def test_accents(self):
        self.assertEqual(to_saved(list("ÁGATA")), "Ágata")
        self.assertEqual(to_saved(list("JOÃO")), "João")
        self.assertEqual(to_saved(list("ÇÉU")), "Çéu")
        self.assertEqual(to_editable("Ágata"), list("ÁGATA"))
        self.assertEqual(to_editable("joão"), list("JOÃO"))

    def test_spaces_and_empty(self):
        self.assertEqual(to_saved(list("  ANA   LU ")), "Ana lu")
        self.assertEqual(to_saved([" ", " "]), "")
        self.assertEqual(to_saved([]), "")

    def test_unknown_letters_dropped(self):
        self.assertEqual(to_editable("Zoë-2"), list("ZO"))

    def test_limit(self):
        self.assertEqual(len(to_editable("A" * 30)), MAX_LEN)
        self.assertEqual(to_saved(list("ABCDEFGHIJKLMNOP")), "Abcdefghijkl")


class TestEditor(unittest.TestCase):
    def test_type_and_save(self):
        e = NameEditor()
        type_name(e, "LULU")
        self.assertEqual(e.saved(), "Lulu")

    def test_accented_letters_reachable(self):
        e = NameEditor()
        type_name(e, "JOÃO")
        self.assertEqual(e.saved(), "João")

    def test_twelve_letter_limit(self):
        e = NameEditor()
        for _ in range(20):
            if e.current() is None:
                e.change(1)
            e.move(1)
        self.assertEqual(len(e.letters), MAX_LEN)
        self.assertEqual(e.pos, MAX_LEN - 1)
        e.change(1)  # changing the last box keeps 12 letters
        self.assertEqual(len(e.letters), MAX_LEN)

    def test_wraps_around(self):
        e = NameEditor()
        e.change(1)
        self.assertEqual(e.current(), "A")
        e.change(-1)
        self.assertEqual(e.current(), " ")  # A -> space (the end of the wheel)
        e.change(1)
        self.assertEqual(e.current(), "A")
        e2 = NameEditor()
        e2.change(-1)
        self.assertEqual(e2.current(), "Z")

    def test_erase(self):
        e = NameEditor("Marina")
        self.assertEqual(e.pos, 6)          # on the empty slot after the name
        self.assertTrue(e.erase())          # backspace
        self.assertEqual(e.saved(), "Marin")
        e.move(-10)
        self.assertTrue(e.erase())          # removes the letter under the cursor
        self.assertEqual(e.saved(), "Arin")
        for _ in range(4):
            e.erase()
        self.assertFalse(e.erase())         # nothing left: the screen goes back

    def test_cursor_bounds(self):
        e = NameEditor("Ana")
        e.move(5)
        self.assertEqual(e.pos, 3)          # at most one empty slot after the name
        e.move(-9)
        self.assertEqual(e.pos, 0)
        full = NameEditor("ABCDEFGHIJKL")
        self.assertEqual(full.pos, MAX_LEN - 1)


class TestFooter(unittest.TestCase):
    def test_optional_footer(self):
        import tempfile
        from totobox.screens.ficha import footer_text
        self.assertEqual(footer_text("/nao/existe.txt"), "")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("meusite.com.br\nsegunda linha\n")
        try:
            self.assertEqual(footer_text(f.name), "meusite.com.br")
        finally:
            os.remove(f.name)


class TestSetting(unittest.TestCase):
    def test_saved_in_settings(self):
        db = sqlite3.connect(":memory:")
        s = Settings(db)
        self.assertEqual(s["player_name"], "")
        s["player_name"] = NameEditor("ágata").saved()
        self.assertEqual(Settings(db)["player_name"], "Ágata")
        raw = db.execute("SELECT value FROM settings WHERE key='player_name'").fetchone()[0]
        self.assertEqual(raw, '"\\u00c1gata"')  # JSON, like the other settings (the copilot decodes it)


if __name__ == "__main__":
    unittest.main()
