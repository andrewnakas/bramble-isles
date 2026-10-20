"""CLEAN ROOM. Backgrounds: our own BG tile roles, BG Map16 (kMap16Data + 0x1100) and every
background layer-2 tilemap (same entry count, same 864-block size and BG flag; pictures new).

Every BG sheet (19 hills, 1B castle, 0C cave, 0D woods) draws the same list of tile roles in
its own style, so any BG picture reads right with any of them: two silhouette layers (far =
palette row 1, near = row 0) whose top edges are 8x8 'profile' tiles (left / right height),
fills, small details, cloud puffs and stars. 0D also holds pictures for other scenes, so the
roles that every picture needs sit on the tiles 0D leaves free (structural survey)."""
import numpy as np
from games.smw import assetfile as A, tilekit as K
from games.smw.tilekit import T, W, O, D, M, L, H, A as AC
from cleanroom.snes import lz2, tiles as TL

BG_SHEETS = {0x19: 'hills', 0x1B: 'high', 0x0C: 'cave', 0x0D: 'woods'}
LEVELS = (0, 2, 4, 6, 8)
PROFILES = [(a, b) for a in LEVELS for b in LEVELS if abs(a - b) <= 4 and (a, b) not in ((0, 0), (8, 8))]
TABLES = ['kLevelData_Layer2', 'kEntranceData_Layer2', 'kChoclateIsland2_Layer2', 'kRollCallData_Layer2',
          'kBufferCreditsBackgrounds_Layer2']


def roles():
    core = ['sky', 'nfill'] + [('nsky', p) for p in PROFILES] + ['ndot', 'cloud0', 'cloud1', 'cloud2', 'cloud3', 'star']
    rest = ['ffill', 'fdot'] + [('fsky', p) for p in PROFILES] + [('nfar', p) for p in PROFILES] + ['ndot2', 'star2',
            'tree0', 'tree1', 'tree2', 'tree3', 'treef0', 'treef1', 'treef2', 'treef3']
    return core, rest


# ----------------------------------------------------------------- role painters
def layer_tex(theme, layer, seed=0):
    y, x = np.mgrid[0:8, 0:8]
    if theme == 'castle':
        t = np.full((8, 8), M if layer == 'n' else D, np.uint8)
        t[3, :] = O; t[7, :] = O; t[0:3, 3] = O; t[4:7, 7] = O
        if layer == 'n':
            t[0, 0:3] = L; t[4, 4:7] = L
        return t
    if theme == 'high':
        v = K.periodic_noise((8, 8), 40 + seed + (5 if layer == 'f' else 0), 8, ((4, 1.0), (2, 0.5)))
        t = K.shade(v, [M, M, L] if layer == 'n' else [L, L, H])
        t[(x + 2 * y) % 13 == 0] = D if layer == 'n' else M
        return t
    if theme == 'cave':
        v = K.periodic_noise((8, 8), 50 + seed + (7 if layer == 'f' else 0), 8, ((4, 1.0), (2, 0.5)))
        return K.shade(v, [O, D, M] if layer == 'f' else [D, M, L])
    if theme == 'woods':
        v = K.periodic_noise((8, 8), 60 + seed + (3 if layer == 'f' else 0), 8, ((4, 1.0), (2, 0.7)))
        t = K.shade(v, [D, M, M, L] if layer == 'n' else [O, D, D, M])
        t[(x + 3 * y) % 11 == 0] = H if layer == 'n' else M
        return t
    # hills: soft dithered bands with bramble dots on the near layer
    v = 0.35 + 0.4 * K.periodic_noise((8, 8), 70 + seed + (9 if layer == 'f' else 0), 8, ((4, 1.0), (2, 0.4)))
    t = K.shade(v, [L, M, M, M, D] if layer == 'n' else [H, L, L, L, M])
    if layer == 'n':
        t[2, 5] = AC; t[6, 1] = AC
    return t


def profile_tile(theme, layer, prof, behind):
    """8x8 edge tile: solid below the line from height hl (left) to hr (right), measured from the
    bottom; behind = 'sky' (clear) or the far-layer fill."""
    hl, hr = prof
    y, x = np.mgrid[0:8, 0:8].astype(float)
    if theme == 'castle':                  # step edges: battlements instead of slopes
        h = np.where(x < 4, hl, hr) + 0.0
        h = np.round(h / 4) * 4
    else:
        h = hl + (hr - hl) * (x + 0.5) / 8.0
    top = 8 - h
    solid = y >= top
    t = np.where(solid, layer_tex(theme, layer), 0).astype(np.uint8)
    edge = solid & (y < top + 1)
    t[edge] = O if theme in ('castle', 'cave') else (H if layer == 'f' else L)
    if theme == 'high':
        t[edge] = W if layer == 'f' else H
    if theme in ('hills', 'woods'):
        t[solid & (y >= top + 1) & (y < top + 2)] = H if layer == 'n' else W
    if behind is not None:
        t[~solid] = behind[~solid]
    return t


