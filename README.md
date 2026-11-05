# Meibox

*[Leia em português](README.pt-BR.md)*

A cozy home screen and an in-game AI helper for the **R36S** handheld (and clones running ArkOS / dArkOS), starring **Mei**, a real black-and-white cat.

The repository has two parts that work on their own or together:

| Folder | What it is |
|---|---|
| [`meibox/`](meibox/) | **Meibox**, a game launcher that opens before EmulationStation. It has a welcome screen with "continue", a random pick by Mei, a fast library, your play stats ("Ficha") and settings in Portuguese or English. |
| [`copiloto/`](copiloto/) | **Copiloto da Mei**, an in-game hint helper. Press **SELECT + R1** in any RetroArch game: the game pauses and Mei's speech balloon tells you what to do right now, based on a screenshot. Press it again to keep playing. |

<p>
  <img src="docs/screenshots/meibox-inicio.png" width="320" alt="Meibox welcome screen">
  <img src="docs/screenshots/meibox-biblioteca.png" width="320" alt="Library">
  <img src="docs/screenshots/copiloto-megaman8.png" width="320" alt="Mei's hint over Mega Man 8">
  <img src="docs/screenshots/meibox-ajustes.png" width="320" alt="Meibox settings">
  <img src="docs/screenshots/meibox-nome.png" width="320" alt="Arcade-style name picker">
  <img src="docs/screenshots/meibox-ficha.png" width="320" alt="Play stats">
</p>

The code, comments and Mei's lines are mostly in Brazilian Portuguese. The interface and the hints also come in English.

## Requirements

