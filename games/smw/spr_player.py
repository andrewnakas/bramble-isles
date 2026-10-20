"""CLEAN ROOM. TOBI (and KIP, same art in other colours): the player sheet kGfx32, plus ZEEP in kGfx33.

TOBI: round hood with a floppy tip, big eye, orange scarf with a flying tail, cream tunic, big boots.
Each pose is drawn whole on a 16 x 32 canvas (head unit over body unit, as the game stacks them) from
pose parameters, then cut: a head unit takes the top half of the first pose that uses it, a body unit
the bottom half. The pose tables (kPlayerGFXRt_*TilePointerIndex) are code: which unit each pose uses.

Player palette indices (spr_pal.PLAYER + row 8):
 1 white, 2 outline, 3 boot dark, 4 boot light, 5 skin, 6 skin shade, 7/8/9 hood light/mid/dark,
 10/11 scarf light/dark, 12/13 tunic light/dark, 14 eye, 15 gold.
"""
import math

import numpy as np

from cleanroom.snes import tiles
from games.smw.spr_draw import Fig, ellipse_mask, line_mask, poly_mask, grow, shrink

W1, OUT, BOOT, BOOTL, SKIN, SKINS, HL, HM, HD, SCL, SCD, TUL, TUD, EYE, GOLD = range(1, 16)
HOOD = (HL, HM, HD)
SCARF = (SCL, SCL, SCD)
TUNIC = (TUL, TUL, TUD)
BOOTS = (BOOTL, BOOT, BOOT)
SKINR = (SKIN, SKIN, SKINS)


def uof(r):
    return (r & 7) + 8 * (r >> 4) + (128 if r & 8 else 0)


# --------------------------------------------------------------------- pose table (ours)
# family, params.  Angles in degrees from straight down, + = forward (toward the left, the facing side).
def P(fam='stand', **k):
    d = dict(fam=fam, view='side', legs=((-8, 0), (8, 0)), arms=((-10, 0), (15, 0)), knees=(0, 0),
             lean=0, look=0, item=False, dy=0, burnt=False, mouth=False, fist=False)
    d.update(k)
    return d


