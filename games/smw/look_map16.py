"""Render Map16 tables of an smw_assets.dat as a contact sheet (layer tiles as the game would
show them, animated tiles at frame 0).
    python -m games.smw.look_map16 <assets.dat> <out.png> [tilesets, e.g. 0,1,3,5] [fgpal] [bg]
'bg' renders the background Map16 (+0x1100) and the first level BG tilemaps instead."""
import sys, struct
import numpy as np
from PIL import Image
from games.smw import assetfile as A, blocks as B
from cleanroom.snes import lz2, tiles as TL

SLOTS = [(0x60, 0), (0x64, 1), (0x68, 2), (0x74, 3), (0xEA, 4), (0x50, 6), (0x54, 7), (0x58, 8), (0x5C, 9),
         (0x78, 10), (0x7C, 11), (0xDA, 12), (0x6C, 13)]
TSET = [(0x70, 14), (0x4C, 15), (0x44, 16), (0x48, 17), (0x40, 18)]
OFS = [0x0, 0x5, 0xa, 0xf, 0x14, 0x14, 0x19, 0x14, 0xa, 0x14, 0, 5, 0, 0x14]
PTR = [0x8b70, 0xbc00, 0xc800, 0xd400, 0xe300, 0xe300, 0xc800, 0x8b70, 0xc800, 0xd400, 0xd400, 0xd400, 0x8b70, 0xe300, 0xd400]


def cols(v):
    w = np.frombuffer(v, '<u2').astype(np.int32)
    return np.stack([w & 31, w >> 5 & 31, w >> 10 & 31], -1) * 255 // 31


def vram(it, ts):
    raw = [lz2.decompress(c) for c in A.unpack_array(it['kGraphicsPtrs'])]
    v = np.zeros((0x200, 8, 8), np.uint8)
    for k, s in enumerate(B.SHEETS[ts]):
        t = TL.decode(raw[s], 3)
        v[k * 128:k * 128 + len(t)] = t[:128]
    g33 = TL.decode(it['kGfx33'], 3)
    fd = struct.unpack('<%dH' % (len(it['kLevelTileAnimations_FrameData']) // 2), it['kLevelTileAnimations_FrameData'])
    for dst, v3 in SLOTS + [(d, s + OFS[ts % 14]) for d, s in TSET]:
        n = (fd[v3 * 4] - 0x7D00) // 32
        if n < 0:
            continue
        if dst == 0x80:
            continue
        for k in range(4):
            v[dst + k] = g33[n + k]
    return v


def cgram(it, fgpal=0, bgpal=0):
    pal = np.zeros((8, 8, 3), np.int32)
    pal[:, 1] = 248
    bg = cols(it['kGlobalPalettes_Background'])[bgpal * 12:bgpal * 12 + 12]
    fg = cols(it['kGlobalPalettes_Foreground'])[fgpal * 12:fgpal * 12 + 12]
    ob = cols(it['kGlobalPalettes_Objects'])
    pal[0, 2:8], pal[1, 2:8] = bg[:6], bg[6:]
    pal[2, 2:8], pal[3, 2:8] = fg[:6], fg[6:]
    for r in range(4):
        pal[4 + r, 2:8] = ob[r * 6:r * 6 + 6]
    sky = cols(it['kGlobalPalettes_Sky'])[0]
    return pal, sky


def draw_block(words, v, pal, sky):
    img = np.zeros((16, 16, 3), np.uint8)
    img[:] = sky
    for k, (dy, dx) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
        w = words[k]
        t = v[w & 0x1FF] if (w & 0x3FF) < 0x200 else np.zeros((8, 8), np.uint8)
        if w & 0x4000: t = t[:, ::-1]
        if w & 0x8000: t = t[::-1]
        p = pal[(w >> 10) & 7]
        sub = img[dy:dy + 8, dx:dx + 8]
        m = t > 0
        sub[m] = p[t[m]]
    return img


def table_words(it, ts, b):
    mask = [0xff] * 14 + [0xe0] + [0] * 17 + [0xfe, 0x0, 0x7f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xe0, 0x0, 0x0, 0x3] + [0xff] * 18
    c, t = 0x8000, PTR[ts]
    for x in range(b + 1):
        if mask[x >> 3] & (0x80 >> (x & 7)):
            a = c; c += 8
        else:
            a = t; t += 8
    for base, name in ((0xe300, 'kMap16Data_GhostHouse'), (0xd400, 'kMap16Data_Underground'), (0xc800, 'kMap16Data_Rope'),
                       (0xbc00, 'kMap16Data_Castle'), (0x8000, 'kMap16Data')):
        if a >= base:
            return struct.unpack_from('<4H', it[name], a - base)


def bg_pictures(it, out, pairs):
    """pairs: list of (level index, tileset, bgpal)."""
    from games.smw.tiles_bg import unrle
    arr = A.unpack_array(it['kLevelData_Layer2'])
    panels = []
    for lv, ts, bp in pairs:
        v = vram(it, ts)
        pal, sky = cgram(it, 0, bp)
        sky = cols(it['kGlobalPalettes_Sky'])[[0, 2, 4, 5][len(panels) % 4]]
        lo = unrle(arr[lv])
        hi = it['kLevelData_Layer2_IsBg'][lv] >> 4
        img = np.zeros((27 * 16, 32 * 16, 3), np.uint8)
        for scr in range(2):
            for r in range(27):
                for c in range(16):
                    blk = lo[scr * 432 + r * 16 + c] | hi << 8
                    words = struct.unpack_from('<4H', it['kMap16Data'], 0x1100 + 8 * blk)
                    img[r * 16:r * 16 + 16, (scr * 16 + c) * 16:(scr * 16 + c) * 16 + 16] = draw_block(words, v, pal, sky)
        panels.append(img[100:])
    rows = [np.concatenate(panels[i:i + 2], 1) for i in range(0, len(panels), 2)]
    full = np.concatenate(rows, 0)
    Image.fromarray(full).save(out)
    print('wrote', out, full.shape)


def main(path, out, tsets='0,1,3,5', fgpal=None, mode='fg'):
    it = dict(A.read(path))
    if mode == 'bgpic':
        pairs = [tuple(int(v) for v in p.split(':')) for p in tsets.split(',')]
        return bg_pictures(it, out, pairs)
    tss = [int(x) for x in tsets.split(',')]
    panels = []
    for ts in tss:
        v = vram(it, ts)
        fp = int(fgpal) if fgpal is not None else {0: 0, 1: 7, 2: 4, 3: 1, 4: 5, 5: 4, 12: 6}.get(ts, 0)
        pal, sky = cgram(it, fp, {0: 0, 1: 3, 3: 1, 5: 6}.get(ts, 0))
        img = np.zeros((16 * 18, 32 * 18, 3), np.uint8)
        img[:] = 40
        for b in range(0x200):
            if mode == 'bg':
                words = struct.unpack_from('<4H', it['kMap16Data'], 0x1100 + 8 * b)
            else:
                words = table_words(it, ts, b)
            y, x = b // 32 * 18, b % 32 * 18
            img[y:y + 16, x:x + 16] = draw_block(words, v, pal, sky)
        panels.append(img)
    full = np.concatenate(panels, 0)
    Image.fromarray(full).resize((full.shape[1] * 2, full.shape[0] * 2), Image.NEAREST).save(out)
    print('wrote', out, full.shape)


if __name__ == '__main__':
    main(*sys.argv[1:])
