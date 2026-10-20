"""Dev: read a ?fram= RAM dump from a headless run and show the loaded level as Map16 numbers.

    python -m games.smw.look_ram <shot dir> [k] [--ascii] [--png out.png]

Prints level mode/screens and an ASCII map (one char per block class); used to check that the
level generator's objects produce the blocks it planned (levels.py expect grid).
"""
import base64
import re
import sys

import numpy as np

STD_HORIZ = [0xc800 + 0x1b0 * i for i in range(32)]
STD_VERT = [0xc800 + 0x200 * i for i in range(28)]


def load(shot, k=0):
    parts = []
    for line in open(shot + '/console.txt', encoding='utf8', errors='replace'):
        m = re.search(r'RAM:%d:(\S+)' % k, line)
        if m and m.group(1) != 'END':
            parts.append(m.group(1))
    return np.frombuffer(base64.b64decode(''.join(parts)), np.uint8)


def level_grid(ram, vertical=False, screens=None):
    """-> (rows, cols) array of 16-bit Map16 numbers for layer 1."""
    mode = ram[0x1928 - 0x1928 + 0x1928] if False else None
    if not vertical:
        n = screens or 32
        g = np.zeros((27, 16 * n), np.int32)
        for s in range(n):
            a = STD_HORIZ[s]
            lo = ram[a:a + 0x1b0].reshape(27, 16).astype(np.int32)
            hi = ram[0x10000 + a:0x10000 + a + 0x1b0].reshape(27, 16).astype(np.int32)
            g[:, s * 16:s * 16 + 16] = lo | hi << 8
        return g
    n = screens or 14
    g = np.zeros((16 * n, 32), np.int32)
    for s in range(n):
        a = STD_VERT[s]
        for half in range(2):
            b = a + half * 256
            lo = ram[b:b + 256].reshape(16, 16).astype(np.int32)
            hi = ram[0x10000 + b:0x10000 + b + 256].reshape(16, 16).astype(np.int32)
            g[s * 16:s * 16 + 16, half * 16:half * 16 + 16] = lo | hi << 8
    return g


def ascii(g, classify=None):
    def ch(v):
        if classify:
            return classify(v)
        if v == 0x25:
            return '.'
        if v < 0x100:
            return 'o' if v == 0x2B else ('~' if v < 0x10 else ':')
        return '#' if v >= 0x130 else ('=' if v < 0x110 else '?')
    return '\n'.join(''.join(ch(v) for v in row) for row in g)


if __name__ == '__main__':
    shot = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0
    ram = load(shot, k)
    vert = '--vert' in sys.argv
    g = level_grid(ram, vert)
    used = np.where((g != 0x25).any(axis=0))[0] if not vert else np.where((g != 0x25).any(axis=1))[0]
    print('ram %d bytes; mode byte $1925=%02X screens $5D=%d' % (len(ram), ram[0x1925], ram[0x5D]))
    if '--ascii' in sys.argv:
        cols = int(ram[0x5D]) * 16 if not vert else g.shape[1]
        print(ascii(g[:, :cols] if not vert else g[:int(ram[0x5D]) * 16]))