def detail_tile(theme, layer):
    t = layer_tex(theme, layer, 3)
    if theme == 'castle':
        t[2:7, 2:6] = O; t[3:6, 3:5] = AC if layer == 'f' else D       # window
    elif theme == 'cave':
        t[K.disc(8, 3.5, 3.5, 2.2)] = H; t[3, 3] = W                     # crystal glint
    elif theme == 'high':
        t[1:8, 2:6] = D; t[0, 2:6:2] = D; t[3:6, 3:5] = AC              # little watchtower
    elif theme == 'woods':
        t[K.disc(8, 4, 3, 2.5)] = L if layer == 'n' else M
    else:
        t[K.disc(8, 3.5, 4.5, 2.4)] = D if layer == 'n' else M           # bush
        t[3, 3] = AC
    return t


def cloud_tile(k, theme):
    y, x = np.mgrid[0:16, 0:16].astype(float)
    m = K.disc(16, 5, 9, 4.5) | K.disc(16, 10, 7, 5.2) | K.disc(16, 13, 10, 3)
    m &= y < 14
    p = np.where(m, W, 0).astype(np.uint8)
    p[m & (y > 10)] = H
    p[K.outline(m)] = L
    if theme == 'cave':      # stalactite cluster instead of a cloud
        p = np.zeros((16, 16), np.uint8)
        for cx, ln in ((3, 12), (8, 15), (12, 9)):
            for yy in range(ln):
                w = (ln - yy) / ln * 2.5
                p[yy, int(cx - w):int(cx + w) + 1] = D if yy < ln - 2 else O
    q = [p[:8, :8], p[:8, 8:], p[8:, :8], p[8:, 8:]][k]
    return q


def tree_tile(k, theme):
    y, x = np.mgrid[0:16, 0:16].astype(float)
    p = np.zeros((16, 16), np.uint8)
    if theme in ('high',):             # pine
        m = (np.abs(x - 7.5) <= (y - 1) * 0.45) & (y < 13)
        p[m] = M; p[m & (x < 7.5)] = L
        p[13:16, 7:9] = D
    elif theme == 'cave':              # stalagmite
        m = (np.abs(x - 7.5) <= (y - 2) * 0.3) & (y >= 2)
        p[m] = M; p[m & (x < 7)] = L
    else:                              # round bramble tree
        m = K.disc(16, 7.5, 6.5, 6.2)
        p[m] = M; p[m & K.disc(16, 6, 5, 3.5)] = L
        p[(x.astype(int) * 3 + y.astype(int) * 5) % 11 == 0 & m] = AC
        p[12:16, 7:9] = D
    p[K.outline(p > 0)] = O
    return [p[:8, :8], p[:8, 8:], p[8:, :8], p[8:, 8:]][k]


def star_tile(big):
    t = np.zeros((8, 8), np.uint8)
    if big:
        t[3:5, 1:7] = H; t[1:7, 3:5] = H; t[3:5, 3:5] = W
    else:
        t[3, 3] = W; t[2, 3] = L; t[4, 3] = L; t[3, 2] = L; t[3, 4] = L
    return t


def render_role(r, theme):
    if r == 'sky':
        return np.zeros((8, 8), np.uint8)
    if r == 'nfill':
        return layer_tex(theme, 'n')
    if r == 'ffill':
        return layer_tex(theme, 'f')
    if r == 'ndot':
        return detail_tile(theme, 'n')
    if r == 'ndot2':
        t = detail_tile(theme, 'n'); return t[:, ::-1].copy()
    if r == 'fdot':
        return detail_tile(theme, 'f')
    if isinstance(r, str) and r.startswith('cloud'):
        return cloud_tile(int(r[-1]), theme)
    if isinstance(r, str) and r.startswith('tree'):
        t = tree_tile(int(r[-1]), theme)
        if r.startswith('treef'):
            f = layer_tex(theme, 'f')
            t = np.where(t > 0, t, f).astype(np.uint8)
        return t
    if r in ('star', 'star2'):
        return star_tile(r == 'star2')
    kind, prof = r
    if kind == 'nsky':
        return profile_tile(theme, 'n', prof, None)
    if kind == 'fsky':
        return profile_tile(theme, 'f', prof, None)
    if kind == 'nfar':
        return profile_tile(theme, 'n', prof, layer_tex(theme, 'f'))
    raise KeyError(r)


