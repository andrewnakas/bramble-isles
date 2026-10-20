"""CLEAN ROOM. New level layouts for every level slot (module `levels` of generate.py).

Input: games/smw/spec/levels.json (structure + anchors only: header settings, screen exits and
their trigger kind, how a level ends, the enemy roster, boss/special sprite anchors) and the kept
entrance tables (spawn positions). Output: kLevelData_Layer1, the object-based (non-background)
layer-2 entries of kLevelData_Layer2, kLvlSprBlob + kLoadLevel_SpriteDataPtrs + kLmSpritePtrBankByte,
kEntranceData_Layer1, kChoclateIsland2_Layer1, kRollCallData_Layer1.

Every layout is designed here by a seeded generator: terrain profiles, pits, floating ledges,
block rows, pipes, stairs, coins and enemy placements are new. Fairness rules (SMW physics, see
JUMP_UP / GAP_MAX) keep every course passable from its spawn to its end trigger; check_course()
re-verifies each generated course on its own block grid.
"""
import json
import os
import random
import struct

import numpy as np

from games.smw import assetfile as A, lvlfmt as F

SPEC = os.path.join(os.path.dirname(__file__), 'spec')
SEED = 0xB7A3B1E
# per-layout seed bumps picked after the originality gate flagged a chance resemblance
# (games/smw/level_reroll.py writes this file; the generator itself never reads retail data)
_BUMPS_PATH = os.path.join(os.path.dirname(__file__), 'level_seeds.json')
BUMPS = json.load(open(_BUMPS_PATH)) if os.path.exists(_BUMPS_PATH) else {}


def bump(key):
    return BUMPS.get(key, 0) * 104729

# ---------------------------------------------------------------- facts from the port's code
# player entrance position tables (smw_05.c kLoadLevel_DATA_05D730/40/50/58)
ENT_Y = [0x000, 0x030, 0x060, 0x080, 0x0a0, 0x0b0, 0x0c0, 0x0e0, 0x110, 0x130, 0x150, 0x160, 0x170, 0x190, 0x100, 0x100]
ENT_X = [0x010, 0x080, 0x000, 0x0e0, 0x110, 0x170, 0x100, 0x1e0]
# extended 1-tile objects 0x10..0x42 -> block (smw_0d.c kExtObjXX_Generic1TileObject_Tiles, page 1 from index 19)
_EXT1 = [0x1f, 0x22, 0x24, 0x42, 0x43, 0x27, 0x29, 0x25, 0x6e, 0x6f, 0x70, 0x71, 0x72, 0x45, 0x46, 0x47, 0x48, 0x36,
         0x37, 0x11, 0x12, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x29, 0x1d, 0x1f, 0x20, 0x21, 0x22,
         0x23, 0x25, 0x26, 0x27, 0x28, 0x2a, 0xde, 0xe0, 0xe2, 0xe4, 0xec, 0xed, 0x2c, 0x25, 0x2d]
EXT_FOR_BLOCK = {}
for _i, _t in enumerate(_EXT1):
    EXT_FOR_BLOCK.setdefault(_t | (0x100 if _i >= 19 else 0), 0x10 + _i)

# blocks the objects below write (blocks.py classes: ledge, decor fill, cement, coin, ...)
EMPTY, LEDGE, FILL, CEMENT, USED, COIN, TURN, QCOIN, NOTE, THROW, MUNCHER = 0x25, 0x100, 0x03F, 0x130, 0x132, 0x02B, 0x11E, 0x124, 0x113, 0x12E, 0x12F
EDGE_L, EDGE_R = 0x14B, 0x14C
Q_POWER, Q_FEATHER, Q_STAR, Q_MULTI, Q_YOSHI = 0x11F, 0x120, 0x121, 0x123, 0x126
SOLID = {CEMENT, USED, TURN, QCOIN, NOTE, THROW, MUNCHER, EDGE_L, EDGE_R, 0x145, 0x148, Q_POWER, Q_FEATHER, Q_STAR,
         Q_MULTI, Q_YOSHI} | set(range(0x133, 0x13B))
STANDABLE = SOLID | {LEDGE}

# SMW movement limits used by the generator (tiles): a walking jump clears 4 up / 4 across,
# a running jump 5 across; the generator stays inside these with margin.
JUMP_UP = 3
GAP_MAX = 4
H = 27                      # rows in a horizontal level

# sprite roles (from the port's sprite routine names)
WALKERS = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x0D, 0x0F, 0x11, 0x13, 0x1D, 0x27, 0x30, 0x31, 0x32,
           0x46, 0x4E, 0x51, 0x6E, 0x6F, 0x70, 0x73, 0x86, 0x91, 0x92, 0x93, 0x94, 0x95, 0x97, 0x98, 0x99, 0x9A,
           0xA2, 0xAB, 0xBD, 0xBF}
FLIERS = {0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x10, 0x1C, 0x1E, 0x3F, 0x71, 0x72, 0x9F, 0xBE, 0x26}
PIPE_DWELLERS = {0x1A, 0x4F}
SWIMMERS = {0x15, 0x16, 0x17, 0x18, 0x3D, 0x44, 0x47, 0xAA, 0xC2, 0xC3}
HELPERS = {0x2F, 0x3E, 0x74, 0x75, 0x76, 0x77, 0x78, 0x2C, 0x35}
PLATFORMS = {0x5F, 0xA3, 0xC4, 0xBA, 0x55, 0x57}
GENERATORS = set(range(0xC9, 0xDE))


def ent_tables(kept):
    return [kept['kLevelInfo_05F%d00' % i] for i in (0, 2, 4, 6)]


