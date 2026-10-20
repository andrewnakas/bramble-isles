"""Reader/writer for the snesrev port's smw_assets.dat container."""
import struct, hashlib

SIG = b'Smw_v0        \n\0'


def read(path):
    """-> list of (name, bytes) in file order."""
    d = open(path, 'rb').read()
    assert d[:16] == SIG, 'not an smw_assets.dat'
    n, klen = struct.unpack_from('<II', d, 80)
    sizes = struct.unpack_from('<%dI' % n, d, 88)
    p = 88 + 4 * n
    names = d[p:p + klen].split(b'\0')[:n]
    p += klen
    out = []
    for nm, sz in zip(names, sizes):
        p = (p + 3) & ~3
        out.append((nm.decode(), d[p:p + sz]))
        p += sz
    return out


def write(path, items):
    key = b''.join(n.encode() + b'\0' for n, _ in items)
    out = bytearray(SIG + hashlib.sha256(key).digest() + b'\0' * 32)
    out += struct.pack('<II', len(items), len(key))
    out += struct.pack('<%dI' % len(items), *[len(v) for _, v in items])
    out += key
    for _, v in items:
        while len(out) & 3:
            out.append(0)
        out += v
    open(path, 'wb').write(out)


def unpack_array(blob):
    """Inverse of the port's pack_arrays -> list of bytes."""
    if not blob:
        return []
    flags, = struct.unpack_from('<H', blob, len(blob) - 2)
    n = (flags & 0xfff) + 1
    end = len(blob) - 2
    idx = None
    nuniq = n
    if flags & 0x4000:
        nuniq = struct.unpack_from('<H', blob, end - 2)[0] + 1
        end -= 2
        w = 1 if nuniq - 1 <= 255 else 2
        end -= n * w
        idx = list(struct.unpack_from('<%d%s' % (n, 'B' if w == 1 else 'H'), blob, end))
    w = 2 if flags & 0x8000 else 4
    offs = [0] + list(struct.unpack_from('<%d%s' % (nuniq - 1, 'H' if w == 2 else 'I'), blob, 0))
    base = (nuniq - 1) * w
    offs.append(end - base)
    uniq = [blob[base + offs[i]:base + offs[i + 1]] for i in range(nuniq)]
    return [uniq[i] for i in idx] if idx else uniq


def pack_array(arr):
    """Same layout as the port's pack_arrays."""
    if not arr:
        return b''
    back, fst, offs, off = {}, [], [], 0
    for v in arr:
        v = bytes(v)
        k = back.get(v)
        if k is None:
            k = len(offs)
            back[v] = k
            off += len(v)
            offs.append(off)
        fst.append(k)
    del offs[-1]
    flags = len(arr) - 1
    if not offs or offs[-1] < 65536:
        r = [struct.pack('<H', i) for i in offs] + list(back)
        flags |= 0x8000
    else:
        r = [struct.pack('<I', i) for i in offs] + list(back)
    if len(back) != len(arr):
        r.append(struct.pack('<%d%s' % (len(fst), 'B' if len(offs) <= 255 else 'H'), *fst))
        r.append(struct.pack('<H', len(offs)))
        flags |= 0x4000
    r.append(struct.pack('<H', flags))
    return b''.join(r)
