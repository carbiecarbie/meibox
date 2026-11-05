"""Passo 2: corte do texto do balão (sem SDL: largura falsa de 10 px por letra)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from copiloto.desenho import cortar_linhas, quebrar  # noqa: E402


def larg(t):
    return 10 * len(t)


class TestCorte(unittest.TestCase):
    def test_curto(self):
        self.assertEqual(cortar_linhas("Pule com B.", larg, 200), ["Pule com B."])

    def test_quebra(self):
        self.assertEqual(quebrar("aaa bbb ccc", larg, 70), ["aaa bbb", "ccc"])

    def test_corta_na_ultima_frase_inteira(self):
        texto = "Frase um aqui. Frase dois aqui. Frase três que não cabe de jeito nenhum aqui."
        linhas = cortar_linhas(texto, larg, 150, max_linhas=3)
        self.assertEqual(" ".join(linhas), "Frase um aqui. Frase dois aqui.")

    def test_sem_frase_que_caiba_usa_reticencias(self):
        texto = " ".join(["palavra"] * 40)
        linhas = cortar_linhas(texto, larg, 150, max_linhas=2)
        self.assertEqual(len(linhas), 2)
        self.assertTrue(linhas[-1].endswith("…"))
        self.assertLessEqual(larg(linhas[-1]), 150)

    def test_vazio(self):
        self.assertEqual(cortar_linhas("   ", larg, 100), [])


if __name__ == "__main__":
    unittest.main()