WALK = [((-25, 0), (25, 0)), ((20, 10), (-20, 10))]
RUN = [((-45, 30), (45, 10)), ((10, 50), (-15, 10)), ((40, 10), (-45, 40))]
POSES = {
    0x00: P('stand'),
    0x01: P('walk', legs=WALK[0], arms=((20, 0), (-25, 0))),
    0x02: P('walk', legs=WALK[1], arms=((-20, 0), (25, 0))),
    0x03: P('lookup', look=1),
    0x04: P('run', legs=RUN[0], arms=((-70, 40), (60, 60)), lean=8),
    0x05: P('run', legs=RUN[1], arms=((-60, 40), (70, 60)), lean=8),
    0x06: P('run', legs=RUN[2], arms=((-70, 40), (60, 60)), lean=8),
    0x07: P('carry', arms=((80, 10), (85, 10)), item=True),
    0x08: P('carry', legs=WALK[0], arms=((80, 10), (85, 10)), item=True),
    0x09: P('carry', legs=WALK[1], arms=((80, 10), (85, 10)), item=True),
    0x0A: P('carry', look=1, arms=((80, 10), (85, 10)), item=True),
    0x0B: P('jump', legs=((-20, 50), (30, 70)), arms=((-40, 20), (160, 0)), fist=True),
    0x0C: P('runjump', legs=((-50, 30), (40, 40)), arms=((-110, 0), (110, 0)), lean=12),
    0x0D: P('skid', legs=((-40, 0), (20, 20)), arms=((-60, 30), (-100, 20)), lean=-12, mouth=True),
    0x0E: P('kick', legs=((-10, 0), (75, 0)), arms=((-60, 20), (40, 30))),
    0x0F: P('front', view='front', arms=((-20, 0), (20, 0))),
    0x10: P('dive', view='dive'),
    0x11: P('tilt', view='tilt', tilt=30),
    0x12: P('tilt', view='tilt', tilt=60),
    0x13: P('tilt', view='tilt', tilt=60),
    0x14: P('punch', arms=((-30, 30), (95, 0)), fist=True, star=True),
    0x15: P('back', view='back', arms=((150, 20), (-150, 20))),
    0x16: P('swim', legs=((-60, 20), (40, 30)), arms=((-120, 30), (100, 20)), lean=30),
    0x17: P('swim', legs=((-30, 20), (60, 40)), arms=((-80, 30), (60, 40)), lean=30),
    0x18: P('swim', legs=((-50, 40), (20, 20)), arms=((-40, 30), (20, 40)), lean=30),
    0x19: P('swim', legs=((-60, 20), (40, 30)), arms=((80, 10), (85, 10)), lean=30, item=True),
    0x1A: P('swim', legs=((-50, 30), (40, 40)), arms=((-110, 0), (110, 0)), lean=12),
    0x1B: P('swim', legs=((-30, 20), (60, 40)), arms=((80, 10), (85, 10)), lean=30, item=True),
    0x1C: P('throw', arms=((-50, 20), (100, 10)), item=True),
    0x1D: P('duck', view='duck'),
    0x1E: P('climb', view='back', arms=((170, 0), (-120, 30)), legs=((-20, 40), (10, 0))),
    0x1F: P('spin', view='front', arms=((-90, 0), (100, 0)), legs=((-15, 0), (25, 30))),
    0x20: P('ride', view='ride', arms=((30, 40), (40, 40))),
    0x21: P('ride', view='ride', arms=((60, 40), (80, 40))),
    0x22: P('ridefront', view='front', legs=((-50, 30), (50, 30)), arms=((-60, 30), (60, 30))),
    0x23: P('ridefront', view='front', legs=((-50, 30), (50, 30)), arms=((-150, 0), (150, 0))),
    0x24: P('ride', view='ride', arms=((-30, 20), (120, 0))),
    0x25: P('back', view='back'),
    0x26: P('punch', arms=((-30, 30), (95, 0)), fist=True, star=True, view='ride'),
    0x27: P('ride', view='ride', arms=((60, 40), (90, 20))),
    0x28: P('ride', view='ride', arms=((30, 40), (40, 40))),
    0x29: P('ride', view='ride', arms=((30, 40), (40, 40))),
    0x2A: P('balloon', view='balloon', puff=0.4),
    0x2B: P('balloon', view='balloon', puff=0.6),
    0x2C: P('balloon', view='balloon', puff=0.8),
    0x2D: P('balloon', view='balloon', puff=1.0),
    0x2E: P('balloon', view='balloon', puff=1.0),
    0x2F: P('balloon', view='balloon', puff=1.0),
    0x30: P('stand', burnt=True, view='front'),
    0x31: P('stand', burnt=True, view='front', arms=((-40, 0), (40, 0))),
    0x32: P('stand'),
    0x33: P('lookback', look=-1),
    0x34: P('lookback', look=-1, view='back'),
    0x35: P('ride', view='ride', arms=((150, 20), (160, 20)), item=True),
    0x36: P('ride', view='ride', arms=((60, 40), (90, 20))),
    0x37: P('ride', view='ride'),
    0x38: P('back', view='back'),
    0x39: P('back', view='back'),
    0x3A: P('ride', view='ride'),
    0x3B: P('ride', view='ride'),
    0x3C: P('duck', view='duck'),
    0x3D: P('grow', view='front'),
    0x3E: P('death', view='front', arms=((-150, 0), (150, 0)), mouth=True),
    0x3F: P('front', view='front'),
    0x40: P('stand'), 0x41: P('stand'),
    0x42: P('front', view='front'),
    0x43: P('jump', legs=((-20, 50), (30, 70)), arms=((-40, 20), (160, 0))),
    0x44: P('back', view='back'),
    0x45: P('front', view='front', arms=((-30, 0), (30, 0))),
}


