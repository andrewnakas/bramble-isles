"""Dev: assemble the big sprite words from the kept tables + the tiles of sheet 0F. usage: look_letters assets.dat"""
import sys
import numpy as np
from games.smw import assetfile as A
from games.smw.look_sheets import sheets
from cleanroom.snes import tiles

path = sys.argv[1]
it = dict(A.read(path))
px = tiles.decode(sheets(path)[0x0F], 3)
T, B = it['kDrawLoadingLetters_TileData'], it['kDrawLoadingLetters_TileData_BottomTiles']
TP, BP = it['kDrawLoadingLetters_TileData_TopProp'], it['kDrawLoadingLetters_TileData_BottomProp']


def src(c):
    return (c & 15) + {0x00: 0, 0x10: 6, 0x40: 12 - 10, 0x50: 18 - 10}[c & 0xF0]


def tile(c, prop):
    t = px[src(c)]
    if prop & 0x40:
        t = t[:, ::-1]
    if prop & 0x80:
        t = t[::-1]
    return t


for name, ks in (('MARIO START !', range(13, -1, -1)), ('LUIGI', range(18, 13, -1)), ('GAME OVER', range(28, 19, -1)), ('TIME UP !', range(37, 28, -1))):
    cv = np.zeros((16, 8 * len(ks)), np.uint8)
    for n, k in enumerate(ks):
        if T[k] < 0x80:
            cv[:8, n * 8:n * 8 + 8] = tile(T[k], TP[k])
            cv[8:, n * 8:n * 8 + 8] = tile(B[k], BP[k])
    print(name)
    for r in cv:
        print(''.join(' .#o45678'[v] for v in r))
