"""Dev (dirty or clean): contact sheets of the GFX files in an smw_assets.dat, index-coloured."""
import sys
import numpy as np
from games.smw import assetfile as A
from cleanroom.snes import lz2, tiles
from cleanroom.gfx import png

PAL = np.array([[70, 70, 90], [255, 255, 255], [0, 0, 0], [240, 190, 120], [220, 60, 40], [60, 110, 230], [70, 190, 80], [250, 220, 60],
                [128, 128, 128], [255, 128, 0], [128, 0, 255], [0, 255, 255], [255, 0, 255], [128, 64, 0], [0, 128, 128], [200, 200, 200]], np.uint8)
BPP = {i: 3 for i in range(0x34)}
BPP.update({0x28: 2, 0x29: 2, 0x2A: 2, 0x2B: 2, 0x2F: 2})


def sheets(path):
    it = dict(A.read(path))
    out = [lz2.decompress(c) for c in A.unpack_array(it['kGraphicsPtrs'])]
    return out + [it['kGfx32'], it['kGfx33']]


def main(path, out, scale=2):
    ss = sheets(path)
    for part, ids in enumerate([range(0, 20), range(20, 40), range(40, 50), [50], [51]]):
        ims = [tiles.sheet(tiles.decode(ss[i], BPP[i])) for i in ids]
        h = max(im.shape[0] for im in ims)
        cols = min(5, len(ims))
        rows = -(-len(ims) // cols)
        if len(ims) == 1:  # tall sheet: split into columns of 16 tile rows
            im = ims[0]
            parts = [im[y:y + 128] for y in range(0, im.shape[0], 128)]
            ims, cols, rows, h = parts, len(parts), 1, 128
        canvas = np.full((rows * (h + 4), cols * 132), 8, np.uint8)
        for k, im in enumerate(ims):
            y, x = k // cols * (h + 4), k % cols * 132
            canvas[y:y + im.shape[0], x:x + 128] = im
        rgb = PAL[canvas].repeat(scale, 0).repeat(scale, 1)
        rgba = np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)])
        png.write('%s_%d.png' % (out, part), rgba)
        print(out, part, rgba.shape)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2)
