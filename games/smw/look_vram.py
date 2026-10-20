"""Dev (clean build): turn a PPU snapshot from the page's ?fvram= hook into
  * one PNG per background layer as it is on screen, and
  * a cell map: for every 8x8 screen cell of each layer, which sheet tile of the CLEAN asset file is shown
    there and how it is flipped. Tilemaps are layout facts, so the map tells us where to draw a picture
    (title logo, signs) so that it comes out assembled on screen.

    python -m games.smw.look_vram <headless out dir> <k> <out prefix> [clean assets.dat]
"""
import sys, os, re, json, base64
import numpy as np
from games.smw import layout as L
from games.smw.look_sheets import sheets
from cleanroom.snes import tiles
from cleanroom.gfx import png


def load(outdir, k):
    parts = []
    for line in open(os.path.join(outdir, 'console.txt'), encoding='utf-8', errors='replace'):
        m = re.match(r'VRAM:%d:(.*)' % k, line.strip())
        if m and m.group(1) != 'END':
            parts.append(m.group(1))
    b = base64.b64decode(''.join(parts))
    reg = b[:32]
    vram = np.frombuffer(b[32:32 + 0x10000], '<u2')
    cg = np.frombuffer(b[32 + 0x10000:32 + 0x10200], '<u2').astype(np.int32)
    rgb = (np.stack([cg & 31, cg >> 5 & 31, cg >> 10 & 31], -1) * 255 // 31).astype(np.uint8)
    return reg, vram, rgb


def layer_cells(reg, vram, layer):
    """-> (28, 33) arrays: tile number, palette, flips; plus pixel scroll remainder and bpp."""
    mode = reg[0] & 7
    bpp = 4 if layer < 2 else 2
    sc = reg[2 + layer]
    tm = (sc & 0xFC) << 8
    wide, tall = sc & 1, sc & 2
    hs = int.from_bytes(reg[8 + 2 * layer:10 + 2 * layer], 'little') & 0x3FF
    vs = int.from_bytes(reg[16 + 2 * layer:18 + 2 * layer], 'little') & 0x3FF
    ents = np.zeros((29, 33), np.int32)
    for cy in range(29):
        for cx in range(33):
            x, y = (hs // 8 + cx), ((vs + 1) // 8 + cy)
            a = tm + (y & 31) * 32 + (x & 31)
            if wide and (x & 32):
                a += 0x400
            if tall and (y & 32):
                a += 0x800 if wide else 0x400
            ents[cy, cx] = vram[a & 0x7FFF]
    base = (int.from_bytes(reg[6:8], 'little') >> (4 * layer) & 15) << 12
    return ents, base, bpp, hs % 8, (vs + 1) % 8


def vram_tile(vram, base, n, bpp):
    w = vram[(base + n * 4 * bpp) & 0x7FFF:][:4 * bpp]
    return tiles.decode(w.astype('<u2').tobytes(), bpp)[0]


def main(outdir, k, prefix, dat='D:/n64work/smw/clean/smw_assets.dat'):
    reg, vram, rgb = load(outdir, int(k))
    ss = sheets(dat)
    look = {}
    for i, s in enumerate(ss):
        px = tiles.decode(s, L.BPP[i])
        for t in range(len(px)):
            for f in range(4):
                p = px[t]
                if f & 1:
                    p = p[:, ::-1]
                if f & 2:
                    p = p[::-1]
                look.setdefault((L.BPP[i] == 2, p.tobytes()), (i, t, f))
    out = {'bgmode': int(reg[0]), 'layers': []}
    for layer in range(3):
        ents, base, bpp, fx, fy = layer_cells(reg, vram, layer)
        img = np.zeros((29 * 8, 33 * 8, 3), np.uint8)
        cells, cache = [], {}
        for cy in range(29):
            row = []
            for cx in range(33):
                e = int(ents[cy, cx])
                n, pal, hf, vf = e & 0x3FF, e >> 10 & 7, e >> 14 & 1, e >> 15 & 1
                if n not in cache:
                    cache[n] = vram_tile(vram, base, n, bpp)
                t = cache[n]
                hit = look.get((bpp == 2, t.tobytes())) if t.any() else None
                if hit:                       # sheet tile shown here, with the flip that maps sheet -> screen
                    row.append([hit[0], hit[1], hit[2] ^ (hf | vf << 1), pal])
                else:
                    row.append(None)
                p = t[:, ::-1] if hf else t
                p = p[::-1] if vf else p
                col = rgb[(pal * (16 if bpp == 4 else 4) + p) & 255]
                col[p == 0] = (40, 40, 60)
                img[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = col
            cells.append(row)
        out['layers'].append({'fx': fx, 'fy': fy, 'bpp': bpp, 'cells': cells})
        big = img.repeat(2, 0).repeat(2, 1)
        png.write('%s_bg%d.png' % (prefix, layer + 1), np.dstack([big, np.full(big.shape[:2], 255, np.uint8)]))
        nm = sum(1 for r in cells for c in r if c)
        print('bg%d: %dbpp, scroll frac (%d,%d), %d of %d cells matched to sheet tiles' % (layer + 1, bpp, fx, fy, nm, 29 * 33))
    json.dump(out, open(prefix + '.json', 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main(*sys.argv[1:])
