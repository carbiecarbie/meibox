"""Short interface sounds, synthesized once into the cache (no third-party audio files).

Played through SDL2_mixer; closed before a game starts so the emulator gets the device.
Any audio failure just means silence.
"""
import ctypes as C
import math
import os
import random
import struct
import wave

from . import sdl as S

RATE = 22050


def _env(i, n, attack=0.01, release=0.6):
    p = i / n
    a = min(1.0, p / attack) if attack else 1.0
    return a * (1 - p) ** (1 / max(release, 1e-3))


def synth(name):
    """Samples (floats -1..1) for each sound."""
    out = []
    if name == "move":       # soft click
        n = int(RATE * 0.025)
        out = [math.sin(2 * math.pi * 1900 * i / RATE) * _env(i, n, 0.05, 0.3) * 0.35 for i in range(n)]
    elif name == "back":     # low blip
        n = int(RATE * 0.07)
        out = [math.sin(2 * math.pi * (420 - 120 * i / n) * i / RATE) * _env(i, n, 0.05, 0.5) * 0.4
               for i in range(n)]
    elif name == "tick":     # roulette tick
        n = int(RATE * 0.018)
        rng = random.Random(7)
        out = [(rng.random() * 2 - 1) * 0.25 * _env(i, n, 0.0, 0.25) + math.sin(2 * math.pi * 1300 * i / RATE)
               * 0.25 * _env(i, n, 0.0, 0.3) for i in range(n)]
    elif name == "ding":     # bell when the roulette lands / a Ficha is saved
        n = int(RATE * 0.6)
        out = [(math.sin(2 * math.pi * 880 * i / RATE) * 0.5 + math.sin(2 * math.pi * 1320 * i / RATE) * 0.3)
               * _env(i, n, 0.005, 1.6) * 0.5 for i in range(n)]
    elif name == "meow":     # "miau": rising then falling pitch with a little vibrato
        n = int(RATE * 0.42)
        phase = 0.0
        for i in range(n):
            p = i / n
            f = 520 + 420 * math.sin(math.pi * min(1, p * 1.25)) + 18 * math.sin(2 * math.pi * 7 * p)
            phase += 2 * math.pi * f / RATE
            s = math.sin(phase) * 0.55 + math.sin(2 * phase) * 0.25 + math.sin(3 * phase) * 0.12
            out.append(s * _env(i, n, 0.12, 0.9) * 0.45)
    return out


def write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))


class Sounds:
    NAMES = ("move", "back", "tick", "ding", "meow")

    def __init__(self, cache_dir):
        self.dir = os.path.join(cache_dir, "sounds")
        self.chunks = {}
        self.ok = False
        self.mix = None

    def open(self):
        try:
            os.makedirs(self.dir, exist_ok=True)
            mix = S.mix
            mix.Mix_OpenAudio.argtypes = [C.c_int, C.c_uint16, C.c_int, C.c_int]
            mix.Mix_LoadWAV_RW.restype = C.c_void_p
            mix.Mix_LoadWAV_RW.argtypes = [C.c_void_p, C.c_int]
            mix.Mix_PlayChannelTimed.argtypes = [C.c_int, C.c_void_p, C.c_int, C.c_int]
            mix.Mix_FreeChunk.argtypes = [C.c_void_p]
            mix.Mix_Volume.argtypes = [C.c_int, C.c_int]
            if S.sdl.SDL_InitSubSystem(S.INIT_AUDIO) != 0:
                return
            if mix.Mix_OpenAudio(RATE, 0x8010, 1, 512) != 0:
                S.sdl.SDL_QuitSubSystem(S.INIT_AUDIO)
                return
            mix.Mix_Volume(-1, 80)
            for name in self.NAMES:
                path = os.path.join(self.dir, name + ".wav")
                if not os.path.exists(path):
                    write_wav(path, synth(name))
                chunk = mix.Mix_LoadWAV_RW(S.sdl.SDL_RWFromFile(path.encode(), b"rb"), 1)
                if chunk:
                    self.chunks[name] = chunk
            self.mix, self.ok = mix, True
        except (OSError, AttributeError):
            self.ok = False

    def play(self, name):
        if self.ok and name in self.chunks:
            self.mix.Mix_PlayChannelTimed(-1, self.chunks[name], 0, -1)

    def close(self):
        if not self.ok:
            return
        for c in self.chunks.values():
            self.mix.Mix_FreeChunk(c)
        self.chunks.clear()
        self.mix.Mix_CloseAudio()
        S.sdl.SDL_QuitSubSystem(S.INIT_AUDIO)
        self.ok = False
