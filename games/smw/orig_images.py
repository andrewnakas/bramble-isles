"""Originality export: every GFX sheet cut into 16x16 units, index -> fixed grey ramp
(the same mapping for retail and clean, so palettes do not matter), plus each whole sheet.
images/units/<sheet>_<unit>.png and images/sheets/<sheet>.png; empty units are skipped
on both sides (the gate pairs files by name: a unit present on one side only is not compared)."""
import os
import numpy as np
from cleanroom.gfx import png
from cleanroom.snes import lz2, tiles
from games.smw import assetfile as A, layout as L


def sheets(items):
    raw = [lz2.decompress(c) for c in A.unpack_array(items['kGraphicsPtrs'])]
    raw += [items['kGfx32'], items['kGfx33']]
    return {i: tiles.sheet(tiles.decode(r, L.BPP[i])) for i, r in enumerate(raw) if r}


def _rgba(idx, bpp):
    g = (idx.astype(np.int32) * 255 // ((1 << bpp) - 1)).astype(np.uint8)
    return np.dstack([g, g, g, np.full_like(g, 255)])


def export(items, outdir):
    n = 0
    os.makedirs(os.path.join(outdir, 'units'), exist_ok=True)
    os.makedirs(os.path.join(outdir, 'sheets'), exist_ok=True)
    for i, img in sheets(items).items():
        bpp = L.BPP[i]
        png.write(os.path.join(outdir, 'sheets', '%02X.png' % i), _rgba(img, bpp))
        n += 1
        h = img.shape[0] // 16 * 16
        for k, (y, x) in enumerate((y, x) for y in range(0, h, 16) for x in range(0, 128, 16)):
            u = img[y:y + 16, x:x + 16]
            if (u > 0).sum() < 16:
                continue
            png.write(os.path.join(outdir, 'units', '%02X_%03d.png' % (i, k)), _rgba(u, bpp))
            n += 1
    return n
