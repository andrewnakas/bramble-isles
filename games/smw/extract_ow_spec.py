"""DIRTY ROOM. Overworld structure facts from the retail-derived smw_assets.dat.

    python -m games.smw.extract_ow_spec [D:/n64work/smw/dirty/smw_assets.dat]

Writes games/smw/spec/ow.json with gameplay anchors only:
  nodes   - every walk-stop cell of layer 1 (level tiles, junctions, stars, pipes): x, y, code
  fixed   - cells whose layer-1 code is changed by an event (positions come from the kept
            tables): x, y, code before the change
  segs    - which node connects to which: start node, leave direction, end node (or submap
            exit), arrive direction, the fixed cells passed on the way (with their in/out
            directions), the retail length (a number), and the reveal order: runs of
            [event, fraction of the segment] from the start node (-1 = visible at start)
  hard    - reveal runs for the hard-wired paths (kOwHardcodedPath* tables)
No path cell positions, terrain, tiles or graphics are written.
"""
import json
import os
import sys

import numpy as np

from games.smw import assetfile as A, ow_render as R, ow_walk as Wk

SPEC = os.path.join(os.path.dirname(__file__), 'spec')
DIRS = (0, 2, 4, 6)


def cell_of_l2(off):
    tx, ty = R.l2_pos(off)
    return tx // 2, (ty // 2) if ty < 64 else 32 + (ty - 64) // 2


def event_cells(ow, items):
    """{(x, y): first event that writes layer-2 tiles over that 16x16 cell}"""
    out = {}

    def mark(e, j, r4):
        tx, ty = R.l2_pos(r4)
        n = 2 if j >= 0x900 else 6
        for dy in range(n):
            for dx in range(n):
                x, y = (tx + dx) // 2, ty + dy
                y = y // 2 if y < 64 else 32 + (y - 64) // 2
                out.setdefault((x, y), e)
                order.setdefault((x, y), len(order))
    order = {}
    for e in range(R.NEV):
        for k in range(ow.ptr[e], ow.ptr[e + 1]):
            mark(e, *ow.ent[k])
    ev = items['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles']
    lay = items['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TileLayer']
    num = R.u16(items['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TileNum'])
    loc = R.u16(items['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TilemapLocation'])
    for i in range(len(ev)):
        if lay[i] & 1:
            mark(int(ev[i]), int(num[i]), int(loc[i]))
    event_cells.order = order
    return out


def xy_of_l1(i):
    x = (i & 15) | ((i >> 8) & 1) << 4
    y = ((i >> 4) & 15) | ((i >> 9) & 1) << 4 | ((i >> 10) & 1) << 5
    return x, y


def changed_cells(items):
    """Cells the kept tables change on layer 1 (event tile, silent tiles, destruction)."""
    s = set()
    for i in R.u16(items['kChangingLayer1OverworldTiles_Layer1TileLocation']):
        if i:
            s.add(xy_of_l1(int(i)))
    lay = items['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TileLayer']
    loc = R.u16(items['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TilemapLocation'])
    for i in range(len(lay)):
        if not lay[i] & 1:
            s.add(xy_of_l1(int(loc[i])))
    for i in R.u16(items['kCheckIfDestroyTileEventIsActive_DATA_04E5B6']):
        s.add(xy_of_l1(int(i)))
        s.add(xy_of_l1(int(i) + 16))
    return s


def runs(cells, evc):
    seq = [evc.get(c, -1) for c in cells]
    out = []
    for e in seq:
        if out and out[-1][0] == e:
            out[-1][1] += 1
        else:
            out.append([e, 1])
    n = max(1, len(seq))
    return [[e, round(k / n, 3)] for e, k in out]


def from_b(cells, evc):
    o = [event_cells.order[c] for c in cells if c in event_cells.order]
    return bool(len(o) > 1 and o[0] > o[-1])


