# SD-card installer

This builds the release ZIP. With it, people install Meibox and the Mei Copilot without SSH, Wi-Fi or a terminal. They copy two folders to the SD card and pick **Options › Tools › Instalar Meibox** on the device.

| Path | What it is |
|---|---|
| `cartao/tools/Instalar Meibox.sh` | The menu item. On ArkOS/dArkOS, `/roms/tools` is the same folder as `/opt/system/Tools` (bind mount), so any script copied there shows up in Options › Tools. |
| `cartao/totobox/instalador/abrir.sh` | Opens the installer on the device screen. It runs as `ark` on `tty1` with `gptokeyb`, the same pattern as the diagnostics tool. |
| `cartao/totobox/instalador/instalar.sh` | The installer, with dialog screens or plain text. Run `--help`-style options are listed at the top of the file. It calls `meibox/device/install.sh` and `copiloto/device/install.sh` from the payload. |
| `cartao/totobox/instalador/chave.py` | Reads the optional API key from `totobox/chave-da-ia.txt` and stores it in `~/.config/mei-copiloto/chaves/` with mode 600. It sets the copilot's provider and model, then puts the template back on the card. It never prints the key. |
| `cartao/totobox/chave-da-ia.txt` | The template people paste their key into. |
| `zip/` | `LEIA-ME.txt` / `READ-ME.txt` for people, and `PARA-SUA-IA.md` with step-by-step instructions for an AI assistant installing over SSH. |
| `scripts/montar_zip.py` | Builds `dist/Meibox-<version>.zip`. The payload is taken from this repository's `meibox/` and `copiloto/`, without tests. |

The version is the `VERSAO=` line in `instalar.sh`.

```bash
python -m unittest discover -s tests
```

```bash
python scripts/montar_zip.py
```

The same `instalar.sh` also works over SSH, with flags instead of screens:

```bash
bash /roms/totobox/instalador/instalar.sh --conferir
```
