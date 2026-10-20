"""Overworld decoder/renderer for any smw_assets.dat (retail-derived or clean).

Used by the overworld exporter (orig_overworld) and for looking at our own map.
Implements the port's data formats only (smw_04.c): layer-2 RLE tilemap, layer-2
event tiles, layer-1 Map16 grid, OW palettes and the 3bpp->4bpp upload rules.

    python -m games.smw.ow_render <assets.dat> <out_prefix> [all|none]
"""
import sys

import numpy as np

from games.smw import assetfile as A
from cleanroom.snes import lz2, tiles as T

W = 64          # layer-2 tiles per row (each half: main map / submaps)
NEV = 111


# ------------------------------------------------------------------ formats
def rle_decode(src, length):
    """BufferOverworldLayer2Tilemap: -> bytes for every 2nd byte slot (length/2 values)."""
    out = bytearray()
    j = 0
    while len(out) * 2 < length:
        r = src[j]
        if r & 0x80:
            out += bytes([src[j + 1]]) * ((r & 0x7f) + 1)
            j += 2
        else:
            out += src[j + 1:j + 2 + r]
            j += r + 2
    return bytes(out[:length // 2])


def rle_encode(data):
    """Inverse of rle_decode (runs >= 3 become fills)."""
    out = bytearray()
    i, n = 0, len(data)
    lit = bytearray()

    def flush():
        while lit:
            c = lit[:128]
            out.append(len(c) - 1)
            out.extend(c)
            del lit[:128]
    while i < n:
        r = 1
        while i + r < n and data[i + r] == data[i] and r < 128:
            r += 1
        if r >= 3:
            flush()
            out += bytes([0x80 | (r - 1), data[i]])
            i += r
        else:
            lit.append(data[i])
            i += 1
    flush()
    return bytes(out)


def evprop_decode(src):
    """LoadOverworldLayer2AndEventsTilemaps_04DD57 (until a 0xFFFF word)."""
    out = bytearray()
    j = 0
    while True:
        r = src[j]
        j += 1
        if r & 0x80:
            out += bytes([src[j]]) * ((r & 0x7f) + 1)
            j += 1
        else:
            out += src[j:j + r + 1]
            j += r + 1
        if src[j] == 0xff and src[j + 1] == 0xff:
            return bytes(out)


def evprop_encode(data):
    return rle_encode(data) + b'\xff\xff'


def l2_offset(tx, ty):
    """(tile x 0..63, tile y 0..127) -> byte offset in ow_layer2_tiles (0x4000)."""
    return ((ty & 31) * 64 + (tx & 31) * 2) | (tx & 32) << 6 | (ty & 32) << 7 | (ty & 64) << 7


def l2_pos(off):
    tx = (off >> 1) & 31 | (off >> 6) & 32
    ty = (off >> 6) & 31 | (off >> 7) & 32 | (off >> 7) & 64
    return tx, ty


def l1_index(x, y):
    """(map16 x 0..31, y 0..63 with 32.. = submaps) -> index in the 0x800 layer-1 grid."""
    return (x & 15) | (x & 16) << 4 | (y & 15) << 4 | (y & 16) << 5 | (y & 32) << 5


def l1_grid(blob):
    g = np.zeros((64, 32), np.uint8)
    for y in range(64):
        for x in range(32):
            g[y, x] = blob[l1_index(x, y)]
    return g


def l1_blob(g):
    b = bytearray(0x800)
    for y in range(64):
        for x in range(32):
            b[l1_index(x, y)] = int(g[y, x])
    return bytes(b)


def u16(b):
    return np.frombuffer(b, '<u2').astype(np.int64)


# ------------------------------------------------------------------ state
class OW:
    def __init__(self, items):
        self.it = items
        t = rle_decode(items['kLoadOverworldLayer2AndEventsTilemaps_OverworldLayer2Tilemap'], 0x4000)
        p = rle_decode(items['kLoadOverworldLayer2AndEventsTilemaps_OverworldLayer2Tilemap_Prop'], 0x4000)
        self.l2 = bytearray(0x4000)
        self.l2[0::2], self.l2[1::2] = t, p
        self.evt = items['kOverworldLayer2EventTilemap_Tiles']
        self.evp = evprop_decode(items['kOverworldLayer2EventTilemap_Prop'])
        self.ent = u16(items['kLayer2EventData_TileEntries']).reshape(-1, 2)
        self.ptr = u16(items['kLayer2EventData_Ptrs_04E359'])
        self.l1 = l1_grid(items['kLoadOverworldLayer1AndEvents_DATA_0CF7DF'])
        self.m16 = u16(items['kMap16Data_OverworldLayer1']).reshape(-1, 4)

    def put_event_tile(self, j, r4):
        """BufferEventTileToLayer2Tilemap_Entry2."""
        n = 2 if j >= 0x900 else 6
        for row in range(n):
            v = r4
            for _ in range(n):
                self.l2[v] = self.evt[j]
                self.l2[v + 1] = self.evp[j]
                v += 2
                j += 1
                if v & 0x3f == 0:
                    v = ((v - 1) & 0xffc0) + 0x800
            old = r4
            r4 += 64
            if r4 & 0x7c0 == 0:
                r4 = (old & 0xf83f) + 0x1000

    def apply_events(self, events):
        lay = self.it['kChangingLayer1OverworldTiles_Layer1TileLocation']
        loc = u16(lay)
        frm = list(self.it['kChangingLayer1OverworldTiles_TilesThatChange'])
        to = list(self.it['kChangingLayer1OverworldTiles_TilesToBecome'])
        flat = bytearray(l1_blob(self.l1))
        for e in sorted(events):
            for k in range(self.ptr[e], self.ptr[e + 1]):
                self.put_event_tile(*self.ent[k])
            if e < len(loc):
                v = flat[loc[e]]
                if v in frm:
                    k = len(frm) - 1 - frm[::-1].index(v)
                    flat[loc[e]] = to[k]
            self.silent(e, flat)
        self.l1 = l1_grid(bytes(flat))

    def silent(self, e, flat):
        ev = self.it['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles']
        lay = self.it['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TileLayer']
        num = u16(self.it['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TileNum'])
        loc = u16(self.it['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TilemapLocation'])
        for i in range(len(ev)):
            if ev[i] == e:
                if lay[i] & 1:
                    self.put_event_tile(num[i], loc[i])
                else:
                    flat[loc[i]] = num[i] & 0xff


# ------------------------------------------------------------------ graphics
def sheet_tiles(items, i):
    arr = A.unpack_array(items['kGraphicsPtrs'])
    return T.decode(lz2.decompress(arr[i]), 3)


def vram_tiles(items):
    """BG tiles 0x000-0x1FF as they are uploaded on the overworld (4bpp indices)."""
    out = np.zeros((512, 8, 8), np.uint8)
    for slot, sh in enumerate([0x1c, 0x1d, 0x08, 0x1e]):
        t = sheet_tiles(items, sh)[:128]
        if sh in (0x08, 0x1e):
            t = np.where(t > 0, t | 8, 0)
        out[slot * 128:slot * 128 + len(t)] = t
    # animated tiles 0x75-0x7F: first frame of each slot (from GFX1E, plane 3 = 0)
    g1e = sheet_tiles(items, 0x1e)
    wat = u16(items['kOwTileAnimations_WaterTileNumbers'])
    num = u16(items['kOwTileAnimations_TileNumbers'])
    srcs = [(a - 0xad00) // 24 for a in wat] + [(num[8 * s] - 0xad00) // 24 for s in range(8)]
    for k, s in enumerate(srcs):
        if 0 <= s < len(g1e):
            out[0x75 + k] = g1e[s]
    return out


def palette(items, area=1, passed=False):
    pal = np.zeros((256, 3), np.uint8)

    def load(name, dst, w, rows, off=0):
        c = T.bgr555_to_rgb(u16(items[name]))
        for r in range(rows):
            for k in range(w):
                if off < len(c):
                    pal[dst + 16 * r + k] = c[off]
                off += 1
    load('kGlobalPalettes_OW_AreasPassed' if passed else 'kGlobalPalettes_OW_Areas', 65, 7, 4, area * 28)
    load('kGlobalPalettes_OW_Objects', 41, 7, 6)
    load('kGlobalPalettes_OW_Sprites', 129, 7, 8)
    return pal


SUBMAP_AREA = {0: 1, 1: 0, 2: 3, 3: 4, 4: 3, 5: 5, 6: 2}      # submap -> kGlobalPalettes_OW_Areas set (tileset order)


def draw_entry(img, prio_mask, tl, w, x, y, vt, pal, want_prio):
    t = (w & 0x3ff)
    p = (w >> 10) & 7
    pr = (w >> 13) & 1
    if pr != want_prio or t >= 512:
        return
    px = vt[t]
    if w & 0x4000:
        px = px[:, ::-1]
    if w & 0x8000:
        px = px[::-1]
    m = px > 0
    sub = img[y:y + 8, x:x + 8]
    sub[m] = pal[p * 16 + px[m]]


def render(ow, items, half=0, area=None):
    """-> RGB image 512x512 of the main map (half 0) or the submap region (half 1)."""
    vt = vram_tiles(items)
    pal = palette(items, SUBMAP_AREA[0] if area is None else area)
    img = np.zeros((512, 512, 3), np.uint8)
    img[:] = pal[0]
    l2 = ow.l2
    for pr in (0, 1):
        for ty in range(64):
            for tx in range(64):
                o = l2_offset(tx, ty + 64 * half)
                draw_entry(img, None, None, l2[o] | l2[o + 1] << 8, tx * 8, ty * 8, vt, pal, pr)
        for y in range(32):
            for x in range(32):
                v = ow.l1[y + 32 * half, x]
                if v >= len(ow.m16):
                    continue
                q = ow.m16[v]
                for k, (dx, dy) in enumerate([(0, 0), (0, 8), (8, 0), (8, 8)]):
                    draw_entry(img, None, None, int(q[k]), x * 16 + dx, y * 16 + dy, vt, pal, pr)
    return img


def main(dat, out, which='all'):
    from cleanroom.gfx import png
    items = dict(A.read(dat))
    ow = OW(items)
    if which == 'all':
        ow.apply_events(range(NEV))
    for h in (0, 1):
        img = render(ow, items, h)
        png.write('%s_%d.png' % (out, h), np.dstack([img, np.full(img.shape[:2], 255, np.uint8)]))
    print('wrote %s_0.png %s_1.png' % (out, out))


if __name__ == '__main__':
    main(*sys.argv[1:])
