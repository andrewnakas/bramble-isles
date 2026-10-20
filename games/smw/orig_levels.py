"""Originality export: every distinct level layout (and the walk-in / cast-roll / Chocolate-Island-2
scenes) rendered with the port's own loader, as a mesh of unit boxes, one per occupied block
(anything that is not air or pure decoration), x = column, y = -row. Same code for retail and
clean; files are named by slot so the gate pairs them.
"""
import os
import tempfile

import numpy as np

from games.smw import assetfile as A, lvl_render as R

SKIP = {'empty', 'decor'}


def _occupied(grid, tileset):
    from games.smw import blocks as B
    occ = np.zeros(grid.shape, bool)
    for v in np.unique(grid):
        if B.cls(int(v) & 0x1FF, tileset) not in SKIP:
            occ |= grid == v
    return occ


def write_obj(path, occ):
    """One square (two triangles) per occupied block, in the z = 0 plane."""
    rows, cols = np.nonzero(occ)
    with open(path, 'w') as f:
        for r, c in zip(rows, cols):
            x0, y0 = float(c), float(-r)
            f.write('v %g %g 0\nv %g %g 0\nv %g %g 0\nv %g %g 0\n' % (x0, y0 - 1, x0 + 1, y0 - 1, x0 + 1, y0, x0, y0))
        for k in range(len(rows)):
            b = 4 * k + 1
            f.write('f %d %d %d\nf %d %d %d\n' % (b, b + 1, b + 2, b, b + 2, b + 3))


def export(items, outdir):
    with tempfile.TemporaryDirectory() as td:
        dat = os.path.join(td, 'x.dat')
        A.write(dat, list(items.items()))
        l1 = A.unpack_array(items['kLevelData_Layer1'])
        import json
        spec = json.load(open(os.path.join(os.path.dirname(__file__), 'spec', 'levels.json')))
        firsts = [e['members'][0] for e in spec['levels'] if not e['empty']]   # one slot per layout group
        n = 0
        jobs = [('level', firsts)]
        for kind, name in (('entrance', 'kEntranceData_Layer1'), ('choco2', 'kChoclateIsland2_Layer1'),
                           ('rollcall', 'kRollCallData_Layer1')):
            jobs.append((kind, [i for i, d in enumerate(A.unpack_array(items[name])) if len(d) > 6]))
        for kind, idx in jobs:
            for i, (mode, screens, g) in R.render(dat, kind, idx).items():
                if kind == 'level':
                    ts = l1[i][4] & 0xF
                else:
                    ts = A.unpack_array(items[{'entrance': 'kEntranceData_Layer1', 'choco2': 'kChoclateIsland2_Layer1',
                                               'rollcall': 'kRollCallData_Layer1'}[kind]])[i][4] & 0xF
                occ = _occupied(g, ts)
                if occ.sum() == 0:          # nothing solid (backdrop-only scene): one cell at the origin
                    occ = np.zeros((1, 1), bool)
                    occ[0, 0] = True
                write_obj(os.path.join(outdir, '%s_%03X.obj' % (kind, i)), occ)
                n += 1
    return n
