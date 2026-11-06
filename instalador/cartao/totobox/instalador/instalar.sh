#!/bin/bash
# Instalador do Meibox e do Copiloto da Mei a partir do cartão SD.
#
# No aparelho: Options > Tools > Instalar Meibox (abrir.sh chama este script com --tela).
# Por SSH, como ark (é o que o arquivo PARA-SUA-IA.md manda um assistente fazer):
#   bash /roms/totobox/instalador/instalar.sh [opções]
#     --conferir       só confere o sistema e diz o que faria; não muda nada
#     --remover        desinstala o Meibox e o copiloto (mantém fotos, frases, dicas e guias)
#     --apagar-chave   com --remover: apaga também a chave da IA guardada no aparelho
#     --sem-boot       não abre o Meibox quando o aparelho liga
#     --sem-copiloto   não instala o copiloto, mesmo com chave
#     --sem-desempenho não aplica as otimizações de desempenho dos jogos
#     --lingua pt|en   idioma das mensagens e do Meibox (padrão: pt)
#     --tela           telas no aparelho (dialog no tty1); sem isso, só texto
#
# O que faz, em ordem: confere se o sistema é da família ArkOS (dArkOS/ArkOS); instala o Meibox
# (meibox/device/install.sh); aplica as otimizações medidas dos jogos (desempenho/desempenho.py);
# se houver chave, instala o copiloto (copiloto/device/install.sh),
# guarda a chave fora do cartão e escolhe o modelo. O registro fica em ultimo-log.txt, ao lado,
# e nunca contém a chave.
set -u
VERSAO=0.2.0
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
CARTAO="$(dirname "$DIR")"
ARQ_CHAVE="$CARTAO/chave-da-ia.txt"
MODELO_CHAVE="$DIR/chave-da-ia.modelo.txt"
LOG="$DIR/ultimo-log.txt"
MEI_APP="$HOME/.local/share/totobox"
COP_APP="$HOME/.local/share/mei-copiloto"
COP_CONF="$HOME/.config/mei-copiloto"
PACOTE="$DIR/desempenho"
desemp() { python3 -I "$PACOTE/desempenho.py" "$@"; }
DROPIN=/etc/systemd/system/emulationstation.service.d/10-totobox.conf

TELA=0; CONFERIR=0; REMOVER=0; APAGAR_CHAVE=0; BOOT=1; COPILOTO=1; DESEMPENHO=1; LINGUA=pt
while [ $# -gt 0 ]; do
  case "$1" in
    --tela) TELA=1 ;;
    --conferir) CONFERIR=1 ;;
    --remover) REMOVER=1 ;;
    --apagar-chave) APAGAR_CHAVE=1 ;;
    --sem-boot) BOOT=0 ;;
    --sem-copiloto) COPILOTO=0 ;;
    --sem-desempenho) DESEMPENHO=0 ;;
    --lingua) shift; LINGUA="${1:-pt}" ;;
    *) echo "opção desconhecida: $1"; exit 2 ;;
  esac
  shift
done
[ "$LINGUA" = en ] || LINGUA=pt

