"""Originality export of the background pictures: every BG layer-2 tilemap (unique per table)
drawn through the BG Map16 with BG sheet 0x19 into a 512x432 index image on the fixed grey ramp
(palettes left out, so retail and clean compare by shape only).

    export(items, outdir) -> number of files; writes outdir/images/bg/<table>_<k>.png
Manifest entry: {"retail": "bg/images/bg/*.png", "clean": "bg/images/bg/*.png"}"""
import os, struct
import numpy as np
from cleanroom.gfx import png
from cleanroom.snes import lz2, tiles
from games.smw import assetfile as A

TABLES = ['kLevelData_Layer2', 'kEntranceData_Layer2', 'kChoclateIsland2_Layer2', 'kRollCallData_Layer2',
          'kBufferCreditsBackgrounds_Layer2']


def unrle(src):
    out, i = bytearray(), 0
    while i + 1 < len(src):
        r = src[i]; i += 1
        if r & 0x80:
            out += bytes([src[i]]) * ((r & 0x7F) + 1); i += 1
        else:
            out += src[i:i + r + 1]; i += r + 1
        if i + 1 >= len(src) or (src[i] == 0xFF and src[i + 1] == 0xFF):
            break
    return bytes(out)


def export(items, outdir):
    raw = [lz2.decompress(c) for c in A.unpack_array(items['kGraphicsPtrs'])]
    t = tiles.decode(raw[0x19], 3)[:128]
    m16 = items['kMap16Data'][0x1100:]
    od = os.path.join(outdir, 'images', 'bg')
    os.makedirs(od, exist_ok=True)
    n = 0
    for tb in TABLES:
        arr = A.unpack_array(items[tb])
        flags = items[tb + '_IsBg']
        seen = set()
        for k, blob in enumerate(arr):
            if k >= len(flags) or not (flags[k] & 2) or not blob or bytes(blob) in seen:
                continue
            seen.add(bytes(blob))
            lo = unrle(blob)
            hi = flags[k] >> 4
            img = np.zeros((432, 512), np.uint8)
            for scr in range(2):
                for r in range(27):
                    for c in range(16):
                        i = scr * 432 + r * 16 + c
                        if i >= len(lo):
                            continue
                        blk = (lo[i] | hi << 8) & 0x1FF
                        w = struct.unpack_from('<4H', m16, 8 * blk)
                        for q, (dy, dx) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
                            tn = w[q] & 0x3FF
                            tt = t[tn - 0x100] if 0x100 <= tn < 0x180 else np.zeros((8, 8), np.uint8)
                            if w[q] & 0x4000: tt = tt[:, ::-1]
                            if w[q] & 0x8000: tt = tt[::-1]
                            y0, x0 = r * 16 + dy, (scr * 16 + c) * 16 + dx
                            img[y0:y0 + 8, x0:x0 + 8] = tt
            g = (img.astype(np.int32) * 255 // 7).astype(np.uint8)
            png.write(os.path.join(od, '%s_%03d.png' % (tb[1:].split('_')[0] + tb.split('_')[-1], k)),
                      np.dstack([g, g, g, np.full_like(g, 255)]))
            n += 1
    return n
