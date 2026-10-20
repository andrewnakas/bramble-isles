# SNES platform notes (from Super Mario World)

## Formats (code in `cleanroom/snes/`)
- **Tiles** (`tiles.py`): planar 8x8, 2bpp = 16 B, 3bpp = 24 B (planes 0/1 interleaved by row, then plane 2), 4bpp = 32 B.
  `decode -> (n,8,8)` index arrays, `sheet/unsheet` = 16 tiles per row.
- **LC_LZ2** (`lz2.py`): commands direct / byte fill / word fill / increasing fill / back copy (big-endian absolute offset), `0xFF` ends. Our encoder is greedy; size differs from retail, which is fine when the port stores blocks with their own lengths.
- **BRR** (`brr.py`): 9-byte blocks, 16 samples each, 4 filters, end + loop flags in the header. `encode(pcm, loop_block)` picks shift/filter per block by error; first block and the loop block use filter 0 so the loop is self-contained.
- **Palettes**: 15-bit BGR words. Kept at 3 bits per channel.
- **SPC sample bank** (SMW): `[len, addr=0x8000][directory: start, loop per instrument][len, addr=0x8100][BRR blob][tail]`. Sizes and offsets must stay equal (ARAM layout is fixed by the engine).

## Traps
- A sheet's bit depth is not in the file. SMW: GFX00-31 are 3bpp, 28-2B and 2F are 2bpp (layer 3 / fonts), **GFX32 (player) is 4bpp**, GFX33 (animated tiles) is 3bpp. Wrong depth still decodes: check by eye once (dirty room).
- The 2-bit alpha fact = which pixels are index 0. A white-on-transparent logo therefore survives as its silhouette. Background tiles are fully opaque, so only the colour grid describes them.
- Fonts are 8x8 cells: stroke fonts turn to mush, use `cleanroom/gfx/pixfont.py` (5x7 pixel face, thin and bold) and check for exact glyph collisions with the taint scan; a plain bold 5x7 face collided with the retail message font on 23 glyphs, the thin face collides on none.
- Upstream snesrev sources are stored CRLF: normalise before patching.
- Emscripten + SDL2 + ASYNCIFY: SDL sleeps inside `SDL_RenderPresent` behind indirect calls. Either instrument everything (slow, large) or set the hint `SDL_EMSCRIPTEN_ASYNCIFY=0`, use `-sASYNCIFY_IGNORE_INDIRECT=1` and yield only in your own frame wait called directly from `main`.
- Editing Python through shell heredocs corrupts `\n` escapes: use the editor tool.

## Commands (SMW)
```
python -m games.smw.extract_spec            # DIRTY: retail smw_assets.dat -> games/smw/spec
python -m games.smw.generate                # CLEAN: spec + drawings -> D:/n64work/smw/clean/smw_assets.dat
bash games/smw/build_web.sh                 # port + patches + clean assets -> D:/n64work/smw/site
python -m games.smw.taint <dirty.dat> <clean.dat> site/smw.wasm site/smw.js site/index.html
python ports/wasm/serve.py D:/n64work/smw/site 8483
python ports/wasm/headless_shot.py out --base http://localhost:8483/index.html --secs 20,40 --query "keys=8:Enter:0.2,..." --webgl
# deterministic test: keys and screenshots counted in GAME FRAMES, 8 frames per browser frame (wall-clock ?keys= drifts with load)
python ports/wasm/headless_shot.py out --base http://localhost:8483/index.html --secs 999 --wait 45 --webgl   --query "turbo=8&fdump=2790,3060&fkeys=600:Enter:10,720:Enter:10,840:Enter:10,1500:KeyZ:10,1800:KeyZ:10,2400:ArrowLeft:20,2700:KeyZ:10"
#   SMW timeline: 600/720/840 Enter = title, file A, 1 player; 1500 dismiss message; ~2000 overworld; 2400 Left, 2700 B = enter Yoshi's Island 1 (in level at ~2790)
python -m games.smw.look_letters <assets.dat>                # big sprite words assembled from the kept tables
python -m games.smw.look_player <assets.dat> out.png         # every player pose in the player palette
python -m games.smw.look_sheets <assets.dat> out_prefix      # contact sheets; look_zoom / look_ascii for detail
bash games/smw/publish.sh                   # taint gate, then push main + gh-pages
```

## Originality rebuild (2026-10): commands
```
python -m games.smw.make_tables                  # DIRTY: spec/tables.dat = kept structure + zero shape placeholders
python -m games.smw.extract_levels               # DIRTY: spec/levels.json (header settings, exits, ends, rosters, anchors)
python -m games.smw.generate <out.dat>           # CLEAN: modules tiles, sprites, overworld, text_gen, levels, music
SMW_STRICT=1 ...                                 # a failing module is fatal instead of a warning
python -m games.smw.look_level <slot hex> [c0 c1]  # planned block grid of a generated layout (ASCII)
python -m games.smw.lvl_render                   # (library) native port level loader: render(dat, kind, indices)
python -m games.smw.level_reroll                 # DEV: re-seed layouts the geometry gate flags (writes level_seeds.json)
python -m games.smw.levels --anchors             # writes level_anchors.json for the gate
python -m games.smw.export_orig <dat> <dir>      # gate exports (images, text, music, levels, overworld, bg)
python -m cleanroom.originality D:/n64work/smw/orig_dirty D:/n64work/smw/orig_clean games/smw/spec --report ORIGINALITY.md
python -m games.smw.taint <dirty.dat> <clean.dat> > TAINT.md
# dev browser hooks: ?fram=frame (RAM dump), ?fpoke=f:addr:hex, ?ffill=f:addr:len:val, ?bot=devbot.js&levels=105.106
```
Traps: level objects in vertical levels must not cross the 16-column half (they wrap one screen down);
the title-demo level replays inputs, so it must stay pit-free; screen-exit secondary flags read entrance tables
the vanilla asset file does not have; geometry for 2D tile levels is judged at voxel 0.5 tile.
