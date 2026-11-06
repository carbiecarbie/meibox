#!/bin/bash
# Abre o instalador na tela do aparelho. Chamado por "tools/Instalar Meibox.sh", que o
# EmulationStation mostra em Options > Tools. Mesmo esquema do R36S Diagnostics: roda como ark,
# usa o tty1 e liga o gptokeyb (botões viram teclas) só se nenhum outro já estiver rodando.
set -u
DIR="$(cd -- "$(dirname -- "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
if [[ "$EUID" -eq 0 ]]; then
  exec runuser -u ark -- env HOME=/home/ark USER=ark LOGNAME=ark /bin/bash "$DIR/abrir.sh" "$@"
fi
if [[ ! -r /dev/tty1 || ! -w /dev/tty1 ]]; then
  echo "sem acesso à tela (tty1)" >&2
  exit 1
fi
ESTADO="/tmp/meibox-instalador-$(id -u)"
mkdir -p -- "$ESTADO" || exit 1
exec 9>"$ESTADO/trava" || exit 1
flock -n 9 || exit 0
if [[ -z "${XDG_RUNTIME_DIR:-}" || ! -d "$XDG_RUNTIME_DIR" || ! -w "$XDG_RUNTIME_DIR" ]]; then
  export XDG_RUNTIME_DIR="$ESTADO"
fi
gpt_pid=''
fonte_antes=''
limpar() {
  local status=$?
  if [[ -n "$fonte_antes" ]]; then
    sudo -n setfont -C /dev/tty1 "$fonte_antes" 2>/dev/null || true
  fi
  if [[ -n "$gpt_pid" ]]; then
    kill "$gpt_pid" 2>/dev/null || true
    for _ in {1..10}; do kill -0 "$gpt_pid" 2>/dev/null || break; sleep 0.05; done
    kill -KILL "$gpt_pid" 2>/dev/null || true
    wait "$gpt_pid" 2>/dev/null || true
  fi
  printf '\033[0m\033[?25h\033[2J\033[H' > /dev/tty1
  exit "$status"
}
trap limpar EXIT
trap 'exit 130' INT TERM HUP
export TERM=linux LANG=C.UTF-8 LC_ALL=C.UTF-8
[[ -f /opt/inttools/noshadows.dialogrc ]] && export DIALOGRC=/opt/inttools/noshadows.dialogrc
if ! pgrep -x gptokeyb >/dev/null && ! pgrep -x oga_controls >/dev/null; then
  # O /dev/uinput começa só para o root; as ferramentas do sistema liberam assim ao abrir.
  [[ -w /dev/uinput ]] || sudo -n chmod 666 /dev/uinput 2>/dev/null
  if [[ -x /opt/inttools/gptokeyb && -w /dev/uinput ]]; then
    export SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt
    /opt/inttools/gptokeyb -c "$DIR/teclas.gptk" >/dev/null 2>&1 &
    gpt_pid=$!
    sleep 0.2
  else
    printf 'Os botoes nao estao disponiveis (gptokeyb).\n' > /dev/tty1
    sleep 5
    exit 1
  fi
fi
# A fonte do console do ArkOS/dArkOS (Lat7-Terminus) não tem ã, õ e ô. Enquanto o instalador está
# aberto, usa a Lat15 do mesmo tamanho (tem todos os acentos do português) e guarda a anterior
# para devolver no fim. Sem ela, os textos saem sem acento.
trocar_fonte() {
  local linhas colunas larg alt nome tela
  read -r linhas colunas < <(stty -F /dev/tty1 size 2>/dev/null) || return 1
  read -r larg alt < <(tr ',' ' ' < /sys/class/graphics/fb0/virtual_size 2>/dev/null) || return 1
  [[ "$linhas" -gt 0 && "$colunas" -gt 0 ]] || return 1
  alt=$(( alt / linhas )); larg=$(( larg / colunas ))
  if [[ "$larg" -eq 8 ]]; then nome="Lat15-Terminus$alt"; else nome="Lat15-Terminus${alt}x$larg"; fi
  tela="/usr/share/consolefonts/$nome.psf.gz"
  [[ -f "$tela" ]] || return 1
  sudo -n setfont -O "$ESTADO/fonte-antes.psf" -C /dev/tty1 "$tela" 2>/dev/null || return 1
  fonte_antes="$ESTADO/fonte-antes.psf"
}
trocar_fonte || export SEM_ACENTOS=1
printf '\033[2J\033[H' > /dev/tty1
bash "$DIR/instalar.sh" --tela
