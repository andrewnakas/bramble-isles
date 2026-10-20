"""CLEAN ROOM. The Mode-7 boss pictures: sheets 0x0B (Thornling bosses) and 0x21 (KING GRUMBOLT's
flying bramble pot), and our own arrangement table kInitializeMode7TilemapsAndPalettes_TilemapData.

Structure kept from the code (smw_03.c, UpdateMode7SpriteAnimations / BufferTilemap):
- each sheet tile t becomes Mode-7 tiles 2t (as drawn) and 2t+1 (mirrored); 0xFF (= tile 0x7F mirrored)
  is the blank tile, so sheet tile 0x7F stays empty;
- the table is 57 blocks of 16 bytes; Thornling frames 0..29 are 4x4 tiles (rows of 4); the pot uses rows
  of 8: propeller row at 896 / 904, four face frames at 800..863 (2 rows each), pot body 864..895 (4 rows),
  bottoms at 16 * frame index (4 rows from blocks 30..49);
- the code writes the spinning rotor's first row itself from sheet-21 tiles 0x37-0x3B, 0x28-0x2B, 0x1E,
  0x1F (fixed slots, drawn here as rotor pieces);
- colours: the boss palette (code) gives Mode-7 indices 1 black, 2 dark, 3 mid, 4 light, 5 red-brown,
  6 orange; our drawings are remapped onto those.
Which table blocks are completely empty is kept (the code shows nothing there on purpose).
"""
import numpy as np

from games.smw import spr_cast as C
from games.smw.spr_draw import Fig, WHITE, LINE, LIGHT, MID, DARK, ACC, ACCD, MAIN, ACCENT, ellipse_mask, poly_mask

REMAP = {0: 0, LINE: 1, DARK: 2, MID: 3, LIGHT: 4, ACCD: 5, ACC: 6, WHITE: 4}
ROTOR_SLOTS = [0x37, 0x38, 0x39, 0x3A, 0x3B, 0x28, 0x29, 0x2A, 0x2B, 0x1E, 0x1F]
BLANK = 0x7F


def m7(a):
    out = np.zeros_like(a)
    for k, v in REMAP.items():
        out[a == k] = v
    return out


