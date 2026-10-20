"""CLEAN ROOM. Our own overworld art for Bramble Isles: palettes and the three map
sheets (GFX 1C, 1D, 1E), drawn here procedurally and from our own pixel sketches.

Palette rows on the map (structure of the port): area colours = rows 4-7 cols 1-7 (per map),
object colours = rows 2-7 cols 9-15 (GFX 1E/08 tiles get +8), sprite colours = rows 8-15.

Our area rows:
  row 4  sea + coast : 1 deep, 2 sea, 3 foam, 4 sand, 5 grass dark, 6 grass, 7 grass light
  row 5  bridges     : 1 deep, 2 sea, 3 foam, 4 wood dark, 5 wood, 6 wood light, 7 rope
  row 6  island decor: 1 grass dark, 2 grass, 3 grass light, 4 bark, 5 bramble dark, 6 bramble, 7 berry
  row 7  islets      : 1 deep, 2 sea, 3 foam, 4 sand, 5 grass dark, 6 grass, 7 stone
"""
import numpy as np

# ------------------------------------------------------------------ palettes (5-bit RGB, ours)


def bgr(c):
    r, g, b = c
    return int(r) | int(g) << 5 | int(b) << 10


def words(cols):
    return np.array([bgr(c) for c in cols], '<u2').tobytes()


def area_set(sea, sand, grass, wood, bark, bramble, berry, stone):
    """28 colours: rows 4-7, cols 1-7."""
    deep, mid, foam = sea
    gd, gm, gl = grass
    wd, wm, wl, rope = wood
    bd, bm = bramble
    return [deep, mid, foam, sand, gd, gm, gl,
            deep, mid, foam, wd, wm, wl, rope,
            gd, gm, gl, bark, bd, bm, berry,
            deep, mid, foam, sand, gd, gm, stone]


# one set per kGlobalPalettes_OW_Areas slot; slot k is used by the maps whose tileset maps to k
AREAS = [
    # 0: Meadow isle (submap 1): bright teal sea, warm sand
    area_set(((3, 10, 20), (6, 17, 27), (24, 30, 31)), (30, 27, 17), ((7, 17, 6), (12, 24, 8), (20, 29, 12)),
             ((14, 8, 4), (21, 13, 6), (27, 20, 11), (29, 27, 22)), (13, 8, 5), ((5, 13, 9), (9, 20, 12)),
             (29, 8, 14), (21, 21, 22)),
    # 1: Bramble Isles main map: deep blue sea, golden sand, lush green
    area_set(((2, 6, 17), (5, 12, 25), (22, 28, 31)), (31, 26, 14), ((5, 15, 7), (10, 22, 9), (18, 28, 11)),
             ((12, 7, 3), (19, 12, 5), (26, 19, 9), (30, 28, 21)), (12, 7, 4), ((4, 11, 8), (8, 18, 11)),
             (27, 5, 10), (20, 20, 21)),
    # 2: Night sea (submap 6): ink blue, silver sand, blue-green moss
    area_set(((1, 2, 9), (3, 6, 16), (17, 21, 30)), (22, 22, 26), ((3, 10, 10), (6, 16, 14), (11, 23, 19)),
             ((9, 6, 7), (14, 10, 10), (20, 16, 15), (26, 26, 30)), (9, 6, 8), ((3, 8, 10), (6, 13, 14)),
             (24, 20, 31), (17, 17, 22)),
    # 3: Dusk lagoon (submaps 2 and 4): violet-blue water, rose sand, olive grass
    area_set(((4, 3, 13), (8, 7, 21), (25, 22, 31)), (28, 21, 20), ((9, 12, 5), (14, 18, 7), (21, 24, 10)),
             ((13, 7, 6), (19, 11, 8), (25, 17, 12), (29, 25, 23)), (12, 7, 6), ((7, 9, 6), (12, 14, 8)),
             (30, 16, 6), (18, 16, 20)),
    # 4: Fern lake (submap 3): green-teal water, pale sand, deep greens
    area_set(((1, 9, 12), (3, 15, 18), (20, 30, 27)), (27, 26, 18), ((3, 12, 5), (6, 18, 7), (12, 25, 9)),
             ((11, 8, 4), (17, 13, 6), (23, 19, 10), (28, 27, 20)), (10, 7, 4), ((2, 9, 6), (5, 14, 8)),
             (31, 20, 6), (19, 21, 19)),
    # 5: Cloud sea (submap 5): pale sky water, cream sand, mint
    area_set(((9, 15, 27), (15, 21, 30), (29, 31, 31)), (31, 29, 22), ((10, 21, 14), (16, 27, 17), (24, 31, 22)),
             ((16, 10, 9), (23, 16, 13), (29, 23, 19), (31, 30, 27)), (15, 10, 9), ((8, 17, 14), (13, 23, 18)),
             (31, 12, 20), (24, 25, 28)),
]


