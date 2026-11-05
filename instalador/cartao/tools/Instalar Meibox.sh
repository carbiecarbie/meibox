#!/bin/bash
# Meibox: instala, atualiza ou remove. Os arquivos ficam na pasta totobox/instalador do cartão.
if [ -f /roms/totobox/instalador/abrir.sh ]; then
  exec /bin/bash /roms/totobox/instalador/abrir.sh "$@"
fi
printf '\033[2J\033[HFaltou a pasta totobox/instalador no cartao.\nCopie de novo as pastas tools e totobox do ZIP.\n' > /dev/tty1
sleep 6
