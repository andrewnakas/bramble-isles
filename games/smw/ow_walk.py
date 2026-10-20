"""Overworld walk simulator: the port's path-following rules (OwProcess03/04 in
smw_04.c) on a layer-1 grid, without speeds (the player jumps to each target).

Used to trace paths (node -> node), to pick layer-1 path codes for our own routes
(every code moves the player its own way across the tile) and to check them.
Movement tables are read from the decomp source (code, not assets).
"""
import os
import re

SRC = [r'D:/n64work/smw/pristine/src/smw_04.c', r'D:/n64work/smw/build/src/smw_04.c']
STEP = {0: (0, -1), 2: (0, 1), 4: (-1, 0), 6: (1, 0)}       # up, down, left, right
REV = {0: 2, 2: 0, 4: 6, 6: 4}
DIRN = {(0, -1): 0, (0, 1): 2, (-1, 0): 4, (1, 0): 6}
_T = None


def T():
    global _T
    if _T is None:
        for p in SRC:
            if os.path.exists(p):
                s = open(p, encoding='utf8', errors='replace').read()
                break
        else:
            raise FileNotFoundError('smw_04.c not found')
        _T = {}
        for n in ['kOwTileDistanceMovedAcross_049EA7', 'kOwTilePathDirection_049F49', 'kOwTilePose_049FEB',
                  'kOverworldProcess04_PlayerIsMoving_DATA_049430', 'kOverworldProcess04_PlayerIsMoving_DATA_04944E']:
            m = re.search(n + r'\[\d+\] = \{([^}]*)\}', s)
            _T[n] = [int(x, 0) for x in m.group(1).replace(' ', '').replace('\n', '').split(',') if x]
    return _T


def sx(b):
    return b - 256 if b >= 128 else b


def sx16(w):
    return w - 65536 if w >= 32768 else w


def walking_codes(exits):
    """Path codes with a walking pose that are not submap-exit tiles."""
    pose = T()['kOwTilePose_049FEB']
    return [c for c in range(1, len(pose) + 1) if pose[c - 1] in (0, 4) and c not in exits]


