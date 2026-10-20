"""CLEAN ROOM. Our own overworld (module `overworld` of generate.py): the Bramble Isles,
a sea of small islands. Every level stands on its own islet; plank bridges (our routes)
link them and appear plank by plank when a level is beaten; stepping stones mark the
hard-wired crossings; a few wooded islands of our own fill the open sea.

Kept from retail (spec/ow.json + kept tables): node cells and codes, event-changed cells,
which node connects to which (leave/arrive direction), event numbers and reveal order,
submap exits, warps, hard-wired paths, the static reveal tile numbers of the port's code.
Everything else is ours: routes (ow_plan), terrain, tiles (GFX 1C/1D/1E, ow_art), Map16,
palettes, layer-2 maps and the event reveal tiles.
"""
import os
import struct

import numpy as np

from games.smw import assetfile as A, ow_plan as P, ow_walk as Wk, ow_art as Art
from games.smw import ow_render as R
from cleanroom.snes import lz2, tiles as T

HERE = os.path.dirname(__file__)
STEP = P.STEP
DIRN = {(0, -1): 0, (0, 1): 2, (-1, 0): 4, (1, 0): 6}


def kept_items():
    """Structural tables (spec/tables.dat; the older kept.dat if that is all there is)."""
    for n in ('tables.dat', 'kept.dat'):
        p = os.path.join(HERE, 'spec', n)
        if os.path.exists(p):
            return dict(A.read(p))
    raise FileNotFoundError('spec/tables.dat')


def hard_routes(spec, items=None):
    """[(start, [cells])] of the hard-wired paths (kOwHardcodedPath* tables)."""
    items = items or kept_items()
    g0 = np.zeros((64, 32), np.uint8)
    for x, y, cf, ci in spec['nodes']:
        g0[y, x] = ci
    for x, y, ci, cf in spec['fixed']:
        g0[y, x] = ci
    flat = R.l1_blob(g0)
    tp, r0 = {}, 1
    for j in range(0x800):
        if 0x56 <= flat[j] < 0x81:
            x = (j & 15) | ((j >> 8) & 1) << 4
            y = ((j >> 4) & 15) | ((j >> 9) & 1) << 4 | ((j >> 10) & 1) << 5
            tp[r0] = (x, y)
            r0 += 1
    lv = list(items['kOwHardcodedPathLevel_049078'])
    st = list(items['kOwHardcodedPathStartIndex_04910E'])
    dirs = list(items['kOwHardcodedPathDirs_0490CA'])
    ci2 = R.u16(items['kOwHardcodedPathChocolateIsland2_049082'])
    out = []
    for k in range(len(lv)):
        x, y = (int(ci2[1]) >> 4, int(ci2[0]) >> 4) if lv[k] == 0xff else tp[lv[k]]
        start = (x, y)
        end = st[k + 1] if k + 1 < len(st) else len(dirs)
        cells = []
        for i in range(st[k], end):
            x, y = x + STEP[dirs[i]][0], y + STEP[dirs[i]][1]
            cells.append((x, y))
        out.append((start, cells))
    return out


def hard_route_cells(spec, items=None):
    return [c for _, cs in hard_routes(spec, items) for c in cs]


def plan(spec, items):
    p = P.Planner(spec, Wk.tables_from_items(items))
    fails = p.plan()
    return p, fails


# ------------------------------------------------------------------ sheets