# --------------------------------------------------------------------- figure
def _v(a, ln):
    r = math.radians(a)
    return -math.sin(r) * ln, math.cos(r) * ln


def figure(p, big):
    """Draw one pose on a 16 x 32 canvas (facing left), -> index array."""
    F = Fig(16, 32)
    view = p['view']
    if big:
        hx, hy, hr = 8.0, 8.0, 6.2
        sh_y, hip_y, foot_y = 15.5, 22.5, 31.0
        torso_w = 2.8
        arm_l, leg_l = 7.5, 8.0
    else:
        hx, hy, hr = 8.0, 16.0, 5.8
        sh_y, hip_y, foot_y = 22.0, 26.5, 31.0
        torso_w = 2.6
        arm_l, leg_l = 5.0, 4.0
    if view == 'duck':
        hy += 6 if big else 3
        sh_y += 6 if big else 3
        hip_y = foot_y - 2
    if view == 'ride':
        hip_y += 1
    if view in ('dive', 'tilt'):
        return _flying(p, big)
    if view == 'balloon':
        return _balloon(p, big)
    lean = p['lean']
    lx = -math.sin(math.radians(lean)) * 3
    cx = 8.0
    front = view in ('front',)
    back = view == 'back'
    legs, arms, knees = p['legs'], p['arms'], p['knees']

    # far limbs first (darker), then torso, near limbs, head
    def leg(a, bend, far):
        hip = (cx + (1.2 if far else -1.2) * (0 if front or back else 1) + (-2 if (front or back) and far else 2 if (front or back) else 0), hip_y)
        if view == 'ride':
            a, bend = 80, -70
        kx, ky = _v(a, leg_l * 0.55)
        knee = (hip[0] + kx, hip[1] + ky)
        fx, fy = _v(a - bend, leg_l * 0.55)
        foot = (knee[0] + fx, min(foot_y - 2, knee[1] + fy))
        if view not in ('ride',) and abs(a) < 30 and bend == 0:
            foot = (foot[0], foot_y - 2)
        ramp = (HD, HD, HD) if far else (HM, HD, HD)
        F.line([hip, knee, foot], 2.0 if big else 1.6, ramp)
        bx = -1.2 if not (front or back) else 0
        F.ellipse(foot[0] + bx, foot[1] + 0.4, 3.0 if big else 2.5, 2.0 if big else 1.6, (BOOT, BOOT, BOOT) if far else BOOTS)
        F.ellipse(foot[0] + bx * 0.3, foot[1] - 1.2, 1.8 if big else 1.4, 1.0, (BOOTL, BOOTL, BOOT) if not far else (BOOT, BOOT, BOOT))

    def arm(a, bend, far):
        sh = (cx + lx + (2.2 if far else -1.5) if not (front or back) else cx + lx + (-3 if far else 3), sh_y + 0.5)
        ex, ey = _v(a, arm_l * 0.55)
        el = (sh[0] + ex, sh[1] + ey)
        hx2, hy2 = _v(a + bend, arm_l * 0.5)
        hand = (el[0] + hx2, el[1] + hy2)
        F.line([sh, el, hand], 1.9 if big else 1.4, (TUD, TUD, TUD) if far else TUNIC)
        F.ellipse(hand[0], hand[1], 1.7 if (big or p['fist']) else 1.3, 1.6 if big else 1.2, SKINR)
        return hand

    if view not in ('duck',):
        leg(legs[0][0], legs[0][1], True)
    else:
        F.ellipse(cx + 2, foot_y - 1.5, 3.0, 1.7, (BOOT, BOOT, BOOT))
    arm(arms[0][0], arms[0][1], True)
    # tunic body
    tb = (sh_y - 1, hip_y + 1.5)
    F.poly([(cx + lx - torso_w, tb[0]), (cx + lx + torso_w, tb[0]), (cx + torso_w + 1.2, tb[1]), (cx - torso_w - 1.2, tb[1])], (TUL, TUD, TUD))
    F.rect(cx - torso_w - 1.0, hip_y - 0.8, cx + torso_w + 1.2, hip_y + 0.5, (BOOT, BOOT, BOOT))          # belt
    F.px(cx - 0.5, hip_y - 0.5, GOLD)
    if view != 'duck':
        leg(legs[1][0], legs[1][1], False)
    else:
        F.ellipse(cx - 2.5, foot_y - 1.5, 3.2, 1.8, BOOTS)
    # scarf tail behind the neck
    if not front:
        flut = 1.5 if p['fam'] in ('run', 'runjump', 'jump', 'swim') else 0.0
        sx0 = cx + lx + (1 if not back else 0)
        F.poly([(sx0 + 1, sh_y - 1.8), (sx0 + 5.5 + flut, sh_y - 1.0 - flut), (sx0 + 6.0 + flut, sh_y + 0.8 - flut * 0.5),
                (sx0 + 4.0 + flut, sh_y + 1.6), (sx0 + 1, sh_y + 0.8)], SCARF)
    hand = arm(arms[1][0], arms[1][1], False)
    _head(F, cx + lx, hy, hr, p, big)
    F.ellipse(cx + lx + 0.5, sh_y - 1.0, torso_w + 0.4, 1.0, SCARF)                                      # scarf wrap
    if p['item']:
        F.ellipse(hand[0] - 2.5, hand[1] - 1.5, 2.8, 2.6, (GOLD, GOLD, BOOTL))
    if p.get('star'):
        x, y = int(hand[0] - 3), int(hand[1])
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            F.px(x + dx, y + dy, GOLD if (dx or dy) else W1)
    img = F.render(outline=OUT)
    if p['burnt']:
        img = np.where(img > 0, np.where(img == W1, W1, np.where(img == OUT, OUT, HD)), 0).astype(np.uint8)
        img[(img == HD) & ((np.indices(img.shape).sum(0) % 3) == 0)] = OUT
    return img


