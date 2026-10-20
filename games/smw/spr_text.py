"""CLEAN ROOM. Layer-3 sheets (fonts, HUD, pictures), the title logo stripe, the layer-3 pictures,
and the words / numbers that live inside sprite sheets. Part of module `sprites`.

Layer-3 VRAM holds sheets 28, 29, 2A, 2B as tiles 000-1FF (sheet 2F replaces 0C0-0FF for THE END).
What each tile code IS comes from structure only: the game's tilemaps (stripe images, layer-3 images,
the status-bar table in the code) and the character codes the text uses (the charmap, same codes as
before). Every tile is drawn here from nothing:
  * fonts: our "Bramble" face (spr_font) in the cell styles the tilemaps need,
  * status bar: TOBI / KIP name plates, coin, gem, clock, item-box frame,
  * pictures rebuilt whole with our own tiles and our own layout: the title (BRAMBLE ISLES logo,
    braided-vine frame, credit line), the castle gate, castle wall, crusher pillar and rock clusters
    layer-3 images; pictures kept in place (tile slots and tilemap untouched, tiles redrawn): tide
    water, cloud bands, sparkles, the overworld frame, the map arrows.
New glyph codes for text_gen: NEW_CODES.
"""
import numpy as np

from cleanroom.snes import lz2, tiles
from games.smw import assetfile as A
from games.smw import spr_font as FN

L3_SHEETS = (0x28, 0x29, 0x2A, 0x2B)
BASE = {0x28: 0x000, 0x29: 0x080, 0x2A: 0x100, 0x2B: 0x180}
BLANK = 0x0FC                       # empty tile (29:7C) used as "nothing" everywhere
SOLID1 = 0x0FE                      # flat colour-1 fill (29:7E)

# stripe images (kLoadStripeImagePtrs) owned here: 1 = title (rebuilt whole);
# 2 = overworld frame and 7 = map arrows (tilemaps kept, their tiles redrawn in place).
OWN_STRIPES = (1, 2, 5, 7, 8, 9, 67, 68, 69, 70, 85)   # 2.. via spr_stripes
# new glyphs in free slots (layer-3 tile codes), for text_gen's charmap
NEW_CODES = {'box :': 0x0B7, 'menu F': 0x0B8, 'menu J': 0x0B9, 'menu K': 0x0BA, 'menu Q': 0x0BB, 'menu X': 0x0BC}


