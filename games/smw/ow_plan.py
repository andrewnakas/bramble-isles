"""CLEAN ROOM. Our own overworld routes: every connection between the kept nodes is
routed anew (detour waypoint + own cost field), keeping only the anchors from
spec/ow.json (node cells and codes, fixed event cells, leave/arrive directions,
reveal order). Result: layer-1 grid + path cells per segment with their events.
"""
import heapq
import json
import os
import random

import numpy as np

STEP = {0: (0, -1), 2: (0, 1), 4: (-1, 0), 6: (1, 0)}
REV = {0: 2, 2: 0, 4: 6, 6: 4}
H, V = 0x04, 0x10
CORNER = {frozenset((2, 6)): 0x0a, frozenset((0, 4)): 0x09, frozenset((0, 6)): 0x19, frozenset((2, 4)): 0x1a}
SHAPES = {'H': [0x04, 0x05, 0x15, 0x16, 0x06, 0x03, 0x14, 0x2b, 0x2c, 0x32, 0x33, 0x4e, 0x4f],
          'V': [0x10, 0x12, 0x0f, 0x1e, 0x20, 0x2a, 0x2f, 0x30, 0x31, 0x34, 0x3a, 0x3d, 0x41, 0x50],
          'DR': [0x0a, 0x07, 0x08, 0x0d, 0x28, 0x2e, 0x49], 'UL': [0x09, 0x0e, 0x11, 0x29, 0x2d],
          'UR': [0x19, 0x1f, 0x37], 'DL': [0x1a, 0x17, 0x35, 0x4a]}
ALT = {v[0]: v for v in SHAPES.values()}
CAMS = [(-17, -40), (-17, 128), (-17, 296), (240, -40), (240, 128), (240, 296)]


def window(sub):
    """Cells (x, y) usable by routes of submap `sub` (0 = main map, y in 0..31 of its half)."""
    if sub == 0:
        return (1, 31, 1, 30)
    cx, cy = CAMS[sub - 1]
    xs = [x for x in range(32) if cx <= x * 16 and x * 16 + 16 <= cx + 256]
    ys = [y for y in range(32) if cy + 24 <= y * 16 + 8 < cy + 208]
    return (min(xs), max(xs) + 1, min(ys), max(ys) + 1)


def submap_of(x, y):
    if y < 32:
        return 0
    y -= 32
    best = None
    for s in range(1, 7):
        x0, x1, y0, y1 = window(s)
        if x0 <= x < x1 and y0 <= y < y1:
            d = abs((y0 + y1) / 2 - y)
            if best is None or d < best[0]:
                best = (d, s)
    return best[1] if best else 1


def code_for(prev_dir, next_dir):
    """Path code for a cell entered moving prev_dir and left moving next_dir."""
    if prev_dir == next_dir:
        return H if prev_dir in (4, 6) else V
    return CORNER[frozenset((REV[prev_dir], next_dir))]


