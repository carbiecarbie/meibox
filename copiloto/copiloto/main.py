"""Serviço do Copiloto da Mei: HTTP em 127.0.0.1:4404 para o Serviço de IA do RetroArch.

Fluxo de um SELECT + R1 (design 5 e 12):
  1. Uma dica por vez: um segundo pedido recebe "Calma, ainda tô pensando".
  2. Limite do dia e chave.
  3. Jogo sem ficha: pesquisa com o aviso do RetroArch na tela (ou, sem aviso, responde na hora
     e pesquisa por trás). Falhou: a dica sai sem ficha, com a frase "Não consegui pesquisar".
  4. Dica: instrução da Mei + ficha + diário + foto ampliada 2x -> {fala, onde}.
  5. Responde o balão; depois salva a imagem da dica em pasta_dicas.
"""
import base64
import json
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, diario, ficha, jogador, label, mensagens, prompts, uso
from .aviso import Aviso
from .conectores import base as conbase

MAX_CORPO = 16 * 1024 * 1024


def rss_mb():
    try:
        with open("/proc/self/status") as f:
            return int(f.read().split("VmRSS:")[1].split()[0]) // 1024
    except (OSError, IndexError, ValueError):
        return 0


class Registro:
    """Log simples com as últimas ~500 linhas. Nunca recebe a chave."""

    def __init__(self, caminho, max_linhas=500, eco=True):
        self.caminho = caminho
        self.max_linhas = max_linhas
        self.eco = eco
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(caminho), exist_ok=True)

    def __call__(self, msg):
        linha = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        with self.lock:
            if self.eco:
                print(linha, flush=True)
            try:
                with open(self.caminho, "a", encoding="utf-8") as f:
                    f.write(linha + "\n")
                if os.path.getsize(self.caminho) > self.max_linhas * 400:
                    with open(self.caminho, encoding="utf-8") as f:
                        resto = f.readlines()[-self.max_linhas:]
                    with open(self.caminho, "w", encoding="utf-8") as f:
                        f.writelines(resto)
            except OSError:
                pass


