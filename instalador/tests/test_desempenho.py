import io
import json
import contextlib
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
PACOTE_FONTE = os.path.join(os.path.dirname(AQUI), "cartao", "totobox", "instalador", "desempenho")
sys.path.insert(0, PACOTE_FONTE)
import desempenho as d  # noqa: E402


def rom_snes(titulo, tipo, tamanho=0x80000):
    """LoROM mínima com cabeçalho válido em 0x7FC0."""
    rom = bytearray(tamanho)
    h = 0x7FC0
    rom[h:h + 21] = titulo.encode("ascii").ljust(21, b" ")
    rom[h + 0x15] = 0x20  # LoROM
    rom[h + 0x16] = tipo
    rom[h + 0x1C:h + 0x1E] = (0x1234 ^ 0xFFFF).to_bytes(2, "little")
    rom[h + 0x1E:h + 0x20] = (0x1234).to_bytes(2, "little")
    return bytes(rom)


def rom_gba(codigo):
    rom = bytearray(0x200)
    rom[0xA0:0xAC] = b"JOGO".ljust(12, b"\0")
    rom[0xAC:0xB0] = codigo.encode("ascii")
    return bytes(rom)


def zipar(caminho, nome_interno, dados):
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr(nome_interno, dados)


ES = """<systemList>
 <system><name>snes</name><path>{roms}/snes/</path>
  <emulators><emulator name="retroarch"><cores><core>snes9x</core><core>chimerasnes</core>
  <core>mednafen_supafaust</core></cores></emulator></emulators></system>
 <system><name>gba</name><path>{roms}/gba/</path>
  <emulators><emulator name="retroarch"><cores><core>mgba_rumble</core><core>mgba</core>
  <core>gpsp</core></cores></emulator></emulators></system>
 <system><name>nes</name><path>{roms}/nes/</path>
  <emulators><emulator name="retroarch"><cores><core>fceumm</core></cores></emulator></emulators></system>
</systemList>
"""


class Cabecalhos(unittest.TestCase):
    def test_snes_superfx(self):
        self.assertEqual(d.snes_cabecalho(rom_snes("STAR FOX", 0x13)), ("STAR FOX", "SuperFX"))

    def test_snes_sem_chip_e_sa1(self):
        self.assertEqual(d.snes_cabecalho(rom_snes("SUPER MARIOWORLD", 0x02))[1], None)
        self.assertEqual(d.snes_cabecalho(rom_snes("KIRBY SUPER DELUXE", 0x35))[1], "SA-1")

    def test_snes_cabecalho_de_copiadora(self):
        self.assertEqual(d.snes_cabecalho(b"\0" * 512 + rom_snes("DOOM", 0x15)), ("DOOM", "SuperFX"))

    def test_snes_lendo_so_o_comeco(self):
        tmp = tempfile.mkdtemp()
        try:
            com_copiadora = b"\0" * 512 + rom_snes("DOOM", 0x15, 0x200000)
            p = os.path.join(tmp, "Doom.zip")
            zipar(p, "doom.smc", com_copiadora)
            comeco, tamanho = d.ler_snes(p)
            self.assertEqual((len(comeco), tamanho), (0x10200, len(com_copiadora)))
            self.assertEqual(d.snes_cabecalho(comeco, tamanho), ("DOOM", "SuperFX"))
            solta = os.path.join(tmp, "sf.sfc")
            with open(solta, "wb") as f:
                f.write(rom_snes("STAR FOX", 0x13))
            self.assertEqual(d.snes_cabecalho(*d.ler_snes(solta)), ("STAR FOX", "SuperFX"))
        finally:
            shutil.rmtree(tmp)

    def test_gba_dentro_do_zip(self):
        tmp = tempfile.mkdtemp()
        try:
            p = os.path.join(tmp, "F-Zero.zip")
            zipar(p, "F-Zero.gba", rom_gba("BFZE"))
            self.assertEqual(d.gba_codigo(p), "BFZE")
            with open(os.path.join(tmp, "quebrado.zip"), "wb") as f:
                f.write(b"nao e zip")
            self.assertIsNone(d.gba_codigo(os.path.join(tmp, "quebrado.zip")))
        finally:
            shutil.rmtree(tmp)


