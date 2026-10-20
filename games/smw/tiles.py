"""CLEAN ROOM. Level tiles, Map16 and backgrounds for Bramble Isles (module 'tiles').

build(items, kept, spec_dir) -> {entry: bytes} replaces
  - FG/BG/animated sheets 07 08 0C 0D 0E 0F 14-1B 1F 2C and kGfx33 (level animation frames),
  - kMap16Data (FG part + background part at +0x1100), kMap16Data_Castle/_Rope/_Underground/_GhostHouse,
  - the background layer-2 tilemaps (kLevelData_Layer2 BG entries, kEntranceData_Layer2, kChoclateIsland2_Layer2,
    kRollCallData_Layer2, kBufferCreditsBackgrounds_Layer2: BG entries),
  - palettes Sky / Background / Foreground / Objects / Flashing / B5EC.
Inputs: code-derived block behaviour (blocks.py), object layouts from running the port's object routines
(spec/object_grids.json), structural survey (spec/tiles.json: entry sizes, BG flags, which sheet tiles
other scenes still need). Every picture is drawn here; no retail outline, colour grid or arrangement."""
import os, json, struct, collections
import numpy as np
from games.smw import assetfile as A, blocks as B, tilekit as K
from games.smw.tilekit import T, W, O, D, M, L, H, A as AC
from cleanroom.snes import lz2, tiles as TL

HERE = os.path.dirname(__file__)
TABLES = {'grass': ('kMap16Data', 0x8B70, 0), 'castle': ('kMap16Data_Castle', 0xBC00, 1),
          'rope': ('kMap16Data_Rope', 0xC800, 2), 'underground': ('kMap16Data_Underground', 0xD400, 3),
          'ghost': ('kMap16Data_GhostHouse', 0xE300, 5)}
# which FG3 sheets render each table (kUploadGraphicsFiles_FGAndBGGFXList x Map16 table per tileset)
TABLE_SHEETS = {'grass': (0x15, 0x1F), 'castle': (0x18,), 'rope': (0x16,), 'underground': (0x1A, 0x08, 0x18),
                'ghost': (0x08, 0x07)}
FG3_SHEETS = (0x15, 0x16, 0x18, 0x1A, 0x08, 0x07, 0x1F, 0x2C)
BG_SHEETS = (0x19, 0x1B, 0x0C, 0x0D)
THEME = {0x15: 'grass', 0x1F: 'forest', 0x16: 'rope', 0x18: 'castle', 0x1A: 'cave', 0x08: 'crystal', 0x07: 'ghost',
         0x2C: 'grass', 0x19: 'hills', 0x1B: 'castle', 0x0C: 'cave', 0x0D: 'woods'}
# sheet components that must share FG3 tile positions (tables x sheets graph)
FG3_COMPONENT = {'grass': 'A', 'rope': 'B', 'castle': 'C', 'underground': 'C', 'ghost': 'C'}
COMP_SHEETS = {'A': (0x15, 0x1F, 0x2C), 'B': (0x16,), 'C': (0x18, 0x1A, 0x08, 0x07)}

# animated VRAM tiles (kLevelTileAnimations slots): Map16 refers to them directly
ANIM = {'prize': 0x60, 'note': 0x64, 'turn': 0x68, 'belt': 0x74, 'spin': 0xEA, 'pdoor': 0x50, 'pcoin': 0x54,
        'used': 0x58, 'muncher': 0x5C, 'pblock': 0x78, 'track': 0x7C, 'onoff': 0xDA, 'coin': 0x6C,
        'water': 0x4C, 'lava': 0x44, 'deco14': 0x70, 'deco17': 0x48, 'deco18': 0x40}
FG2_RESERVED = {0x00, 0x01, 0x10, 0x11, 0x5A, 0x5B, 0x5C, 0x5D, 0x6A, 0x6B, 0x6C, 0x6D}
PAL_GROUND, PAL_SECOND = 2, 3
PAL_SLATE, PAL_GREEN, PAL_GOLD, PAL_BERRY = 4, 5, 6, 7

