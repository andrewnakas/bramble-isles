"""LC_LZ2 (Nintendo SNES: SMW, ALttP big-endian-offset variant) codec."""


def decompress(src, pos=0, return_length=False):
    out = bytearray()
    p = pos
    while True:
        b = src[p]; p += 1
        if b == 0xff:
            break
        if (b & 0xe0) != 0xe0:
            cmd, n = b >> 5, b & 0x1f
        else:
            cmd, n = (b >> 2) & 7, ((b & 3) << 8) | src[p]
            p += 1
        n += 1
        if cmd == 0:
            out += src[p:p + n]; p += n
        elif cmd == 1:
            out += bytes([src[p]]) * n; p += 1
        elif cmd == 2:
            a, c = src[p], src[p + 1]; p += 2
            out += bytes([a, c] * (n // 2 + 1))[:n]
        elif cmd == 3:
            a = src[p]; p += 1
            out += bytes((a + i) & 0xff for i in range(n))
        else:
            o = src[p] << 8 | src[p + 1]; p += 2
            for i in range(n):
                out.append(out[o + i])
    return (bytes(out), p - pos) if return_length else bytes(out)


def _emit(out, cmd, n, payload):
    n -= 1
    if n < 32 and cmd != 7:
        out.append(cmd << 5 | n)
    else:
        out.append(0xe0 | cmd << 2 | n >> 8)
        out.append(n & 0xff)
    out += payload


def compress(data):
    """Greedy encoder: byte fill, word fill, increasing fill, back copy, literal."""
    data = bytes(data)
    n = len(data)
    out, lit = bytearray(), bytearray()
    index = {}

    def flush():
        while lit:
            chunk = lit[:1024]
            _emit(out, 0, len(chunk), chunk)
            del lit[:1024]

    i = 0
    while i < n:
        best, kind, arg = 0, None, None
        r = 1
        while i + r < n and r < 1024 and data[i + r] == data[i]:
            r += 1
        if r >= 3:
            best, kind, arg = r, 1, bytes([data[i]])
        if i + 1 < n:
            r = 2
            while i + r < n and r < 1024 and data[i + r] == data[i + (r & 1)]:
                r += 1
            if r >= 4 and r > best + 1:
                best, kind, arg = r, 2, data[i:i + 2]
        r = 1
        while i + r < n and r < 1024 and data[i + r] == (data[i] + r) & 0xff:
            r += 1
        if r >= 3 and r > best:
            best, kind, arg = r, 3, bytes([data[i]])
        key = data[i:i + 4]
        for j in reversed(index.get(key, ())[-24:]):
            r = 4
            while i + r < n and r < 1024 and data[j + r] == data[i + r]:
                r += 1
            if r > best + 1:
                best, kind, arg = r, 4, bytes([j >> 8, j & 0xff])
        if kind is None:
            lit.append(data[i])
            step = 1
        else:
            flush()
            _emit(out, kind, best, arg)
            step = best
        for k in range(i, min(i + step, n - 3)):
            if k < 65536:
                index.setdefault(data[k:k + 4], []).append(k)
        i += step
    flush()
    out.append(0xff)
    return bytes(out)
