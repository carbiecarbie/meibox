#!/bin/bash
# Plan B, run as root by systemd-run (outside ES's service, so stopping ES does not kill it).
# Stops ES, runs Totobox as ark, and always starts ES again.
APP="${1:-$HOME/.local/share/totobox}"
STATE="$APP/state"
LOG="$STATE/planb.log"
restore() { systemctl start emulationstation; printf '%s ES started again\n' "$(date -Is)" >> "$LOG"; }
trap restore EXIT
printf '%s plan B: stopping ES\n' "$(date -Is)" > "$LOG"
touch /run/totobox-booted   # ES's start hook must not open Totobox a second time
systemctl stop emulationstation
sleep 1
runuser -u ark -- env TERM=linux SDL_VIDEO_EGL_DRIVER=libEGL.so XDG_RUNTIME_DIR=/run/user/1000 \
  TOTOBOX_T0="$(date +%s.%N)" \
  python3 "$APP/totobox/main.py" --home "$APP" --report "$STATE/planb-report.json" 2>> "$LOG"
printf '%s plan B: Totobox exit %s\n' "$(date -Is)" "$?" >> "$LOG"