MATERIAL_WORDS = [  # routine-name keyword -> material (first match wins)
    ('Pipe', 'pipe'), ('Bush', 'leaf'), ('TreeTop', 'leaf'), ('Trunk', 'trunk'), ('Branch', 'trunk'),
    ('Cloud', 'cloud'), ('Seaweed', 'weed'), ('BoneLog', 'log'), ('LogBridge', 'log'), ('HorizontalLog', 'log'),
    ('VerticalLog', 'log'), ('MushroomTop', 'cap'), ('MushroomColumn', 'stem'), ('Column', 'column'),
    ('Spike', 'spike'), ('Lava', 'lavarock'), ('StoneBlock', 'stone'), ('WoodCrate', 'stone'), ('WoodenBlocks', 'stone'),
    ('SolidBrickWall', 'stone'), ('Pillar', 'column'), ('WoodLedge', 'wood'), ('WoodenLedge', 'wood'),
    ('Railing', 'beam'), ('BackgroundLog', 'beam'), ('Beam', 'beam'), ('Cobweb', 'web'), ('Clock', 'clock'),
    ('Window', 'window'), ('Entrance', 'facade'), ('GhostHouseExit', 'facade'), ('BossDoor', 'facade'),
    ('YoshisHouse', 'house'), ('GoalSign', 'sign'), ('SwitchPalace', 'palace'), ('LineGuide', 'line'),
    ('ConveyorEnd', 'line'), ('Escalator', 'line'), ('ConveyorRope', 'line'), ('RopeAndCloudLine', 'line'),
    ('DonutBridge', 'donut'), ('Torpedo', 'launcher'), ('Brick', 'wallbg'), ('Canvas', 'wallbg'),
    ('RockWall', 'wallbg'), ('BackgroundArea', 'wallbg'), ('MidwayAndGoal', 'post'), ('MidwayBar', 'post'),
    ('Ground', 'ground'), ('Ledge', 'ground'), ('Slope', 'ground'), ('Dirt', 'ground'), ('Ceiling', 'ground'),
    ('PurpleTriangle', 'ground'), ('Coins', None),
]
# cliff side pieces of StdObj13 (types 3-6): top corner and column of the left / right ground edge
EDGE_SIDES = {0x145: dict(u=True, d=False, l=True, r=False), 0x14B: dict(u=False, d=False, l=True, r=False),
              0x148: dict(u=True, d=False, l=False, r=True), 0x14C: dict(u=False, d=False, l=False, r=True)}
IGNORE = {  # extended objects that belong to other tilesets (the port runs them anywhere)
    'grass': ('Canvas', 'Brick', 'LineGuide', 'Clock', 'Cobweb', 'Cave', 'Torpedo', 'Beam', 'GhostHouseWindow'),
    'rope': ('Canvas', 'Brick', 'Clock', 'Cobweb', 'Cave', 'Yoshi', 'Beam', 'GhostHouseWindow'),
    'castle': ('GhostHouse', 'Clock', 'Cobweb', 'Yoshi', 'Bush', 'TreeBranch', 'Beam'),
    'underground': ('GhostHouse', 'Clock', 'Cobweb', 'Yoshi', 'Bush', 'TreeBranch', 'Beam'),
    'ghost': ('Yoshi', 'Bush', 'Cave', 'Castle', 'TreeBranch', 'Torpedo'),
}
THEMED = {'ground', 'stone', 'wood', 'wallbg', 'beam', 'column', 'cap', 'stem', 'trunk', 'log', 'lavarock'}


# ===================================================================== data
class Data:
    def __init__(self, spec):
        self.grids = json.load(open(os.path.join(spec, 'object_grids.json')))
        self.objs = json.load(open(os.path.join(spec, 'objects.json')))
        self.survey = json.load(open(os.path.join(spec, 'tiles.json')))
        grp = {'grass': 'grassland', 'castle': 'castle', 'rope': 'rope', 'underground': 'underground', 'ghost': 'ghosthouse'}
        self.grp = grp

    def routine(self, fam, o):
        if o.startswith('E'):
            e = self.objs['extended'].get(o[1:])
            return e['routine'] if e else ''
        e = self.objs['standard'].get(o, {}).get(self.grp[fam])
        return e['routine'] if e else ''

    def stats(self, fam, b):
        return self.grids[fam].get('%03X' % b)

    def material(self, fam, b):
        st = self.stats(fam, b)
        if not st:
            return None
        votes = collections.Counter()
        for o in st['objs']:
            r = self.routine(fam, o)
            if any(w in r for w in IGNORE.get(fam, ())) or 'Unused' in r:
                continue
            for word, mat in MATERIAL_WORDS:
                if word in r:
                    if mat:
                        votes[mat] += 1 if o.startswith('E') else 3
                    break
        if votes['ground'] and any('Ground' in self.routine(fam, o) for o in st['objs']):
            return 'ground'                  # ground objects win over size-overflow writes of other objects
        return votes.most_common(1)[0][0] if votes else None

    def open(self, fam, b, thr=0.5):
        if b in EDGE_SIDES:
            return EDGE_SIDES[b]
        st = self.stats(fam, b)
        if not st:
            return dict(u=True, d=True, l=True, r=True)
        return {k: st['open'][k] >= thr for k in 'udlr'}