# ------------------------------------------------------------------ textos e telas
# t "português" "english". SEM_ACENTOS=1 troca os acentos (para fontes de console sem eles).
t() {
  local s="$1"; [ "$LINGUA" = en ] && s="$2"
  if [ "${SEM_ACENTOS:-0}" = 1 ]; then printf '%s' "$s" | iconv -f UTF-8 -t ASCII//TRANSLIT 2>/dev/null || printf '%s' "$s"
  else printf '%s' "$s"; fi
}
DLG=(dialog --backtitle "Meibox $VERSAO" --no-collapse)
altura() {  # linhas que o texto ocupa numa caixa de 62 colunas, mais bordas e botões (tela: 24)
  local h=$(( $(printf '%s\n' "$1" | fold -s -w 56 | wc -l) + 5 ))
  [ "$h" -lt 8 ] && h=8; [ "$h" -gt 22 ] && h=22; echo "$h"
}
aviso() {  # aviso "título" "texto"
  if [ "$TELA" = 1 ]; then
    "${DLG[@]}" --title " $1 " --ok-label "OK" --msgbox "$2" "$(altura "$2")" 62 >/dev/tty1 </dev/tty1
  else printf '\n== %s\n%s\n' "$1" "$2"; fi
}
espera() {  # espera "texto": tela de "aguarde", sem botão
  if [ "$TELA" = 1 ]; then "${DLG[@]}" --infobox "$1" 7 56 >/dev/tty1
  else printf '\n... %s\n' "$1"; fi
}
pergunta() {  # pergunta "texto" padrão(0=sim,1=não). Sem tela, devolve o padrão.
  [ "$TELA" = 1 ] || return "$2"
  local extra=(); [ "$2" = 1 ] && extra=(--defaultno)
  "${DLG[@]}" "${extra[@]}" --yes-label "$(t Sim Yes)" --no-label "$(t Não No)" \
    --yesno "$1" "$(altura "$1")" 62 >/dev/tty1 </dev/tty1
}
escolha() {  # escolha "texto" tag1 item1 tag2 item2 ... -> imprime a tag escolhida
  local texto="$1"; shift
  local n=$(( $# / 2 ))
  "${DLG[@]}" --no-cancel --no-tags --output-fd 3 --menu "$texto" $(( n + 8 )) 50 "$n" "$@" \
    3>&1 1>/dev/tty1 </dev/tty1
}
rodar() {  # rodar comando...: saída no log (e na tela, no modo texto)
  echo "\$ $*" >>"$LOG"
  if [ "$TELA" = 1 ]; then "$@" >>"$LOG" 2>&1
  else "$@" 2>&1 | tee -a "$LOG"; return "${PIPESTATUS[0]}"; fi
}
fim_do_log() { tail -n 8 "$LOG" | cut -c1-58; }

# ------------------------------------------------------------------ conferências
PROBLEMAS=""
conferir_sistema() {
  PROBLEMAS=""
  [ "$(id -un)" = ark ] || PROBLEMAS+="- $(t 'usuário ark (é o do ArkOS/dArkOS)' 'user ark (the ArkOS/dArkOS one)')"$'\n'
  [ -f /etc/emulationstation/es_systems.cfg ] || PROBLEMAS+="- /etc/emulationstation/es_systems.cfg"$'\n'
  [ -d /opt/system ] || PROBLEMAS+="- $(t 'menu Options' 'Options menu') (/opt/system)"$'\n'
  sudo -n true 2>/dev/null || PROBLEMAS+="- $(t 'sudo sem senha' 'passwordless sudo')"$'\n'
  python3 -c 'import ctypes, sqlite3
for l in ("libSDL2-2.0.so.0", "libSDL2_image-2.0.so.0", "libSDL2_ttf-2.0.so.0",
          "libSDL2_mixer-2.0.so.0", "libSDL2_gfx-1.0.so.0"):
    ctypes.CDLL(l)' 2>/dev/null || PROBLEMAS+="- Python 3 + SDL2 (image, ttf, mixer, gfx)"$'\n'
  [ -f "$DIR/meibox/totobox/main.py" ] && [ -f "$DIR/copiloto/mei_copiloto.py" ] \
    || PROBLEMAS+="- $(t 'arquivos do instalador incompletos na pasta' 'installer files missing in') $DIR"$'\n'
  [ -z "$PROBLEMAS" ]
}
jogo_aberto() { pgrep -f '/usr/local/bin/retroarch|/opt/retroarch/bin/' >/dev/null; }
tem_internet() { python3 -c 'import socket; socket.create_connection(("pypi.org", 443), 6)' 2>/dev/null; }
boot_possivel() { systemctl cat emulationstation.service >/dev/null 2>&1; }
chave_guardada() {  # imprime o fornecedor da chave já guardada no aparelho, se houver
  if [ -s "$COP_CONF/chaves/openai" ]; then echo openai
  elif [ -s "$COP_CONF/chaves/anthropic" ]; then echo anthropic; fi
}
nome_fornecedor() { [ "$1" = anthropic ] && echo "Anthropic (Claude)" || echo "OpenAI"; }

# ------------------------------------------------------------------ remover
remover() {
  if [ "$TELA" = 1 ]; then
    pergunta "$(t 'Remover o Meibox e o Copiloto da Mei deste aparelho?

Suas fotos da Ficha, frases, dicas e guias continuam na pasta totobox do cartão.' \
'Remove Meibox and the Mei Copilot from this device?

Your Ficha pictures, lines, hints and guides stay in the totobox folder on the card.')" 1 || return 0
  fi
  espera "$(t 'Removendo...' 'Removing...')"
  local ok=1
  if [ -f "$PACOTE/desempenho.py" ] && desemp instalado; then rodar desemp remover || ok=0; fi
  if [ -f "$COP_APP/device/uninstall.sh" ]; then rodar bash "$COP_APP/device/uninstall.sh" || ok=0; fi
  if [ -f "$MEI_APP/device/uninstall.sh" ]; then rodar bash "$MEI_APP/device/uninstall.sh" || ok=0; fi
  if [ -n "$(chave_guardada)" ]; then
    if [ "$TELA" = 1 ]; then
      pergunta "$(t 'Apagar também a chave da IA guardada no aparelho?' \
                    'Also erase the AI key stored on the device?')" 0 && APAGAR_CHAVE=1
    fi
    [ "$APAGAR_CHAVE" = 1 ] && rodar python3 -I "$DIR/chave.py" apagar "$COP_CONF"
  fi
  if [ "$ok" = 1 ]; then
    aviso "$(t 'Pronto' 'Done')" "$(t 'O Meibox foi removido. O EmulationStation volta a abrir direto ao ligar. Emuladores e ajustes de jogo voltaram ao original; a escolha de emulador por jogo volta no próximo início.' \
                                     'Meibox was removed. EmulationStation opens directly again at boot. Emulators and game settings are back to the originals; per-game emulator choices revert at the next start.')"
  else
    aviso "$(t 'Algo deu errado' 'Something went wrong')" "$(fim_do_log)"
    return 1
  fi
}

# ------------------------------------------------------------------ instalar
instalar() {
  # 1. Meibox
  espera "$(t 'Instalando o Meibox...' 'Installing Meibox...')"
  local args=(); [ "$BOOT" = 1 ] && args=(--boot)
  if ! rodar bash "$DIR/meibox/device/install.sh" "${args[@]}"; then
    aviso "$(t 'Não deu para instalar o Meibox' 'Could not install Meibox')" "$(fim_do_log)"
    return 1
  fi
  if [ "$BOOT" = 0 ] && [ -e "$DROPIN" ]; then  # atualização em que a pessoa desligou a abertura
    rodar sudo -n rm -f "$DROPIN"; rodar sudo -n systemctl daemon-reload
  fi
  rodar python3 -I "$DIR/chave.py" idioma "$MEI_APP/data/totobox.db" "$LINGUA"
  local resumo
  resumo="$(t '- Meibox instalado.' '- Meibox installed.')"$'\n'
  if [ "$BOOT" = 1 ]; then
    resumo+="$(t '- Ele abre quando o aparelho liga (segure B ao ligar para pular).' \
                 '- It opens when the device starts (hold B at boot to skip it).')"$'\n'
  else
    resumo+="$(t '- Abra pelo menu Options > Meibox.' '- Open it from Options > Meibox.')"$'\n'
  fi

  # 2. Desempenho dos jogos (o que foi medido em desempenho/)
  if [ "$DESEMPENHO" = 1 ] && [ -f "$PACOTE/desempenho.py" ]; then
    if jogo_aberto; then
      resumo+="$(t '- Desempenho NÃO aplicado: feche o jogo aberto e rode de novo.' \
                   '- Performance NOT applied: close the open game and run again.')"$'\n'
    else
      espera "$(t 'Ajustando os jogos... Lendo a sua biblioteca, pode levar 1 minuto.' \
                  'Tuning the games... Reading your library, may take a minute.')"
      local saida_desemp
      echo "\$ desempenho.py aplicar $PACOTE $LINGUA" >>"$LOG"
      if saida_desemp="$(desemp aplicar "$PACOTE" "$LINGUA" 2>>"$LOG")"; then
        printf '%s\n' "$saida_desemp" >>"$LOG"
        [ "$TELA" = 1 ] || printf '%s\n' "$saida_desemp"
        resumo+="$saida_desemp"$'\n'
      else
        resumo+="$(t '- Desempenho NÃO aplicado. Últimas linhas do registro:' \
                     '- Performance NOT applied. Last log lines:')"$'\n'"$(fim_do_log)"$'\n'
      fi
    fi
  fi

  # 3. Copiloto: só com chave (no cartão ou já guardada) ou se já estava instalado
  local prov_cartao="" rc=1 prov
  prov_cartao="$(python3 -I "$DIR/chave.py" ler "$ARQ_CHAVE")"; rc=$?
  if [ "$rc" = 2 ]; then
    resumo+="$(t '- A chave em totobox/chave-da-ia.txt não parece uma chave de API. Confira e rode de novo.' \
                 '- The key in totobox/chave-da-ia.txt does not look like an API key. Check it and run again.')"$'\n'
    prov_cartao=""
  fi
  prov="${prov_cartao:-$(chave_guardada)}"
  if [ "$COPILOTO" = 1 ] && [ -n "$prov_cartao" ] && [ "$TELA" = 1 ]; then
    pergunta "$(t "Achei uma chave da $(nome_fornecedor "$prov") no cartão.

Instalar o Copiloto da Mei? Ele dá dicas durante o jogo com SELECT + R1 e precisa de Wi-Fi." \
"Found a $(nome_fornecedor "$prov") key on the card.

Install the Mei Copilot? It gives in-game hints with SELECT + R1 and needs Wi-Fi.")" 0 || COPILOTO=0
  fi
  if [ "$COPILOTO" = 1 ] && { [ -n "$prov" ] || [ -d "$COP_APP" ]; }; then
    local cop_args=() cop_ok=1
    if [ "$prov" = anthropic ] && [ ! -d "$COP_APP/vendor/anthropic" ]; then
      if tem_internet; then cop_args=(--com-sdk)
      else
        cop_ok=0
        resumo+="$(t '- Copiloto NÃO instalado: a chave da Anthropic precisa baixar um componente (~47 MB). Conecte o Wi-Fi e rode de novo.' \
                     '- Copilot NOT installed: an Anthropic key needs a ~47 MB download. Connect Wi-Fi and run again.')"$'\n'
      fi
    fi
    if [ "$cop_ok" = 1 ]; then
      espera "$(t 'Instalando o Copiloto da Mei...' 'Installing the Mei Copilot...')"
      if ! rodar bash "$DIR/copiloto/device/install.sh" "${cop_args[@]}"; then
        cop_ok=0
        resumo+="$(t '- Copiloto NÃO instalado. Últimas linhas do registro:' '- Copilot NOT installed. Last log lines:')"$'\n'"$(fim_do_log)"$'\n'
      fi
    fi
    if [ "$cop_ok" = 1 ]; then
      if [ -n "$prov_cartao" ]; then
        python3 -I "$DIR/chave.py" guardar "$ARQ_CHAVE" "$COP_CONF" "$MODELO_CHAVE" >/dev/null 2>>"$LOG" \
          && echo "chave guardada ($prov_cartao) e apagada do cartão" >>"$LOG"
      elif [ -n "$prov" ]; then
        rodar python3 -I "$DIR/chave.py" ajustar "$COP_CONF"
      fi
      rodar sudo -n systemctl restart mei-copiloto
      if [ -n "$prov" ]; then
        resumo+="$(t "- Copiloto da Mei instalado, com $(nome_fornecedor "$prov"). Num jogo, aperte SELECT + R1." \
                     "- Mei Copilot installed, using $(nome_fornecedor "$prov"). In a game, press SELECT + R1.")"$'\n'
        [ -n "$prov_cartao" ] && resumo+="$(t '- A chave foi guardada no aparelho e apagada do cartão.' \
                                              '- The key was stored on the device and erased from the card.')"$'\n'
      else
        resumo+="$(t '- Copiloto atualizado, ainda sem chave.' '- Copilot updated, still without a key.')"$'\n'
      fi
    fi
  elif [ "$COPILOTO" = 1 ]; then
    resumo+="$(t '- Copiloto (opcional) não instalado: não há chave em totobox/chave-da-ia.txt.' \
                 '- Copilot (optional) not installed: no key in totobox/chave-da-ia.txt.')"$'\n'
  fi

  if [ "$TELA" = 1 ]; then
    if pergunta "$resumo
$(t 'Reiniciar o aparelho agora?' 'Restart the device now?')" 0; then
      espera "$(t 'Reiniciando...' 'Restarting...')"
      sync; sudo -n systemctl reboot
    fi
  else
    aviso "$(t 'Pronto' 'Done')" "$resumo$(t 'Reinicie o aparelho para o Meibox abrir.' 'Restart the device so Meibox opens.')"
  fi
}

# ------------------------------------------------------------------ começo
{ echo "=== Meibox instalador $VERSAO  $(date -Is)  $(id -un)  $*"; grep -m1 PRETTY_NAME /etc/os-release 2>/dev/null; } >"$LOG" 2>/dev/null \
  || LOG=/tmp/meibox-instalador.log

if [ "$TELA" = 1 ]; then
  LINGUA="$(escolha "Idioma / Language" pt "Português" en "English")" || exit 0
fi

if ! conferir_sistema; then
  aviso "$(t 'Este sistema não é compatível' 'This system is not supported')" \
"$(t 'O Meibox é feito para R36S com dArkOS ou ArkOS. Faltou:' 'Meibox is made for the R36S with dArkOS or ArkOS. Missing:')
$PROBLEMAS
$(t 'Nada foi mudado.' 'Nothing was changed.')"
  echo "incompatível:"$'\n'"$PROBLEMAS" >>"$LOG"
  exit 1
fi
boot_possivel || BOOT=0

if [ "$CONFERIR" = 1 ]; then
  prov="$(python3 -I "$DIR/chave.py" ler "$ARQ_CHAVE")"; rc=$?
  aviso "$(t 'Conferência' 'Check')" "$(t 'Sistema compatível.' 'System supported.')
Meibox: $([ -d "$MEI_APP" ] && t 'já instalado (seria atualizado)' 'installed (would be updated)' || t 'seria instalado' 'would be installed')
Boot: $([ "$BOOT" = 1 ] && t 'abriria ao ligar' 'would open at boot' || t 'não abriria ao ligar' 'would not open at boot')
$(t 'Chave no cartão' 'Key on card'): $(case $rc in 0) nome_fornecedor "$prov" ;; 2) t 'inválida' 'invalid' ;; *) t 'nenhuma' 'none' ;; esac)
$(t 'Chave guardada' 'Stored key'): $(p=$(chave_guardada); [ -n "$p" ] && nome_fornecedor "$p" || t 'nenhuma' 'none')"
  if [ -f "$PACOTE/desempenho.py" ]; then
    echo; echo "--- $(t 'desempenho dos jogos' 'game performance')"
    desemp conferir "$PACOTE" "$LINGUA"
  fi
  if [ -f "$DIR/copiloto/device/install.sh" ]; then
    echo; echo "--- copiloto/device/install.sh --conferir"
    bash "$DIR/copiloto/device/install.sh" --conferir
  fi
  exit 0
