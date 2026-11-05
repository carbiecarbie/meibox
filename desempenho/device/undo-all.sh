#!/bin/bash
# Desfaz todas as mudanças do projeto r36s-perf no aparelho, na ordem inversa.
# Fonte de verdade: results/manifest.jsonl no PC.
#
# Uso:
#   undo-all.sh -n          mostra o que faria, sem mudar nada
#   undo-all.sh             desfaz as mudanças de configuração e de cores
#   undo-all.sh --limpar    também remove g++-12, a pasta do projeto no
#                           aparelho e a chave SSH do PC
#
# Não precisa de rede. Roda como ark (usa sudo -n onde precisa).
set -u
DRY=0; LIMPAR=0
for a in "$@"; do
  case "$a" in
    -n) DRY=1 ;;
    --limpar) LIMPAR=1 ;;
    *) echo "opção desconhecida: $a" >&2; exit 2 ;;
  esac
done

BASE=/home/ark/.local/share/r36s-perf
CORES=/home/ark/.config/retroarch/cores
OVR=/home/ark/.config/retroarch/config

run() { echo "+ $*"; [ $DRY = 1 ] || eval "$@"; }

if pgrep -f '^/opt/retroarch/bin/' >/dev/null; then
  echo "Tem um jogo aberto. Feche o jogo e rode de novo." >&2; exit 3
fi

# O ES regrava o gamelist.xml ao sair, então ele fica parado durante a volta.
if [ $DRY = 0 ]; then
  trap 'sudo -n systemctl start emulationstation' EXIT
fi
run "sudo -n systemctl stop emulationstation"
run "sleep 2"

echo "== L2: overrides de thread de vídeo (só os arquivos do projeto)"
if [ -d "$OVR" ]; then
  for d in "Genesis Plus GX" Snes9x mGBA gpSP; do
    [ -d "$OVR/$d" ] || continue
    grep -l "r36s-perf L2" "$OVR/$d"/*.cfg 2>/dev/null | while read -r f; do
      run "rm -f \"$f\""
    done
    run "rmdir \"$OVR/$d\" 2>/dev/null || true"
  done
fi

echo "== L3: emulador por jogo no gamelist.xml"
GAMES_SNES=("Star Fox (USA) (Rev 2).zip" "Stunt Race FX (USA) (Rev 1).zip"
  "Doom (USA).zip" "Vortex (USA) (En,Es).zip" "Dirt Racer (Europe) (En,Fr,De).zip"
  "Star Fox 2 (USA).zip" "Starwing (Europe).zip" "Starwing - Competition (Europe).zip"
  "Super Star Fox Weekend (USA).zip")
GAMES_GBA=("Doom II (USA).zip" "Duke Nukem Advance (USA).zip"
  "F-Zero - GP Legend (USA).zip" "Super Monkey Ball Jr. (USA).zip")
untag() {  # $1 gamelist, resto: arquivos de ROM
  local gl="$1"; shift
  [ -f "$gl" ] || return
  echo "+ tirar <emulator>/<core> de $# jogos em $gl"
  [ $DRY = 1 ] && return
  python3 - "$gl" "$@" <<'PY'
import re, sys
gl, roms = sys.argv[1], sys.argv[2:]
s = open(gl, encoding="utf-8").read()
for rom in roms:
    pat = re.compile(r"(<game>(?:(?!</game>).)*?<path>\./" + re.escape(rom) + r"</path>(?:(?!</game>).)*?</game>)", re.S)
    s = pat.sub(lambda m: re.sub(r"\s*<(emulator|core)>[^<]*</\1>", "", m.group(1)), s)
open(gl, "w", encoding="utf-8").write(s)
PY
}
untag /roms/snes/gamelist.xml "${GAMES_SNES[@]}"
untag /roms/gba/gamelist.xml "${GAMES_GBA[@]}"

echo "== L4: cores originais (snes9x, mgba, mgba_rumble, gpsp)"
for c in snes9x mgba mgba_rumble gpsp; do
  b="$BASE/backup/cores/${c}_libretro.so"
  if [ -f "$b" ]; then run "cp -p \"$b\" \"$CORES/${c}_libretro.so\""
  else echo "  (sem backup de $c, deixado como está)"; fi
done

echo "== L1: serviços, timers e escalonador do cartão"
run "sudo -n systemctl enable --now smbd nmbd"
run "sudo -n systemctl enable --now apt-daily.timer apt-daily-upgrade.timer dpkg-db-backup.timer xfs_scrub_all.timer e2scrub_all.timer"
run "sudo -n rm -f /etc/udev/rules.d/60-r36s-perf-iosched.rules"
run "echo cfq | sudo -n tee /sys/block/mmcblk0/queue/scheduler >/dev/null"

echo "== L0: proteção de tela, brilho e som"
ES=/home/ark/.emulationstation/es_settings.cfg
run "sed -i 's|\\(name=\"ScreenSaverBehavior\" value=\"\\)black\"|\\1random video\"|' \"$ES\""
run "rm -f $BASE/state/backlight-off $BASE/state/muted"
run "echo 80 | sudo -n tee /sys/class/backlight/backlight/brightness >/dev/null"
run "amixer -q sset Playback 193"

if [ $LIMPAR = 1 ]; then
  echo "== limpeza"
  run "sudo -n apt-get remove -y --autoremove g++-12"
  run "sed -i '/r36s-perf@pc/d' /home/ark/.ssh/authorized_keys"
  run "rm -rf \"$BASE\""
fi

echo "Pronto. O snapshot btrfs /.snapshots/00-inicial continua lá como última garantia."
