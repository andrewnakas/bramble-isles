"""DEV / dirty-room check (reads the retail meshes in D:/n64work/smw/orig_dirty/levels): for every
generated layout that the originality geometry check flags, try further seeds of the SAME generator
until the layout is clearly different, and record the seed bump in games/smw/level_seeds.json.
Like cleanroom.audio.compose.self_check: retail data only ever rejects an output, it never shapes one.

    python -m games.smw.level_reroll [--max 60]
"""
import json
import os
import random
import sys
import tempfile

from cleanroom.originality import geometry as G
from cleanroom.originality.config import merged
from games.smw import assetfile as A, levels as LV, orig_levels as OL

DIRTY = 'D:/n64work/smw/orig_dirty/levels'
CFG = merged(json.load(open(os.path.join(os.path.dirname(__file__), 'originality.json'))).get('thresholds'))['geometry']


def score(lv, key, anchors, td):
    occ = OL._occupied(lv.g, lv.tileset)
    p = os.path.join(td, key)
    OL.write_obj(p, occ)
    a = anchors.get(key)
    import numpy as np
    a = np.asarray(a, float).reshape(-1, 3) if a else None
    return G.compare(G.load_mesh(os.path.join(DIRTY, key)), G.load_mesh(p), a, CFG)


def main(argv):
    mx = int(argv[argv.index('--max') + 1]) if '--max' in argv else 60
    spec = json.load(open(os.path.join(LV.SPEC, 'levels.json')))
    kept = dict(A.read(os.path.join(LV.SPEC, 'tables.dat')))
    anchors = LV.anchor_points(spec, kept)['by_mesh']
    bumps = dict(LV.BUMPS)
    fixed, stuck = [], []
    with tempfile.TemporaryDirectory() as td:
        jobs = []
        for e in spec['levels']:
            if not e['empty']:
                jobs.append(('level_%03X.obj' % e['members'][0], e))
        for key, kind in (('entrance_scenes', 'entrance'), ('rollcall', 'rollcall'), ('choco2', 'choco2')):
            for i, sc in enumerate(spec[key]):
                if sc is not None:
                    jobs.append(('%s_%03X.obj' % (kind, i), (kind, i, sc)))
        for key, e in jobs:
            if not os.path.exists(os.path.join(DIRTY, key)):
                continue
            base = key[:-4]

            def make(b):
                LV.BUMPS[base] = b
                if isinstance(e, tuple):
                    kind, i, sc = e
                    if kind == 'choco2':
                        ee = {'screens': sc['screens'], 'tileset': sc['tileset'], 'mode': sc['mode'], 'ends': [],
                              'exits': [dict(x, kind=['pipe_v']) for x in sc['exits']], 'roster': [],
                              'anchor_sprites': [], 'behaviour': [], 'n_sprites': 0}
                        return LV.gen_course(ee, None, kept, random.Random(LV.SEED + 77 + i + LV.bump(base)), 'room',
                                             spawn={'col': 2, 'xhi': 0, 'row': sc['floor'] - 2, 'screen': 0,
                                                    'action': 0, 'midway': 0})
                    return LV.gen_scene(sc, random.Random(LV.SEED + 31 * i + LV.bump(base)))
                return LV.build_one(e, kept)
            b0 = bumps.get(base, 0)
            lv = make(b0)
            if lv is None or not score(lv, key, anchors, td)['fail']:
                continue
            for b in range(b0 + 1, b0 + mx):
                lv = make(b)
                if not score(lv, key, anchors, td)['fail']:
                    bumps[base] = b
                    fixed.append(base)
                    break
            else:
                stuck.append(base)
            LV.BUMPS[base] = bumps.get(base, 0)
    json.dump(dict(sorted(bumps.items())), open(LV._BUMPS_PATH, 'w'), indent=0)
    print('level_reroll: %d re-seeded, %d still similar %s' % (len(fixed), len(stuck), stuck))


if __name__ == '__main__':
    main(sys.argv)