ROW = {'n': 0, 'f': 1}


def role_row(r):
    if r in ('ffill', 'fdot') or (isinstance(r, tuple) and r[0] == 'fsky'):
        return 1
    if isinstance(r, str) and r.startswith('treef'):
        return 1
    if isinstance(r, str) and (r.startswith('cloud') or r.startswith('star')):
        return 1
    return 0


# ----------------------------------------------------------------- compositions
def heights(rng, n, base, amp, freq, slope=0.5):
    """Periodic height profile (px from the picture bottom) at n+1 tile boundaries."""
    nb = n // 2                               # sampled per 16 px block, multiples of 4 px
    x = np.arange(nb + 1) / nb
    h = np.full(nb + 1, float(base))
    for k in range(1, 4):
        h += amp / k * np.sin(2 * np.pi * (round(freq) * k * x + rng.random()))
    h = np.round(h / 4) * 4
    for i in range(1, nb + 1):                # limit the slope to 8 px per block
        h[i] = np.clip(h[i], h[i - 1] - 8, h[i - 1] + 8)
    for i in range(nb, 0, -1):                # close the loop (the picture repeats every 32 blocks)
        if abs(h[i] - h[(i + 1) % nb if i < nb else 1]) > 8 or i == nb:
            h[i] = np.clip(h[0] if i == nb else h[i], h[i - 1] - 8, h[i - 1] + 8)
    h[nb] = h[0]
    for i in range(nb - 1, 0, -1):
        h[i] = np.clip(h[i], h[i + 1] - 8, h[i + 1] + 8)
    ht = np.zeros(n + 1)
    ht[0::2] = h
    ht[1::2] = (h[:-1] + h[1:]) / 2
    return ht