def _head(F, x, y, r, p, big):
    view = p['view']
    look = p['look']
    # hood: round with a floppy tip falling back (to the right)
    tipdir = -1 if view == 'back' else 1
    if view in ('front', 'back'):
        tip = [(x - 2, y - r + 1), (x + 2, y - r + 1), (x + 0.5, y - r - 2.5)]
    else:
        tip = [(x - 0.5, y - r + 0.5), (x + r * 0.9, y - r * 0.6), (x + r + 2.5, y + 0.5 - look * 2)]
    F.poly(tip, HOOD)
    F.ellipse(x, y, r, r * 0.95, HOOD)
    if view == 'back':
        F.dline([(x - r * 0.5, y + r * 0.3), (x + r * 0.5, y + r * 0.3)], HD)
        return
    if view in ('front', 'grow'):
        fm = ellipse_mask(16, 32, x, y + 1.0, r * 0.68, r * 0.62)
        F.part(fm, SKINR)
        e = 1.8 if big else 1.5
        for ex in (x - 2.0, x + 2.0):
            F.dmask(ellipse_mask(16, 32, ex, y + 0.5, 0.9, e * 0.8), EYE)
            F.px(ex, y - 0.3, W1)
        if p['mouth']:
            F.dmask(ellipse_mask(16, 32, x, y + 3.2, 1.2, 1.0), OUT)
        else:
            F.dline([(x - 1, y + 3.2), (x + 1, y + 3.2)], SKINS)
        return
    # side: face opening on the left of the hood
    fx = x - r * 0.38
    fy = y + 0.8 - look * 1.2
    F.part(ellipse_mask(16, 32, fx, fy, r * 0.62, r * 0.66), SKINR)
    F.part(ellipse_mask(16, 32, fx - r * 0.55, fy + 0.6, 1.2, 1.0), (SKIN, SKIN, SKIN))       # nose bump
    ex, ey = fx - r * 0.15, fy - 0.6 - look * 0.6
    F.dmask(ellipse_mask(16, 32, ex, ey, 0.9, 1.6 if big else 1.3), EYE)
    F.px(ex, ey - 1, W1)
    if p['mouth']:
        F.px(fx - r * 0.25, fy + 2.4, OUT)
        F.px(fx - r * 0.25 + 1, fy + 2.4, OUT)
    # cheek
    F.px(fx + r * 0.25, fy + 1.5, SKINS)


