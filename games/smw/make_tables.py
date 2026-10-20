"""DIRTY ROOM. Writes games/smw/spec/tables.dat, the only retail-derived container the clean
generator reads: kept structural tables (taint.KEPT_STRUCTURE: positions, flags, counts, timing)
verbatim, and for every other entry a SHAPE placeholder only: the same byte length filled with
zeros, or for packed arrays the same element count and element lengths filled with zeros.
No regenerated entry's content survives.

    python -m games.smw.make_tables [D:/n64work/smw/dirty/smw_assets.dat]
"""
import os
import sys

from games.smw import assetfile as A, taint as T

SPEC = os.path.join(os.path.dirname(__file__), 'spec')


def shape(v):
    try:
        arr = A.unpack_array(v)
        if arr and A.pack_array(arr) == v:
            return A.pack_array([bytes(len(x)) for x in arr]), 'array'
    except Exception:
        pass
    return bytes(len(v)), 'bytes'


def main(dat):
    out, kinds = [], {'kept': 0, 'array': 0, 'bytes': 0}
    for n, v in A.read(dat):
        if n == 'kRom':
            v = b''
        if n in T.KEPT_STRUCTURE or not v:
            out.append((n, v))
            kinds['kept'] += 1
        else:
            s, k = shape(v)
            out.append((n, s))
            kinds[k] += 1
    p = os.path.join(SPEC, 'tables.dat')
    A.write(p, out)
    print('tables.dat: %d entries (%d kept tables, %d array shapes, %d byte shapes), %d bytes' % (
        len(out), kinds['kept'], kinds['array'], kinds['bytes'], os.path.getsize(p)))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'D:/n64work/smw/dirty/smw_assets.dat')