class Planner:
    def __init__(self, spec, tables, seed=7):
        self.spec = spec
        self.tables = tables
        from games.smw import ow_walk as Wk
        self.cands = Wk.walking_codes(tables['exits'])
        self.seed = seed
        self.grid = np.zeros((64, 32), np.uint8)
        self.occ = np.zeros((64, 32), bool)        # cells a new route may not use
        self.walk = np.zeros((64, 32), bool)       # cells the walker can step on
        self.corners = set()                       # cells that must have no extra walkable neighbours
        wk = lambda c: 0 < c < 0x87
        for x, y, cf, ci in spec['nodes']:
            self.grid[y, x] = ci
            self.occ[y, x] = self.walk[y, x] = True
        for x, y, ci, cf in spec['fixed']:
            self.grid[y, x] = ci
            self.occ[y, x] = True
            self.walk[y, x] = wk(ci) or wk(cf)
            if self.walk[y, x] and not (0x56 <= ci < 0x87 or 0x56 <= cf < 0x87):
                self.corners.add((x, y))
        for s in spec['segs']:
            if s['kind'] == 'exit':
                bx, by = s['b']
                self.grid[by, bx] = s['bcode']
                self.occ[by, bx] = self.walk[by, bx] = True
        rng = np.random.default_rng(seed)
        # own cost field: smooth noise so routes wander
        n = rng.random((64 + 8, 32 + 8))
        k = np.ones((5, 5)) / 25
        from scipy.signal import convolve2d
        self.noise = convolve2d(n, k, mode='valid')[:64, :32] * 6.0
        self.paths = {}
        self.strict = True
        self.plain = False
        self.avoid = {}
        self.apen = (15.0, 6.0)

    def nb(self, c):
        x, y = c
        for d in STEP.values():
            n = (x + d[0], y + d[1])
            if 0 <= n[0] < 32 and 0 <= n[1] < 64 and n[1] // 32 == y // 32:
                yield n

    def free(self, c, allow):
        """c may hold a new path cell: unused, and not beside a corner-like cell."""
        x, y = c
        if not (0 <= x < 32 and 0 <= y < 64) or self.occ[y, x]:
            return False
        if not self.strict:
            return True
        return not any(n in self.corners and n not in allow for n in self.nb(c))

    def corner_ok(self, c, keep):
        """c turns: its only walkable neighbours may be the two it connects."""
        if not self.strict:
            return True
        return not any(self.walk[n[1], n[0]] and n not in keep for n in self.nb(c))

    def route(self, P, dout, Q, din, sub, way=None):
        """A* cells from P (leaving dout) to Q (arriving din); optional detour cell `way`."""
        s = (P[0] + STEP[dout][0], P[1] + STEP[dout][1])
        e = (Q[0] - STEP[din][0], Q[1] - STEP[din][1])
        if s == Q:
            return [] if dout == din else None
        x0, x1, y0, y1 = window(sub)
        off = 32 if P[1] >= 32 else 0

        def inwin(c):
            return x0 <= c[0] < x1 and y0 + off <= c[1] < y1 + off
        if not inwin(s) or not inwin(e):
            return None
        if not self.free(s, {P} | ({Q} if s == e else set())):
            return None
        if s == e:
            if dout == din or self.corner_ok(s, {P, Q}):
                return [s]
            return None
        start = (s, dout, 1 if way is None or s == way else 0)
        openq = [(0, 0, start, None)]
        came = {}
        best = {start: 0}
        cnt = 0
        while openq:
            f, g, st, par = heapq.heappop(openq)
            if st in came:
                continue
            came[st] = par
            c, d, ph = st
            if c == e and ph and (d == din or self.corner_ok(c, {(c[0] - STEP[d][0], c[1] - STEP[d][1]), Q})):
                out = []
                while st:
                    out.append(st[0])
                    st = came[st]
                return out[::-1]
            cnt += 1
            if cnt > 40000:
                return None
            for nd in STEP:
                if nd == REV[d]:
                    continue
                n = (c[0] + STEP[nd][0], c[1] + STEP[nd][1])
                if not inwin(n) or n == P or n == Q:
                    continue
                if not self.free(n, {c} | ({Q} if n == e else set())):
                    continue
                if nd != d and not self.corner_ok(c, {(c[0] - STEP[d][0], c[1] - STEP[d][1]), n}):
                    continue
                nph = 1 if (ph or n == way) else 0
                if self.plain:
                    ng = g + 1 + (0.2 if nd != d else 0)
                else:
                    ng = g + 1 + (1.5 if nd != d else 0) + self.noise[n[1], n[0]] + self.avoid.get(n, 0)
                if not self.strict and not self.plain:
                    ng += 2.5 * sum(1 for m in self.nb(n) if self.walk[m[1], m[0]] and m != c and m != Q)
                key = (n, nd, nph)
                if ng < best.get(key, 1e9):
                    best[key] = ng
                    hx = abs(n[0] - e[0]) + abs(n[1] - e[1])
                    if not nph and way:
                        hx = abs(n[0] - way[0]) + abs(n[1] - way[1]) + abs(way[0] - e[0]) + abs(way[1] - e[1])
                    heapq.heappush(openq, (ng + hx, ng, key, st))
        return None

    def ok_shape(self, cells, P, Q):
        """No corner of the route touches a non-consecutive cell of the same route."""
        pts = [P] + cells + [Q]
        idx = {c: i for i, c in enumerate(pts)}
        for i in range(1, len(pts) - 1):
            a, b, c = pts[i - 1], pts[i], pts[i + 1]
            if (b[0] - a[0], b[1] - a[1]) == (c[0] - b[0], c[1] - b[1]):
                continue
            for d in STEP.values():
                k = idx.get((b[0] + d[0], b[1] + d[1]))
                if k is not None and abs(k - i) > 1:
                    return False
        return True

    def waypoints(self, P, Q, sub, salt):
        """Detour cells to try, own rule: off the P-Q midpoint, perpendicular, both sides."""
        mx, my = (P[0] + Q[0]) / 2, (P[1] + Q[1]) / 2
        dx, dy = Q[0] - P[0], Q[1] - P[1]
        dist = abs(dx) + abs(dy)
        if dist < 3:
            return [None]
        px, py = (-dy, dx) if dist else (1, 0)
        nrm = max(1e-6, (px * px + py * py) ** 0.5)
        px, py = px / nrm, py / nrm
        r = random.Random(str(salt))
        side = 1 if r.random() < 0.5 else -1
        out = []
        for k in (4, 3, 5, 2, 6):
            for sg in (side, -side):
                out.append((int(round(mx + px * k * sg)), int(round(my + py * k * sg))))
        return out + [None]

    def place(self, cells, P, Q, prev_dir):
        pts = [P] + cells + [Q]
        for i in range(1, len(pts) - 1):
            a, b, c = pts[i - 1], pts[i], pts[i + 1]
            d1 = {(0, -1): 0, (0, 1): 2, (-1, 0): 4, (1, 0): 6}[(b[0] - a[0], b[1] - a[1])]
            d2 = {(0, -1): 0, (0, 1): 2, (-1, 0): 4, (1, 0): 6}[(c[0] - b[0], c[1] - b[1])]
            self.grid[b[1], b[0]] = code_for(d1, d2)
            self.occ[b[1], b[0]] = self.walk[b[1], b[0]] = True
            if d1 != d2:
                self.corners.add(b)

    def unplace(self, cells):
        for x, y in cells:
            self.grid[y, x] = 0
            self.occ[y, x] = self.walk[y, x] = False
            self.corners.discard((x, y))

    def plan(self):
        segs = self.spec['segs']
        order = sorted(range(len(segs)), key=lambda i: segs[i]['len'])
        fails = order
        for attempt, strict in enumerate([True] + [False] * 8):
            self.strict = strict
            left = []
            for i in fails:
                pieces = self.route_seg(i, segs[i], attempt)
                if pieces is None:
                    left.append(i)
                else:
                    self.paths[i] = pieces
            fails = left
            if not fails:
                break
            if 1 <= attempt < 7:
                # rip up the neighbour that crowds each failed segment most, route it after
                for i in list(fails):
                    a, b = segs[i]['a'], segs[i]['b']
                    if a == b:
                        continue
                    x0, x1 = min(a[0], b[0]) - 2, max(a[0], b[0]) + 2
                    y0, y1 = min(a[1], b[1]) - 2, max(a[1], b[1]) + 2
                    score = {k: sum(1 for p in self.paths[k] for c in p if x0 <= c[0] <= x1 and y0 <= c[1] <= y1)
                             for k in self.paths}
                    score = {k: v for k, v in score.items() if v}
                    if score:
                        k = max(score, key=score.get)
                        self.unplace([c for p in self.paths.pop(k) for c in p])
                        fails.append(k)
        self.strict = True
        self.improve()
        # last resort for anything still unrouted: free its box, route it plain, re-route the rest
        for i in [i for i in fails if segs[i]['a'] != segs[i]['b']]:
            a, b = segs[i]['a'], segs[i]['b']
            x0, x1 = min(a[0], b[0]) - 2, max(a[0], b[0]) + 2
            y0, y1 = min(a[1], b[1]) - 2, max(a[1], b[1]) + 2
            crowd = [k for k in self.paths if any(x0 <= c[0] <= x1 and y0 <= c[1] <= y1 for q in self.paths[k] for c in q)]
            saved = {k: self.paths[k] for k in crowd}
            snap = (self.grid.copy(), self.occ.copy(), self.walk.copy(), set(self.corners))
            for k in crowd:
                self.unplace([c for q in self.paths.pop(k) for c in q])
            self.strict, self.plain, self.avoid = False, True, {}
            got = self.route_seg(i, segs[i], 50)
            ok = got is not None
            if ok:
                self.paths[i] = got
                for k in sorted(crowd, key=lambda k: segs[k]['len']):
                    self.plain = False
                    r = self.route_seg(k, segs[k], 51)
                    if r is None:
                        self.plain, self.avoid = True, {}
                        r = self.route_seg(k, segs[k], 52)
                    if r is None:
                        ok = False
                        break
                    self.paths[k] = r
            if ok:
                fails.remove(i)
            else:
                self.grid, self.occ, self.walk, self.corners = snap[0], snap[1], snap[2], snap[3]
                self.paths.pop(i, None)
                for k in crowd:
                    self.paths[k] = saved[k]
        self.strict, self.plain = True, False
        bad = [i for i in self.paths if not self.check(segs[i])]
        return fails + bad

    def overlap(self, i, pieces):
        """Cells (inner, not first/last) a route shares with or touches on its direct route."""
        s = self.spec['segs'][i]
        pts = [(tuple(s['a']), None, s['j'])] + [((v[0], v[1]), v[2], v[3]) for v in s['via']] + [(tuple(s['b']), s['arr'], None)]
        n = 0
        for k, cells in enumerate(pieces):
            P, _, dout = pts[k]
            Q, din, _ = pts[k + 1]
            self.set_avoid(P, dout, Q, din, submap_of(*s['a']))
            n += sum(1 for c in cells[1:-1] if self.avoid.get(c, 0) >= self.apen[0])
        return n

    def improve(self):
        """Second look at routes that still run on (or beside) their direct route: re-route
        them with the relaxed rules and keep the new one if it strays further."""
        segs = self.spec['segs']
        for i in sorted(self.paths, key=lambda i: -segs[i]['len']):
            old = self.paths[i]
            ov = self.overlap(i, old)
            if not ov:
                continue
            cells = [c for q in old for c in q]
            saved = {c: (int(self.grid[c[1], c[0]]), c in self.corners) for c in cells}
            self.unplace(cells)
            del self.paths[i]
            self.strict = False
            got = None
            for att in (11, 12, 13):
                got = self.route_seg(i, segs[i], att)
                if got is None:
                    continue
                if self.overlap(i, got) < ov:
                    break
                self.unplace([c for q in got for c in q])
                got = None
            self.strict = True
            if got is not None:
                self.paths[i] = got
                continue
            for c, (v, cn) in saved.items():
                self.grid[c[1], c[0]] = v
                self.occ[c[1], c[0]] = self.walk[c[1], c[0]] = True
                if cn:
                    self.corners.add(c)
            self.paths[i] = old

    def check(self, s):
        """Walk the segment both ways with the port's rules."""
        from games.smw import ow_walk as Wk
        w = Wk.Walker(self.grid, self.tables)
        a, b = tuple(s['a']), tuple(s['b'])
        sub = 1 if a[1] >= 32 else 0
        r = w.walk(sub, (a[0], a[1] % 32), s['j'])
        want = 'exit' if s['kind'] == 'exit' else 'node'
        if r['reason'] != want or (r['end'][0], r['end'][1] + 32 * sub) != b:
            return False
        if s['kind'] == 'node' and a != b:
            r = w.walk(sub, (b[0], b[1] % 32), REV[s['arr']])
            if r['reason'] != 'node' or (r['end'][0], r['end'][1] + 32 * sub) != a:
                return False
        return True

    def codes(self, s, cells):
        """Pick layer-1 codes for the route so that the port walks it both ways."""
        from games.smw import ow_walk as Wk
        sub = 1 if s['a'][1] >= 32 else 0
        loc = lambda c: (c[0], c[1] - 32 * sub)
        fixed = {loc((v[0], v[1])): int(self.grid[v[1], v[0]]) for v in s['via']}
        A, B = loc(tuple(s['a'])), loc(tuple(s['b']))
        cl = [loc(c) for c in cells]
        ok = Wk.assign_codes(self.grid, self.tables, sub, A, s['j'], cl, B, s['kind'], fixed,
                             lambda i: self.cands, limit=1500)
        return ok

    def set_avoid(self, P, dout, Q, din, sub):
        """Our routes keep two cells off the direct route between the same two cells."""
        self.plain, self.avoid = True, {}
        direct = self.route(P, dout, Q, din, sub, None) or []
        self.plain = False
        keep = {P, Q} | set(direct[:1]) | set(direct[-1:])
        for c in direct:
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    n = (c[0] + dx, c[1] + dy)
                    if n in keep:
                        continue
                    pen = self.apen[0] if max(abs(dx), abs(dy)) <= 1 else self.apen[1]
                    self.avoid[n] = max(self.avoid.get(n, 0), pen)

    def verify_near(self, i, cells):
        segs = self.spec['segs']
        near = set()
        for k, pcs in self.paths.items():
            cs = [c for p in pcs for c in p] + [tuple(segs[k]['a']), tuple(segs[k]['b'])]
            if any(abs(c[0] - d[0]) + abs(c[1] - d[1]) <= 2 for c in cs for d in cells):
                near.add(k)
        return all(self.check(segs[k]) for k in near)

    def route_seg(self, i, s, attempt):
        pts = [(tuple(s['a']), None, s['j'])] + [((v[0], v[1]), v[2], v[3]) for v in s['via']] + [(tuple(s['b']), s['arr'], None)]
        sub = submap_of(*s['a'])
        wl = [self.waypoints(pts[k][0], pts[k + 1][0], sub, (self.seed, i, k, attempt)) for k in range(len(pts) - 1)]
        nvar = max(len(w) for w in wl)
        for var in range(nvar):
            pieces = []
            for k in range(len(pts) - 1):
                P, _, dout = pts[k]
                Q, din, _ = pts[k + 1]
                w = wl[k][min(var, len(wl[k]) - 1)]
                if w is not None and not (0 <= w[0] < 32 and 0 <= w[1] < 64 and not self.occ[w[1], w[0]]):
                    w = None
                if not self.plain:
                    self.set_avoid(P, dout, Q, din, sub)
                cells = self.route(P, dout, Q, din, sub, w)
                if cells is None or not self.ok_shape(cells, P, Q):
                    break
                self.place(cells, P, Q, dout)
                pieces.append(cells)
            else:
                allc = []
                for k, p in enumerate(pieces):
                    allc += p
                    if k < len(pieces) - 1:
                        allc.append(pts[k + 1][0])
                if self.codes(s, allc) and (self.strict or self.verify_near(i, allc)):
                    return pieces
            for p in pieces:
                self.unplace(p)
        return None