# ===================================================================== tile store
class Store:
    """8x8 tiles per group. fg1/fg2: fixed pixels (deduped with flips). fg3/bg: keys rendered per theme."""
    def __init__(self):
        self.px = {'fg1': {}, 'fg2': {}}
        self.free = {'fg1': list(range(0x00, 0x40)), 'fg2': [i for i in range(0x80) if i not in FG2_RESERVED]}
        self.keys = {}          # (group, key) -> index for fg3 components / bg
        self.free_k = {}
        self.overflow = collections.Counter()

    def pixel(self, group, tile):
        """-> (group, index, hflip, vflip) for an 8x8 index array."""
        t = np.asarray(tile, np.uint8)
        for g in ([group] if group else ['fg1', 'fg2']):
            for hf in (0, 1):
                for vf in (0, 1):
                    v = t[::-1 if vf else 1, ::-1 if hf else 1]
                    k = v.tobytes()
                    if k in self.px[g]:
                        return g, self.px[g][k], hf, vf
        for g in ([group] if group else ['fg1', 'fg2']):
            if self.free[g]:
                i = self.free[g].pop(0)
                self.px[g][t.tobytes()] = i
                return g, i, 0, 0
        self.overflow['pixel'] += 1
        return 'fg1', 0, 0, 0

    def key(self, space, key, render):
        """space: 'fg3:common', 'fg3:A' ... or 'bg'. render(theme) -> 8x8. -> index in the sheet."""
        sk = (space, key)
        if sk in self.keys:
            return self.keys[sk][0]
        pool = self.free_k[space]
        if not pool:
            self.overflow[space] += 1
            return None
        i = pool.pop(0)
        self.keys[sk] = (i, render)
        return i


# ===================================================================== textures per theme
def tex(theme, mat, seed=0):
    """8x8 periodic fill texture (indices 2..7) for a material in a theme."""
    r = K.rng(hash((theme, mat, seed)) & 0xFFFF)
    y, x = np.mgrid[0:8, 0:8]
    if mat in ('ground', 'lavarock'):
        if theme in ('castle',):
            t = np.full((8, 8), M, np.uint8)
            t[3, :] = D; t[7, :] = D; t[0:3, 5] = D; t[4:7, 1] = D
            t[0, 0:5] = L; t[4, 2:8] = L
            return t
        if theme == 'ghost':
            t = np.full((8, 8), M, np.uint8)
            t[:, 0] = D; t[:, 4] = D
            t[(y * 3 + x) % 7 == 0] = L
            t[2, 1:4] = L; t[6, 5:8] = O
            return t
        if theme == 'crystal':
            t = np.full((8, 8), M, np.uint8)
            t[(x + y) == 7] = H; t[(x + y) == 8] = D; t[x == y] = L
            t[0, :] = D; t[:, 0] = D
            return t
        if theme == 'cave':
            v = K.periodic_noise((8, 8), 31 + seed, 8, ((4, 1.0), (2, 0.6)))
            t = K.shade(v, [D, M, M, L])
            t[(v > 0.85)] = H
            t[(v < 0.12)] = O
            return t
        v = K.periodic_noise((8, 8), 11 + seed + (5 if theme == 'forest' else 0), 8, ((4, 1.0), (2, 0.5)))
        t = K.shade(v, [D, M, M, L])
        t[2, 5] = L; t[6, 1] = L; t[5, 6] = O if theme != 'rope' else D
        if theme == 'forest':
            t[1, 2] = O; t[4, 4] = H
        return t
    if mat in ('stone',):
        t = np.full((8, 8), M, np.uint8)
        t[0, :] = L; t[:, 0] = L; t[7, :] = D; t[:, 7] = D; t[0, 7] = M; t[7, 0] = M
        t[3:5, 3:5] = L if theme != 'ghost' else D
        return t
    if mat in ('wood', 'log', 'beam'):
        t = np.full((8, 8), M, np.uint8)
        t[0, :] = L; t[7, :] = O; t[3, 1:6] = D; t[5, 4:8] = D
        return t
    if mat == 'wallbg':
        t = np.full((8, 8), D, np.uint8)
        t[3, :] = O; t[7, :] = O; t[0:3, 2] = O; t[4:7, 6] = O
        t[1, 3:6] = M; t[5, 0:2] = M
        return t
    if mat in ('column', 'stem', 'trunk'):
        t = np.full((8, 8), M, np.uint8)
        t[:, 1] = L; t[:, 2] = H if mat == 'stem' else L; t[:, 6] = D; t[:, 7] = D
        if mat == 'trunk':
            t[(y + 2 * x) % 9 == 0] = D
        return t
    if mat == 'cap':
        t = np.full((8, 8), M, np.uint8)
        t[K.disc(8, 3.5, 3.5, 2.0)] = H
        t[K.disc(8, 3.0, 3.0, 0.9)] = W
        return t
    return np.full((8, 8), M, np.uint8)


