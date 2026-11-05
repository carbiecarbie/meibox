"""Passo 1: partes puras (config, label, uso, diário, mensagens, prompts, jogador)."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from copiloto import config, diario, jogador, label, mensagens, prompts, uso  # noqa: E402


class TestLabel(unittest.TestCase):
    def test_snes(self):
        d = label.interpretar("super_nes__ActRaiser (USA)")
        self.assertEqual(d["console"], "Super Nintendo")
        self.assertEqual(d["jogo"], "ActRaiser")
        self.assertEqual(d["regiao"], "USA")

    def test_gba_varias_regioes(self):
        d = label.interpretar("game_boy_advance__Advance Wars 2 - Black Hole Rising (USA, Australia)")
        self.assertEqual(d["console"], "Game Boy Advance")
        self.assertEqual(d["jogo"], "Advance Wars 2 - Black Hole Rising")
        self.assertEqual(d["regiao"], "USA, Australia")

    def test_marcas(self):
        self.assertEqual(label.limpar_nome("Super Metroid (Japan, USA) (En,Ja) [!]"), "Super Metroid")
        self.assertEqual(label.limpar_nome("Tetris [!]"), "Tetris")
        self.assertEqual(label.limpar_nome("Asterix (Europe) (En,Fr,De)"), "Asterix")
        self.assertEqual(label.regiao("Asterix (Europe) (En,Fr,De)"), "Europe")
        self.assertEqual(label.limpar_nome("/roms/snes/Zelda (USA).zip"), "Zelda")

    def test_so_marcas_nao_some(self):
        self.assertEqual(label.limpar_nome("(Beta)"), "(Beta)")

    def test_consoles(self):
        self.assertEqual(label.console_legivel("mega_drive"), "Mega Drive")
        self.assertEqual(label.console_legivel("nintendo_64"), "Nintendo 64")
        self.assertEqual(label.console_legivel("game_boy_color"), "Game Boy Color")
        self.assertEqual(label.console_legivel("algo_novo"), "Algo Novo")

    def test_sem_system_id(self):
        d = label.interpretar("Chrono Trigger (USA)")
        self.assertEqual((d["console"], d["jogo"]), ("", "Chrono Trigger"))
        self.assertEqual(label.interpretar("")["jogo"], "")

    def test_nomes_de_arquivo(self):
        self.assertEqual(label.nome_arquivo('Zelda: A Link "to" the Past?'), "Zelda A Link to the Past")
        self.assertEqual(label.nome_arquivo("Pokémon Edição. "), "Pokémon Edição")
        self.assertEqual(label.nome_arquivo("..."), "Sem nome")
        self.assertEqual(label.nome_ascii("Pokémon: Edição Ouro!"), "Pokemon-Edicao-Ouro")
        self.assertLessEqual(len(label.nome_ascii("x" * 200)), 60)


class TestConfig(unittest.TestCase):
    def test_padroes_e_mescla(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "config.json")
            self.assertEqual(config.carregar(p)["dicas"]["fornecedor"], "")  # nenhuma IA de fábrica
            with open(p, "w") as f:
                json.dump({"dicas": {"modelo": "claude-sonnet-5-5"}, "limite_por_dia": 5}, f)
            cfg = config.carregar(p)
            self.assertEqual(cfg["dicas"]["modelo"], "claude-sonnet-5-5")
            self.assertEqual(cfg["dicas"]["esforco"], "low")  # mantido do padrão
            self.assertEqual(cfg["limite_por_dia"], 5)
            self.assertNotIn("~", cfg["pasta_estado"])
            self.assertNotIn("~", cfg["fornecedores"]["anthropic"]["chave"])
            # o padrão não foi alterado pela mescla
            self.assertEqual(config.PADROES["dicas"]["modelo"], "")

    def test_json_quebrado(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "config.json")
            with open(p, "w") as f:
                f.write('{"limite_por_dia": 5,\n}')
            with self.assertRaises(ValueError):
                config.carregar(p)


class TestUso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dia = "2026-11-05"
        self.u = uso.Uso(self.tmp.name, relogio=lambda: self.dia)

    def tearDown(self):
        self.tmp.cleanup()

    def test_virada_do_dia(self):
        for _ in range(3):
            self.u.contar_dica()
        self.assertEqual(self.u.dicas_hoje(), 3)
        self.assertFalse(self.u.pode_dar_dica(3))
        self.dia = "2026-11-06"
        self.assertEqual(self.u.dicas_hoje(), 0)
        self.assertTrue(self.u.pode_dar_dica(3))

    def test_persistencia(self):
        self.u.contar_dica()
        outro = uso.Uso(self.tmp.name, relogio=lambda: self.dia)
        self.assertEqual(outro.dicas_hoje(), 1)

    def test_limite_de_fichas(self):
        self.u.contar_ficha()
        self.u.contar_ficha()
        self.assertFalse(self.u.pode_fazer_ficha("j", limite_dia=2))
        self.assertTrue(self.u.pode_fazer_ficha("j", limite_dia=3))

    def test_tres_falhas_esperam_o_dia_seguinte(self):
        for _ in range(2):
            self.u.falha_ficha("j")
        self.assertTrue(self.u.pode_fazer_ficha("j", 10))
        self.u.falha_ficha("j")
        self.assertFalse(self.u.pode_fazer_ficha("j", 10))
        self.assertTrue(self.u.pode_fazer_ficha("outro", 10))
        self.dia = "2026-11-06"
        self.assertTrue(self.u.pode_fazer_ficha("j", 10))  # falhas sobrevivem à virada, mas liberam
        self.u.falha_ficha("j")
        self.assertFalse(self.u.pode_fazer_ficha("j", 10))
        self.u.sucesso_ficha("j")
        self.assertTrue(self.u.pode_fazer_ficha("j", 10))

    def test_arquivo_estragado(self):
        with open(os.path.join(self.tmp.name, "uso.json"), "w") as f:
            f.write("{nao e json")
        self.assertEqual(uso.Uso(self.tmp.name, relogio=lambda: self.dia).dicas_hoje(), 0)


class TestDiario(unittest.TestCase):
    def test_so_as_ultimas_5(self):
        with tempfile.TemporaryDirectory() as d:
            di = diario.Diario(d, linhas=5)
            self.assertEqual(di.ler("Super Nintendo", "ActRaiser"), [])
            for i in range(8):
                di.anotar("Super Nintendo", "ActRaiser", f"lugar {i}", f"fala\n{i}")
            linhas = di.ler("Super Nintendo", "ActRaiser")
            self.assertEqual(len(linhas), 5)
            self.assertEqual(linhas[0], ("lugar 3", "fala 3"))
            self.assertEqual(linhas[-1], ("lugar 7", "fala 7"))
            self.assertEqual(di.ler("Game Boy Advance", "ActRaiser"), [])

    def test_onde_vazio_nao_anota(self):
        with tempfile.TemporaryDirectory() as d:
            di = diario.Diario(d)
            di.anotar("C", "J", "  ", "fala")
            self.assertEqual(di.ler("C", "J"), [])


class TestMensagens(unittest.TestCase):
    def test_cada_erro(self):
        codigos = ["sem_internet", "sem_chave", "chave_recusada", "limite_dia", "demorou",
                   "sem_credito", "recusou", "vazio", "ocupado", "estudando_aviso",
                   "estudando_balao", "ainda_estudando", "ficha_falhou"]
        for idioma in ("pt", "en"):
            vistos = set()
            for c in codigos:
                t = mensagens.frase(c, idioma, limite=200, jogo="ActRaiser")
                self.assertTrue(t and "{" not in t, (c, t))
                vistos.add(t)
            self.assertGreaterEqual(len(vistos), len(codigos) - 1)  # recusou == vazio
        self.assertIn("200", mensagens.frase("limite_dia", "pt", limite=200))
        self.assertIn("Wi-Fi", mensagens.frase("sem_internet"))
        self.assertIn("ActRaiser", mensagens.frase("estudando_aviso", jogo="ActRaiser"))

    def test_codigo_desconhecido(self):
        self.assertEqual(mensagens.frase("xyz"), "Deu ruim aqui (xyz).")
        self.assertEqual(mensagens.frase("outro", "en", codigo="E42"), "Something broke here (E42).")
        self.assertEqual(mensagens.frase("sem_internet", "fr"), mensagens.frase("sem_internet", "pt"))

    def test_sem_emoji(self):
        for tabela in mensagens.FRASES.values():
            for t in tabela.values():
                self.assertTrue(all(ord(ch) < 0x2000 for ch in t), t)


class TestPrompts(unittest.TestCase):
    def test_com_e_sem_nome(self):
        com = prompts.sistema_dica("pt", "Lulu")
        sem = prompts.sistema_dica("pt", "")
        self.assertIn("Lulu", com)
        self.assertNotIn("Lulu", sem)
        self.assertIn("Não chame o jogador", sem)
        self.assertIn("português do Brasil", sem)
        en = prompts.sistema_dica("en", "Ana")
        self.assertIn("call Ana", en)
        self.assertIn("in English", en)
        self.assertIn("by any name", prompts.sistema_dica("en"))
        self.assertEqual(prompts.sistema_dica("xx"), sem)

    def test_texto_com_diario(self):
        t = prompts.texto_dica("Super Nintendo", "ActRaiser", "USA",
                               [("Fillmore ato 1", "Pule com B"), ("Bloodpool", "")])
        self.assertIn("Jogo: ActRaiser (versão: USA).", t)
        self.assertIn("- Fillmore ato 1 (dica dada: Pule com B)", t)
        self.assertIn("- Bloodpool\n", t + "\n")
        self.assertEqual(prompts.texto_dica("NES", "Zelda"), "Console: NES. Jogo: Zelda.")
        self.assertIn("Game: Zelda", prompts.texto_dica("NES", "Zelda", idioma="en"))

    def test_ficha(self):
        com = prompts.sistema_ficha("pt", "USA", True)
        self.assertIn("ONDE MAIS SE TRAVA", com)
        self.assertIn("FONTES", com)
        self.assertIn("(USA)", com)
        sem = prompts.sistema_ficha("pt", "", False)
        self.assertNotIn("FONTES", sem)
        self.assertIn("não invente fontes", sem)
        self.assertIn("SOURCES", prompts.sistema_ficha("en"))
        self.assertEqual(prompts.bloco_ficha(""), "")


class TestJogador(unittest.TestCase):
    def _banco(self, d, linhas, tabela=True):
        p = os.path.join(d, "totobox.db")
        con = sqlite3.connect(p)
        if tabela:
            con.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
            con.executemany("INSERT INTO settings VALUES (?, ?)",
                            [(k, json.dumps(v)) for k, v in linhas.items()])
        con.commit()
        con.close()
        return p

    def test_sem_banco(self):
        self.assertEqual(jogador.ler({"idioma": "auto", "banco_meibox": "/nao/existe.db"}), ("pt", ""))

    def test_banco_sem_tabela_ou_chaves(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._banco(d, {}, tabela=False)
            self.assertEqual(jogador.ler({"idioma": "auto", "banco_meibox": p}), ("pt", ""))
        with tempfile.TemporaryDirectory() as d:
            p = self._banco(d, {"since": 1.0})
            self.assertEqual(jogador.ler({"idioma": "auto", "banco_meibox": p}), ("pt", ""))

    def test_le_idioma_e_nome(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._banco(d, {"lang": "en", "player_name": "LULU"})
            self.assertEqual(jogador.ler({"idioma": "auto", "banco_meibox": p}), ("en", "Lulu"))
            self.assertEqual(jogador.ler({"idioma": "pt", "banco_meibox": p}), ("pt", "Lulu"))
            cfg = {"idioma": "auto", "banco_meibox": p, "nome_jogador": "Ana Luiza"}
            self.assertEqual(jogador.ler(cfg), ("en", "Ana Luiza"))

    def test_idioma_invalido(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._banco(d, {"lang": "fr"})
            self.assertEqual(jogador.ler({"idioma": "auto", "banco_meibox": p}), ("pt", ""))


if __name__ == "__main__":
    unittest.main()
