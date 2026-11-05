"""Passos 4 e 6: ficha (nunca sobrescreve, nomes, limites) e o fluxo do serviço com peças falsas."""
import base64
import copy
import os
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from copiloto import config, ficha, main  # noqa: E402
from copiloto.aviso import Aviso  # noqa: E402
from copiloto.conectores import base  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\nfalso"


class DesenhoFalso:
    def __init__(self):
        self.baloes = []

    def balao_png(self, texto, rodape=""):
        self.baloes.append(texto)
        return b"PNG:" + texto.encode()

    def ampliar_png(self, dados, fator):
        return dados

    def imagem_dica(self, tela, texto, rodape=""):
        return b"DICA"

    def imprimivel(self, texto):
        return "".join(ch for ch in texto if ord(ch) < 0x2000).strip()

    def cabe(self, texto):
        return len(texto) <= 220


class ConectorFalso:
    tem_busca_web = True

    def __init__(self, chave=True):
        self.chave = chave
        self.dicas, self.fichas = [], []
        self.erro_dica = None
        self.erro_ficha = None
        self.evento = None

    def carregar(self):
        pass

    def chave_existe(self):
        return self.chave

    def dica(self, **kw):
        self.dicas.append(kw)
        if self.evento:
            self.evento.wait(5)
        if self.erro_dica:
            raise self.erro_dica
        return base.RespostaDica(fala="Pule com B. 😺", onde=f"lugar {len(self.dicas)}")

    def ficha(self, **kw):
        self.fichas.append(kw)
        if self.erro_ficha:
            raise self.erro_ficha
        return base.RespostaFicha(texto="RESUMO\nUm jogo.\n" + "x" * 300, com_pesquisa=True, buscas=4,
                                  fontes=["https://ex.example/a"])


class TestFichas(unittest.TestCase):
    def test_nunca_sobrescreve(self):
        with tempfile.TemporaryDirectory() as d:
            f = ficha.Fichas(d)
            self.assertEqual(f.ler("Super Nintendo", "ActRaiser"), "")
            p = f.salvar("Super Nintendo", "ActRaiser", "primeira")
            self.assertTrue(p.endswith(os.path.join("Super Nintendo", "ActRaiser.txt")))
            self.assertIsNone(f.salvar("Super Nintendo", "ActRaiser", "segunda"))
            self.assertEqual(f.ler("Super Nintendo", "ActRaiser"), "primeira")

    def test_nome_seguro(self):
        with tempfile.TemporaryDirectory() as d:
            f = ficha.Fichas(d)
            p = f.caminho("Game Boy Advance", 'Pokémon: "Fire" Red?')
            self.assertEqual(os.path.basename(p), "Pokémon Fire Red.txt")
            self.assertEqual(os.path.basename(os.path.dirname(f.caminho("", "X"))), "Outros")

    def test_bom_e_tamanho(self):
        with tempfile.TemporaryDirectory() as d:
            f = ficha.Fichas(d)
            p = f.caminho("NES", "Zelda")
            os.makedirs(os.path.dirname(p))
            with open(p, "w", encoding="utf-8-sig") as fh:
                fh.write("a" * 50000)
            self.assertEqual(len(f.ler("NES", "Zelda")), ficha.MAX_LETRAS_LIDAS)

    def test_montar(self):
        r = base.RespostaFicha(texto="RESUMO\nx", com_pesquisa=True, buscas=5, fontes=["https://a.example"])
        t = ficha.montar(r, "Super Nintendo", "ActRaiser", "USA", "pt", "claude-sonnet-5-5", 0)
        self.assertTrue(t.startswith("ActRaiser (Super Nintendo, versão USA)\n"))
        self.assertIn("com pesquisa na web (5 buscas)", t)
        self.assertIn("- https://a.example", t)
        r2 = base.RespostaFicha(texto="RESUMO\nx", com_pesquisa=False)
        self.assertIn("FEITA SEM PESQUISA", ficha.montar(r2, "NES", "Zelda", "", "pt", "m", 0))
        self.assertIn("WITHOUT RESEARCH", ficha.montar(r2, "NES", "Zelda", "", "en", "m", 0))


