"""SNES BRR (bit rate reduction) sample codec: 9-byte blocks of 16 samples."""
import numpy as np


def _pred(f, o1, o2):
    if f == 0:
        return 0
    if f == 1:
        return o1 + ((-o1) >> 4)
    if f == 2:
        return o1 * 2 + ((-o1 * 3) >> 5) - o2 + (o2 >> 4)
    return o1 * 2 + ((-o1 * 13) >> 6) - o2 + ((o2 * 3) >> 4)


def _step(nib, shift, f, o1, o2):
    s = (nib << shift) >> 1 if shift <= 12 else (nib >> 3) << 12
    s += _pred(f, o1, o2)
    s = -0x8000 if s < -0x8000 else 0x7fff if s > 0x7fff else s
    return (s & 0x3fff) - (s & 0x4000)


def decode(data, start=0):
    """-> (int16 array, bytes consumed, loop flag). Stops at the end-flag block."""
    out = []
    o1 = o2 = 0
    p = start
    while True:
        h = data[p]
        shift, f = h >> 4, h >> 2 & 3
        for i in range(16):
            b = data[p + 1 + i // 2]
            nib = (b >> 4) if i % 2 == 0 else (b & 15)
            nib = (nib & 7) - (nib & 8)
            s = _step(nib, shift, f, o1, o2)
            o2, o1 = o1, s
            out.append(s * 2)
        p += 9
        if h & 1:
            return np.array(out, np.int16), p - start, bool(h & 2)


def encode(pcm, loop_block=None, raw_blocks=()):
    """int16 PCM (length multiple of 16) -> BRR bytes. `loop_block`: index of the
    block the sample loops back to (None = one-shot). The first block and the loop
    block use filter 0 so the loop does not depend on decoder history."""
    pcm = np.asarray(pcm, np.int64)
    assert len(pcm) % 16 == 0
    nb = len(pcm) // 16
    out = bytearray()
    o1 = o2 = 0
    for b in range(nb):
        x = [int(v) >> 1 for v in pcm[b * 16:b * 16 + 16]]
        flags = (2 if loop_block is not None else 0) | (1 if b == nb - 1 else 0)
        best = None
        filters = (0,) if b == 0 or b == loop_block or b in raw_blocks else (0, 1, 2, 3)
        peak = max(1, max(abs(v) for v in x))
        for f in filters:
            for shift in range(0, 13):
                if f == 0 and (7 << shift) >> 1 < peak // 2 and shift < 12:
                    continue
                a1, a2 = o1, o2
                err = 0
                nibs = []
                for v in x:
                    p = _pred(f, a1, a2)
                    q = ((v - p) << 1) >> shift if shift else (v - p) << 1
                    cands = (q - 1, q, q + 1)
                    bs = be = bn = None
                    for c in cands:
                        c = -8 if c < -8 else 7 if c > 7 else c
                        s = _step(c, shift, f, a1, a2)
                        e = (s - v) * (s - v)
                        if be is None or e < be:
                            be, bs, bn = e, s, c
                    err += be
                    if best is not None and err >= best[0]:
                        break
                    nibs.append(bn)
                    a2, a1 = a1, bs
                else:
                    best = (err, f, shift, nibs, a1, a2)
        _, f, shift, nibs, o1, o2 = best
        out.append(shift << 4 | f << 2 | flags)
        for i in range(8):
            out.append((nibs[2 * i] & 15) << 4 | (nibs[2 * i + 1] & 15))
    return bytes(out)
