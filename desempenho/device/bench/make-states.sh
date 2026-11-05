#!/bin/bash
# Cria o savestate de benchmark (slot 0) de cada jogo num core, a partir de nav-*.json.
# Uso: make-states.sh <emu> <core> <roteiros.json>
cd /home/ark/.local/share/r36s-perf/bench || exit 1
python3 - "$@" <<'PY'
import json, subprocess, sys, glob, os, shutil
emu, core, jobs = sys.argv[1:4]
os.makedirs("shots", exist_ok=True)
for rom, script in json.load(open(jobs)).items():
    out = subprocess.run(["python3", "nav.py", emu, core, rom, script], capture_output=True, text=True)
    print(os.path.basename(rom), "|", out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr[-200:], flush=True)
    for f in glob.glob("tmp/*.png"):
        shutil.move(f, f"shots/{os.path.basename(core).replace('_libretro.so', '')}-{os.path.basename(f)}")
PY
