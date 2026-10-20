"""CLEAN ROOM. Our own palettes for the sprite side of Bramble Isles.

Values are picked here in 5-bit components (not a 3-bit rebuild of anything). Row roles kept from the
game's structure: which sprite row is the grey / yellow / blue / red / green family (behaviour depends
on it, e.g. the four ZEEP colours), the layer-3 palettes' light / dark / colour slots, the player's
four sets (TOBI, KIP, TOBI ember, KIP ember).

3bpp sprite rows (cols 2..7): outline, light, mid, dark, accent light, accent dark (spr_draw constants).
"""
import numpy as np


def rgb(r, g, b):
    return r | g << 5 | b << 10


def words(cols):
    return np.array([rgb(*c) for c in cols], '<u2').tobytes()


def ramp(light, mid, dark, acc=(30, 26, 18), accd=(22, 12, 6), line=(3, 2, 6)):
    return [line, light, mid, dark, acc, accd]


# sprite rows 8..13 (inside kGlobalPalettes_Objects, entries 24..59)
ROW8 = [(3, 2, 6), (17, 9, 4), (26, 17, 9), (31, 24, 17), (31, 31, 31), (31, 31, 31)]      # outline, boot brown, tan, skin
ROWS_9_13 = [
    ramp((27, 28, 29), (19, 20, 23), (11, 12, 16), acc=(31, 22, 10), accd=(24, 6, 4)),       # 9 stone grey
    ramp((31, 30, 12), (30, 22, 4), (22, 12, 2), acc=(31, 31, 24), accd=(17, 7, 3)),         # A amber
    ramp((16, 24, 31), (7, 14, 29), (4, 6, 18), acc=(31, 27, 16), accd=(22, 11, 4)),         # B sky blue
    ramp((31, 16, 13), (27, 6, 6), (16, 2, 5), acc=(31, 27, 16), accd=(22, 11, 4)),          # C berry red
    ramp((17, 30, 12), (6, 22, 7), (2, 12, 6), acc=(31, 27, 16), accd=(22, 11, 4)),          # D leaf green
]

# kGlobalPalettes_Sprites: 7 settings x 2 rows (rows 14, 15) x 6 colours
SPRITE_SETS = [
    ramp((24, 22, 18), (16, 14, 11), (9, 7, 6)),                                    # bark
    ramp((20, 28, 22), (11, 21, 16), (5, 12, 10), acc=(30, 10, 8), line=(4, 7, 6)),  # moss
    ramp((31, 31, 31), (24, 27, 31), (14, 18, 26), acc=(10, 13, 26), accd=(4, 6, 14)),  # frost
    ramp((31, 18, 26), (25, 8, 20), (15, 3, 12), acc=(31, 24, 8), accd=(22, 12, 2)),  # plum
    ramp((24, 22, 18), (16, 14, 11), (9, 7, 6)),                                    # bark
    ramp((30, 27, 20), (24, 19, 13), (16, 11, 8), acc=(18, 8, 6)),                  # sand
    ramp((14, 18, 30), (10, 24, 14), (29, 10, 16), acc=(30, 26, 10), accd=(18, 22, 30)),  # festival
    ramp((18, 16, 12), (12, 12, 10), (6, 6, 8), acc=(16, 10, 8), accd=(10, 10, 12), line=(14, 12, 8)),  # dusk
    ramp((8, 24, 24), (4, 16, 17), (2, 8, 10), acc=(26, 8, 4), accd=(30, 20, 6)),    # deep teal
    ramp((26, 26, 27), (18, 18, 20), (11, 11, 13), acc=(26, 10, 4), accd=(30, 20, 6)),  # slate
    ramp((26, 28, 31), (18, 22, 30), (12, 15, 24), acc=(29, 29, 31), accd=(28, 4, 8)),  # pale blue
    ramp((26, 26, 27), (18, 18, 20), (11, 11, 13), acc=(30, 30, 30), accd=(28, 4, 8)),  # slate 2
    ramp((31, 27, 26), (31, 22, 24), (28, 16, 22), acc=(24, 20, 30), accd=(28, 4, 8)),  # blossom
    ramp((28, 31, 31), (24, 30, 31), (18, 26, 29), acc=(30, 31, 31), accd=(31, 31, 31)),  # mist
]