- An R36S (RK3326) or similar handheld with **dArkOS / ArkOS**. Tested on dArkOSRE (Debian 13, Python 3.13, RetroArch 1.22.2).
- The SDL2, SDL2_image and SDL2_ttf libraries. They already ship with those systems.
- For the copilot: Wi-Fi with internet, and an API key from an AI provider (see [Choosing the AI](#choosing-the-ai)).
- SSH access to the device to install, for example with "Enable Remote Services".

## Meibox

### Install

Copy the `meibox/` folder to the device, for example to `/tmp/meibox`, and run as your normal user (`ark`):

```bash
bash /tmp/meibox/device/install.sh --boot
```

What the install does:
- installs the app to `~/.local/share/totobox` (the internal name is still *totobox*);
- adds **Meibox** to EmulationStation's *Options* menu;
- with `--boot`, also opens Meibox when the device is switched on. When you leave Meibox, EmulationStation starts as usual.

Ways to skip Meibox at boot:
- hold **B** while booting;
- or create the file `/roms/totobox/nao-abrir-ao-ligar`.

Optional: `meibox/assets/meibox/loading-meibox.jpg` can replace `/roms/launchimages/loading.jpg` as the game-loading picture.

### Use

- **Welcome screen:** left/right and A to pick a card, START for settings, SELECT for your stats, B to go back to EmulationStation.
- **Settings › What Mei calls you:** pick up to 12 letters, arcade style. Up/down change the letter, left/right move, A saves and B erases. Mei and the copilot then use this name.
- **Your own lines:** write them for Mei in `/roms/totobox/frases-pt.txt` (or `frases-en.txt`). The file explains the format.
- **Stats image:** START on the stats screen saves a picture to post, to `/roms/totobox/fichas/`. To add a footer to it, such as your site, write it on the first line of `/roms/totobox/rodape-ficha.txt`.

### Uninstall

```bash
bash ~/.local/share/totobox/device/uninstall.sh
```

Your lines and saved pictures in `/roms/totobox` stay.

## Copiloto da Mei (in-game hints)

RetroArch has a built-in **AI Service**. When you press the shortcut, it pauses the game and sends the screenshot to a URL. The copilot is a small Python service on `127.0.0.1:4404`. It sends the following to the AI provider you configured:
- the screenshot;
- the console and game name;
- the game guide, if one exists;
- the last few hints.

It draws Mei's balloon as a transparent PNG, and RetroArch shows it over the paused game.

- **Game guide:** the first time you ask for help in a game, Mei **researches that game on the web** (about 1 minute; RetroArch shows "Mei está estudando…"). She writes a plain-text guide to `/roms/totobox/guias/<Console>/<Game>.txt` with:
  - controls for that version;
  - levels;
  - the 5 places where players get stuck most;
  - bosses;
  - missable items;
  - secrets.

  Every later hint uses it. You can read and edit it from a PC; delete it to have it redone.
- **Journal:** a short log per game, so Mei doesn't repeat herself.
- **Saved hints:** each hint is also saved as an image (game screen + balloon) in `/roms/totobox/dicas/`, ready to post.
- **Limits:** 200 hints and 10 guides per day by default. A failed hint doesn't count.
- **Language and name:** they follow Meibox's settings when Meibox is installed. Otherwise Portuguese, or set `"idioma": "en"` in the config.

### Install

Copy the `copiloto/` folder to the device, for example to `/tmp/copiloto`. First look at what it would change, then install:

```bash
bash /tmp/copiloto/device/install.sh --conferir
```

```bash
bash /tmp/copiloto/device/install.sh
```

What it changes:
1. It installs the app to `~/.local/share/mei-copiloto` and the config to `~/.config/mei-copiloto/config.json`. An existing config is never overwritten.
2. It creates `/roms/totobox/dicas` and `/roms/totobox/guias`.
3. It adds an **nft rule** (service `mei-copiloto-porta`) that closes UDP port 55355 to the network. RetroArch's network commands, which show the "studying" notice, would otherwise listen on every interface. Skip this with `--sem-porta`.
4. It adds the **`mei-copiloto` service**, which starts at boot.
5. In **both** RetroArch configs (`retroarch` and `retroarch32`), it saves a backup as `retroarch.cfg.antes-copiloto` and changes 6 lines: `ai_service_enable`, `ai_service_url`, `ai_service_mode`, `ai_service_pause`, `input_ai_service_btn = "5"` (R1) and `network_cmd_enable`. Skip this with `--sem-retroarch`. It refuses to run while a game is open, and it stops without writing anything if any hotkey or core override already uses R1.

`--com-sdk` also installs the Anthropic Python SDK (about 47 MB). It is only needed for Claude.

### Choosing the AI

**No AI provider is set up by default.** Until you choose one, the balloon says so. You need to:
1. put your key on the device, and
2. pick the provider and model in the config.

**1. The key.** Run this from your computer. It asks for the key without showing it, saves it with permission 600, and never writes it to the log:

```bash
ssh -t ark@<device-ip> 'umask 077; mkdir -p ~/.config/mei-copiloto/chaves && read -rsp Key: K && printf %s "$K" > ~/.config/mei-copiloto/chaves/openai && unset K && echo && echo saved'
```

Use `chaves/openai` for OpenAI or any OpenAI-compatible service, and `chaves/anthropic` for Claude.

**2. The config.** Edit `~/.config/mei-copiloto/config.json` and fill in `dicas` (hints) and `ficha` (game guide):

OpenAI. This is what the author uses: better hints in testing, and no extra SDK.
```json
"dicas": {"fornecedor": "openai_compat", "modelo": "gpt-6.1-terra", "esforco": "low"},
"ficha": {"fornecedor": "openai_compat", "modelo": "gpt-6.1-terra", "esforco": "medium", "busca_web": true, "max_buscas": 5},
```

Claude. Install with `--com-sdk`.
```json
"dicas": {"fornecedor": "anthropic", "modelo": "claude-haiku-5-5", "esforco": "low"},
"ficha": {"fornecedor": "anthropic", "modelo": "claude-sonnet-5-5", "esforco": "medium", "busca_web": true, "max_buscas": 5},
```

Other OpenAI-compatible services (OpenRouter, Gemini's compatible endpoint, a local Ollama or llama.cpp server):
- set `fornecedores.openai_compat.url` and pick a model that accepts images;
- web search only works on `api.openai.com`, so elsewhere the guide is written from the model's own knowledge and marked "written without research".

Then restart the service:

```bash
sudo systemctl restart mei-copiloto
```

### Cost, speed and impact (measured on an R36S)

- **Hint speed:** with `gpt-6.1-terra`, a hint takes about 2.5–4 s from button to balloon and costs about US$ 0.003. With Claude Haiku 5.5 it takes about 2 s and costs about US$ 0.0005.
- **Guide cost:** a game guide with web search costs about US$ 0.06–0.08 with Terra, or US$ 0.2–0.3 with Claude Sonnet, **once per game**.
- **Memory:** about 30 MB while idle. With the Anthropic SDK, about 90 MB after the first hint.
- **Frame rate:** unchanged. Super Mario RPG ran at 76.6 vs 76.0 fps and Doom (SNES) at 79.1 vs 79.4, copilot off vs on, within measurement noise. The service does nothing while you play.
- **Privacy:** only the screenshot, the game and console names, your chosen name and that game's guide and journal go to the provider. The service listens only on `127.0.0.1`.

### Uninstall

```bash
bash ~/.local/share/mei-copiloto/device/uninstall.sh
```

What it does:
- puts back only those 6 RetroArch lines, from the backup;
- removes both services and the nft rule;
- deletes the app.

It keeps your keys, your config, your hints and your guides.

### Development

Tests run on a PC, with no SDL and no network:

```bash
cd copiloto && python -m unittest discover -s tests
```

```bash
cd meibox && python -m unittest discover -s tests
```

`copiloto/scripts/deploy.py` copies the copilot to `/tmp` on a device: `R36S_HOST=ark@<ip> python scripts/deploy.py`.

## Credits

- **Mei** is the author's cat. All the photos are of her.
- Fonts: [Baloo 2](https://fonts.google.com/specimen/Baloo+2) and [Nunito](https://fonts.google.com/specimen/Nunito), SIL Open Font License 1.1.
- Interface sounds are synthesized by the code; there are no third-party audio files.

## License

[MIT](LICENSE). The fonts keep their own OFL license.