class Copiloto:
    def __init__(self, cfg, desenho=None, conectores=None, log=None):
        self.cfg = cfg
        estado = cfg["pasta_estado"]
        self.log = log or Registro(os.path.join(estado, "copiloto.log"))
        self.uso = uso.Uso(estado)
        self.diario = diario.Diario(estado, cfg["linhas_diario"])
        self.fichas = ficha.Fichas(cfg["pasta_guias"])
        if desenho is None:
            from .desenho import Desenho
            desenho = Desenho(cfg["pasta_assets"])
        self.desenho = desenho
        if conectores is None:
            nome_d, nome_f = cfg["dicas"]["fornecedor"], cfg["ficha"]["fornecedor"]
            con_d = conbase.criar(nome_d, cfg)
            con_f = con_d if nome_f == nome_d else conbase.criar(nome_f, cfg)
            if not cfg["ficha"].get("modelo"):
                con_f = None  # sem modelo para a ficha: as dicas saem sem ficha
            conectores = (con_d, con_f)
        self.con_dica, self.con_ficha = conectores
        self.aviso = Aviso(cfg["aviso_porta"], cfg["aviso_intervalo_s"]) if cfg["aviso"] else None
        self.ocupado = threading.Lock()
        self.estudando = set()
        self.lock_estudo = threading.Lock()

    def carregar_sdk(self):
        t = time.monotonic()
        for c in {id(self.con_dica): self.con_dica, id(self.con_ficha): self.con_ficha}.values():
            if c is not None:
                c.carregar()
        return time.monotonic() - t

    # ---------------------------------------------------------------- balões
    def _balao(self, texto, idioma):
        return self.desenho.balao_png(texto, rodape=mensagens.frase("rodape", idioma))

    def _erro(self, chave, idioma, **campos):
        campos.setdefault("limite", self.cfg["limite_por_dia"])
        return self._balao(mensagens.frase(chave, idioma, **campos), idioma), None

    # ---------------------------------------------------------------- ficha
    def _estudar(self, info, idioma, com_aviso):
        """Pesquisa e salva a ficha. Devolve o texto (ou "" se falhou)."""
        console, jogo = info["console"], info["jogo"]
        k = ficha.chave_jogo(console, jogo)
        with self.lock_estudo:
            self.estudando.add(k)
        if com_aviso and self.aviso:
            self.aviso.iniciar(mensagens.frase("estudando_aviso", idioma, jogo=jogo))
        t0 = time.monotonic()
        cf = self.cfg["ficha"]
        try:
            self.uso.contar_ficha()
            r = ficha.gerar(self.con_ficha, cf, console, jogo, info["regiao"], idioma,
                            self.cfg["tempo_ficha_s"])
            texto = ficha.montar(r, console, jogo, info["regiao"], idioma, cf["modelo"])
            caminho = self.fichas.salvar(console, jogo, texto)
            self.uso.sucesso_ficha(k)
            self.log(f"FICHA ok {jogo!r} [{console}] {time.monotonic() - t0:.1f}s "
                     f"buscas={r.buscas} in={r.tokens_entrada} out={r.tokens_saida} "
                     f"custo=US${r.custo_usd:.4f} palavras={len(r.texto.split())} "
                     f"pesquisa={'sim' if r.com_pesquisa else 'NAO'} -> {caminho}")
            return self.fichas.ler(console, jogo) or texto
        except Exception as e:  # noqa: BLE001 - qualquer falha: a dica segue sem ficha
            self.uso.falha_ficha(k)
            det = f"{e.codigo} {e.detalhe}" if isinstance(e, conbase.ErroIA) else repr(e)[:300]
            self.log(f"FICHA falhou {jogo!r} [{console}] {time.monotonic() - t0:.1f}s {det}")
            return ""
        finally:
            if com_aviso and self.aviso:
                self.aviso.parar()
            with self.lock_estudo:
                self.estudando.discard(k)

    def _acordar(self, idioma):
        """Carrega o SDK no primeiro aperto, com o aviso na tela."""
        if self.aviso:
            self.aviso.iniciar(mensagens.frase("acordando_aviso", idioma))
        try:
            self.log(f"SDK carregado no 1º aperto em {self.carregar_sdk():.1f}s rss={rss_mb()}MB")
        finally:
            if self.aviso:
                self.aviso.parar()

    # ---------------------------------------------------------------- pedido
    def atender(self, corpo, usar_ficha=True):
        """Pedido do RetroArch -> (png do balão, função para rodar depois de responder ou None)."""
        t0 = time.monotonic()
        info = label.interpretar(corpo.get("label"))
        console, jogo = info["console"], info["jogo"]
        idioma, nome = jogador.ler(self.cfg)
        try:
            tela = base64.b64decode(corpo.get("image") or "", validate=False)
        except ValueError:
            tela = b""
        if not self.ocupado.acquire(blocking=False):
            self.log(f"DICA ocupado {jogo!r}")
            return self._erro("ocupado", idioma)
        try:
            return self._atender(info, idioma, nome, tela, t0, usar_ficha)
        finally:
            self.ocupado.release()

    def _atender(self, info, idioma, nome, tela, t0, usar_ficha):
        console, jogo = info["console"], info["jogo"]
        cfg = self.cfg
        if not tela.startswith(b"\x89PNG"):
            self.log(f"DICA sem tela {jogo!r}")
            return self._erro("vazio", idioma)
        if not self.uso.pode_dar_dica(cfg["limite_por_dia"]):
            self.log(f"DICA limite do dia {jogo!r}")
            return self._erro("limite_dia", idioma)
        if self.con_dica is None or not cfg["dicas"].get("modelo"):
            self.log("DICA sem IA configurada (config.json: dicas.fornecedor e dicas.modelo)")
            return self._erro("nao_configurado", idioma)
        if not self.con_dica.chave_existe():
            self.log(f"DICA sem chave ({cfg['dicas']['fornecedor']})")
            return self._erro("sem_chave", idioma)

        prefixo, texto_ficha, t_ficha = "", "", 0.0
        if usar_ficha and jogo:
            texto_ficha = self.fichas.ler(console, jogo)
            k = ficha.chave_jogo(console, jogo)
            with self.lock_estudo:
                em_estudo = k in self.estudando
            if not texto_ficha and em_estudo:
                return self._erro("ainda_estudando", idioma, jogo=jogo)
            if (not texto_ficha and self.uso.pode_fazer_ficha(k, cfg["fichas_por_dia"])
                    and self.con_ficha is not None and self.con_ficha.chave_existe()):
                if self.aviso is None:  # reserva: responde já e pesquisa por trás
                    threading.Thread(target=self._estudar, args=(info, idioma, False), daemon=True).start()
                    self.log(f"DICA estudando por trás {jogo!r}")
                    return self._erro("estudando_balao", idioma, jogo=jogo)
                tf = time.monotonic()
                texto_ficha = self._estudar(info, idioma, True)
                t_ficha = time.monotonic() - tf
                if not texto_ficha:
                    prefixo = mensagens.frase("ficha_falhou", idioma, jogo=jogo)

        try:
            if getattr(self.con_dica, "sdk", True) is None:  # SDK ainda não carregado (~13 s)
                self._acordar(idioma)
            ta = time.monotonic()
            ampliada = self.desenho.ampliar_png(tela, int(cfg["ampliar"]))
            tb = time.monotonic()
            r = self.con_dica.dica(
                modelo=cfg["dicas"]["modelo"], esforco=cfg["dicas"].get("esforco"),
                sistema=prompts.sistema_dica(idioma, nome),
                ficha=prompts.bloco_ficha(texto_ficha, idioma),
                texto=prompts.texto_dica(console, jogo, info["regiao"],
                                         self.diario.ler(console, jogo), idioma),
                imagem_png=ampliada, tempo_max=cfg["tempo_maximo_s"],
            )
            tc = time.monotonic()
            fala = self.desenho.imprimivel(r.fala)
            if not fala:
                raise conbase.ErroIA(conbase.VAZIO, "fala só com emoji")
        except conbase.ErroIA as e:
            self.log(f"DICA erro {jogo!r} [{console}] {time.monotonic() - t0:.1f}s {e.codigo} {e.detalhe}")
            return self._erro(e.codigo, idioma)
        except Exception as e:  # noqa: BLE001
            self.log(f"DICA erro {jogo!r} [{console}] {type(e).__name__}: "
                     f"{traceback.format_exc(limit=3)[-600:]}")
            return self._erro("outro", idioma, codigo=type(e).__name__)

        texto = f"{prefixo} {fala}" if prefixo and self.desenho.cabe(f"{prefixo} {fala}") else fala
        self.uso.contar_dica()
        self.diario.anotar(console, jogo, r.onde, fala)
        png = self._balao(texto, idioma)
        total = time.monotonic() - t0
        self.log(f"DICA ok {jogo!r} [{console}] total={total:.1f}s ficha={t_ficha:.1f}s "
                 f"ampliar={tb - ta:.2f}s ia={tc - tb:.1f}s in={r.tokens_entrada} "
                 f"cache={r.tokens_cache} out={r.tokens_saida} tent={r.tentativas} "
                 f"com_ficha={'sim' if texto_ficha else 'nao'} rss={rss_mb()}MB")
        self.log(f"   onde: {r.onde}")
        self.log(f"   fala: {texto}")

        def depois():
            if not cfg["salvar_dicas"]:
                return
            try:
                img = self.desenho.imagem_dica(tela, texto, mensagens.frase("rodape", idioma))
                os.makedirs(cfg["pasta_dicas"], exist_ok=True)
                raiz = f"{time.strftime('%Y-%m-%d_%H-%M-%S')}_{label.nome_ascii(jogo)}"
                for n in range(1, 100):
                    caminho = os.path.join(cfg["pasta_dicas"], raiz + (f"_{n}" if n > 1 else "") + ".png")
                    try:
                        with open(caminho, "xb") as f:
                            f.write(img)
                        break
                    except FileExistsError:
                        continue
                self.log(f"   salva: {caminho}")
            except Exception as e:  # noqa: BLE001
                self.log(f"   dica não salva: {e!r}")

        return png, depois