class Sistemas(unittest.TestCase):
    def test_le_todos_os_cores_inclusive_o_primeiro(self):
        tmp = tempfile.mkdtemp()
        try:
            es = os.path.join(tmp, "es.cfg")
            with open(es, "w", encoding="utf-8") as f:
                f.write(ES.format(roms="/roms"))
            sis = {s["nome"]: s for s in d.sistemas([es])}
            self.assertEqual(sis["snes"]["emuladores"]["retroarch"], ["snes9x", "chimerasnes", "mednafen_supafaust"])
            self.assertEqual(sis["gba"]["pasta"], "/roms/gba")
        finally:
            shutil.rmtree(tmp)


class Gamelist(unittest.TestCase):
    BASE = ('<?xml version="1.0"?>\n<gameList>\n\t<game>\n\t\t<path>./Star Fox (USA).zip</path>\n'
            '\t\t<name>Star Fox</name>\n\t\t<playcount>3</playcount>\n\t</game>\n</gameList>\n')

    def test_por_e_tirar_mantem_o_resto(self):
        t = d.gamelist_por(self.BASE, "Star Fox (USA).zip", "retroarch", "mednafen_supafaust")
        self.assertIn("<core>mednafen_supafaust</core>", t)
        self.assertIn("<playcount>3</playcount>", t)
        self.assertEqual(t.count("<game>"), 1)
        de_volta = d.gamelist_tirar(t, "Star Fox (USA).zip", "mednafen_supafaust")
        self.assertNotIn("<core>", de_volta)
        self.assertIn("<playcount>3</playcount>", de_volta)

    def test_cria_entrada_e_escapa(self):
        t = d.gamelist_por(self.BASE, "Tom & Jerry.zip", "retroarch", "gpsp")
        self.assertIn("<path>./Tom &amp; Jerry.zip</path>", t)
        self.assertEqual(t.count("<game>"), 2)
        t2 = d.gamelist_por(t, "Tom & Jerry.zip", "retroarch", "gpsp")
        self.assertEqual(t2.count("<game>"), 2)  # não duplica

    def test_tirar_nao_mexe_na_escolha_da_pessoa(self):
        t = d.gamelist_por(self.BASE, "Star Fox (USA).zip", "retroarch", "snes9x2010")
        self.assertEqual(d.gamelist_tirar(t, "Star Fox (USA).zip", "mednafen_supafaust"), t)


