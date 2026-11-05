"""Conector "chat completions" com imagem (OpenAI, Gemini compatível, OpenRouter, Ollama...).

HTTP puro (urllib), sem biblioteca extra.
- Dica: POST {url}/chat/completions, imagem em data URI, JSON pedido na instrução e
  response_format quando o serviço aceitar. O esforço da config vai em `reasoning_effort`.
- Ficha: com busca web, POST {url}/responses com a ferramenta `web_search` (API Responses da
  OpenAI). Sem busca, chat completions comum e a ficha sai "feita sem pesquisa".
Config do fornecedor: {"url": ".../v1", "chave": "<arquivo>"}; opcionais:
  "json_mode" (padrão true), "busca_web" (padrão: true só para api.openai.com),
  "reasoning_effort" (usado quando a chamada não traz esforço).
Campos que o serviço recusar (response_format, max_tokens, reasoning_effort) são ajustados sozinhos.
"""
import base64
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from . import base

_LOCAIS = {"127.0.0.1", "localhost", "::1"}

# US$ por milhão de tokens (entrada, saída), página oficial em 05/11/2026. Só para o log.
PRECOS = {
    "gpt-6.1-terra": (1.00, 5.00),
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-sol": (2.00, 10.00),
    "gpt-6-astra": (10.00, 50.00),
}
PRECO_BUSCA = 10.0 / 1000

_CITACAO = re.compile(r"\s*\(\[[^\]]*\]\([^)]*\)\)")      # " ([site](url))"
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")    # "[texto](url)" -> "texto"


def limpar_citacoes(texto):
    """Tira as citações em Markdown que a busca da OpenAI põe no meio do texto."""
    return _LINK.sub(r"\1", _CITACAO.sub("", texto or ""))


