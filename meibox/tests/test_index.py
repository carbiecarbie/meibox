import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from totobox import index  # noqa: E402

SYSTEMS_XML = """<systemList>
  <system><name>snes</name><fullname>SuFami Turbo</fullname><path>{root}/sufami/</path>
    <extension>.sfc .zip</extension><command>run %ROM%</command></system>
  <system><name>snes</name><fullname>Super NES</fullname><path>{root}/snes/</path>
    <extension>.sfc .SFC .zip .ZIP</extension>
    <command>sudo perfmax %GOVERNOR% %ROM%; /usr/local/bin/%EMULATOR% -L %CORE% %ROM%</command>
    <emulators><emulator name="retroarch"><cores><core>snes9x</core><core>snes9x2010</core></cores></emulator>
    <emulator name="retroarch32"><cores><core>snes9x2002</core></cores></emulator></emulators></system>
  <system><name>tools</name><fullname>Tools</fullname><path>{root}/tools/</path>
    <extension>.sh</extension><command>%ROM%</command></system>
  <system><name>empty</name><fullname>Empty</fullname><path>{root}/missing/</path>
    <extension>.zip</extension><command>x</command></system>
</systemList>"""

GAMELIST = """<?xml version="1.0"?><gameList>
  <game><path>./Zelda.sfc</path><name>The Legend of Zelda</name><sortname>Legend of Zelda</sortname>
    <image>./images/Zelda.png</image><favorite>true</favorite><lastplayed>20261103T195652</lastplayed></game>
  <game><path>./sub/Mario Kart.zip</path><name>Super Mario Kart</name><core>snes9x2010</core></game>
  <game><path>./Removed.sfc</path><name>Not on disk</name></game>
</gameList>"""


def touch(path, data=b""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.root = self.tmp.name.replace("\\", "/")
        touch(f"{r}/snes/Zelda.sfc")
        touch(f"{r}/snes/Aladdin.SFC")
        touch(f"{r}/snes/sub/Mario Kart.zip")
        touch(f"{r}/snes/images/Zelda.png", b"png")
        touch(f"{r}/snes/images/ignored.zip")      # media folders are skipped
        touch(f"{r}/snes/notes.txt")
        touch(f"{r}/snes/.hidden.sfc")
        touch(f"{r}/snes/gamelist.xml", GAMELIST.encode())
        touch(f"{r}/sufami/Poi Poi.sfc")
        touch(f"{r}/tools/Totobox.sh")
        self.cfg = f"{r}/es_systems.cfg"
        touch(self.cfg, SYSTEMS_XML.format(root=r).encode())
        index.EXCLUDED_SYSTEMS.add(index.norm_path(f"{r}/tools"))
        self.idx = index.Index(os.path.join(r, "db", "t.db"), cfg_path=self.cfg, roms_root=r + "/")

    def tearDown(self):
        self.idx.db.close()
        self.tmp.cleanup()

    def test_systems_keyed_by_path_and_tools_excluded(self):
        self.idx.refresh()
        names = [s["fullname"] for s in self.idx.systems()]
        self.assertEqual(names, ["SuFami Turbo", "Super NES"])  # alphabetical, both named "snes"

    def test_games_merge_gamelist_and_disk(self):
        self.idx.refresh()
        games = self.idx.games(index.norm_path(f"{self.root}/snes"))
        self.assertEqual([g["name"] for g in games], ["Aladdin", "The Legend of Zelda", "Super Mario Kart"])
        zelda = games[1]
        self.assertTrue(zelda["favorite"])
        self.assertTrue(zelda["image"].endswith("images/Zelda.png"))
        self.assertEqual(zelda["es_lastplayed"], "20261103T195652")
        self.assertEqual(games[2]["core"], "snes9x2010")
        self.assertEqual(games[2]["rel"], "sub/Mario Kart.zip")

    def test_rescan_only_when_changed(self):
        self.assertEqual(self.idx.refresh()["scanned"], 3)  # snes, sufami and the empty one
        self.assertEqual(self.idx.refresh()["scanned"], 0)
        future = time.time() + 5
        os.utime(f"{self.root}/sufami", (future, future))
        self.assertEqual(self.idx.refresh()["scanned"], 1)

    def test_favorites_seeded_once(self):
        snes = index.norm_path(f"{self.root}/snes")
        self.idx.refresh()
        self.assertFalse(self.idx.toggle_favorite(snes, "Zelda.sfc"))  # user removes it in Totobox
        self.idx.refresh(force=True)                                   # ES still says favorite
        self.assertFalse(self.idx.games(snes)[1]["favorite"])

    def test_pack_numbering_ignored_when_sorting(self):
        self.assertEqual(index.sort_key("0002 =-  007 : NIGHTFIRE"), "007 : nightfire")
        self.assertEqual(index.sort_key("Legend of Zelda"), "legend of zelda")

    def test_broken_gamelist_falls_back_to_filenames(self):
        touch(f"{self.root}/snes/gamelist.xml", b"<gameList><game>")
        self.idx.refresh(force=True)
        names = [g["name"] for g in self.idx.games(index.norm_path(f"{self.root}/snes"))]
        self.assertIn("Zelda", names)


if __name__ == "__main__":
    unittest.main()