fi

if [ "$REMOVER" = 1 ]; then remover; exit $?; fi

if [ "$TELA" = 1 ]; then
  if [ -d "$MEI_APP" ] || [ -d "$COP_APP" ]; then
    acao="$(escolha "$(t 'O Meibox já está instalado. O que fazer?' 'Meibox is already installed. What now?')" \
      atualizar "$(t 'Atualizar / reinstalar' 'Update / reinstall')" \
      remover "$(t 'Remover' 'Remove')" \
      sair "$(t 'Sair' 'Exit')")" || exit 0
    case "$acao" in remover) remover; exit $? ;; sair) exit 0 ;; esac
  else
    pergunta "$(t 'Instalar o Meibox?

Ele vira a tela de início do aparelho, com a gata Mei, os seus jogos e a sua Ficha. O EmulationStation continua lá: é só sair do Meibox.' \
'Install Meibox?

It becomes the device home screen, with Mei the cat, your games and your Ficha. EmulationStation is still there: just leave Meibox.')" 0 || exit 0
  fi
  if [ "$BOOT" = 1 ]; then
    pergunta "$(t 'Abrir o Meibox sempre que ligar o aparelho?

(Se disser não, ele fica no menu Options > Meibox.)' \
'Open Meibox every time the device starts?

(If not, it stays in Options > Meibox.)')" 0 || BOOT=0
  fi
  if [ "$DESEMPENHO" = 1 ] && [ -f "$PACOTE/desempenho.py" ]; then
    pergunta "$(t 'Deixar os jogos mais rápidos? (recomendado)

Troca emuladores por versões recompiladas e ajusta o vídeo, como medido no R36S: SNES em média 24% mais rápido, GBA de 11% a 280%, botão um quadro mais rápido. O que não servir no seu sistema fica como está. Remover desfaz tudo.' \
'Make games run faster? (recommended)

Swaps emulators for rebuilt versions and tunes video, as measured on the R36S: SNES 24% faster on average, GBA 11% to 280%, button one frame quicker. Anything that does not fit your system is left alone. Remove undoes it all.')" 0 || DESEMPENHO=0
  fi
fi

instalar