def main(dat):
    items = dict(A.read(dat))
    init = R.OW(items)
    g0 = init.l1.copy()
    fin = R.OW(items)
    fin.apply_events(range(R.NEV))
    g1 = fin.l1
    evc = event_cells(init, items)
    chg = changed_cells(items)
    nodes = [[x, y, int(g1[y, x]), int(g0[y, x])] for y in range(64) for x in range(32) if 0x56 <= g1[y, x] < 0x87 or 0x56 <= g0[y, x] < 0x87]
    nodeset = {(x, y) for x, y, _, _ in nodes}
    fixed = [[x, y, int(g0[y, x]), int(g1[y, x])] for x, y in sorted(chg) if (x, y) not in nodeset]
    fixset = {(x, y) for x, y, _, _ in fixed}
    exits = set(items['kOwExitLevelTiles_049426'])
    w = Wk.Walker(g1, Wk.tables_from_items(items))
    segs, seen = [], set()
    for x, y, c, _ in nodes:
        if not (0x56 <= c < 0x87):
            continue
        for j in DIRS:
            r = w.walk(y // 32, (x, y % 32), j)
            if r['reason'] not in ('node', 'exit'):
                continue
            cells = [(cx, cy + 32 * (y // 32)) for cx, cy in r['cells']]
            b = cells[-1] if r['reason'] == 'exit' else (r['end'][0], r['end'][1] + 32 * (y // 32))
            body = cells[:-1] if r['reason'] == 'node' else cells[:-1]
            key = frozenset([(x, y), b]), frozenset(body)
            if key in seen:
                continue
            seen.add(key)
            pts = [(x, y)] + body + [b]

            def d(p, q):
                return {(0, -1): 0, (0, 1): 2, (-1, 0): 4, (1, 0): 6}[(q[0] - p[0], q[1] - p[1])]
            via = [[p[0], p[1], d(pts[i - 1], p), d(p, pts[i + 1])]
                   for i, p in enumerate(pts) if 0 < i < len(pts) - 1 and p in fixset]
            segs.append({'a': [x, y], 'j': j, 'b': list(b), 'arr': d(pts[-2], pts[-1]),
                         'kind': r['reason'], 'via': via, 'len': len(body),
                         'reveal': runs(body, evc), 'from_b': from_b(body, evc), 'bcode': int(g1[b[1], b[0]])})
    hard = harded(items, g0, evc)
    lay = items['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TileLayer']
    num = R.u16(items['kOwEventProcess07_SilentEventsAndEndOfEvent_SilentEventTiles_TileNum'])
    # silent tiles: layer-1 entries keep their tile code (structure); layer-2 entries only say
    # whether the code writes a 6x6 or a 2x2 block (j < 0x900)
    silent = [{'layer': int(lay[i] & 1), 'code': int(num[i]) if not lay[i] & 1 else None,
               'six': bool(lay[i] & 1 and num[i] < 0x900)} for i in range(len(lay))]
    out = {'nodes': nodes, 'fixed': fixed, 'segs': segs, 'hard': hard, 'silent': silent,
           'note': 'DIRTY-derived anchors only (positions, codes, event order); see extract_ow_spec.py'}
    p = os.path.join(SPEC, 'ow.json')
    json.dump(out, open(p, 'w'), indent=0)
    print('wrote %s: %d nodes, %d fixed cells, %d segments, %d hard-wired paths' % (
        p, len(nodes), len(fixed), len(segs), len(hard)))


def translevel_pos(g0):
    """translevel number -> (x, y), numbering as LoadOverworldLayer1AndEvents_04D7F2."""
    flat = R.l1_blob(g0)
    out, r0 = {}, 1
    for j in range(0x800):
        if 0x56 <= flat[j] < 0x81:
            out[r0] = xy_of_l1(j)
            r0 += 1
    return out


def hard_cells(items, g0):
    """Cells of each hard-wired path from its start level (OwProcess03/04 rules)."""
    lv = list(items['kOwHardcodedPathLevel_049078'])
    st = list(items['kOwHardcodedPathStartIndex_04910E'])
    dirs = list(items['kOwHardcodedPathDirs_0490CA'])
    tls = list(items['kOwHardcodedPathTiles_049086'])
    ci2 = R.u16(items['kOwHardcodedPathChocolateIsland2_049082'])
    tp = translevel_pos(g0)
    out = []
    for k in range(len(lv)):
        if lv[k] == 0xff:
            start = (int(ci2[1]) >> 4, int(ci2[0]) >> 4)
        else:
            start = tp[lv[k]]
        end = st[k + 1] if k + 1 < len(st) else len(dirs)
        x, y = start
        cells = []
        for i in range(st[k], end):
            dx, dy = Wk.STEP[dirs[i]]
            x, y = x + dx, y + dy
            cells.append((x, y, tls[i]))
        out.append({'k': k, 'start': list(start), 'cells': cells})
    return out


def harded(items, g0, evc):
    return [{'k': h['k'], 'reveal': runs([(x, y) for x, y, _ in h['cells']], evc)} for h in hard_cells(items, g0)]


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'D:/n64work/smw/dirty/smw_assets.dat')
