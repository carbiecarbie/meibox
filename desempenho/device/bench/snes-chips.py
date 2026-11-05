#!/usr/bin/env python3
"""Lê o cabeçalho interno dos ROMs de SNES (soltos ou dentro de .zip) e diz
qual chip extra o cartucho usa. Saída: JSON por linha.
Uso: snes-chips.py /roms/snes [/roms/sfc ...]"""
import json, os, sys, zipfile

EXT = ('.sfc', '.smc', '.swc', '.fig', '.bin')
CHIP = {0x0: 'DSP', 0x1: 'SuperFX', 0x2: 'OBC1', 0x3: 'SA-1', 0x4: 'S-DD1',
        0x5: 'S-RTC', 0xE: 'outro', 0xF: 'custom'}
CUSTOM = {0x00: 'SPC7110', 0x01: 'ST010/011', 0x02: 'ST018', 0x10: 'CX4'}


def score(rom, base):
    if base + 0x40 > len(rom):
        return -1, None
    h = rom[base:base + 0x40]
    chk = h[0x1E] | h[0x1F] << 8
    cmp_ = h[0x1C] | h[0x1D] << 8
    s = 0
    if (chk ^ cmp_) == 0xFFFF:
        s += 4
    mode = h[0x15]
    if (base in (0x7FC0,) and mode & 0x01 == 0) or (base in (0xFFC0, 0x40FFC0) and mode & 0x01):
        s += 2
    if all(32 <= c < 127 for c in h[:21]):
        s += 1
    return s, h


def chip(rom):
    if len(rom) % 1024 == 512:
        rom = rom[512:]
    best = max((score(rom, b) + (b,) for b in (0x7FC0, 0xFFC0, 0x40FFC0)), key=lambda t: t[0])
    s, h, base = best
    if h is None:
        return None
    t = h[0x16]
    title = h[:21].decode('ascii', 'replace').strip()
    if t & 0x0F < 3:
        return {'title': title, 'chip': None, 'type': t}
    name = CHIP.get(t >> 4, f'?{t:02x}')
    if name == 'custom' and base >= 0x10:
        name = CUSTOM.get(rom[base - 1], f'custom{rom[base - 1]:02x}')
    return {'title': title, 'chip': name, 'type': t}


def roms(d):
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        lf = f.lower()
        try:
            if lf.endswith('.zip'):
                with zipfile.ZipFile(p) as z:
                    for n in z.namelist():
                        if n.lower().endswith(EXT):
                            yield f, z.read(n)
                            break
            elif lf.endswith(EXT):
                with open(p, 'rb') as fh:
                    yield f, fh.read()
        except Exception as e:  # zip quebrado, 7z etc.
            print(json.dumps({'file': f, 'erro': str(e)}, ensure_ascii=False))


for d in sys.argv[1:]:
    if not os.path.isdir(d):
        continue
    for f, data in roms(d):
        r = chip(data) or {'erro': 'sem cabeçalho'}
        r.update(file=f, dir=d)
        print(json.dumps(r, ensure_ascii=False))
