"""Dev: zoomed view of chosen sheets with an 8px tile grid. usage: look_zoom assets.dat out.png scale id[,id..]"""
import sys
import numpy as np
from games.smw import layout as L
from games.smw.look_sheets import sheets, PAL
from cleanroom.snes import tiles
from cleanroom.gfx import png


def main(path, out, scale, ids, rows=None):
    ss = sheets(path)
    ims = []
    for i in ids:
        im = tiles.sheet(tiles.decode(ss[i], L.BPP[i]))
        if rows:
            im = im[rows[0] * 8:rows[1] * 8]
        rgb = PAL[im].repeat(scale, 0).repeat(scale, 1)
        rgb[::8 * scale] = (rgb[::8 * scale] // 2 + 60)
        rgb[:, ::8 * scale] = (rgb[:, ::8 * scale] // 2 + 60)
        rgb[::16 * scale] = (255, 0, 255)
        rgb[:, ::16 * scale] = (255, 0, 255)
        ims.append(rgb)
        ims.append(np.full((6, rgb.shape[1], 3), 128, np.uint8))
    rgb = np.vstack(ims)
    png.write(out, np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)]))
    print(out, rgb.shape)


if __name__ == '__main__':
    a = sys.argv
    main(a[1], a[2], int(a[3]), [int(x, 16) for x in a[4].split(',')],
         [int(x) for x in a[5].split('-')] if len(a) > 5 else None)