# -------------------------------------------------------------------- HTTP

def _handler(copiloto):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            try:
                n = min(int(self.headers.get("Content-Length") or 0), MAX_CORPO)
                corpo = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(corpo, dict):
                    corpo = {}
            except (ValueError, OSError):
                corpo = {}
            png, depois = copiloto.atender(corpo)
            dados = json.dumps({"image": base64.b64encode(png).decode()}).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)
                self.wfile.flush()
            except OSError as e:
                copiloto.log(f"resposta não entregue: {e!r}")
            if depois:
                depois()

        def log_message(self, *a):
            pass

    return Handler


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def principal(args=()):
    cfg = config.carregar()
    log = Registro(os.path.join(cfg["pasta_estado"], "copiloto.log"))
    cop = Copiloto(cfg, log=log)
    log(f"iniciando: dicas={cfg['dicas']['fornecedor']}/{cfg['dicas']['modelo']} "
        f"ficha={cfg['ficha']['fornecedor']}/{cfg['ficha']['modelo']} aviso={cfg['aviso']} "
        f"sdk={cfg['carregar_sdk']} rss={rss_mb()}MB")
    if cfg["carregar_sdk"] == "inicio":
        t = cop.carregar_sdk()
        log(f"SDK carregado em {t:.1f}s rss={rss_mb()}MB")
    srv = _Servidor(("127.0.0.1", int(cfg["porta"])), _handler(cop))
    log(f"escutando 127.0.0.1:{cfg['porta']}")
    srv.serve_forever(poll_interval=3600)