class TestServico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.cfg = copy.deepcopy(config.PADROES)
        self.cfg.update(pasta_estado=os.path.join(d, "estado"), pasta_guias=os.path.join(d, "guias"),
                        pasta_dicas=os.path.join(d, "dicas"), banco_meibox=os.path.join(d, "nao.db"),
                        aviso=False)
        self.cfg["dicas"].update(fornecedor="falso", modelo="m")
        self.cfg["ficha"].update(fornecedor="falso", modelo="m")
        self.des = DesenhoFalso()
        self.con = ConectorFalso()
        self.logs = []

    def tearDown(self):
        self.tmp.cleanup()

    def _cop(self, **muda):
        self.cfg.update(muda)
        return main.Copiloto(self.cfg, desenho=self.des, conectores=(self.con, self.con),
                             log=self.logs.append)

    def _pedido(self, cop, label="super_nes__ActRaiser (USA)"):
        png, depois = cop.atender({"image": base64.b64encode(PNG).decode(), "label": label})
        if depois:
            depois()
        return png.decode()[4:]

    def test_primeira_dica_faz_ficha_e_seguintes_usam(self):
        cop = self._cop(aviso=True, aviso_porta=9)  # porta sem RetroArch: o envio só falha calado
        fala = self._pedido(cop)
        self.assertEqual(fala, "Pule com B.")  # emoji removido
        self.assertEqual(len(self.con.fichas), 1)
        self.assertIn("RESUMO", self.con.dicas[0]["ficha"])
        self.assertTrue(os.path.exists(cop.fichas.caminho("Super Nintendo", "ActRaiser")))
        self._pedido(cop)
        self.assertEqual(len(self.con.fichas), 1)  # não pesquisa de novo
        texto2 = self.con.dicas[1]["texto"]
        self.assertIn("- lugar 1 (dica dada: Pule com B.)", texto2)
        self.assertEqual(cop.uso.dicas_hoje(), 2)
        self.assertEqual(cop.uso.fichas_hoje(), 1)
        self.assertEqual(len(os.listdir(self.cfg["pasta_dicas"])), 2)

    def test_ficha_falhou_dica_sai_mesmo_assim(self):
        self.con.erro_ficha = base.ErroIA("demorou", "x")
        cop = self._cop(aviso=True, aviso_porta=9)
        fala = self._pedido(cop)
        self.assertTrue(fala.startswith("Não consegui pesquisar ActRaiser agora"), fala)
        self.assertEqual(self.con.dicas[0]["ficha"], "")
        self._pedido(cop)
        self._pedido(cop)
        self.assertEqual(len(self.con.fichas), 3)
        self._pedido(cop)
        self.assertEqual(len(self.con.fichas), 3)  # 3 falhas seguidas: espera o dia seguinte

    def test_reserva_sem_aviso(self):
        cop = self._cop(aviso=False)
        fala = self._pedido(cop)
        self.assertIn("Tô estudando ActRaiser", fala)
        for t in threading.enumerate():
            if t is not threading.current_thread() and t.daemon:
                t.join(2)
        self.assertEqual(self._pedido(cop), "Pule com B.")
        self.assertEqual(len(self.con.dicas), 1)

    def test_ocupado(self):
        cop = self._cop()
        cop.fichas.salvar("Super Nintendo", "ActRaiser", "ficha pronta")
        self.con.evento = threading.Event()
        t = threading.Thread(target=self._pedido, args=(cop,))
        t.start()
        while not self.con.dicas:
            pass
        self.assertEqual(self._pedido(cop), "Calma, ainda tô pensando!")
        self.con.evento.set()
        t.join()

    def test_limite_e_chave(self):
        cop = self._cop(limite_por_dia=1)
        cop.fichas.salvar("Super Nintendo", "ActRaiser", "ficha pronta")
        self._pedido(cop)
        self.assertEqual(self._pedido(cop), "Já dei 1 dicas hoje! Amanhã tem mais.")
        self.con.chave = False
        cop2 = self._cop(limite_por_dia=10)
        self.assertIn("Falta a chave", self._pedido(cop2))

    def test_erro_da_ia_nao_conta(self):
        cop = self._cop()
        cop.fichas.salvar("Super Nintendo", "ActRaiser", "ficha pronta")
        self.con.erro_dica = base.ErroIA("sem_internet")
        self.assertEqual(self._pedido(cop), "Tô sem internet. Confere o Wi-Fi.")
        self.assertEqual(cop.uso.dicas_hoje(), 0)
        self.assertFalse(os.path.exists(self.cfg["pasta_dicas"]))
        self.con.erro_dica = RuntimeError("bug")
        self.assertEqual(self._pedido(cop), "Deu ruim aqui (RuntimeError).")

    def test_sem_ia_configurada(self):
        self.cfg["dicas"].update(fornecedor="", modelo="")
        cop = self._cop()
        self.assertIn("ainda não foi configurada", self._pedido(cop))
        self.assertEqual(self.con.dicas, [])

    def test_sem_imagem(self):
        cop = self._cop()
        png, _ = cop.atender({"label": "x__y"})
        self.assertIn(b"Tenta em outro momento", png)


class TestAviso(unittest.TestCase):
    def test_uma_mensagem_por_vez(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        s.settimeout(2)
        a = Aviso(s.getsockname()[1], intervalo=0.2)
        a.iniciar("Mei está estudando ActRaiser...")
        recebidas = [s.recvfrom(1024)[0] for _ in range(3)]
        a.parar()
        s.close()
        self.assertEqual(recebidas[0], "SHOW_MSG Mei está estudando ActRaiser...".encode())
        self.assertGreaterEqual(a.enviadas, 3)


if __name__ == "__main__":
    unittest.main()
