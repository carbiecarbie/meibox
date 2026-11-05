#!/bin/bash
# Installs Meibox (internal folder name: totobox) on the R36S, from the folder this script is in
# (or from STAGE=<folder>). Run it as your normal user (ark on ArkOS/dArkOS).
#   install.sh [--boot]   --boot also makes Totobox open when the device is switched on.
# Undo everything with: ~/.local/share/totobox/device/uninstall.sh
set -eu
STAGE="${STAGE:-$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)}"
APP="$HOME/.local/share/totobox"
DROPIN_DIR=/etc/systemd/system/emulationstation.service.d
DROPIN="$DROPIN_DIR/10-totobox.conf"

mkdir -p "$APP"
for d in totobox assets lang frases device; do
  rm -rf "${APP:?}/$d"
  cp -r "$STAGE/$d" "$APP/$d"
done
find "$APP/device" -name '*.sh' -exec sed -i 's/\r$//' {} + -exec chmod 755 {} +
mkdir -p "$APP/data" "$APP/cache" "$APP/state" /roms/totobox/fichas

# The user's own lines start as a commented example next to the games, easy to edit from a PC.
if [[ ! -e /roms/totobox/frases-pt.txt ]]; then
  printf '%s\n' "# Suas frases da Mei. Uma por linha: tipo: texto" \
    "# Tipos: lembrete saudade madrugada manha tarde noite calor ficha piada sorteio" \
    "# Buracos: {jogo} {console} {dias} {hora} {temp} {horas} {jogo_top}" \
    "# piada: Escreva aqui a sua e tire o # da frente." > /roms/totobox/frases-pt.txt
fi

# Menu entry (replaces the old Totobox ones)
printf '%s\n' '#!/bin/bash' "exec /bin/bash $APP/device/launcher.sh \"\$@\"" | sudo -n tee "/opt/system/Meibox.sh" >/dev/null
sudo -n chown ark:ark /opt/system/Meibox.sh
sudo -n chmod 755 /opt/system/Meibox.sh
sudo -n rm -f /opt/system/Totobox.sh "/opt/system/Totobox (teste).sh"   # old names

if [[ "${1:-}" == "--boot" ]]; then
  sudo -n mkdir -p "$DROPIN_DIR"
  printf '%s\n' "# Meibox opens before EmulationStation, once per boot. Remove this file to undo." \
    "[Service]" "ExecStartPre=-/bin/bash $APP/device/boot.sh" "TimeoutStartSec=0" | sudo -n tee "$DROPIN" >/dev/null
  sudo -n systemctl daemon-reload
  sudo -n touch /run/totobox-booted   # not now: only from the next boot on
fi
echo "installed in $APP"
