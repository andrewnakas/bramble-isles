"""CLEAN ROOM. Our labels: what each sprite slot is (role + frame), as groups of 16x16 units.

ROLES[sheet] = [(units, role, frame, opts), ...]; units = list of unit numbers forming one picture,
drawn as one canvas over the union of their 16x16 cells (top-left = smallest x / y), then cut back.
"""
import numpy as np
from games.smw import spr_cast as C

ROLES = {
    0x00: [([0], 'crate', 0), ([7], 'glider_leaf', 0), ([10], 'sprout_berry', 0), ([11], 'ember_bud', 0), ([13], 'crate', 1),
           ([15], 'crate', 2), ([16], 'crate', 3), ([17], 'press_pad', 0), ([20], 'spark_gem', 0), ([24], 'puff', 0),
           ([25], 'sparkle', 0), ([26], 'sparkle', 1), ([27], 'sparkle', 2), ([28], 'puff', 1), ([29], 'puff', 2), ([30], 'puff', 3)],
    0x01: [([0], 'sprout_berry', 1), ([1], 'pipkin', 0), ([2], 'pipkin', 1), ([5], 'shell', 0), ([6], 'shell', 1), ([7], 'shell', 2),
           ([11], 'thornshot', 0), ([14], 'shell', 3), ([15], 'shell', 1), ([28], 'coin', 0), ([29], 'leaf_key', 1), ([30], 'leaf_key', 0)],
    0x02: [([0], 'urchin', 0), ([1], 'urchin', 1), ([7], 'ember', 0), ([14], 'ember', 1), ([15], 'ember', 2)],
    0x04: [([0], 'shell', 0), ([1], 'shell', 1), ([2], 'shell', 2), ([3], 'shell', 3), ([4], 'ember', 0), ([24], 'wisp', 0), ([25], 'wisp', 1)],
    0x11: [([0, 1, 2, 3, 8, 9, 10, 11, 16, 17, 18, 19, 24, 25, 26, 27], 'wisp', 0)],
    0x21: [([0, 1, 2, 3, 8, 9, 10, 11, 16, 17, 18, 19, 24, 25, 26, 27], 'thornshot', 0)],
    0x25: [([16, 17, 24, 25], 'burrbug', 0), ([18, 19, 26, 27], 'burrbug', 1)],
    0x30: [([0, 1, 8, 9], 'thornling', 0), ([2, 3, 10, 11], 'thornling', 1), ([4, 5, 12, 13], 'thornling', 0),
           ([6, 7, 14, 15], 'thornling', 1)],
}


def render(ent, s, rng):
    units, role, frame = ent[0], ent[1], ent[2]
    opts = ent[3] if len(ent) > 3 else {}
    xs = [u % 8 for u in units]
    ys = [u // 8 for u in units]
    w, h = (max(xs) - min(xs) + 1) * 16, (max(ys) - min(ys) + 1) * 16
    fn = getattr(C, role)
    art = fn(w, h, frame, rng, **opts)
    return units, art
