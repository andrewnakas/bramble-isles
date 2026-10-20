# Taint report: Bramble Isles (smw)

Command: `python -m games.smw.taint D:/n64work/smw/dirty/smw_assets.dat D:/n64work/smw/clean/smw_assets.dat site/smw.wasm site/smw.js site/index.html site/smw.data` (2026-10-19). Raw bytes of every regenerated entry (packed arrays element by element), LZ2 / planar / pixel forms of all sheets, palettes, BRR + PCM, and the shipped files; runs inside the wasm that come from static tables of the port C source are explained as compiled code.

```
taint: 1444 clean streams vs 1444 retail streams; 13 with short coincidental matches; 0 failing (run >= 32 B)
pixels: 0 of 5869 informative 8x8 tiles identical (0.00%, limit 2%) []; 0 of 1521 16x16 units identical
shipped: 4 files scanned, 0 failing
TOTAL failing: 0
```
