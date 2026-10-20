"""Render level layouts of any smw_assets.dat with the port's own level loader (native build of
games/smw/lvl_render.c against the pristine source), for the generator self-check and the
originality geometry export.

    render(dat, kind, indices) -> {index: (mode, screens, grid)}   grid = int32 Map16 numbers
    kind: 'level' (0-511), 'entrance', 'choco2', 'rollcall'
"""
import os
import subprocess
import tempfile

import numpy as np

SRC = 'D:/n64work/smw/pristine'
EXE = 'D:/n64work/smw/tools/lvl_render.exe'
OBJ = 'D:/n64work/smw/tools/lvlobj'
ZIG = 'C:/Users/andre/.local/zig-x86_64-windows-0.16.0/zig.exe'
SDLI = 'D:/n64work/emsdk/upstream/emscripten/cache/sysroot/include/SDL2'
HERE = os.path.dirname(os.path.abspath(__file__))
VERTICAL = {3, 4, 7, 8, 10, 13}


def exe():
    c = os.path.join(HERE, 'lvl_render.c')
    if os.path.exists(EXE) and os.path.getmtime(EXE) >= os.path.getmtime(c):
        return EXE
    os.makedirs(OBJ, exist_ok=True)
    flags = ['-O1', '-w', '-fno-strict-aliasing', '-I' + SRC, '-I' + SRC + '/src', '-I' + SDLI]
    srcs = [os.path.join(SRC, 'src', f) for f in os.listdir(SRC + '/src') if f.endswith('.c')]
    srcs += [os.path.join(SRC, 'src/snes', f) for f in os.listdir(SRC + '/src/snes') if f.endswith('.c')]
    objs = []
    for s in srcs:
        if os.path.basename(s)[:-2] in ('main', 'opengl', 'glsl_shader', 'config'):
            continue
        o = os.path.join(OBJ, os.path.relpath(s, SRC).replace('\\', '_').replace('/', '_') + '.o')
        if not os.path.exists(o):
            subprocess.run([ZIG, 'cc', '-c'] + flags + [s, '-o', o], check=True)
        objs.append(o)
    subprocess.run([ZIG, 'cc'] + flags + [c] + objs + ['-o', EXE], check=True)
    return EXE


def _grid(lo, hi, mode, screens):
    m16 = lo.astype(np.int32) | hi.astype(np.int32) << 8
    if mode in VERTICAL:
        n = min(screens, 14)
        g = np.zeros((16 * n, 32), np.int32)
        for s in range(n):
            a = s * 0x200
            for half in range(2):
                g[s * 16:s * 16 + 16, half * 16:half * 16 + 16] = m16[a + half * 256:a + half * 256 + 256].reshape(16, 16)
        return g
    n = min(screens, 32)
    g = np.zeros((27, 16 * n), np.int32)
    for s in range(n):
        a = s * 0x1B0
        if a + 0x1B0 > len(m16):
            break
        g[:, s * 16:s * 16 + 16] = m16[a:a + 0x1B0].reshape(27, 16)
    return g


def render(dat, kind, indices):
    out = {}
    indices = list(indices)
    with tempfile.TemporaryDirectory() as td:
        ob = os.path.join(td, 'o.bin')
        for k in range(0, len(indices), 64):
            part = indices[k:k + 64]
            subprocess.run([exe(), dat, ob, kind] + [str(i) for i in part], check=True)
            d = open(ob, 'rb').read()
            rec = 4 + 0x7000
            for j in range(len(part)):
                b = d[j * rec:(j + 1) * rec]
                idx = int.from_bytes(b[:2], 'little')
                mode, screens = b[2], b[3]
                lo = np.frombuffer(b[4:4 + 0x3800], np.uint8)
                hi = np.frombuffer(b[4 + 0x3800:], np.uint8)
                out[idx] = (mode, screens, _grid(lo, hi, mode, screens))
    return out
