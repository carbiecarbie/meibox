"""Contadores do dia (dicas e fichas) e falhas seguidas de ficha por jogo.

Arquivo: <pasta_estado>/uso.json. O "dia" é a data local do aparelho.
Dica que falha não conta (design 5.6). Ficha conta quando a pesquisa é tentada.
"""
import json
import os
import time


def _hoje():
    return time.strftime("%Y-%m-%d")


class Uso:
    def __init__(self, pasta, relogio=_hoje):
        self.caminho = os.path.join(pasta, "uso.json")
        self.relogio = relogio
        self.dados = self._ler()

    def _ler(self):
        try:
            with open(self.caminho, encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _gravar(self):
        os.makedirs(os.path.dirname(self.caminho), exist_ok=True)
        tmp = self.caminho + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.dados, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.caminho)

    def _dia(self):
        hoje = self.relogio()
        if self.dados.get("dia") != hoje:
            falhas = self.dados.get("falhas_ficha", {})
            self.dados = {"dia": hoje, "dicas": 0, "fichas": 0, "falhas_ficha": falhas}
        return self.dados

    # ---- dicas
    def dicas_hoje(self):
        return self._dia()["dicas"]

    def pode_dar_dica(self, limite):
        return self.dicas_hoje() < limite

    def contar_dica(self):
        self._dia()["dicas"] += 1
        self._gravar()

    # ---- fichas
    def fichas_hoje(self):
        return self._dia()["fichas"]

    def pode_fazer_ficha(self, chave_jogo, limite_dia, max_falhas=3):
        """Falso se o limite de fichas do dia acabou ou se o jogo falhou 3 vezes seguidas hoje."""
        d = self._dia()
        if d["fichas"] >= limite_dia:
            return False
        f = d["falhas_ficha"].get(chave_jogo)
        return not (f and f["seguidas"] >= max_falhas and f["dia"] == d["dia"])

    def contar_ficha(self):
        self._dia()["fichas"] += 1
        self._gravar()

    def falha_ficha(self, chave_jogo):
        d = self._dia()
        f = d["falhas_ficha"].get(chave_jogo, {"seguidas": 0})
        d["falhas_ficha"][chave_jogo] = {"seguidas": f["seguidas"] + 1, "dia": d["dia"]}
        self._gravar()

    def sucesso_ficha(self, chave_jogo):
        d = self._dia()
        if d["falhas_ficha"].pop(chave_jogo, None) is not None:
            self._gravar()
