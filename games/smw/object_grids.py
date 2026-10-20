"""CODE ONLY: run the port's own level-object routines (native harness, tools/tiles_harness.c)
on one-object levels and collect, per tileset family, what each block number is next to.

    python -m games.smw.object_grids <harness.exe> <any clean smw_assets.dat>
      -> games/smw/spec/object_grids.json

Per block: count of objects that place it, and for each side (u, d, l, r) how often the
neighbour cell is empty (block 0x025 = not written by the object) -- the "open sides" that
tell a top edge from an inside fill, plus the names of the routines that place it.
No retail level data is involved: the levels are synthetic, one object each."""
import sys, os, json, subprocess, collections

OUT = os.path.join(os.path.dirname(__file__), 'spec', 'object_grids.json')
FAMS = {'grass': 0, 'castle': 1, 'rope': 2, 'underground': 3, 'ghost': 5}   # one per Map16 table / object set
SIZES = sorted({h << 4 | w for h in (0, 1, 2, 4) for w in range(16)} | {0x55, 0x77, 0x99, 0xFF, 0x80, 0xC3})


def run(exe, dat, jobs):
    p = subprocess.run([exe, dat], input=''.join('%d %d %d %d %d\n' % j for j in jobs),
                       capture_output=True, text=True, timeout=600)
    grids, cur = [], None
    for ln in p.stdout.splitlines():
        if ln.startswith('G '):
            cur = (tuple(int(v) for v in ln.split()[1:]), [])
            grids.append(cur)
        elif cur is not None and len(ln.split()) == 48 and all(len(t) == 3 for t in ln.split()):
            cur[1].append([int(v, 16) for v in ln.split()])
    return grids, p.returncode


def main(exe, dat):
    routines = json.load(open(os.path.join(os.path.dirname(__file__), 'spec', 'objects.json')))
    res = {}
    for fam, ts in FAMS.items():
        jobs = [(ts, o, s, 3, 8) for o in range(1, 0x40) for s in SIZES]
        jobs += [(ts, 0x100 | e, 0, 3, 8) for e in range(2, 0x98)]
        grids = []
        # run in chunks; a routine that crashes the harness is skipped
        i = 0
        while i < len(jobs):
            chunk = jobs[i:]
            g, rc = run(exe, dat, chunk)
            grids += [x for x in g if len(x[1]) == 27]
            # a job that hung or crashed ends the process: skip it and go on with the rest
            i += len(g) + (1 if rc != 0 or len(g) < len(chunk) else 0)
        st = collections.defaultdict(lambda: {'n': 0, 'u': 0, 'd': 0, 'l': 0, 'r': 0, 'objs': set(), 'nb': collections.Counter()})
        import numpy as np
        seen = set()
        for (t, o, s), g in grids:
            key = (o, str(g))
            if key in seen:
                continue
            seen.add(key)
            H, W = len(g), len(g[0])
            ga = np.array(g)
            for y, x in zip(*np.nonzero(ga != 0x25)):
                    b = g[y][x]
                    e = st[b]
                    e['n'] += 1
                    e['objs'].add(('%02X' % o) if o < 0x100 else ('E%02X' % (o & 0xFF)))
                    for k, (dy, dx) in (('u', (-1, 0)), ('d', (1, 0)), ('l', (0, -1)), ('r', (0, 1))):
                        yy, xx = y + dy, x + dx
                        nb = g[yy][xx] if 0 <= yy < H and 0 <= xx < W else 0x25
                        if nb == 0x25:
                            e[k] += 1
                        else:
                            e['nb'][k + '%03X' % nb] += 1
        out = {}
        for b, e in st.items():
            out['%03X' % b] = {'n': e['n'], 'open': {k: round(e[k] / e['n'], 2) for k in 'udlr'},
                               'objs': sorted(e['objs'])[:12], 'nb': dict(e['nb'].most_common(8))}
        res[fam] = out
        # example layouts: every extended object, standard objects at a few sizes (cells: [x, y, block])
        ex = {}
        for (t, o, s), g in grids:
            if o < 0x100 and s not in (0x00, 0x11, 0x23, 0x44, 0x12, 0x21, 0x03, 0x30, 0x05):
                continue
            ga = np.array(g)
            ys, xs = np.nonzero(ga != 0x25)
            if len(ys) == 0:
                continue
            name = ('%02X_%02X' % (o, s)) if o < 0x100 else ('E%02X' % (o & 0xFF))
            ex[name] = [[int(x - xs.min()), int(y - ys.min()), int(ga[y, x])] for y, x in zip(ys, xs)]
        res[fam + ':layouts'] = ex
        print('%-12s ts %2d: %d grids, %d distinct blocks' % (fam, ts, len(grids), len(out)))
    json.dump(res, open(OUT, 'w'), indent=0)


if __name__ == '__main__':
    main(*sys.argv[1:])
