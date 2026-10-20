"""Render songs / SFX of an smw_assets.dat offline with the port's own C SPC player.

    python -m games.smw.spc_render <assets.dat> <bank|level|overworld|credits> <slot> [secs] [out.wav]
    python -m games.smw.spc_render <assets.dat> sfx <port> <id> [out.wav]
    render(items, bank, events, frames) -> int16 (n, 2) at 32 kHz, or raises on a player assert

Compiles games/smw/spc_render.c with gcc against the pristine port source once
(D:/n64work/smw/tools/spc_render.exe). Works on any .dat; outputs are only for listening/checks.
"""
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

from games.smw import assetfile as A

SRC = 'D:/n64work/smw/pristine/src'
EXE = 'D:/n64work/smw/tools/spc_render.exe'
BANKS = {'level': 'kSpcLevelMusicBank', 'overworld': 'kSpcOverworldMusicBank', 'credits': 'kSpcCreditsMusicBank'}
HERE = os.path.dirname(os.path.abspath(__file__))


ZIG = 'C:/Users/andre/.local/zig-x86_64-windows-0.16.0/zig.exe'


def _cc():
    import shutil
    if shutil.which('gcc.exe') or shutil.which('gcc.EXE'):
        return ['gcc']
    return [ZIG, 'cc']


def exe():
    c = os.path.join(HERE, 'spc_render.c')
    if not os.path.exists(EXE) or os.path.getmtime(EXE) < os.path.getmtime(c):
        os.makedirs(os.path.dirname(EXE), exist_ok=True)
        r = subprocess.run(_cc() + ['-O2', '-w', '-I' + SRC, '-o', EXE, c, SRC + '/smw_spc_player.c',
                            SRC + '/snes/dsp.c', SRC + '/util.c'], capture_output=True, text=True)
        if r.returncode:
            r = subprocess.run(_cc() + ['-O2', '-w', '-I' + SRC, '-o', EXE, c, SRC + '/smw_spc_player.c',
                                SRC + '/snes/dsp.c'], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-2000:]
    return EXE


def render(items, bank, events, frames):
    """events: [(frame, port, value)]; bank: entry name or short name or None."""
    with tempfile.TemporaryDirectory() as td:
        ups = []
        names = ['kSpcEngine', 'kSpcSamples'] + ([BANKS.get(bank, bank)] if bank else [])
        for n in names:
            p = os.path.join(td, n + '.bin')
            open(p, 'wb').write(items[n])
            ups.append(p)
        out = os.path.join(td, 'o.raw')
        r = subprocess.run([exe(), out, str(frames)] + ups + ['--'] + ['%d:%d:%d' % e for e in events],
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError('spc_render failed (%d): %s' % (r.returncode, r.stderr.strip()[:200]))
        return np.fromfile(out, '<i2').reshape(-1, 2)


def save_wav(path, x, rate=32000):
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.ascontiguousarray(x, '<i2').tobytes())


def level_db(x):
    x = x.astype(np.float64) / 32768
    return 10 * np.log10(np.mean(x ** 2) + 1e-12)


def main(argv):
    items = dict(A.read(argv[1]))
    if argv[2] == 'sfx':
        port, sid = int(argv[3]), int(argv[4])
        x = render(items, 'level', [(5, port, sid)], 200)
        out = argv[5] if len(argv) > 5 else 'sfx_%d_%d.wav' % (port, sid)
    else:
        slot = int(argv[3])
        secs = float(argv[4]) if len(argv) > 4 else 20
        x = render(items, argv[2], [(5, 2, slot)], int(secs * 60))
        out = argv[5] if len(argv) > 5 else '%s_%d.wav' % (argv[2], slot)
    save_wav(out, x)
    print('%s: %.1f s, level %.1f dB' % (out, len(x) / 32000, level_db(x)))


if __name__ == '__main__':
    main(sys.argv)
