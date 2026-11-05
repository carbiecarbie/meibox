#!/bin/bash
# Roda as compilações da L4 em sequência, com o ES parado para liberar memória.
# Uso: nohup build-all.sh "snes9x o3" "mgba o3" ... > build-all.log 2>&1 &
B=/home/ark/.local/share/r36s-perf/build
sudo -n systemctl stop emulationstation
for cv in "$@"; do
  echo "== $cv $(date +%T)"
  $B/build-core.sh $cv || echo "{\"erro\":\"$cv falhou\"}"
done
sudo -n systemctl start emulationstation
echo FIM
