#!/bin/bash
# Roda um comando com o EmulationStation parado e sempre o religa no fim.
# Recusa se houver um jogo aberto.
if pgrep -f '^/opt/retroarch/bin/' >/dev/null; then
  echo "jogo aberto; nada foi feito" >&2; exit 3
fi
restore() {
  sudo -n systemctl start emulationstation
  sleep 3
  [ -f /home/ark/.local/share/r36s-perf/state/backlight-off ] && echo 0 > /sys/class/backlight/backlight/brightness
}
trap restore EXIT
sudo -n systemctl stop emulationstation
sleep 2
"$@"
