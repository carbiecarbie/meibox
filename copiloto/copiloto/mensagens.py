"""Frases da Mei para erros e avisos (design 5.6 e 12.5), em português e inglês.

Sem emojis: a fonte do balão (Nunito) não tem esses desenhos.
"""

FRASES = {
    "pt": {
        "sem_internet": "Tô sem internet. Confere o Wi-Fi.",
        "nao_configurado": "A IA ainda não foi configurada. Veja no README como escolher uma e pôr a chave.",
        "sem_chave": "Falta a chave da IA. Ela vai em ~/.config/mei-copiloto/chaves/.",
        "chave_recusada": "A chave da IA não funcionou.",
        "limite_dia": "Já dei {limite} dicas hoje! Amanhã tem mais.",
        "demorou": "A IA demorou demais. Tenta de novo?",
        "sem_credito": "A conta da IA está sem crédito ou ocupada.",
        "recusou": "Não consegui ver nada nessa tela. Tenta em outro momento?",
        "vazio": "Não consegui ver nada nessa tela. Tenta em outro momento?",
        "ocupado": "Calma, ainda tô pensando!",
        "outro": "Deu ruim aqui ({codigo}).",
        "estudando_aviso": "Mei está estudando {jogo}... (até 1 min)",
        "acordando_aviso": "Mei está acordando... (uns 15 s)",
        "estudando_balao": "Tô estudando {jogo} pela primeira vez! Volta a jogar e me chama de novo em 1 minutinho.",
        "ainda_estudando": "Ainda tô estudando {jogo}. Me chama de novo daqui a pouco!",
        "ficha_falhou": "Não consegui pesquisar {jogo} agora, mas vamos lá:",
        "rodape": "SELECT + R1 para voltar ao jogo",
    },
    "en": {
        "sem_internet": "I'm offline. Check the Wi-Fi.",
        "nao_configurado": "No AI is set up yet. The README shows how to pick one and add its key.",
        "sem_chave": "The AI key is missing. It goes in ~/.config/mei-copiloto/chaves/.",
        "chave_recusada": "The AI key didn't work.",
        "limite_dia": "That's {limite} tips today! More tomorrow.",
        "demorou": "The AI took too long. Try again?",
        "sem_credito": "The AI account is out of credit or busy.",
        "recusou": "I couldn't make out this screen. Try another moment?",
        "vazio": "I couldn't make out this screen. Try another moment?",
        "ocupado": "Hold on, I'm still thinking!",
        "outro": "Something broke here ({codigo}).",
        "estudando_aviso": "Mei is studying {jogo}... (up to 1 min)",
        "acordando_aviso": "Mei is waking up... (about 15 s)",
        "estudando_balao": "I'm studying {jogo} for the first time! Go play and call me again in a minute.",
        "ainda_estudando": "Still studying {jogo}. Call me again in a bit!",
        "ficha_falhou": "I couldn't research {jogo} right now, but here goes:",
        "rodape": "SELECT + R1 to go back to the game",
    },
}


def frase(chave, idioma="pt", **campos):
    """Frase da Mei para `chave`; chave desconhecida vira "Deu ruim aqui (chave)"."""
    tabela = FRASES.get(idioma, FRASES["pt"])
    texto = tabela.get(chave)
    if texto is None:
        texto = tabela["outro"]
        campos.setdefault("codigo", chave)
    campos.setdefault("codigo", "?")
    campos.setdefault("jogo", "o jogo" if idioma != "en" else "the game")
    return texto.format(**campos)
