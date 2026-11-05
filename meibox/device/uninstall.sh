#!/bin/bash
# Removes Totobox: boot hook, menu entry and app folder. Keeps /roms/totobox (your phrases and
# saved Ficha images) and the loading image backup in /roms/launchimages.
set -u
sudo -n rm -f /etc/systemd/system/emulationstation.service.d/10-totobox.conf
sudo -n rmdir /etc/systemd/system/emulationstation.service.d 2>/dev/null
sudo -n systemctl daemon-reload
sudo -n rm -f /opt/system/Meibox.sh /opt/system/Totobox.sh "/opt/system/Totobox (teste).sh"
rm -rf "$HOME/.local/share/totobox"
echo "Meibox removed. Loading image: rename /roms/launchimages/loading-original.jpg back to loading.jpg if you want the old one."