class ConectorOpenAICompat:
    nome = "openai_compat"

    def __init__(self, fornecedor, abrir=urllib.request.urlopen):
        self.url = fornecedor.get("url", "").rstrip("/")
        self.caminho_chave = fornecedor.get("chave", "")
        self.json_mode = fornecedor.get("json_mode", True)
        self.reasoning_effort = fornecedor.get("reasoning_effort")
        self.tem_busca_web = bool(fornecedor.get(
            "busca_web", urllib.parse.urlparse(self.url).hostname == "api.openai.com"))
        self.campo_max = "max_tokens"
        self.aceita_esforco = True
        self.abrir = abrir

    def carregar(self):
        return None

    def _local(self):
        return urllib.parse.urlparse(self.url).hostname in _LOCAIS

    def chave_existe(self):
        if self._local():
            return True
        try:
            base.ler_chave(self.caminho_chave)
            return True
        except base.ErroIA:
            return False

    def _cabecalhos(self):
        h = {"Content-Type": "application/json"}
        try:
            h["Authorization"] = "Bearer " + base.ler_chave(self.caminho_chave)
        except base.ErroIA:
            if not self._local():
                raise
        return h

    def _post(self, caminho, corpo, prazo):
        """POST com até 3 ajustes automáticos para serviços que recusam um campo."""
        for _ in range(4):
            restante = prazo - time.monotonic()
            if restante <= 0.5:
                raise base.ErroIA(base.DEMOROU, "prazo acabou")
            req = urllib.request.Request(self.url + caminho, data=json.dumps(corpo).encode(),
                                         method="POST", headers=self._cabecalhos())
            try:
                with self.abrir(req, timeout=restante) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detalhe = e.read().decode("utf-8", "replace")[:400] if e.fp else ""
                baixo = detalhe.lower()
                if e.code == 400 and "response_format" in corpo and "response_format" in baixo:
                    corpo = {k: v for k, v in corpo.items() if k != "response_format"}
                    self.json_mode = False
                    continue
                if e.code == 400 and "max_tokens" in corpo and "max_completion_tokens" in baixo:
                    corpo = dict(corpo)
                    corpo["max_completion_tokens"] = corpo.pop("max_tokens")
                    self.campo_max = "max_completion_tokens"
                    continue
                if e.code == 400 and "reasoning_effort" in corpo and "reasoning" in baixo:
                    corpo = {k: v for k, v in corpo.items() if k != "reasoning_effort"}
                    self.aceita_esforco = False
                    continue
                raise self._erro_http(e.code, detalhe) from None
            except (TimeoutError, socket.timeout):
                raise base.ErroIA(base.DEMOROU, "timeout") from None
            except urllib.error.URLError as e:
                if isinstance(e.reason, (TimeoutError, socket.timeout)):
                    raise base.ErroIA(base.DEMOROU, "timeout") from None
                raise base.ErroIA(base.SEM_INTERNET, type(e.reason).__name__) from None
            except ValueError:
                raise base.ErroIA(base.VAZIO, "resposta não é JSON") from None
        raise base.ErroIA("http_400", "serviço recusou o pedido")

    @staticmethod
    def _erro_http(codigo, detalhe):
        if codigo in (401, 403):
            return base.ErroIA(base.CHAVE_RECUSADA, f"http {codigo}")
        if codigo in (402, 429) or codigo >= 500:
            return base.ErroIA(base.SEM_CREDITO, f"http {codigo}")
        return base.ErroIA(f"http_{codigo}", detalhe[:200])

    def _corpo(self, modelo, mensagens, max_tokens, json_mode, esforco):
        corpo = {"model": modelo, "messages": mensagens, self.campo_max: max_tokens}
        if json_mode and self.json_mode:
            corpo["response_format"] = {"type": "json_object"}
        esforco = esforco or self.reasoning_effort
        if esforco and self.aceita_esforco:
            corpo["reasoning_effort"] = esforco
        return corpo

    @staticmethod
    def _resposta(dados):
        try:
            escolha = dados["choices"][0]
        except (KeyError, IndexError, TypeError):
            raise base.ErroIA(base.VAZIO, "sem choices") from None
        if escolha.get("finish_reason") == "content_filter":
            raise base.ErroIA(base.RECUSOU, "content_filter")
        conteudo = (escolha.get("message") or {}).get("content") or ""
        if isinstance(conteudo, list):  # alguns serviços devolvem partes
            conteudo = "".join(p.get("text", "") for p in conteudo if isinstance(p, dict))
        u = dados.get("usage") or {}
        cache = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
        return conteudo, u.get("prompt_tokens", 0) or 0, u.get("completion_tokens", 0) or 0, cache

    def dica(self, modelo, esforco, sistema, ficha, texto, imagem_png, tempo_max):
        uri = "data:image/png;base64," + base64.standard_b64encode(imagem_png).decode()
        sistema_total = sistema + ("\n\n" + ficha if ficha else "")
        mensagens = [
            {"role": "system", "content": sistema_total},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": uri}},
                {"type": "text", "text": texto},
            ]},
        ]
        dados = self._post("/chat/completions", self._corpo(modelo, mensagens, 2048, True, esforco),
                           time.monotonic() + tempo_max)
        conteudo, entrada, saida, cache = self._resposta(dados)
        fala, onde = base.interpretar_json(conteudo)
        return base.RespostaDica(fala=fala, onde=onde, tokens_entrada=entrada, tokens_saida=saida,
                                 tokens_cache=cache)

    def ficha(self, modelo, esforco, sistema, pedido, busca_web, max_buscas, tempo_max):
        prazo = time.monotonic() + tempo_max
        if busca_web and self.tem_busca_web:
            return self._ficha_com_busca(modelo, esforco, sistema, pedido, max_buscas, prazo)
        mensagens = [{"role": "system", "content": sistema}, {"role": "user", "content": pedido}]
        dados = self._post("/chat/completions", self._corpo(modelo, mensagens, 4000, False, esforco), prazo)
        texto, entrada, saida, _ = self._resposta(dados)
        texto = texto.strip()
        if len(texto) < 200:
            raise base.ErroIA(base.VAZIO, f"ficha curta demais ({len(texto)} letras)")
        p_in, p_out = PRECOS.get(modelo, (0.0, 0.0))
        return base.RespostaFicha(texto=texto, com_pesquisa=False, tokens_entrada=entrada,
                                  tokens_saida=saida,
                                  custo_usd=entrada / 1e6 * p_in + saida / 1e6 * p_out)

    def _ficha_com_busca(self, modelo, esforco, sistema, pedido, max_buscas, prazo):
        """API Responses com a ferramenta web_search (não há limite de buscas na API: vai na instrução)."""
        corpo = {
            "model": modelo,
            "instructions": sistema + f"\nUse at most {max_buscas} web searches.",
            "input": pedido,
            "tools": [{"type": "web_search"}],
            "max_output_tokens": 16000,
        }
        esforco = esforco or self.reasoning_effort
        if esforco:
            corpo["reasoning"] = {"effort": esforco}
        dados = self._post("/responses", corpo, prazo)
        buscas, partes, fontes = 0, [], []
        for item in dados.get("output") or []:
            tipo = item.get("type")
            if tipo == "web_search_call":
                if ((item.get("action") or {}).get("type") or "search") == "search":
                    buscas += 1
            elif tipo == "message":
                partes = []  # fica com a última mensagem
                for c in item.get("content") or []:
                    if c.get("type") == "output_text":
                        partes.append(c.get("text") or "")
                        for a in c.get("annotations") or []:
                            url = a.get("url")
                            if a.get("type") == "url_citation" and url and url not in fontes:
                                fontes.append(url.split("?utm_source=")[0])
            elif tipo == "refusal":
                raise base.ErroIA(base.RECUSOU, "ficha recusada")
        texto = limpar_citacoes("".join(partes)).strip()
        if len(texto) < 200:
            raise base.ErroIA(base.VAZIO, f"ficha curta demais ({len(texto)} letras), "
                              f"status={dados.get('status')}")
        u = dados.get("usage") or {}
        entrada, saida = u.get("input_tokens", 0) or 0, u.get("output_tokens", 0) or 0
        p_in, p_out = PRECOS.get(modelo, (0.0, 0.0))
        return base.RespostaFicha(
            texto=texto, com_pesquisa=buscas > 0, buscas=buscas, tokens_entrada=entrada,
            tokens_saida=saida, fontes=fontes,
            custo_usd=entrada / 1e6 * p_in + saida / 1e6 * p_out + buscas * PRECO_BUSCA)
