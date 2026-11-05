"""Desenho com SDL2 via ctypes, sem janela: balão da Mei, ampliação nítida e imagem da dica.

O SDL só é carregado quando se cria um `Desenho`, então as funções puras (cortar_linhas,
quebrar) podem ser testadas no PC sem as bibliotecas.
"""
import ctypes as C
import itertools
import os
import re
import tempfile
import threading

W, H = 640, 480
BX, BY, BW, BH = 16, 292, 608, 172          # caixa do balão (4 linhas + rodapé)
TX = BX + 140                                # início do texto (a Mei fica à esquerda)
LARGURA_TEXTO = BX + BW - TX - 16
MAX_LINHAS = 4

_FIM_FRASE = re.compile(r"(?<=[.!?…])\s+")


# ------------------------------------------------------------------ partes puras

def quebrar(texto, largura_de, largura_max):
    """Quebra em linhas por palavras. `largura_de(str) -> px`."""
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if largura_de(teste) > largura_max and atual:
            linhas.append(atual)
            atual = palavra
        else:
            atual = teste
    return linhas + [atual] if atual else linhas


def cortar_linhas(texto, largura_de, largura_max=LARGURA_TEXTO, max_linhas=MAX_LINHAS):
    """Linhas que cabem no balão: corta na última frase inteira que cabe; se nem a primeira
    frase couber, corta a seco com reticências."""
    texto = re.sub(r"\s+", " ", texto or "").strip()
    linhas = quebrar(texto, largura_de, largura_max)
    if len(linhas) <= max_linhas:
        return linhas
    frases = _FIM_FRASE.split(texto)
    while len(frases) > 1:
        frases.pop()
        tentativa = quebrar(" ".join(frases), largura_de, largura_max)
        if len(tentativa) <= max_linhas:
            return tentativa
    linhas = linhas[:max_linhas]
    ultima = linhas[-1].rstrip(".,;: ")
    while ultima and largura_de(ultima + "…") > largura_max:
        ultima = ultima[:-1].rstrip()
    linhas[-1] = ultima + "…"
    return linhas


# ------------------------------------------------------------------ SDL

class _Rect(C.Structure):
    _fields_ = [("x", C.c_int), ("y", C.c_int), ("w", C.c_int), ("h", C.c_int)]


class _Color(C.Structure):
    _fields_ = [("r", C.c_uint8), ("g", C.c_uint8), ("b", C.c_uint8), ("a", C.c_uint8)]


class _Surface(C.Structure):
    _fields_ = [("flags", C.c_uint32), ("format", C.c_void_p), ("w", C.c_int), ("h", C.c_int)]


_RGBA32, _BLEND, _NONE = 0x16762004, 1, 0
_vp = C.c_void_p
_SP = C.POINTER(_Surface)

COR_BORDA = (255, 240, 250, 255)
COR_FUNDO = (28, 14, 48, 230)
COR_TITULO = (255, 205, 80)
COR_TEXTO = (255, 255, 255)
COR_RODAPE = (190, 170, 220)


