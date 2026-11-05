import os
import shlex
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from totobox import launcher  # noqa: E402

RA = ("sudo perfmax %GOVERNOR% %ROM%; nice -n -19 /usr/local/bin/%EMULATOR% -L "
      "/home/ark/.config/%EMULATOR%/cores/%CORE%_libretro.so %ROM%; sudo perfnorm")
EMUS = [["retroarch", ["mgba_rumble", "mgba", "gpsp"]], ["retroarch32", ["gpsp"]]]


class LauncherTest(unittest.TestCase):
    def test_default_is_first_emulator_and_core(self):
        self.assertEqual(launcher.pick_emulator(EMUS), ("retroarch", "mgba_rumble"))

    def test_game_choice_wins(self):
        self.assertEqual(launcher.pick_emulator(EMUS, None, "gpsp"), ("retroarch", "gpsp"))
        self.assertEqual(launcher.pick_emulator(EMUS, "retroarch32"), ("retroarch32", "gpsp"))

    def test_command_matches_es_shape(self):
        cmd = launcher.build_command(RA, "/roms/gba/Doom II (USA).zip", EMUS, None, "gpsp")
        self.assertEqual(cmd, "sudo perfmax performance '/roms/gba/Doom II (USA).zip'; nice -n -19 "
                              "/usr/local/bin/retroarch -L /home/ark/.config/retroarch/cores/gpsp_libretro.so "
                              "'/roms/gba/Doom II (USA).zip'; sudo perfnorm")

    def test_awkward_names_survive_the_shell(self):
        for name in ["Sonic & Knuckles + Sonic 2.md", "Dragon Ball Z - Buu's Fury.gba", "a;b$(c)`d`.zip",
                     "Pokémon \"Red\".gb"]:
            rom = "/roms/x/" + name
            cmd = launcher.build_command("run %ROM%", rom, [])
            self.assertEqual(shlex.split(cmd), ["run", rom])

    def test_systems_without_emulators(self):
        cmd = launcher.build_command("sudo perfmax %GOVERNOR% %ROM%; nice -n -19 %ROM%; sudo perfnorm",
                                     "/roms/ports/Balatro.sh", [])
        self.assertEqual(cmd, "sudo perfmax performance /roms/ports/Balatro.sh; nice -n -19 "
                              "/roms/ports/Balatro.sh; sudo perfnorm")


if __name__ == "__main__":
    unittest.main()