def band_cols(theme, mat):
    """(top line, band 1, band 2) indices for an exposed top surface."""
    if mat != 'ground':
        return (O, H, L)
    return {'castle': (O, H, L), 'ghost': (O, H, L), 'crystal': (O, W, H), 'cave': (O, AC, H)}.get(theme, (O, AC, H))


def render_class(code, theme, mat):
    """Turn an 8x8 class map (0 empty, 1 fill, 2 band1, 3 outline, 4 shade, 5 band2, 6 band-top line)
    into indices."""
    c = np.frombuffer(code, np.uint8).reshape(8, 8)
    t = tex(theme, mat)
    top, b1, b2 = band_cols(theme, mat)
    out = np.where(c == 1, t, 0).astype(np.uint8)
    out[c == 2] = b1
    out[c == 5] = b2
    out[c == 3] = O
    out[c == 4] = D
    out[c == 6] = top
    return out


# ===================================================================== class maps (autotile)
def terrain_block(mask, opn, band=True, slope=False):
    """16x16 class map for a solid mask with open sides (dict u,d,l,r)."""
    m = mask.astype(bool)
    c = np.where(m, 1, 0).astype(np.uint8)
    # exposed top: the first solid pixel of each column, when the column is open above
    for x in range(16):
        ys = np.nonzero(m[:, x])[0]
        if not len(ys):
            continue
        y0 = ys[0]
        if y0 > 0 or opn['u']:
            if band:
                c[y0, x] = 6
                if y0 + 1 < 16 and m[min(y0 + 1, 15), x]: c[y0 + 1, x] = 2
                if y0 + 2 < 16 and m[min(y0 + 2, 15), x]: c[y0 + 2, x] = 2
                if y0 + 3 < 16 and m[min(y0 + 3, 15), x] and (x % 3 != 1): c[y0 + 3, x] = 5
            else:
                c[y0, x] = 3
    if opn['l']:
        col = m[:, 0]
        c[col & (c[:, 0] == 1), 0] = 3
        c[m[:, 1] & (c[:, 1] == 1), 1] = 4
    if opn['r']:
        c[m[:, 15] & (c[:, 15] == 1), 15] = 3
        c[m[:, 14] & (c[:, 14] == 1), 14] = 4
    if opn['d']:
        c[15, m[15, :] & (c[15, :] == 1)] = 3
        c[14, m[14, :] & (c[14, :] == 1)] = 4
    if slope:   # outline the diagonal face below the band for readability
        pass
    return c


def quads(img16):
    return [img16[:8, :8], img16[:8, 8:], img16[8:, :8], img16[8:, 8:]]