class Sheets:
    """GFX 1C, 1D, 1E as (128, 8, 8) index arrays; BG tile numbers 0x000/0x080/0x180."""
    BASE = {0x1c: 0x000, 0x1d: 0x080, 0x1e: 0x180}

    def __init__(self):
        self.t = {k: np.zeros((128, 8, 8), np.uint8) for k in self.BASE}
        self.used = {k: set() for k in self.BASE}
        self.cache = {}
        for k in range(0x75, 0x80):      # VRAM 0x75-0x7F are animated: never static art
            self.used[0x1c].add(k)
        self.used[0x1c].add(0)           # 1C tile 0 stays empty (transparent)
        for k in (80, 81, 82):           # GFX 1E 80-82: sea animation sources (the other frames are free:
            self.used[0x1e].add(k)       # our map never shows the animated tiles 0x78-0x7F)

    def put(self, sheet, idx, tile):
        self.t[sheet][idx] = tile
        self.used[sheet].add(idx)
        return self.BASE[sheet] + idx

    def alloc(self, sheet, tile, order=None):
        key = (sheet, tile.tobytes())
        if key in self.cache:
            return self.cache[key]
        for i in (order or range(128)):
            if i not in self.used[sheet]:
                n = self.put(sheet, i, tile)
                self.cache[key] = n
                return n
        raise RuntimeError('sheet %02X full' % sheet)

    def alloc_any(self, tile):
        for s in (0x1c, 0x1d):
            try:
                return self.alloc(s, tile)
            except RuntimeError:
                continue
        raise RuntimeError('1C/1D full')


def word(tile, pal, h=False, v=False):
    return tile | pal << 10 | (0x4000 if h else 0) | (0x8000 if v else 0)


# ------------------------------------------------------------------ layout