class Walker:
    def __init__(self, grid, tb):
        self.g = grid
        self.frm, self.xy, self.adir = tb['from'], tb['xy'], tb['dir']
        self.alpha, self.exits = tb['alpha'], tb['exits']

    def tile(self, sub, cx, cy):
        if not (0 <= cx < 32 and 0 <= cy < 32):
            return None
        return int(self.g[cy + 32 * sub, cx])

    def depart(self, sub, node, j):
        """OwProcess03: standing on node, press j -> state or None."""
        cx, cy = node
        px, py = cx * 16 + 8, cy * 16 + 8
        v = self.tile(sub, cx + STEP[j][0], cy + STEP[j][1])
        if not v or v > 0x86:
            return None
        if v in self.frm:
            k = self.frm.index(v)
            a, b = sx16(self.xy[2 * k]), sx16(self.xy[2 * k + 1])
            ax = self.adir[k] >> 1
        else:
            a, b = (8 if j & 2 else -8), 0
            ax = 1 if j < 4 else 0
        tgt = [0, 0]
        tgt[ax] = (px, py)[ax] + a
        tgt[ax ^ 1] = (px, py)[ax ^ 1] + b
        return {'pos': tuple(tgt), 'dir': j, 'grid': (cx, cy), 'standing': v, 'timer': 0, 'sub': sub}

    def step(self, st):
        """Arrived at st['pos']: probe the next cell and set the next target (OwProcess04).
        -> new state (with 'cell' = cell entered), or a final dict with 'reason'."""
        t = T()
        px, py = st['pos']
        if st['timer']:
            ok = (px & 15) == 8 and (py & 15) == 8
            return {'reason': 'node' if ok else 'offcentre', 'end': (px >> 4, py >> 4), 'pos': (px, py)}
        copy_standing = st['standing']
        direction = st['dir']
        grid = st['grid']
        r8, v11, rev = 8, direction, direction ^ 2
        while True:
            r0, r2 = grid[0] + STEP[v11][0], grid[1] + STEP[v11][1]
            v15 = self.tile(st['sub'], r0, r2)
            if v15 and v15 < 0x87:
                break
            while True:
                r8 -= 2
                if r8 != rev:
                    break
            if r8 < 0:
                return {'reason': 'stuck', 'pos': (px, py)}
            v11 = r8
        grid = (r0, r2)
        v19 = v11
        if v15 in self.exits:
            return {'reason': 'exit', 'end': grid, 'pos': (px, py), 'cell': grid}
        timer = 0
        if v15 < 0x56:
            if v15 > len(t['kOwTilePathDirection_049F49']):
                return {'reason': 'badcode', 'pos': (px, py)}
            r4 = t['kOwTilePathDirection_049F49'][v15 - 1]
            v24 = t['kOwTileDistanceMovedAcross_049EA7'][v15 - 1]
            v25 = 2 * (v15 - 1)
        else:
            timer = 1
            r4 = 1
            if copy_standing in self.frm:
                v24 = self.alpha[self.frm.index(copy_standing)]
            else:
                v24 = 0x800 if v19 < 4 else 8
            v25 = 0
        r0w = v24
        tab, tab2 = t['kOverworldProcess04_PlayerIsMoving_DATA_049430'], t['kOverworldProcess04_PlayerIsMoving_DATA_04944E']
        v29 = None
        for v28 in range(14, -1, -1):
            if (v25 & 0xff) == (tab[v28] & 0xff):
                if v19 != tab[v28] >> 8:
                    v29 = tab2[v28]
                break
        if v29 is None:
            v29 = 1 if v19 & 2 else 0
        if r4 & (0xff00 if v29 else 0xff):
            r0w = ((-(r0w & 0xff)) & 0xff) | (((-(r0w >> 8)) & 0xff) << 8)
        lo, hi = sx(r0w & 0xff), sx(r0w >> 8)
        tgt = ((px + lo) & ~3, (py + hi) & ~3)
        if tgt[0] & 15:
            if tgt[1] & 15 == 0:
                v19 = 0 if r0w & 0x8000 else 2
        else:
            v19 = 4 if r0w & 0x80 else 6
        return {'pos': tgt, 'dir': v19, 'grid': grid, 'standing': v15, 'timer': timer, 'sub': st['sub'], 'cell': grid}

    def walk(self, sub, node, j, limit=400):
        """Start standing at node (cx, cy), press direction j. -> dict(cells, end, pos, reason)."""
        st = self.depart(sub, node, j)
        if st is None:
            return {'cells': [], 'end': None, 'reason': 'blocked'}
        cells = []
        for _ in range(limit):
            st = self.step(st)
            if 'cell' in st:
                cells.append(st['cell'])
            if 'reason' in st:
                st['cells'] = cells
                return st
        return {'cells': cells, 'end': None, 'reason': 'limit'}


def vec(code, v19):
    """Move vector of a path code for a cell entered with probe direction v19."""
    t = T()
    r4 = t['kOwTilePathDirection_049F49'][code - 1]
    r0w = t['kOwTileDistanceMovedAcross_049EA7'][code - 1]
    v25 = 2 * (code - 1)
    tab, tab2 = t['kOverworldProcess04_PlayerIsMoving_DATA_049430'], t['kOverworldProcess04_PlayerIsMoving_DATA_04944E']
    v29 = None
    for v28 in range(14, -1, -1):
        if (v25 & 0xff) == (tab[v28] & 0xff):
            if v19 != tab[v28] >> 8:
                v29 = tab2[v28]
            break
    if v29 is None:
        v29 = 1 if v19 & 2 else 0
    if r4 & (0xff00 if v29 else 0xff):
        r0w = ((-(r0w & 0xff)) & 0xff) | (((-(r0w >> 8)) & 0xff) << 8)
    return sx(r0w & 0xff), sx(r0w >> 8)


def symmetric(code, d_in, d_out):
    """Walking the cell backwards retraces it: reverse vector = -forward vector."""
    f = vec(code, d_in)
    r = vec(code, REV[d_out])
    return r == (-f[0], -f[1])


