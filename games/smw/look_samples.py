"""Dev (reads the dirty file): per instrument sample, retail vs clean level and loop pitch. One line each."""
import sys, struct
import numpy as np
from games.smw import assetfile as A, layout as L
from cleanroom.snes import brr


def samples(path):
    d = dict(A.read(path))['kSpcSamples']
    n0, _ = struct.unpack_from('<HH', d, 0)
    n1, _ = struct.unpack_from('<HH', d, 4 + n0)
    blob = d[8 + n0:8 + n0 + n1]
    out, seen = [], set()
    for i in range(n0 // 4):
        s, l = struct.unpack_from('<HH', d, 4 + i * 4)
        if s in seen:
            continue
        seen.add(s)
        pcm, used, loop = brr.decode(blob, s - L.SAMPLE_BASE)
        out.append((np.asarray(pcm, float), (l - s) // 9 * 16 if loop else None))
    return out


def cyc(x):
    """Cycles in a loop section: strongest FFT bin."""
    sp = np.abs(np.fft.rfft(x - x.mean()))
    return int(sp[1:len(x) // 4].argmax() + 1) if len(x) >= 16 else 0


a, b = samples(sys.argv[1]), samples(sys.argv[2])
db = lambda x: 20 * np.log10(np.sqrt(np.mean(x ** 2)) / 32768 + 1e-9)
for i, ((p, lp), (q, lq)) in enumerate(zip(a, b)):
    line = '%2d len %5d/%5d  rms %6.1f/%6.1f dB  peak %5d/%5d' % (i, len(p), len(q), db(p), db(q), abs(p).max(), abs(q).max())
    if lp is not None:
        line += '  loop %4d: cycles %d/%d  loop rms %6.1f/%6.1f' % (len(p) - lp, cyc(p[lp:]), cyc(q[lq:]), db(p[lp:]), db(q[lq:]))
    print(line)
