# Instalação manual e opções avançadas

*[Read in English](manual-install.md)*

Para a maioria das pessoas, o [jeito fácil pelo cartão SD](../README.md#instalar) basta. Este guia é para quem prefere o terminal, quer outra IA ou vai mexer no código. Tudo aqui roda pelo SSH, com o usuário `ark`. Para isso, ligue **Options › Enable Remote Services** e veja o IP em **Options › Network Info**.

## Instalador do cartão, pelo SSH

O mesmo instalador do menu roda em modo texto. Copie as pastas `tools` e `totobox` do ZIP para `/roms` e rode:

```bash
bash /roms/totobox/instalador/instalar.sh --conferir
```

```bash
bash /roms/totobox/instalador/instalar.sh
```

Opções:

| Opção | O que faz |
|---|---|
| `--lingua en` | Põe as mensagens e o Meibox em inglês. |
| `--sem-boot` | Não abre o Meibox quando o aparelho liga. |
| `--sem-copiloto` | Não instala o copiloto, mesmo havendo uma chave. |
| `--sem-desempenho` | Não troca os emuladores nem cria os ajustes de jogo (os "jogos mais rápidos"). |
| `--remover` | Remove os dois programas. |
| `--apagar-chave` | Junto com `--remover`, apaga também a chave guardada. |

## Meibox, só ele

Copie a pasta `meibox/` do repositório para o aparelho, por exemplo para `/tmp/meibox`, e rode:

```bash
bash /tmp/meibox/device/install.sh --boot
```

Sem `--boot`, o Meibox fica só no menu Options. Para desinstalar:

```bash
bash ~/.local/share/totobox/device/uninstall.sh
```

Outras opções:
- Para o Meibox não abrir ao ligar, crie o arquivo `/roms/totobox/nao-abrir-ao-ligar`. Dá para fazer isso pelo PC, no cartão.
- Para usar a imagem do Meibox no carregamento dos jogos, troque `/roms/launchimages/loading.jpg` por `meibox/assets/meibox/loading-meibox.jpg`.

## Copiloto, só ele

Copie a pasta `copiloto/` para o aparelho, por exemplo para `/tmp/copiloto`. Confira o que ele mudaria e depois instale:

```bash
bash /tmp/copiloto/device/install.sh --conferir
```

```bash
bash /tmp/copiloto/device/install.sh
```

| Opção | O que faz |
|---|---|
| `--sem-porta` | Não cria a regra que fecha a porta 55355. |
| `--sem-retroarch` | Não mexe nas configs do RetroArch. |
| `--com-sdk` | Instala o SDK da Anthropic, que só o Claude usa (cerca de 47 MB). |

A instalação recusa rodar com um jogo aberto. Ela também não grava nada se algum atalho ou override de núcleo já usar o R1. Para desinstalar:

```bash
bash ~/.local/share/mei-copiloto/device/uninstall.sh
```

## Chave e modelo, à mão

**A chave.** Rode este comando no seu computador. Ele pede a chave sem mostrar na tela, grava com permissão 600 e nunca registra a chave no log:

```bash
ssh -t ark@<ip-do-aparelho> 'umask 077; mkdir -p ~/.config/mei-copiloto/chaves && read -rsp Chave: K && printf %s "$K" > ~/.config/mei-copiloto/chaves/openai && unset K && echo && echo ok'
```

Use `chaves/openai` para a OpenAI ou qualquer serviço compatível, e `chaves/anthropic` para o Claude.

**O modelo.** Edite `~/.config/mei-copiloto/config.json` e preencha `dicas` e `ficha`.

OpenAI, o padrão do instalador:
```json
"dicas": {"fornecedor": "openai_compat", "modelo": "gpt-6.1-terra", "esforco": "low"},
"ficha": {"fornecedor": "openai_compat", "modelo": "gpt-6.1-terra", "esforco": "medium", "busca_web": true, "max_buscas": 5},
```

Claude (precisa do `--com-sdk`):
```json
"dicas": {"fornecedor": "anthropic", "modelo": "claude-haiku-5-5", "esforco": "low"},
"ficha": {"fornecedor": "anthropic", "modelo": "claude-sonnet-5-5", "esforco": "medium", "busca_web": true, "max_buscas": 5},
```

**Outros serviços compatíveis com a OpenAI:** OpenRouter, o endereço compatível do Gemini, ou um servidor local Ollama ou llama.cpp.
- Ajuste `fornecedores.openai_compat.url` e escolha um modelo que aceite imagem.
- A busca na web só funciona na `api.openai.com`. Nos outros serviços, a ficha do jogo sai só com o que o modelo já sabe, marcada "feita sem pesquisa".

Depois de mudar a config, reinicie o serviço:

```bash
sudo systemctl restart mei-copiloto
```

Outras chaves da config:

| Chave | O que faz |
|---|---|
| `limite_por_dia` | Máximo de dicas por dia (padrão 200). |
| `fichas_por_dia` | Máximo de fichas por dia (padrão 10). |
| `idioma` | `"pt"` ou `"en"`. Com `"auto"`, segue os Ajustes do Meibox. |
| `salvar_dicas` | Liga ou desliga as imagens em `/roms/totobox/dicas`. |

## Desenvolvimento

Os testes rodam no PC, sem SDL e sem rede:

```bash
cd meibox && python -m unittest discover -s tests
```

```bash
cd copiloto && python -m unittest discover -s tests
```

```bash
cd instalador && python -m unittest discover -s tests
```

- `copiloto/scripts/deploy.py` copia o copiloto para o `/tmp` de um aparelho: `R36S_HOST=ark@<ip> python scripts/deploy.py`.
- O ZIP da release é montado por `instalador/scripts/montar_zip.py`.
