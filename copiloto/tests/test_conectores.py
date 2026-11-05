"""Passo 3: conectores com cliente falso (anthropic) e servidor HTTP falso (openai_compat)."""
import base64
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from copiloto.conectores import base  # noqa: E402
from copiloto.conectores.anthropic_ import ConectorAnthropic  # noqa: E402
from copiloto.conectores.openai_compat import ConectorOpenAICompat  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\nfalso"


def _chave(d, conteudo="sk-teste-123"):
    p = os.path.join(d, "chave")
    with open(p, "w") as f:
        f.write(conteudo + "\n")
    return p


# ------------------------------------------------------------------ SDK falso

class FakeSDK:
    class APIError(Exception):
        pass

    class APIConnectionError(APIError):
        pass

    class APITimeoutError(APIConnectionError):
        pass

    class APIStatusError(APIError):
        def __init__(self, status_code, message=""):
            super().__init__(message)
            self.status_code, self.message = status_code, message

    class AuthenticationError(APIStatusError):
        pass

    class PermissionDeniedError(APIStatusError):
        pass

    class RateLimitError(APIStatusError):
        pass

    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.pedidos = []
        self.clientes = []

    def Anthropic(self, api_key, max_retries):  # noqa: N802 - imita o SDK
        self.clientes.append({"api_key": api_key, "max_retries": max_retries})
        sdk = self

        class Msgs:
            def create(self, **kw):
                sdk.pedidos.append(kw)
                item = sdk.roteiro.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item

        class Cliente:
            messages = Msgs()
            beta = NS(messages=Msgs())

            def with_options(self, timeout):
                sdk.pedidos.append({"timeout": timeout})
                return self

        return Cliente()


def _uso(i=100, o=20, buscas=0):
    return NS(input_tokens=i, output_tokens=o, cache_read_input_tokens=0, cache_creation_input_tokens=0,
              server_tool_use=NS(web_search_requests=buscas, web_fetch_requests=0))


def _msg(texto, stop="end_turn", blocos=None, buscas=0, model="claude-haiku-5-5"):
    conteudo = blocos if blocos is not None else [NS(type="thinking", thinking=""), NS(type="text", text=texto)]
    return NS(content=conteudo, stop_reason=stop, usage=_uso(buscas=buscas), model=model)


