"""CLEAN ROOM. The Bramble Isles cast, drawn by code (spr_draw kit, 3bpp sprite palette convention).

Every function returns an index array of the requested size, figure facing LEFT (the game mirrors
for right). `f` is the animation frame, `rng` a numpy Generator for per-slot variety.
Designs (ours): Burrbugs (domed beetle walkers whose shell can be kicked), Pipkins (seed walkers with a
leaf sprout), Moths and Flaplings (fliers), Snapbuds (one-eyed bud plants), Wisps (teardrop ghosts),
Thornshots (acorn missiles), Urchins (spiky balls), Finnows (fish), Thornlings (KING GRUMBOLT's crew).
Items: sprout berry (grow), ember bud (fire), glider leaf (cape), spark gem (star), life acorn (1-up),
ring coins, leaf key, coil spring, press pad.
"""
import numpy as np
from games.smw.spr_draw import (Fig, WHITE, LINE, LIGHT, MID, DARK, ACC, ACCD, MAIN, ACCENT, PALE,
                                ellipse_mask, poly_mask, line_mask, rect_mask, grow, shrink, fit)


def _feet(F, cx, by, spread, f, ramp=ACCENT, r=1.6):
    ph = [0, 1, 0, -1][f % 4]
    F.ellipse(cx - spread + ph * 0.8, by - r, r * 1.3, r, ramp)
    F.ellipse(cx + spread - ph * 0.8, by - r, r * 1.3, r, ramp)


# ------------------------------------------------------------------ walkers
def pipkin(w, h, f=0, rng=None):
    """Seed-shaped walker with a two-leaf sprout and a single big eye."""
    F = Fig(w, h)
    s = min(w, h)
    cx, by = w / 2, h - 0.5
    bh = s * 0.62
    _feet(F, cx, by, s * 0.22, f)
    F.ellipse(cx, by - bh * 0.62, s * 0.40, bh * 0.52, MAIN)
    top = by - bh * 1.12
    sway = [0, 0.8, 0, -0.8][f % 4]
    F.line([(cx, top + 2), (cx + sway, top)], 0.9, DARK)
    F.ellipse(cx - 2 + sway, top, 2.0, 1.0, (ACC, ACC, ACCD), rot=0.5)
    F.ellipse(cx + 2 + sway, top - 0.5, 2.0, 1.0, (ACC, ACC, ACCD), rot=-0.5)
    F.eye(cx - s * 0.12, by - bh * 0.62, r=max(1.3, s * 0.13))
    F.dline([(cx - s * 0.25, by - bh * 0.30), (cx - s * 0.05, by - bh * 0.25)], DARK)
    return F.render()


def burrbug(w, h, f=0, rng=None):
    """Upright beetle: dome shell on its back, round head with antenna, stubby legs."""
    F = Fig(w, h)
    cx = w * 0.55
    by = h - 0.5
    sh = h * 0.42
    _feet(F, cx, by, w * 0.18, f, r=1.5)
    F.ellipse(cx + w * 0.10, by - sh * 0.9, w * 0.34, sh * 0.62, MAIN)                 # shell
    F.line([(cx - w * 0.15, by - sh * 0.95), (cx + w * 0.38, by - sh * 0.75)], 0.6, DARK)
    hy = by - sh * 1.55
    F.ellipse(cx - w * 0.18, hy, w * 0.24, h * 0.17, ACCENT)                            # head
    F.line([(cx - w * 0.15, hy - h * 0.15), (cx - w * 0.30, hy - h * 0.25)], 0.7, ACCD)
    F.eye(cx - w * 0.27, hy, r=max(1.2, w * 0.09))
    return F.render()


def shell(w, h, f=0, rng=None):
    """Burrbug shell alone (spinning frames turn the ridge)."""
    F = Fig(w, h)
    cx, cy = w / 2, h * 0.58
    F.ellipse(cx, cy, w * 0.44, h * 0.36, MAIN)
    F.rect(1, cy + h * 0.12, w - 1, cy + h * 0.2, ACCENT)
    ph = (f % 4) / 4.0
    for k in range(3):
        x = 2 + ((k / 3.0 + ph) % 1.0) * (w - 4)
        F.dline([(x, cy - h * 0.25), (x - 1, cy + h * 0.05)], DARK)
    F.px(cx - w * 0.2, cy - h * 0.2, WHITE)
    return F.render()


