import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from totobox.screens.library import folder_label, split_view  # noqa: E402

GAMES = [{"rel": r, "name": r.rsplit("/", 1)[-1]} for r in [
    "Zelda.sfc", "# PT-BR #/Chrono (BR).sfc", "# PT-BR #/Mario (BR).sfc", "Featured Games/ActRaiser.sfc",
    "Featured Games/deep/Hidden.sfc", "Aladdin.sfc"]]


class FoldersTest(unittest.TestCase):
    def test_top_level_shows_folders_first_then_games(self):
        items = split_view(GAMES, "")
        self.assertEqual([(i.get("folder", False), i["name"]) for i in items],
                         [(True, "Featured Games"), (True, "PT-BR"), (False, "Zelda.sfc"), (False, "Aladdin.sfc")])
        self.assertEqual(items[0]["count"], 2)  # counts games in subfolders too
        self.assertEqual(items[1]["rel"], "# PT-BR #/")

    def test_inside_a_folder(self):
        items = split_view(GAMES, "Featured Games/")
        self.assertEqual([i["name"] for i in items], ["deep", "ActRaiser.sfc"])

    def test_label(self):
        self.assertEqual(folder_label("# SUPER FAMICOM (JP) #"), "SUPER FAMICOM (JP)")
        self.assertEqual(folder_label("Classic Game"), "Classic Game")


if __name__ == "__main__":
    unittest.main()
