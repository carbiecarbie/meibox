"""Minimal ctypes bindings for the SDL2 libraries already installed on the R36S.

Only the functions Totobox uses are declared. Loading is lazy so the pure-Python
modules (index, launcher) can be imported and tested on a PC without SDL.
"""
import ctypes as C

vp = C.c_void_p


class Rect(C.Structure):
    _fields_ = [("x", C.c_int), ("y", C.c_int), ("w", C.c_int), ("h", C.c_int)]


class GUID(C.Structure):
    _fields_ = [("data", C.c_uint8 * 16)]


class Color(C.Structure):
    _fields_ = [("r", C.c_uint8), ("g", C.c_uint8), ("b", C.c_uint8), ("a", C.c_uint8)]


# SDL_Init flags
INIT_AUDIO = 0x10
INIT_VIDEO = 0x20
INIT_JOYSTICK = 0x200
INIT_GAMECONTROLLER = 0x2000
INIT_EVENTS = 0x4000

WINDOW_FULLSCREEN = 0x1
WINDOW_SHOWN = 0x4
RENDERER_ACCELERATED = 0x2
RENDERER_PRESENTVSYNC = 0x4
RENDERER_TARGETTEXTURE = 0x8
BLENDMODE_BLEND = 1
TEXTUREACCESS_TARGET = 2
PIXELFORMAT_ABGR8888 = 0x16762004  # byte order R,G,B,A on little endian

# Event types
QUIT = 0x100
KEYDOWN = 0x300
CONTROLLERAXISMOTION = 0x650
CONTROLLERBUTTONDOWN = 0x651
CONTROLLERBUTTONUP = 0x652
CONTROLLERDEVICEADDED = 0x653
CONTROLLERDEVICEREMOVED = 0x654

# Game controller buttons
BTN_A, BTN_B, BTN_X, BTN_Y = 0, 1, 2, 3
BTN_BACK, BTN_GUIDE, BTN_START = 4, 5, 6
BTN_LSHOULDER, BTN_RSHOULDER = 9, 10
BTN_DPUP, BTN_DPDOWN, BTN_DPLEFT, BTN_DPRIGHT = 11, 12, 13, 14
AXIS_LEFTX, AXIS_LEFTY = 0, 1

EVENT_SIZE = 56

sdl = img = ttf = mix = gfx = None


def _fn(lib, name, res, *args):
    f = getattr(lib, name)
    f.restype = res
    f.argtypes = list(args)