# ===================================================================== FG1/FG2 pixel pictures (theme free)
def pic_pipe(part, horizontal=False):
    """Pipe parts drawn for the vertical case; horizontal = transposed. part in
    shaftL, shaftR, endL, endR (lip band in rows 3..12 so it reads at either end)."""
    p = np.zeros((16, 16), np.uint8)
    x = np.arange(16)
    if part in ('shaftL', 'endL'):
        col = np.where(x < 2, O, np.where(x < 4, L, np.where(x < 6, H, np.where(x < 11, L, M))))
        col[0] = O
    else:
        col = np.where(x < 5, M, np.where(x < 10, D, np.where(x < 14, D, O)))
        col[15] = O
        col[12:15] = O if False else col[12:15]
    p[:, :] = col[None, :]
    if part.startswith('shaft'):
        for yy in (3, 11):   # bramble rings
            p[yy, :] = np.where(p[yy, :] == O, O, D)
    else:
        p[2:14, :] = np.where(col[None, :] == O, O, np.minimum(col[None, :] + 0, 7))
        p[2, :] = O; p[13, :] = O
        p[3, :] = np.where(p[3, :] == O, O, H)
        p[12, :] = np.where(p[12, :] == O, O, D)
        p[5:11, :] = np.where(p[5:11, :] == O, O, np.where(p[5:11, :] == D, M, p[5:11, :]))
        if part == 'endL':
            p[2:14, 0] = O
        else:
            p[2:14, 15] = O
    return p.T.copy() if horizontal else p


def pic_cement():
    b = K.block_base()
    b[b == H] = L
    b[5:11, 5:11] = np.where(b[5:11, 5:11] != O, D, O)
    b[6:10, 6:10] = M
    return b


def pic_throw():
    b = K.block_base()
    for k in range(2, 14, 4):
        K.line(b, 2, k, k, 2, D)
    b[7:9, 7:9] = H
    return b


def pic_glass():
    b = np.zeros((16, 16), np.uint8)
    b[0, :] = O; b[15, :] = O; b[:, 0] = O; b[:, 15] = O
    K.line(b, 3, 10, 10, 3, W); K.line(b, 6, 12, 12, 6, L)
    return b


def pic_star_block():
    b = K.block_base()
    m = K.sparkle(16, 7.5, 7.5, 4.5)
    b[m] = W
    return b


def pic_net(opn):
    """Climbing net: diamond lattice, rope border on open sides (transparent between strands)."""
    p = np.zeros((16, 16), np.uint8)
    y, x = np.mgrid[0:16, 0:16]
    lat = ((x + y) % 8 == 0) | ((x - y) % 8 == 0)
    p[lat] = L
    p[((x + y) % 8 == 1) & lat == False] = 0
    knots = ((x + y) % 8 == 0) & ((x - y) % 8 == 0)
    p[knots] = H
    if opn['u']: p[0:2, :] = D; p[0, :] = O
    if opn['d']: p[14:16, :] = D; p[15, :] = O
    if opn['l']: p[:, 0:2] = D; p[:, 0] = O
    if opn['r']: p[:, 14:16] = D; p[:, 15] = O
    return p


def pic_vine():
    p = np.zeros((16, 16), np.uint8)
    for yy in range(16):
        xx = int(7 + 2.5 * np.sin(yy * np.pi / 8))
        p[yy, xx - 1:xx + 2] = M
        p[yy, xx - 1] = O
    for (yy, side) in ((3, -1), (11, 1)):
        xx = int(7 + 2.5 * np.sin(yy * np.pi / 8))
        lf = K.disc(16, xx + side * 4, yy, 2.2)
        p[lf] = L
        p[K.outline(lf)] = O
    return p


def pic_door(top):
    p = np.zeros((16, 16), np.uint8)
    p[:, 1:15] = M
    p[:, 1] = O; p[:, 14] = O
    if top:
        y, x = np.mgrid[0:16, 0:16]
        arch = (x - 7.5) ** 2 + (y - 8) ** 2 > 7.5 ** 2
        p[(y < 8) & arch] = 0
        p[K.outline(p > 0)] = O
        p[6:16, 7:9] = D
    else:
        p[0:15, 7:9] = D
        p[8:10, 11:13] = H
        p[15, 1:15] = O
    for xx in (4, 11):
        p[:, xx] = np.where(p[:, xx] == M, L, p[:, xx])
    return p