def thornling(w, h, f=0, rng=None, crown=True):
    """KING GRUMBOLT's crew: stocky goblin with a thorn crown, big nose and tiny arms."""
    F = Fig(w, h)
    cx, by = w / 2, h - 0.5
    _feet(F, cx, by, w * 0.18, f, ramp=MAIN, r=max(1.4, h * 0.06))
    F.ellipse(cx, by - h * 0.32, w * 0.34, h * 0.24, MAIN)                     # body
    F.ellipse(cx + 0.5, by - h * 0.28, w * 0.18, h * 0.14, PALE)               # belly
    hy = by - h * 0.66
    F.ellipse(cx, hy, w * 0.30, h * 0.20, ACCENT)                              # head
    F.ellipse(cx - w * 0.28, hy + h * 0.04, w * 0.10, h * 0.07, ACCENT)        # nose
    arm = [0.5, -0.5][f % 2]
    F.line([(cx - w * 0.30, by - h * 0.38), (cx - w * 0.44, by - h * (0.30 + 0.06 * arm))], 1.1, ACCENT)
    if crown:
        y0 = hy - h * 0.17
        for k in range(3):
            x = cx - w * 0.18 + k * w * 0.18
            F.poly([(x - 1.5, y0 + 1), (x + 1.5, y0 + 1), (x, y0 - h * 0.12)], (DARK, DARK, DARK))
    F.eye(cx - w * 0.10, hy - 0.5, r=max(1.2, w * 0.08))
    F.dline([(cx - w * 0.18, hy + h * 0.10), (cx, hy + h * 0.11)], LINE)
    return F.render()


# ------------------------------------------------------------------ fliers / swimmers / ghosts
def moth(w, h, f=0, rng=None):
    F = Fig(w, h)
    cx, cy = w / 2, h * 0.55
    up = f % 2 == 0
    for side in (-1, 1):
        tip = (cx + side * w * 0.46, cy - h * (0.42 if up else -0.05))
        F.poly([(cx, cy - 1), tip, (cx + side * w * 0.30, cy + h * (0.15 if up else 0.35))], (ACC, ACC, ACCD))
    F.ellipse(cx, cy, w * 0.16, h * 0.30, MAIN)
    F.eye(cx - w * 0.06, cy - h * 0.12, r=max(1.0, w * 0.07))
    return F.render()


def flapling(w, h, f=0, rng=None):
    """Round flier with a beak and one wing."""
    F = Fig(w, h)
    cx, cy = w * 0.55, h * 0.58
    up = f % 2 == 0
    F.ellipse(cx, cy, w * 0.34, h * 0.30, MAIN)
    F.poly([(cx - w * 0.30, cy - 1), (cx - w * 0.50, cy + 1), (cx - w * 0.30, cy + 2)], ACCENT)
    F.poly([(cx + w * 0.05, cy - 1), (cx + w * 0.45, cy - h * (0.45 if up else -0.2)), (cx + w * 0.35, cy + 2)], PALE)
    F.eye(cx - w * 0.12, cy - h * 0.08, r=max(1.0, w * 0.08))
    return F.render()


def wisp(w, h, f=0, rng=None):
    """Teardrop ghost with a curled tail and hollow eyes."""
    F = Fig(w, h)
    cx, cy = w * 0.45, h * 0.45
    F.ellipse(cx, cy, w * 0.36, h * 0.34, PALE)
    sw = [1, -1][f % 2]
    F.poly([(cx + w * 0.10, cy), (cx + w * 0.46, cy + h * 0.30 + sw), (cx + w * 0.20, cy + h * 0.32)], PALE)
    for dx in (-0.16, 0.06):
        F.dmask(ellipse_mask(w, h, cx + w * dx, cy - h * 0.05, max(0.8, w * 0.06), max(1.0, h * 0.10)), LINE)
    F.dline([(cx - w * 0.12, cy + h * 0.16), (cx + w * 0.02, cy + h * 0.14)], DARK)
    return F.render()


