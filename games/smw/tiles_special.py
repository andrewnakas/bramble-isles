"""CLEAN ROOM. Sheets that other scenes use as sprite / picture sheets (0D, 0E, 0F, 2C) and the
static copies of the animated block tiles in sheets 14 / 17.

Which 8x8 tiles carry something is a structural fact (spec/tiles.json 'tileuse': empty / has clear
pixels / opaque). Each used 16x16 unit gets one of our own small pictures (gem, seed pod, crate,
leaf sprite, shell, star...) or, when opaque, a panel texture. Sheet 0F's first two rows hold the
big 8x16 'loading letters' (words from kDrawLoadingLetters_*): drawn in our own block face from the
kept word tables. Sheet 0D's lowercase letter cells get our pixel font."""
import numpy as np
from games.smw import tilekit as K
from games.smw.tilekit import T, W, O, D, M, L, H, A as AC
from cleanroom.gfx import pixfont


def unit_picture(kind, seed):
    r = K.rng(seed)
    p = np.zeros((16, 16), np.uint8)
    y, x = np.mgrid[0:16, 0:16].astype(float)
    if kind == 0:      # faceted gem
        m = (np.abs(x - 7.5) + np.abs(y - 8) * 0.8) <= 6.5
        p[m] = M; p[m & (x < 7.5)] = L; p[m & (y < 6)] = H
        p[K.outline(m)] = O
    elif kind == 1:    # seed pod with a sprout
        m = ((x - 7.5) / 5.5) ** 2 + ((y - 10) / 5) ** 2 <= 1
        p[m] = M; p[m & (y < 9)] = L
        p[K.outline(m)] = O
        p[1:6, 7:9] = D; p[2, 9:12] = L; p[3, 4:7] = L
    elif kind == 2:    # little crate
        p[2:15, 2:14] = M; p[2:15, 2] = O; p[2:15, 13] = O; p[2, 2:14] = O; p[14, 2:14] = O
        K.line(p, 3, 3, 12, 13, D); K.line(p, 12, 3, 3, 13, D); p[3, 3:13] = L
    elif kind == 3:    # leaf sprite with eyes
        m = ((x - 7.5) / 6.5) ** 2 + ((y - 8.5) / 6.5) ** 2 <= 1
        m &= ~((y < 4) & (np.abs(x - 7.5) > 2.5))
        p[m] = M; p[m & (x + y < 13)] = L
        p[K.outline(m)] = O
        p[7:10, 5] = W; p[7:10, 10] = W; p[8:10, 5] = O; p[8:10, 10] = O
    elif kind == 4:    # spiral shell
        m = K.disc(16, 7.5, 8.5, 6.5)
        p[m] = M
        for t in np.linspace(0, 4 * np.pi, 60):
            rr = 1 + t * 0.42
            xx, yy = int(7.5 + rr * np.cos(t)), int(8.5 + rr * np.sin(t))
            if 0 <= xx < 16 and 0 <= yy < 16 and m[yy, xx]:
                p[yy, xx] = D
        p[K.outline(m)] = O
    elif kind == 5:    # star burst
        m = K.sparkle(16, 7.5, 7.5, 5.0) | K.sparkle(16, 7.5, 7.5, 3.5, diag=True)
        p[m] = L; p[K.disc(16, 7.5, 7.5, 2)] = W
        p[K.outline(m)] = O
    else:              # round lantern
        m = K.disc(16, 7.5, 9, 5.5)
        p[m] = M; p[K.disc(16, 7.5, 9, 3)] = H; p[K.disc(16, 7.5, 9, 1.5)] = W
        p[1:4, 6:10] = D
        p[K.outline(m)] = O
    return p


def panel(seed):
    v = K.periodic_noise((16, 16), 300 + seed, 16, ((8, 1.0), (4, 0.6), (2, 0.3)))
    p = K.shade(v, [D, M, M, L])
    p[0, :] = L; p[:, 0] = L; p[15, :] = O; p[:, 15] = O
    return p


