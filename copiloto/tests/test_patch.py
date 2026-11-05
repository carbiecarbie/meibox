"""Fase B: device/retroarch-patch.py (troca só as 6 linhas, backup, desfazer, conferências)."""
import importlib.util
import os
import tempfile
import unittest
from unittest import mock

_spec = importlib.util.spec_from_file_location(
    "patch", os.path.join(os.path.dirname(__file__), "..", "device", "retroarch-patch.py"))
patch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(patch)

CFG = (
    'ai_service_enable = "false"\n'
    'ai_service_mode = "0"\n'
    'ai_service_pause = "false"\n'
    'ai_service_url = "http://localhost:4404/"\n'
    'config_save_on_exit = "false"\n'
    'input_ai_service_btn = "nul"\n'
    'input_enable_hotkey_btn = "12"\n'
    'input_player1_r_btn = "5"\n'
    'menu_driver = "rgui"\n'
    'network_cmd_enable = "false"\n'
    'network_cmd_port = "55355"\n'
)


class TestPatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfgs = []
        for nome in ("retroarch", "retroarch32"):
            d = os.path.join(self.tmp.name, nome)
            os.makedirs(os.path.join(d, "config", "Snes9x"))
            p = os.path.join(d, "retroarch.cfg")
            with open(p, "w", newline="") as f:
                f.write(CFG)
            self.cfgs.append(p)
        self.p1 = mock.patch.object(patch, "CONFIGS", self.cfgs)
        self.p2 = mock.patch.object(patch, "retroarch_aberto", lambda: False)
        self.p1.start()
        self.p2.start()

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()
        self.tmp.cleanup()

    def _ler(self, p):
        with open(p, newline="") as f:
            return f.read()

    def test_conferir_nao_grava(self):
        self.assertEqual(patch.principal("conferir"), 0)
        self.assertEqual(self._ler(self.cfgs[0]), CFG)
        self.assertFalse(os.path.exists(self.cfgs[0] + ".antes-copiloto"))

    def test_aplicar_e_desfazer(self):
        self.assertEqual(patch.principal("aplicar"), 0)
        for p in self.cfgs:
            v = patch.valores(patch.ler(p))
            self.assertEqual(v["ai_service_enable"], "true")
            self.assertEqual(v["input_ai_service_btn"], "5")
            self.assertEqual(v["network_cmd_enable"], "true")
            self.assertEqual(v["ai_service_url"], "http://127.0.0.1:4404/")
            self.assertEqual(v["menu_driver"], "rgui")
            self.assertEqual(v["input_player1_r_btn"], "5")
            self.assertEqual(self._ler(p + ".antes-copiloto"), CFG)
        # o usuário muda outra coisa depois; desfazer não pode apagar isso
        txt = self._ler(self.cfgs[0]).replace('menu_driver = "rgui"', 'menu_driver = "ozone"')
        with open(self.cfgs[0], "w", newline="") as f:
            f.write(txt)
        self.assertEqual(patch.principal("aplicar"), 0)  # segunda vez: idempotente
        self.assertEqual(self._ler(self.cfgs[0] + ".antes-copiloto"), CFG)  # backup não muda
        self.assertEqual(patch.principal("desfazer"), 0)
        self.assertEqual(self._ler(self.cfgs[0]), CFG.replace('"rgui"', '"ozone"'))
        self.assertEqual(self._ler(self.cfgs[1]), CFG)

    def test_crlf_preservado(self):
        with open(self.cfgs[0], "w", newline="") as f:
            f.write(CFG.replace("\n", "\r\n"))
        self.assertEqual(patch.principal("aplicar"), 0)
        self.assertNotIn("\n", self._ler(self.cfgs[0]).replace("\r\n", ""))

    def test_para_se_faltar_linha_ou_conflito(self):
        with open(self.cfgs[0], "w", newline="") as f:
            f.write(CFG.replace('network_cmd_enable = "false"\n', ""))
        with open(self.cfgs[1], "w", newline="") as f:
            f.write(CFG + 'input_screenshot_btn = "5"\n')
        self.assertEqual(patch.principal("aplicar"), 1)
        self.assertFalse(os.path.exists(self.cfgs[0] + ".antes-copiloto"))
        self.assertFalse(os.path.exists(self.cfgs[1] + ".antes-copiloto"))

    def test_override_de_nucleo(self):
        with open(os.path.join(os.path.dirname(self.cfgs[0]), "config", "Snes9x", "Snes9x.cfg"), "w") as f:
            f.write('ai_service_enable = "false"\n')
        self.assertEqual(patch.principal("aplicar"), 1)
        self.assertEqual(self._ler(self.cfgs[1]), CFG)  # a outra config também fica intacta

    def test_recusa_com_retroarch_aberto(self):
        with mock.patch.object(patch, "retroarch_aberto", lambda: True):
            self.assertEqual(patch.principal("aplicar"), 3)


if __name__ == "__main__":
    unittest.main()
