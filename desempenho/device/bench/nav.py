#!/usr/bin/env python3
"""Leva um jogo até a cena de teste apertando botões, e salva um savestate.

Roda o RetroArch em tempo real (vsync ligado) com os comandos de rede e o
gamepad por rede ligados. Os botões vão por UDP para a porta do gamepad
remoto; SAVE_STATE e QUIT vão pela porta de comandos.

Uso: nav.py <emu> <core> <rom> <roteiro>
roteiro: "t:BOTAO[:dur] t:BOTAO ..." com t em segundos desde o início,
         ou "t:SAVE" / "t:SHOT" (screenshot) / "t:QUIT".
"""
import os
import socket
import struct
import subprocess
import sys
import time

BASE = "/home/ark/.local/share/r36s-perf/bench"
IDS = {"B": 0, "Y": 1, "SELECT": 2, "START": 3, "UP": 4, "DOWN": 5, "LEFT": 6,
       "RIGHT": 7, "A": 8, "X": 9, "L": 10, "R": 11}
CMD_PORT = 55355
PAD_PORT = 55400  # network_remote_base_port + usuário 0


def pad(sock, button, state):
    # struct remote_message { int port; int device; int index; int id; uint16_t state; }
    msg = struct.pack("<iiiiH2x", 0, 1, 0, IDS[button], state)
    sock.sendto(msg, ("127.0.0.1", PAD_PORT))


def cmd(sock, text):
    sock.sendto(text.encode(), ("127.0.0.1", CMD_PORT))


def main():
    emu, core, rom, script = sys.argv[1:5]
    cfg = f"{BASE}/nav.cfg"
    with open(cfg, "w") as f:
        f.write('video_vsync = "true"\naudio_sync = "true"\n'
                'network_cmd_enable = "true"\nnetwork_remote_enable = "true"\n'
                'network_remote_enable_user_p1 = "true"\n'
                'savestate_auto_index = "false"\nstate_slot = "0"\n'
                'screenshots_in_content_dir = "false"\n'
                f'screenshot_directory = "{BASE}/tmp"\n')
    so = core if "/" in core else f"/home/ark/.config/{emu}/cores/{core}_libretro.so"
    proc = subprocess.Popen(
        [f"/opt/retroarch/bin/{emu}", "-c", f"/home/ark/.config/{emu}/retroarch.cfg",
         f"--appendconfig={BASE}/bench.cfg|" + (f"{BASE}/bench32.cfg|" if emu == "retroarch32" else "") + cfg, "-v", "-L", so, rom],
        stdout=subprocess.DEVNULL, stderr=open(f"{BASE}/tmp/nav.log", "w"))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    t0 = time.monotonic()
    steps = []
    for tok in script.split():
        parts = tok.split(":")
        steps.append((float(parts[0]), parts[1], float(parts[2]) if len(parts) > 2 else 0.12))
    for t, what, dur in sorted(steps):
        while time.monotonic() - t0 < t:
            if proc.poll() is not None:
                sys.exit(f"RetroArch saiu antes da hora (rc={proc.returncode})")
            time.sleep(0.01)
        if what == "SAVE":
            cmd(sock, "SAVE_STATE")
        elif what == "SHOT":
            cmd(sock, "SCREENSHOT")
        elif what == "QUIT":
            cmd(sock, "QUIT")
        else:
            pad(sock, what, 1)
            time.sleep(dur)
            pad(sock, what, 0)
        print(f"{time.monotonic() - t0:7.2f} {what}", flush=True)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("rc", proc.returncode)


if __name__ == "__main__":
    main()
