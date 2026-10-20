"""CLEAN ROOM. Formats of the port's text-bearing entries (structure only, no data):
stripe images, the message-box blob, level-name fragments, the layer-3 message font charmap.

Charmap = which tile code the message font (layer-3 sheet 0x2A, tiles 0x100-0x17F, so a code is
written with property byte 0x39) uses for which letter. It is a structural fact of the font
layout; the glyph shapes themselves are drawn by the sprites worker.
"""
import struct

# message font (tile code & 0x7F, layer-3 tile 0x100 + code)
MSG_CHARS = {}
for _i, _c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ!.-,? '):
    MSG_CHARS[_c] = _i
for _i, _c in enumerate('abcdefghijklmnopqrstuvwxyz#()\''):
    MSG_CHARS[_c] = 0x40 + _i
for _i, _c in enumerate('12345670'):
    MSG_CHARS[_c] = 0x64 + _i
MSG_SPACE = 0x1F
MSG_DECODE = {v: k for k, v in MSG_CHARS.items()}

# status-bar / HUD font (layer-3 sheet 0x28, tiles 0x00-0x7F): 0-9 then A-Z, punctuation
HUD_CHARS = {c: i for i, c in enumerate('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')}
HUD_CHARS.update({'.': 0x24, ',': 0x25, '-': 0x27, '!': 0x28, ':': 0x78, "'": 0x85, '"': 0x86, ' ': 0xFC})
HUD_DECODE = {v: k for k, v in HUD_CHARS.items()}
HUD_DECODE[0x26] = 'x'

# bold menu font (file select, player select, prompts): sparse layer-3 tiles (full tile number)
BOLD_CHARS = {'A': 0x171, 'B': 0x12C, 'C': 0x12D, 'D': 0x07C, 'E': 0x173, 'G': 0x175, 'H': 0x084, 'I': 0x082,
              'L': 0x170, 'M': 0x176, 'N': 0x079, 'O': 0x07A, 'P': 0x16F, 'R': 0x174, 'S': 0x131, 'T': 0x12F,
              'U': 0x07B, 'V': 0x080, 'W': 0x081, 'Y': 0x172, 'Z': 0x121, '>': 0x12E, ' ': 0x0FC}
BOLD_CHARS.update({str(d): 0x122 + d for d in range(10)})
BOLD_CHARS.update({':': 0x0B7, 'F': 0x0B8, 'J': 0x0B9, 'K': 0x0BA, 'Q': 0x0BB, 'X': 0x0BC})  # drawn by `sprites`
BOLD_MENU_DIGITS = {'1': 0x16D, '2': 0x16E}          # the player-select digits
BOLD_DECODE = {v: k for k, v in BOLD_CHARS.items()}
BOLD_DECODE.update({0x130: 'N', 0x083: 'O', 0x16D: '1', 0x16E: '2', 0x024: '.'})

# big two-row font (credits names, layer-3 tiles 0xC0-0xFF): top tile, bottom = top + 0x10
BIG_CHARS = {c: 0xC0 + i for i, c in enumerate('ABCDEFGHIJKLMNOP')}
BIG_CHARS.update({c: 0xE0 + i for i, c in enumerate('QRSTUVWXYZ-.')})
BIG_CHARS[' '] = 0xFC
BIG_DECODE = {v: k for k, v in BIG_CHARS.items()}


def enc(table, s, what='text'):
    try:
        return [table[c] for c in s]
    except KeyError as e:
        raise ValueError('%s: letter %r has no code in this font (%r)' % (what, e.args[0], s)) from None


def msg_encode(s):
    """str -> list of codes (no terminator bit)."""
    try:
        return [MSG_CHARS[c] for c in s]
    except KeyError as e:
        raise ValueError('letter %r has no message-font code' % e.args[0]) from None


def msg_decode(codes):
    return ''.join(MSG_DECODE.get(c & 0x7F, '~') for c in codes)