def finnow(w, h, f=0, rng=None):
    F = Fig(w, h)
    cx, cy = w * 0.45, h / 2
    t = [1, -1][f % 2]
    F.poly([(cx + w * 0.25, cy), (w - 0.5, cy - h * 0.30 + t), (w - 0.5, cy + h * 0.30 + t)], ACCENT)
    F.ellipse(cx, cy, w * 0.36, h * 0.30, MAIN)
    F.poly([(cx - 1, cy - h * 0.25), (cx + 3, cy - h * 0.45), (cx + 3, cy - h * 0.2)], ACCENT)
    F.eye(cx - w * 0.18, cy - 1, r=max(1.1, w * 0.08))
    return F.render()


def snapbud(w, h, f=0, rng=None):
    """One-eyed bud on a stem with two leaves; frames open/close the petals."""
    F = Fig(w, h)
    cx = w / 2
    F.line([(cx, h - 0.5), (cx, h * 0.45)], max(1.0, w * 0.08), DARK)
    F.ellipse(cx - w * 0.22, h * 0.78, w * 0.20, h * 0.08, ACCENT, rot=-0.4)
    F.ellipse(cx + w * 0.22, h * 0.70, w * 0.20, h * 0.08, ACCENT, rot=0.4)
    open_ = f % 2
    hy = h * 0.32
    F.ellipse(cx, hy, w * 0.34, h * 0.26, MAIN)
    if open_:
        F.cut(poly_mask(w, h, [(cx - 1, hy - h * 0.36), (cx + 1, hy - h * 0.36), (cx, hy - h * 0.12)]))
    F.eye(cx, hy, r=max(1.2, w * 0.12), look=(0, 0))
    return F.render()


def urchin(w, h, f=0, rng=None):
    F = Fig(w, h)
    cx, cy = w / 2, h / 2
    n = 8
    r0, r1 = min(w, h) * 0.30, min(w, h) * 0.48
    pts = []
    for k in range(n * 2):
        a = k * np.pi / n + (f % 2) * np.pi / n / 2
        r = r1 if k % 2 == 0 else r0
        pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    F.poly(pts, (DARK, DARK, DARK))
    F.ellipse(cx, cy, r0, r0, MAIN)
    F.eye(cx - r0 * 0.35, cy - 0.5, r=max(1.0, r0 * 0.30))
    return F.render()


def thornshot(w, h, f=0, rng=None):
    """Acorn missile with a cap, eye and a stub of flame at the back."""
    F = Fig(w, h)
    cy = h / 2
    F.poly([(w * 0.70, cy - h * 0.25), (w - 0.5, cy - h * 0.38 - (f % 2)), (w - 0.5, cy + h * 0.38 + (f % 2)), (w * 0.70, cy + h * 0.25)], ACCENT)
    F.ellipse(w * 0.42, cy, w * 0.40, h * 0.36, MAIN)
    F.ellipse(w * 0.62, cy, w * 0.16, h * 0.40, (DARK, DARK, DARK))
    F.eye(w * 0.28, cy - h * 0.08, r=max(1.2, h * 0.12))
    return F.render()


# ------------------------------------------------------------------ items
def coin(w, h, f=0, rng=None):
    """Ring coin with a leaf mark; frames turn it."""
    F = Fig(w, h)
    sq = [1.0, 0.7, 0.3, 0.7][f % 4]
    cx, cy = w / 2, h / 2
    rx, ry = max(1.0, w * 0.36 * sq), h * 0.44
    F.ellipse(cx, cy, rx, ry, (ACC, ACC, ACCD))
    if sq > 0.5:
        F.dmask(ellipse_mask(w, h, cx, cy, rx * 0.45, ry * 0.45), DARK)
        F.px(cx - rx * 0.5, cy - ry * 0.5, WHITE)
    return F.render()


