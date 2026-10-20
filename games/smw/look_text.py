"""Dev (clean): render every message box, castle line, menu row and the big loading words of an
smw_assets.dat offline with its own fonts -> one contact sheet PNG.

    python -m games.smw.look_text <assets.dat> <out.png>
"""
import struct
import sys

import numpy as np

from cleanroom.gfx import png
from cleanroom.snes import tiles
from games.smw import assetfile as A, textfmt as T
from games.smw.look_sheets import sheets, PAL

INK = np.array([[30, 30, 60], [255, 255, 255], [0, 0, 0], [240, 190, 120], [220, 60, 40], [60, 110, 230],
                [70, 190, 80], [250, 220, 60]], np.uint8)


def layer3_tiles(ss):
    """Layer-3 tile number -> 8x8 index image (sheets 28, 29, 2A, 2B at tiles 0x000-0x1FF)."""
    out = {}
    for base, sid in ((0, 0x28), (0x80, 0x29), (0x100, 0x2A), (0x180, 0x2B)):
        for k, t in enumerate(tiles.decode(ss[sid], 2)):
            out[base + k] = t
    big = tiles.decode(ss[0x2F], 2)        # uploaded over 0xC0-0xFF for the credits / THE END
    big_map = {0xC0 + k: big[k] for k in range(len(big))}
    return out, big_map


def draw_words(words, tl, w=None):
    w = w or len(words)
    img = np.zeros((8, 8 * w), np.uint8)
    for i, word in enumerate(words[:w]):
        t = tl.get(word & 0x3FF)
        if t is None or (word & 0x3FF) == 0xFC:
            continue
        if word & 0x4000:
            t = t[:, ::-1]
        if word & 0x8000:
            t = t[::-1]
        img[:, 8 * i:8 * i + 8] = t
    return img


def main(path, out):
    it = dict(A.read(path))
    ss = sheets(path)
    tl, big = layer3_tiles(ss)
    panels = []
    # message boxes
    b = it['kDisplayMessage_DATA_05A5D9']
    boxes = []
    for a, e in T.msg_slots():
        rows, _ = T.msg_lines(b, a)
        im = np.vstack([draw_words([0x100 | c for c in r] + [0x11F] * (18 - len(r)), tl, 18) for r in rows])
        boxes.append(np.pad(im, 4, constant_values=2))
    for r in range(0, len(boxes), 4):
        row = boxes[r:r + 4]
        row += [np.zeros_like(boxes[0])] * (4 - len(row))
        panels.append(np.hstack([np.pad(x, 2) for x in row]))
    arr = A.unpack_array(it['kLoadStripeImagePtrs'])

    def stripe_rows(idx, tlm=tl):
        out = []
        for i in idx:
            segs, _ = T.stripe_parse(arr[i])
            for s in segs:
                if T.is_layer3(s['addr']) and not s['rle']:
                    out.append(draw_words(s['data'], tlm, 32))
        return out
    # castle text, menus, roll-call names, file select
    castle = []
    for c in range(7):
        castle += stripe_rows([11 + 8 * c + l for l in reversed(range(8))]) + [np.zeros((4, 256), np.uint8)]
    left = np.vstack(castle)
    menu = stripe_rows([4, 6, 10]) + stripe_rows(range(72, 85))
    fs = it['kFileSelectText_EraseFile']
    for off in (0, 0xCB):
        for s in T.stripe_parse(fs[off:])[0]:
            if not s['rle']:
                menu.append(draw_words(s['data'], tl, 32))
    right = np.vstack(menu)
    h = max(left.shape[0], right.shape[0])
    panels.append(np.hstack([np.pad(left, ((0, h - left.shape[0]), (2, 2))), np.pad(right, ((0, h - right.shape[0]), (2, 2)))]))
    # credits (big rows use sheet 2F)
    tm = it['kGameMode1B_EndingCinema_Tilemaps']
    rp = struct.unpack('<%dH' % (len(it['kGameMode1B_EndingCinema_RowPointers']) // 2), it['kGameMode1B_EndingCinema_RowPointers'])
    cr = []
    for p in rp[:140]:
        if tm[p] == 0xFF:
            cr.append(np.zeros((8, 256), np.uint8))
            continue
        n = tm[p + 1]
        ws = struct.unpack_from('<%dH' % (n // 2 + 1), tm, p + 2)
        tlm = dict(tl)
        tlm.update(big)
        im = draw_words(ws, tlm)
        x = tm[p] * 8
        row = np.zeros((8, 256), np.uint8)
        row[:, x:x + im.shape[1]] = im[:, :256 - x]
        cr.append(row)
    cr = np.vstack(cr)
    half = cr.shape[0] // 2
    panels.append(np.hstack([cr[:half], np.zeros((half, 8), np.uint8), cr[half:2 * half]]))
    # loading letters (sheet 0F pieces)
    px = tiles.decode(ss[0x0F], 3)
    src = lambda c: (c & 15) + {0x00: 0, 0x10: 6, 0x40: 2, 0x50: 8}[c & 0xF0]
    Tt, Bt = it['kDrawLoadingLetters_TileData'], it['kDrawLoadingLetters_TileData_BottomTiles']
    TP, BP = it['kDrawLoadingLetters_TileData_TopProp'], it['kDrawLoadingLetters_TileData_BottomProp']

    def cell(c, prop):
        t = px[src(c)]
        if prop & 0x40:
            t = t[:, ::-1]
        if prop & 0x80:
            t = t[::-1]
        return np.minimum(t, 7)
    words = []
    for ks in (list(range(13, -1, -1)), list(range(19, 13, -1)) + list(range(7, -1, -1))):
        cv = np.zeros((16, 8 * len(ks)), np.uint8)
        for n, k in enumerate(ks):
            if Tt[k] < 0x80:
                cv[:8, 8 * n:8 * n + 8] = cell(Tt[k], TP[k])
                cv[8:, 8 * n:8 * n + 8] = cell(Bt[k], BP[k])
        words.append(np.pad(cv, 2))
    W = max(p.shape[1] for p in panels)
    lw = np.hstack(words)
    panels.append(lw)
    canvas = np.vstack([np.pad(p, ((3, 3), (0, W - p.shape[1])), constant_values=0) for p in panels])
    rgb = INK[np.minimum(canvas, 7)].repeat(2, 0).repeat(2, 1)
    png.write(out, np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)]))
    print('look_text ->', out, rgb.shape)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