# ---------------------------------------------------------------- stripe images
def stripe_parse(blob):
    """-> list of segments dict(addr, vert, rle, data=list of 16-bit words), and the tail bytes
    after the 0xFF terminator (kept as is)."""
    segs, p = [], 0
    while p < len(blob) and not blob[p] & 0x80:
        addr = blob[p] << 8 | blob[p + 1]
        vert, rle = bool(blob[p + 2] & 0x80), bool(blob[p + 2] & 0x40)
        n = ((blob[p + 2] & 0x3F) << 8 | blob[p + 3]) + 1
        p += 4
        if rle:
            w = struct.unpack_from('<H', blob, p)[0]
            segs.append(dict(addr=addr, vert=vert, rle=True, n=n, data=[w]))
            p += 2
        else:
            segs.append(dict(addr=addr, vert=vert, rle=False, n=n,
                             data=list(struct.unpack_from('<%dH' % (n // 2), blob, p))))
            p += n
    return segs, blob[p:]


def stripe_build(segs, tail=b'\xff'):
    out = bytearray()
    for s in segs:
        n = s['n'] if s['rle'] else 2 * len(s['data'])
        out += bytes([s['addr'] >> 8, s['addr'] & 0xFF,
                      (0x80 if s['vert'] else 0) | (0x40 if s['rle'] else 0) | ((n - 1) >> 8 & 0x3F), (n - 1) & 0xFF])
        out += struct.pack('<%dH' % len(s['data']), *s['data'])
    return bytes(out) + tail


def is_layer3(addr):
    return 0x5000 <= addr < 0x6000


def msg_letter(word):
    """True if a layer-3 tilemap word shows a message-font letter/digit/punctuation (not space)."""
    t = word & 0x3FF
    return 0x100 <= t < 0x180 and (t & 0x7F) in MSG_DECODE and (t & 0x7F) != MSG_SPACE


def hud_letter(word):
    t = word & 0x3FF
    return t < 0x24


# ---------------------------------------------------------------- message blob
def msg_lines(blob, start, nlines=8, width=18):
    """Decode one message box exactly as the game reads it: nlines rows, each ends at a byte
    with bit 7 set (or after width bytes are drawn the reading still continues to the end bit)."""
    rows, p = [], start
    for _ in range(nlines):
        row = []
        while p < len(blob):
            b = blob[p]
            p += 1
            row.append(b & 0x7F)
            if b & 0x80:
                break
        rows.append(row)
    return rows, p


# message start offsets: code-side table kDisplayMessage_DATA_05A5A7 (smw_05.c), fixed
MSG_STARTS = [0x8d, 0x8d, 0x8d, 0x8d, 0x0, 0x291, 0x41d, 0x518, 0x61d, 0x8b7, 0x7b2, 0x30b, 0x83c, 0x99d,
              0xa9e, 0x4a0, 0xa2c, 0x6a6, 0x730, 0x911, 0x5a4, 0x38f, 0x109, 0x20a, 0x191]
MSG_BLOB_SIZE = 2854


def msg_slots():
    """-> sorted list of (start, end) of distinct message slots in the blob."""
    st = sorted(set(MSG_STARTS))
    return [(a, (st[i + 1] if i + 1 < len(st) else MSG_BLOB_SIZE)) for i, a in enumerate(st)]


def stripe_cells(segs):
    """Simulate segments onto VRAM words -> {word address: tilemap word} (later segments win)."""
    cells = {}
    for s in segs:
        step = 32 if s['vert'] else 1
        if s['rle']:
            w = (s['n'] + 1) // 2
            for k in range(w):
                cells[s['addr'] + k * step] = s['data'][0]
        else:
            for k, v in enumerate(s['data']):
                cells[s['addr'] + k * step] = v
    return cells


def stripe_encode_cells(cells, descending=True):
    """Our own encoding of a cell map: maximal runs of one word along VRAM order become fixed-word
    segments, everything else literal segments; emitted from the highest address down."""
    addrs = sorted(cells)
    runs, i = [], 0
    while i < len(addrs):
        j = i
        while j + 1 < len(addrs) and addrs[j + 1] == addrs[j] + 1 and j + 1 - i < 8000:
            j += 1
        block = [cells[a] for a in addrs[i:j + 1]]
        k = 0
        while k < len(block):
            e = k
            while e + 1 < len(block) and block[e + 1] == block[k]:
                e += 1
            if e - k + 1 >= 3:
                runs.append(dict(addr=addrs[i] + k, vert=False, rle=True, n=2 * (e - k + 1) - 1, data=[block[k]]))
                k = e + 1
                continue
            e = k
            while e + 1 < len(block) and not (e + 3 < len(block) and block[e + 1] == block[e + 2] == block[e + 3]):
                e += 1
            runs.append(dict(addr=addrs[i] + k, vert=False, rle=False, n=2 * (e - k + 1), data=block[k:e + 1]))
            k = e + 1
        i = j + 1
    return sorted(runs, key=lambda r: -r['addr']) if descending else runs
