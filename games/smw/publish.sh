#!/bin/bash
# Taint gate, then push the source repo (main) and the site (gh-pages).
set -e
REPO=$(cd "$(dirname "$0")/../.." && pwd)
W=/d/n64work/smw
S=$W/site
cd $REPO
python games/smw/web/make_page.py $S --publish             # page without dev hooks + THIRD_PARTY.md + LICENSE.smw.txt
python -m games.smw.taint $W/dirty/smw_assets.dat $W/clean/smw_assets.dat $S/smw.wasm $S/smw.js $S/index.html | tee $W/taint.txt
grep -q "TOTAL failing: 0" $W/taint.txt
cmp $W/clean/smw_assets.dat $W/build/fs/smw_assets.dat          # the site holds the scanned file
git remote get-url origin >/dev/null 2>&1 || git remote add origin https://github.com/andrewnakas/smw-cleanroom.git
git push -q origin main
P=$W/pages
rm -rf $P && mkdir -p $P && cp -r $S/. $P/
NAME=$(git config user.name); MAIL=$(git config user.email)
cd $P
git init -q -b gh-pages
git add -A
git -c user.name="$NAME" -c user.email="$MAIL" commit -qm "Site build $(date +%F_%H%M)"
git push -q -f https://github.com/andrewnakas/smw-cleanroom.git gh-pages
echo "published: $(ls $P | tr '\n' ' ')"