# ------------------------------------------------------------------ stripe format
def parse(d):
    p, out = 0, []
    while p < len(d) and d[p] != 0xFF:
        addr, f = d[p] << 8 | d[p + 1], d[p + 2]
        n = ((f & 0x3F) << 8 | d[p + 3]) + 1
        if f & 0x40:
            w = d[p + 4] | d[p + 5] << 8
            cells = [w] * (n // 2)
            p += 6
        else:
            cells = [d[p + 4 + 2 * i] | d[p + 5 + 2 * i] << 8 for i in range(n // 2)]
            p += 4 + n
        out.append((addr, bool(f & 0x80), cells))
    return out


def cell_map(d, base=0x5000):
    """{tilemap word offset: cell word} of a stripe (layer-3 tilemap area)."""
    out = {}
    for addr, vert, cells in parse(d):
        if not base <= addr < base + 0x1000:      # other layers' entries
            continue
        a = addr - base
        for n, w in enumerate(cells):
            out[a + (32 * n if vert else n)] = w
    return out


def encode_rows(cells, base=0x5000):
    """cells {offset: word} -> stripe bytes, horizontal runs inside 32-cell rows."""
    out = bytearray()
    keys = sorted(cells)
    i = 0
    while i < len(keys):
        a = keys[i]
        run = [cells[a]]
        while i + len(run) < len(keys) and keys[i + len(run)] == a + len(run) and (a + len(run)) % 32 != 0:
            run.append(cells[a + len(run)])
        n = len(run) * 2 - 1
        addr = base + a
        out += bytes([addr >> 8, addr & 0xFF, (n >> 8) & 0x3F, n & 0xFF])
        for w in run:
            out += bytes([w & 0xFF, w >> 8])
        i += len(run)
    return bytes(out + b'\xff')


# ------------------------------------------------------------------ tile store
class Store:
    def __init__(self):
        self.t = np.zeros((512, 8, 8), np.uint8)

    def put(self, code, a):
        self.t[code] = a

    def alloc_picture(self, img, pal, prio, pool, cache):
        """Cut img (H x W, multiples of 8) into tiles, dedupe (exact and flips), allocate from pool.
        -> list of rows of cell words."""
        rows = []
        for y in range(0, img.shape[0], 8):
            row = []
            for x in range(0, img.shape[1], 8):
                t = img[y:y + 8, x:x + 8]
                if not t.any():
                    row.append(BLANK | pal << 10)
                    continue
                w = None
                for fl, tt in ((0, t), (0x4000, t[:, ::-1]), (0x8000, t[::-1]), (0xC000, t[::-1, ::-1])):
                    k = tt.tobytes()
                    if k in cache:
                        w = cache[k] | fl
                        break
                if w is None:
                    code = pool.pop(0)
                    self.t[code] = t
                    cache[t.tobytes()] = code
                    w = code
                row.append(w | pal << 10 | prio << 13)
            rows.append(row)
        return rows


# ------------------------------------------------------------------ cell styles
def hud(c, body=3, edge=1, heavy=True):
    return FN.outlined(FN.cell(c, heavy, dy=0, dx=0 if heavy else 1), body, edge)


def boxc(c, body=3, bg=1):
    return np.where(FN.cell(c, False, dy=1, dx=1), body, bg).astype(np.uint8)


def menu(c, body=2, plate=3):
    m = FN.cell(c, True, dy=0, dx=0)
    out = np.where(m, body, plate).astype(np.uint8)
    out[7, :] = plate
    for y, x in ((0, 0), (0, 7), (7, 0), (7, 7)):
        out[y, x] = 0
    return out


def word(text, ntiles, body, edge=None, bg=0, heavy=False, dx=None):
    m = np.zeros((8, ntiles * 8), bool)
    ln = FN.line(text, heavy)
    if ln.shape[1] > m.shape[1] - 2:
        ln = FN.line(text, False)
    x = (m.shape[1] - ln.shape[1]) // 2 if dx is None else dx
    w = min(ln.shape[1], m.shape[1] - x)
    m[0:7, x:x + w] = ln[:, :w]
    return FN.outlined(m, body, edge, bg) if edge is not None else np.where(m, body, bg).astype(np.uint8)


def tiny(text, body, shadow=None, w=16, x0=0, y0=1):
    """Our 3x5 face (spr_font.tiny) -> (8, w)."""
    out = np.zeros((8, w), np.uint8)
    x = x0
    for ch in text:
        g = FN.tiny(ch)
        gh, gw = g.shape
        if shadow is not None:
            sub = out[y0 + 1:y0 + 1 + gh, x + 1:x + 1 + gw]
            gg = g[:sub.shape[0], :sub.shape[1]]
            sub[gg & (sub == 0)] = shadow
        sub = out[y0:y0 + gh, x:x + gw]
        sub[g[:sub.shape[0], :sub.shape[1]]] = body
        x += gw + 1
    return out


def split(img, store, code0):
    for k in range(img.shape[1] // 8):
        store.put(code0 + k, img[:, k * 8:k * 8 + 8])


# ------------------------------------------------------------------ small pictures
def coin_icon():
    m = np.zeros((8, 8), np.uint8)
    y, x = np.mgrid[0:8, 0:8]
    r = ((x - 3.5) / 3.0) ** 2 + ((y - 3.5) / 3.6) ** 2
    m[r <= 1.6] = 1
    m[r <= 1.0] = 2
    m[r <= 0.55] = 3
    m[(np.abs(x - 3.5) < 1) & (np.abs(y - 3.5) < 1.6)] = 1
    return m


def gem_icon(fill=3, edge=1, hi=2):
    m = np.zeros((6, 6), bool)
    for y in range(6):
        for x in range(6):
            dx, dy = abs(x - 2.5), abs(y - 2.5)
            m[y, x] = (dx + dy * 0.5 <= 1.8) or (dy + dx * 0.5 <= 1.8)
    o = np.zeros((8, 8), np.uint8)
    o[1:7, 1:7] = FN.outlined(m, fill, edge)
    full = np.zeros((8, 8), bool)
    full[1:7, 1:7] = m
    o[FN.ring(full) & (o == 0)] = edge
    o[3, 3] = hi
    return o


def clock_icon():
    y, x = np.mgrid[0:8, 0:8]
    r = np.hypot(x - 3.5, y - 3.5)
    o = np.zeros((8, 8), np.uint8)
    o[r <= 3.7] = 1
    o[r <= 2.7] = 3
    o[1:4, 3] = 1
    o[3, 4:6] = 1
    return o


def frame_corner():
    o = np.zeros((8, 8), np.uint8)
    y, x = np.mgrid[0:8, 0:8]
    r = np.hypot(x - 7.5, y - 7.5)
    o[(r <= 6.5)] = 1
    o[(r <= 5.5)] = 2
    o[(r <= 4.5)] = 3
    o[(r <= 3.5)] = 0
    return o


def frame_top():
    o = np.zeros((8, 8), np.uint8)
    o[1, :] = 1
    o[2, :] = 2
    o[3, :] = 3
    o[2, ::4] = 3
    return o


def frame_side():
    return frame_top().T.copy()


def arrow_tip():
    o = np.zeros((8, 8), np.uint8)
    for y in range(8):
        for x in range(8):
            if y >= x:
                o[y, x] = 2 if y - x >= 2 else 1
    return o


def arrow_hstem():
    o = np.zeros((8, 8), np.uint8)
    o[3, :] = 1
    o[4:, :] = 2
    o[4:, 7] = 1
    return o


def arrow_vstem():
    return arrow_hstem().T.copy()


def water_surface(k):
    o = np.zeros((8, 8), np.uint8)
    for x in range(8):
        h = 2 + int(round(1.2 * np.sin((x + 4 * k) * np.pi / 4)))
        o[h:, x] = 2
        o[h, x] = 3
    o[6, (np.arange(8) + k * 3) % 5 == 0] = 1
    return o


def water_fill():
    o = np.full((8, 8), 2, np.uint8)
    y, x = np.mgrid[0:8, 0:8]
    o[((x + 2 * y) % 8) < 4] = 0
    return o


def cloud_edge(k):
    o = np.zeros((8, 8), np.uint8)
    y, x = np.mgrid[0:8, 0:8]
    if k == 0:
        o[(x - 6) ** 2 + (y - 8) ** 2 <= 20] = 3
    else:
        o[y >= 3 + (np.cos(x * np.pi / 4) * 1.5).round()] = 3
    return o


def sparkle_tile():
    o = np.zeros((8, 8), np.uint8)
    o[3, 1:6] = 3
    o[1:6, 3] = 3
    o[3, 3] = 1
    o[2, 2] = o[4, 4] = o[2, 4] = o[4, 2] = 2
    return o


def motif(kind):
    """Overworld frame motifs (ours): leaf, berry pair, spark, ring, knot, seed."""
    o = np.zeros((8, 8), np.uint8)
    y, x = np.mgrid[0:8, 0:8]
    if kind == 0:
        u, v = (x - 3.5 + y - 3.5) * 0.7, (x - 3.5 - (y - 3.5)) * 0.7
        m = u ** 2 / 9 + v ** 2 / 2.2 <= 1
        o[m] = 2
        o[(np.abs(x - y) < 1) & m] = 1
    elif kind == 1:
        for cx, cy in ((2.5, 4.5), (5, 3)):
            o[(x - cx) ** 2 + (y - cy) ** 2 <= 3.2] = 2
        o[2, 2] = 1
        o[1, 5] = 1
    elif kind == 2:
        o[3, :] = 2
        o[:, 3] = 2
        o[3, 3] = 1
    elif kind == 3:
        r = np.hypot(x - 3.5, y - 3.5)
        o[(r <= 3.2) & (r >= 1.8)] = 2
    elif kind == 4:
        o[(x + y) % 4 == 0] = 2
        o[(x - y) % 4 == 0] = 1
        o[0, :] = 0
        o[:, 0] = 0
    else:
        o[((x - 3.5) / 2.2) ** 2 + ((y - 4) / 3.3) ** 2 <= 1] = 2
        o[2, 3] = 1
    return o


def times_sign():
    return FN.outlined(FN.cell('*', False, 0, 1), 3, 1)


# ------------------------------------------------------------------ sheets 28 / 29 / 2A (fonts + HUD)
def draw_fonts(S):
    t = lambda sid, i: BASE[sid] + i
    for i, c in enumerate('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
        S.put(t(0x28, i), hud(c))
    for i, c in zip(range(0x24, 0x29), '.,*-!'):
        S.put(t(0x28, i), hud(c))
    S.put(t(0x28, 0x26), times_sign())
    S.put(t(0x28, 0x2E), coin_icon())
    split(word('TOBI', 5, 2, 1, heavy=True), S, t(0x28, 0x30))
    split(word('KIP', 5, 2, 1, heavy=True), S, t(0x28, 0x40))
    tm = np.zeros((8, 24), np.uint8)
    tm[:, 0:8] = clock_icon()
    txt = tiny('TIME', 3, None, 16, 0, 1) > 0
    tm[:, 8:24] = FN.outlined(txt, 3, 1)
    split(tm, S, t(0x28, 0x3D))
    S.put(t(0x28, 0x3A), frame_corner())
    S.put(t(0x28, 0x3B), frame_top())
    S.put(t(0x28, 0x4A), frame_side())
    S.put(t(0x28, 0x64), gem_icon())
    S.put(t(0x28, 0x76), clock_icon())
    S.put(t(0x28, 0x70), gem_icon(2, 1, 3))
    S.put(t(0x28, 0x4E), menu('3'))
    for i, c in enumerate('4567'):
        S.put(t(0x28, 0x50 + i), menu(c))
    S.put(t(0x28, 0x54), hud('0', 2))
    S.put(t(0x28, 0x36), hud('1', 2))
    S.put(t(0x28, 0x37), hud('9', 2))
    S.put(t(0x28, 0x77), hud('='))
    S.put(t(0x28, 0x78), hud(':'))
    for i, c in enumerate('NOUD'):
        S.put(t(0x28, 0x79 + i), menu(c))
    S.put(t(0x28, 0x7D), arrow_hstem())
    S.put(t(0x28, 0x7E), arrow_tip())
    S.put(t(0x28, 0x7F), arrow_vstem())
    # 29
    for i, c in enumerate('VWIOH'):
        S.put(t(0x29, i), menu(c))
    S.put(t(0x29, 0x05), hud("'"))
    q = hud("'").copy()
    q[:, 3:] = np.maximum(q[:, 3:], hud("'")[:, :5])
    S.put(t(0x29, 0x06), q)
    S.put(t(0x29, 0x07), gem_icon())
    S.put(t(0x29, 0x0F), times_sign())
    S.put(t(0x29, 0x12), frame_corner())
    S.put(t(0x29, 0x13), frame_top())
    S.put(t(0x29, 0x14), frame_side()[:, ::-1].copy())      # the map uses it x-flipped on the left
    for k, code in enumerate((0x15, 0x16, 0x17)):
        S.put(t(0x29, code), motif(k))
    sh = np.zeros((8, 8), np.uint8)                         # frame shadow: end, horizontal, vertical
    sh[3:, 0:4] = 2
    sh[3, 0] = sh[3, 3] = 0
    S.put(t(0x29, 0x54), sh)
    sh = np.zeros((8, 8), np.uint8)
    sh[0:4, :] = 2
    S.put(t(0x29, 0x55), sh)
    S.put(t(0x29, 0x56), sh.T.copy())
    S.put(t(0x29, 0x7E), np.ones((8, 8), np.uint8))           # flat colour-1 fill
    S.put(t(0x29, 0x7F), np.full((8, 8), 3, np.uint8))        # flat colour-3 fill (cloud body)
    S.put(NEW_CODES['box :'], boxc(':'))
    for k, c in zip(('menu F', 'menu J', 'menu K', 'menu Q', 'menu X'), 'FJKQX'):
        S.put(NEW_CODES[k], menu(c))
    # 2A: message / credits face, menu letters, lowercase
    for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ!.-,? '):
        S.put(t(0x2A, i), boxc(c))
    S.put(t(0x2A, 0x20), hud(',', 2))
    for i, c in enumerate('Z0123456789BC'):
        S.put(t(0x2A, 0x21 + i), menu(c))
    S.put(t(0x2A, 0x2E), hud('>', 2))
    S.put(t(0x2A, 0x2F), menu('T'))
    S.put(t(0x2A, 0x30), menu('N'))
    S.put(t(0x2A, 0x31), menu('S'))
    row = np.zeros((8, 88), bool)
    for i, c in enumerate('ILLUSIYELLOW'):
        g = FN.cell(c, False, 0, 0)
        x0 = 2 + i * 7
        w = min(8, 88 - x0)
        if w > 0:
            row[:, x0:x0 + w] |= g[:, :w]
    split(np.where(row, 3, 1).astype(np.uint8), S, t(0x2A, 0x32))
    S.put(t(0x2A, 0x3D), boxc('?'))
    S.put(t(0x2A, 0x3E), menu('O'))
    S.put(t(0x2A, 0x3F), boxc('/'))
    for i, c in enumerate("abcdefghijklmnopqrstuvwxyz#()'"):
        S.put(t(0x2A, 0x40 + i), boxc(c))
    for i, c in enumerate('12345670'):
        S.put(t(0x2A, 0x64 + i), boxc(c))
    for i, c in enumerate('12P'):
        S.put(t(0x2A, 0x6D + i), menu(c))
    for i, c in enumerate('LAYERGM'):
        S.put(t(0x2A, 0x70 + i), menu(c))
    S.put(t(0x2A, 0x7A), boxc('R'))
    S.put(t(0x2A, 0x7D), water_surface(0))
    S.put(t(0x2A, 0x7E), water_surface(1))
    S.put(t(0x2B, 0x0E), water_fill())
    S.put(t(0x2B, 0x0F), cloud_edge(0))
    S.put(t(0x2B, 0x1E), cloud_edge(1))
    S.put(t(0x2B, 0x1F), sparkle_tile())


# ------------------------------------------------------------------ title (stripe 1)
TITLE_TEXT = 'built on snesrev/smw'


def logo_word(text, sx=3, sy=3, fill=2, accent=3, edge=1, gap=3):
    """Big outlined letters from our face scaled sx x sy, two-tone with diagonal thorn marks."""
    gl = [FN.bold(FN.glyph(c)) for c in text]
    w = sum(g.shape[1] * sx + gap for g in gl) - gap + 2
    h = 7 * sy + 2
    m = np.zeros((h, w), bool)
    x = 1
    for g in gl:
        big = g.repeat(sy, 0).repeat(sx, 1)
        m[1:1 + big.shape[0], x:x + big.shape[1]] |= big
        x += big.shape[1] + gap
    out = FN.outlined(m, fill, edge)
    yy = np.arange(h)[:, None]
    xx = np.arange(w)[None, :]
    out[m & (yy < 1 + 2 * sy)] = accent
    out[m & (yy == 1 + 2 * sy)] = edge
    out[m & ((xx + 2 * yy) % 16 == 0) & (yy > 2 + 2 * sy)] = accent
    return out


def braid(w, h):
    """Braided-vine frame (ours): 16 px band around a w x h picture, colours 1..3."""
    img = np.zeros((h, w), np.uint8)
    y, x = np.mgrid[0:h, 0:w]

    def band(u, v):
        a = np.sin(u * np.pi / 8.0) * 4.5 + 7.5
        b = -np.sin(u * np.pi / 8.0) * 4.5 + 7.5
        o = np.full(u.shape, 3, np.uint8)
        o[np.abs(v - a) < 2.0] = 1
        o[np.abs(v - b) < 2.0] = 2
        o[np.abs(v - a) < 0.8] = 2
        o[(v < 1) | (v > 14)] = 1
        return o
    top, bot, lef, rig = y < 16, y >= h - 16, x < 16, x >= w - 16
    img[top] = band(x[top], y[top])
    img[bot] = band(x[bot], (h - 1 - y)[bot])
    m = lef & ~top & ~bot
    img[m] = band(y[m], x[m])
    m = rig & ~top & ~bot
    img[m] = band(y[m], (w - 1 - x)[m])
    for cy, cx in ((8, 8), (8, w - 8), (h - 8, 8), (h - 8, w - 8)):
        r = np.hypot(x - cx + 0.5, y - cy + 0.5)
        img[r <= 7] = 1
        img[r <= 5.5] = 2
        img[r <= 3] = 3
    return img


def build_title(S, old, pools):
    """Stripe 1 rebuilt: frame (pal 3), logo (BRAMBLE pal 7, ISLES pal 6), credit line (pal 2)."""
    cache = {}
    pool = pools['title']
    cells = {}
    fr = braid(256, 224)
    for r, row in enumerate(S.alloc_picture(fr, 3, 1, pool, cache)):
        for c, wd in enumerate(row):
            if (wd & 0x3FF) != BLANK:
                cells[r * 32 + c] = wd

    def place(img, pal, r0, c0):
        h8, w8 = -(-img.shape[0] // 8) * 8, -(-img.shape[1] // 8) * 8
        pad = np.zeros((h8, w8), np.uint8)
        pad[:img.shape[0], :img.shape[1]] = img
        for r, row in enumerate(S.alloc_picture(pad, pal, 1, pool, cache)):
            for c, wd in enumerate(row):
                if (wd & 0x3FF) != BLANK:
                    cells[(r0 + r) * 32 + c0 + c] = wd
    b = logo_word('BRAMBLE', fill=2, accent=3)          # pal 7 on the title: red, green
    i = logo_word('ISLES', fill=3, accent=2)            # pal 6 on the title: gold, cyan
    place(b, 7, 4, (32 - -(-b.shape[1] // 8)) // 2)
    place(i, 6, 8, (32 - -(-i.shape[1] // 8)) // 2)
    ln = FN.line(TITLE_TEXT)
    t = np.zeros((8, -(-(ln.shape[1] + 2) // 8) * 8), bool)
    t[0:7, 1:1 + ln.shape[1]] = ln
    place(FN.outlined(t, 3, 1), 2, 24, (32 - t.shape[1] // 8) // 2)
    for off in old:                                     # cells the game's title image covers: blank the rest
        cells.setdefault(off, BLANK | 2 << 10)
    return encode_rows(cells)


# ------------------------------------------------------------------ layer-3 images
def _edge(m):
    p = np.pad(m, 1)
    return m & ~(p[2:, 1:-1] & p[:-2, 1:-1] & p[1:-1, 2:] & p[1:-1, :-2])


def gate_picture(w, h):
    """Castle gate (ours): arched gilded frame with twisted vine bars."""
    img = np.zeros((h, w), np.uint8)
    y, x = np.mgrid[0:h, 0:w]
    cx = w / 2
    arch = (y >= 24) | (((x - cx) / (w / 2)) ** 2 + ((y - 24) / 24.0) ** 2 <= 1)
    inner = arch & (x >= 10) & (x < w - 10) & (y < h - 10) & \
        ((y >= 34) | (((x - cx) / (w / 2 - 10)) ** 2 + ((y - 34) / 24.0) ** 2 <= 1))
    img[arch] = 3
    img[arch & ((x + y) % 8 == 0)] = 2
    img[inner] = 0
    for bx in range(20, w - 12, 16):
        d = np.abs(x - bx - np.sin(y * np.pi / 4.0) * 1.5)
        img[inner & (d < 2.0)] = 2
        img[inner & (d < 0.8)] = 3
    img[inner & (np.abs(y - (h - 36)) < 1.5)] = 2
    img[_edge(arch)] = 1
    return img


def crusher_picture(w, h):
    """Crusher pillar (ours): banded stone with rivets and a toothed foot."""
    img = np.zeros((h, w), np.uint8)
    y, x = np.mgrid[0:h, 0:w]
    body = (x >= 8) & (x < w - 8)
    img[body] = 2
    img[body & ((y % 24) < 3)] = 3
    img[body & ((y % 24) == 3)] = 1
    img[body & ((x - 8) % 32 == 0)] = 1
    img[body & ((x % 32) == 20) & ((y % 24) == 12)] = 3
    img[body & ((x % 32) == 21) & ((y % 24) == 13)] = 1
    foot = y >= h - 16
    img[foot] = 2
    img[foot & (y >= h - 6) & ((x % 12) >= 6)] = 0
    img[foot & (y == h - 16)] = 3
    img[((x == 8) | (x == w - 9)) & ~foot] = 1
    return img


def wall_tiles():
    """Castle-wall kit (ours): a 16x8 stone and a 16x24 round-topped window."""
    st = np.zeros((8, 16), np.uint8)
    st[1:7, 1:15] = 3
    st[1, 1:15] = 2
    st[6, 1:15] = 1
    st[1:7, 1] = 2
    st[1:7, 14] = 1
    win = np.zeros((24, 16), np.uint8)
    y, x = np.mgrid[0:24, 0:16]
    shape = (y >= 8) | (((x - 7.5) / 7.5) ** 2 + ((y - 8) / 7.5) ** 2 <= 1)
    win[shape] = 1
    inner = ((y >= 9) & (x >= 3) & (x < 13) & (y < 22)) | ((((x - 7.5) / 5) ** 2 + ((y - 9) / 6) ** 2) <= 1)
    win[inner] = 2
    win[inner & ((x == 7) | (x == 8) | (y == 15))] = 3
    return st, win


def rock_cluster(rng, w=32, h=24):
    img = np.zeros((h, w), np.uint8)
    y, x = np.mgrid[0:h, 0:w]
    for _ in range(3):
        cx, cy = rng.uniform(8, w - 8), rng.uniform(10, h - 6)
        rx, ry = rng.uniform(5, 9), rng.uniform(4, 6)
        m = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1
        img[m] = 2
        img[m & (y < cy - ry * 0.3)] = 3
        img[m & ((x * 3 + y * 5) % 11 == 0)] = 1
    return img


def _cells_of(rows, off0, keep=lambda r, c: True):
    out = {}
    for r, row in enumerate(rows):
        for c, wd in enumerate(row):
            if (wd & 0x3FF) != BLANK and keep(r, c):
                out[off0 + r * 32 + c] = wd
    return out


def build_layer3_images(S, old_arr, pools):
    pool = pools['l3']
    out = list(old_arr)
    cache = {}
    gate_bytes = encode_rows(_cells_of(S.alloc_picture(gate_picture(24 * 8, 18 * 8), 7, 1, pool, cache), 0x800 + 4))
    cr_rows = S.alloc_picture(crusher_picture(18 * 8, 19 * 8), 3, 1, pool, cache)
    cr_bytes = encode_rows(_cells_of(cr_rows, 5 * 32 + 7, lambda r, c: r >= 17 or 1 <= c <= 16))
    st, win = wall_tiles()
    st_w = S.alloc_picture(st, 5, 0, pool, cache)[0]
    win_w = S.alloc_picture(win, 5, 0, pool, cache)
    rng = np.random.default_rng(1205)
    wall = {}
    for scr in (2, 3):
        for _ in range(26):
            r, c = int(rng.integers(0, 30)), int(rng.integers(0, 28))
            for k in range(int(rng.integers(1, 4))):
                cc = c + 2 * k + (r % 2)
                if cc < 31:
                    wall[scr * 0x400 + r * 32 + cc] = st_w[0]
                    wall[scr * 0x400 + r * 32 + cc + 1] = st_w[1]
        for k in range(5):
            r, c = 3 + 10 * (k % 3), 3 + 6 * k
            for rr in range(3):
                for cc in range(2):
                    wall[scr * 0x400 + (r + rr) * 32 + c + cc] = win_w[rr][cc]
    wall_bytes = encode_rows(wall)
    rng = np.random.default_rng(4411)
    kinds = [S.alloc_picture(rock_cluster(rng), 4, 0, pool, cache) for _ in range(2)]
    rocks = {}
    for k in range(18):
        r, c = int(rng.integers(30, 112)), int(rng.integers(2, 26))
        scr, rr0 = divmod(r, 32)
        for dr, row in enumerate(kinds[k % 2]):
            if rr0 + dr >= 32:
                break
            for dc, wd in enumerate(row):
                if (wd & 0x3FF) != BLANK:
                    rocks[scr * 0x400 + (rr0 + dr) * 32 + c + dc] = wd
    rock_bytes = encode_rows(rocks)
    for i, d in enumerate(old_arr):
        if not d or len(d) < 4:
            continue
        if len(d) == 525:
            out[i] = gate_bytes
        elif i == 4:
            out[i] = cr_bytes
        elif i == 5:
            out[i] = wall_bytes
        elif i in (11, 44):
            out[i] = rock_bytes
    return out


# ------------------------------------------------------------------ 2F tall face, big loading letters (sheet 0F)
def build_2f():
    t = np.zeros((64, 8, 8), np.uint8)
    for k, c in enumerate('ABCDEFGHIJKLMNOP'):
        g = FN.outlined(FN.tall(c), 3, 1)
        t[k], t[0x10 + k] = g[:8], g[8:]
    for k, c in enumerate('QRSTUVWXYZ-.'):
        g = FN.outlined(FN.tall(c), 3, 1)
        t[0x20 + k], t[0x30 + k] = g[:8], g[8:]
    dash = np.zeros((16, 8), bool)                    # wavy dash and a diamond stop (ours)
    for x in range(1, 7):
        dash[7 + (x % 2), x] = True
        dash[8 - (x % 2), x] = True
    stop = np.zeros((16, 8), bool)
    for y in range(9, 15):
        w = 2 - abs(y - 12) if abs(y - 12) < 3 else 0
        stop[y, 3 - w:4 + w] = True
    for k, m in ((0x0A, dash), (0x0B, stop)):
        g = FN.outlined(m, 3, 1)
        t[0x20 + k], t[0x30 + k] = g[:8], g[8:]
    return t


# Our 8x16 "neon" face for the big loading words: 1 px strokes, outlined. The code builds every word
# from 24 tiles of sheet 0F, re-using tiles flipped (kDrawLoadingLetters_*): I, O, E and the M parts
# must be top/bottom mirror images, S turns half-way, A's top is O's top, U's bottom is O's top flipped,
# V's top is U's top, T's bottom is I flipped. Each letter below is drawn to those rules.
BIGL = {
    'I': ["........", ".#####..", "...#....", "...#....", "...#....", "...#....", "...#....", "...#....",
          "...#....", "...#....", "...#....", "...#....", "...#....", "...#....", ".#####..", "........"],
    'O': ["........", "..###...", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..",
          ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", "..###...", "........"],
    'A': ["........", "..###...", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..",
          ".#####..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", "........"],
    'U': ["........", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..",
          ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", "..###...", "........"],
    'V': ["........", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..",
          ".#...#..", ".#...#..", "..#.#...", "..#.#...", "..#.#...", "...#....", "...#....", "........"],
    'E': ["........", ".#####..", ".#......", ".#......", ".#......", ".#......", ".#......", ".####...",
          ".####...", ".#......", ".#......", ".#......", ".#......", ".#......", ".#####..", "........"],
    'M': ["........", ".#...#..", ".##.##..", ".#.#.#..", ".#.#.#..", ".#...#..", ".#...#..", ".#...#..",
          ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", "........"],
    'R': ["........", ".####...", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#..#...", ".###....",
          ".#.#....", ".#..#...", ".#..#...", ".#...#..", ".#...#..", ".#...#..", ".#...#..", "........"],
    'S': ["........", "..####..", ".#......", ".#......", ".#......", ".#......", "..#.....", "...#....",
          "....#...", ".....#..", "......#.", "......#.", "......#.", "......#.", ".####...", "........"],
    'T': ["........", "#######.", "...#....", "...#....", "...#....", "...#....", "...#....", "...#....",
          "...#....", "...#....", "...#....", "...#....", "...#....", "...#....", ".#####..", "........"],
    'L': ["........", ".#......", ".#......", ".#......", ".#......", ".#......", ".#......", ".#......",
          ".#......", ".#......", ".#......", ".#......", ".#......", ".#......", ".#####..", "........"],
    'G': ["........", "..####..", ".#......", ".#......", ".#......", ".#......", ".#......", ".#......",
          ".#..##..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", "..###...", "........"],
    'P': ["........", ".####...", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".#...#..", ".####...",
          ".#......", ".#......", ".#......", ".#......", ".#......", ".#......", ".#......", "........"],
    '!': ["........", ".#####..", "...#....", "...#....", "...#....", "...#....", "...#....", "...#....",
          "...#....", "...#....", "........", "........", "...#....", "...#....", "........", "........"],
}


def _bigl(c):
    m = np.array([[ch == '#' for ch in r] for r in BIGL[c]], bool)
    out = FN.outlined(m, 3, 2)
    out[m & (np.arange(16)[:, None] >= 8)] = 4
    out[1, :][m[1, :]] = 1
    return out


def loading_tiles():
    """{sheet-0F tile number: 8x8} for the 24 big-letter tiles."""
    g = {c: _bigl(c) for c in BIGL}
    top, bot = (lambda a: a[:8]), (lambda a: a[8:])
    z = np.zeros((8, 8), np.uint8)
    return {0: top(g['I']), 1: top(g['P']), 2: top(g['G']), 3: top(g['O']), 4: top(g['M']), 5: top(g['E']),
            6: bot(g['!']), 7: bot(g['P']), 8: bot(g['G']), 9: bot(g['A']), 10: bot(g['M']), 11: z,
            12: top(g['U']), 13: top(g['E']), 14: top(g['R']), 15: top(g['T']), 16: top(g['L']), 17: z,
            18: bot(g['V']), 19: z, 20: bot(g['R']), 21: top(g['S']), 22: bot(g['L']), 23: z}


def restyle_loading_letters(raw0f):
    """Sheet 0F tiles 00-17 (the big MARIO START / GAME OVER letters; the sheet is shared with
    `tiles`, only these 24 tiles are ours)."""
    img = tiles.sheet(tiles.decode(raw0f, 3))
    for tnum, t in loading_tiles().items():
        yy, xx = tnum // 16 * 8, tnum % 16 * 8
        img[yy:yy + 8, xx:xx + 8] = t
    return tiles.encode(tiles.unsheet(img)[:len(raw0f) // 24], 3)


# ------------------------------------------------------------------ pools
def pools_from(kept):
    """DIRTY side (games/smw/extract_sprite_slots): tile codes we may reuse for rebuilt pictures: those only the rebuilt pictures used before."""
    use = {}
    st = A.unpack_array(kept['kLoadStripeImagePtrs'])
    l3 = A.unpack_array(kept['kLayer3ImagePtrs'])
    for i, d in enumerate(st):
        if d and len(d) > 1:
            for w in cell_map(d).values():
                use.setdefault(w & 0x3FF, set()).add('S%d' % i)
    for i, d in enumerate(l3):
        if d and len(d) > 1:
            for w in cell_map(d).values():
                use.setdefault(w & 0x3FF, set()).add('L%d' % i)
    rebuilt_l = {'L%d' % i for i, d in enumerate(l3) if d and (len(d) == 525 or i in (4, 5, 11, 44))}
    keep = {0x3A, 0x3B, 0x4A, 0x64, 0x2E, 0x26, 0x30, 0x31, 0x32, 0x33, 0x34, 0x3D, 0x3E, 0x3F, 0x00,
            0x4E, 0x50, 0x51, 0x52, 0x53, 0x54, 0x36, 0x37, 0x77, 0x78}
    keep |= set(NEW_CODES.values()) | {BLANK, SOLID1, 0x0FF}
    title = [c for c in range(0x000, 0x100) if use.get(c) == {'S1'} and c not in keep]
    title += [c for c in range(0x0BD, 0x0C0) if c not in use]
    l3p = [c for c in range(0x180, 0x200) if c not in (0x18E, 0x18F, 0x19E, 0x19F) and
           (not use.get(c) or use[c] <= (rebuilt_l | {'S1'}))]
    return {'title': title, 'l3': l3p}


# ------------------------------------------------------------------ sprite-sheet words
def _bubble(w, h):
    y, x = np.mgrid[0:h, 0:w]
    m = ((x - (w - 1) / 2) / (w / 2 - 0.5)) ** 4 + ((y - (h - 1) / 2) / (h / 2 - 0.5)) ** 4 <= 1
    out = np.zeros((h, w), np.uint8)
    out[m] = 1
    out[_edge(m)] = 2
    return out


def _tile3(img, t):
    y, x = t // 16 * 8, t % 16 * 8
    return img[y:y + 8, x:x + 8]


def _set(img, t, a):
    y, x = t // 16 * 8, t % 16 * 8
    img[y:y + a.shape[0], x:x + a.shape[1]] = a


def big_word(text, w, h, fill=(3, 4, 5), edge=2, hi=1):
    """Chunky striped letters (3bpp) for the ending words."""
    gl = [FN.bold(FN.glyph(c)) for c in text]
    sx = max(1, (w - 2) // (len(text) * 6))
    sy = max(1, (h - 2) // 7)
    m = np.zeros((h, w), bool)
    tw = sum(g.shape[1] * sx + sx for g in gl) - sx
    x = max(1, (w - tw) // 2)
    for g in gl:
        big = g.repeat(sy, 0).repeat(sx, 1)
        y0 = max(1, (h - big.shape[0]) // 2)
        bh, bw = min(big.shape[0], h - y0), min(big.shape[1], w - x)
        if bw > 0:
            m[y0:y0 + bh, x:x + bw] |= big[:bh, :bw]
        x += big.shape[1] + sx
    out = FN.outlined(m, fill[1], edge)
    yy = np.arange(h)[:, None]
    out[m & (yy % 6 < 2)] = fill[0]
    out[m & (yy % 6 == 5)] = fill[2]
    up = np.zeros_like(m)
    up[1:] = m[:-1]
    out[m & ~up] = hi
    return out


def patch_sprite_text(imgs, slots, kept):
    """Words / numbers inside sprite sheets, in our faces (3bpp convention: 1 white, 2 outline,
    3-5 main light/mid/dark, 6/7 accent). Slot positions come from the code's tile tables."""
    g0 = imgs[0x00]
    # boot logo: GFX00 tiles 02-09 / 12-19 = four 16x16 sprites side by side (palette row 8)
    logo = np.zeros((16, 64), np.uint8)
    top = FN.line('BRAMBLE', heavy=True)
    tm = np.zeros((8, 64), bool)
    x0 = (64 - top.shape[1]) // 2
    tm[0:7, x0:x0 + top.shape[1]] = top
    logo[0:8] = FN.outlined(tm, 1, 3)
    bot = FN.line('presents')
    x0 = (64 - bot.shape[1]) // 2
    logo[9:16, x0:x0 + bot.shape[1]] = np.where(bot, 7, 0)
    g0[0:16, 16:80] = logo
    # score pop-ups (8x8 tiles of GFX00; which tile shows which digits is code: kProcessScoreSprites)
    for t, s in ((0x44, '10'), (0x54, '20'), (0x46, '40'), (0x47, '80'), (0x45, '0'), (0x55, '00'),
                 (0x56, '1'), (0x29, '2'), (0x39, '3'), (0x38, '4'), (0x28, '5')):
        x0 = 0 if t in (0x45, 0x55) else max(0, 8 - 4 * len(s))
        _tile3(g0, t)[:] = tiny(s, 1, 2, 8, x0, 1)
    _tile3(g0, 0x57)[:] = tiny('UP', 6, 2, 8, 0, 1)
    if 0x24 in imgs:                       # HELP! bubble, 32x16 at tile 20
        b = _bubble(32, 16)
        b[4:12] = np.where(tiny('HELP!', 2, None, 32, 6, 0) > 0, 2, b[4:12])
        _set(imgs[0x24], 0x20, b)
    if 0x22 in imgs:                       # thanks bubble: 32x16 at tile 26 + tail tile 0D (code table)
        b = _bubble(32, 16)
        b[1:9] = np.where(tiny('THANK', 2, None, 32, 6, 1) > 0, 2, b[1:9])
        b[8:16] = np.where(tiny('YOU!', 2, None, 32, 8, 0) > 0, 2, b[8:16])
        _set(imgs[0x22], 0x26, b)
        tail = np.zeros((8, 8), np.uint8)
        for y in range(6):
            n = max(1, 5 - y)
            tail[y, 1] = 2
            tail[y, 2:2 + n] = 1
            tail[y, 2 + n] = 2
        tail[6, 1:3] = 2
        _tile3(imgs[0x22], 0x0D)[:] = tail
    if 0x2E in imgs:                       # THANK / YOU ending words (DrawEndingThankYou tile list)
        g = imgs[0x2E]
        you = big_word('YOU!', 64, 32)
        thank = big_word('THANK', 64, 32)
        for k, t in enumerate((0x26, 0x28, 0x2A, 0x2C)):
            _set(g, t, you[0:16, k * 16:k * 16 + 16])
        for k, t in enumerate((0x46, 0x48, 0x4A, 0x4C)):
            _set(g, t, you[16:32, k * 16:k * 16 + 16])
        for k, t in enumerate((0x60, 0x62, 0x64, 0x66)):
            _set(g, t, thank[0:16, k * 16:k * 16 + 16])
        for k, t in enumerate((0x6A, 0x6C, 0x6E, 0x0A)):
            _set(g, t, thank[16:32, k * 16:k * 16 + 16])
    if 0x10 in imgs:                       # villain's door sign, 32x8 at tile 6C
        sign = np.full((8, 32), 6, np.uint8)
        sign[0, :] = sign[7, :] = 2
        sign[:, 0] = sign[:, 31] = 2
        sign = np.where(tiny('GRUMBOLT', 2, None, 32, 0, 1) > 0, 2, sign)
        _set(imgs[0x10], 0x6C, sign)
    if 0x20 in imgs:                       # countdown digits, tiles 33..36
        for k, c in enumerate('4321'):
            _tile3(imgs[0x20], 0x33 + k)[:] = FN.outlined(FN.cell(c, True, 0, 1), 1, 2)
    if 0x2D in imgs:                       # burst word, 48x32 at tile 20
        g = imgs[0x2D]
        y, x = np.mgrid[0:32, 0:48]
        ang = np.arctan2(y - 15.5, (x - 23.5) / 1.5)
        r = np.hypot((x - 23.5) / 1.5, y - 15.5)
        star = r <= 12 + 3.5 * np.cos(ang * 9)
        burst = np.where(star, 3, 0).astype(np.uint8)
        burst[star & (r > 9 + 3.5 * np.cos(ang * 9))] = 4
        wd = big_word('BAM', 36, 18, fill=(6, 6, 7))
        burst[7:25, 6:42] = np.where(wd > 0, wd, burst[7:25, 6:42])
        burst[_edge(star)] = 2
        _set(g, 0x20, burst)


# ------------------------------------------------------------------ build
def build(items, kept, slots, arr):
    S = Store()
    draw_fonts(S)
    struct = slots['_struct']                            # structure facts from the dirty extractor
    pools = {k: list(v) for k, v in struct['pools'].items()}
    out = {}
    stripes = A.unpack_array(items['kLoadStripeImagePtrs'])
    stripes[1] = build_title(S, struct['title_cells'], pools)
    l3 = build_layer3_images(S, A.unpack_array(items['kLayer3ImagePtrs']), pools)
    from games.smw import spr_stripes                    # our arrangements for the other picture stripes
    stripes, l3, _ = spr_stripes.build(struct['stripes'], stripes, l3)
    out['kLoadStripeImagePtrs'] = A.pack_array(stripes)
    out['kLayer3ImagePtrs'] = A.pack_array(l3)
    for sid in L3_SHEETS:
        img = tiles.sheet(S.t[BASE[sid]:BASE[sid] + 128])
        raw = tiles.encode(tiles.unsheet(img), 2)
        assert len(raw) == slots['%02X' % sid]['bytes'], sid
        arr[sid] = lz2.compress(raw)
    raw = tiles.encode(build_2f(), 2)
    assert len(raw) == slots['2F']['bytes']
    arr[0x2F] = lz2.compress(raw)
    arr[0x0F] = lz2.compress(restyle_loading_letters(lz2.decompress(arr[0x0F])))
    return out
