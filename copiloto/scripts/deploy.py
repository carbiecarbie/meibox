#!/usr/bin/env python3
"""Copia o copiloto para o aparelho (padrão: /tmp/copiloto-dev, a pasta de testes).

Uso: python scripts/deploy.py [destino]
Copia copiloto/, assets/, device/ e mei_copiloto.py. Não toca em nada fora do destino.
Depois, no aparelho: bash <destino>/device/install.sh
"""
import io
import os
import subprocess
import sys
import tarfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Aparelho e chave SSH vêm do ambiente: R36S_HOST=ark@<ip>, R36S_SSH_KEY e R36S_KNOWN_HOSTS opcionais.
HOST = os.environ.get("R36S_HOST", "")
SSH = (["ssh"] + (["-i", os.environ["R36S_SSH_KEY"]] if os.environ.get("R36S_SSH_KEY") else [])
       + (["-o", "UserKnownHostsFile=" + os.environ["R36S_KNOWN_HOSTS"]] if os.environ.get("R36S_KNOWN_HOSTS") else [])
       + ["-o", "BatchMode=yes", HOST])
ITENS = ["copiloto", "assets", "device", "mei_copiloto.py"] + [
    p for p in ("spike/run-game.sh", "spike/test.cfg", "spike/test-notify.cfg")  # só no projeto de desenvolvimento
    if os.path.exists(os.path.join(RAIZ, p))]


def main():
    if not HOST:
        sys.exit("defina R36S_HOST, por exemplo: R36S_HOST=ark@192.168.0.50 python scripts/deploy.py")
    destino = sys.argv[1] if len(sys.argv) > 1 else "/tmp/copiloto-dev"
    if not destino.startswith("/tmp/"):
        sys.exit(f"destino recusado: {destino}")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for item in ITENS:
            caminho = os.path.join(RAIZ, item)
            if os.path.exists(caminho):
                nome = os.path.basename(item) if item.startswith("spike/") else item
                tar.add(caminho, arcname=nome,
                        filter=lambda t: None if "__pycache__" in t.name else t)
    cmd = f"mkdir -p '{destino}' && tar -xzf - -C '{destino}' && chmod +x '{destino}/run-game.sh'"
    subprocess.run(SSH + [cmd], input=buf.getvalue(), check=True)
    print(f"copiado para {HOST}:{destino} ({len(buf.getvalue()) // 1024} KB)")


if __name__ == "__main__":
    main()
