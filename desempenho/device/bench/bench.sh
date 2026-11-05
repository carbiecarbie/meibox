#!/bin/bash
# Uma rodada do teste de velocidade do r36s-perf.
# Uso: bench.sh <emulador: retroarch|retroarch32> <core> <rom> <quadros> [slot]
# Imprime uma linha JSON com tempo de parede, frequências e temperaturas.
# Não para o EmulationStation; quem orquestra decide a condição.
set -u
EMU="$1"; CORE="$2"; ROM="$3"; FRAMES="$4"; SLOT="${5:-}"
BASE=/home/ark/.local/share/r36s-perf
BENCH_CFG="$BASE/bench/bench.cfg"
# retroarch32 guarda estados à parte: alguns cores têm o mesmo nome nas duas versões.
[ "$EMU" = retroarch32 ] && BENCH_CFG="$BENCH_CFG|$BASE/bench/bench32.cfg"
COOL_MAX_MC=${COOL_MAX_MC:-55000}   # só começa abaixo de 55 °C
COOL_TIMEOUT=${COOL_TIMEOUT:-600}
CPU=/sys/devices/system/cpu/cpufreq/policy0
GPU=/sys/class/devfreq/ff400000.gpu
DMC=/sys/class/devfreq/dmc
TZ0=/sys/class/thermal/thermal_zone0/temp

CORE_SO="/home/ark/.config/$EMU/cores/${CORE}_libretro.so"
[ -f "$CORE" ] && CORE_SO="$CORE"   # aceita caminho completo para cores de teste
[ -f "$CORE_SO" ] || { echo "{\"erro\":\"core nao encontrado: $CORE_SO\"}"; exit 2; }
[ -f "$ROM" ] || { echo "{\"erro\":\"rom nao encontrada: $ROM\"}"; exit 2; }
mkdir -p "$BASE/bench/saves" "$BASE/bench/states" "$BASE/bench/saves32" "$BASE/bench/states32" "$BASE/bench/tmp"

# Espera esfriar.
waited=0
while [ "$(cat $TZ0)" -ge "$COOL_MAX_MC" ] && [ "$waited" -lt "$COOL_TIMEOUT" ]; do
  sleep 5; waited=$((waited + 5))
done
temp_start=$(cat $TZ0)

# Mesmo governador que o ES usa nos jogos (GlobalPerformanceGovernor=performance).
sudo -n perfmax performance "$ROM" >/dev/null 2>&1

# Amostrador: tempo, cpu kHz, gpu Hz, dmc Hz, temperatura m°C, a cada 250 ms.
SAMPLES="$BASE/bench/tmp/samples.$$"
# Só builtins do bash (read, printf), para não criar processos durante a medição.
( exec 7<> <(:)   # fd que nunca recebe dados: "read -t" nele vira um sleep sem fork
  while :; do
    read -r c <"$CPU/scaling_cur_freq"; read -r g <"$GPU/cur_freq"
    read -r d <"$DMC/cur_freq"; read -r t <"$TZ0"
    printf '%s %s %s %s %s\n' "$EPOCHREALTIME" "$c" "$g" "$d" "$t"
    read -r -t 0.25 -u 7 || true
  done ) > "$SAMPLES" &
SAMPLER=$!

ENTRY=()
[ -n "$SLOT" ] && ENTRY=(-e "$SLOT")
# SS_PATH=arquivo.png tira um screenshot no último quadro (confere a cena).
[ -n "${SS_PATH:-}" ] && ENTRY+=(--max-frames-ss --max-frames-ss-path="$SS_PATH")
LOG="$BASE/bench/tmp/ra.$$.log"
# RUNPFX="nice -n -19 taskset -c 1-3" prefixa o RetroArch; EXTRA_CFG=a.cfg|b.cfg soma configs.
read -r -a PFX <<< "${RUNPFX:-}"
[ -n "${EXTRA_CFG:-}" ] && BENCH_CFG="$BENCH_CFG|$EXTRA_CFG"
t0=$(date +%s.%N)
"${PFX[@]}" /opt/retroarch/bin/$EMU -c "/home/ark/.config/$EMU/retroarch.cfg" \
  --appendconfig="$BENCH_CFG" -v -L "$CORE_SO" "${ENTRY[@]}" \
  --max-frames="$FRAMES" "$ROM" > "$LOG" 2>&1
rc=$?
t1=$(date +%s.%N)
kill "$SAMPLER" 2>/dev/null; wait "$SAMPLER" 2>/dev/null

sudo -n perfnorm >/dev/null 2>&1
# perfmax/perfnorm limpam a tty1; mantém a tela apagada se estava apagada.
[ -f "$BASE/state/backlight-off" ] && echo 0 > /sys/class/backlight/backlight/brightness

python3 - "$SAMPLES" "$t0" "$t1" "$rc" "$EMU" "$CORE" "$CORE_SO" "$ROM" "$FRAMES" "$SLOT" "$temp_start" "$waited" "$LOG" <<'PY'
import json, sys, hashlib, os
samples, t0, t1, rc, emu, core, core_so, rom, frames, slot, temp_start, waited, log = sys.argv[1:]
logtext = open(log, errors='replace').read()
os.remove(log)
# Sem isto, um savestate ausente faria a rodada medir o boot do jogo em silêncio.
state_loaded = None
if slot:
    state_loaded = "[State] Loading state" in logtext and "Failed to load" not in logtext
t0, t1 = float(t0), float(t1)
rows = []
for line in open(samples):
    p = line.split()
    if len(p) == 5:
        rows.append((float(p[0]), int(p[1]), int(p[2]), int(p[3]), int(p[4])))
os.remove(samples)
cpu = [r[1] for r in rows]; gpu = [r[2] for r in rows]; dmc = [r[3] for r in rows]; tmp = [r[4] for r in rows]
h = hashlib.sha256(open(core_so, 'rb').read()).hexdigest()[:16]
print(json.dumps({
    "emu": emu, "core": core, "core_sha": h, "rom": os.path.basename(rom),
    "frames": int(frames), "slot": slot or None, "state_loaded": state_loaded, "rc": int(rc),
    "wall_s": round(t1 - t0, 4),
    "cpu_khz_min": min(cpu) if cpu else None, "cpu_khz_max": max(cpu) if cpu else None,
    "gpu_hz_min": min(gpu) if gpu else None, "dmc_hz_min": min(dmc) if dmc else None,
    "temp_start_c": int(temp_start) / 1000, "temp_max_c": max(tmp) / 1000 if tmp else None,
    "cooldown_s": int(waited), "samples": len(rows),
    "runpfx": os.environ.get("RUNPFX") or None, "extra_cfg": os.environ.get("EXTRA_CFG") or None,
    "throttled": bool(cpu) and min(cpu) < int(open('/sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq').read()),
}))
PY
