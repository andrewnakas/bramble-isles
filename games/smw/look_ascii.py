"""Dev: ASCII dump of tile rows. usage: look_ascii assets.dat sheet(hex) row0-row1"""
import sys
from games.smw import layout as L
from games.smw.look_sheets import sheets
from cleanroom.snes import tiles

path, sid, rr = sys.argv[1], int(sys.argv[2], 16), [int(x) for x in sys.argv[3].split('-')]
im = tiles.sheet(tiles.decode(sheets(path)[sid], L.BPP[sid]))
CH = ' .#o45678'
for r in range(rr[0], rr[1] + 1):
    print('--- sheet %02X row %d (tiles %02X..)' % (sid, r, r * 16))
    for y in range(r * 8, r * 8 + 8):
        print('|'.join(''.join(CH[v] for v in im[y, x:x + 8]) for x in range(0, 128, 8)))
