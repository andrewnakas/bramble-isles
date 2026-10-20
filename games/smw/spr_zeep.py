"""CLEAN ROOM. ZEEP, the ridable lizard (green / red / blue / yellow by palette row), plus the lava ember.

ZEEP: slim gecko with round eyes on top of a flat head, a frilled crest, a cream throat, a leather
riding harness and a striped tail. Drawn in the dynamic slots of kGfx33 (the code uploads the mount's
16x16 frames from there): head units sit 10 px ahead of and 16 px above the body unit (code offsets),
so the neck runs from the head unit's lower right into the body unit's upper left.
Our labels of the slots (what each is): heads, bodies, the ember.
"""
import numpy as np
from games.smw.spr_draw import (Fig, WHITE, LINE, LIGHT, MID, DARK, ACC, ACCD, MAIN, ACCENT,
                                ellipse_mask, poly_mask)

HEADS = {16: dict(), 18: dict(dy=1), 22: dict(dy=-1, blink=True), 23: dict(mouth=True), 26: dict(dy=3, mouth=True),
         29: dict(dy=-3), 30: dict(front=True), 32: dict(dy=2, mouth=True), 34: dict(dy=1, tongue=True)}
BODIES = {17: dict(ph=0), 19: dict(ph=1), 21: dict(ph=2), 25: dict(ph=3), 27: dict(ph=1, lean=1), 31: dict(ph=0, lean=1),
          24: dict(ph=2, jump=True), 28: dict(ph=0, jump=True), 33: dict(duck=True)}
EMBER = 20


def head(dy=0, mouth=False, blink=False, front=False, tongue=False):
    F = Fig(16, 16)
    hy = 7 + dy
    F.line([(8, hy + 2), (12, 12), (13.5, 16)], 3.2, MAIN)                      # neck
    F.line([(8.5, hy + 4), (11, 13), (12, 16)], 1.2, ACCENT)                    # throat stripe
    if front:
        F.ellipse(8, hy, 5.5, 4.5, MAIN)
        for ex in (5.5, 10.5):
            F.ellipse(ex, hy - 3.5, 2.0, 2.0, MAIN)
            F.eye(ex, hy - 3.5, r=1.4, look=(0, 0))
        F.dline([(5.5, hy + 2), (10.5, hy + 2)], LINE)
        return F.render()
    for k in range(3):                                                          # crest frill
        x = 9.5 + k * 1.8
        F.poly([(x - 1.2, hy - 2), (x + 1.2, hy - 2), (x + 1.6, hy - 5.5 + k * 0.8)], ACCENT)
    F.ellipse(7.5, hy, 6.0, 3.6, MAIN)                                          # flat head
    F.ellipse(2.8, hy + 0.8, 2.6, 2.4, MAIN)                                    # snout
    F.ellipse(7.0, hy - 3.2, 2.3, 2.3, MAIN)                                    # eye bump
    if mouth:
        F.cut(poly_mask(16, 16, [(0, hy + 1.0), (6, hy + 1.5), (0, hy + 4.5)]))
        F.poly([(0.5, hy + 2.0), (5.5, hy + 1.8), (1.5, hy + 4.2)], ACCENT)
    if tongue:
        F.line([(2, hy + 2.5), (0, hy + 3)], 1.0, (ACCD, ACCD, ACCD))
    if blink:
        F.dline([(5.8, hy - 3.2), (8.2, hy - 3.2)], LINE)
    else:
        F.eye(6.6, hy - 3.2, r=1.6, look=(-1, 0))
    F.px(1.5, hy, LINE)                                                         # nostril
    for x in (9, 11.5):
        F.px(x, hy - 0.5, DARK)                                                 # spots
    return F.render()


def body(ph=0, lean=0, jump=False, duck=False):
    F = Fig(16, 16)
    by = 7 + (3 if duck else 0) - (1 if jump else 0)
    sw = [0, 1, 0, -1][ph % 4]
    # tail: curls up to the right
    F.line([(12, by + 1), (14.5, by - 2), (15.5, by - 6 + sw)], 2.4, MAIN)
    for t in ((13.6, by - 0.5), (15, by - 4)):
        F.px(t[0], t[1], DARK)
    # far legs
    if not duck:
        F.line([(6, by + 3), (5 - sw * 1.5 - (2 if jump else 0), 14.5)], 1.6, (DARK, DARK, DARK))
        F.line([(11, by + 3), (12 + sw * 1.5 + (2 if jump else 0), 14.5)], 1.6, (DARK, DARK, DARK))
    F.ellipse(8.5, by + 1.5, 7.0, 5.0 - (1 if duck else 0), MAIN)               # torso
    F.ellipse(6.5, by + 3, 4.0, 2.0, ACCENT)                                     # cream belly
    F.line([(2.5, 0), (4, by - 1)], 3.0, MAIN)                                   # neck base
    # near legs with round toes
    if duck:
        F.ellipse(4, 14.5, 2.5, 1.4, MAIN)
        F.ellipse(12, 14.5, 2.5, 1.4, MAIN)
    else:
        for x0, d in ((4.5, -1), (10.5, 1)):
            fx = x0 + d * sw * 1.5 * (-1 if x0 < 8 else 1) + (d * 2 if jump else 0)
            F.line([(x0 + 1, by + 3), (fx, 14)], 2.0, MAIN)
            F.ellipse(fx - 0.6, 14.6, 1.8, 1.0, MAIN)
    # riding harness: strap + seat
    F.rect(6.5, by - 4, 12, by - 1.5, (ACCD, ACCD, ACCD))
    F.dline([(8, by - 1.5), (7.5, by + 4)], ACCD)
    F.px(9, by - 3.2, WHITE)
    for x in (4.5, 13):
        F.px(x, by, DARK)
    return F.render()


def ember(w=16, h=16):
    """Lava ember: a teardrop of fire with two coal eyes (symmetric: the code mirrors halves)."""
    F = Fig(w, h)
    F.poly([(8, 0.5), (13.5, 9), (8, 15.5), (2.5, 9)], (ACC, ACC, ACCD))
    F.ellipse(8, 10, 5.0, 5.2, (ACC, MID, ACCD))
    F.ellipse(8, 11, 2.6, 2.6, (WHITE, ACC, ACC))
    F.px(6.5, 9, LINE)
    F.px(9.5, 9, LINE)
    a = F.render()
    a[:, 8:] = a[:, :8][:, ::-1]
    return a


def paint(img, s):
    def put(u, a):
        y, x = u // 8 * 16, u % 8 * 16
        img[y:y + 16, x:x + 16] = a
    for u, k in HEADS.items():
        put(u, head(**k))
    for u, k in BODIES.items():
        put(u, body(**k))
    put(EMBER, ember())
    return img
