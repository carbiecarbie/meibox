#!/bin/bash
cd /home/ark/.local/share/r36s-perf/bench
rm -rf shots && mkdir shots
for ec in "retroarch snes9x" "retroarch snes9x2010" "retroarch snes9x2005" "retroarch chimerasnes" "retroarch mednafen_supafaust" "retroarch32 snes9x2002" "retroarch32 snes9x2005"; do
  echo "== $ec"; ./make-states.sh $ec nav-snes-fix2.json
done
for ec in "retroarch vba_next" "retroarch gpsp" "retroarch vbam" "retroarch32 gpsp"; do
  echo "== $ec"; ./make-states.sh $ec nav-fzero.json
done
echo FIM