def load_spec(spec_dir):
    return json.load(open(os.path.join(spec_dir, 'ow.json')))


def ascii_grid(g, half):
    rows = []
    for y in range(32 * half, 32 * half + 32):
        rows.append('%2d ' % y + ''.join(('%02x' % v if v else '..') for v in g[y]))
    return '\n'.join(rows)


if __name__ == '__main__':
    import sys
    from games.smw import assetfile as A, ow_walk as Wk
    sp = load_spec(os.path.join(os.path.dirname(__file__), 'spec'))
    kept = dict(A.read(os.path.join(os.path.dirname(__file__), 'spec', 'tables.dat')))
    p = Planner(sp, Wk.tables_from_items(kept))
    f = p.plan()
    print('failed segments:', f)
    print(ascii_grid(p.grid, int(sys.argv[1]) if len(sys.argv) > 1 else 0))


def forced_cells(p):
    """Route cells the grid allows no way around: with the cell blocked, no walkable route
    (any shape) exists between the same two kept cells with the other routes in place."""
    segs = p.spec['segs']
    out = set()
    p.strict, p.plain = False, True
    for i, pieces in p.paths.items():
        s = segs[i]
        pts = [(tuple(s['a']), None, s['j'])] + [((v[0], v[1]), v[2], v[3]) for v in s['via']] + [(tuple(s['b']), s['arr'], None)]
        sub = submap_of(*s['a'])
        for k, cells in enumerate(pieces):
            P, _, dout = pts[k]
            Q, din, _ = pts[k + 1]
            saved = [int(p.grid[c[1], c[0]]) for c in cells]
            corners = [c in p.corners for c in cells]
            p.unplace(cells)
            for c in cells:
                p.occ[c[1], c[0]] = True
                if p.route(P, dout, Q, din, sub, None) is None:
                    out.add(c)
                p.occ[c[1], c[0]] = False
            for c, v, cn in zip(cells, saved, corners):
                p.grid[c[1], c[0]] = v
                p.occ[c[1], c[0]] = p.walk[c[1], c[0]] = True
                if cn:
                    p.corners.add(c)
    p.strict, p.plain = True, False
    return out


