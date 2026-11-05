"""Aviso na tela do RetroArch durante a pesquisa (comando de rede SHOW_MSG por UDP).

O RetroArch mostra cada SHOW_MSG por 180 quadros (~3 s) e empilha mensagens que chegam antes
da anterior sumir (visto em 9.3). Por isso manda uma por vez e renova a cada ~3,3 s.
Precisa de `network_cmd_enable = "true"` no RetroArch.
"""
import socket
import threading


class Aviso:
    def __init__(self, porta=55355, intervalo=3.3, host="127.0.0.1"):
        self.destino = (host, porta)
        self.intervalo = intervalo
        self._parar = threading.Event()
        self._thread = None
        self.enviadas = 0

    def enviar(self, texto):
        texto = " ".join((texto or "").split())
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(b"SHOW_MSG " + texto.encode("utf-8"), self.destino)
        self.enviadas += 1

    def _laco(self, texto):
        while not self._parar.is_set():
            try:
                self.enviar(texto)
            except OSError:
                pass  # RetroArch fechado ou sem comandos de rede: o aviso só não aparece
            self._parar.wait(self.intervalo)

    def iniciar(self, texto):
        self.parar()
        self._parar.clear()
        self.enviadas = 0
        self._thread = threading.Thread(target=self._laco, args=(texto,), daemon=True)
        self._thread.start()

    def parar(self):
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
