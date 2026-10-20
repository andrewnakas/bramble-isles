#!/bin/bash
# Web build: pristine port source + patches + CLEAN smw_assets.dat -> D:/n64work/smw/site
# usage: games/smw/build_web.sh [assets.dat]   (never pass the dirty file except for local A/B looks)
set -e
REPO=$(cd "$(dirname "$0")/../.." && pwd)
W=/d/n64work/smw
DAT=${1:-$W/clean/smw_assets.dat}
SITE=${2:-$W/site}
B=$W/build
export EMSDK_QUIET=1
source /d/n64work/emsdk/emsdk_env.sh >/dev/null 2>&1

if [ ! -d $B/src ]; then
  mkdir -p $B/src
  (cd $W/pristine && tar cf - --exclude=.git --exclude=other --exclude=.github .) | (cd $B/src && tar xf -)
fi
(cd $REPO && python -m games.smw.port_patches $B/src)

mkdir -p $B/obj $B/fs $SITE
cp "$DAT" $B/fs/smw_assets.dat
cp $REPO/games/smw/web/smw.ini $B/fs/smw.ini
cd $B/src
SRCS=$(ls smb1/*.c smbll/*.c src/*.c src/snes/*.c | grep -v -e opengl.c -e glsl_shader.c)
CF="-O2 -fno-strict-aliasing -sUSE_SDL=2 -DSYSTEM_VOLUME_MIXER_AVAILABLE=0 -I. -w"
OBJS=""
for s in $SRCS; do
  o=$B/obj/$(echo $s | tr '/' '_').o
  OBJS="$OBJS $o"
  if [ ! -s $o ] || [ $s -nt $o ]; then echo "$s $o"; fi
done > $B/todo.txt
cat $B/todo.txt | xargs -P 2 -L 1 sh -c 'emcc -c '"$CF"' $0 -o $1 2>&1 | grep -E "error" ; true'
emcc $OBJS -O2 -sUSE_SDL=2 -sASYNCIFY -sASYNCIFY_IGNORE_INDIRECT=1 -sASYNCIFY_STACK_SIZE=65536 -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=67108864 \
  -sSTACK_SIZE=1048576 -sENVIRONMENT=web -lidbfs.js -sEXPORTED_RUNTIME_METHODS=FS,HEAPU8 -sEXPORTED_FUNCTIONS=_main,_web_ppu_dump,_web_ram ${SMW_PROFILE:+--profiling-funcs} \
  --preload-file $B/fs@/ -o $SITE/smw.js 2>&1 | grep -v "^cache:" | head -20
python $REPO/games/smw/web/make_page.py $SITE
ls -la $SITE | awk '{print $5, $9}' | tail -n +2 | tr '\n' ' '; echo