def load():
    """Load the shared libraries and declare signatures. Safe to call twice."""
    global sdl, img, ttf, mix, gfx
    if sdl is not None:
        return
    sdl = C.CDLL("libSDL2-2.0.so.0")
    img = C.CDLL("libSDL2_image-2.0.so.0")
    ttf = C.CDLL("libSDL2_ttf-2.0.so.0")
    mix = C.CDLL("libSDL2_mixer-2.0.so.0")
    gfx = C.CDLL("libSDL2_gfx-1.0.so.0")
    i, u32, u8, cp = C.c_int, C.c_uint32, C.c_uint8, C.c_char_p
    _fn(sdl, "SDL_Init", i, u32)
    _fn(sdl, "SDL_InitSubSystem", i, u32)
    _fn(sdl, "SDL_QuitSubSystem", None, u32)
    _fn(sdl, "SDL_Quit", None)
    _fn(sdl, "SDL_GetError", cp)
    _fn(sdl, "SDL_SetHint", C.c_bool, cp, cp)
    _fn(sdl, "SDL_ShowCursor", i, i)
    _fn(sdl, "SDL_GetTicks", u32)
    _fn(sdl, "SDL_CreateWindow", vp, cp, i, i, i, i, u32)
    _fn(sdl, "SDL_DestroyWindow", None, vp)
    _fn(sdl, "SDL_CreateRenderer", vp, vp, i, u32)
    _fn(sdl, "SDL_DestroyRenderer", None, vp)
    _fn(sdl, "SDL_RenderClear", i, vp)
    _fn(sdl, "SDL_RenderPresent", None, vp)
    _fn(sdl, "SDL_RenderCopy", i, vp, vp, vp, vp)
    _fn(sdl, "SDL_RenderFillRect", i, vp, vp)
    _fn(sdl, "SDL_SetRenderDrawColor", i, vp, u8, u8, u8, u8)
    _fn(sdl, "SDL_SetRenderDrawBlendMode", i, vp, i)
    _fn(sdl, "SDL_SetRenderTarget", i, vp, vp)
    _fn(sdl, "SDL_RenderReadPixels", i, vp, vp, u32, vp, i)
    _fn(sdl, "SDL_CreateTexture", vp, vp, u32, i, i, i)
    _fn(sdl, "SDL_CreateTextureFromSurface", vp, vp, vp)
    _fn(sdl, "SDL_DestroyTexture", None, vp)
    _fn(sdl, "SDL_SetTextureBlendMode", i, vp, i)
    _fn(sdl, "SDL_ComposeCustomBlendMode", i, i, i, i, i, i, i)
    _fn(sdl, "SDL_SetTextureAlphaMod", i, vp, u8)
    _fn(sdl, "SDL_SetTextureColorMod", i, vp, u8, u8, u8)
    _fn(sdl, "SDL_QueryTexture", i, vp, vp, vp, C.POINTER(i), C.POINTER(i))
    _fn(sdl, "SDL_CreateRGBSurfaceWithFormat", vp, u32, i, i, i, u32)
    _fn(sdl, "SDL_CreateRGBSurfaceWithFormatFrom", vp, vp, i, i, i, i, u32)
    _fn(sdl, "SDL_ConvertSurfaceFormat", vp, vp, u32, u32)
    _fn(sdl, "SDL_FreeSurface", None, vp)
    _fn(sdl, "SDL_SoftStretchLinear", i, vp, vp, vp, vp)
    _fn(sdl, "SDL_LockSurface", i, vp)
    _fn(sdl, "SDL_UnlockSurface", None, vp)
    _fn(sdl, "SDL_PollEvent", i, vp)
    _fn(sdl, "SDL_WaitEventTimeout", i, vp, i)
    _fn(sdl, "SDL_RWFromFile", vp, cp, cp)
    _fn(sdl, "SDL_GameControllerAddMappingsFromRW", i, vp, i)
    _fn(sdl, "SDL_NumJoysticks", i)
    _fn(sdl, "SDL_IsGameController", C.c_bool, i)
    _fn(sdl, "SDL_GameControllerOpen", vp, i)
    _fn(sdl, "SDL_GameControllerClose", None, vp)
    _fn(sdl, "SDL_GameControllerName", cp, vp)
    _fn(sdl, "SDL_JoystickGetDeviceGUID", GUID, i)
    _fn(sdl, "SDL_JoystickNameForIndex", cp, i)
    _fn(img, "IMG_Init", i, i)
    _fn(img, "IMG_Quit", None)
    _fn(img, "IMG_Load", vp, cp)
    _fn(img, "IMG_LoadTexture", vp, vp, cp)
    _fn(img, "IMG_SavePNG", i, vp, cp)
    _fn(ttf, "TTF_Init", i)
    _fn(ttf, "TTF_Quit", None)
    _fn(ttf, "TTF_OpenFont", vp, cp, i)
    _fn(ttf, "TTF_CloseFont", None, vp)
    _fn(ttf, "TTF_RenderUTF8_Blended", vp, vp, cp, Color)
    _fn(ttf, "TTF_SizeUTF8", i, vp, cp, C.POINTER(i), C.POINTER(i))
    _fn(ttf, "TTF_FontHeight", i, vp)
    _fn(ttf, "TTF_GlyphIsProvided32", i, vp, u32)
    _fn(gfx, "roundedBoxRGBA", i, vp, C.c_int16, C.c_int16, C.c_int16, C.c_int16, C.c_int16, u8, u8, u8, u8)
    _fn(gfx, "roundedRectangleRGBA", i, vp, C.c_int16, C.c_int16, C.c_int16, C.c_int16, C.c_int16, u8, u8, u8, u8)
    _fn(gfx, "filledPolygonRGBA", i, vp, C.POINTER(C.c_int16), C.POINTER(C.c_int16), i, u8, u8, u8, u8)
    _fn(gfx, "filledTrigonRGBA", i, vp, C.c_int16, C.c_int16, C.c_int16, C.c_int16, C.c_int16, C.c_int16, u8, u8, u8, u8)


def error():
    return sdl.SDL_GetError().decode(errors="replace")


def texture_size(tex):
    w, h = C.c_int(), C.c_int()
    sdl.SDL_QueryTexture(tex, None, None, C.byref(w), C.byref(h))
    return w.value, h.value


def surface_dims(surf):
    """(w, h, pitch, pixels_ptr) of an SDL_Surface* (SDL2 struct layout, 64-bit)."""
    # struct SDL_Surface { Uint32 flags; SDL_PixelFormat *format; int w, h; int pitch; void *pixels; ... }
    base = surf
    w = C.c_int.from_address(base + 16).value
    h = C.c_int.from_address(base + 20).value
    pitch = C.c_int.from_address(base + 24).value
    pixels = C.c_void_p.from_address(base + 32).value
    return w, h, pitch, pixels