def _flying(p, big):
    """Cape dive / tilt: TOBI tucked into a ball, leaning by the tilt (our pose)."""
    F = Fig(16, 32)
    k = 0 if p['view'] == 'dive' else (1 if p.get('tilt', 45) < 45 else 2)
    cy = 22 if big else 24
    F.ellipse(9 - k, cy + 2, 4.5, 3.5, (TUL, TUD, TUD))
    F.ellipse(12 - k, cy + 5, 2.6, 1.8, BOOTS)
    F.ellipse(6.5 + k, cy - 2 + k, 5.6, 5.2, HOOD)
    F.ellipse(4.5 + k, cy - 1 + k, 3.0, 3.2, SKINR)
    F.dmask(ellipse_mask(16, 32, 3.8 + k, cy - 1.5 + k, 0.8, 1.3), EYE)
    F.ellipse(8, cy + 1, 3.6, 1.0, SCARF)
    F.ellipse(2.5 + k, cy + 3, 1.5, 1.4, SKINR)
    return F.render(outline=OUT)


def _balloon(p, big):
    F = Fig(16, 32)
    k = p.get('puff', 1.0)
    cy = 20
    F.ellipse(8, cy, 5 + 2.5 * k, 5 + 2.5 * k, HOOD)
    F.ellipse(8, cy - 4.5 - 2 * k, 3.4, 3.0, SKINR)
    F.dmask(ellipse_mask(16, 32, 7, cy - 5 - 2 * k, 0.8, 1.2), EYE)
    F.dmask(ellipse_mask(16, 32, 10, cy - 5 - 2 * k, 0.8, 1.2), EYE)
    F.ellipse(4, cy + 7 + k, 2, 1.4, BOOTS)
    F.ellipse(12, cy + 7 + k, 2, 1.4, BOOTS)
    F.ellipse(8, cy + 1, 3, 2.4, (GOLD, GOLD, BOOTL))
    return F.render(outline=OUT)


# --------------------------------------------------------------------- cape / glider cloak pieces
def cloak_piece(w, h, k):
    """A glider-leaf cloak fragment filling a box: veined leaf colours (hood ramp + gold)."""
    F = Fig(w, h)
    pts = [(0.5, h * 0.2), (w * 0.6, 0.5), (w - 0.5, h * 0.45), (w * 0.7, h - 0.5), (w * 0.15, h * 0.85)]
    rot = k % 4
    pts = [((x if rot % 2 == 0 else w - x), (y if rot < 2 else h - y)) for x, y in pts]
    F.poly(pts, (HL, HM, HD))
    F.dline([pts[0], pts[2]], HD)
    F.dline([(w * 0.4, h * 0.3), (w * 0.5, h * 0.75)], GOLD)
    return F.render(outline=OUT)