def pic_dragon(top):
    """Big coin, two blocks tall: a gold medallion with a leaf."""
    y, x = np.mgrid[0:32, 0:16].astype(float)
    m = ((x - 7.5) / 7.2) ** 2 + ((y - 15.5) / 13.5) ** 2 <= 1
    p = np.where(m, M, 0).astype(np.uint8)
    inner = ((x - 7.5) / 5.0) ** 2 + ((y - 15.5) / 10.5) ** 2 <= 1
    p[inner] = L
    leaf = ((x - 7.5) / 2.5) ** 2 + ((y - 15.5) / 6.5) ** 2 <= 1
    p[leaf] = H
    p[(np.abs(x - 7.5) < 0.6) & (np.abs(y - 15.5) < 7)] = D
    p[K.outline(m)] = O
    return p[:16] if top else p[16:]


def pic_moon():
    p = np.zeros((16, 16), np.uint8)
    m = K.disc(16, 7.5, 7.5, 6.5) & ~K.disc(16, 10.5, 5.5, 5.0)
    p[m] = L
    p[m & K.disc(16, 5, 9, 3)] = H
    p[K.outline(m)] = O
    return p


def pic_berry():
    p = np.zeros((16, 16), np.uint8)
    for (cx, cy) in ((6, 9), (10, 9), (8, 5.5), (8, 11.5)):
        m = K.disc(16, cx, cy, 3.0)
        p[m] = M
    p[K.outline(p > 0)] = O
    for (cx, cy) in ((5, 8), (9, 8), (7, 4.5)):
        p[int(cy), int(cx)] = W
    p[0:3, 7:9] = D
    return p


def pic_bush_eaten():
    p = np.zeros((16, 16), np.uint8)
    m = K.disc(16, 7.5, 12, 5.5) & (np.mgrid[0:16, 0:16][0] >= 7)
    p[m] = M
    p[K.outline(m)] = O
    return p


def pic_shooter(part):
    p = np.zeros((16, 16), np.uint8)
    p[:, 1:15] = D
    p[:, 1] = O; p[:, 14] = O
    if part == 0:   # muzzle: a dark ring
        p[1:15, 1:15] = M
        p[K.ring(16, 7.5, 7.5, 3, 5.5)] = O
        p[K.disc(16, 7.5, 7.5, 3)] = D
        p[0, :] = O
    elif part == 1:
        p[6:10, 2:14] = M
        p[7, 3:13] = L
    else:
        p[2:14, 4:12] = M
        p[15, :] = O
    return p


def pic_post(kind):
    p = np.zeros((16, 16), np.uint8)
    p[:, 6:10] = M; p[:, 6] = O; p[:, 9] = O; p[:, 7] = L
    if kind == 'top':
        p[0:5, 4:12] = L
        p[K.outline(p > 0)] = O
    if kind == 'tape':
        p[6:9, :] = AC; p[6, :] = O; p[8, :] = O
    return p


def pic_line(opn):
    p = np.zeros((16, 16), np.uint8)
    h = not (opn['l'] and opn['r'])
    v = not (opn['u'] and opn['d'])
    if h or not v:
        p[7:9, :] = L; p[7, :] = O
    if v and not h:
        p[:, 7:9] = L; p[:, 7] = O
    return p


def pic_outline():
    p = np.zeros((16, 16), np.uint8)
    for i in range(0, 16, 2):
        p[0, i] = L; p[15, i + 1] = L; p[i, 0] = L; p[i + 1, 15] = L
    y, x = np.mgrid[0:16, 0:16]
    p[(np.abs(x - 7.5) + np.abs(y - 7.5)) <= 3.5] = M
    p[(np.abs(x - 7.5) + np.abs(y - 7.5)) <= 1.5] = L
    return p


def pic_donut():
    p = np.zeros((16, 16), np.uint8)
    m = K.disc(16, 7.5, 7.5, 7) & ~K.disc(16, 7.5, 7.5, 2.5)
    p[m] = M
    p[m & (np.mgrid[0:16, 0:16][0] < 7)] = L
    p[K.outline(m)] = O
    return p


def pic_spike(down=False):
    p = np.zeros((16, 16), np.uint8)
    for cx in (3.5, 11.5):
        for yy in range(16):
            w = (yy + 1) / 4.0
            xs = np.arange(16)
            row = np.abs(xs - cx) <= w
            p[yy, row] = L if yy < 8 else M
    p[14:16, :] = D
    p[K.outline(p > 0)] = O
    return p[::-1] if down else p