def sprout_berry(w, h, f=0, rng=None):
    F = Fig(w, h)
    cx, cy = w / 2, h * 0.60
    F.ellipse(cx, cy, w * 0.40, h * 0.36, MAIN)
    F.ellipse(cx - w * 0.15, h * 0.18, w * 0.18, h * 0.10, (ACC, ACC, ACCD), rot=0.5)
    F.ellipse(cx + w * 0.15, h * 0.16, w * 0.18, h * 0.10, (ACC, ACC, ACCD), rot=-0.5)
    F.px(cx - w * 0.18, cy - h * 0.15, WHITE)
    F.px(cx - w * 0.12, cy - h * 0.20, WHITE)
    F.eye(cx - w * 0.12, cy, r=1.0)
    F.eye(cx + w * 0.12, cy, r=1.0)
    return F.render()


def life_acorn(w, h, f=0, rng=None):
    F = Fig(w, h)
    cx = w / 2
    F.ellipse(cx, h * 0.62, w * 0.34, h * 0.34, MAIN)
    F.ellipse(cx, h * 0.30, w * 0.44, h * 0.18, ACCENT)
    F.line([(cx, h * 0.12), (cx + 1.5, h * 0.02)], 0.8, ACCD)
    F.dline([(cx - w * 0.2, h * 0.30), (cx + w * 0.2, h * 0.30)], ACCD)
    F.eye(cx - w * 0.1, h * 0.62, r=1.0)
    F.eye(cx + w * 0.12, h * 0.62, r=1.0)
    return F.render()


def ember_bud(w, h, f=0, rng=None):
    F = Fig(w, h)
    cx = w / 2
    F.line([(cx, h - 0.5), (cx, h * 0.55)], 1.0, (ACCD, ACCD, ACCD))
    F.ellipse(cx - 3, h * 0.80, 2.5, 1.2, (ACCD, ACCD, ACCD), rot=-0.4)
    F.ellipse(cx + 3, h * 0.75, 2.5, 1.2, (ACCD, ACCD, ACCD), rot=0.4)
    fl = [0, 1][f % 2]
    F.poly([(cx - w * 0.36, h * 0.55), (cx - w * 0.15, h * 0.08 + fl), (cx, h * 0.30), (cx + w * 0.15, h * 0.04 + fl),
            (cx + w * 0.36, h * 0.55)], MAIN)
    F.ellipse(cx, h * 0.45, w * 0.14, h * 0.12, PALE)
    return F.render()


def spark_gem(w, h, f=0, rng=None):
    F = Fig(w, h)
    cx, cy = w / 2, h / 2
    a = w * 0.48
    b = w * 0.16
    F.poly([(cx, cy - a), (cx + b, cy - b), (cx + a, cy), (cx + b, cy + b), (cx, cy + a), (cx - b, cy + b), (cx - a, cy), (cx - b, cy - b)], (ACC, ACC, ACCD))
    F.eye(cx - 1.5, cy, r=0.8)
    F.eye(cx + 1.5, cy, r=0.8)
    if f % 2:
        F.px(cx, cy - a + 2, WHITE)
    return F.render()


def glider_leaf(w, h, f=0, rng=None):
    F = Fig(w, h)
    F.ellipse(w * 0.5, h * 0.5, w * 0.46, h * 0.24, MAIN, rot=-0.6)
    F.dline([(w * 0.15, h * 0.82), (w * 0.85, h * 0.18)], DARK)
    return F.render()


def leaf_key(w, h, f=0, rng=None):
    F = Fig(w, h)
    cy = h / 2
    F.ellipse(w * 0.25, cy, w * 0.20, h * 0.30, (ACC, ACC, ACCD))
    F.rect(w * 0.40, cy - 1, w * 0.95, cy + 1, (ACC, ACC, ACCD))
    F.rect(w * 0.75, cy + 1, w * 0.85, cy + 4, (ACC, ACC, ACCD))
    F.dmask(ellipse_mask(w, h, w * 0.25, cy, w * 0.07, h * 0.10), 0)
    return F.render()


