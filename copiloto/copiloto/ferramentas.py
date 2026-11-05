"""Comandos de teste no aparelho (sem RetroArch).

  balao SAIDA.png TEXTO...           desenha um balão e mede o tempo
  dica FOTO.png LABEL [SAIDA.png]    pede uma dica de verdade (com ficha e diário, se houver)
  ficha LABEL                        gera a ficha do jogo (nunca sobrescreve)
  aviso TEXTO [SEGUNDOS]             manda SHOW_MSG ao RetroArch durante SEGUNDOS
"""
import os
import sys
import time

from . import config


def _desenho(cfg):
    from .desenho import Desenho
    return Desenho(cfg["pasta_assets"])


def cmd_balao(cfg, args):
    saida, texto = args[0], " ".join(args[1:])
    t0 = time.time()
    d = _desenho(cfg)
    t1 = time.time()
    png = d.balao_png(texto, rodape="SELECT + R1 para voltar ao jogo")
    t2 = time.time()
    with open(saida, "wb") as f:
        f.write(png)
    print(f"carregar={t1 - t0:.3f}s desenhar={t2 - t1:.3f}s linhas={d.linhas(texto)} -> {saida}")


def principal(args):
    cfg = config.carregar()
    if not os.path.isdir(cfg["pasta_assets"]):
        cfg["pasta_assets"] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    comandos = {"balao": cmd_balao}
    try:
        from . import main  # comandos que usam o serviço completo
        comandos.update({"dica": main.cmd_dica, "ficha": main.cmd_ficha, "aviso": main.cmd_aviso})
    except ImportError:
        pass
    if not args or args[0] not in comandos:
        print(__doc__)
        sys.exit(2)
    comandos[args[0]](cfg, args[1:])