# -------------------------------------------------------------------- comandos de teste

def cmd_dica(cfg, args):
    """dica FOTO.png LABEL [SAIDA.png] [--sem-ficha]"""
    sem_ficha = "--sem-ficha" in args
    args = [a for a in args if a != "--sem-ficha"]
    foto, lbl = args[0], args[1]
    saida = args[2] if len(args) > 2 else "/tmp/copiloto-dev/teste/balao-dica.png"
    cop = Copiloto(cfg)
    if cfg["carregar_sdk"] == "inicio":
        print(f"SDK em {cop.carregar_sdk():.1f}s rss={rss_mb()}MB")
    with open(foto, "rb") as f:
        corpo = {"image": base64.b64encode(f.read()).decode(), "label": lbl}
    png, depois = cop.atender(corpo, usar_ficha=not sem_ficha)
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, "wb") as f:
        f.write(png)
    if depois:
        depois()
    print(f"balão -> {saida} rss={rss_mb()}MB")


def cmd_ficha(cfg, args):
    """ficha LABEL — gera a ficha sem dica (com o aviso, se ligado)."""
    cop = Copiloto(cfg)
    info = label.interpretar(args[0])
    idioma, _ = jogador.ler(cfg)
    existente = cop.fichas.ler(info["console"], info["jogo"])
    if existente:
        print(f"já existe: {cop.fichas.caminho(info['console'], info['jogo'])}")
        return
    texto = cop._estudar(info, idioma, com_aviso=False)
    print("ok" if texto else "falhou", cop.fichas.caminho(info["console"], info["jogo"]))


def cmd_aviso(cfg, args):
    """aviso TEXTO [SEGUNDOS]"""
    segundos = float(args[1]) if len(args) > 1 else 12
    a = Aviso(cfg["aviso_porta"], cfg["aviso_intervalo_s"])
    a.iniciar(args[0])
    time.sleep(segundos)
    a.parar()
    print(f"enviadas={a.enviadas}")