def spring(w, h, f=0, rng=None):
    F = Fig(w, h)
    sq = [1.0, 0.75, 0.5][f % 3]
    top = h - h * 0.9 * sq
    F.rect(1, h - 3, w - 1, h - 0.5, MAIN)
    F.rect(1, top, w - 1, top + 3, MAIN)
    n = 3
    for k in range(n):
        y = top + 3 + (h - 6 - top) * (k + 0.5) / n
        F.line([(3, y), (w - 3, y)], 1.0, ACCENT)
    return F.render()


def press_pad(w, h, f=0, rng=None):
    F = Fig(w, h)
    flat = f % 2
    top = h * (0.65 if flat else 0.25)
    F.rect(0.5, h - 4, w - 0.5, h - 0.5, (DARK, DARK, DARK))
    F.ellipse(w / 2, top + (h - 4 - top) / 2 + 1, w * 0.40, (h - 4 - top) / 2 + 1.5, MAIN)
    if not flat:
        F.dline([(w / 2, top + 2), (w / 2, top + 5)], WHITE, 1.0)
        F.dline([(w / 2 - 2, top + 4), (w / 2, top + 6), (w / 2 + 2, top + 4)], WHITE)
    return F.render()


def crate(w, h, f=0, rng=None):
    """Bounce / used block as a sprite: carved crate with a knot."""
    F = Fig(w, h)
    F.rect(0, 0, w, h, MAIN)
    out = F.render(outline=None)
    out[0, :] = out[:, 0] = LIGHT
    out[-1, :] = out[:, -1] = LINE
    for y in range(4, h - 2, 5):
        out[y, 2:w - 2] = DARK
    out[h // 2 - 1:h // 2 + 1, w // 2 - 1:w // 2 + 1] = ACCD
    return out


def puff(w, h, f=0, rng=None):
    """Smoke / dust: a cluster of round puffs (frames shrink)."""
    F = Fig(w, h)
    k = 1.0 - 0.2 * (f % 4)
    for dx, dy, r in ((0.35, 0.55, 0.28), (0.65, 0.5, 0.26), (0.5, 0.32, 0.24)):
        F.ellipse(w * dx, h * dy, max(1, w * r * k), max(1, h * r * k), PALE)
    return F.render(outline=None)


def sparkle(w, h, f=0, rng=None):
    out = np.zeros((h, w), np.uint8)
    cx, cy = w // 2, h // 2
    n = max(1, min(w, h) // 2 - (f % 3))
    for d in range(-n, n + 1):
        if 0 <= cy + d < h:
            out[cy + d, cx] = WHITE if abs(d) < 2 else ACC
        if 0 <= cx + d < w:
            out[cy, cx + d] = WHITE if abs(d) < 2 else ACC
    return out


def ember(w, h, f=0, rng=None):
    """Fireball: a swirl of flame."""
    F = Fig(w, h)
    cx, cy = w / 2, h / 2
    F.ellipse(cx, cy, w * 0.36, h * 0.36, (ACC, MID, ACCD))
    a = (f % 4) * np.pi / 2
    F.ellipse(cx + np.cos(a) * w * 0.3, cy + np.sin(a) * h * 0.3, w * 0.18, h * 0.18, (ACC, ACC, ACCD))
    F.px(cx - 1, cy - 1, WHITE)
    return F.render()


def pebble(w, h, f=0, rng=None):
    F = Fig(w, h)
    F.ellipse(w / 2, h / 2, w * 0.42, h * 0.38, MAIN)
    F.px(w * 0.35, h * 0.35, WHITE)
    return F.render()


def interior(w, h, f=0, rng=None):
    """Fully covered slot (inside of a big figure): soft body fill with scattered scales."""
    out = np.full((h, w), MID, np.uint8)
    y, x = np.mgrid[0:h, 0:w]
    out[((x * 3 + y * 5 + f * 7) % 11) == 0] = LIGHT
    out[((x * 5 + y * 3 + f * 3) % 13) == 0] = DARK
    return out


def panel(w, h, f=0, rng=None):
    """Opaque picture slot: woven bramble panel."""
    out = np.full((h, w), MID, np.uint8)
    y, x = np.mgrid[0:h, 0:w]
    out[((x + y) // 3) % 2 == 0] = LIGHT
    out[((x - y) % 6) == 0] = DARK
    out[0, :] = LIGHT
    out[-1, :] = LINE
    return out


WALKERS = [pipkin, burrbug, thornling, urchin]
FLIERS = [moth, flapling, wisp]
SMALL = [pebble, sparkle, ember, puff, urchin]
ITEMS = [sprout_berry, life_acorn, ember_bud, spark_gem, glider_leaf, leaf_key]
EVERY = WALKERS + FLIERS + [finnow, snapbud, thornshot, shell, pipkin, burrbug]


def auto(w, h, rng):
    """A figure for an unlabelled slot, picked by its box shape."""
    f = int(rng.integers(0, 4))
    if w <= 6 and h <= 6:
        g = [sparkle, pebble, ember][int(rng.integers(0, 3))]
    elif w <= 9 and h <= 9:
        g = SMALL[int(rng.integers(0, len(SMALL)))]
    elif w > h * 1.6:
        g = [thornshot, finnow, moth, flapling][int(rng.integers(0, 4))]
    elif h > w * 1.6:
        g = [snapbud, thornling, wisp][int(rng.integers(0, 3))]
    else:
        g = EVERY[int(rng.integers(0, len(EVERY)))]
    return g(w, h, f, rng)


# ------------------------------------------------------------------ pieces of bigger figures
def family(rng):
    """Features shared by the pieces of one sheet (so pieces assembled by the game match)."""
    return dict(horn=int(rng.integers(0, 4)), eyes=int(rng.integers(1, 3)), belly=bool(rng.integers(0, 2)),
                spots=bool(rng.integers(0, 2)))


def _crown(F, cx, top, w, fam):
    h = fam['horn']
    if h == 1:
        for s in (-1, 1):
            F.poly([(cx + s * w * 0.18, top + 2), (cx + s * w * 0.34, top + 2), (cx + s * w * 0.32, top - 3)], ACCENT)
    elif h == 2:
        F.ellipse(cx - 2, top - 1, 2.6, 1.2, ACCENT, rot=0.5)
        F.ellipse(cx + 2, top - 1.5, 2.6, 1.2, ACCENT, rot=-0.5)
    elif h == 3:
        for k in range(4):
            x = cx - w * 0.3 + k * w * 0.2
            F.poly([(x - 1.4, top + 2), (x + 1.4, top + 2), (x, top - 2)], (DARK, DARK, DARK))


def _eyes(F, cx, cy, s, fam):
    r = max(1.2, s * 0.10)
    if fam['eyes'] == 1:
        F.eye(cx, cy, r=r * 1.3)
    else:
        F.eye(cx - s * 0.16, cy, r=r)
        F.eye(cx + s * 0.10, cy, r=r)


def piece(edges, fam, f=0, rng=None):
    """16x16 piece of a larger figure: the figure is drawn whole on a virtual canvas and the piece cut
    from it. edges = sides the piece continues across ('T','B','L','R'); fam picks the creature."""
    T, B, Lf, R = ('T' in edges), ('B' in edges), ('L' in edges), ('R' in edges)
    if T and B and (Lf or R) or (Lf and R and (T or B)):
        return None
    W = 16 * (1 + (Lf or R) + (Lf and R))
    H = 16 * (1 + (T or B) + (T and B))
    tall = [thornling, burrbug, pipkin, snapbud]
    wide = [finnow, thornshot, flapling, moth]
    big = [thornling, burrbug, pipkin, urchin]
    if W == 16:
        g = tall[fam['horn']]
    elif H == 16:
        g = wide[fam['horn']]
    else:
        g = big[fam['horn']]
    art = g(W, H, f, rng)
    x = 16 if (Lf and R) else (W - 16 if Lf else 0)
    y = 16 if (T and B) else (H - 16 if T else 0)
    return art[y:y + 16, x:x + 16]
