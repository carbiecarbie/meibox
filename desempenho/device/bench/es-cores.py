import re, glob, os
f = next(p for p in ["/etc/emulationstation/es_systems.cfg", os.path.expanduser("~/.emulationstation/es_systems.cfg")] if os.path.exists(p))
print(f)
t = open(f).read()
for blk in re.findall(r"<system>.*?</system>", t, re.S):
    name = re.search(r"<name>(.*?)</name>", blk).group(1)
    if name in ("snes", "genesis", "megadrive", "gba"):
        print("==", name)
        print(" cmd", " ".join(re.search(r"<command>(.*?)</command>", blk, re.S).group(1).split())[:300])
        for m in re.finditer(r"<emulator name=\"(.*?)\".*?</emulator>", blk, re.S):
            print(" emu", m.group(1), re.findall(r"<core[^>]*>(.*?)</core>", m.group(0)))
s = open(os.path.expanduser("~/.emulationstation/es_settings.cfg")).read()
for l in s.splitlines():
    if re.search(r"snes|genesis|megadrive|gba", l, re.I):
        print(" set", l.strip())
