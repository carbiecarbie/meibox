# Define emulador/core por jogo no gamelist.xml do ES (campos EMULATOR/CORE dos metadados).
# Uso: python3 set-game-core.py <gamelist.xml> <arquivo da rom> <emulador> <core>
# Com o ES parado: ele reescreve o gamelist ao sair. Faz backup .bak-r36s-perf uma vez.
import re, sys, shutil, os
gl, rom, emu, core = sys.argv[1:5]
bak = gl + ".bak-r36s-perf"
if not os.path.exists(bak):
    shutil.copy2(gl, bak)
t = open(gl, encoding="utf-8").read()
pat = re.compile(r"(<game>(?:(?!</game>).)*?<path>\./" + re.escape(rom) + r"</path>.*?)(</game>)", re.S)
m = pat.search(t)
if not m:
    # Jogo sem entrada: cria uma mínima.
    t = t.replace("</gameList>", f"\t<game>\n\t\t<path>./{rom}</path>\n\t</game>\n</gameList>")
    m = pat.search(t)
body = re.sub(r"\s*<(emulator|core)>.*?</\1>", "", m.group(1))
body = body.rstrip() + f"\n\t\t<emulator>{emu}</emulator>\n\t\t<core>{core}</core>\n\t"
t = t[:m.start()] + body + m.group(2) + t[m.end():]
open(gl, "w", encoding="utf-8").write(t)
print("ok", rom, emu, core)
