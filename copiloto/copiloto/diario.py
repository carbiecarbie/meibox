"""Diário do jogo: as últimas N dicas, com "onde estava" e o que a Mei disse (design 12.2).

Um arquivo de texto por jogo em <pasta_estado>/diario/, uma dica por linha: "onde<TAB>fala".
Guardar a fala junto deixa a IA saber o que já disse e não repetir. Interno, não é para postar.
"""
import os
import re

from . import label


def _linha(texto, limite):
    return re.sub(r"\s+", " ", texto or "").strip()[:limite]


class Diario:
    def __init__(self, pasta_estado, linhas=5):
        self.pasta = os.path.join(pasta_estado, "diario")
        self.linhas = linhas

    def _caminho(self, console, jogo):
        return os.path.join(self.pasta, label.nome_arquivo(f"{console} - {jogo}", 120) + ".txt")

    def ler(self, console, jogo):
        """Lista de (onde, fala), do mais antigo para o mais novo."""
        try:
            with open(self._caminho(console, jogo), encoding="utf-8") as f:
                brutas = [l.rstrip("\n") for l in f if l.strip()]
        except OSError:
            return []
        out = []
        for l in brutas[-self.linhas:]:
            onde, _, fala = l.partition("\t")
            out.append((onde.strip(), fala.strip()))
        return out

    def anotar(self, console, jogo, onde, fala=""):
        onde, fala = _linha(onde, 120), _linha(fala, 300)
        if not onde:
            return
        linhas = [f"{o}\t{f}" for o, f in self.ler(console, jogo)] + [f"{onde}\t{fala}"]
        os.makedirs(self.pasta, exist_ok=True)
        caminho = self._caminho(console, jogo)
        tmp = caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas[-self.linhas:]) + "\n")
        os.replace(tmp, caminho)
