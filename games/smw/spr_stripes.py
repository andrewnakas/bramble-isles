"""CLEAN ROOM. Our own arrangements for the picture-only stripe images (kLoadStripeImagePtrs) and the
remaining layer-3 images (kLayer3ImagePtrs): tide water, cloud bands, star field, the overworld frame,
the map arrows, the cutscene backgrounds, and the "clear" stripes.

Kept from the originals (structure the code and the screen layout depend on): which tilemap cells a
stripe covers, which tile codes / palettes mean what (piece vocabulary: water surface, cloud ends, frame
edge, shadow, fill), the window of the overworld frame, the castle's place in the cutscene. The layout
inside (patterns, motif placement, cloud and star positions, cluster placement, mirroring) and the byte
encoding (our run builder with fills) are ours.
"""
from collections import Counter

import numpy as np

from games.smw import spr_text as T

H, V = 0x4000, 0x8000


# ------------------------------------------------------------------ encoding
def encode(cells, min_fill=6):
    """{absolute word address: cell word} -> stripe bytes: horizontal runs within 32-cell rows, runs of
    >= min_fill equal cells become fill entries."""
    out = bytearray()
    keys = sorted(cells)
    i = 0
    while i < len(keys):
        a = keys[i]
        run = [cells[a]]
        while i + len(run) < len(keys) and keys[i + len(run)] == a + len(run) and (a + len(run)) % 32:
            run.append(cells[a + len(run)])
        j = 0
        while j < len(run):
            k = j
            while k < len(run) and run[k] == run[j]:
                k += 1
            if k - j >= min_fill:
                n = 2 * (k - j) - 1
                ad = a + j
                out += bytes([ad >> 8, ad & 0xFF, 0x40 | (n >> 8) & 0x3F, n & 0xFF, run[j] & 0xFF, run[j] >> 8])
                j = k
            else:
                e = j
                while e < len(run):
                    k = e
                    while k < len(run) and run[k] == run[e]:
                        k += 1
                    if k - e >= min_fill:
                        break
                    e = k
                n = 2 * (e - j) - 1
                ad = a + j
                out += bytes([ad >> 8, ad & 0xFF, (n >> 8) & 0x3F, n & 0xFF])
                for w in run[j:e]:
                    out += bytes([w & 0xFF, w >> 8])
                j = e
        i += len(run)
    return bytes(out + b'\xff')

def fill_chunks(cells, n):
    """A large clear: fill entries of n cells over each contiguous stretch."""
    out = bytearray()
    keys = sorted(cells, key=lambda a: (-(a & 0xF000), a))       # last layer first
    i = 0
    while i < len(keys):
        a, k = keys[i], 1
        while i + k < len(keys) and keys[i + k] == a + k and cells[keys[i + k]] == cells[a] and k < n:
            k += 1
        m = 2 * k - 1
        out += bytes([a >> 8, a & 0xFF, 0x40 | (m >> 8) & 0x3F, m & 0xFF, cells[a] & 0xFF, cells[a] >> 8])
        i += k
    return bytes(out) + bytes([0xFF])


def clear_like(cells_src, word):
    return encode({a: word for a in cells_src}, min_fill=3)




def cells_of(d):
    """{absolute word address: word} of any stripe (all layers). Dirty side only (facts())."""
    out = {}
    for addr, vert, cells in T.parse(d):
        for n, w in enumerate(cells):
            out[addr + (32 * n if vert else n)] = w
    return out


def runs(addrs):
    """addresses -> [[start, count], ...]"""
    out = []
    for a in sorted(addrs):
        if out and out[-1][0] + out[-1][1] == a:
            out[-1][1] += 1
        else:
            out.append([a, 1])
    return out


def unruns(rs):
    return [a + k for a, n in rs for k in range(n)]


