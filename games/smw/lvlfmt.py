"""SMW level data formats (from the port's code: LoadLevelHeader, LoadLevelDataObject,
ExtObj00_ScreenExit, ParseLevelSpriteList; blob layout from assets/compile_resources.py).

Layer data:  5-byte header, then 3-byte objects, 0xFF end.
  b0 = N.HH.S.YYYY   N new screen, HH object bits 4-5, S lower sub-screen (+16 rows), Y row
  b1 = LLLL.XXXX     object bits 0-3, column
  b2 = size/type     (extended objects: object 0, b2 = extended number)
  Extended 0x00 (screen exit): b0 & 0x1F = screen, b1 & 1 = exit property, b1 >> 1 = secondary flag,
                              + 1 byte destination level (low byte).
  Extended 0x01 (screen jump): b0 & 0x1F = screen.
Sprite list: 1 header byte, then 3 bytes per sprite, 0xFF end, sorted by screen then x:
  b0 = YYYY.EE.S.Y'  (row = b0 >> 4 | (b0 & 1) << 4, extra bits EE, screen bit 4 = S)
  b1 = XXXX.SSSS     (column, screen bits 0-3)
  b2 = sprite number
"""
import struct
from dataclasses import dataclass, field


@dataclass
class Obj:
    num: int            # 0 = extended (then ext holds the extended number)
    screen: int
    x: int              # column 0-15 in the screen
    y: int              # row 0-31 (bit 4 = lower sub-screen)
    size: int = 0       # b2 for standard objects
    ext: int = None
    extra: int = None   # screen exit: destination level low byte
    flags: int = 0      # screen exit: b1 low bits


@dataclass
class Spr:
    num: int
    screen: int
    x: int
    y: int
    extra: int = 0      # EE bits


def parse_objects(data, start=5):
    """-> (header bytes, [Obj]) ; screen numbers resolved (new-screen bits + screen jumps)."""
    hdr = bytes(data[:start])
    out, p, scr = [], start, 0
    while p < len(data) and data[p] != 0xFF:
        b0, b1, b2 = data[p], data[p + 1], data[p + 2]
        p += 3
        num = (b1 >> 4) | ((b0 & 0x60) >> 1)
        if b0 & 0x80:
            scr += 1
        if num == 0 and b2 == 0:
            o = Obj(0, b0 & 0x1F, 0, 0, ext=0, extra=data[p], flags=b1 & 0xF)
            p += 1
        elif num == 0 and b2 == 1:
            scr = b0 & 0x1F
            o = Obj(0, scr, 0, 0, ext=1)
        elif num == 0:
            o = Obj(0, scr, b1 & 0xF, b0 & 0x1F, ext=b2)
        else:
            o = Obj(num, scr, b1 & 0xF, b0 & 0x1F, size=b2)
        out.append(o)
    return hdr, out


def emit_objects(hdr, objs):
    """Objects in any order -> bytes. Sorted by screen; screen jumps are written where a
    screen is skipped by more than one (new-screen bit for +1)."""
    exits = [o for o in objs if o.num == 0 and o.ext == 0]
    rest = sorted([o for o in objs if not (o.num == 0 and o.ext in (0, 1))], key=lambda o: o.screen)
    out = bytearray(hdr)
    for o in exits:                     # exits carry their own screen and do not move the cursor
        out += bytes([o.screen & 0x1F, o.flags & 0xF, 0, o.extra & 0xFF])
    scr = 0
    for o in rest:
        nb = 0
        if o.screen == scr + 1:
            nb, scr = 0x80, o.screen
        elif o.screen != scr:
            out += bytes([o.screen & 0x1F, 0x00, 0x01])
            scr = o.screen
        num = o.num
        b0 = nb | ((num & 0x30) << 1) | (o.y & 0x1F)
        b1 = ((num & 0xF) << 4) | (o.x & 0xF)
        out += bytes([b0, b1, (o.ext if num == 0 else o.size) & 0xFF])
    out.append(0xFF)
    return bytes(out)


def parse_sprites(data, start=0):
    hdr = data[start]
    p, out = start + 1, []
    while data[p] != 0xFF:
        b0, b1, b2 = data[p], data[p + 1], data[p + 2]
        out.append(Spr(b2, ((b0 << 3) & 0x10) | (b1 & 0xF), b1 >> 4, (b0 >> 4) | ((b0 & 1) << 4), (b0 >> 2) & 3))
        p += 3
    return hdr, out


def emit_sprites(hdr, sprs):
    out = bytearray([hdr])
    for s in sorted(sprs, key=lambda s: (s.screen, s.x)):
        b0 = ((s.y & 0xF) << 4) | ((s.extra & 3) << 2) | (((s.screen >> 4) & 1) << 1) | ((s.y >> 4) & 1)
        out += bytes([b0, ((s.x & 0xF) << 4) | (s.screen & 0xF), s.num])
    out.append(0xFF)
    return bytes(out)


def unpack_blob(blob):
    """-> list of (address, bytes) ranges."""
    n, = struct.unpack_from('<H', blob, 0)
    addrs = [int.from_bytes(blob[2 + 3 * i:5 + 3 * i], 'little') for i in range(n)]
    offs = [int.from_bytes(blob[2 + 3 * n + 3 * i:5 + 3 * n + 3 * i], 'little') for i in range(n)] + [len(blob)]
    return [(addrs[i], blob[offs[i]:offs[i + 1]]) for i in range(n)]


def pack_blob(ranges):
    ranges = sorted(ranges)
    for (a, d), (b, _) in zip(ranges, ranges[1:]):
        assert a + len(d) <= b, 'overlapping blob ranges at %06X' % b
    off = 2 + len(ranges) * 6
    head, offs, body = [], [], []
    for a, d in ranges:
        head.append(a.to_bytes(3, 'little'))
        offs.append(off.to_bytes(3, 'little'))
        body.append(bytes(d))
        off += len(d)
    return struct.pack('<H', len(ranges)) + b''.join(head) + b''.join(offs) + b''.join(body)


def blob_at(ranges, addr):
    for a, d in ranges:
        if a <= addr < a + len(d):
            return d[addr - a:]
    raise KeyError('%06X' % addr)
