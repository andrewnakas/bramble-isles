#!/bin/bash
# Run one heavy command (browser run, build) under the shared lock so parallel workers take turns (RAM).
#   bash games/smw/locked.sh python ports/wasm/headless_shot.py ...
LOCK=/d/n64work/smw/build.lock
for i in $(seq 1 900); do mkdir $LOCK 2>/dev/null && break; sleep 2; done
trap 'rmdir $LOCK 2>/dev/null' EXIT
"$@"
