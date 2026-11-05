"""Turns SDL game controller events into Totobox actions, with key repeat.

Actions: up down left right a b x y l1 r1 start select.
"""
import ctypes as C
import struct
import time

from . import sdl as S

BUTTONS = {S.BTN_A: "a", S.BTN_B: "b", S.BTN_X: "x", S.BTN_Y: "y", S.BTN_START: "start",
           S.BTN_BACK: "select", S.BTN_LSHOULDER: "l1", S.BTN_RSHOULDER: "r1",
           S.BTN_DPUP: "up", S.BTN_DPDOWN: "down", S.BTN_DPLEFT: "left", S.BTN_DPRIGHT: "right"}
REPEATABLE = {"up", "down", "left", "right", "l1", "r1"}
REPEAT_DELAY, REPEAT_EVERY = 0.30, 0.06
AXIS_ON, AXIS_OFF = 16000, 8000
GAMECONTROLLER_DB = "/opt/inttools/gamecontrollerdb.txt"


class Input:
    def __init__(self):
        self.pads = []
        self.held = None          # (action, next_fire_time)
        self.axis_dir = {S.AXIS_LEFTX: None, S.AXIS_LEFTY: None}
        self.ev = C.create_string_buffer(S.EVENT_SIZE)
        self.info = []

    def open(self):
        rw = S.sdl.SDL_RWFromFile(GAMECONTROLLER_DB.encode(), b"rb")
        if rw:
            S.sdl.SDL_GameControllerAddMappingsFromRW(rw, 1)
        self.pads, self.info, self.held = [], [], None
        for i in range(S.sdl.SDL_NumJoysticks()):
            guid = bytes(S.sdl.SDL_JoystickGetDeviceGUID(i).data).hex()
            name = (S.sdl.SDL_JoystickNameForIndex(i) or b"?").decode(errors="replace")
            ok = S.sdl.SDL_IsGameController(i)
            self.info.append({"index": i, "name": name, "guid": guid, "mapped": bool(ok)})
            if ok:
                pad = S.sdl.SDL_GameControllerOpen(i)
                if pad:
                    self.pads.append(pad)

    def close(self):
        for p in self.pads:
            S.sdl.SDL_GameControllerClose(p)
        self.pads = []
        self.held = None

    def timeout_ms(self, idle_ms):
        if self.held:
            return max(0, int((self.held[1] - time.monotonic()) * 1000))
        return idle_ms

    def _press(self, action, out):
        out.append(action)
        if action in REPEATABLE:
            self.held = (action, time.monotonic() + REPEAT_DELAY)

    def _release(self, action):
        if self.held and self.held[0] == action:
            self.held = None

    def poll(self, wait_ms):
        """Wait up to wait_ms for input; returns (actions, quit_requested)."""
        out, quit_ = [], False
        got = S.sdl.SDL_WaitEventTimeout(self.ev, self.timeout_ms(wait_ms))
        while got:
            etype = struct.unpack_from("<I", self.ev.raw, 0)[0]
            if etype == S.QUIT:
                quit_ = True
            elif etype in (S.CONTROLLERBUTTONDOWN, S.CONTROLLERBUTTONUP):
                button = self.ev.raw[12]
                action = BUTTONS.get(button)
                if action:
                    if etype == S.CONTROLLERBUTTONDOWN:
                        self._press(action, out)
                    else:
                        self._release(action)
            elif etype == S.CONTROLLERAXISMOTION:
                axis = self.ev.raw[12]
                value = struct.unpack_from("<h", self.ev.raw, 16)[0]
                if axis in self.axis_dir:
                    neg, pos = ("left", "right") if axis == S.AXIS_LEFTX else ("up", "down")
                    cur = self.axis_dir[axis]
                    new = neg if value < -AXIS_ON else pos if value > AXIS_ON else (
                        cur if abs(value) > AXIS_OFF else None)
                    if new != cur:
                        if cur:
                            self._release(cur)
                        if new:
                            self._press(new, out)
                        self.axis_dir[axis] = new
            elif etype in (S.CONTROLLERDEVICEADDED, S.CONTROLLERDEVICEREMOVED):
                self.close()
                self.open()
            got = S.sdl.SDL_PollEvent(self.ev)
        if self.held and time.monotonic() >= self.held[1]:
            out.append(self.held[0])
            self.held = (self.held[0], time.monotonic() + REPEAT_EVERY)
        return out, quit_
