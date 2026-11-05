#!/bin/bash
# Instala o Copiloto da Mei no R36S (dArkOSRE). Roda como ark; usa sudo -n só nos passos de sistema.
#
# Uso: device/install.sh [--conferir] [--sem-porta] [--sem-retroarch] [--com-sdk]
#   --conferir       só mostra o que faria, sem mudar nada
#   --sem-porta      não instala a regra nft da porta 55355
#   --sem-retroarch  não mexe nas configs do RetroArch
#   --com-sdk        instala o SDK da Anthropic em vendor/ (baixa ~47 MB; só para usar o Claude)
#
# O que faz:
#  1. copia o app para ~/.local/share/mei-copiloto (mantém state/ e vendor/ se já existirem)
#  2. cria ~/.config/mei-copiloto/config.json com device/config.json (se ainda não existir)
#  3. move a chave antiga api_key para chaves/anthropic (permissão 600)
#  4. cria /roms/totobox/dicas e /roms/totobox/guias (a pasta de dados do Meibox)
#  5. regra nft que fecha a porta 55355 para a rede (serviço mei-copiloto-porta)
#  6. serviço mei-copiloto (systemd, com o usuário que roda o install, ligado no boot)
#  7. as 6 chaves do RetroArch nas duas configs, com backup (device/retroarch-patch.py)
set -euo pipefail

SRC="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
APP="$HOME/.local/share/mei-copiloto"
CONF="$HOME/.config/mei-copiloto"
CONFERIR=0; PORTA=1; RETRO=1; SDK=0
for a in "$@"; do
  case "$a" in
    --conferir) CONFERIR=1 ;;
    --sem-porta) PORTA=0 ;;
    --sem-retroarch) RETRO=0 ;;
    --com-sdk) SDK=1 ;;
    *) echo "opção desconhecida: $a"; exit 2 ;;
  esac
done
passo() { echo; echo "== $*"; }
faz() { if [ "$CONFERIR" = 1 ]; then echo "   [conferir] $*"; else echo "   $*"; eval "$@"; fi; }

# ---------------------------------------------------------------- conferências
[ "$(id -u)" != 0 ] || { echo "rode com o seu usuário (no ArkOS/dArkOS, ark), não como root"; exit 1; }
[ -f "$SRC/mei_copiloto.py" ] && [ -d "$SRC/copiloto" ] || { echo "não achei o app em $SRC"; exit 1; }
if [ "$CONFERIR" = 0 ] && pgrep -f '/usr/local/bin/retroarch|/opt/retroarch/bin/' >/dev/null; then
  echo "o RetroArch está aberto: feche o jogo antes de instalar"; exit 1
fi
sudo -n true || { echo "precisa de sudo sem senha"; exit 1; }
python3 -c 'import ctypes; [ctypes.CDLL(l) for l in ("libSDL2-2.0.so.0","libSDL2_image-2.0.so.0","libSDL2_ttf-2.0.so.0")]' \
  || { echo "faltam as bibliotecas SDL2"; exit 1; }
echo "origem: $SRC   conferir=$CONFERIR porta=$PORTA retroarch=$RETRO sdk=$SDK"

# ---------------------------------------------------------------- 1. app
passo "1. app em $APP"
faz "mkdir -p '$APP/state'"
faz "rm -rf '$APP/copiloto' '$APP/assets'"
faz "rm -rf '$APP/device' && mkdir -p '$APP/device'"
faz "cp -r '$SRC/copiloto' '$SRC/assets' '$SRC/mei_copiloto.py' '$APP/'"
faz "cp '$SRC/device/'*.sh '$SRC/device/'*.py '$SRC/device/'*.service '$SRC/device/'*.nft '$SRC/device/config.json' '$APP/device/'"
faz "find '$APP' -name __pycache__ -prune -exec rm -rf {} +"
if [ "$SDK" = 1 ]; then
  faz "python3 -m pip install --quiet --only-binary=:all: --target '$APP/vendor' anthropic"
fi

# ---------------------------------------------------------------- 2-3. config e chaves
passo "2. config e chaves em $CONF"
faz "mkdir -p '$CONF/chaves' && chmod 700 '$CONF' '$CONF/chaves'"
if [ -f "$CONF/config.json" ]; then
  echo "   config.json já existe: mantido"
else
  faz "install -m 644 '$SRC/device/config.json' '$CONF/config.json'"
fi
if [ -f "$CONF/api_key" ] && [ ! -e "$CONF/chaves/anthropic" ]; then
  faz "mv '$CONF/api_key' '$CONF/chaves/anthropic' && chmod 600 '$CONF/chaves/anthropic'"
fi
faz "chmod 600 '$CONF'/chaves/* 2>/dev/null || true"

# ---------------------------------------------------------------- 4. pastas no cartão
passo "4. pastas /roms/totobox/dicas e /roms/totobox/guias"
faz "mkdir -p /roms/totobox/dicas /roms/totobox/guias"

# ---------------------------------------------------------------- 5. porta 55355
if [ "$PORTA" = 1 ]; then
  passo "5. regra nft: porta 55355 fechada para a rede"
  faz "sudo -n /usr/sbin/nft -c -f '$SRC/device/mei-copiloto-porta.nft'"
  faz "sudo -n install -m 644 '$SRC/device/mei-copiloto-porta.nft' /etc/mei-copiloto-porta.nft"
  faz "sudo -n install -m 644 '$SRC/device/mei-copiloto-porta.service' /etc/systemd/system/"
  faz "sudo -n systemctl daemon-reload"
  faz "sudo -n systemctl enable --now mei-copiloto-porta.service"
  faz "sudo -n /usr/sbin/nft list table inet mei_copiloto"
fi

# ---------------------------------------------------------------- 6. serviço
passo "6. serviço mei-copiloto"
faz "sed -e 's|^User=.*|User=$(id -un)|' -e 's|/home/ark/|$HOME/|' '$SRC/device/mei-copiloto.service' > /tmp/mei-copiloto.service.$$"
faz "sudo -n install -m 644 /tmp/mei-copiloto.service.$$ /etc/systemd/system/mei-copiloto.service && rm -f /tmp/mei-copiloto.service.$$"
faz "sudo -n systemctl daemon-reload"
faz "sudo -n systemctl enable mei-copiloto.service"
faz "sudo -n systemctl restart mei-copiloto.service"
if [ "$CONFERIR" = 0 ]; then
  for i in $(seq 1 60); do ss -ltn | grep -q '127.0.0.1:4404 ' && break; sleep 0.5; done
  ss -ltn | grep -q '127.0.0.1:4404 ' && echo "   escutando em 127.0.0.1:4404" \
    || { echo "   ERRO: o serviço não abriu a porta 4404"; sudo -n journalctl -u mei-copiloto -n 20 --no-pager; exit 1; }
fi

# ---------------------------------------------------------------- 7. RetroArch
if [ "$RETRO" = 1 ]; then
  passo "7. configs do RetroArch"
  if [ "$CONFERIR" = 1 ]; then
    python3 -I "$SRC/device/retroarch-patch.py" conferir
  else
    python3 -I "$SRC/device/retroarch-patch.py" aplicar
  fi
fi

passo "pronto"
[ "$CONFERIR" = 1 ] && echo "   (nada foi mudado: era só conferência)" || true
