#!/bin/bash
# Compila um core libretro no aparelho com o GCC do sistema.
# Uso: build-core.sh <snes9x|mgba|gpsp> <variante>
# variantes: o2 | o3 | o3lto | pgogen | pgouse (pgouse reusa a pasta de pgogen)
# Saída: ~/.local/share/r36s-perf/cores/<core>-<variante>_libretro.so
set -eu
CORE="$1"; VAR="$2"
BASE=/home/ark/.local/share/r36s-perf
SRC="$BASE/build/src"; OUT="$BASE/cores"; PROF="$BASE/build/prof/$CORE"
mkdir -p "$OUT" "$PROF"

CPU="-mcpu=cortex-a35"
JOBS=${JOBS:-3}   # 895 MiB sem swap: -j4 no g++ -O3 arrisca OOM
case "$VAR" in
  o2)     FLAGS="-O2 $CPU" ;;
  o3)     FLAGS="-O3 $CPU" ;;
  o3lto)  FLAGS="-O3 $CPU -flto=4 -fuse-linker-plugin" ;;
  pgogen) FLAGS="-O3 $CPU -fprofile-generate -fprofile-update=prefer-atomic -fprofile-dir=$PROF" ;;
  pgouse) FLAGS="-O3 $CPU -fprofile-use -fprofile-correction -Wno-missing-profile -fprofile-dir=$PROF" ;;
  *) echo "variante desconhecida: $VAR" >&2; exit 2 ;;
esac
# O PGO precisa dos mesmos caminhos de objeto na geração e no uso.
DIR_VAR="$VAR"; [ "$VAR" = pgouse ] && DIR_VAR=pgogen
WORK="$BASE/build/$CORE-$DIR_VAR"

# Embrulhos: as flags vão no fim, então ganham das -O do Makefile do projeto.
WRAP="$BASE/build/wrap-$VAR"; mkdir -p "$WRAP"
# O Debian do aparelho só tem o g++ versionado (g++-12), sem o link g++.
for t in gcc g++; do
  real=/usr/bin/$t; [ "$t" = g++ ] && real=/usr/bin/g++-12
  printf '#!/bin/sh\nexec %s "$@" %s\n' "$real" "$FLAGS" > "$WRAP/$t"
  chmod +x "$WRAP/$t"
done

if [ "$VAR" != pgouse ]; then
  rm -rf "$WORK"; mkdir -p "$WORK"
  tar -xzf "$(ls "$SRC/$CORE"-*.tar.gz | head -1)" -C "$WORK" --strip-components=1
fi
cd "$WORK"
t0=$(date +%s)
case "$CORE" in
  snes9x)
    [ "$VAR" = pgouse ] && make -C libretro platform=unix clean >/dev/null
    make -C libretro -j"$JOBS" platform=unix CC="$WRAP/gcc" CXX="$WRAP/g++" > "$WORK/build.log" 2>&1
    SO=libretro/snes9x_libretro.so ;;
  gpsp)
    # platform=unix só liga o recompilador (dynarec) em cross-compilação;
    # compilando no aparelho, sem ele o gpsp vira interpretador (2,5x mais lento).
    [ "$VAR" = pgouse ] && make platform=arm64 clean >/dev/null
    make -j"$JOBS" platform=arm64 CC="$WRAP/gcc" CXX="$WRAP/g++" > "$WORK/build.log" 2>&1
    SO=gpsp_libretro.so ;;
  mgba)
    rm -rf b; mkdir b
    cmake -S . -B b -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER="$WRAP/gcc" \
      -DCMAKE_CXX_COMPILER="$WRAP/g++" -DBUILD_LIBRETRO=ON -DSKIP_LIBRARY=ON \
      -DBUILD_QT=OFF -DBUILD_SDL=OFF -DBUILD_GL=OFF -DBUILD_GLES2=OFF -DBUILD_GLES3=OFF \
      -DUSE_DEBUGGERS=OFF -DUSE_EDITLINE=OFF -DUSE_FFMPEG=OFF -DUSE_MAGICK=OFF \
      -DUSE_DISCORD_RPC=OFF -DUSE_LUA=OFF -DUSE_SQLITE3=OFF -DUSE_ELF=OFF \
      -DENABLE_SCRIPTING=OFF -DBUILD_UPDATER=OFF > "$WORK/build.log" 2>&1
    make -C b -j"$JOBS" mgba_libretro >> "$WORK/build.log" 2>&1
    SO=b/mgba_libretro.so ;;
  *) echo "core desconhecido: $CORE" >&2; exit 2 ;;
esac
strip "$SO"
cp "$SO" "$OUT/$CORE-${VAR}_libretro.so"
echo "{\"core\":\"$CORE\",\"var\":\"$VAR\",\"flags\":\"$FLAGS\",\"build_s\":$(( $(date +%s) - t0 )),\"so\":\"$OUT/$CORE-${VAR}_libretro.so\",\"sha\":\"$(sha256sum "$OUT/$CORE-${VAR}_libretro.so" | cut -c1-16)\"}"
