import contextlib
import io
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
INSTALADOR = os.path.join(os.path.dirname(AQUI), "cartao", "totobox", "instalador")
sys.path.insert(0, INSTALADOR)
import chave  # noqa: E402

MODELO = os.path.join(os.path.dirname(INSTALADOR), "chave-da-ia.txt")
OPENAI = "sk-proj-" + "a1B2c3D4e5" * 4
ANTHROPIC = "sk-ant-api03-" + "Z9y8X7w6V5" * 4
CONFIG_PADRAO = {
    "dicas": {"fornecedor": "", "modelo": "", "esforco": "low"},
    "ficha": {"fornecedor": "", "modelo": "", "esforco": "medium", "busca_web": True},
    "idioma": "auto",
}


def rodar(*args):
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(io.StringIO()):
        rc = chave.main(list(args))
    return rc, saida.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.arq = os.path.join(self.tmp, "chave-da-ia.txt")
        shutil.copy(MODELO, self.arq)
        self.conf = os.path.join(self.tmp, "conf")
        os.makedirs(self.conf)
        self.escrever_config(CONFIG_PADRAO)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def escrever_config(self, dados):
        with open(os.path.join(self.conf, "config.json"), "w", encoding="utf-8") as f:
            json.dump(dados, f)

    def config(self):
        with open(os.path.join(self.conf, "config.json"), encoding="utf-8") as f:
            return json.load(f)

    def colar(self, texto, bom=False, crlf=False):
        with open(MODELO, encoding="utf-8") as f:
            corpo = f.read() + texto + "\n"
        if crlf:
            corpo = corpo.replace("\n", "\r\n")
        with open(self.arq, "wb") as f:
            f.write((b"\xef\xbb\xbf" if bom else b"") + corpo.encode("utf-8"))


class Ler(Base):
    def test_modelo_sem_chave(self):
        self.assertEqual(rodar("ler", self.arq), (1, ""))

    def test_arquivo_ausente(self):
        self.assertEqual(rodar("ler", os.path.join(self.tmp, "nada.txt"))[0], 1)

    def test_openai_e_anthropic(self):
        self.colar(OPENAI)
        self.assertEqual(rodar("ler", self.arq), (0, "openai\n"))
        self.colar(ANTHROPIC)
        self.assertEqual(rodar("ler", self.arq), (0, "anthropic\n"))

    def test_bloco_de_notas_do_windows(self):
        self.colar('  "' + OPENAI + '"  ', bom=True, crlf=True)
        self.assertEqual(rodar("ler", self.arq), (0, "openai\n"))

    def test_texto_que_nao_e_chave(self):
        self.colar("minha chave é esta aqui")
        self.assertEqual(rodar("ler", self.arq), (2, ""))
        self.colar("sk-curta")
        self.assertEqual(rodar("ler", self.arq)[0], 2)

    def test_nunca_imprime_a_chave(self):
        self.colar(OPENAI)
        self.assertNotIn(OPENAI, rodar("ler", self.arq)[1])