class TestAnthropic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.chave = _chave(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _con(self, roteiro):
        sdk = FakeSDK(roteiro)
        return ConectorAnthropic({"chave": self.chave}, sdk=sdk), sdk

    def _dica(self, con, ficha="FICHA"):
        return con.dica("claude-haiku-5-5", "low", "SISTEMA", ficha, "Console: X.", PNG, 15)

    def test_pedido_montado(self):
        con, sdk = self._con([_msg('{"fala": "Pule com B.", "onde": "Fase 1"}')])
        r = self._dica(con)
        self.assertEqual((r.fala, r.onde), ("Pule com B.", "Fase 1"))
        self.assertEqual(sdk.clientes[0], {"api_key": "sk-teste-123", "max_retries": 0})
        kw = [p for p in sdk.pedidos if "model" in p][0]
        self.assertEqual(kw["model"], "claude-haiku-5-5")
        self.assertEqual(kw["output_config"]["effort"], "low")
        self.assertEqual(kw["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(kw["system"][0]["text"], "SISTEMA")
        self.assertEqual(kw["system"][1]["cache_control"], {"type": "ephemeral"})
        conteudo = kw["messages"][0]["content"]
        self.assertEqual(conteudo[0]["type"], "image")
        self.assertEqual(base64.b64decode(conteudo[0]["source"]["data"]), PNG)
        self.assertEqual(conteudo[1]["text"], "Console: X.")
        self.assertNotIn("temperature", kw)

    def test_sem_ficha_um_bloco(self):
        con, sdk = self._con([_msg('{"fala": "a", "onde": "b"}')])
        self._dica(con, ficha="")
        kw = [p for p in sdk.pedidos if "model" in p][0]
        self.assertEqual(len(kw["system"]), 1)

    def test_recusa(self):
        con, _ = self._con([_msg("", stop="refusal")])
        with self.assertRaises(base.ErroIA) as c:
            self._dica(con)
        self.assertEqual(c.exception.codigo, "recusou")

    def test_erros_mapeados(self):
        casos = [
            (FakeSDK.AuthenticationError(401, "invalid x-api-key"), "chave_recusada"),
            (FakeSDK.PermissionDeniedError(403), "chave_recusada"),
            (FakeSDK.RateLimitError(429), "sem_credito"),
            (FakeSDK.APIStatusError(400, "Your credit balance is too low"), "sem_credito"),
            (FakeSDK.APIStatusError(400, "bad"), "http_400"),
            (FakeSDK.APITimeoutError("t"), "demorou"),
        ]
        for exc, codigo in casos:
            con, _ = self._con([exc])
            with self.assertRaises(base.ErroIA) as c:
                self._dica(con)
            self.assertEqual(c.exception.codigo, codigo, exc)
            self.assertNotIn("sk-teste", str(c.exception))

    def test_uma_nova_tentativa_em_falha_de_rede(self):
        con, _ = self._con([FakeSDK.APIConnectionError("x"), _msg('{"fala": "ok", "onde": "aqui"}')])
        self.assertEqual(self._dica(con).tentativas, 2)
        con, _ = self._con([FakeSDK.APIConnectionError("x"), FakeSDK.APIConnectionError("y")])
        with self.assertRaises(base.ErroIA) as c:
            self._dica(con)
        self.assertEqual(c.exception.codigo, "sem_internet")

    def test_timeout_nao_tenta_de_novo(self):
        con, sdk = self._con([FakeSDK.APITimeoutError("t"), _msg('{"fala": "ok", "onde": ""}')])
        with self.assertRaises(base.ErroIA):
            self._dica(con)
        self.assertEqual(len(sdk.roteiro), 1)

    def test_json_quebrado(self):
        con, _ = self._con([_msg('{"fala": "sem fim')])
        with self.assertRaises(base.ErroIA) as c:
            self._dica(con)
        self.assertEqual(c.exception.codigo, "vazio")

    def test_sem_chave(self):
        con = ConectorAnthropic({"chave": os.path.join(self.tmp.name, "nao")}, sdk=FakeSDK([]))
        self.assertFalse(con.chave_existe())
        with self.assertRaises(base.ErroIA) as c:
            self._dica(con)
        self.assertEqual(c.exception.codigo, "sem_chave")

    def test_ficha_com_busca_e_pause_turn(self):
        uso_busca = [NS(type="server_tool_use", name="web_search"), NS(type="web_search_tool_result")]
        r1 = _msg("", stop="pause_turn", buscas=3, model="claude-sonnet-5-5",
                  blocos=[NS(type="text", text="Vou pesquisar.", citations=None)] + uso_busca)
        texto = "RESUMO\n" + "x" * 300
        r2 = _msg("", buscas=2, model="claude-sonnet-5-5", blocos=uso_busca + [
            NS(type="text", text=texto[:100], citations=[NS(url="https://a.example")]),
            NS(type="text", text=texto[100:], citations=None)])
        con, sdk = self._con([r1, r2])
        f = con.ficha("claude-sonnet-5-5", "medium", "SIS", "Jogo: X.", True, 8, 90)
        self.assertEqual(f.texto, texto)
        self.assertEqual(f.buscas, 5)
        self.assertTrue(f.com_pesquisa)
        self.assertEqual(f.fontes, ["https://a.example"])
        self.assertGreater(f.custo_usd, 0.05)
        pedidos = [p for p in sdk.pedidos if "model" in p]
        self.assertEqual(pedidos[0]["tools"][0]["type"], "web_search_20260209")
        self.assertEqual(pedidos[0]["tools"][0]["max_uses"], 8)
        self.assertEqual(pedidos[0]["fallbacks"], "default")
        self.assertEqual(pedidos[1]["messages"][1]["role"], "assistant")

    def test_ficha_curta(self):
        con, _ = self._con([_msg("curta", model="claude-sonnet-5-5")])
        with self.assertRaises(base.ErroIA):
            con.ficha("claude-sonnet-5-5", None, "S", "P", True, 8, 90)


class TestInterpretarJson(unittest.TestCase):
    def test_variantes(self):
        self.assertEqual(base.interpretar_json('```json\n{"fala": "a", "onde": "b"}\n```'), ("a", "b"))
        self.assertEqual(base.interpretar_json('Claro! {"fala": "a"} pronto'), ("a", ""))
        self.assertEqual(base.interpretar_json("Só texto."), ("Só texto.", ""))
        for ruim in ("", '{"onde": "b"}', '{"fala": '):
            with self.assertRaises(base.ErroIA):
                base.interpretar_json(ruim)


# ------------------------------------------------------------------ servidor falso

class _Servidor:
    def __init__(self, roteiro):
        self.roteiro = list(roteiro)
        self.pedidos = []
        srv = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                srv.pedidos.append({"path": self.path, "auth": self.headers.get("Authorization"),
                                    "corpo": corpo})
                codigo, resposta, espera = srv.roteiro.pop(0)
                time.sleep(espera)
                dados = json.dumps(resposta).encode() if not isinstance(resposta, bytes) else resposta
                try:
                    self.send_response(codigo)
                    self.send_header("Content-Length", str(len(dados)))
                    self.end_headers()
                    self.wfile.write(dados)
                except OSError:
                    pass

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def fechar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _ok(texto, finish="stop"):
    return (200, {"choices": [{"message": {"content": texto}, "finish_reason": finish}],
                  "usage": {"prompt_tokens": 50, "completion_tokens": 10}}, 0)


class TestOpenAICompat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.chave = _chave(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _rodar(self, roteiro, tempo=5, url=None):
        srv = _Servidor(roteiro)
        try:
            con = ConectorOpenAICompat({"url": url or srv.url, "chave": self.chave})
            try:
                return con.dica("gpt-x", "low", "SIS", "FICHA", "Console: X.", PNG, tempo), srv
            except base.ErroIA as e:
                return e, srv
        finally:
            srv.fechar()

    def test_pedido_montado(self):
        r, srv = self._rodar([_ok('{"fala": "Pule.", "onde": "Fase 2"}')])
        self.assertEqual((r.fala, r.onde, r.tokens_entrada), ("Pule.", "Fase 2", 50))
        p = srv.pedidos[0]
        self.assertEqual(p["path"], "/v1/chat/completions")
        self.assertEqual(p["auth"], "Bearer sk-teste-123")
        c = p["corpo"]
        self.assertEqual(c["model"], "gpt-x")
        self.assertEqual(c["response_format"], {"type": "json_object"})
        self.assertIn("FICHA", c["messages"][0]["content"])
        img = c["messages"][1]["content"][0]["image_url"]["url"]
        self.assertTrue(img.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(img.split(",", 1)[1]), PNG)

    def test_tira_response_format_se_recusado(self):
        r, srv = self._rodar([(400, {"error": {"message": "response_format not supported"}}, 0),
                              _ok('{"fala": "a", "onde": "b"}')])
        self.assertEqual(r.fala, "a")
        self.assertNotIn("response_format", srv.pedidos[1]["corpo"])

    def test_troca_max_tokens(self):
        r, srv = self._rodar([(400, {"error": {"message": "use max_completion_tokens instead"}}, 0),
                              _ok('{"fala": "a", "onde": "b"}')])
        self.assertEqual(srv.pedidos[1]["corpo"]["max_completion_tokens"], 2048)

    def test_erros(self):
        for codigo, esperado in ((401, "chave_recusada"), (403, "chave_recusada"), (429, "sem_credito"),
                                 (402, "sem_credito"), (503, "sem_credito"), (404, "http_404")):
            e, _ = self._rodar([(codigo, {"error": "x"}, 0)])
            self.assertIsInstance(e, base.ErroIA)
            self.assertEqual(e.codigo, esperado)
            self.assertNotIn("sk-teste", str(e))

    def test_json_quebrado_e_filtro(self):
        e, _ = self._rodar([_ok('{"fala": ')])
        self.assertEqual(e.codigo, "vazio")
        e, _ = self._rodar([(200, b"nao e json", 0)])
        self.assertEqual(e.codigo, "vazio")
        e, _ = self._rodar([_ok("", finish="content_filter")])
        self.assertEqual(e.codigo, "recusou")

    def test_demora(self):
        e, _ = self._rodar([(200, {}, 2.5)], tempo=1)
        self.assertEqual(e.codigo, "demorou")

    def test_sem_conexao(self):
        e, _ = self._rodar([], url="http://127.0.0.1:9/v1")
        self.assertEqual(e.codigo, "sem_internet")

    def test_sem_chave(self):
        con = ConectorOpenAICompat({"url": "https://api.exemplo.com/v1",
                                    "chave": os.path.join(self.tmp.name, "nao")})
        self.assertFalse(con.chave_existe())
        with self.assertRaises(base.ErroIA) as c:
            con.dica("m", None, "S", "", "T", PNG, 5)
        self.assertEqual(c.exception.codigo, "sem_chave")
        local = ConectorOpenAICompat({"url": "http://127.0.0.1:11434/v1", "chave": "/nao/existe"})
        self.assertTrue(local.chave_existe())

    def test_esforco_da_chamada(self):
        r, srv = self._rodar([_ok('{"fala": "a", "onde": "b"}')])
        self.assertEqual(srv.pedidos[0]["corpo"]["reasoning_effort"], "low")
        r, srv = self._rodar([(400, {"error": {"message": "Unrecognized request argument: reasoning_effort"}}, 0),
                              _ok('{"fala": "a", "onde": "b"}')])
        self.assertEqual(r.fala, "a")
        self.assertNotIn("reasoning_effort", srv.pedidos[1]["corpo"])

    def test_busca_so_na_openai_por_padrao(self):
        self.assertTrue(ConectorOpenAICompat({"url": "https://api.openai.com/v1"}).tem_busca_web)
        self.assertFalse(ConectorOpenAICompat({"url": "https://openrouter.ai/api/v1"}).tem_busca_web)
        self.assertTrue(ConectorOpenAICompat({"url": "https://x.example/v1", "busca_web": True}).tem_busca_web)

    def test_ficha_com_busca_responses(self):
        texto = "RESUMO\nUm jogo ([wiki](https://w.example/a?utm_source=openai)). Veja [aqui](https://b.example).\n" + "z" * 300
        resposta = {"status": "completed", "output": [
            {"type": "reasoning"},
            {"type": "web_search_call", "status": "completed", "action": {"type": "search", "query": "q"}},
            {"type": "web_search_call", "status": "completed", "action": {"type": "open_page"}},
            {"type": "web_search_call", "status": "completed", "action": {"type": "search", "query": "q2"}},
            {"type": "message", "content": [{"type": "output_text", "text": texto, "annotations": [
                {"type": "url_citation", "url": "https://w.example/a?utm_source=openai", "title": "w"}]}]},
        ], "usage": {"input_tokens": 20000, "output_tokens": 3000}}
        srv = _Servidor([(200, resposta, 0)])
        try:
            con = ConectorOpenAICompat({"url": srv.url, "chave": self.chave, "busca_web": True})
            f = con.ficha("gpt-6.1-terra", "medium", "SIS", "Jogo: X.", True, 5, 10)
        finally:
            srv.fechar()
        p = srv.pedidos[0]
        self.assertEqual(p["path"], "/v1/responses")
        self.assertEqual(p["corpo"]["tools"], [{"type": "web_search"}])
        self.assertEqual(p["corpo"]["reasoning"], {"effort": "medium"})
        self.assertIn("at most 5 web searches", p["corpo"]["instructions"])
        self.assertTrue(f.com_pesquisa)
        self.assertEqual(f.buscas, 2)
        self.assertEqual(f.fontes, ["https://w.example/a"])
        self.assertTrue(f.texto.startswith("RESUMO\nUm jogo. Veja aqui.\n"), f.texto[:60])
        self.assertAlmostEqual(f.custo_usd, 0.02 + 0.015 + 0.02, places=4)

    def test_ficha_sem_pesquisa(self):
        srv = _Servidor([_ok("RESUMO\n" + "y" * 300)])
        try:
            con = ConectorOpenAICompat({"url": srv.url, "chave": self.chave})
            f = con.ficha("gpt-x", None, "SIS", "Jogo: X.", True, 8, 5)
        finally:
            srv.fechar()
        self.assertFalse(f.com_pesquisa)
        self.assertNotIn("response_format", srv.pedidos[0]["corpo"])


if __name__ == "__main__":
    unittest.main()