def spawn_of(slot, kept):
    """Main entrance of a level slot: (col, row, screen, action, midway_screen) from the kept tables."""
    f0, f2, f4, f6 = ent_tables(kept)
    y = ENT_Y[f0[slot] & 0xF]
    x = ENT_X[f2[slot] & 7]
    return {'col': (x & 0xFF) >> 4, 'xhi': x >> 8, 'row': y >> 4, 'screen': f6[slot] & 0x1F,
            'action': (f2[slot] >> 3) & 7, 'midway': f4[slot] >> 4, 'ypix': y}


# ---------------------------------------------------------------- level builder
class Level:
    def __init__(self, cols, rows=H, vertical=False, tileset=0):
        self.cols, self.rows, self.vertical, self.tileset = cols, rows, vertical, tileset
        self.g = np.full((rows, cols), EMPTY, np.int32)       # expected Map16 grid
        self.objs, self.sprs = [], []
        self.notes = []

    # --- object helpers (col, row in level coordinates)
    def _o(self, num, c, r, size=0, ext=None):
        if self.vertical:
            o = F.Obj(num, r // 16, r % 16, (c & 15) | ((c >> 4) << 4), size, ext)
        else:
            o = F.Obj(num, c // 16, c % 16, r, size, ext)
        self.objs.append(o)

    def _set(self, r0, r1, c0, c1, v):
        r0, c0 = max(r0, 0), max(c0, 0)
        if r1 >= r0 and c1 >= c0:
            self.g[r0:r1 + 1, c0:min(c1, self.cols - 1) + 1] = v

    def _split(self, c0, c1):
        """Vertical levels: objects must not run across the left/right half (they wrap a screen down)."""
        if self.vertical and c0 < 16 <= c1:
            return [(c0, 15), (16, c1)]
        return [(c0, c1)]

    def rect(self, num, block, c, r, w, h):
        """Rectangle objects 0x01-0x0E (one block, up to 16x16)."""
        if len(self._split(c, c + w - 1)) > 1:
            for a, b in self._split(c, c + w - 1):
                self.rect(num, block, a, r, b - a + 1, h)
            return
        for cc in range(c, c + w, 16):
            ww = min(16, c + w - cc)
            for rr in range(r, r + h, 16):
                hh = min(16, r + h - rr)
                self._o(num, cc, rr, ((hh - 1) << 4) | (ww - 1))
                self._set(rr, rr + hh - 1, cc, cc + ww - 1, block)

    def cement(self, c, r, w, h):
        self.rect(0x0D, CEMENT, c, r, w, h)

    def coins(self, c, r, w=1, h=1):
        self.rect(0x05, COIN, c, r, w, h)

    def block(self, c, r, b):
        if b == TURN:
            self.rect(0x09, TURN, c, r, 1, 1)
        elif b == QCOIN:
            self.rect(0x0A, QCOIN, c, r, 1, 1)
        elif b == NOTE:
            self.rect(0x08, NOTE, c, r, 1, 1)
        elif b == USED:
            self.rect(0x0E, USED, c, r, 1, 1)
        elif b == THROW:
            self.rect(0x0B, THROW, c, r, 1, 1)
        else:
            self._o(0, c, r, ext=EXT_FOR_BLOCK[b])
            self._set(r, r, c, c, b)

    def ground(self, c0, c1, top, bottom=None, left_edge=True, right_edge=True):
        """Ground ledge: walk-on top row + fill down to `bottom`, solid edge columns."""
        bottom = self.rows - 1 if bottom is None else bottom
        if len(self._split(c0, c1)) > 1:
            (a, b), (c, d) = self._split(c0, c1)
            self.ground(a, b, top, bottom, left_edge, False)
            self.ground(c, d, top, bottom, False, right_edge)
            return
        fill = min(15, bottom - top)
        for cc in range(c0, c1 + 1, 16):
            w = min(16, c1 + 1 - cc)
            self._o(0x14, cc, top, (fill << 4) | (w - 1))
            self._set(top, top, cc, cc + w - 1, LEDGE)
            self._set(top + 1, top + fill, cc, cc + w - 1, FILL)
        if top + fill < bottom:                        # deeper than one object: walk-through fill below
            self.rect(0x06, FILL, c0, top + fill + 1, c1 - c0 + 1, bottom - top - fill)
        for c, typ, cls in ((c0, 3, 0x145), (c1, 5, 0x148)):
            if (c == c0 and not left_edge) or (c == c1 and not right_edge):
                continue
            rr, t = top, typ
            while rr <= bottom:
                n = min(15, bottom - rr)
                self._o(0x13, c, rr, (n << 4) | t)
                self._set(rr, rr, c, c, cls if t == typ else (EDGE_L if typ == 3 else EDGE_R))
                self._set(rr + 1, rr + n, c, c, EDGE_L if typ == 3 else EDGE_R)
                rr += n + 1
                t = 4 if typ == 3 else 6

    def platform(self, c0, c1, r):
        """Floating ledge (top only, one row)."""
        if len(self._split(c0, c1)) > 1:
            for a, b in self._split(c0, c1):
                self.platform(a, b, r)
            return
        for cc in range(c0, c1 + 1, 16):
            w = min(16, c1 + 1 - cc)
            self._o(0x14, cc, r, w - 1)
            self._set(r, r, cc, cc + w - 1, LEDGE)

    def pipe(self, c, top, bottom, enterable=False):
        """Vertical pipe, opening at `top`, shaft down to `bottom` (2 columns)."""
        h = bottom - top
        r = top
        typ = 1 if enterable else 0
        while True:
            n = min(15, bottom - r)
            self._o(0x0F, c, r, (n << 4) | typ)
            if typ in (0, 1):
                self._set(r, r, c, c + 1, 0x137 if typ == 1 else 0x133)
                self.g[r, c + 1] = 0x138 if typ == 1 else 0x134
                self._set(r + 1, r + n, c, c, 0x135)
                self._set(r + 1, r + n, c + 1, c + 1, 0x136)
            r += n + 1
            if r > bottom:
                break
            typ = 5                                  # shaft only (type 5) for the remainder
            self._set(r, min(bottom, r + 15), c, c, 0x168)
            self._set(r, min(bottom, r + 15), c + 1, c + 1, 0x169)
        return h

    def door(self, c, r):
        """Door: top block at r, bottom at r + 1."""
        self._o(0, c, r, ext=0x47)
        self.g[r, c], self.g[r + 1, c] = 0x1F, 0x20

    def midway(self, c, r):
        self._o(0, c, r, ext=0x46)
        self.g[r, c - 1], self.g[r, c] = 0x35, 0x38

    def goal(self, c, floor):
        """Goal posts (3 columns from c, standing on `floor`) and the moving tape sprite."""
        h = 8
        self._o(0x15, c, floor - h - 1, (h << 4) | 1)
        self.sprite(0x7B, c + 1, floor - 2)

    def dragon_coin(self, c, r):
        self._o(0, c, r, ext=0x41)
        self.g[r, c], self.g[r + 1, c] = 0x2D, 0x2E

    def screen_exit(self, screen, dest, flags=0):
        self.objs.append(F.Obj(0, screen, 0, 0, ext=0, extra=dest, flags=flags))

    def sprite(self, num, c, r, extra=0):
        if self.vertical:
            self.sprs.append(F.Spr(num, r // 16, r % 16, c & 31, extra))
        else:
            self.sprs.append(F.Spr(num, c // 16, c % 16, r, extra))

    def emit(self, hdr, spr_hdr):
        return F.emit_objects(hdr, self.objs), F.emit_sprites(spr_hdr, self.sprs)


# ---------------------------------------------------------------- course generator (horizontal)
def _floor_of(sp):
    """Ground row under a standing spawn."""
    return max(6, min(25, sp['row'] + 2))


def gen_course(e, slot, kept, rng, mode='course', spawn=None):
    screens = e['screens']
    cols = 16 * screens
    L = Level(cols, H, False, e['tileset'])
    sp = spawn or spawn_of(slot, kept)
    scol = sp['screen'] * 16 + sp['col']
    scol = min(cols - 4, max(1, scol))
    action = sp['action']
    water = action == 7
    F0 = _floor_of(sp)
    if action == 3:                         # rises out of a floor pipe: pipe top at the spawn floor
        F0 = min(25, F0 + 2)
    # reserved flat zones: (c0, c1, floor, why)
    zones = [(max(0, scol - 2), min(cols - 1, scol + 3), F0, 'spawn')]
    ends = set(e['ends'])
    goal_col = None
    if 'goal' in ends or (mode == 'course' and not ends and not e['exits']):
        goal_col = cols - 22 if cols >= 48 else cols - 8
    exits = list(e['exits'])
    exit_cols = {}
    for x in exits:
        s = x['screen']
        if s >= screens:
            continue
        c = s * 16 + 7
        if abs(c - scol) < 6:
            c = min(s * 16 + 13, scol + 7)
        exit_cols[s] = c
    mid_s = sp['midway']
    mid_col = None
    if mode == 'course' and 0 < mid_s < screens - 1 and (goal_col is None or mid_s * 16 + 8 < goal_col - 8):
        mid_col = mid_s * 16 + 8
    key_needed = 'keyhole' in ends
    fl = {}
    # terrain: the ground wanders between new target heights (stairs of <= JUMP_UP rows), with
    # flat runs, pits (courses) and dips; only the spawn zone sits on the anchored floor row
    rowmin, rowmax = max(9, F0 - 11), 25
    cur = F0
    target = rng.randint(rowmin, rowmax)
    c = 0
    tops = [None] * cols
    pits_ok = mode == 'course' and not water
    goal_h = None
    if goal_col is not None:
        goal_h = max(rowmin, min(25, F0 - rng.randint(3, 8) if F0 > 14 else F0 + rng.randint(3, 6)))
        zones.append((max(0, goal_col - 6), cols - 1, goal_h, 'goal'))
    while c < cols:
        z = next((z for z in zones if z[0] <= c <= z[1]), None)
        if z:
            for cc in range(c, z[1] + 1):
                tops[cc] = z[2]
            cur = z[2]
            c = z[1] + 1
            continue
        nxt = min([z[0] for z in zones if z[0] > c] + [cols])
        room = nxt - c
        if goal_h is not None and c > goal_col - 30:
            target = goal_h
        if (cur == target and rng.random() < 0.5) or rng.random() < 0.08:
            target = rng.randint(rowmin, rowmax)
            if mode == 'safe':
                target = max(F0 - 4, min(25, target))
        r = rng.random()
        if cur != target and room >= 3:
            d = target - cur
            d = max(-JUMP_UP, min(4 if mode != 'safe' else 2, d)) if d > 0 else max(-JUMP_UP if mode != 'safe' else -2, d)
            cur = max(rowmin, min(rowmax, cur + d))
            n = rng.randint(3, 7)
        elif pits_ok and r < 0.35 and room > 8:
            w = rng.randint(2, GAP_MAX)
            c += w
            cur = max(rowmin, min(rowmax, cur + rng.choice([0, 1, 1, 2])))
            n = rng.randint(3, 6)
        else:
            n = rng.randint(4, 11)
        for cc in range(c, min(cols, c + n, nxt)):
            tops[cc] = cur
        c = min(c + n, nxt) if n else c + 1
    # make every exit / midway / goal column flat over 4 columns
    for x in list(exit_cols.values()) + ([mid_col] if mid_col else []) + ([goal_col] if goal_col else []):
        h = tops[x] if tops[x] is not None else next((tops[i] for i in range(x, -1, -1) if tops[i] is not None), F0)
        for cc in range(max(0, x - 2), min(cols, x + 4)):
            tops[cc] = h
    _fix_steps(tops)
    # build ground runs
    c = 0
    while c < cols:
        if tops[c] is None:
            c += 1
            continue
        c1 = c
        while c1 + 1 < cols and tops[c1 + 1] == tops[c]:
            c1 += 1
        lt = tops[c - 1] if c > 0 else None
        rt = tops[c1 + 1] if c1 + 1 < cols else None
        L.ground(c, c1, tops[c], left_edge=(lt is None or lt > tops[c]) and c > 0,
                 right_edge=(rt is None or rt > tops[c]) and c1 < cols - 1)
        c = c1 + 1
    # spawn features
    if action == 3:
        L.pipe(scol, F0 - 2, F0 - 1)
    # pits get coin arcs and sometimes a helper ledge
    c = 0
    while c < cols:
        if tops[c] is None:
            c1 = c
            while c1 + 1 < cols and tops[c1 + 1] is None:
                c1 += 1
            lt = tops[c - 1] if c > 0 else F0
            w = c1 - c + 1
            for i in range(w):
                L.coins(c + i, max(1, lt - 3 - (1 if 0 < i < w - 1 else 0)))
            c = c1 + 1
        else:
            c += 1
    # flat stretches: block rows, stairs, pipes, enemies
    occupied = set()
    for x in list(exit_cols.values()) + ([mid_col] if mid_col else []) + [scol]:
        occupied.update(range(x - 3, x + 5))
    if goal_col is not None:
        occupied.update(range(goal_col - 8, goal_col + 5))
    runs = []
    c = 0
    while c < cols:
        if tops[c] is None:
            c += 1
            continue
        c1 = c
        while c1 + 1 < cols and tops[c1 + 1] == tops[c]:
            c1 += 1
        runs.append((c, c1, tops[c]))
        c = c1 + 1
    items_placed = 0
    for (a, b, t) in runs:
        free = [x for x in range(a + 4, b - 3) if x not in occupied]   # run ends stay clear overhead
        if len(free) < 5:
            continue
        kind = rng.random()
        x0 = free[rng.randint(0, max(0, len(free) - 5))]
        if kind < 0.4 and t - 4 >= 2:
            n = rng.randint(3, 5)
            pat = [rng.choice([TURN, QCOIN, TURN, COIN]) for _ in range(n)]
            if items_placed < 2 + screens // 4:
                pat[rng.randint(0, n - 1)] = rng.choice([Q_POWER, Q_POWER, Q_FEATHER, Q_MULTI])
                items_placed += 1
            for i, bk in enumerate(pat):
                if x0 + i <= b - 1:
                    if bk == COIN:
                        L.coins(x0 + i, t - 4)
                    else:
                        L.block(x0 + i, t - 4, bk)
            occupied.update(range(x0, x0 + n))
        elif kind < 0.55 and b - x0 >= 6:
            hgt = rng.randint(2, 3)
            if mode != 'room':
                L.pipe(x0, t - hgt, t - 1)
                occupied.update(range(x0, x0 + 2))
                if PIPE_DWELLERS & set(e['roster']) and rng.random() < 0.5:
                    L.sprite(sorted(PIPE_DWELLERS & set(e['roster']))[0], x0, t - hgt - 1)
        elif kind < 0.7 and b - x0 >= 7:
            up = rng.randint(2, 3)
            for i in range(up):
                L.cement(x0 + i, t - 1 - i, 1, i + 1)
            for i in range(up):
                L.cement(x0 + up + i, t - up + i, 1, up - i)
            occupied.update(range(x0, x0 + 2 * up))
        elif kind < 0.85:
            L.coins(x0, t - 3, min(4, b - x0), 1)
    # floating ledges (a higher route in courses; furniture in rooms)
    for s_ in range(0, screens):
        for _ in range(1 if mode == 'course' else 2):
            if rng.random() > (0.4 if mode == 'course' else 0.75):
                continue
            w = rng.randint(3, 6)
            a = s_ * 16 + rng.randint(1, 15 - w)
            if a + w >= cols or any(x in occupied for x in range(a, a + w + 1)):
                continue
            col_tops = [tops[x] for x in range(a, a + w + 1) if tops[x] is not None]
            t = min(col_tops) if col_tops else F0
            r = t - rng.randint(4, 6)
            if r >= 3:
                L.platform(a, a + w, r)
                if rng.random() < 0.6:
                    L.coins(a + 1, r - 1, w - 1, 1)
                occupied.update(range(a, a + w + 1))
    # exits: a door or an enterable pipe in each exit screen
    for x in exits:
        s = x['screen']
        if s not in exit_cols:
            continue
        c = exit_cols[s]
        t = tops[c]
        if 'door' in x['kind'] or 'ghost_exit' in x['kind']:
            L.door(c, t - 2)
        else:
            L.pipe(c, t - 2, t - 1, enterable=True)
        L.screen_exit(s, x['dest'], x['flags'] & 1)
    if mid_col:
        L.midway(mid_col, tops[mid_col] - 1)
    if goal_col is not None:
        L.goal(goal_col, tops[goal_col])
    if 'ghost_exit' in ends and goal_col is None:
        c = cols - 6
        L.door(c, tops[c] - 2)
    if key_needed:
        kc = (goal_col - 10) if goal_col else cols - 8
        kc = max(4, kc)
        t = tops[kc] if tops[kc] is not None else F0
        L.platform(kc - 1, kc + 3, t - 4)
        L.sprite(0x0E, kc + 1, t - 6)                 # keyhole on the ledge
        kk = max(2, kc - 14)
        tk = tops[kk] if tops[kk] is not None else F0
        L.sprite(0x80, kk, tk - 1)
    # dragon coins: up to five per course, in reach
    if mode == 'course':
        picks = [r for r in runs if r[1] - r[0] >= 4]
        rng.shuffle(picks)
        for (a, b, t) in picks[:5]:
            x = (a + b) // 2
            if x not in occupied and t - 4 >= 1:
                L.dragon_coin(x, t - 3)
                occupied.add(x)
    if mode != 'safe':
        _place_enemies(L, e, rng, runs, occupied, tops, water, F0)
    _anchor_sprites(L, e)
    L.tops = tops
    L.spawn = (scol, F0)
    L.goal_col = goal_col
    L.exit_cols = exit_cols
    return L


def _fix_steps(tops):
    """Enforce the jump limits between neighbouring ground runs and pit widths."""
    n = len(tops)
    for _ in range(3):
        for c in range(1, n):
            a, b = tops[c - 1], tops[c]
            if a is not None and b is not None and a - b > JUMP_UP:      # step up too high
                tops[c] = a - JUMP_UP
        # pits: the landing must be at most JUMP_UP above the take-off and pits at most GAP_MAX wide
        c = 0
        while c < n:
            if tops[c] is None:
                c1 = c
                while c1 + 1 < n and tops[c1 + 1] is None:
                    c1 += 1
                lt = tops[c - 1] if c > 0 else None
                rt = tops[c1 + 1] if c1 + 1 < n else None
                if lt is None:
                    for i in range(c, c1 + 1):
                        tops[i] = rt
                elif rt is None:
                    for i in range(c, c1 + 1):
                        tops[i] = lt
                else:
                    w = c1 - c + 1
                    ok = (w <= 3 and rt >= lt) or (w <= GAP_MAX and rt >= lt + 1)
                    if not ok:
                        for i in range(c, c1 + 1):
                            tops[i] = lt
                c = c1 + 1
            else:
                c += 1


def _place_enemies(L, e, rng, runs, occupied, tops, water, F0):
    roster = set(e['roster'])
    walkers = sorted(roster & WALKERS)
    fliers = sorted(roster & FLIERS)
    swimmers = sorted(roster & SWIMMERS)
    helpers = sorted(roster & HELPERS)
    plats = sorted(roster & PLATFORMS)
    budget = max(2, min(20, e['n_sprites']))
    placed = 0
    spawn_c = L.spawn[0] if hasattr(L, 'spawn') else 0
    cand = [(a, b, t) for (a, b, t) in runs if b - a >= 3]
    rng.shuffle(cand)
    for (a, b, t) in cand:
        if placed >= budget:
            break
        x = rng.randint(a + 1, b - 1)
        if abs(x - spawn_c) < 8 or x in occupied:
            continue
        if water and swimmers:
            L.sprite(rng.choice(swimmers), x, max(2, t - rng.randint(3, 6)))
        elif walkers:
            L.sprite(rng.choice(walkers), x, t - 1)
        elif fliers:
            L.sprite(rng.choice(fliers), x, max(2, t - rng.randint(4, 6)))
        else:
            break
        placed += 1
    if fliers and walkers:
        for _ in range(min(3, len(cand))):
            a, b, t = rng.choice(cand)
            x = rng.randint(a, b)
            if abs(x - spawn_c) >= 10:
                L.sprite(rng.choice(fliers), x, max(2, t - 5))
    for h in helpers[:2]:
        a, b, t = rng.choice(cand) if cand else (2, 4, F0)
        L.sprite(h, a + 1, t - 1)
    for p in plats[:1]:
        pits = [c for c in range(1, L.cols - 1) if tops[c] is None and tops[c - 1] is not None]
        if pits:
            c = rng.choice(pits)
            L.sprite(p, c, tops[c - 1] - 1)


def _anchor_sprites(L, e):
    """Bosses and specials whose position the code depends on keep their position."""
    for num, scr, x, y, extra in e['anchor_sprites']:
        if L.vertical:
            L.sprs.append(F.Spr(num, scr, x, y, extra))
        else:
            L.sprs.append(F.Spr(num, scr, x, y, extra))
    for num in e['behaviour']:
        if num in GENERATORS:
            L.sprite(num, 16 if L.cols > 16 else 2, 1)


# ---------------------------------------------------------------- vertical levels
def gen_vertical(e, slot, kept, rng):
    screens = e['screens']
    rows = 16 * screens
    L = Level(32, rows, True, e['tileset'])
    sp = spawn_of(slot, kept)
    srow = sp['screen'] * 16 + sp['row'] % 16
    scol = min(29, max(1, sp['col'] + (16 if sp['xhi'] else 0)))
    floor = min(rows - 1, srow + 2)
    L.ground(max(0, scol - 4), min(31, scol + 5), floor, bottom=min(rows - 1, floor + 2))
    # zig-zag ledges climbing up and down from the spawn floor
    r = floor - 3
    side = 0
    top_ledge = None
    while r >= 3:
        w = rng.randint(4, 7)
        c0 = rng.randint(1, 10) if side == 0 else rng.randint(15, 31 - w)
        L.platform(c0, c0 + w, r)
        if rng.random() < 0.4:
            L.coins(c0 + 1, r - 1, w - 2, 1)
        top_ledge = (c0, c0 + w, r)
        side ^= 1
        r -= 3
    r = floor + 4
    while r <= rows - 3:
        w = rng.randint(5, 9)
        c0 = rng.randint(1, 31 - w)
        L.platform(c0, c0 + w, r)
        r += 3
    if top_ledge:
        a, b, t = top_ledge
        L.platform(0, 31, t)
    ends = set(e['ends'])
    if 'goal' in ends and top_ledge:
        L.goal(12, top_ledge[2])
    for x in e['exits']:
        s = x['screen']
        rr = min(rows - 2, s * 16 + 12)
        c = 6 if rng.random() < 0.5 else 22
        L.platform(c - 2, c + 4, rr)
        if 'door' in x['kind']:
            L.door(c, rr - 2)
        else:
            L.pipe(c, rr - 2, rr - 1, enterable=True)
        L.screen_exit(s, x['dest'], x['flags'] & 1)
    roster = sorted(set(e['roster']) & (WALKERS | FLIERS))
    for i in range(min(10, e['n_sprites'])):
        if roster:
            rr = rng.randint(2, rows - 3)
            if abs(rr - srow) > 10:
                L.sprite(rng.choice(roster), rng.randint(2, 29), rr)
    _anchor_sprites(L, e)
    L.spawn = (scol, floor)
    return L


# ---------------------------------------------------------------- special rooms and scenes
def gen_arena(e, slot, kept, rng):
    """Boss rooms and other anchored rooms: flat arena on the spawn floor, walls at both ends;
    bosses keep their anchored positions; throw blocks for rooms whose boss needs them."""
    screens = max(1, e['screens'])
    cols = 16 * screens
    L = Level(cols, H, False, e['tileset'])
    sp = spawn_of(slot, kept)
    F0 = _floor_of(sp)
    if e.get('anchor_pipes'):          # kid rooms: pipes on the anchored columns, own heights, no floor
        hs = [20, 19, 20, 18, 20, 19, 20, 19]
        for k, (c, r, n) in enumerate(e['anchor_pipes']):
            L.pipe(c, hs[k % len(hs)], H - 1)
        for _ in range(3):
            x = rng.randint(1, cols - 5)
            L.platform(x, x + rng.randint(1, 3), rng.randint(9, 14))
        _anchor_sprites(L, e)
        L.spawn = (sp['col'], 18)
        return L
    a, b = 3, cols - 4
    L.ground(0, a - 1, F0 - 2, left_edge=False)
    L.ground(a, b, F0, left_edge=False, right_edge=False)
    L.ground(b + 1, cols - 1, F0 - 2, right_edge=False)
    for _ in range(max(2, screens * 2)):
        w = rng.randint(2, 4)
        x = rng.randint(a + 1, max(a + 2, b - w - 1))
        L.platform(x, x + w, F0 - rng.randint(4, 6))
    if 'bigboo' in e['ends']:
        for c in (4, cols - 6):
            L.block(c, F0 - 1, THROW)
    for x in e['exits']:
        c = x['screen'] * 16 + 8
        if c < cols:
            L.door(c, F0 - 2) if 'door' in x['kind'] else L.pipe(c, F0 - 2, F0 - 1, enterable=True)
            L.screen_exit(x['screen'], x['dest'], x['flags'] & 1)
    _anchor_sprites(L, e)
    L.spawn = (sp['col'], F0)
    return L


def gen_scene(sc, rng):
    """Short code-driven scenes (castle/ghost-house walk-ins, cast roll stages): the floor row and the
    building spot are anchors (the code walks the player / the cast along them); the rest is new."""
    cols = 16 * sc['screens']
    L = Level(cols, H, False, sc['tileset'])
    F0 = sc['floor']
    L.ground(0, cols - 1, F0, left_edge=False, right_edge=False)
    for _ in range(rng.randint(2, 4)):                 # own scenery above the anchored floor
        w = rng.randint(2, 5)
        x = rng.randint(0, cols - w - 1)
        r = F0 - rng.randint(4, 8)
        if r >= 1:
            if rng.random() < 0.6:
                L.platform(x, x + w, r)
            else:
                L.cement(x, r, w, 1)
    for b, c, r in sc.get('buildings', []):
        L._o(0, c, r, ext=b)
    for x in sc['exits']:
        L.screen_exit(x['screen'], x['dest'], x['flags'])
    return L


# ---------------------------------------------------------------- whole build
# title-demo level, intro message level, the home hut and the credits walk: the code replays inputs or
# shows them without the player's control, so they stay flat and enemy-free
SAFE_SLOTS = {0xC5, 0xC7, 0xC8, 0x104, 0x1C8}


def classify(e):
    ends = set(e['ends'])
    if e['empty']:
        return 'empty'
    if set(e['members']) & SAFE_SLOTS:
        return 'safe'
    if e['mode'] in (7, 8, 10, 13):
        return 'vertical'
    if ends & {'koopakid', 'reznor', 'bowser', 'bigboo'} or e['anchor_sprites'] and e['screens'] <= 2 and not ends & {'goal'}:
        return 'arena'
    if ends & {'goal', 'keyhole', 'orb', 'ghost_exit', 'switch', 'bonusgame'} or e['screens'] >= 6:
        return 'course'
    return 'room'


def build_one(e, kept):
    """One layout (None for empty slots)."""
    slot = e['members'][0]
    kind = classify(e)
    if kind == 'empty':
        return None
    rng = random.Random(SEED * 1000 + slot + bump('level_%03X' % slot))
    if kind == 'vertical':
        return gen_vertical(e, slot, kept, rng)
    if kind == 'arena':
        return gen_arena(e, slot, kept, rng)
    for attempt in range(40):          # re-roll until the course passes its own reachability check
        lv = gen_course(e, slot, kept, random.Random(SEED * 1000 + slot + 7919 * attempt + bump('level_%03X' % slot)),
                        kind if kind in ('course', 'safe') else 'room')
        if not check_course(lv):
            return lv
    print('levels: WARNING %03X still fails: %s' % (slot, check_course(lv)))
    return lv


def build_all(kept, spec=None):
    spec = spec or json.load(open(os.path.join(SPEC, 'levels.json')))
    L1 = [b''] * 512
    L2obj = {}
    spr_lists = [None] * 512
    built = {}
    stats = {}
    for e in spec['levels']:
        slot = e['members'][0]
        kind = classify(e)
        stats[kind] = stats.get(kind, 0) + 1
        hdr = bytes.fromhex(e['hdr'])
        if kind == 'empty':
            d1 = hdr + bytes([0xFF])
            ds = bytes([e['spr_hdr'], 0xFF])
            lv = None
        else:
            lv = build_one(e, kept)
            d1, ds = lv.emit(hdr, e['spr_hdr'])
        for m in e['members']:
            L1[m] = d1
            spr_lists[m] = ds
            if e['layer2'] == 'objects':
                L2obj[m] = hdr + b'\xff'
        built[slot] = (kind, lv)
    return L1, L2obj, spr_lists, built, stats


def pack_sprites(spr_lists, spec):
    """Sprite lists into one blob in bank 7, keeping the addresses the code uses directly."""
    special = {int(a, 16): v for a, v in spec['special_sprite_lists'].items()}
    fixed = {}
    for a, v in special.items():
        fixed[a] = bytes([v['spr_hdr'], 0xFF])
    ranges = list(fixed.items())
    ptrs = [0] * 512
    uniq = {}
    addr = 0x078000
    chunk = bytearray()
    for i, d in enumerate(spr_lists):
        if d not in uniq:
            uniq[d] = addr + len(chunk)
            chunk += d
        ptrs[i] = uniq[d] & 0xFFFF
    assert addr + len(chunk) <= 0x07C3EE, 'sprite lists overflow bank 7 space (%d bytes)' % len(chunk)
    ranges.append((addr, bytes(chunk)))
    return F.pack_blob(ranges), struct.pack('<512H', *ptrs), bytes([7] * 512)


def build(items, kept, spec_dir):
    spec = json.load(open(os.path.join(spec_dir, 'levels.json')))
    L1, L2obj, spr_lists, built, stats = build_all(kept, spec)
    out = {'kLevelData_Layer1': A.pack_array(L1)}
    # object-type (non-background) layer-2 data of every table: our own (empty) object lists
    for name in ('kLevelData_Layer2', 'kEntranceData_Layer2', 'kChoclateIsland2_Layer2', 'kRollCallData_Layer2',
                 'kBufferCreditsBackgrounds_Layer2'):
        arr = A.unpack_array(items[name])
        flags = items[name + '_IsBg']
        for i in range(len(arr)):
            if i < len(flags) and not flags[i] and len(arr[i]):
                arr[i] = bytes(5) + bytes([0xFF])
        out[name] = A.pack_array(arr)
    blob, ptrs, banks = pack_sprites(spr_lists, spec)
    out['kLvlSprBlob'], out['kLoadLevel_SpriteDataPtrs'], out['kLmSpritePtrBankByte'] = blob, ptrs, banks
    rng = random.Random(SEED)
    for name, key in (('kEntranceData_Layer1', 'entrance_scenes'), ('kRollCallData_Layer1', 'rollcall'),
                      ('kChoclateIsland2_Layer1', 'choco2')):
        arr = []
        for k, sc in enumerate(spec[key]):
            if sc is None:
                arr.append(b'')
                continue
            if sc.get('empty'):                # an empty scene stays empty (structure)
                arr.append(bytes.fromhex(sc['hdr']) + bytes([0xFF]))
                continue
            if key == 'choco2':          # playable variants of one level: rooms with their exits
                e = {'screens': sc['screens'], 'tileset': sc['tileset'], 'mode': sc['mode'], 'ends': [],
                     'exits': [dict(x, kind=['pipe_v']) for x in sc['exits']], 'roster': [0x0F, 0x02, 0x0D],
                     'anchor_sprites': [], 'behaviour': [], 'n_sprites': 6}
                lv = gen_course(e, None, kept, random.Random(SEED + 77 + k + bump('choco2_%03X' % k)), 'room', spawn={
                    'col': 2, 'xhi': 0, 'row': sc['floor'] - 2, 'screen': 0, 'action': 0, 'midway': 0})
                lv.sprs = []               # their sprites come from the fixed lists the code points at
            else:
                kind_ = 'entrance' if key == 'entrance_scenes' else 'rollcall'
                lv = gen_scene(sc, random.Random(SEED + 31 * k + bump('%s_%03X' % (kind_, k))))
            arr.append(F.emit_objects(bytes.fromhex(sc['hdr']), lv.objs))
        out[name] = A.pack_array(arr)
    print('levels: %s' % ', '.join('%s %d' % kv for kv in sorted(stats.items())))
    return out


# ---------------------------------------------------------------- playability check
STAND_CLS = {'solid', 'ledge', 'conveyor_ledge', 'cement', 'used_block', 'turn_block', 'question_block', 'note_block',
             'throw_block', 'pipe', 'slope', 'slope_support', 'side_block', 'glass_block', 'star_block', 'onoff_block',
             'shooter', 'palace_switch', 'water_slope', 'invisible_block'}
BLOCK_CLS = STAND_CLS - {'ledge', 'conveyor_ledge', 'slope', 'slope_support', 'water_slope', 'invisible_block'}


def _classes(grid, tileset):
    from games.smw import blocks as B
    cache = {}
    stand = np.zeros(grid.shape, bool)
    block = np.zeros(grid.shape, bool)
    for v in np.unique(grid):
        c = cache.setdefault(int(v), B.cls(int(v) & 0x1FF, tileset))
        m = grid == v
        stand |= m & (c in STAND_CLS)
        block |= m & (c in BLOCK_CLS)
    return stand, block


def reachable(grid, tileset, spawn):
    """BFS over standing spots (col, row of the block stood on) with SMW-like jump limits:
    up to 4 rows up and 5 columns across (fewer across when jumping high), any drop, 2 rows of
    head room. Returns the set of (col, row)."""
    stand, block = _classes(grid, tileset)
    rows, cols = grid.shape
    free = ~block

    def ok(c, r):
        return 0 <= c < cols and 1 <= r < rows and stand[r, c] and free[r - 1, c] and (r < 2 or free[r - 2, c])

    sc, sf = spawn
    start = None
    for r in range(max(1, sf - 3), rows):
        if ok(sc, r):
            start = (sc, r)
            break
    if start is None:
        return set(), None
    seen = {start}
    todo = [start]
    while todo:
        c, r = todo.pop()
        head = 0
        while head < 4 and r - 2 - head >= 0 and free[r - 2 - head, c]:
            head += 1
        for dc in range(-5, 6):
            c2 = c + dc
            if not 0 <= c2 < cols:
                continue
            for r2 in range(max(1, r - head), rows):
                up = r - r2
                if abs(dc) > 5 - max(0, up - 2):
                    continue
                if ok(c2, r2) and (c2, r2) not in seen:
                    # the columns flown over must not be walls at take-off height
                    lo, hi = sorted((c, c2))
                    top = min(r, r2) - 2
                    if all(free[max(0, top), x] for x in range(lo, hi + 1)):
                        seen.add((c2, r2))
                        todo.append((c2, r2))
    return seen, start


def check_course(lv, grid=None):
    """-> list of problems (empty = goal / exits / keyhole reachable from the spawn)."""
    g = lv.g if grid is None else grid
    if lv.vertical or not hasattr(lv, 'spawn'):
        return []
    seen, start = reachable(g, lv.tileset, lv.spawn)
    if start is None:
        return ['no floor at spawn']
    cols = {c for c, r in seen}
    probs = []
    if getattr(lv, 'goal_col', None) is not None and not any(abs(c - lv.goal_col - 1) <= 2 for c in cols):
        probs.append('goal unreachable (max col %d of %d)' % (max(cols), lv.goal_col))
    for c in getattr(lv, 'exit_cols', {}).values():
        if not any(abs(x - c) <= 1 for x in cols):
            probs.append('exit at col %d unreachable' % c)
    return probs


# ---------------------------------------------------------------- gate anchors
def anchor_points(spec=None, kept=None):
    """Gameplay anchors for the geometry gate, in orig_levels mesh space (x = col, y = -row):
    the anchored spawn floor of every level, the boss pipes of the kid rooms, and the whole floor
    row of the code-driven scenes (walk-ins and the cast roll run along it)."""
    spec = spec or json.load(open(os.path.join(SPEC, 'levels.json')))
    kept = kept or dict(A.read(os.path.join(SPEC, 'tables.dat')))
    by = {}
    for e in spec['levels']:
        if e['empty']:
            continue
        slot = e['members'][0]
        sp = spawn_of(slot, kept)
        c, r = sp['screen'] * 16 + sp['col'], _floor_of(sp)
        pts = [[c + dx + 0.5, -r - 0.5, z] for dx in range(-2, 4) for z in (0.0,)]
        for pc, pr, n in e.get('anchor_pipes', []):
            pts += [[pc + dx + 0.5, -rr - 0.5, z] for dx in (0, 1) for rr in range(17, H) for z in (0.0,)]
        by['level_%03X.obj' % slot] = pts
    for key, kind in (('entrance_scenes', 'entrance'), ('rollcall', 'rollcall'), ('choco2', 'choco2')):
        for i, sc in enumerate(spec[key]):
            if sc is None:
                continue
            f = sc['floor']
            by['%s_%03X.obj' % (kind, i)] = [[c + 0.5, -f - 0.5, z] for c in range(16 * sc['screens'])
                                             for z in (0.0,)] if kind != 'choco2' else \
                [[c + 0.5, -f - 0.5, z] for c in range(0, 6) for z in (0.0,)]
    return {'by_mesh': by}


if __name__ == '__main__':
    import sys
    if '--anchors' in sys.argv:
        out = os.path.join(os.path.dirname(__file__), 'level_anchors.json')
        json.dump(anchor_points(), open(out, 'w'))
        print('wrote', out)