class World:
    def __init__(self, spec, p, items):
        self.spec, self.p, self.items = spec, p, items
        self.g = p.grid
        self.shape = {}       # cell -> ('H'|'V'|'DR'|'UL'|'UR'|'DL')
        self.cell_event = {}  # cell -> event (-1 visible)
        self.reveal = {}      # event -> [cells in order]
        self.kind = {}        # cell -> 'bridge' | 'islet' | 'stones'
        self.nodes = {(x, y) for x, y, _, _ in spec['nodes']}
        self.route_cells()
        self.hard()
        self.islands()

    def route_cells(self):
        segs = self.spec['segs']
        order = []
        for i in sorted(self.p.paths):
            s = segs[i]
            pts = [tuple(s['a'])]
            k = 0
            vias = [(v[0], v[1]) for v in s['via']]
            for q, cells in enumerate(self.p.paths[i]):
                pts += cells
                if q < len(vias):
                    pts.append(vias[q])
            pts.append(tuple(s['b']))
            body = pts[1:-1] + ([pts[-1]] if s['kind'] == 'exit' else [])
            for n in range(1, len(pts) - (0 if s['kind'] == 'exit' else 1)):
                c = pts[n]
                if c in self.nodes:
                    continue
                a = pts[n - 1]
                b = pts[n + 1] if n + 1 < len(pts) else (2 * c[0] - a[0], 2 * c[1] - a[1])
                d1 = DIRN[(c[0] - a[0], c[1] - a[1])]
                d2 = DIRN[(b[0] - c[0], b[1] - c[1])]
                self.shape[c] = shape_of(d1, d2)
                self.kind[c] = 'bridge'
            evs = per_cell_events(s['reveal'], len(body))
            if s.get('from_b'):
                body, evs = body[::-1], evs[::-1]
            order.append((body, evs))
        for body, evs in order:
            for c, e in zip(body, evs):
                if c in self.nodes or c in self.cell_event:
                    continue
                self.cell_event[c] = e
                if e >= 0:
                    self.reveal.setdefault(e, []).append(c)

    def hard(self):
        for (start, cells), h in zip(hard_routes(self.spec, self.items), self.spec['hard']):
            evs = per_cell_events(h['reveal'], len(cells))
            for c, e in zip(cells, evs):
                if c in self.nodes or c in self.kind:
                    continue
                self.kind[c] = 'stones'
                if c not in self.cell_event:
                    self.cell_event[c] = e
                    if e >= 0:
                        self.reveal.setdefault(e, []).append(c)

    def islands(self):
        """Our wooded islands: blobs in open sea, two cells clear of every route, ~9 % of each map."""
        self.land = np.zeros((2, 65, 65), bool)       # tile-corner land field per half
        busy = np.zeros((64, 32), bool)
        for c in list(self.kind) + list(self.nodes):
            busy[c[1], c[0]] = True
        for x, y, _, _ in self.spec['fixed']:
            busy[y, x] = True
        near = busy.copy()
        for _ in range(2):
            n2 = near.copy()
            n2[1:] |= near[:-1]
            n2[:-1] |= near[1:]
            n2[:, 1:] |= near[:, :-1]
            n2[:, :-1] |= near[:, 1:]
            near = n2
        for m in range(7):
            cells = maps_cells(m)
            inmap = set(cells)
            half = 0 if m == 0 else 1
            budget = int(0.09 * len(cells))
            free = [c for c in cells if not near[c[1], c[0]]]
            rng = np.random.default_rng(1009 + m)
            rng.shuffle(free)
            got = 0

            def corner_ok(tx, ty):
                for qx in {(tx - 1) // 2, tx // 2}:
                    for qy in {(ty - 1) // 2, ty // 2}:
                        c = (qx, qy + 32 * half)
                        if c not in inmap or near[c[1], c[0]]:
                            return False
                return True
            for cx, cy in free:
                if got >= budget:
                    break
                rx, ry = rng.uniform(1.0, 2.6), rng.uniform(0.9, 2.2)
                ox, oy = cx * 2 + 1, (cy - 32 * half) * 2 + 1      # tile-corner coords of the cell centre
                pts = []
                for ty in range(int(oy - ry * 2 - 1), int(oy + ry * 2 + 2)):
                    for tx in range(int(ox - rx * 2 - 1), int(ox + rx * 2 + 2)):
                        if not (1 <= tx <= 63 and 1 <= ty <= 63):
                            continue
                        d = ((tx - ox) / (rx * 2)) ** 2 + ((ty - oy) / (ry * 2)) ** 2
                        d += 0.25 * (Art.hashf(tx, ty, m) - 0.5)
                        if d < 1 and corner_ok(tx, ty):
                            pts.append((tx, ty))
                if len(pts) < 6:
                    continue
                for tx, ty in pts:
                    self.land[half, ty, tx] = True
                got += len(pts) // 4


def maps_cells(m):
    if m == 0:
        return [(x, y) for y in range(1, 31) for x in range(1, 31)]
    x0, x1, y0, y1 = P.window(m)
    return [(x, y + 32) for y in range(y0, y1) for x in range(x0, x1)]


def shape_of(d1, d2):
    if d1 == d2:
        return 'H' if d1 in (4, 6) else 'V'
    ends = {P.REV[d1], d2}           # the two sides the cell connects
    name = {frozenset((2, 6)): 'DR', frozenset((0, 4)): 'UL', frozenset((0, 6)): 'UR', frozenset((2, 4)): 'DL'}
    return name[frozenset(ends)]


def per_cell_events(runs, n):
    """Reveal runs [[event, fraction], ...] -> one event per cell (-1 = visible from the start).
    A visible run between two hidden ones takes the event before it."""
    if n == 0:
        return []
    out = []
    acc = 0.0
    for k, (e, f) in enumerate(runs):
        acc += f
        while len(out) < round(acc * n):
            out.append(e)
    while len(out) < n:
        out.append(runs[-1][0])
    first = next((i for i, e in enumerate(out) if e >= 0), None)
    if first is None:
        return out
    last = out[first]
    for i in range(first, n):
        if out[i] < 0:
            out[i] = last
        else:
            last = out[i]
    return out


# ------------------------------------------------------------------ art assembly


class Painter:
    def __init__(self):
        self.sh = Sheets()
        self.place_fixed_icons()
        self.coast = {}
        for combo in range(16):
            c = ((combo >> 3) & 1, (combo >> 2) & 1, (combo >> 1) & 1, combo & 1)
            self.coast[combo] = [self.sh.alloc(0x1c, Art.coast_tile(c, v)) for v in range(2)]
        self.grass = [self.sh.alloc(0x1c, Art.grass_tile(v)) for v in range(4)]
        self.water_static = [self.sh.alloc(0x1c, np.array([[Art.water_px(x, y, s) for x in range(8)] for y in range(8)], np.uint8)) for s in range(2)]
        self.bridge = self.make16(Art.bridge_h())
        self.bridge_v = self.make16(Art.bridge_h().T.copy())
        self.corner = self.make16(Art.bridge_corner())
        self.stones = self.make16(Art.stones())
        self.islet_q = self.sh.alloc(0x1c, Art.islet()[:8, :8])
        self.decor = {k: self.make16(Art.sketch(v), sheet=0x1d) for k, v in Art.DECOR.items()}
        self.water_anim()

    def make16(self, img, sheet=0x1c):
        return [self.sh.alloc(sheet, q.copy()) if sheet == 0x1c else self.sh.alloc(0x1d, q.copy()) for q in Art.quads(img)]

    # ---- the port's code hard-wires these tile numbers for revealed level tiles
    def place_fixed_icons(self):
        s = self.sh
        e = 0x1e
        s.put(e, 0x06, Art.icon('berry_small_q'))
        s.put(e, 0x16, Art.icon('berry_big_q'))
        k = Art.icon('keep')
        tl, tr, bl, br = Art.quads(k)
        s.put(e, 0x08, tl), s.put(e, 0x09, tr), s.put(e, 0x18, bl), s.put(e, 0x19, br)
        for base, img in ((0x24, Art.sign_with('4')), (0x28, Art.sign_with('5')), (0x26, Art.icon('ladder')),
                          (0x22, Art.icon('hut')), (0x02, Art.icon('boulder'))):
            tl, tr, bl, br = Art.quads(img)
            s.put(e, base, tl), s.put(e, base + 1, tr), s.put(e, base + 0x10, bl), s.put(e, base + 0x11, br)
        post = Art.icon('post')
        s.put(e, 0x10, post)
        s.put(e, 0x11, post[:, ::-1].copy())
        st = Art.icon('star')
        tl, tr, bl, br = Art.quads(st)
        s.put(e, 0x48, tl), s.put(e, 0x49, tr), s.put(e, 0x78, bl), s.put(e, 0x79, br)
        d = Art.icon('door')
        tl, tr, bl, br = Art.quads(d)
        s.put(e, 0x42, tl), s.put(e, 0x43, tr), s.put(e, 0x52, bl), s.put(e, 0x53, br)
        sh = Art.mirror_half(Art.icon('shrine'))
        tl, tr, bl, br = Art.quads(sh)
        s.put(0x1d, 0x00, tl), s.put(0x1d, 0x01, tr), s.put(0x1d, 0x10, bl)
        s.used[0x1d].add(0x7f)           # 1D 0x7F: an empty tile
        # our own icons (free choice of tiles)
        self.icon = {}
        free = [i for i in range(64) if i not in s.used[e]]
        for name, img in (('tower', Art.icon('tower')), ('ruin', Art.icon('ruin')), ('home', Art.icon('home')),
                          ('log', Art.mirror_half(Art.icon('log'))), ('gate', Art.mirror_half(Art.icon('gate'))),
                          ('pressed', Art.mirror_half(Art.icon('shrine_pressed'))), ('sign3', Art.sign_with('3'))):
            ids = []
            for q in Art.quads(img):
                ids.append(s.alloc(e, q.copy(), order=free))
            self.icon[name] = ids

    def water_anim(self):
        """Animation sources: GFX 1E 80-82 feed VRAM 0x75-0x77 (scrolling sea), 3bpp, colours 0-7."""
        for k, seed in ((80, 21), (81, 22), (82, 23)):
            t = np.array([[Art.water_px(x, y, seed) for x in range(8)] for y in range(8)], np.uint8)
            if k == 81:
                t = np.where((np.arange(8)[:, None] % 4 == 0) & (np.arange(8)[None, :] % 4 == 1), 2, t).astype(np.uint8)
            self.sh.t[0x1e][k] = t
        # other animation slots: give them our own frames (a small glint) so nothing retail-like is left
        for k in range(64, 128):
            if k in (80, 81, 82, 0x42, 0x43, 0x48, 0x49, 0x52, 0x53, 0x78, 0x79):
                continue
            f = (k - 64) % 8
            t = np.zeros((8, 8), np.uint8)
            if f < 4:
                t[3, 3 + (f % 2)] = 3
                if f in (1, 2):
                    t[2, 3] = t[4, 3] = t[3, 2] = t[3, 4] = 3
            self.sh.t[0x1e][k] = t


def put16(ids, pal, h=False, v=False):
    """16x16 from quadrant tiles (TL, TR, BL, BR) with flips -> words for TL, TR, BL, BR."""
    tl, tr, bl, br = ids
    if h:
        tl, tr, bl, br = tr, tl, br, bl
    if v:
        tl, tr, bl, br = bl, br, tl, tr
    return [word(t, pal, h, v) for t in (tl, tr, bl, br)]


def sym16(q, pal):
    """4-fold symmetric 16x16 from its top-left quadrant."""
    return [word(q, pal), word(q, pal, h=True), word(q, pal, v=True), word(q, pal, h=True, v=True)]


# ------------------------------------------------------------------ map16 for layer 1


STATIC = {  # TilesToBecome code -> the port's fixed words (TL, BL, TR, BR): from its code, smw_04.c 04ECD3
}


def static_reveal_words():
    """The reveal stripes of OwEventProcess01 use fixed tile words (C table in smw_04.c)."""
    import re
    for pth in Wk.SRC:
        if os.path.exists(pth):
            s = open(pth, encoding='utf8', errors='replace').read()
            break
    m = re.search(r'kOverworldEventProcess01_DestroyTileAnimation_DATA_04ECD3\[176\] = \{([^}]*)\}', s)
    b = [int(x) for x in m.group(1).replace(' ', '').replace('\n', '').split(',') if x]
    return [[b[8 * i + 2 * k] | b[8 * i + 2 * k + 1] << 8 for k in range(4)] for i in range(22)]


def map16(items, pt):
    n = len(items['kMap16Data_OverworldLayer1']) // 8
    blank = word(0x0ff, 0)               # 1D 0x7F: our empty tile
    m = [[blank] * 4 for _ in range(n)]
    to = list(items['kChangingLayer1OverworldTiles_TilesToBecome'])
    stat = static_reveal_words()
    copies = {}

    def own(w):
        """Our own word for a tile the reveal code names by number: a mirrored copy of the
        same picture in another tile (so the reveal and the reloaded map look the same)."""
        t = w & 0x3ff
        if t == 0x122:                   # the port's blank (GFX 08): ours instead
            return blank
        if t not in copies:
            sheet = 0x1e if t >= 0x180 else 0x1d
            src = pt.sh.t[sheet][t - Sheets.BASE[sheet]][:, ::-1].copy()
            free = [k for k in range(64, 128) if k not in pt.sh.used[0x1e]] if sheet == 0x1e else None
            for k in (free or range(128)):
                if k not in pt.sh.used[sheet]:
                    copies[t] = pt.sh.put(sheet, k, src)
                    break
            else:
                raise RuntimeError('no room for a copy of tile %03x' % t)
        return (w & ~0x3ff & 0xffff) ^ 0x4000 | copies[t]
    for i, c in enumerate(to):
        if c < n:
            m[c] = [own(w) for w in stat[i]]

    def icon(code, ids, pal):           # ids TL, TR, BL, BR -> map16 TL, BL, TR, BR
        if code < n and code not in to:
            tl, tr, bl, br = ids
            m[code] = [word(tl, pal), word(bl, pal), word(tr, pal), word(br, pal)]
    I = pt.icon
    icon(0x5d, I['tower'], 2)
    icon(0x81, I['ruin'], 2)
    icon(0x56, I['home'], 3)
    icon(0x82, I['log'], 5)
    icon(0x5b, I['log'], 5)
    icon(0x61, I['gate'], 2)
    icon(0x64, I['gate'], 5)
    icon(0x62, I['sign3'], 4)
    icon(0x85, I['pressed'], 5)
    icon(0x86, I['pressed'], 3)
    icon(0x83, [0x1c2, 0x1c3, 0x1d2, 0x1d3], 4)
    for code, ids, pal in ((0x58, [0x188, 0x189, 0x198, 0x199], 5), (0x5f, [0x1c8, 0x1c9, 0x1f8, 0x1f9], 6)):
        if code < n and code not in to:
            tl, tr, bl, br = [own(word(t, pal)) for t in ids]
            m[code] = [tl, bl, tr, br]
    icon(0x7e, [0x186] * 4, 6)
    icon(0x80, [0x186] * 4, 6)
    for c in (0x7e, 0x80, 0x66, 0x6a):
        if c < n and c not in to:
            m[c] = [own(w) for w in (word(0x186, 6, v=True), word(0x186, 6), word(0x186, 6, h=True, v=True), word(0x186, 6, h=True))]
    return m


# ------------------------------------------------------------------ layer 2


class L2:
    def __init__(self):
        self.w = np.zeros((128, 64), np.uint16)     # tile words, rows 64.. = submap half

    def set16(self, cell, words4):
        x, y = cell
        ty = 2 * y if y < 32 else 64 + 2 * (y - 32)
        tl, tr, bl, br = words4
        self.w[ty, 2 * x], self.w[ty, 2 * x + 1] = tl, tr
        self.w[ty + 1, 2 * x], self.w[ty + 1, 2 * x + 1] = bl, br

    def get16(self, cell):
        x, y = cell
        ty = 2 * y if y < 32 else 64 + 2 * (y - 32)
        return [int(self.w[ty, 2 * x]), int(self.w[ty, 2 * x + 1]), int(self.w[ty + 1, 2 * x]), int(self.w[ty + 1, 2 * x + 1])]

    def blob(self):
        out = bytearray(0x4000)
        for ty in range(128):
            for tx in range(64):
                o = R.l2_offset(tx, ty)
                v = int(self.w[ty, tx])
                out[o], out[o + 1] = v & 0xff, v >> 8
        return bytes(out)


def paint(world, pt, final):
    """Layer-2 words of every cell: sea, coast, islands, islets, bridges (final = all revealed)."""
    l2 = L2()
    land = world.land
    for half in (0, 1):
        for ty in range(64):
            for tx in range(64):
                c = (land[half, ty, tx], land[half, ty, tx + 1], land[half, ty + 1, tx], land[half, ty + 1, tx + 1])
                combo = c[0] << 3 | c[1] << 2 | c[2] << 1 | c[3]
                h = Art.hashf(tx, ty, 5 + half)
                if combo == 0:
                    t = pt.water_static[int(h * 10) % 2]
                elif combo == 15:
                    t = pt.grass[int(h * 4) % 4]
                else:
                    t = pt.coast[combo][int(h * 2) % 2]
                l2.w[ty + 64 * half, tx] = word(t, 4)
    # decor on island interiors
    for half in (0, 1):
        for cy in range(32):
            for cx in range(32):
                if land[half, 2 * cy:2 * cy + 3, 2 * cx:2 * cx + 3].all():
                    h = Art.hashf(cx, cy, 31 + half)
                    if h < 0.62:
                        names = ['bush', 'bramble', 'bush', 'mound', 'rock', 'flowers', 'bramble']
                        k = names[int(h * 100) % len(names)]
                        l2.set16((cx, cy + 32 * half), [word(t, 6) for t in pt.decor[k]])
    # islets under nodes and the cells the event tables touch
    cells = set(world.nodes) | {(x, y) for x, y, _, _ in world.spec['fixed']}
    for c in cells:
        if world.kind.get(c) != 'bridge':
            l2.set16(c, sym16(pt.islet_q, 7))
    for c, k in world.kind.items():
        if c in world.nodes:
            continue
        e = world.cell_event.get(c, -1)
        if not final and e >= 0:
            continue
        l2.set16(c, route_words(world, pt, c, k))
    return l2


def route_words(world, pt, c, k):
    if k == 'stones':
        return [word(t, 7) for t in pt.stones]
    s = world.shape.get(c, 'H')
    if s == 'H':
        return [word(t, 5) for t in pt.bridge]
    if s == 'V':
        return [word(t, 5) for t in pt.bridge_v]
    return put16(pt.corner, 5, h=s in ('DL', 'UL'), v=s in ('UR', 'UL'))


# ------------------------------------------------------------------ events


def events(world, base, final, items):
    """Layer-2 event entries: per event, one 2x2 block per revealed cell in reveal order."""
    tiles = bytearray(0x900)
    props = bytearray(0x900)
    blocks = {}

    def block2(words4):
        key = tuple(words4)
        if key not in blocks:
            j = len(tiles)
            for w in words4:
                tiles.append(w & 0xff)
                props.append(w >> 8)
            blocks[key] = j
        return blocks[key]
    ent, ptr = [], []
    for e in range(120):
        ptr.append(len(ent))
        for c in world.reveal.get(e, []):
            j = block2(final.get16(c))
            x, y = c
            ty = 2 * y if y < 32 else 64 + 2 * (y - 32)
            ent.append((j, R.l2_offset(2 * x, ty)))
    ptr.append(len(ent))
    # silent layer-2 writes (kept event + place): our own tiles = the final map there
    sil = world.spec['silent']
    num = [e['code'] or 0 for e in sil]
    loc = R.u16(items['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TilemapLocation'])
    six = 0
    for i, e in enumerate(sil):
        if not e['layer']:
            continue
        tx, ty = R.l2_pos(int(loc[i]))
        if not e['six']:
            w4 = [int(final.w[ty, tx]), int(final.w[ty, (tx + 1) % 64]), int(final.w[ty + 1, tx]), int(final.w[ty + 1, (tx + 1) % 64])]
            num[i] = block2(w4)
        else:
            j = six * 36
            six += 1
            for dy in range(6):
                for dx in range(6):
                    w = int(final.w[min(127, ty + dy), (tx + dx) % 64])
                    tiles[j + dy * 6 + dx] = w & 0xff
                    props[j + dy * 6 + dx] = w >> 8
            num[i] = j
    out = {
        'kOverworldLayer2EventTilemap_Tiles': bytes(tiles),
        'kOverworldLayer2EventTilemap_Prop': R.evprop_encode(bytes(props)),
        'kLayer2EventData_TileEntries': b''.join(struct.pack('<HH', j, r4) for j, r4 in ent),
        'kLayer2EventData_Ptrs_04E359': struct.pack('<%dH' % len(ptr), *ptr),
        'kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TileNum': struct.pack('<%dH' % len(num), *num),
    }
    return out, len(ent), len(blocks)


# ------------------------------------------------------------------ build


def sheets_blob(items, pt):
    arr = A.unpack_array(items['kGraphicsPtrs'])
    for s in (0x1c, 0x1d, 0x1e):
        raw = T.encode(pt.sh.t[s], 3)
        arr[s] = lz2.compress(raw)
    return A.pack_array(arr)


def build(items, kept, spec_dir):
    spec = P.load_spec(spec_dir)
    p, fails = plan(spec, items)
    world = World(spec, p, items)
    pt = Painter()
    base = paint(world, pt, final=False)
    final = paint(world, pt, final=True)
    out = {}
    out['kLoadOverworldLayer1AndEvents_DATA_0CF7DF'] = R.l1_blob(p.grid)
    m16 = map16(items, pt)
    out['kMap16Data_OverworldLayer1'] = struct.pack('<%dH' % (4 * len(m16)), *[w for q in m16 for w in q])
    b = base.blob()
    out['kLoadOverworldLayer2AndEventsTilemaps_OverworldLayer2Tilemap'] = R.rle_encode(b[0::2])
    out['kLoadOverworldLayer2AndEventsTilemaps_OverworldLayer2Tilemap_Prop'] = R.rle_encode(b[1::2])
    ev, nent, nblk = events(world, base, final, items)
    out.update(ev)
    out['kGraphicsPtrs'] = sheets_blob(items, pt)
    out.update(Art.palettes())
    # destroyed-tile stripes: our Map16 words of the codes the destruction table writes
    m = lambda c: struct.pack('<4H', *m16[c])
    out['kOverworldEventProcess01_DestroyTileAnimation_DATA_04EE7A'] = m(0x85) + m(0x86) + m(0) + m(0x10) + m(0) + m(0x81)
    rng = np.random.default_rng(4242)
    out['kOverworldLightningAndRandomCloudSpawning'] = rng.integers(0, 256, len(items['kOverworldLightningAndRandomCloudSpawning']), dtype=np.uint8).tobytes()
    print('  overworld: %d connections routed (%d dropped %s), %d reveal tiles in %d blocks' % (
        len(p.paths), len(fails), fails, nent, nblk))
    return out
