#!/bin/bash
# Device-local launcher. Own helper processes are cleaned up on every exit.
set -u
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$EUID" -eq 0 ]]; then
  exec runuser -u ark -- /bin/bash "$APP_DIR/launcher.sh" "$@"
fi
if [[ ! -r /dev/tty1 || ! -w /dev/tty1 ]]; then
  printf 'Cannot access the console terminal.\n' >&2
  exit 1
fi
umask 077
STATE_DIR="$APP_DIR/state"
mkdir -p -- "$STATE_DIR" || exit 1
# EmulationStation can retain XDG_RUNTIME_DIR after logind removes that
# SSH session directory. The instance lock must survive that lifecycle.
exec 9>"$STATE_DIR/instance.lock" || exit 1
flock -n 9 || exit 0
exec 2>"$STATE_DIR/last-launch.log"
printf '%s Starting diagnostics\n' "$(date -Is)" >&2
if [[ -z "${XDG_RUNTIME_DIR:-}" || ! -d "$XDG_RUNTIME_DIR" || ! -w "$XDG_RUNTIME_DIR" ]]; then
  mkdir -p -- "$STATE_DIR/runtime" || exit 1
  export XDG_RUNTIME_DIR="$STATE_DIR/runtime"
fi
gpt_pid=''
cleanup() {
  local status=$?
  if [[ -n "$gpt_pid" ]]; then
    kill "$gpt_pid" 2>/dev/null || true
    # This build of gptokeyb can ignore SIGTERM. Bound cleanup time and
    # force-stop only our own child, never other tools' helpers.
    for attempt in {1..10}; do
      kill -0 "$gpt_pid" 2>/dev/null || break
      sleep 0.05
    done
    kill -KILL "$gpt_pid" 2>/dev/null || true
    wait "$gpt_pid" 2>/dev/null || true
  fi
  printf '\033[0m\033[?25h\033[2J\033[H' > /dev/tty1
  printf '%s Exit: %s\n' "$(date -Is)" "$status" >&2
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP
export TERM=linux LANG=C.UTF-8 LC_ALL=C.UTF-8
export DIALOGRC=/opt/inttools/noshadows.dialogrc
if ! pgrep -x gptokeyb >/dev/null && ! pgrep -x oga_controls >/dev/null; then
  if [[ ! -x /opt/inttools/gptokeyb || ! -w /dev/uinput ]]; then
    printf 'Gamepad input is unavailable.\n' > /dev/tty1
    sleep 4
    exit 1
  fi
  export SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt
  /opt/inttools/gptokeyb -c "$APP_DIR/keys.gptk" > /dev/null 2>&1 &
  gpt_pid=$!
  sleep 0.2
  if ! kill -0 "$gpt_pid" 2>/dev/null; then
    printf 'Could not start gamepad input.\n' > /dev/tty1
    sleep 4
    exit 1
  fi
fi
python3 "$APP_DIR/r36s_diagnostics.py" --ui --tty /dev/tty1 --reports-dir "$APP_DIR/reports"