class Bank:
    """Stores 8x8 tiles into a sheet image, sharing identical and mirrored tiles."""

    def __init__(self, reserved):
        self.img = np.zeros((64, 128), np.uint8)
        self.seen = {np.zeros((8, 8), np.uint8).tobytes(): 2 * BLANK}
        self.free = [t for t in range(128) if t not in reserved and t != BLANK]

    def put_at(self, t, tile):
        self.img[t // 16 * 8:t // 16 * 8 + 8, t % 16 * 8:t % 16 * 8 + 8] = tile

    def add(self, tile):
        k = tile.tobytes()
        if k in self.seen:
            return self.seen[k]
        if not self.free:
            raise RuntimeError('mode-7 sheet full')
        t = self.free.pop(0)
        self.put_at(t, tile)
        self.seen[k] = 2 * t
        self.seen[tile[:, ::-1].tobytes()] = 2 * t + 1
        return 2 * t

    def cells(self, pic):
        h, w = pic.shape
        return [self.add(pic[y:y + 8, x:x + 8].copy()) for y in range(0, h, 8) for x in range(0, w, 8)]


# ------------------------------------------------------------------ Thornling bosses (sheet 0B)
def thorn_boss(boss, pose):
    """32x32 frame, facing left. boss 0/1/2 changes crown and belly, pose 0..8 (our pose list)."""
    F = Fig(32, 32)
    squash = pose == 4
    front = pose in (6, 7, 8)
    ph = [0, 1, 2, 0, 0, 1, 0, 0, 1][pose]
    by = 31
    top = 12 if squash else 4
    # feet
    sw = [0, 2, -2][ph]
    F.ellipse(11 + sw, by - 2, 4, 2.4, (DARK, DARK, DARK))
    F.ellipse(21 - sw, by - 2, 4, 2.4, (DARK, DARK, DARK))
    # body
    F.ellipse(16, by - (6 if squash else 9), 10, 6 if squash else 8, MAIN)
    F.ellipse(15, by - (6 if squash else 8), 5, 4 if squash else 5.5, (ACC, ACC, ACCD))
    # head
    hy = top + 7
    F.ellipse(16 if front else 14, hy, 8, 7, ACCENT)
    if not front:
        F.ellipse(6.5, hy + 1.5, 2.6, 2.2, ACCENT)                          # nose
    # arms
    if pose == 3:
        F.line([(8, by - 13), (4, hy - 4)], 2.2, ACCENT)
        F.line([(24, by - 13), (28, hy - 4)], 2.2, ACCENT)
    elif pose == 5:
        F.line([(8, by - 12), (3, by - 8)], 2.2, ACCENT)
    else:
        F.line([(7, by - 12), (5, by - 7 - ph)], 2.2, ACCENT)
        F.line([(25, by - 12), (27, by - 7 + ph)], 2.2, ACCENT)
    # crown: three kinds of thorns
    y0 = hy - 6
    xs = (10, 16, 22) if front else (9, 14, 19)
    for k, x in enumerate(xs):
        if boss == 0:
            F.poly([(x - 2, y0 + 1), (x + 2, y0 + 1), (x, y0 - 5)], (DARK, DARK, DARK))
        elif boss == 1:
            F.ellipse(x, y0 - 1, 1.8, 3.0, (DARK, DARK, DARK), rot=0.4 * (k - 1))
        else:
            F.poly([(x - 2.5, y0 + 1), (x + 2.5, y0 + 1), (x + 1.5 * (k - 1), y0 - 4), (x, y0 - 2)], (DARK, DARK, DARK))
    if front:
        for ex in (12.5, 19.5):
            F.eye(ex, hy, r=1.8, look=(0, 0))
        F.dline([(13, hy + 4), (19, hy + 4)], LINE)
    else:
        F.eye(10, hy - 1, r=1.8)
        F.dline([(8, hy + 4), (13, hy + 4.5)], LINE)
    if pose == 5:
        F.dmask(ellipse_mask(32, 32, 10, hy - 1, 1.5, 0.6), LINE)
    return F.render()


def thorn_ball(f):
    """Rolled-up Thornling (spin frames)."""
    F = Fig(32, 32)
    F.ellipse(16, 18, 12, 12, MAIN)
    a = f * np.pi / 3
    for k in range(6):
        b = a + k * np.pi / 3
        x, y = 16 + 12 * np.cos(b), 18 + 12 * np.sin(b)
        F.poly([(x - 2, y), (x + 2, y), (16 + 15.5 * np.cos(b), 18 + 15.5 * np.sin(b))], (DARK, DARK, DARK))
    F.ellipse(16, 18, 6, 6, (ACC, ACC, ACCD))
    return F.render()


# ------------------------------------------------------------------ KING GRUMBOLT's pot (sheet 21)
def rotor(width):
    """A rotor blade picture `width` px wide, 8 high (thin bar with rounded ends)."""
    F = Fig(width, 8)
    F.ellipse(width / 2, 4, width / 2 - 0.5, 2.2, (LIGHT, MID, DARK))
    F.ellipse(width / 2, 4, 2.5, 2.5, (ACC, ACC, ACCD))
    return F.render()


def mast():
    F = Fig(64, 8)
    F.rect(29, 0, 35, 8, (MID, MID, DARK))
    F.ellipse(32, 1.5, 5, 1.6, (ACC, ACC, ACCD))
    return F.render()


def face(f):
    """King's face in the pot window, 64x16: f = 0 normal, 1 blink, 2 look left, 3 look right."""
    F = Fig(64, 16)
    F.ellipse(32, 12, 14, 11, ACCENT)
    for k, x in enumerate((24, 32, 40)):
        F.poly([(x - 3, 3), (x + 3, 3), (x, -3 + (k % 2) * 2)], (DARK, DARK, DARK))
    look = [0, 0, -1, 1][f]
    for ex in (26, 38):
        if f == 1:
            F.dline([(ex - 2, 9), (ex + 2, 9)], LINE)
        else:
            F.eye(ex, 9, r=2.4, look=(look, 0))
    F.ellipse(32, 13, 2.4, 2.0, ACCENT)
    return F.render()


def pot_body():
    """64x32: rim and belly of the bramble pot, a leaf crest on the front."""
    F = Fig(64, 32)
    F.ellipse(32, 18, 30, 15, MAIN)
    F.rect(3, 0, 61, 5, (LIGHT, LIGHT, MID))
    for x in range(8, 60, 8):
        F.dline([(x, 7), (x + 4, 30)], DARK)
    F.ellipse(32, 18, 7, 5, (ACC, ACC, ACCD))
    F.eye(28, 17, r=1.6)
    F.eye(36, 17, r=1.6)
    return F.render()


def pot_bottom(v, drop=0):
    """64x32 underside: tapering pot base with v = flame size 0..2, `drop` rows lower."""
    F = Fig(64, 32)
    y = 8 * drop
    F.poly([(4, y), (60, y), (48, y + 14), (16, y + 14)], MAIN)
    F.rect(18, y + 12, 46, y + 16, (DARK, DARK, DARK))
    fl = [4, 9, 15][v]
    for x in (24, 32, 40):
        F.poly([(x - 3, y + 16), (x + 3, y + 16), (x, y + 16 + fl)], (ACC, ACC, ACCD))
    return F.render()


def build(facts):
    """facts = {'bytes', 'blank_blocks'} from the dirty extractor (sprite_struct.json)."""
    out = bytearray(facts['bytes'])
    blank_blocks = set(facts['blank_blocks'])

    # sheet 0B: Thornling frames
    b0 = Bank(set())
    for f in range(30):
        pic = thorn_ball(f - 27) if f >= 27 else thorn_boss(f // 9, f % 9)
        out[f * 16:f * 16 + 16] = bytes(b0.cells(m7(pic)))

    # sheet 21: rotor pieces in their fixed slots
    b1 = Bank(set(ROTOR_SLOTS))
    r48, r32, r16 = m7(rotor(48)), m7(rotor(32)), m7(rotor(16))
    for k, t in enumerate([0x37, 0x38, 0x39, 0x3A, 0x3B]):
        b1.put_at(t, r48[:, k * 8:k * 8 + 8])
    for k, t in enumerate([0x28, 0x29, 0x2A, 0x2B]):
        b1.put_at(t, r32[:, k * 8:k * 8 + 8])
    b1.put_at(0x1E, r16[:, :8])
    b1.put_at(0x1F, r16[:, 8:])
    mast_row = b1.cells(m7(mast()))
    out[896:904] = bytes(mast_row)
    out[904:912] = bytes(b1.cells(m7(mast()[:, ::-1].copy())))
    for f in range(4):
        out[800 + 16 * f:816 + 16 * f] = bytes(b1.cells(m7(face(f))))
    out[864:896] = bytes(b1.cells(m7(pot_body())))
    # bottoms: blocks 30..49 in pairs (32 bytes = 4 rows of 8); fully empty retail blocks stay empty
    for i, blk in enumerate(range(30, 50, 2)):
        rows = bytearray(b1.cells(m7(pot_bottom(i % 3, 1 if blk >= 36 and blk < 46 else 0))))
        for half in (0, 1):
            if blk + half in blank_blocks:
                rows[half * 16:half * 16 + 16] = b'\xff' * 16
        out[blk * 16:blk * 16 + 32] = rows
    for b in blank_blocks:
        out[b * 16:b * 16 + 16] = b'\xff' * 16
    return b0.img, b1.img, bytes(out)