class Ciclo(unittest.TestCase):
    """Aplicar, boot, remover e boot de novo, numa casa e numa biblioteca falsas."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.casa = os.path.join(self.tmp, "home")
        roms = os.path.join(self.tmp, "roms")
        for s in ("snes", "gba", "nes"):
            os.makedirs(os.path.join(roms, s))
        self.roms = roms
        zipar(os.path.join(roms, "snes", "Star Fox (USA).zip"), "sf.sfc", rom_snes("STAR FOX", 0x13))
        zipar(os.path.join(roms, "snes", "Yoshi's Island (USA).zip"), "y.sfc", rom_snes("YOSHI'S ISLAND", 0x15))
        zipar(os.path.join(roms, "snes", "Super Mario World (USA).zip"), "m.sfc", rom_snes("SUPER MARIOWORLD", 0x02))
        os.makedirs(os.path.join(roms, "snes", "hacks"))
        with open(os.path.join(roms, "snes", "hacks", "Doom.sfc"), "wb") as f:
            f.write(rom_snes("DOOM", 0x15))
        zipar(os.path.join(roms, "gba", "F-Zero GP (BR).zip"), "f.gba", rom_gba("BFZP"))  # outra região
        zipar(os.path.join(roms, "gba", "Golden Sun.zip"), "g.gba", rom_gba("AGSE"))
        with open(os.path.join(roms, "gba", "Doom II.gba"), "wb") as f:
            f.write(rom_gba("A9DE"))
        with open(os.path.join(roms, "snes", "gamelist.xml"), "w", encoding="utf-8") as f:
            f.write(Gamelist.BASE)
        es = os.path.join(self.tmp, "es_systems.cfg")
        with open(es, "w", encoding="utf-8") as f:
            f.write(ES.format(roms=roms.replace(os.sep, "/")))
        self.es = es
        # cores instalados no sistema (originais) e o pacote com os nossos
        self.cores = os.path.join(self.casa, ".config", "retroarch", "cores")
        os.makedirs(self.cores)
        for c in ("snes9x", "mgba", "mgba_rumble", "gpsp", "mednafen_supafaust", "chimerasnes"):
            with open(os.path.join(self.cores, c + "_libretro.so"), "wb") as f:
                f.write(b"original " + c.encode())
        self.pacote = os.path.join(self.tmp, "pacote")
        os.makedirs(os.path.join(self.pacote, "cores"))
        shutil.copy(os.path.join(PACOTE_FONTE, "regras.json"), self.pacote)
        for c in ("snes9x", "mgba", "gpsp"):
            with open(os.path.join(self.pacote, "cores", c + "_libretro.so"), "wb") as f:
                f.write(b"nosso " + c.encode())
        # ajuste que a pessoa já tinha
        self.ajustes = os.path.join(self.casa, ".config", "retroarch", "config")
        os.makedirs(os.path.join(self.ajustes, "mGBA"))
        with open(os.path.join(self.ajustes, "mGBA", "mGBA.cfg"), "w") as f:
            f.write('video_shader_enable = "true"\n')

        self.antigos = {k: getattr(d, k) for k in ("APP", "ESTADO", "CORES", "AJUSTES", "ES_SYSTEMS",
                                                   "abre_aqui", "instalar_gancho", "subprocess")}
        d.APP = os.path.join(self.casa, ".local", "share", "meibox-desempenho")
        d.ESTADO = os.path.join(d.APP, "estado.json")
        d.CORES, d.AJUSTES, d.ES_SYSTEMS = self.cores, self.ajustes, [es]
        d.abre_aqui = lambda caminho: "gpsp" not in caminho  # gpSP "não abre" neste sistema falso
        self.ganchos = []
        d.instalar_gancho = lambda: self.ganchos.append(1)

        class SemSudo:
            @staticmethod
            def run(*a, **k):
                return None
        d.subprocess = SemSudo

    def tearDown(self):
        for k, v in self.antigos.items():
            setattr(d, k, v)
        shutil.rmtree(self.tmp)

    def ler(self, *partes):
        with open(os.path.join(*partes), encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_ciclo_completo(self):
        plano = d.planejar(self.pacote)
        situ = {c["core"]: c["situacao"] for c in plano["cores"]}
        self.assertEqual(situ, {"snes9x_libretro.so": "trocar", "mgba_libretro.so": "trocar",
                                "mgba_rumble_libretro.so": "trocar", "gpsp_libretro.so": "nao_abre"})
        arquivos = {os.path.relpath(a["arquivo"], self.ajustes).replace(os.sep, "/"): a for a in plano["ajustes"]}
        self.assertIn("Snes9x/Star Fox (USA).cfg", arquivos)          # SuperFX: com thread
        self.assertIn("Snes9x/Yoshi's Island (USA).cfg", arquivos)
        self.assertIn("Snes9x/Doom.cfg", arquivos)                    # subpasta
        self.assertNotIn("Snes9x/Super Mario World (USA).cfg", arquivos)
        self.assertIn("mGBA/F-Zero GP (BR).cfg", arquivos)            # pelo código, outra região
        self.assertNotIn("mGBA/Golden Sun.cfg", arquivos)
        self.assertEqual(arquivos["mGBA/mGBA.cfg"]["situacao"], "manter_da_pessoa")
        jogos = {(os.path.basename(os.path.dirname(g["gamelist"])), g["rom"], g["core"]) for g in plano["gamelist"]}
        self.assertEqual(jogos, {("snes", "Star Fox (USA).zip", "mednafen_supafaust"),
                                 ("snes", "hacks/Doom.sfc", "chimerasnes")})  # gpSP não abriu: GBA fica no mGBA

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(d.main(["aplicar", self.pacote]), 0)
        self.assertEqual(self.ler(self.cores, "mgba_rumble_libretro.so"), "nosso mgba")
        self.assertEqual(self.ler(self.cores, "gpsp_libretro.so"), "original gpsp")
        self.assertEqual(self.ler(self.ajustes, "mGBA", "mGBA.cfg"), 'video_shader_enable = "true"\n')
        self.assertIn('video_threaded = "true"', self.ler(self.ajustes, "Snes9x", "Star Fox (USA).cfg"))
        self.assertIn('video_threaded = "false"', self.ler(self.ajustes, "Snes9x", "Snes9x.cfg"))
        self.assertTrue(self.ganchos)
        self.assertNotIn("<core>", self.ler(self.roms, "snes", "gamelist.xml"))  # só no boot

        d.boot()
        gl = self.ler(self.roms, "snes", "gamelist.xml")
        self.assertIn("<core>mednafen_supafaust</core>", gl)
        self.assertIn("<path>./hacks/Doom.sfc</path>", gl)
        self.assertIn("<playcount>3</playcount>", gl)
        self.assertTrue(os.path.exists(os.path.join(self.roms, "snes", "gamelist.xml" + d.BACKUP_GL)))
        self.assertEqual(d.main(["instalado"]), 0)

        with contextlib.redirect_stdout(io.StringIO()):
            d.main(["aplicar", self.pacote])  # de novo (atualização): nada quebra
        self.assertTrue(os.path.exists(os.path.join(d.APP, "originais", "snes9x_libretro.so")))
        self.assertEqual(self.ler(d.APP, "originais", "snes9x_libretro.so"), "original snes9x")
        d.boot()
        self.assertEqual(self.ler(self.roms, "snes", "gamelist.xml").count("<core>mednafen_supafaust</core>"), 1)

        d.main(["remover"])
        self.assertEqual(self.ler(self.cores, "snes9x_libretro.so"), "original snes9x")
        self.assertEqual(self.ler(self.cores, "mgba_rumble_libretro.so"), "original mgba_rumble")
        self.assertFalse(os.path.exists(os.path.join(self.ajustes, "Snes9x")))
        self.assertTrue(os.path.exists(os.path.join(self.ajustes, "mGBA", "mGBA.cfg")))
        d.boot()
        gl = self.ler(self.roms, "snes", "gamelist.xml")
        self.assertNotIn("<core>", gl)
        self.assertIn("<playcount>3</playcount>", gl)
        self.assertFalse(os.path.exists(d.APP))
        self.assertEqual(d.main(["instalado"]), 1)

    def test_remover_sem_ter_aplicado(self):
        d.main(["remover"])
        self.assertFalse(self.ganchos)
        self.assertEqual(self.ler(self.cores, "snes9x_libretro.so"), "original snes9x")

    def test_core_trocado_depois_pelo_sistema_nao_e_desfeito(self):
        with contextlib.redirect_stdout(io.StringIO()):
            d.main(["aplicar", self.pacote])
        with open(os.path.join(self.cores, "snes9x_libretro.so"), "wb") as f:
            f.write(b"atualizacao do sistema")
        d.main(["remover"])
        self.assertEqual(self.ler(self.cores, "snes9x_libretro.so"), "atualizacao do sistema")

    def test_resumo(self):
        texto = d.resumo(d.planejar(self.pacote))
        self.assertIn("snes9x", texto)
        self.assertIn("gpSP", texto)  # nos mantidos
        self.assertIn("2 jogos", texto)


class Regras(unittest.TestCase):
    def test_regras_conferem_com_o_medido(self):
        with open(os.path.join(PACOTE_FONTE, "regras.json"), encoding="utf-8") as f:
            r = json.load(f)
        self.assertEqual(len(r["gba_com_thread"]), 100)
        self.assertEqual(set(r["gba_core_por_codigo"]), {"A9D", "AD9", "BFZ", "ALU"})
        self.assertEqual(r["cores"]["mgba_rumble_libretro.so"], "mgba_libretro.so")


if __name__ == "__main__":
    unittest.main()
