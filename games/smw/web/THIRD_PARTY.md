# BRAMBLE ISLES: credits and third-party notices

BRAMBLE ISLES is an original platformer built on the **snesrev/smw decomp** (a C reimplementation of the game logic).
The program in `smw.wasm` / `smw.js` is compiled from that source. Every level, map, picture, palette, tune, sound
effect, instrument sample and line of text in `smw.data` was generated for this project; no data from the original
game ships, and no ROM is needed or read. Clean-room pipeline: https://github.com/andrewnakas/smw-cleanroom (MIT).

## Third-party software in this build

| Component | Files | Licence | Source |
|---|---|---|---|
| snesrev/smw (C reimplementation; includes parts of LakeSnes by elzo_d) | `smw.wasm`, `smw.js` | MIT, Copyright (c) 2023 snesrev, (c) 2021 elzo_d (`LICENSE.smw.txt`) | https://github.com/snesrev/smw |
| SDL2 (Emscripten port) | `smw.wasm`, `smw.js` | zlib | https://www.libsdl.org |
| Emscripten runtime (JS glue, libc, file system) | `smw.js`, `smw.wasm` | MIT / University of Illinois-NCSA | https://emscripten.org |
