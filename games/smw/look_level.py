"""Dev: ASCII of a generated level's planned block grid. usage: look_level <slot hex> [col0] [col1]"""
import sys
from games.smw import levels, assetfile as A
CH = {0x25: '.', 0x100: '=', 0x03F: ':', 0x130: '#', 0x132: 'u', 0x02B: 'o', 0x11E: 't', 0x124: '?', 0x113: 'n',
      0x14B: '|', 0x14C: '|', 0x145: '+', 0x148: '+', 0x1F: 'D', 0x20: 'D', 0x35: 'm', 0x38: 'M', 0x2D: '$', 0x2E: '$'}
slot = int(sys.argv[1], 16)
kept = dict(A.read('games/smw/spec/tables.dat'))
L1, L2, spr, built, stats = levels.build_all(kept)
for s, (kind, lv) in built.items():
    pass
key = next(s for s, (k, lv) in built.items() if slot in [e for e in [s]] or False) if slot in built else None
import json
spec = json.load(open('games/smw/spec/levels.json'))
first = next(e['members'][0] for e in spec['levels'] if slot in e['members'])
kind, lv = built[first]
c0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
c1 = int(sys.argv[3]) if len(sys.argv) > 3 else min(lv.cols, c0 + 120)
print(kind, 'cols', lv.cols, 'spawn', getattr(lv, 'spawn', None), 'goal', getattr(lv, 'goal_col', None))
for r in range(lv.rows):
    print('%2d ' % r + ''.join(CH.get(int(v), '%' if 0x133 <= v <= 0x169 else '*') for v in lv.g[r, c0:c1]))
spr_cols = sorted((s.screen * 16 + s.x, s.num) for s in lv.sprs if c0 <= s.screen * 16 + s.x < c1)
print('sprites', [(c - c0, hex(n)) for c, n in spr_cols])