def forced_cells_exact(p, skip=(), radius=0):
    """Like forced_cells, but a way round must also walk (codes) and keep the other routes walking.
    radius=1: the way round must also keep off the cell's 8 neighbours (a cell 'pinned' by the grid)."""
    segs = p.spec['segs']
    out = set()
    for i in list(p.paths):
        pieces = p.paths[i]
        cells = [c for q in pieces for c in q]
        todo = [c for c in cells if c not in skip]
        if not todo:
            continue
        saved = {c: (int(p.grid[c[1], c[0]]), c in p.corners) for c in cells}

        def restore():
            for c, (v, cn) in saved.items():
                p.grid[c[1], c[0]] = v
                p.occ[c[1], c[0]] = p.walk[c[1], c[0]] = True
                if cn:
                    p.corners.add(c)
        ends = set(skip)
        for c in todo:
            p.unplace(cells)
            del p.paths[i]
            blk = [(c[0] + dx, c[1] + dy) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1)]
            blk = [b for b in blk if 0 <= b[0] < 32 and 0 <= b[1] < 64 and not p.occ[b[1], b[0]] and b not in ends]
            for b in blk:
                p.occ[b[1], b[0]] = True
            p.strict = False
            got = p.route_seg(i, segs[i], 99)
            p.strict = True
            if got is None:
                out.add(c)
            else:
                p.unplace([x for q in got for x in q])
            for b in blk:
                p.occ[b[1], b[0]] = False
            restore()
            p.paths[i] = pieces
    return out