def assign_codes(grid, tb, sub, A, j, cells, B, kind, fixed, cands, limit=20000):
    """Choose a code for every cell of a route A -> cells -> B (B a node or an exit tile)
    so that the port walks it both ways. `fixed` = {cell: code} kept as is; `cands(i)` ->
    candidate codes for cells[i] (preferred first). Writes the codes into grid. -> bool."""
    w = Walker(grid, tb)
    for c in cells:
        if c not in fixed:
            grid[c[1] + 32 * sub, c[0]] = 0x04            # walkable placeholder
    dead = set()
    revfail = [False]
    budget = [limit]
    rev_ok = kind != 'node' or A == B

    def put(c, v):
        grid[c[1] + 32 * sub, c[0]] = v

    def finish(st):
        st = w.step(st)
        if kind == 'exit':
            return st.get('reason') == 'exit' and st['end'] == B
        if 'reason' in st or st['cell'] != B:
            return False
        st = w.step(st)
        return st.get('reason') == 'node' and st['end'] == B

    def back():
        if rev_ok:
            return True
        r = w.walk(sub, B, REV[arrive])
        return r['reason'] == 'node' and r['end'] == A

    def dfs(i, st):
        budget[0] -= 1
        if budget[0] < 0:
            return False
        if i == len(cells):
            if not finish(st):
                return False
            if back():
                return True
            revfail[0] = True
            return False
        c = cells[i]
        nxt = pts[i + 2]
        ideal = (c[0] * 16 + 8 + (nxt[0] - c[0]) * 8, c[1] * 16 + 8 + (nxt[1] - c[1]) * 8)
        prv = pts[i]
        d_in = DIRN[(c[0] - prv[0], c[1] - prv[1])]
        d_out = DIRN[(nxt[0] - c[0], nxt[1] - c[1])]
        opts = [fixed[c]] if c in fixed else [v for v in cands(i) if symmetric(v, d_in, d_out)]
        tried = []
        for v in opts:
            put(c, v)
            s1 = st
            if i == 0:
                s1 = w.depart(sub, A, j)
                if s1 is None:
                    continue
            s2 = w.step(s1)
            if 'reason' in s2 or s2['cell'] != c:
                continue
            dev = abs(s2['pos'][0] - ideal[0]) + abs(s2['pos'][1] - ideal[1])
            tried.append((dev, opts.index(v), v, s2))
        tried.sort(key=lambda t: (t[0], t[1]))
        for dev, _, v, s2 in tried:
            put(c, v)
            key = (i, s2['pos'][0] - c[0] * 16, s2['pos'][1] - c[1] * 16, s2['dir'], v if i == len(cells) - 1 else 0)
            if key in dead:
                continue
            if dfs(i + 1, s2):
                return True
            dead.add(key)
        if c not in fixed:
            put(c, 0x04)
        return False
    pts = [A] + list(cells) + [B]
    arrive = {(0, -1): 0, (0, 1): 2, (-1, 0): 4, (1, 0): 6}[(pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])]
    if not cells:
        return True
    c0 = cells[0]
    if c0 in fixed:
        return dfs(0, None)
    nxt = pts[2]
    d_out = DIRN[(nxt[0] - c0[0], nxt[1] - c0[1])]
    ideal = (c0[0] * 16 + 8 + (nxt[0] - c0[0]) * 8, c0[1] * 16 + 8 + (nxt[1] - c0[1]) * 8)
    first = []
    for v in cands(0):
        if not symmetric(v, j, d_out):
            continue
        put(c0, v)
        s1 = w.depart(sub, A, j)
        s2 = w.step(s1) if s1 else {'reason': 'x'}
        if 'reason' in s2:
            continue
        first.append((abs(s2['pos'][0] - ideal[0]) + abs(s2['pos'][1] - ideal[1]), v))
    first.sort()
    total = [limit * 4]
    for _, v in first:
        fixed[c0] = v
        dead.clear()
        budget[0] = min(limit, total[0])
        ok = dfs(0, None)
        total[0] -= min(limit, total[0]) - budget[0]
        if ok:
            del fixed[c0]
            return True
        if total[0] <= 0:
            break
    del fixed[c0]
    put(c0, 0x04)
    return False


def tables_from_items(items):
    import numpy as np
    u = lambda n: [int(x) for x in np.frombuffer(items[n], '<u2')]
    return {'from': list(items['kOwUnknownTableA_From_04A03C']), 'xy': u('kOwUnknownTableA_XY_04A084'),
            'dir': list(items['kOwUnknownTableA_Direction_04A0E4']), 'alpha': u('kOwUnknownTableA_Alpha_04A054'),
            'exits': list(items['kOwExitLevelTiles_049426'])}