def pic_cloud(opn):
    p = np.full((16, 16), W, np.uint8)
    y, x = np.mgrid[0:16, 0:16]
    m = np.ones((16, 16), bool)
    if opn['u']:
        m &= (y >= 3 + 2 * np.cos(x * np.pi / 8) ** 2)
    if opn['d']:
        m &= (y <= 12 - 1.5 * np.sin(x * np.pi / 8) ** 2)
    if opn['l']:
        m &= (x >= 3 + 2 * np.cos(y * np.pi / 8) ** 2)
    if opn['r']:
        m &= (x <= 12 - 2 * np.cos(y * np.pi / 8) ** 2)
    p[~m] = 0
    p[m & (y > 9)] = H
    p[K.outline(m)] = L
    return p


def pic_leaf(opn):
    """Bramble bush / canopy: dark leafy mass with berry-thorn dots; scalloped open edges."""
    y, x = np.mgrid[0:16, 0:16]
    v = K.periodic_noise((16, 16), 77, 16, ((8, 1.0), (4, 0.6), (2, 0.3)))
    p = K.shade(v, [D, M, M, L])
    p[(v > 0.9)] = H
    m = np.ones((16, 16), bool)
    if opn['u']:
        m &= y >= 2 + 3 * np.abs(np.sin(x * np.pi / 6))
    if opn['d']:
        m &= y <= 13
    if opn['l']:
        m &= x >= 2 + 3 * np.abs(np.sin(y * np.pi / 6))
    if opn['r']:
        m &= x <= 13 - 3 * np.abs(np.sin(y * np.pi / 6))
    p[~m] = 0
    p[K.outline(m)] = O
    for (yy, xx) in ((5, 10), (11, 4)):
        if m[yy, xx]:
            p[yy, xx] = AC
    return p


def pic_weed(f=0):
    p = np.zeros((16, 16), np.uint8)
    for k, cx in enumerate((4, 9, 13)):
        for yy in range(16):
            xx = int(cx + 1.5 * np.sin(yy * 0.6 + k))
            if 0 <= xx < 16:
                p[yy, xx] = M if k % 2 else L
    return p


def pic_palace(part):
    """Big switch tiles: a dome button 32x32 split by part (0..3 = TL TR BL BR)."""
    y, x = np.mgrid[0:32, 0:32].astype(float)
    p = np.zeros((32, 32), np.uint8)
    dome = ((x - 15.5) / 13) ** 2 + ((y - 20) / 11) ** 2 <= 1
    p[dome & (y < 22)] = M
    p[dome & (y < 14)] = L
    p[(y >= 22) & (y < 30) & (np.abs(x - 15.5) < 15)] = D
    p[K.outline(p > 0)] = O
    p[K.disc(32, 11, 10, 2.5)] = W
    q = [p[:16, :16], p[:16, 16:], p[16:, :16], p[16:, 16:]][part]
    return q


# ===================================================================== animated frames into kGfx33
V3_PAINTER = {  # kLevelTileAnimations_FrameData entry -> painter(frame); frames come from the kept table
    0: K.prize_frame, 1: K.note_frame, 4: K.turn_frame, 3: lambda f: K.belt_frame(f), 8: lambda f: K.used_frame(),
    9: K.muncher_frame, 12: lambda f: K.lamp_frame(True), 13: K.coin_frame, 14: K.drip_frame,
    15: lambda f: K.liquid_frame(f, 'water'), 21: lambda f: K.liquid_frame(f, 'lava'), 23: K.orb_frame,
    25: lambda f: K.liquid_frame(f, 'water'), 26: lambda f: K.belt_frame(f, rope=True), 29: K.torch_frame,
    30: lambda f: K.liquid_frame(f, 'water'), 31: lambda f: K.liquid_frame(f, 'lava'), 32: K.bubbles_frame,
    35: lambda f: K.liquid_frame(f, 'water'), 36: lambda f: K.liquid_frame(f, 'lava'),
    40: lambda f: K.liquid_frame(f, 'water'), 44: lambda f: K.panel_frame(), 50: lambda f: K.lamp_frame(False),
}


