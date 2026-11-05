#!/bin/bash
# Procura o modo demonstração: roda cada jogo desde o boot, sem input, e tira
# um screenshot em vários pontos. Uso: probe.sh <lista.tsv> <saida_dir> <quadros...>
# lista.tsv: emulador<TAB>core<TAB>rom
set -u
LIST="$1"; OUT="$2"; shift 2
BASE=/home/ark/.local/share/r36s-perf
mkdir -p "$OUT"
while IFS=$'\t' read -r emu core rom; do
  [ -z "$rom" ] && continue
  name=$(basename "$rom" | tr -c 'A-Za-z0-9\n' '_' | cut -c1-40)
  for n in "$@"; do
    t0=$EPOCHREALTIME
    /opt/retroarch/bin/$emu -c "/home/ark/.config/$emu/retroarch.cfg" \
      --appendconfig="$BASE/bench/bench.cfg" \
      -L "/home/ark/.config/$emu/cores/${core}_libretro.so" \
      --max-frames="$n" --max-frames-ss --max-frames-ss-path="$OUT/${name}-${core}-${n}.png" \
      "$rom" >/dev/null 2>&1
    echo -e "$name\t$core\t$n\t$(awk -v a="$t0" -v b="$EPOCHREALTIME" 'BEGIN{printf "%.2f", b-a}')"
  done
done < "$LIST"
