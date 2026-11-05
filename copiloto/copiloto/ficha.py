"""Ficha do jogo (design 12.1): pesquisada na primeira dica, salva como texto editável.

Caminho: <pasta_guias>/<Console>/<Jogo>.txt. Nunca sobrescreve: para refazer, o usuário apaga.
"""
import os
import time

from . import label, prompts

MAX_LETRAS_LIDAS = 16000   # protege o pedido se o usuário escrever muito na ficha

_CABECALHO = {
    "pt": {
        "versao": "versão",
        "com": "Ficha da Mei, feita em {data} com {modelo}, com pesquisa na web ({buscas} {plural}).",
        "sem": "FEITA SEM PESQUISA: a Mei escreveu com o que o modelo {modelo} já sabia, em {data}. "
               "Pode ter erros.",
        "editar": "Pode corrigir e acrescentar à vontade: a Mei lê este arquivo em toda dica. "
                  "Para refazer, apague o arquivo.",
        "fontes": "FONTES",
    },
    "en": {
        "versao": "version",
        "com": "Mei's guide, written on {data} with {modelo}, using web search ({buscas} {plural}).",
        "sem": "WRITTEN WITHOUT RESEARCH: Mei wrote it from what {modelo} already knew, on {data}. "
               "It may contain mistakes.",
        "editar": "Feel free to fix and add things: Mei reads this file on every tip. "
                  "To redo it, delete the file.",
        "fontes": "SOURCES",
    },
}


def chave_jogo(console, jogo):
    return f"{console}|{jogo}"


class Fichas:
    def __init__(self, pasta_guias):
        self.pasta = pasta_guias

    def caminho(self, console, jogo):
        return os.path.join(self.pasta, label.nome_arquivo(console or "Outros"),
                            label.nome_arquivo(jogo) + ".txt")

    def ler(self, console, jogo):
        try:
            with open(self.caminho(console, jogo), encoding="utf-8-sig", errors="replace") as f:
                return f.read(MAX_LETRAS_LIDAS).strip()
        except OSError:
            return ""

    def salvar(self, console, jogo, texto):
        """Grava só se não existir. Devolve o caminho, ou None se já havia uma ficha."""
        caminho = self.caminho(console, jogo)
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        try:
            with open(caminho, "x", encoding="utf-8") as f:
                f.write(texto.rstrip() + "\n")
        except FileExistsError:
            return None
        return caminho


def montar(resposta, console, jogo, regiao, idioma, modelo, quando=None):
    """Cabeçalho + texto da IA (+ fontes citadas, se o texto não trouxer a seção)."""
    c = _CABECALHO[prompts.idioma_ok(idioma)]
    data = time.strftime("%d/%m/%Y" if idioma != "en" else "%Y-%m-%d", time.localtime(quando))
    titulo = f"{jogo} ({console}" + (f", {c['versao']} {regiao})" if regiao else ")")
    if resposta.com_pesquisa:
        n = resposta.buscas
        plural = ("busca" if n == 1 else "buscas") if idioma != "en" else ("search" if n == 1 else "searches")
        origem = c["com"].format(data=data, modelo=modelo, buscas=n, plural=plural)
    else:
        origem = c["sem"].format(data=data, modelo=modelo)
    corpo = resposta.texto.strip()
    if resposta.fontes and "http" not in corpo:
        corpo += f"\n\n{c['fontes']}\n" + "\n".join(f"- {u}" for u in resposta.fontes)
    return f"{titulo}\n{origem}\n{c['editar']}\n\n{corpo}\n"


def gerar(conector, cfg_ficha, console, jogo, regiao, idioma, tempo_max):
    """Pede a ficha ao conector. Busca web só se a config pedir e o conector tiver."""
    busca = bool(cfg_ficha.get("busca_web", True)) and conector.tem_busca_web
    return conector.ficha(
        modelo=cfg_ficha["modelo"], esforco=cfg_ficha.get("esforco"),
        sistema=prompts.sistema_ficha(idioma, regiao, busca),
        pedido=prompts.pedido_ficha(console, jogo, regiao, idioma),
        busca_web=busca, max_buscas=int(cfg_ficha.get("max_buscas", 8)), tempo_max=tempo_max,
    )