def layer_roles(h, rows=54, cols=64):
    """-> rows x cols array of (hl, hr) local profiles per tile (0,0 empty, 8,8 fill)."""
    out = np.zeros((rows, cols, 2), np.int32)
    for r in range(rows):
        yb = (rows - 1 - r) * 8
        for c in range(cols):
            a = int(np.clip(h[c] - yb, 0, 8)); b = int(np.clip(h[c + 1] - yb, 0, 8))
            out[r, c] = (a // 2 * 2, b // 2 * 2)
    return out


def snap(p):
    a, b = int(p[0]), int(p[1])
    if abs(a - b) > 4:
        b = a + 4 * np.sign(b - a)
    return (a, b)


def compose(style, seed, core_only=False):
    """-> 54 x 64 grid of (role, hflip, vflip). style: hills / tall / night / castle / cave / ghost / crystal / woods."""
    rng = K.rng(seed)
    R, C = 54, 64
    g = [[('sky', 0, 0) for _ in range(C)] for _ in range(R)]
    far = near = None
    if style in ('hills', 'night', 'woods', 'tall', 'castle', 'crystal', 'ghost', 'cave'):
        fb = {'hills': 190, 'night': 170, 'woods': 230, 'tall': 260, 'castle': 240, 'crystal': 210, 'ghost': 300,
              'cave': 150}[style]
        nb = {'hills': 120, 'night': 110, 'woods': 160, 'tall': 170, 'castle': 140, 'crystal': 120, 'ghost': 200,
              'cave': 90}[style]
        if not core_only:
            far = layer_roles(heights(rng, C, fb, 26 if style != 'castle' else 18, 2 + rng.integers(0, 2)))
        near = layer_roles(heights(rng, C, nb, 22 if style != 'crystal' else 10, 1 + rng.integers(0, 3)))
    for r in range(R):
        for c in range(C):
            n = tuple(near[r, c]) if near is not None else (0, 0)
            f = tuple(far[r, c]) if far is not None else (0, 0)
            if n == (8, 8):
                role = 'nfill'
                if (r * 7 + c * 13 + seed) % 23 == 0:
                    role = 'ndot' if (c + r) % 2 else ('ndot2' if not core_only else 'ndot')
            elif n != (0, 0):
                n = snap(n)
                if far is not None and f == (8, 8) or (f != (0, 0) and sum(f) >= 8):
                    role = ('nfar', n)
                else:
                    role = ('nsky', n)
            elif f == (8, 8):
                role = 'ffill' if (r * 5 + c * 11 + seed) % 19 else 'fdot'
            elif f != (0, 0):
                role = ('fsky', snap(f))
            else:
                role = 'sky'
            g[r][c] = (role, 0, 0)
    # ceiling for caves / ghost halls: mirror a second near layer from the top (v-flipped tiles)
    if style in ('cave', 'ghost'):
        top = layer_roles(heights(rng, C, 70 if style == 'cave' else 50, 18, 2))
        for r in range(R):
            for c in range(C):
                p = tuple(top[R - 1 - r, c])
                if p == (8, 8):
                    g[r][c] = ('nfill', 0, 1)
                elif p != (0, 0) and g[r][c][0] == 'sky':
                    g[r][c] = (('nsky', snap(p)), 0, 1)
    # trees standing on flat stretches of the near layer
    if not core_only and style in ('hills', 'woods', 'tall', 'night', 'cave'):
        for c in range(0, C - 1, 2):
            if rng.random() > (0.35 if style == 'woods' else 0.15):
                continue
            for r in range(2, R):
                if g[r][c][0] == 'nfill' and g[r][c + 1][0] == 'nfill' and g[r - 1][c][0] != 'nfill':
                    rr = r - 2 if g[r - 1][c][0] == 'sky' else r - 3
                    cells = [g[rr + dr][c + dc][0] for dr in (0, 1) for dc in (0, 1)] if rr >= 0 else []
                    if cells and all(x == 'sky' for x in cells):
                        nm = 'tree'
                    elif cells and all(x in ('ffill', 'fdot') for x in cells):
                        nm = 'treef'
                    else:
                        nm = None
                    if nm:
                        for k, (dr, dc) in enumerate(((0, 0), (0, 1), (1, 0), (1, 1))):
                            g[rr + dr][c + dc] = ('%s%d' % (nm, k), 0, 0)
                    break
    # clouds / stalactites / stars in the open sky
    def free(r, c):
        return all(0 <= r + dr < R and g[r + dr][(c + dc) % C][0] == 'sky' for dr in (0, 1) for dc in (0, 1))
    n_cl = {'hills': 7, 'tall': 5, 'woods': 3, 'night': 2, 'castle': 3, 'crystal': 2, 'cave': 6, 'ghost': 0}[style]
    for _ in range(n_cl * 4):
        if n_cl <= 0:
            break
        r, c = int(rng.integers(2, 30)), int(rng.integers(0, C))
        if style == 'cave':
            r = int(rng.integers(8, 20))
        if free(r, c):
            for k, (dr, dc) in enumerate(((0, 0), (0, 1), (1, 0), (1, 1))):
                g[r + dr][(c + dc) % C] = ('cloud%d' % k, 0, 0)
            n_cl -= 1
    if style in ('night', 'crystal', 'ghost'):
        for _ in range(40):
            r, c = int(rng.integers(0, 34)), int(rng.integers(0, C))
            if g[r][c][0] == 'sky':
                g[r][c] = ('star2' if rng.random() < 0.2 and not core_only else 'star', 0, 0)
    return g


# ----------------------------------------------------------------- build
def rle(data):
    out, i, n = bytearray(), 0, len(data)
    while i < n:
        j = i
        while j < n and data[j] == data[i] and j - i < 128:
            j += 1
        if j - i >= 3:
            out += bytes([0x80 | (j - i - 1), data[i]]); i = j; continue
        k = i
        while k < n and k - i < 128 and not (k + 2 < n and data[k] == data[k + 1] == data[k + 2]):
            k += 1
        out += bytes([k - i - 1]) + bytes(data[i:k]); i = k
    return bytes(out) + b'\xff\xff'


def unrle(src):
    out, i = bytearray(), 0
    while True:
        r = src[i]; i += 1
        if r & 0x80:
            out += bytes([src[i]]) * ((r & 0x7F) + 1); i += 1
        else:
            out += src[i:i + r + 1]; i += r + 1
        if src[i] == 0xFF and src[i + 1] == 0xFF:
            return bytes(out)


STYLE_BY_TS = {0: 'hills', 7: 'hills', 12: 'woods', 1: 'castle', 11: 'castle', 2: 'tall', 6: 'cave', 8: 'tall',
               3: 'cave', 9: 'cave', 14: 'cave', 5: 'ghost', 13: 'ghost', 4: 'crystal', 10: 'crystal'}


def build(items, survey, sheets):
    core, rest = roles()
    free0d = sorted(set(survey['usage']['0D']['fg']) | set(survey['usage']['0D']['bg']))
    pos = {}
    for r, i in zip(core, free0d):
        pos[r] = i
    taken = set(pos.values())
    pool = [i for i in range(128) if i not in taken]
    for r in core[len(free0d):] + rest:
        pos[r] = pool.pop(0)
    # unique pictures: one per distinct retail blob (grouping only), style from the tilesets it is paired with
    pairing = survey['bg_pairing']
    level_ids = survey['level_bg_id']
    styles = {}
    for k, v in pairing.items():
        ts = max(((int(a[2:]), n) for a, n in v.items() if a.startswith('ts')), key=lambda t: t[1])[0]
        styles[int(k)] = STYLE_BY_TS.get(ts, 'hills')
        if any(a in v for a in ('ts9', 'ts13')):          # shown with sheet 0D: core roles only
            styles[int(k)] += '/core'
    vocab, words = {}, []

    def block_id(key):
        if key not in vocab:
            vocab[key] = len(vocab)
        return vocab[key]

    def picture(style, seed, core_only):
        g = compose(style, seed, core_only)
        ids = np.zeros((27, 32), np.int32)
        for br in range(27):
            for bc in range(32):
                q = tuple(g[br * 2 + dr][bc * 2 + dc] for dr in (0, 1) for dc in (0, 1))
                ids[br, bc] = block_id(q)
        lo = bytearray(864)
        for scr in range(2):
            for br in range(27):
                for bc in range(16):
                    lo[scr * 432 + br * 16 + bc] = ids[br, scr * 16 + bc]
        return bytes(lo)

    out, pics = {}, {}
    variety = ['hills', 'night', 'tall', 'woods']
    for t in TABLES:
        arr = A.unpack_array(items[t])
        flags = items[t + '_IsBg']
        uniq = {}
        for k, blob in enumerate(arr):
            if k >= len(flags) or not (flags[k] & 2) or not blob:
                continue
            if t == 'kLevelData_Layer2' and level_ids[k] is not None:
                # own grouping (three picture variants per BG family), so the shared-entry index
                # table of the packed array does not repeat the retail pattern
                key = ('L', level_ids[k], (k * 7 + level_ids[k]) % 3)
                style = styles.get(level_ids[k], 'hills')
                core_only = style.endswith('/core')
                style = style.split('/')[0]
                if style == 'hills':
                    style = variety[level_ids[k] % len(variety)]
            else:
                key = (t, bytes(blob))
                style = variety[(len(uniq) + len(t)) % len(variety)] if t != 'kRollCallData_Layer2' else 'night'
                core_only = False
            if key not in uniq:
                uniq[key] = len(uniq)
            if key not in pics:
                pics[key] = rle(picture(style, 1000 + len(pics) * 37, core_only))
            arr[k] = pics[key]
        out[t] = A.pack_array(arr)
    # BG Map16: vocabulary in both halves (the BG flag picks the half)
    m16 = bytearray(0x1000)
    for key, i in vocab.items():
        ws = []
        for (role, hf, vf) in key:
            ws.append((0x100 + pos[role]) | role_row(role) << 10 | hf << 14 | vf << 15)
        b = np.array([ws[0], ws[2], ws[1], ws[3]], '<u2').tobytes()       # TL, BL, TR, BR
        if i < 256:
            m16[8 * i:8 * i + 8] = b
            m16[0x800 + 8 * i:0x800 + 8 * i + 8] = b
    # sheets
    raw = [lz2.decompress(c) for c in A.unpack_array(items['kGraphicsPtrs'])]
    for s, theme in BG_SHEETS.items():
        img = TL.decode(raw[s], 3)[:128].copy() if s == 0x0D else np.zeros((128, 8, 8), np.uint8)
        if s == 0x0D:
            img[free0d] = 0            # level tiles of 0D without a role stay clear
        for r, i in pos.items():
            if s == 0x0D and i not in free0d:
                continue
            img[i] = render_role(r, theme)
        sheets[s] = img
    stats = '%d BG blocks, %d pictures, %d tiles' % (len(vocab), len(pics), len(pos))
    assert len(vocab) <= 256, stats
    return {'entries': out, 'map16': bytes(m16), 'stats': stats}
