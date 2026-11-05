#!/usr/bin/env python3
"""Ponto de entrada. Roda com `python3 -I mei_copiloto.py [comando]`.

Sem comando (ou `servir`): o serviço HTTP em 127.0.0.1:4404.
Comandos de teste: `balao`, `dica`, `ficha`, `aviso` (veja `copiloto/ferramentas.py`).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "servir":
        from copiloto import main
        main.principal(args[1:])
    else:
        from copiloto import ferramentas
        ferramentas.principal(args)
