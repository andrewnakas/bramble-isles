"""Originality export of the overworld (any smw_assets.dat, retail-derived or clean).

Per map (0 = main map, 1-6 = submaps), with every event applied:
  overworld/paths_<m>.obj  one unit box per walkable layer-1 cell (paths, level tiles)
  overworld/land_<m>.obj   one unit box per 16x16 non-walkable cell that is not water / backdrop
Cell (x, y) -> box [x, x+1] x [y, y+1] x [0, 1] (y 32..63 = submap half).
games/smw/ow_anchors.json lists the kept cells (nodes, exits, event-changed cells, the forced
first/last cell of each connection, hard-wired paths) so the gate leaves them out.
"""
import json
import os

import numpy as np

from games.smw import assetfile as A, ow_render as R, ow_plan as P

HERE = os.path.dirname(__file__)


def box_obj(cells):
    v, f = [], []
    for x, y in cells:
        b = len(v)
        for dz in (0, 1):
            for dy in (0, 1):
                for dx in (0, 1):
                    v.append((x + dx, y + dy, dz))
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            f.append([b + k + 1 for k in q])
    return ''.join('v %d %d %d\n' % p for p in v) + ''.join('f %d %d %d %d\n' % tuple(q) for q in f)


def map_cells(m):
    """All cells (x, y) of map m's window."""
    if m == 0:
        return [(x, y) for y in range(32) for x in range(32)]
    x0, x1, y0, y1 = P.window(m)
    return [(x, y + 32) for y in range(y0, y1) for x in range(x0, x1)]


def is_water(rgb):
    r, g, b = [rgb[..., k].astype(int) for k in range(3)]
    return (b > r + 24) & (b >= g - 8)


def land_cells(ow, items):
    out = {}
    for half in (0, 1):
        for m in ([0] if half == 0 else range(1, 7)):
            img = R.render(ow, items, half, R.SUBMAP_AREA[m])
            cells = [c for c in map_cells(m)]
            land = []
            for x, y in cells:
                yy = y - 32 * half
                px = img[yy * 16:yy * 16 + 16, x * 16:x * 16 + 16]
                dark = px.max(axis=2) < 24
                wet = is_water(px)
                if (wet | dark).mean() < 0.5:
                    land.append((x, y))
            out[m] = land
    return out


def anchors(spec):
    pts = set()
    for x, y, _, _ in spec['nodes']:
        pts.add((x, y))
    for x, y, _, _ in spec['fixed']:
        pts.add((x, y))
    for s in spec['segs']:
        a, b = s['a'], s['b']
        pts.add(tuple(b))
        pts.add((a[0] + P.STEP[s['j']][0], a[1] + P.STEP[s['j']][1]))
        pts.add((b[0] - P.STEP[s['arr']][0], b[1] - P.STEP[s['arr']][1]))
    from games.smw import overworld
    for c in overworld.hard_route_cells(spec):
        pts.add(c)
    p, _ = overworld.plan(spec, overworld.kept_items())
    pts |= P.forced_cells_exact(p, set(pts), radius=1)
    return sorted(pts)


def anchor_points(cells):
    out = []
    for x, y in cells:
        for dz in (0, 0.5, 1):
            for dy in (0, 0.5, 1):
                for dx in (0, 0.5, 1):
                    out.append([x + dx, y + dy, dz])
    return out


def export(items, outdir):
    ow = R.OW(items)
    ow.apply_events(range(R.NEV))
    land = land_cells(ow, items)
    n = 0
    for m in range(7):
        cells = map_cells(m)
        path = [(x, y) for x, y in cells if 0 < ow.l1[y, x] < 0x87]
        ps = set(path)
        terrain = [c for c in land[m] if c not in ps]      # walkable cells are compared in paths_*
        for name, cs in (('paths', path), ('land', terrain)):
            open(os.path.join(outdir, '%s_%d.obj' % (name, m)), 'w').write(box_obj(cs))
            n += 1
    spec = json.load(open(os.path.join(HERE, 'spec', 'ow.json')))
    an = anchors(spec)
    by = {}
    for m in range(7):
        win = set(map_cells(m))
        pts = anchor_points([c for c in an if c in win])
        by['paths_%d.obj' % m] = pts
        by['land_%d.obj' % m] = pts
    json.dump({'by_mesh': by}, open(os.path.join(HERE, 'ow_anchors.json'), 'w'))
    return n