def fill_units(img, use, keep=()):
    """img: (128,8,8) tiles of one sheet; use: 128-char string; keep: tile indices left alone."""
    for u in range(32):
        ty, tx = u // 8 * 2, u % 8 * 2
        ids = [ty * 16 + tx, ty * 16 + tx + 1, (ty + 1) * 16 + tx, (ty + 1) * 16 + tx + 1]
        codes = [use[i] for i in ids]
        if all(c == '0' for c in codes) or any(i in keep for i in ids):
            continue
        pic = panel(u) if all(c == '2' for c in codes) else unit_picture((u * 5 + 3) % 7, u)
        for k, i in enumerate(ids):
            if use[i] != '0':
                img[i] = pic[(k // 2) * 8:(k // 2) * 8 + 8, (k % 2) * 8:(k % 2) * 8 + 8]
    return img


# ----------------------------------------------------------------- big loading letters (sheet 0F)
def big_glyph(c):
    """Our own 8x16 block letter: the 5x7 pixel face doubled vertically, widened, outlined."""
    g = np.zeros((16, 8), np.uint8)
    if c == ' ':
        return g
    cell = pixfont.glyph(c)[:7, :5]
    big = np.zeros((14, 7), bool)
    cols = [0, 1, 1, 2, 3, 3, 4]
    for yy in range(14):
        for xx in range(7):
            big[yy, xx] = cell[yy // 2, cols[xx]]
    g[1:15, 0:7][big] = L
    g[1:15, 0:7][big & (np.arange(14)[:, None] >= 8)] = M
    pad = np.pad(g > 0, 1)
    ring = (pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]) & ~(g > 0)
    g[ring] = O
    return g


WORDS = (('MARIO START !', range(13, -1, -1)), ('LUIGI', range(18, 13, -1)), ('GAME OVER', range(28, 19, -1)),
         ('TIME UP !', range(37, 28, -1)))


def loading_letters(img, items):
    T_, B_ = items['kDrawLoadingLetters_TileData'], items['kDrawLoadingLetters_TileData_BottomTiles']
    TP, BP = items['kDrawLoadingLetters_TileData_TopProp'], items['kDrawLoadingLetters_TileData_BottomProp']

    def src(cc):
        return (cc & 15) + {0x00: 0, 0x10: 6, 0x40: 2, 0x50: 8}.get(cc & 0xF0, 0) if (cc & 0xF0) in (0, 0x10, 0x40, 0x50) else None

    done = {}
    for word, ks in WORDS:
        chars = [ch for ch in word]
        for ch, k in zip(chars, ks):
            if k >= len(T_) or T_[k] >= 0x80 or ch == ' ':
                continue
            gl = big_glyph(ch)
            for half, tt, pp in ((0, T_[k], TP[k]), (1, B_[k], BP[k])):
                s = src(tt)
                if s is None or s in done:
                    continue
                part = gl[half * 8:half * 8 + 8]
                if pp & 0x40: part = part[:, ::-1]
                if pp & 0x80: part = part[::-1]
                img[s] = part
                done[s] = ch
    return img


# ----------------------------------------------------------------- 0D lowercase font cells
FONT_0D = {(8 + i, 0): c for i, c in enumerate('abcdefg')}
FONT_0D.update({(8 + i, 1): c for i, c in enumerate('hijklmn')})
FONT_0D.update({(8 + i, 2): c for i, c in enumerate('opqrstuv')})
FONT_0D.update({(8 + i, 3): c for i, c in enumerate('wxyz#.,\'')})


def font_0d(img):
    for (tx, ty), c in FONT_0D.items():
        t = np.zeros((8, 8), np.uint8)
        try:
            cell = np.array(pixfont.cell(c, 8, 8, bold=False), bool)
            t[cell[:8, :8]] = O
        except Exception:
            pass
        img[ty * 16 + tx] = t
    return img


def build(sheets, items, survey, old_raw):
    from cleanroom.snes import tiles as TL
    use = survey['tileuse']
    for s in (0x0E, 0x0F, 0x2C):
        img = np.zeros((128, 8, 8), np.uint8)
        keep = set(range(32)) if s == 0x0F else set()
        fill_units(img, use['%02X' % s], keep)
        # sheet 0F tiles 0..31 = the big loading letters: left clear here (their halves are shared
        # between letters by the kept word tables; a font that fits those tables is open work)
        sheets[s] = img
    # 0D: BG roles already sit on its level tiles; the rest are pictures + the font cells
    img = sheets[0x0D]
    lvl = set(survey['usage']['0D']['fg']) | set(survey['usage']['0D']['bg'])
    font = {ty * 16 + tx for (tx, ty) in FONT_0D}
    u = ''.join('0' if (i in lvl or i in font) else c for i, c in enumerate(use['0D']))
    fill_units(img, u)
    font_0d(img)
    sheets[0x0D] = img
    return sheets