# --------------------------------------------------------------------- sheet
def build_sheet(s, kept):
    H, B = kept['kPlayerGFXRt_HeadTilePointerIndex'], kept['kPlayerGFXRt_BodyTilePointerIndex']
    nunits = len(s['units'])
    img = np.zeros((nunits // 8 * 16, 128), np.uint8)
    done = set()

    def put(u, a):
        y, x = u // 8 * 16, u % 8 * 16
        img[y:y + 16, x:x + 16] = a
        done.add(u)
    cache = {}
    for e in range(len(H)):
        big = e >= 0x46 and e not in range(0x3D, 0x46)
        pose = e if e < 0x46 else (e - 0x46 if e < 0x83 else e - 0x83)
        if e < 0x46 and e >= 0x3D:
            big = e in (0x3D, 0x3F, 0x43, 0x44, 0x45)
        hu, bu = uof(H[e]), uof(B[e])
        for u in (hu, bu):
            if s['units'][u] is None:
                done.add(u)          # slot empty in the game's layout: an invisible part, keep it empty
        if hu in done and bu in done:
            continue
        key = (pose, big)
        if key not in cache:
            cache[key] = figure(POSES.get(pose, POSES[0]), big)
        fig = cache[key]
        if hu not in done:
            put(hu, fig[:16])
        if bu not in done:
            put(bu, fig[16:])
    for k, b in enumerate(s['units']):
        if b is None or k in done:
            continue
        x0, y0, x1, y1 = b
        y, x = k // 8 * 16, k % 8 * 16
        img[y + y0:y + y1 + 1, x + x0:x + x1 + 1] = cloak_piece(x1 - x0 + 1, y1 - y0 + 1, k)
    nt = s['bytes'] // 32
    out = tiles.encode(tiles.unsheet(img)[:nt], 4)
    assert len(out) == s['bytes']
    return out


# --------------------------------------------------------------------- ZEEP (kGfx33)
def patch_gfx33(raw, s):
    """Replace the mount's slots in the animated sheet (other slots belong to the tiles worker)."""
    from games.smw import spr_zeep
    img = tiles.sheet(tiles.decode(raw, 3))
    img = spr_zeep.paint(img, s)
    nt = len(raw) // 24
    out = tiles.encode(tiles.unsheet(img)[:nt], 3)
    assert len(out) == len(raw)
    return out


# --------------------------------------------------------------------- overworld TOBI (sheet 0x10)
# map-walker slots of sheet 0x10 (our labels): view, step
OW_SLOTS = {3: ('front', 1), 5: ('front', 0), 6: ('front', 2), 10: ('front', 1), 26: ('front', 0), 4: ('side', 0),
            7: ('back', 0), 8: ('back', 1), 19: ('back', 2), 27: ('back', 0)}
# player indices -> overworld sprite row slots (1 white, 2 black, 3/4 hat dark/light, 5 clothes, 6/7 skin)
OW_MAP = {0: 0, W1: 1, OUT: 2, EYE: 2, BOOT: 3, BOOTL: 3, HD: 3, HM: 4, HL: 4, TUL: 5, TUD: 5, SCL: 6, SCD: 3, SKIN: 7, SKINS: 6, GOLD: 7}


def ow_tobi(view, step):
    F = Fig(16, 16)
    sw = [0, 1, -1][step]
    F.ellipse(5.5 + sw, 14.3, 2.4, 1.6, BOOTS)
    F.ellipse(10.5 - sw, 14.3, 2.4, 1.6, BOOTS)
    F.ellipse(8, 10.5, 4.2, 3.2, TUNIC)
    if view == 'side':
        F.poly([(8, 1.5), (13, 2.5), (14.5, 7)], HOOD)
        F.ellipse(8, 5.5, 5, 4.6, HOOD)
        F.ellipse(6, 6.2, 3.0, 3.0, SKINR)
        F.px(5.3, 5.6, EYE)
    else:
        F.poly([(6, 2), (10, 2), (8, -0.5)], HOOD)
        F.ellipse(8, 5.5, 5.2, 4.6, HOOD)
        if view == 'front':
            F.ellipse(8, 6.4, 3.4, 2.8, SKINR)
            F.px(6.6, 6.0, EYE)
            F.px(9.4, 6.0, EYE)
    F.ellipse(8, 8.6, 3.6, 1.0, SCARF)
    return F.render(outline=OUT)


def paint_ow(img):
    for u, (view, step) in OW_SLOTS.items():
        a = ow_tobi(view, step)
        out = np.zeros_like(a)
        for k, v in OW_MAP.items():
            out[a == k] = v
        y, x = u // 8 * 16, u % 8 * 16
        img[y:y + 16, x:x + 16] = out