def _carregar_libs():
    sdl = C.CDLL("libSDL2-2.0.so.0")
    img = C.CDLL("libSDL2_image-2.0.so.0")
    ttf = C.CDLL("libSDL2_ttf-2.0.so.0")
    sdl.SDL_CreateRGBSurfaceWithFormat.restype = _SP
    sdl.SDL_CreateRGBSurfaceWithFormat.argtypes = [C.c_uint32, C.c_int, C.c_int, C.c_int, C.c_uint32]
    sdl.SDL_FillRect.argtypes = [_vp, C.POINTER(_Rect), C.c_uint32]
    sdl.SDL_MapRGBA.restype = C.c_uint32
    sdl.SDL_MapRGBA.argtypes = [_vp, C.c_uint8, C.c_uint8, C.c_uint8, C.c_uint8]
    sdl.SDL_SetSurfaceBlendMode.argtypes = [_vp, C.c_int]
    sdl.SDL_UpperBlit.argtypes = [_vp, C.POINTER(_Rect), _vp, C.POINTER(_Rect)]
    sdl.SDL_UpperBlitScaled.argtypes = [_vp, C.POINTER(_Rect), _vp, C.POINTER(_Rect)]
    sdl.SDL_FreeSurface.argtypes = [_vp]
    sdl.SDL_RWFromConstMem.restype = _vp
    sdl.SDL_RWFromConstMem.argtypes = [C.c_void_p, C.c_int]
    sdl.SDL_GetError.restype = C.c_char_p
    img.IMG_Load.restype = _SP
    img.IMG_Load.argtypes = [C.c_char_p]
    img.IMG_Load_RW.restype = _SP
    img.IMG_Load_RW.argtypes = [_vp, C.c_int]
    img.IMG_SavePNG.argtypes = [_vp, C.c_char_p]
    ttf.TTF_OpenFont.restype = _vp
    ttf.TTF_OpenFont.argtypes = [C.c_char_p, C.c_int]
    ttf.TTF_RenderUTF8_Blended.restype = _SP
    ttf.TTF_RenderUTF8_Blended.argtypes = [_vp, C.c_char_p, _Color]
    ttf.TTF_SizeUTF8.argtypes = [_vp, C.c_char_p, C.POINTER(C.c_int), C.POINTER(C.c_int)]
    ttf.TTF_GlyphIsProvided32.argtypes = [_vp, C.c_uint32]
    img.IMG_Init(2)  # PNG
    if ttf.TTF_Init() != 0:
        raise RuntimeError("TTF_Init falhou")
    return sdl, img, ttf


