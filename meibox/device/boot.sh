#!/bin/bash
# Opens Totobox once per boot, BEFORE EmulationStation starts (ExecStartPre of ES's service,
# via /etc/systemd/system/emulationstation.service.d/10-totobox.conf). When Totobox exits
# ("Voltar ao EmulationStation"), ES starts as usual. Any failure here also lets ES start.
#
# Skipped (ES starts directly) when:
#   - Totobox already ran since this boot (ES restarts do not bring it back);
#   - B is held during boot (keeps the system's BaRT recovery menu reachable);
#   - the file /roms/totobox/nao-abrir-ao-ligar exists (switch it off from a PC).
APP="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
# /run is emptied only at boot; the file is root-owned so logind's IPC cleanup (which empties
# /dev/shm files of a user whose last session ends) cannot remove it.
MARK=/run/totobox-booted
[[ -e "$MARK" ]] && exit 0
sudo -n touch "$MARK"
[[ -e /roms/totobox/nao-abrir-ao-ligar ]] && exit 0
if [[ -r /usr/local/bin/buttonmon.sh ]]; then
  . /usr/local/bin/buttonmon.sh
  Test_Button_B
  [[ "$?" -eq 10 ]] && exit 0
fi
mkdir -p "$APP/state"
exec >"$APP/state/boot.log" 2>&1
printf '%s boot launch\n' "$(date -Is)"
sudo -n chmod 666 /dev/tty1   # what ES's own start script does
export TERM=linux SDL_VIDEO_EGL_DRIVER=libEGL.so TOTOBOX_T0="$(date +%s.%N)"
export XDG_RUNTIME_DIR=/run/user/1000
if [[ ! -d "$XDG_RUNTIME_DIR" || ! -w "$XDG_RUNTIME_DIR" ]]; then
  mkdir -p "$APP/state/runtime"; export XDG_RUNTIME_DIR="$APP/state/runtime"
fi
python3 "$APP/totobox/main.py" --home "$APP" --report "$APP/state/boot-report.json"
printf '%s exit %s\n' "$(date -Is)" "$?"
exit 0
