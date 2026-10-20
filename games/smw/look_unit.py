"""Dev: hex dump of 16x16 units side by side. usage: look_unit assets.dat sheet(hex) unit[,unit..]"""
import sys
from games.smw import layout as L
from games.smw.look_sheets import sheets
from cleanroom.snes import tiles

path, sid, us = sys.argv[1], int(sys.argv[2], 16), [int(x) for x in sys.argv[3].split(',')]
im = tiles.sheet(tiles.decode(sheets(path)[sid], L.BPP[sid]))
for k in range(0, len(us), 6):
    row = us[k:k + 6]
    print('   '.join('unit %-11d' % u for u in row))
    for y in range(16):
        print('   '.join(''.join('.123456789ABCDEF'[v] for v in im[u // 8 * 16 + y, u % 8 * 16:u % 8 * 16 + 16]) for u in row))