def anim_groups(survey):
    """gfx33 first tile of a 4-tile frame -> (painter, frame number)."""
    G = {}
    for v3, fn in V3_PAINTER.items():
        for f, n in enumerate(survey['anim'][v3]):
            if n >= 0 and n not in G:
                G[n] = (fn, f)
    return G


def build_gfx33(old, survey):
    t = TL.decode(old, 3).copy()
    covered = set()
    for v3 in survey['anim']:
        for n in v3:
            if n >= 0:
                covered |= set(range(n, n + 4))
    for n in covered:          # clear every level-animation tile we own, then paint
        if n < len(t):
            t[n] = 0
    for first, (fn, f) in anim_groups(survey).items():
        img = fn(f)
        for k, q in enumerate([img[:8, :8], img[:8, 8:], img[8:, :8], img[8:, 8:]]):
            if first + k < len(t):
                t[first + k] = q
    # the 1120 / 1124 groups share tiles with the blank 1121 group (377..380 stay clear)
    t[376] = K.track_frame(0)[:8, :8]
    for n in (377, 378, 379, 380):
        t[n] = 0
    for k, q in enumerate(quads(K.track_frame(1))[1:]):
        t[381 + k] = q
    return TL.encode(t, 3)


def static_anim(sheets, gfx33, items):
    """Sheets 14 / 17 also serve as sprite sheets: give the animated VRAM slots their first frame."""
    g = TL.decode(gfx33, 3)
    fd = struct.unpack('<%dH' % (len(items['kLevelTileAnimations_FrameData']) // 2), items['kLevelTileAnimations_FrameData'])
    slots = [(0x60, 0), (0x64, 1), (0x68, 2), (0x74, 3), (0xEA, 4), (0x50, 6), (0x54, 7), (0x58, 8), (0x5C, 9),
             (0x78, 10), (0x7C, 11), (0xDA, 12), (0x6C, 13), (0x70, 14), (0x4C, 15), (0x44, 16), (0x48, 17), (0x40, 18)]
    for dst, v3 in slots:
        n = (fd[v3 * 4] - 0x7D00) // 32
        if n < 0:
            continue
        sh = sheets[0x14] if dst < 0x80 else sheets[0x17]
        for k in range(4):
            sh[(dst + k) & 0x7F] = g[n + k]


# ===================================================================== module entry
MY_SHEETS = (0x07, 0x08, 0x0C, 0x0D, 0x0E, 0x0F, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1F, 0x2C)


def build(items, kept, spec_dir):
    from games.smw import tiles_map16, tiles_bg
    survey = json.load(open(os.path.join(spec_dir, 'tiles.json')))
    out = dict(K.palettes())
    out['kGfx33'] = build_gfx33(items['kGfx33'], survey)
    bld = tiles_map16.Builder(spec_dir)
    m16 = bld.build_map16(items)
    sheets = {}
    sheets.update(bld.fg12_sheets())
    sheets.update(bld.fg3_sheets())
    bg = tiles_bg.build(items, survey, sheets)
    from games.smw import tiles_special
    tiles_special.build(sheets, items, survey, None)
    static_anim(sheets, out['kGfx33'], items)
    out.update(bg['entries'])
    out['kMap16Data'] = m16.pop('kMap16Data') + bg['map16']
    out.update(m16)
    raw = [lz2.decompress(c) for c in A.unpack_array(items['kGraphicsPtrs'])]
    for s, img in sheets.items():
        n = len(raw[s]) // 24
        raw[s] = TL.encode(img[:n], 3)
    arr = A.unpack_array(items['kGraphicsPtrs'])
    for s in sheets:
        arr[s] = lz2.compress(raw[s])
    out['kGraphicsPtrs'] = A.pack_array(arr)
    for k, v in out.items():
        assert len(v) == len(items[k]) or k == 'kGraphicsPtrs' or 'Layer2' in k, (k, len(v), len(items[k]))
    print('tiles: fg1 %d/64 fg2 %d/116 fg3 common %d, components %s, bg %s, overflow %s' % (
        len(bld.st.px['fg1']), len(bld.st.px['fg2']), bld.fg3_common_next,
        {c: 127 - v for c, v in bld.fg3_comp_next.items()}, bg['stats'], dict(bld.st.overflow)))
    return out