# ZEEP berry rows (cols 9..15): white, outline, leaf, berry light -> dark (red, pink, green berries)
BERRY = [
    [(31, 31, 31), (3, 2, 6), (6, 20, 6), (31, 20, 16), (30, 10, 8), (24, 4, 6), (14, 2, 4)],
    [(31, 31, 31), (3, 2, 6), (6, 20, 6), (31, 24, 30), (30, 14, 24), (24, 8, 20), (14, 4, 12)],
    [(31, 31, 31), (3, 2, 6), (6, 20, 6), (22, 31, 14), (12, 26, 8), (6, 18, 6), (3, 10, 4)],
]

# player row 8, cols 6..15:
#  6 skin shade, 7 hood light, 8 hood mid, 9 hood dark, 10 scarf light, 11 scarf dark,
#  12 tunic light, 13 tunic dark, 14 eye / dark detail, 15 gold highlight
PLAYER = [
    [(25, 18, 12), (14, 26, 22), (6, 18, 16), (3, 10, 10), (31, 22, 8), (27, 10, 4), (31, 29, 22), (23, 19, 13), (4, 3, 8), (31, 30, 10)],   # TOBI
    [(25, 18, 12), (28, 18, 30), (19, 9, 23), (10, 4, 14), (12, 28, 30), (4, 16, 24), (31, 29, 22), (23, 19, 13), (4, 3, 8), (31, 30, 10)],  # KIP
    [(25, 18, 12), (31, 31, 28), (26, 25, 22), (16, 15, 13), (31, 12, 4), (20, 4, 2), (31, 26, 12), (27, 16, 4), (4, 3, 8), (31, 30, 10)],  # TOBI ember
    [(25, 18, 12), (31, 31, 28), (26, 25, 22), (16, 15, 13), (31, 12, 4), (20, 4, 2), (20, 28, 31), (9, 18, 27), (4, 3, 8), (31, 30, 10)],   # KIP ember
]

# layer 3: palettes 2, 3, 6, 7 (4 colours each; colour 0 is transparent)
LAYER3 = [(0, 0, 0), (2, 2, 5), (19, 10, 5), (8, 25, 10),
          (0, 0, 0), (2, 2, 5), (31, 31, 30), (30, 8, 9),
          (0, 0, 0), (2, 2, 5), (7, 13, 30), (31, 31, 30),
          (0, 0, 0), (2, 2, 5), (27, 19, 10), (31, 27, 8)]
LAYER3_SMASHER = [(0, 0, 0), (2, 2, 5), (17, 10, 5), (27, 20, 10)]


def bowser_set(n):
    """The final boss's dynamic colour table: our own ramps (stone, thorn green, ember)."""
    base = [(29, 29, 27), (4, 4, 6), (26, 22, 14), (12, 22, 8), (8, 15, 6), (22, 6, 4), (30, 18, 6), (26, 26, 30)]
    out = []
    for i in range(n):
        r, g, b = base[i % 8]
        k = i // 8
        f = max(0.25, 1.0 - 0.12 * k)
        out.append((int(r * f), int(g * f), int(b * f)))
    return out


def build(items):
    out = {}
    obj = bytearray(items['kGlobalPalettes_Objects'])
    cols = ROW8 + [c for r in ROWS_9_13 for c in r]
    obj[24 * 2:60 * 2] = words(cols)
    out['kGlobalPalettes_Objects'] = bytes(obj)
    sp = [c for r in SPRITE_SETS for c in r]
    assert len(sp) * 2 == len(items['kGlobalPalettes_Sprites'])
    out['kGlobalPalettes_Sprites'] = words(sp)
    out['kGlobalPalettes_YoshiBerry'] = words([c for r in BERRY for c in r])
    out['kPlayerPalettes'] = words([c for r in PLAYER for c in r])
    out['kGlobalPalettes_Layer3'] = words(LAYER3)
    out['kGlobalPalettes_Layer3Smasher'] = words(LAYER3_SMASHER)
    n = len(items['kGlobalPalettes_Bowser']) // 2
    out['kGlobalPalettes_Bowser'] = words(bowser_set(n))
    for k, v in out.items():
        assert len(v) == len(items[k]), k
    return out