def autumn(cols):
    """AreasPassed: the same isles after the hidden world is cleared: amber leaves, warmer sea."""
    out = []
    for i, (r, g, b) in enumerate(cols):
        row, k = divmod(i, 7)
        grassy = (row == 0 and k >= 4) or row == 2 or (row == 3 and k in (4, 5))
        if grassy:
            r, g, b = min(31, int(r * 0.6 + g * 0.75 + 3)), int(g * 0.62 + 2), int(b * 0.4)
        elif (row in (0, 1, 3) and k <= 1):
            r, g, b = int(r * 0.8 + 2), int(g * 0.85), min(31, int(b * 0.95 + 1))
        out.append((r, g, b))
    return out


# objects: rows 2-7, cols 9-15 (pixel 1-7 of GFX 1E)
OBJECTS = [
    # row 2: stone keep: outline, stone dark, stone, stone light, roof dark, roof, white
    [(3, 3, 6), (10, 10, 14), (17, 17, 21), (25, 25, 28), (14, 5, 9), (23, 9, 12), (31, 31, 31)],
    # row 3: bright: outline, gold dark, gold, gold light, leaf, sky, white
    [(3, 3, 6), (22, 12, 2), (29, 21, 4), (31, 29, 14), (6, 20, 8), (12, 22, 31), (31, 31, 31)],
    # row 4: timber: outline, wood dark, wood, wood light, teal, teal light, cream
    [(4, 3, 4), (12, 7, 4), (20, 12, 6), (27, 19, 11), (3, 15, 17), (9, 24, 25), (31, 29, 22)],
    # row 5: keep (castle): outline, stone dark, stone, stone light, thorn dark, thorn, banner
    [(3, 3, 6), (11, 10, 14), (18, 17, 21), (26, 25, 27), (6, 12, 6), (11, 19, 8), (29, 8, 12)],
    # row 6: gold berry: outline, leaf dark, leaf, white, FLASH, berry, berry light
    [(4, 3, 5), (5, 12, 5), (9, 20, 7), (31, 31, 29), (31, 26, 6), (27, 17, 3), (31, 29, 16)],
    # row 7: red berry: outline, leaf dark, leaf, white, FLASH, berry, berry light
    [(4, 3, 5), (5, 12, 5), (9, 20, 7), (31, 31, 29), (31, 9, 12), (22, 3, 9), (31, 19, 20)],
]

# OW sprites: rows 8-15 cols 1-7. Row roles follow the sprite art (index use of each row):
#   8 misc  9 lizard  10 hero  11 second hero  12/13 water creatures  14 critters  15 ghosts/clouds
SPRITES = [
    [(31, 31, 31), (3, 2, 6), (17, 10, 5), (30, 24, 6), (31, 30, 22), (29, 22, 15), (12, 26, 28)],
    [(31, 31, 31), (3, 2, 6), (2, 12, 6), (8, 14, 29), (6, 22, 7), (22, 8, 4), (31, 20, 6)],
    [(31, 31, 31), (3, 2, 6), (6, 18, 16), (14, 26, 22), (31, 22, 8), (25, 18, 12), (30, 25, 18)],   # TOBI
    [(31, 31, 31), (3, 2, 6), (19, 9, 23), (28, 18, 30), (12, 28, 30), (25, 18, 12), (30, 25, 18)],  # KIP
    [(31, 31, 31), (3, 2, 6), (4, 16, 22), (8, 22, 27), (14, 27, 30), (22, 30, 31), (28, 31, 31)],
    [(31, 31, 31), (3, 2, 6), (4, 16, 22), (8, 22, 27), (14, 27, 30), (22, 30, 31), (28, 31, 31)],
    [(3, 2, 6), (26, 5, 8), (14, 15, 19), (20, 21, 25), (5, 16, 7), (10, 23, 9), (17, 29, 13)],
    [(3, 2, 6), (9, 8, 13), (13, 12, 17), (17, 16, 21), (21, 20, 25), (25, 24, 28), (31, 31, 31)],
]


