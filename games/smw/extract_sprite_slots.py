"""DIRTY ROOM. Structural facts about the sprite / font / layer-3 sheets for games/smw/sprites.py.

    python -m games.smw.extract_sprite_slots [retail smw_assets.dat]

Writes games/smw/spec/sprite_slots.json with, per sheet the `sprites` worker owns:
  bpp, bytes            sheet size and bit depth
  used                  hex bitmap, one bit per 8x8 tile: does the tile show anything
  units                 per 16x16 unit: null (empty) or [x0, y0, x1, y1] bounding box of shown pixels
  opaque                units that are (almost) fully covered (pictures, not figures)
and games/smw/spec/sprite_struct.json: stripe / layer-3 cell positions and piece vocabulary
(spr_stripes.facts), free layer-3 tile pools, the title stripe's cell positions, empty Mode-7 blocks.
No pixels, outlines, colours or grids are written: only sizes, boxes and which slots are in use.
"""
import json
import os
import sys

import numpy as np

from games.smw import assetfile as A, layout as L
from cleanroom.snes import lz2, tiles

SPEC = os.path.join(os.path.dirname(__file__), 'spec')
OWN = ([*range(0x00, 0x07), 0x09, 0x0A, 0x0B, *range(0x10, 0x14), *range(0x20, 0x28), 0x2D, 0x2E, 0x30, 0x31,
        0x28, 0x29, 0x2A, 0x2B, 0x2F, 0x32, 0x33])


def sheet_facts(raw, bpp):
    img = tiles.sheet(tiles.decode(raw, bpp))
    if img.shape[0] % 16:
        img = np.vstack([img, np.zeros((16 - img.shape[0] % 16, 128), np.uint8)])
    shown = img > 0
    nt = len(raw) // tiles.TILE_BYTES[bpp]
    used = [bool(shown[t // 16 * 8:t // 16 * 8 + 8, t % 16 * 8:t % 16 * 8 + 8].any()) for t in range(nt)]
    bits = np.packbits(np.array(used + [False] * (-len(used) % 8), np.uint8)).tobytes().hex()
    units, opaque = [], []
    nu = img.shape[0] // 16 * 8
    for k in range(nu):
        y, x = k // 8 * 16, k % 8 * 16
        s = shown[y:y + 16, x:x + 16]
        if s.sum() < 2:
            units.append(None)
            continue
        ys, xs = np.nonzero(s)
        units.append([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())])
        if s.mean() > 0.9:
            opaque.append(k)
    return {'bpp': bpp, 'bytes': len(raw), 'used': bits, 'units': units, 'opaque': opaque}


def main(path):
    it = dict(A.read(path))
    raw = [lz2.decompress(c) for c in A.unpack_array(it['kGraphicsPtrs'])] + [it['kGfx32'], it['kGfx33']]
    spec = {'%02X' % i: sheet_facts(raw[i], L.BPP[i]) for i in OWN}
    json.dump(spec, open(os.path.join(SPEC, 'sprite_slots.json'), 'w'), separators=(',', ':'))
    # stripe / layer-3 / Mode-7 structure (positions, piece vocabulary, free tile pools, empty blocks)
    from games.smw import spr_stripes, spr_text
    st, l3 = A.unpack_array(it['kLoadStripeImagePtrs']), A.unpack_array(it['kLayer3ImagePtrs'])
    m7 = it['kInitializeMode7TilemapsAndPalettes_TilemapData']
    struct = {'stripes': spr_stripes.facts(st, l3), 'pools': spr_text.pools_from(it),
              'title_cells': sorted(spr_text.cell_map(st[1])),
              'mode7': {'bytes': len(m7), 'blank_blocks': [b for b in range(len(m7) // 16) if set(m7[b * 16:b * 16 + 16]) == {0xFF}]}}
    json.dump(struct, open(os.path.join(SPEC, 'sprite_struct.json'), 'w'), separators=(',', ':'))
    print('sheets %d, units in use %d' % (len(spec), sum(sum(u is not None for u in s['units']) for s in spec.values())))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'D:/n64work/smw/dirty/smw_assets.dat')
