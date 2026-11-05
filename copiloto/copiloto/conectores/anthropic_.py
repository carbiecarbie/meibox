"""Conector Claude pelo SDK oficial `anthropic` (carregado só quando este fornecedor é usado).

Dica: saída estruturada {fala, onde}, effort da config, prazo total com 1 nova tentativa.
Ficha: ferramenta de servidor web_search, prazo total (padrão 90 s), retoma pause_turn.
"""
import os
import sys
import time

from .. import prompts
from . import base

# US$ por milhão de tokens (entrada, saída); tabela de 06/10/2026. Só para o log.
PRECOS = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
PRECO_BUSCA = 10.0 / 1000          # US$ 10 por 1.000 buscas
MIN_PARA_TENTAR_DE_NOVO = 3.0      # segundos que precisam sobrar para a 2ª tentativa
BETA_FALLBACK = "server-side-fallback-2026-07-01"


def custo(modelo, entrada, saida, buscas=0):
    p_in, p_out = PRECOS.get(modelo, (0.0, 0.0))
    return entrada / 1e6 * p_in + saida / 1e6 * p_out + buscas * PRECO_BUSCA


class ConectorAnthropic:
    nome = "anthropic"
    tem_busca_web = True

    def __init__(self, fornecedor, pasta_vendor=None, sdk=None):
        self.caminho_chave = fornecedor["chave"]
        self.pasta_vendor = pasta_vendor
        self.sdk = sdk
        self._cliente = None
        self._chave_do_cliente = None

    # ---- SDK e cliente
    def carregar(self):
        """Importa o SDK (12-15 s no aparelho). Chamado na partida ou no primeiro uso."""
        if self.sdk is None:
            if self.pasta_vendor and os.path.isdir(self.pasta_vendor) and self.pasta_vendor not in sys.path:
                sys.path.insert(0, self.pasta_vendor)
            import anthropic
            self.sdk = anthropic
        return self.sdk

    def chave_existe(self):
        try:
            base.ler_chave(self.caminho_chave)
            return True
        except base.ErroIA:
            return False

    def _cliente_atual(self):
        sdk = self.carregar()
        chave = base.ler_chave(self.caminho_chave)
        if self._cliente is None or chave != self._chave_do_cliente:
            self._cliente = sdk.Anthropic(api_key=chave, max_retries=0)
            self._chave_do_cliente = chave
        return self._cliente

    def _traduzir(self, e):
        """Exceção do SDK -> ErroIA (código para a frase da Mei). Sem a chave no detalhe."""
        sdk = self.sdk
        if isinstance(e, sdk.APITimeoutError):
            return base.ErroIA(base.DEMOROU, "timeout")
        if isinstance(e, sdk.APIConnectionError):
            return base.ErroIA(base.SEM_INTERNET, type(e.__cause__ or e).__name__)
        if isinstance(e, (sdk.AuthenticationError, sdk.PermissionDeniedError)):
            return base.ErroIA(base.CHAVE_RECUSADA, f"http {e.status_code}")
        if isinstance(e, sdk.RateLimitError):
            return base.ErroIA(base.SEM_CREDITO, "http 429")
        if isinstance(e, sdk.APIStatusError):
            msg = str(getattr(e, "message", "") or "")
            if e.status_code == 402 or "credit" in msg.lower() or "billing" in msg.lower():
                return base.ErroIA(base.SEM_CREDITO, f"http {e.status_code}")
            if e.status_code >= 500:
                return base.ErroIA(base.SEM_CREDITO, f"http {e.status_code} (ocupada)")
            return base.ErroIA(f"http_{e.status_code}", msg[:200])
        return base.ErroIA(type(e).__name__, str(e)[:200])

    def _chamar(self, prazo, fazer):
        """Roda `fazer(timeout)` até o prazo, com 1 nova tentativa para falha de rede ou 5xx."""
        tentativas = 0
        while True:
            restante = prazo - time.monotonic()
            if restante <= 0.5:
                raise base.ErroIA(base.DEMOROU, "prazo acabou")
            tentativas += 1
            try:
                return fazer(restante), tentativas
            except base.ErroIA:
                raise
            except Exception as e:  # noqa: BLE001 - traduzido abaixo
                if self.sdk is None or not isinstance(e, self.sdk.APIError):
                    raise
                erro = self._traduzir(e)
                transitorio = isinstance(e, self.sdk.APIConnectionError) and erro.codigo != base.DEMOROU
                transitorio |= isinstance(e, self.sdk.APIStatusError) and e.status_code >= 500
                if (tentativas >= 2 or not transitorio
                        or prazo - time.monotonic() < MIN_PARA_TENTAR_DE_NOVO):
                    raise erro from None

    # ---- dica
    def dica(self, modelo, esforco, sistema, ficha, texto, imagem_png, tempo_max):
        import base64
        cliente = self._cliente_atual()
        blocos_sistema = [{"type": "text", "text": sistema}]
        if ficha:
            blocos_sistema.append({"type": "text", "text": ficha, "cache_control": {"type": "ephemeral"}})
        conteudo = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.standard_b64encode(imagem_png).decode()}},
            {"type": "text", "text": texto},
        ]
        output_config = {"format": {"type": "json_schema", "schema": prompts.ESQUEMA_DICA}}
        if esforco:
            output_config["effort"] = esforco

        def fazer(timeout):
            return cliente.with_options(timeout=timeout).messages.create(
                model=modelo, max_tokens=2048, system=blocos_sistema,
                output_config=output_config,
                messages=[{"role": "user", "content": conteudo}],
            )

        r, tentativas = self._chamar(time.monotonic() + tempo_max, fazer)
        if r.stop_reason == "refusal":
            raise base.ErroIA(base.RECUSOU, str(getattr(r, "stop_details", "") or "")[:120])
        if r.stop_reason == "max_tokens":
            raise base.ErroIA(base.VAZIO, "max_tokens")
        texto_resp = "".join(b.text for b in r.content if b.type == "text")
        fala, onde = base.interpretar_json(texto_resp)
        u = r.usage
        return base.RespostaDica(
            fala=fala, onde=onde,
            tokens_entrada=(u.input_tokens or 0) + (u.cache_read_input_tokens or 0)
            + (u.cache_creation_input_tokens or 0),
            tokens_saida=u.output_tokens or 0,
            tokens_cache=u.cache_read_input_tokens or 0,
            tentativas=tentativas,
        )

    # ---- ficha
    def ficha(self, modelo, esforco, sistema, pedido, busca_web, max_buscas, tempo_max):
        cliente = self._cliente_atual()
        prazo = time.monotonic() + tempo_max
        ferramentas = ([{"type": "web_search_20260209", "name": "web_search", "max_uses": max_buscas}]
                       if busca_web else [])
        mensagens = [{"role": "user", "content": pedido}]
        extra = {"tools": ferramentas} if ferramentas else {}
        if esforco:
            extra["output_config"] = {"effort": esforco}
        blocos, entrada, saida, buscas, modelo_usado = [], 0, 0, 0, modelo

        for _ in range(4):  # 1 pedido + até 3 retomadas de pause_turn
            def fazer(timeout):
                return cliente.with_options(timeout=timeout).beta.messages.create(
                    model=modelo, max_tokens=16000, system=sistema, messages=mensagens,
                    betas=[BETA_FALLBACK], fallbacks="default", **extra)

            r, _t = self._chamar(prazo, fazer)
            u = r.usage
            entrada += (u.input_tokens or 0) + (u.cache_read_input_tokens or 0) \
                + (u.cache_creation_input_tokens or 0)
            saida += u.output_tokens or 0
            stu = getattr(u, "server_tool_use", None)
            buscas += (getattr(stu, "web_search_requests", 0) or 0) if stu else 0
            modelo_usado = getattr(r, "model", modelo) or modelo
            blocos.extend(r.content)
            if r.stop_reason == "refusal":
                raise base.ErroIA(base.RECUSOU, "ficha recusada")
            if r.stop_reason != "pause_turn":
                break
            mensagens = [mensagens[0], {"role": "assistant", "content": r.content}]

        texto, fontes = _texto_final(blocos)
        if len(texto) < 200:
            raise base.ErroIA(base.VAZIO, f"ficha curta demais ({len(texto)} letras)")
        return base.RespostaFicha(
            texto=texto, com_pesquisa=bool(busca_web and buscas), buscas=buscas,
            tokens_entrada=entrada, tokens_saida=saida,
            custo_usd=custo(modelo_usado, entrada, saida, buscas), fontes=fontes,
        )


def _texto_final(blocos):
    """Texto depois da última ferramenta (descarta frases soltas entre buscas) + URLs citadas."""
    partes, fontes = [], []
    for b in blocos:
        tipo = getattr(b, "type", "")
        if tipo == "text":
            partes.append(b.text)
            for c in getattr(b, "citations", None) or []:
                url = getattr(c, "url", None)
                if url and url not in fontes:
                    fontes.append(url)
        elif tipo.endswith("tool_use") or tipo.endswith("tool_result"):
            partes = []
    return "".join(partes).strip(), fontes