def palettes():
    a = [c for s in AREAS for c in s]
    p = [c for s in AREAS for c in autumn(s)]
    return {'kGlobalPalettes_OW_Areas': words(a), 'kGlobalPalettes_OW_AreasPassed': words(p),
            'kGlobalPalettes_OW_Objects': words([c for r in OBJECTS for c in r]),
            'kGlobalPalettes_OW_Sprites': words([c for r in SPRITES for c in r])}


# ------------------------------------------------------------------ pixel helpers


def sketch(rows):
    """Pixel sketch -> index array ('.' = 0, digits = pixel values)."""
    return np.array([[0 if ch in '. ' else int(ch) for ch in r] for r in rows], np.uint8)


def quads(img):
    """16x16 -> TL, TR, BL, BR 8x8 tiles."""
    return img[:8, :8], img[:8, 8:], img[8:, :8], img[8:, 8:]


def hashf(x, y, seed=0):
    v = (x * 374761393 + y * 668265263 + seed * 2147483647) & 0xffffffff
    v = (v ^ (v >> 13)) * 1274126177 & 0xffffffff
    return (v ^ (v >> 16)) / 4294967295.0


def water_px(x, y, seed=0):
    """Our sea texture: deep base, sea-colour wave crests in staggered short arcs."""
    k = (x + 2 * (y // 4)) % 8
    row = y % 4
    if row == 1 and k in (1, 2, 3):
        return 2
    if row == 2 and k in (0, 4):
        return 2
    if hashf(x, y, seed) > 0.985:
        return 3
    return 1


# ------------------------------------------------------------------ coast tiles


def coast_tile(corners, variant=0):
    """8x8 tile of the sea/land edge: land where the bilinear corner field (+ wobble) > 0.5.
    corners = (tl, tr, bl, br) in {0, 1}."""
    tl, tr, bl, br = corners
    t = np.zeros((8, 8), np.uint8)
    for y in range(8):
        for x in range(8):
            u, v = (x + 0.5) / 8, (y + 0.5) / 8
            f = tl * (1 - u) * (1 - v) + tr * u * (1 - v) + bl * (1 - u) * v + br * u * v
            # wobble that vanishes on the tile border so neighbours join
            w = 0.10 * np.sin(6.0 * u + 4.0 * v + variant * 1.7) * np.sin(np.pi * u) * np.sin(np.pi * v)
            f += w
            if f > 0.66:
                g = hashf(x, y, 11 + variant)
                t[y, x] = 7 if g > 0.86 else (5 if g < 0.12 else 6)
            elif f > 0.5:
                t[y, x] = 4
            elif f > 0.40:
                t[y, x] = 3
            else:
                t[y, x] = water_px(x, y, variant)
    return t


def grass_tile(variant):
    t = np.full((8, 8), 6, np.uint8)
    for y in range(8):
        for x in range(8):
            g = hashf(x, y, 40 + variant)
            if g > 0.9:
                t[y, x] = 7
            elif g < 0.1:
                t[y, x] = 5
    if variant == 2:      # small tuft
        t[5, 2] = t[4, 3] = 5
        t[5, 4] = 5
    if variant == 3:      # tiny flowers (sand colour as petals)
        t[2, 5] = 4
        t[5, 1] = 4
    return t


# ------------------------------------------------------------------ bridges (row 5)


def bridge_h():
    """16x16 plank bridge running left-right over the sea (rows 0..15)."""
    img = np.zeros((16, 16), np.uint8)
    for y in range(16):
        for x in range(16):
            img[y, x] = water_px(x, y, 3)
    for x in range(16):
        img[3, x] = 7                     # rope rail
        img[12, x] = 7
        for y in range(4, 12):
            img[y, x] = 6 if x % 4 != 3 else 4
        img[4, x] = 6 if x % 4 != 3 else 4
        img[11, x] = 4
    for x in (1, 9):                      # posts
        img[2, x] = img[13, x] = 4
    return img


def bridge_corner():
    """16x16 bridge turning between the bottom and the right edge (DR corner)."""
    img = np.zeros((16, 16), np.uint8)
    for y in range(16):
        for x in range(16):
            img[y, x] = water_px(x, y, 5)
    cx, cy = 16.0, 16.0                   # arc centre = bottom-right corner
    for y in range(16):
        for x in range(16):
            r = np.hypot(x + 0.5 - cx, y + 0.5 - cy)
            if 3.5 <= r <= 4.5 or 11.5 <= r <= 12.5:
                img[y, x] = 7
            elif 4.5 < r < 11.5:
                a = np.degrees(np.arctan2(cy - y - 0.5, cx - x - 0.5))
                img[y, x] = 4 if int(a // 11) % 3 == 2 or r > 10.6 else 6
    return img


def stones():
    """Stepping stones over the sea (hard-wired paths), row 7."""
    img = np.zeros((16, 16), np.uint8)
    for y in range(16):
        for x in range(16):
            img[y, x] = water_px(x, y, 9)
    for cx, cy, r in ((4.5, 5.0, 3.2), (11.5, 11.0, 3.2), (11.0, 3.5, 2.2), (4.0, 12.0, 2.2)):
        for y in range(16):
            for x in range(16):
                d = np.hypot(x + 0.5 - cx, y + 0.5 - cy)
                if d < r - 0.8:
                    img[y, x] = 7 if (x + y) % 5 else 4
                elif d < r:
                    img[y, x] = 3
    return img


def islet():
    """16x16 rounded islet a node stands on (row 7): sand rim, grass top, foam ring."""
    img = np.zeros((16, 16), np.uint8)
    for y in range(16):
        for x in range(16):
            dx, dy = abs(x + 0.5 - 8), abs(y + 0.5 - 8)
            d = (dx ** 2.6 + dy ** 2.6) ** (1 / 2.6)
            if d < 5.4:
                img[y, x] = 6 if hashf(x, y, 77) > 0.15 else 5
            elif d < 7.2:
                img[y, x] = 4
            elif d < 7.9:
                img[y, x] = 3
            else:
                img[y, x] = water_px(x, y, 13)
    return img


# ------------------------------------------------------------------ island decor (row 6, on grass)
DECOR = {
    'bush': [
        "2222222222222222",
        "2222255555522222",
        "2225566666655222",
        "2256667666665522",
        "2256766676666522",
        "2566666766766652",
        "2566766666667652",
        "2566666676666652",
        "2556766666676552",
        "2255666766665522",
        "2225556666555222",
        "2222255555222122",
        "2222222442222112",
        "2122222442221122",
        "2112222222211222",
        "2222222222222222"],
    'mound': [
        "2222222222222222",
        "2222222222222222",
        "2222222333222222",
        "2222223333332222",
        "2222233322333222",
        "2222333222233322",
        "2223332222223332",
        "2233322222222332",
        "2333222222222232",
        "2332222222222222",
        "1222222222222221",
        "1122222222222211",
        "2111222222221112",
        "2221111111111222",
        "2222222222222222",
        "2222222222222222"],
    'rock': [
        "2222222222222222",
        "2222222222222222",
        "2222222222222222",
        "2222224444222222",
        "2222443333442222",
        "2224333333334222",
        "2243333334433422",
        "2243333443333422",
        "2243344333333422",
        "2224333333334222",
        "2222444444442222",
        "2222111111112222",
        "2222222222222222",
        "2222222222222222",
        "2222222222222222",
        "2222222222222222"],
    'bramble': [
        "2222222222222222",
        "2222522225222222",
        "2225652256522222",
        "2256765567652222",
        "2225656656565222",
        "2222565666765222",
        "2255656765652522",
        "2567665656565652",
        "2256566765676522",
        "2225656656565222",
        "2222565565652222",
        "2222255225522222",
        "2221111111111222",
        "2222222222222222",
        "2222222222222222",
        "2222222222222222"],
    'flowers': [
        "2222222222222222",
        "2272222222222222",
        "2777222222272222",
        "2272222222777222",
        "2212222222272222",
        "2222222222212222",
        "2222222722222222",
        "2222227772222222",
        "2222222722222222",
        "2222222122222722",
        "2722222222227772",
        "7772222222222722",
        "2722222222222122",
        "2122222722222222",
        "2222227772222222",
        "2222222122222222"],
}

# ------------------------------------------------------------------ node icons (GFX 1E, objects palette)
# pixel values 1..7 = object colours of the row named in ICON_ROW (overworld.py uses the rows)
ICONS = {
    # 4-fold symmetric berries: the drawn tile is the bottom-left quadrant (map16 mirrors it)
    'berry_small_q': [
        "........",
        "........",
        "........",
        "......11",
        ".....166",
        ".....165",
        "......11",
        "........"],
    'berry_big_q': [
        "......11",
        "....1176",
        "...17665",
        "..176655",
        "..165544",
        "...16554",
        "....1165",
        "......11"],
    'keep': [               # thorn keep (castle), row 5
        "....1.1..1.1....",
        "....131..131....",
        "...1331111331...",
        "...1333333331...",
        "...1323223231...",
        "...1333773331...",
        "...1322772231...",
        "..113333333311..",
        ".16134444443161.",
        ".16133322333161.",
        "..1133211233311.",
        "..1332111123331.",
        "..1332111123331.",
        "...15566665551..",
        "....11111111....",
        "................"],
    'tower': [              # stone watch tower (fortress), row 2
        "................",
        ".....1.11.1.....",
        ".....1311131....",
        ".....13333331...",
        "......133331....",
        "......155651....",
        "......156651....",
        "......133331....",
        "......132231....",
        "......133331....",
        ".....13322331...",
        ".....13211231...",
        ".....13211231...",
        "....1333333331..",
        "....1111111111..",
        "................"],
    'ruin': [               # fallen keep, row 2
        "................",
        "................",
        "................",
        "................",
        "......1.........",
        ".....131........",
        "....1331...1....",
        "....13331.131...",
        "...1323331331...",
        "...1333333331...",
        "..133223333231..",
        "..132112332231..",
        ".13333333333331.",
        ".11111111111111.",
        "................",
        "................"],
    'hut': [                # crooked hut (ghost house), row 4
        "................",
        "......1111......",
        "....11555511....",
        "...1556666551...",
        "..155666666551..",
        ".11111111111111.",
        "..1333333332231.",
        "..1323777332331.",
        "..1323777333331.",
        "..1333333311331.",
        "..1332223311331.",
        "..1332223311331.",
        "..1333333311331.",
        "..1111111111111.",
        "................",
        "................"],
    'home': [               # ZEEP's round home, row 3
        "................",
        "......1111......",
        "....11555511....",
        "...1555555551...",
        "..155544445551..",
        "..155444444551..",
        ".11111111111111.",
        "..1777777777771.",
        "..1772277737771.",
        "..1772277737771.",
        "..1777777333771.",
        "..1772217333771.",
        "..1772217777771.",
        "..1111111111111.",
        "................",
        "................"],
    'star': [               # wishing star, row 6 (static tiles 0x48/0x49 top, 0x78/0x79 bottom)
        "................",
        ".......11.......",
        "......1771......",
        "......1761......",
        ".....176651.....",
        "1111117666111111",
        "1777776655566661",
        ".1766665555661..",
        "..11665555511...",
        "...1665555661...",
        "...166511566....",
        "..1665111.1661..",
        "..1661....1661..",
        ".1661......1661.",
        ".111........111.",
        "................"],
    'log': [                # hollow-log warp, row 5 (left half, mirrored)
        "........",
        "........",
        "........",
        "....1111",
        "..113333",
        ".1332222",
        ".1321111",
        "13211111",
        "13211111",
        "13211111",
        ".1321111",
        ".1332222",
        "..113333",
        "....1111",
        "........",
        "........"],
    'shrine': [             # switch shrine (GFX 1D, area row 7 / 5): left half, mirrored
        "........",
        "......11",
        "....1166",
        "...16666",
        "..166555",
        "..165555",
        ".1111111",
        "..144444",
        "..146664",
        "..146664",
        "..146664",
        "..146664",
        "..144444",
        ".1111111",
        "........",
        "........"],
    'shrine_pressed': [     # pressed shrine (left half, mirrored), row 3
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "........",
        "....1111",
        "..112222",
        ".1222333",
        ".1111111",
        "..144444",
        "..111111",
        "........"],
    'gate': [               # thorn gate (left half), row 2
        "........",
        "....1111",
        "...13333",
        "..133222",
        "..132111",
        ".1321111",
        ".1321111",
        ".1321111",
        ".1321155",
        ".1321155",
        ".1321111",
        ".1321111",
        ".1321111",
        ".1333333",
        ".1111111",
        "........"],
    'door': [               # cave door (static 0x42/0x43 top, 0x52/0x53 bottom), row 4
        "................",
        "......1111......",
        "....11333311....",
        "...1332222331...",
        "..132211112231..",
        "..132111111231..",
        ".13211111111231.",
        ".13211111111231.",
        ".13211111111231.",
        ".13211111111231.",
        ".13211111111231.",
        ".13211111111231.",
        ".13333333333331.",
        ".11111111111111.",
        "................",
        "................"],
    'ladder': [             # rope ladder (static 0x26/0x27/0x36/0x37), row 4
        "....1......1....",
        "...131....131...",
        "...1311111131...",
        "...1333333331...",
        "...1311111131...",
        "...131....131...",
        "...1311111131...",
        "...1333333331...",
        "...1311111131...",
        "...131....131...",
        "...1311111131...",
        "...1333333331...",
        "...1311111131...",
        "...131....131...",
        "....1......1....",
        "................"],
    'boulder': [            # thorny boulder (static 0x02/0x03/0x12/0x13), rows 6/7
        "................",
        "................",
        ".......1........",
        "......121.......",
        "....11666111....",
        "...16677666 1...",
        "..1667766665 1..",
        "..1667666655 1..",
        ".216666665551 2.",
        "..166666555521..",
        "..1666555522 1..",
        "...1155552211...",
        "....11222211....",
        "......1111......",
        "................",
        "................"],
    'sign': [               # signpost board, row 4 (digit drawn in by overworld)
        "................",
        "..111111111111..",
        ".17777777777771.",
        ".17777777777771.",
        ".17777777777771.",
        ".17777777777771.",
        ".17777777777771.",
        ".17777777777771.",
        "..111111111111..",
        "......1331......",
        "......1321......",
        "......1321......",
        "......1321......",
        ".....133331.....",
        "....11111111....",
        "................"],
    'post': [               # low marker (static 0x10/0x11 bottom), row 4
        "........",
        "........",
        ".1111111",
        "17777777",
        "17777777",
        ".1111111",
        "......13",
        "......11"],
}

DIGITS = {
    '3': ["111", "..1", ".11", "..1", "111"],
    '4': ["1.1", "1.1", "111", "..1", "..1"],
    '5': ["111", "1..", "111", "..1", "111"],
}


def berry_quadrant(r):
    """Bottom-left quadrant of a 4-fold symmetric berry of radius r centred on the 16x16 cell:
    dark rim, berry body, a light ring, and a core in the flashing colour (5)."""
    q = np.zeros((8, 8), np.uint8)
    for y in range(8):
        for x in range(8):
            d = np.hypot(x + 0.5 - 8, y + 0.5)
            if d < r * 0.38:
                q[y, x] = 5
            elif d < r * 0.62:
                q[y, x] = 7
            elif d < r - 1.0:
                q[y, x] = 6
            elif d < r:
                q[y, x] = 1
    return q


def icon(name):
    if name == 'berry_small_q':
        return berry_quadrant(4.8)
    if name == 'berry_big_q':
        return berry_quadrant(6.9)
    a = sketch(ICONS[name])
    return a


def sign_with(d):
    a = icon('sign').copy()
    g = DIGITS[d]
    for y, r in enumerate(g):
        for x, ch in enumerate(r):
            if ch == '1':
                a[2 + y, 6 + x] = 1
    return a


def mirror_half(h):
    """Left half 16x8 -> full 16x16 symmetric icon."""
    return np.concatenate([h, h[:, ::-1]], axis=1)
