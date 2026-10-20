#!/bin/bash
# Shared dev build for parallel workers: generate a clean .dat and link a site, under a lock.
#   bash games/smw/dev_build.sh <name>            -> D:/n64work/smw/dev/<name>/{smw_assets.dat, site/}
#   SMW_ONLY=music bash games/smw/dev_build.sh x   (passes --only=music to generate.py)
# The C objects are shared (code never changes here); only the link + preload differ per site.
set -e
NAME=${1:?name}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
D=/d/n64work/smw/dev/$NAME
mkdir -p $D
cd $REPO
ONLY=""; [ -n "$SMW_ONLY" ] && ONLY="--only=$SMW_ONLY"
python -m games.smw.generate $D/smw_assets.dat $ONLY | tail -8
LOCK=/d/n64work/smw/build.lock
for i in $(seq 1 600); do mkdir $LOCK 2>/dev/null && break; sleep 2; done
trap 'rmdir $LOCK 2>/dev/null' EXIT
bash games/smw/build_web.sh $D/smw_assets.dat $D/site 2>&1 | tail -3