class Desenho:
    """Um por processo. Métodos são seguros entre threads (um lock só)."""

    def __init__(self, pasta_assets):
        self.sdl, self.img, self.ttf = _carregar_libs()
        fontes = os.path.join(pasta_assets, "fonts")
        self.f_titulo = self._fonte(os.path.join(fontes, "Baloo2-Bold.ttf"), 30)
        self.f_corpo = self._fonte(os.path.join(fontes, "Nunito-Bold.ttf"), 21)
        self.f_rodape = self._fonte(os.path.join(fontes, "Nunito-Bold.ttf"), 15)
        self.mei = self.img.IMG_Load(os.path.join(pasta_assets, "mascote-mei.png").encode())
        if self.mei:
            self.sdl.SDL_SetSurfaceBlendMode(self.mei, _BLEND)
        self.lock = threading.Lock()
        pasta_tmp = "/dev/shm" if os.path.isdir("/dev/shm") else tempfile.gettempdir()
        self._tmp = os.path.join(pasta_tmp, f"mei-copiloto-{os.getpid()}")
        self._n = itertools.count()

    def _fonte(self, caminho, tamanho):
        f = self.ttf.TTF_OpenFont(caminho.encode(), tamanho)
        if not f:
            raise RuntimeError(f"fonte não abriu: {caminho}")
        return f

    # ---- utilidades
    def _superficie(self, w, h):
        return self.sdl.SDL_CreateRGBSurfaceWithFormat(0, w, h, 32, _RGBA32)

    def _preencher(self, s, x, y, w, h, rgba):
        cor = self.sdl.SDL_MapRGBA(s.contents.format, *rgba)
        self.sdl.SDL_FillRect(s, C.byref(_Rect(x, y, w, h)), cor)

    def largura(self, fonte, texto):
        w, h = C.c_int(), C.c_int()
        self.ttf.TTF_SizeUTF8(fonte, texto.encode(), C.byref(w), C.byref(h))
        return w.value

    def _escrever(self, s, fonte, texto, x, y, rgb):
        t = self.ttf.TTF_RenderUTF8_Blended(fonte, texto.encode(), _Color(*rgb, 255))
        if not t:
            return 0
        self.sdl.SDL_SetSurfaceBlendMode(t, _BLEND)
        self.sdl.SDL_UpperBlit(t, None, s, C.byref(_Rect(x, y, 0, 0)))
        altura = t.contents.h
        self.sdl.SDL_FreeSurface(t)
        return altura

    def imprimivel(self, texto):
        """Tira os caracteres que a fonte não tem (emojis viram quadrados vazios)."""
        ok = "".join(ch for ch in texto or ""
                     if ch.isspace() or self.ttf.TTF_GlyphIsProvided32(self.f_corpo, ord(ch)))
        return re.sub(r"\s+", " ", ok).strip()

    def linhas(self, texto):
        return cortar_linhas(self.imprimivel(texto), lambda t: self.largura(self.f_corpo, t))

    def cabe(self, texto):
        """True se o texto inteiro cabe no balão, sem corte."""
        return " ".join(self.linhas(texto)) == self.imprimivel(texto)

    def _png(self, s):
        caminho = f"{self._tmp}-{next(self._n)}.png"
        try:
            if self.img.IMG_SavePNG(s, caminho.encode()) != 0:
                raise RuntimeError(f"IMG_SavePNG: {self.sdl.SDL_GetError()!r}")
            with open(caminho, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(caminho)
            except OSError:
                pass

    def _abrir_png(self, dados):
        buf = C.create_string_buffer(dados, len(dados))
        rw = self.sdl.SDL_RWFromConstMem(buf, len(dados))
        s = self.img.IMG_Load_RW(rw, 1)
        if not s:
            raise ValueError("a imagem recebida não é um PNG válido")
        return s, buf

    def _balao(self, s, texto, rodape, titulo="Mei"):
        self._preencher(s, BX, BY, BW, BH, COR_BORDA)
        self._preencher(s, BX + 4, BY + 4, BW - 8, BH - 8, COR_FUNDO)
        if self.mei:
            fw, fh = self.mei.contents.w, self.mei.contents.h
            lado = 112
            dw, dh = (lado, lado * fh // fw) if fw >= fh else (lado * fw // fh, lado)
            self.sdl.SDL_UpperBlitScaled(self.mei, None, s,
                                         C.byref(_Rect(BX + 14, BY + (BH - dh) // 2, dw, dh)))
        y = BY + 4
        y += self._escrever(s, self.f_titulo, titulo, TX, y, COR_TITULO) - 10
        for linha in self.linhas(texto):
            y += self._escrever(s, self.f_corpo, linha, TX, y, COR_TEXTO) - 3
        if rodape:
            x = BX + BW - 16 - self.largura(self.f_rodape, rodape)
            self._escrever(s, self.f_rodape, rodape, x, BY + BH - 24, COR_RODAPE)

    # ---- o que o serviço usa
    def balao_png(self, texto, rodape=""):
        """PNG 640x480 transparente com o balão, para o RetroArch desenhar por cima do jogo."""
        with self.lock:
            s = self._superficie(W, H)
            try:
                self.sdl.SDL_FillRect(s, None, 0)
                self._balao(s, texto, rodape)
                return self._png(s)
            finally:
                self.sdl.SDL_FreeSurface(s)

    def ampliar_png(self, dados, fator):
        """Ampliação nítida (vizinho mais próximo) da tela recebida, para mandar à IA."""
        if fator <= 1:
            return dados
        with self.lock:
            src, _buf = self._abrir_png(dados)
            dst = None
            try:
                w, h = src.contents.w, src.contents.h
                dst = self._superficie(w * fator, h * fator)
                self.sdl.SDL_SetSurfaceBlendMode(src, _NONE)
                self.sdl.SDL_UpperBlitScaled(src, None, dst, C.byref(_Rect(0, 0, w * fator, h * fator)))
                return self._png(dst)
            finally:
                if dst:
                    self.sdl.SDL_FreeSurface(dst)
                self.sdl.SDL_FreeSurface(src)

    def imagem_dica(self, tela, texto, rodape=""):
        """Tela ampliada para caber em 640x480 (pixels nítidos, faixas pretas) + balão por cima."""
        with self.lock:
            src, _buf = self._abrir_png(tela)
            s = self._superficie(W, H)
            try:
                w, h = src.contents.w, src.contents.h
                k = min(W / w, H / h)
                dw, dh = int(w * k), int(h * k)
                self._preencher(s, 0, 0, W, H, (0, 0, 0, 255))
                self.sdl.SDL_SetSurfaceBlendMode(src, _NONE)
                self.sdl.SDL_UpperBlitScaled(src, None, s,
                                             C.byref(_Rect((W - dw) // 2, (H - dh) // 2, dw, dh)))
                self._balao(s, texto, rodape)
                return self._png(s)
            finally:
                self.sdl.SDL_FreeSurface(s)
                self.sdl.SDL_FreeSurface(src)
