#!/bin/bash
# Totobox, opened from EmulationStation's Options menu (/opt/system/Totobox.sh).
# Plan A: run right away (ES releases the screen when it runs a menu script; verified 04/11/2026).
# Plan B (approved by the user): if the screen is busy, a detached systemd unit stops ES,
# runs Totobox and always starts ES again.
set -u
APP="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$APP/state"
if [[ "$EUID" -eq 0 ]]; then
  exec runuser -u ark -- /bin/bash "${BASH_SOURCE[0]}" "$@"
fi
mkdir -p "$STATE"
exec 9>"$STATE/instance.lock"
flock -n 9 || exit 0
exec 2>"$STATE/last-launch.log"
printf '%s menu launch\n' "$(date -Is)" >&2
export TERM=linux SDL_VIDEO_EGL_DRIVER=libEGL.so TOTOBOX_T0="$(date +%s.%N)"
if [[ -z "${XDG_RUNTIME_DIR:-}" || ! -w "${XDG_RUNTIME_DIR:-/nonexistent}" ]]; then
  mkdir -p "$STATE/runtime"; export XDG_RUNTIME_DIR="$STATE/runtime"
fi
python3 "$APP/totobox/main.py" --home "$APP" --report "$STATE/last-report.json"
code=$?
printf '%s exit %s\n' "$(date -Is)" "$code" >&2
if [[ "$code" -eq 3 ]]; then
  printf '%s screen busy -> plan B\n' "$(date -Is)" >&2
  flock -u 9
  sudo -n systemd-run --unit="totobox-planb-$(date +%s)" --collect /bin/bash "$APP/device/planb.sh" "$APP" >&2
fi
exit 0