# ================================================================== DIRTY side: structural facts
def facts(kept_st, kept_l3):
    """Run by games/smw/extract_sprite_slots (dirty room): positions, piece vocabulary, counts only."""
    f = {'l3': {}, 'st': {}}
    tide_i = [i for i, d in enumerate(kept_l3) if len(d) == 149]
    c = cells_of(kept_l3[tide_i[0]])
    f['l3']['tide'] = {'indices': tide_i, 'cells': runs(c),
                       'surf': sorted({c[a] & ~(H | V) for a in c if (a & 0x3FF) < 32}),
                       'fill': Counter(c.values()).most_common(1)[0][0]}
    cl = [i for i, d in enumerate(kept_l3) if len(d) == 1081]
    c = cells_of(kept_l3[cl[0]])
    solid = Counter(w for w in c.values() if (w & 0x3FF) == 0x0FF).most_common(1)[0][0]
    end = Counter(w for w in c.values() if (w & 0x3FF) == 0x19E).most_common(1)[0][0]
    f['l3']['clouds'] = {'indices': cl, 'bases': sorted({a & ~0x3FF for a in c}), 'solid': solid, 'end': end}
    sx = [i for i, d in enumerate(kept_l3) if len(d) == 201]
    c = cells_of(kept_l3[sx[0]])
    f['l3']['stars'] = {'indices': sx, 'bases': sorted({a & ~0x3FF for a in c}),
                        'words': [w for w, _ in Counter(c.values()).most_common(2)]}
    c = cells_of(kept_st[2])
    fillish = {a for a, w in c.items() if (w & 0x3FF) in (0x0FE, 0x095, 0x096, 0x097)}
    f['st']['2'] = {'fill': runs(fillish),
                    'attr': Counter(c[a] & 0xFC00 & ~(H | V) for a in fillish).most_common(1)[0][0],
                    'pieces': sorted([a, w] for a, w in c.items() if a not in fillish)}
    f['st']['7'] = sorted([a, w] for a, w in cells_of(kept_st[7]).items())
    f['st']['8'] = next(iter(cells_of(kept_st[8]).values()))
    c = cells_of(kept_st[9])
    f['st']['9'] = {'cells': runs(c), 'word': next(iter(c.values()))}
    c = cells_of(kept_st[70])
    rr = []
    for a, n in runs(c):          # split where the word changes
        for k in range(n):
            w = c[a + k]
            if rr and rr[-1][0] + rr[-1][1] == a + k and rr[-1][2] == w:
                rr[-1][1] += 1
            else:
                rr.append([a + k, 1, w])
    f['st']['70'] = rr
    bg = {}
    for i in (5, 67, 68, 69, 85):
        c = cells_of(kept_st[i])
        fill = Counter(c.values()).most_common(1)[0][0]
        pic = {a: w for a, w in c.items() if w != fill}
        rows = {}
        for a in pic:
            rows.setdefault(a // 32, []).append(a)
        bands = {}
        for row, cells in rows.items():
            ws = [pic[a] for a in cells]
            if len(ws) >= 12 and len(set(ws)) <= 4:
                bands[str(row)] = {'cells': runs(cells), 'words': [w for w, _ in Counter(ws).most_common()]}
        rest = {a for a in pic if str(a // 32) not in bands}
        clusters, seen = [], set()
        for a0 in sorted(rest):
            if a0 in seen:
                continue
            comp, todo = [], [a0]
            seen.add(a0)
            while todo:
                a = todo.pop()
                comp.append(a)
                for d in (1, -1, 32, -32):
                    b = a + d
                    if b in rest and b not in seen and (d in (32, -32) or b // 32 == a // 32):
                        seen.add(b)
                        todo.append(b)
            clusters.append({'cells': runs(comp), 'words': sorted({pic[a] for a in comp})})
        bg[str(i)] = {'fill': fill, 'cells': runs(c), 'bands': bands, 'clusters': clusters}
    f['st']['bg'] = bg
    return f


# ================================================================== CLEAN side: our arrangements
def tide(t):
    cells = unruns(t['cells'])
    surf, fill = t['surf'], t['fill']
    pat = [surf[0], surf[-1], surf[-1] | H, surf[0] | H, surf[-1], surf[0] | H]
    tops = {}
    for a in cells:
        b = a & ~0x3FF
        tops[b] = min(tops.get(b, 1 << 20), (a - b) // 32)
    out = {}
    for a in cells:
        b = a & ~0x3FF
        r, x = (a - b) // 32, a % 32
        if r == tops[b]:
            out[a] = pat[(x * 5 + 2) % len(pat)]
        elif r == tops[b] + 1:
            out[a] = fill | (H if (x // 3) % 2 else 0)
        else:
            out[a] = fill
    return encode(out)


def clouds(cf, seed=77):
    solid, e = cf['solid'], cf['end']
    lt, lb, rt, rb = e, e ^ V, e ^ H, e ^ H ^ V
    rng = np.random.default_rng(seed)
    lo = cf['bases'][0]
    out, band = {}, []
    for pair in ((0, 1), (2, 3)):
        for r0 in (range(28, 31) if pair == (0, 1) else range(1, 20, 3)):
            x = int(rng.integers(0, 10))
            while x < 30:
                ln = int(rng.integers(4, 13))
                band.append((pair, r0, x, min(31, x + ln)))
                x += ln + int(rng.integers(3, 9))
    for pair, r0, x0, x1 in band:
        for s in pair:
            b = lo + s * 0x400
            for rr, (le, re) in enumerate(((lt, rt), (lb, rb))):
                y = r0 + rr
                if y > 31:
                    continue
                for x in range(x0, x1 + 1):
                    out[b + y * 32 + x] = le if x == x0 else re if x == x1 else solid
    return encode(out)


def stars(sf, seed=29):
    rng = np.random.default_rng(seed)
    words = sf['words']
    out = {}
    pts = [(int(rng.integers(0, 22)), int(rng.integers(0, 32))) for _ in range(9)]
    for k, b in enumerate(sf['bases']):
        dy = 10 if k < 2 else 0
        for i, (r, x) in enumerate(pts):
            out[b + (r + dy) % 32 * 32 + x] = words[i % len(words)]
    return encode(out)


def overworld_frame(ff):
    MOTIF = (0x095, 0x096, 0x097)
    attr = ff['attr']
    out = {}
    for a in unruns(ff['fill']):
        r, x = (a - 0x5000) // 32, (a - 0x5000) % 32
        out[a] = 0x0FE | attr if (r * 3 + x * 2) % 11 else MOTIF[(r + x) % 3] | attr | (H if r % 2 else 0)
    for a, w in ff['pieces']:
        r, x = (a - 0x5000) // 32, (a - 0x5000) % 32
        code = w & 0x3FF
        if code == 0x093:                        # top / bottom edge: alternate flips
            w ^= H if x % 2 else 0
        elif code == 0x094:                      # side edge
            w ^= V if r % 2 else 0
        out[a] = w
    return encode(out, min_fill=4)


def arrows(cells):
    return encode({a: w ^ (H if a % 2 else 0) for a, w in cells}, min_fill=99)


def bg_scene(bf, seed, move=True):
    """Cutscene background: fill, ground bands re-patterned, each cluster re-laid from its piece
    vocabulary in our own pattern, mirrored and (optionally) moved inside the picture."""
    fill = bf['fill']
    out = dict.fromkeys(unruns(bf['cells']), fill)
    rng = np.random.default_rng(seed)
    for row in sorted(bf['bands'], key=int):
        b = bf['bands'][row]
        uniq = b['words']
        for i, a in enumerate(unruns(b['cells'])):
            out[a] = uniq[(i + i // 3) % len(uniq)]
    for cl in bf['clusters']:
        comp = unruns(cl['cells'])
        words = cl['words']
        xs = [a % 32 for a in comp]
        ys = [a // 32 for a in comp]
        x0, x1, y0 = min(xs), max(xs), min(ys)
        dx = int(rng.integers(-3, 4)) if move else 0
        if x0 + dx < 0 or x1 + dx > 31:
            dx = 0
        for a in comp:
            out[a] = fill
        for a in comp:
            r, x = a // 32, a % 32
            na = r * 32 + (x0 + x1 - x + dx)
            if na in out:
                out[na] = words[((r - y0) * 3 + (x - x0) * 5) % len(words)] ^ H
    return encode(out)


def build(f, st, l3):
    """f = spec facts (sprite_struct.json 'stripes'); st / l3 = current lists -> (stripes, layer-3, owned)."""
    st, l3 = list(st), list(l3)
    L = f['l3']
    for i in L['tide']['indices']:
        l3[i] = tide(L['tide'])
    for i in L['clouds']['indices']:
        l3[i] = clouds(L['clouds'])
    for i in L['stars']['indices']:
        l3[i] = stars(L['stars'])
    S = f['st']
    st[2] = overworld_frame(S['2'])
    st[7] = arrows(S['7'])
    st[8] = clear_like([a for a, _ in S['7']], S['8'])
    st[9] = clear_like(unruns(S['9']['cells']), S['9']['word'])
    st[70] = fill_chunks({a + k: w for a, n, w in S['70'] for k in range(n)}, 384)
    for i in ('5', '67', '68', '85'):
        st[int(i)] = bg_scene(S['bg'][i], int(i))
    st[69] = bg_scene(S['bg']['69'], 69, move=False)
    return st, l3, (2, 5, 7, 8, 9, 67, 68, 69, 70, 85)
