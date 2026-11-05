#!/bin/bash
# Desinstala o Copiloto da Mei. Mantém as chaves e a config (~/.config/mei-copiloto),
# as dicas e as fichas (/roms/totobox/dicas e guias) e os backups do RetroArch.
#
# Uso: device/uninstall.sh [--conferir]
set -uo pipefail

SRC="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
APP="$HOME/.local/share/mei-copiloto"
CONFERIR=0; [ "${1:-}" = "--conferir" ] && CONFERIR=1
faz() { if [ "$CONFERIR" = 1 ]; then echo "   [conferir] $*"; else echo "   $*"; eval "$@"; fi; }

if [ "$CONFERIR" = 0 ] && pgrep -f '/usr/local/bin/retroarch|/opt/retroarch/bin/' >/dev/null; then
  echo "o RetroArch está aberto: feche o jogo antes"; exit 1
fi

echo "== 1. configs do RetroArch: as 6 chaves voltam ao valor do backup"
PATCH="$SRC/device/retroarch-patch.py"; [ -f "$PATCH" ] || PATCH="$APP/retroarch-patch.py"
if [ "$CONFERIR" = 1 ]; then echo "   [conferir] python3 -I $PATCH desfazer"; else python3 -I "$PATCH" desfazer; fi

echo "== 2. serviço"
faz "sudo -n systemctl disable --now mei-copiloto.service 2>/dev/null || true"
faz "sudo -n rm -f /etc/systemd/system/mei-copiloto.service"

echo "== 3. regra da porta 55355"
faz "sudo -n systemctl disable --now mei-copiloto-porta.service 2>/dev/null || true"
faz "sudo -n /usr/sbin/nft delete table inet mei_copiloto 2>/dev/null || true"
faz "sudo -n rm -f /etc/systemd/system/mei-copiloto-porta.service /etc/mei-copiloto-porta.nft"
faz "sudo -n systemctl daemon-reload"

echo "== 4. app"
faz "rm -rf '$APP'"

echo "== pronto. Ficaram: ~/.config/mei-copiloto (chaves e config), /roms/totobox/dicas e guias, retroarch.cfg.antes-copiloto"
