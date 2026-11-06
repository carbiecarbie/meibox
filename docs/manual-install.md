# Manual install and advanced options

*[Leia em português](instalacao-manual.md)*

For most people, the [easy SD-card install](../README.en.md#install) is enough. This guide is for people who prefer the terminal, want a different AI, or are working on the code. Everything here runs over SSH as the user `ark`. To use it, turn on **Options › Enable Remote Services** and find the IP in **Options › Network Info**.

## The card installer, over SSH

The installer from the menu also runs in text mode. Copy the `tools` and `totobox` folders from the ZIP to `/roms`, then run:

```bash
bash /roms/totobox/instalador/instalar.sh --conferir
```

```bash
bash /roms/totobox/instalador/instalar.sh
```

Options:

| Option | What it does |
|---|---|
| `--lingua en` | Shows the messages and Meibox in English. |
| `--sem-boot` | Does not open Meibox at boot. |
| `--sem-copiloto` | Skips the copilot, even when there is a key. |
| `--sem-desempenho` | Skips the emulator swap and per-game overrides (the "faster games" part). |
| `--remover` | Removes both programs. |
| `--apagar-chave` | With `--remover`, also erases the stored key. |

## Meibox only

Copy the repository's `meibox/` folder to the device, for example to `/tmp/meibox`, and run:

```bash
bash /tmp/meibox/device/install.sh --boot
```

Without `--boot`, Meibox is only in the Options menu. To uninstall:

```bash
bash ~/.local/share/totobox/device/uninstall.sh
```

Other options:
- To stop Meibox opening at boot, create the file `/roms/totobox/nao-abrir-ao-ligar`. You can do this from a PC, on the card.
- To use Meibox's picture while games load, replace `/roms/launchimages/loading.jpg` with `meibox/assets/meibox/loading-meibox.jpg`.

## Copilot only

Copy the `copiloto/` folder to the device, for example to `/tmp/copiloto`. Check what it would change, then install:

```bash
bash /tmp/copiloto/device/install.sh --conferir
```

```bash
bash /tmp/copiloto/device/install.sh
```

| Option | What it does |
|---|---|
| `--sem-porta` | Skips the rule that closes port 55355. |
| `--sem-retroarch` | Leaves the RetroArch configs alone. |
| `--com-sdk` | Installs the Anthropic SDK, which only Claude needs (about 47 MB). |

The installer refuses to run while a game is open. It also writes nothing if a hotkey or core override already uses R1. To uninstall:

```bash
bash ~/.local/share/mei-copiloto/device/uninstall.sh
```

## Key and model, by hand

**The key.** Run this on your computer. It asks for the key without showing it, saves it with mode 600, and never writes it to the log:

```bash
ssh -t ark@<device-ip> 'umask 077; mkdir -p ~/.config/mei-copiloto/chaves && read -rsp Key: K && printf %s "$K" > ~/.config/mei-copiloto/chaves/openai && unset K && echo && echo saved'
```

Use `chaves/openai` for OpenAI or any compatible service, and `chaves/anthropic` for Claude.

**The model.** Edit `~/.config/mei-copiloto/config.json` and fill in `dicas` (hints) and `ficha` (game guide).

OpenAI, the installer's default:
```json
"dicas": {"fornecedor": "openai_compat", "modelo": "gpt-6.1-terra", "esforco": "low"},
"ficha": {"fornecedor": "openai_compat", "modelo": "gpt-6.1-terra", "esforco": "medium", "busca_web": true, "max_buscas": 5},
```

Claude (needs `--com-sdk`):
```json
"dicas": {"fornecedor": "anthropic", "modelo": "claude-haiku-5-5", "esforco": "low"},
"ficha": {"fornecedor": "anthropic", "modelo": "claude-sonnet-5-5", "esforco": "medium", "busca_web": true, "max_buscas": 5},
```

**Other OpenAI-compatible services:** OpenRouter, Gemini's compatible endpoint, or a local Ollama or llama.cpp server.
- Set `fornecedores.openai_compat.url` and pick a model that accepts images.
- Web search only works on `api.openai.com`. Elsewhere, the game guide is written from the model's own knowledge and marked "written without research".

After changing the config, restart the service:

```bash
sudo systemctl restart mei-copiloto
```

Other config keys:

| Key | What it does |
|---|---|
| `limite_por_dia` | Maximum hints per day (default 200). |
| `fichas_por_dia` | Maximum game guides per day (default 10). |
| `idioma` | `"pt"` or `"en"`. With `"auto"`, it follows Meibox's settings. |
| `salvar_dicas` | Turns the hint pictures in `/roms/totobox/dicas` on or off. |

## Development

Tests run on a PC, with no SDL and no network:

```bash
cd meibox && python -m unittest discover -s tests
```

```bash
cd copiloto && python -m unittest discover -s tests
```

```bash
cd instalador && python -m unittest discover -s tests
```

- `copiloto/scripts/deploy.py` copies the copilot to `/tmp` on a device: `R36S_HOST=ark@<ip> python scripts/deploy.py`.
- The release ZIP is built by `instalador/scripts/montar_zip.py`.
