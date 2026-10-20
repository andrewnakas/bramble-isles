# Bramble Isles

An original side-scrolling platformer built on the [snesrev/smw](https://github.com/snesrev/smw) decomp
(the community C reimplementation of the SNES game, MIT), compiled to WebAssembly with Emscripten + SDL2.

Only the game **code** comes from the decomp. Every level, the overworld map, all graphics and palettes, all
music, sound effects and instrument samples, and every line of text are new and are produced by the generators
in this repository. Kept from the original are structural facts and gameplay anchors only: sizes, counts,
formats, timing, string budgets, level entrance/exit positions, overworld node and warp cells, and which enemy
types a level may use.

Hero TOBI rides the gecko ZEEP across the Bramble Isles to free QUEEN MARLA from KING GRUMBOLT.

## How it is built

- `games/smw/generate.py` writes the port's asset file from `games/smw/spec/tables.dat` (kept structural tables
  plus zero-filled shape placeholders) and the module generators:
  `tiles` (level tile kits, Map16, backgrounds), `sprites` (TOBI, ZEEP, cast, fonts, title, Mode-7 bosses),
  `overworld` (routes, terrain, reveal tiles), `text_gen` (all text), `levels` (seeded level generator),
  `music` (N-SPC songs from `cleanroom.audio.compose`, SFX, synthetic instruments).
- `games/smw/build_web.sh` builds the port with the clean asset file.
- Gates, both must report 0 failing (`ORIGINALITY.md`, `TAINT.md`):
  - `python -m games.smw.export_orig <dat> <dir>` (dirty and clean) then
    `python -m cleanroom.originality <dirty dir> <clean dir> games/smw/spec` (music n-grams + contour, text runs +
    names, level/overworld geometry, image hashes/SSIM);
  - `python -m games.smw.taint <dirty.dat> <clean.dat>` (byte runs of every regenerated entry, tiles, pixels, samples).
- `games/smw/lvl_render.c` runs the port's own level loader natively to check that each generated layout loads as
  planned; `levels.check_course` checks every course is passable.

No ROM, no retail graphics, levels, music or text are in the published site. Dirty-room extractors
(`extract_*.py`, `make_tables.py`) read a retail-derived asset file only to write structural specs.

Controls: arrows move, Z jump (B), X spin jump (A), A/S run (Y/X), C/V L/R, Enter Start, Right Shift Select.
Gamepads and touch work.