class Guardar(Base):
    def test_guarda_privado_e_limpa_o_cartao(self):
        self.colar(OPENAI)
        rc, saida = rodar("guardar", self.arq, self.conf, MODELO)
        self.assertEqual((rc, saida), (0, "openai\n"))
        guardada = os.path.join(self.conf, "chaves", "openai")
        with open(guardada) as f:
            self.assertEqual(f.read(), OPENAI)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(os.stat(guardada).st_mode), 0o600)
        with open(self.arq, "rb") as a, open(MODELO, "rb") as b:
            self.assertEqual(a.read(), b.read())
        self.assertEqual(rodar("ler", self.arq)[0], 1)

    def test_escolhe_o_modelo_e_mantem_o_resto(self):
        self.colar(OPENAI)
        rodar("guardar", self.arq, self.conf, MODELO)
        c = self.config()
        self.assertEqual(c["dicas"], {"fornecedor": "openai_compat", "modelo": "gpt-6.1-terra", "esforco": "low"})
        self.assertEqual(c["ficha"]["modelo"], "gpt-6.1-terra")
        self.assertTrue(c["ficha"]["busca_web"])
        self.assertEqual(c["idioma"], "auto")

    def test_anthropic(self):
        self.colar(ANTHROPIC)
        rodar("guardar", self.arq, self.conf, MODELO)
        c = self.config()
        self.assertEqual((c["dicas"]["fornecedor"], c["dicas"]["modelo"]), ("anthropic", "claude-haiku-5-5"))
        self.assertEqual(c["ficha"]["modelo"], "claude-sonnet-5-5")
        self.assertTrue(os.path.exists(os.path.join(self.conf, "chaves", "anthropic")))

    def test_mantem_o_modelo_que_a_pessoa_escolheu(self):
        self.escrever_config({"dicas": {"fornecedor": "openai_compat", "modelo": "outro-modelo"},
                              "ficha": {"fornecedor": "", "modelo": ""}})
        self.colar(OPENAI)
        rodar("guardar", self.arq, self.conf, MODELO)
        self.assertEqual(self.config()["dicas"]["modelo"], "outro-modelo")

    def test_chave_nova_de_outro_fornecedor_troca(self):
        self.escrever_config({"dicas": {"fornecedor": "anthropic", "modelo": "claude-haiku-5-5"},
                              "ficha": {"fornecedor": "anthropic", "modelo": "claude-sonnet-5-5"}})
        self.colar(OPENAI)
        rodar("guardar", self.arq, self.conf, MODELO)
        self.assertEqual(self.config()["dicas"]["fornecedor"], "openai_compat")

    def test_sem_chave_nao_mexe_em_nada(self):
        antes = self.config()
        self.assertEqual(rodar("guardar", self.arq, self.conf, MODELO)[0], 1)
        self.assertEqual(self.config(), antes)
        self.assertFalse(os.path.exists(os.path.join(self.conf, "chaves")))

    def test_chave_invalida_fica_no_cartao(self):
        self.colar("isto não é chave")
        self.assertEqual(rodar("guardar", self.arq, self.conf, MODELO)[0], 2)
        with open(self.arq, encoding="utf-8") as f:
            self.assertIn("isto não é chave", f.read())


class AjustarApagar(Base):
    def guardar_direto(self, nome, texto):
        os.makedirs(os.path.join(self.conf, "chaves"), exist_ok=True)
        with open(os.path.join(self.conf, "chaves", nome), "w") as f:
            f.write(texto)

    def test_ajustar_com_chave_posta_pelo_ssh(self):
        self.guardar_direto("anthropic", ANTHROPIC)
        self.assertEqual(rodar("ajustar", self.conf), (0, "anthropic\n"))
        self.assertEqual(self.config()["dicas"]["fornecedor"], "anthropic")

    def test_ajustar_nao_troca_o_que_ja_foi_escolhido(self):
        self.escrever_config({"dicas": {"fornecedor": "anthropic", "modelo": "x"},
                              "ficha": {"fornecedor": "anthropic", "modelo": "y"}})
        self.guardar_direto("openai", OPENAI)
        rodar("ajustar", self.conf)
        self.assertEqual(self.config()["dicas"], {"fornecedor": "anthropic", "modelo": "x"})

    def test_ajustar_sem_chave(self):
        self.assertEqual(rodar("ajustar", self.conf)[0], 1)

    def test_apagar(self):
        self.guardar_direto("openai", OPENAI)
        self.guardar_direto("anthropic", ANTHROPIC)
        self.assertEqual(rodar("apagar", self.conf)[0], 0)
        self.assertEqual(os.listdir(os.path.join(self.conf, "chaves")), [])
        self.assertEqual(rodar("apagar", self.conf)[0], 0)  # de novo, sem erro


class Idioma(Base):
    def lingua(self, db):
        con = sqlite3.connect(db)
        try:
            return json.loads(con.execute("SELECT value FROM settings WHERE key='lang'").fetchone()[0])
        finally:
            con.close()

    def test_poe_so_na_primeira_vez(self):
        db = os.path.join(self.tmp, "data", "totobox.db")
        self.assertEqual(rodar("idioma", db, "en")[0], 0)
        self.assertEqual(self.lingua(db), "en")
        rodar("idioma", db, "pt")
        self.assertEqual(self.lingua(db), "en")  # a escolha feita no Meibox vale

    def test_lingua_desconhecida(self):
        self.assertEqual(rodar("idioma", os.path.join(self.tmp, "x.db"), "fr")[0], 2)


if __name__ == "__main__":
    unittest.main()
