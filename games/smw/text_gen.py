"""CLEAN ROOM. All player-readable text of Bramble Isles.

build(items, kept, spec_dir) -> {entry: bytes}. Inputs: our strings (games/smw/text/strings.json)
and structural facts (spec/text.json: slot boundaries, segment addresses, credit row grid, per-level
fragment slot numbers). Retail words never enter: every text byte is encoded from strings.json;
from `items` we only take the parts other workers own (picture segments of mixed stripe images,
the loading-letter slots we do not use).
"""
import json
import os
import struct

from games.smw import assetfile as A, textfmt as T

HERE = os.path.dirname(__file__)
STRINGS = os.path.join(HERE, 'text', 'strings.json')

# kLoadStripeImagePtrs indices whose letters are ours (picture-only stripes belong to `sprites`)
OWNED_STRIPES = {
    'menus': [4, 6, 10],                # game-over choice, player select, overworld save prompt
    'small': [3, 8, 9, 71],             # message-window clear, arrow clear, prompt clear, THE END
    'castle': list(range(11, 67)),      # castle-fall story lines, 7 cutscenes x 8 rows
    'rollcall': list(range(72, 85)),    # cast names (only their layer-3 text segments)
}
ENTRIES = ['kDisplayMessage_DATA_05A5D9', 'kUpdateLevelName_LevelNameStrings', 'kUpdateLevelName_DATA_049C91',
           'kUpdateLevelName_DATA_049CCF', 'kUpdateLevelName_DATA_049CED', 'kLevelNames',
           'kGameMode1B_EndingCinema_Tilemaps', 'kGameMode1B_EndingCinema_RowPointers', 'kLoadStripeImagePtrs',
           'kFileSelectText_EraseFile', 'kDrawLoadingLetters_TileData', 'kDrawLoadingLetters_TileData_BottomTiles',
           'kDrawLoadingLetters_TileData_TopProp', 'kDrawLoadingLetters_TileData_BottomProp']


def load(spec_dir):
    return json.load(open(os.path.join(spec_dir, 'text.json'))), json.load(open(STRINGS, encoding='utf8'))


# ---------------------------------------------------------------- message boxes
def build_messages(spec, S):
    m = spec['msg']
    blob = bytearray([0x80 | T.MSG_SPACE]) * m['size']
    for a, e, ids in m['slots']:
        lines = S['messages'][str(ids[0])]
        assert len(lines) == m['lines'], ids
        out = []
        for ln in lines:
            ln = ln.rstrip()
            assert len(ln) <= m['width'], 'message %s line too long: %r' % (ids, ln)
            c = T.msg_encode(ln) or [T.MSG_SPACE]
            c[-1] |= 0x80
            out += c
        assert len(out) <= e - a, 'message %s: %d B > slot %d B' % (ids, len(out), e - a)
        blob[a:a + len(out)] = bytes(out)
    return bytes(blob)


# ---------------------------------------------------------------- level names
def frag_bytes(s):
    c = T.msg_encode(s)
    c[-1] |= 0x80
    return bytes(c)


def level_parts(F, p, m, x):
    """Our name for a level of this kind -> (zone word, place word, tail word); '' = none."""
    if p == 0:                                          # one-word special stages
        return '', '', F['tails'].get(str(x), F['kind_tails'].get(str(m), ''))
    if str(p) in F['places']:
        return F['places'][str(p)], '', F['tails'].get(str(x), '') if x in (1, 2, 3, 4) else ''
    zone = F['zones'][str(p)]
    if str(m) in F['kinds']:
        tail = F['tails'].get(str(x), '') if F['kinds'][str(m)] == 'NOOK' else ''
        return zone, F['kinds'][str(m)], tail
    nouns = F['nouns'].get('%s:%d' % (zone, m)) or F['nouns'].get(zone) or F['nouns']['*']
    return zone, nouns[max(x - 1, 0) % len(nouns)], ''


def build_levelnames(spec, S):
    """Every level number gets its name from our rules; the three fragment tables are filled in our
    own order (sorted), so the per-level index table is a new assignment, not the old one."""
    ln, F = spec['levelnames'], S['levelnames']
    blank = ln['blob'] - 1                      # code pads names with the fragment at 0x1CB: one blank
    assert blank == 0x1CB
    parts = []
    for lv, (p, mi, x, hi) in enumerate(ln['levels']):
        if str(lv) in F.get('overrides', {}):
            parts.append(tuple(F['overrides'][str(lv)]))
        elif p >= ln['nprefix'] or mi >= ln['nmiddle'] or x >= ln['nsuffix'] or (p | mi | x) == 0:
            parts.append(None)          # level numbers the map never names
        else:
            parts.append(level_parts(F, p, mi, x))
    sizes = (ln['nprefix'], ln['nmiddle'], ln['nsuffix'])
    tabs_s = []
    for k in range(3):
        words = sorted({q[k] for q in parts if q and q[k]})
        assert len(words) + 1 <= sizes[k], 'level names: %d words for %d slots' % (len(words) + 1, sizes[k])
        tabs_s.append([''] + words)
    blob, where = bytearray(), {}

    def place(w, k):
        if not w:
            return blank
        s = w + ' ' if k < 2 else w
        if s not in where:
            where[s] = len(blob)
            blob.extend(frag_bytes(s))
        return where[s]
    tabs = [[place(w, k) for w in tabs_s[k]] + [blank] * (sizes[k] - len(tabs_s[k])) for k in range(3)]
    assert len(blob) <= blank, 'level-name fragments %d B > %d B' % (len(blob), blank)
    blob = bytes(blob) + bytes([0x80 | T.MSG_SPACE]) * (ln['blob'] - len(blob))
    vals, names = [], []
    for q in parts:
        if q is None:
            vals.append(0)
            names.append('')
            continue
        i = [tabs_s[k].index(q[k]) for k in range(3)]
        vals.append(i[0] << 8 | i[1] << 4 | i[2])
        names.append(' '.join(w for w in q if w))
        assert len(names[-1]) <= ln['width'], 'level name too long: %r' % names[-1]
    return {'kUpdateLevelName_LevelNameStrings': blob,
            'kUpdateLevelName_DATA_049C91': struct.pack('<%dH' % sizes[0], *tabs[0]),
            'kUpdateLevelName_DATA_049CCF': struct.pack('<%dH' % sizes[1], *tabs[1]),
            'kUpdateLevelName_DATA_049CED': struct.pack('<%dH' % sizes[2], *tabs[2]),
            'kLevelNames': struct.pack('<%dH' % len(vals), *vals)}, names


# ---------------------------------------------------------------- credits
def build_credits(spec, S, old_size):
    cr = spec['credits']
    assert len(S['credits']) == len(cr['slots']), (len(S['credits']), len(cr['slots']))
    blob = bytearray([0xFF])                    # every empty row points here
    ptrs = [0] * cr['nrows']

    def row(k, words):
        x = (32 - len(words)) // 2
        ptrs[k] = len(blob)
        blob.extend(bytes([x, 2 * len(words) - 1]) + struct.pack('<%dH' % len(words), *words))
    for (k, kind, prop), (skind, text) in zip(cr['slots'], S['credits']):
        assert kind == skind, (k, kind, skind)
        if kind == 'line':
            assert len(text) <= 30
            row(k, [0x00FC if c == ' ' else prop << 8 | t for c, t in zip(text, T.enc(T.HUD_CHARS, text, 'credits'))])
        else:
            assert len(text) <= 28
            codes = T.enc(T.BIG_CHARS, text, 'credits')
            row(k, [0x00FC if c == 0xFC else prop << 8 | c for c in codes])
            row(k + 1, [0x00FC if c == 0xFC else prop << 8 | (c + 0x10) for c in codes])
    assert len(blob) <= old_size, 'credits %d B > %d B' % (len(blob), old_size)
    blob += b'\xff' * (old_size - len(blob))
    return bytes(blob), struct.pack('<%dH' % len(ptrs), *ptrs)


# ---------------------------------------------------------------- stripe images
def seg(addr, words, vert=False):
    return dict(addr=addr, vert=vert, rle=False, n=2 * len(words), data=list(words))


def rle_seg(s):
    return dict(addr=s['addr'], vert=s['vert'], rle=True, n=s['rle_n'], data=[s['word']])


def msg_words(text, prop=0x38):
    return [prop << 8 | 0x100 | c for c in T.msg_encode(text)]


def bold_words(text, prop, digits=None):
    table = dict(T.BOLD_CHARS)
    table.update(digits or {})
    return [0x38FC if c == ' ' else prop << 8 | t for c, t in zip(text, T.enc(table, text, 'menu'))]


def hud_words(text, prop=0x38):
    return [0x00FC if c == ' ' else prop << 8 | t for c, t in zip(text, T.enc(T.HUD_CHARS, text, 'roll-call'))]


def build_castle(spec, S, arr):
    cs = spec['stripes']['castle']
    for c in range(1, 8):
        idx = [11 + 8 * (c - 1) + l for l in range(8)]
        usable = [i for i in reversed(idx) if cs[str(i)]]        # top row (line 7) first
        lines = S['castle'][str(c)]
        assert len(lines) <= len(usable), 'castle %d: %d lines > %d rows' % (c, len(lines), len(usable))
        for i in idx:
            arr[i] = b'\xff'
        for i, text in zip(usable, lines):
            s0 = cs[str(i)][0]
            assert len(text) <= 24, text
            arr[i] = T.stripe_build([seg(s0['addr'], msg_words(text, s0['prop']))])


def build_rollcall(spec, S, arr):
    for key, segspec in spec['stripes']['rollcall'].items():
        i = int(key)
        names = S['rollcall'][key]
        assert len(names) == len(segspec), (i, len(names), len(segspec))
        rows = {}
        text = []
        for s, name in zip(segspec, names):
            row, col = (s['addr'] - 0x5000) // 32, (s['addr'] - 0x5000) % 32
            start = int(round(col + s['n'] / 2 - len(name) / 2))
            assert 0 <= start and start + len(name) <= 32, (i, name)
            for a, b in rows.get(row, []):
                assert start + len(name) <= a or start >= b, 'roll-call %d: %r overlaps' % (i, name)
            rows.setdefault(row, []).append((start, start + len(name)))
            text.append(seg(0x5000 + row * 32 + start, hud_words(name, s['prop'])))
        # the room frame on layers 1/2 (a fill mask around the cast): same cells, our own run layout
        fr = spec['stripes']['frames'][key]
        cells = {a + k: fr['word'] for a, n in fr['runs'] for k in range(n)}
        frame = T.stripe_encode_cells(cells)
        arr[i] = T.stripe_build(frame + text)


def build_menus(spec, S, arr):
    M, ms = S['menus'], spec['stripes']['menus']
    # game-over choice: two rows
    a, b = ms['4']
    arr[4] = T.stripe_build([seg(a['addr'], bold_words(M['gameover'][0], a['prop'])),
                             seg(b['addr'], bold_words(M['gameover'][1], b['prop']))])
    # player select: keep the row clears, then two rows
    segs = [rle_seg(s) for s in ms['6'] if s['rle']]
    rows = [s for s in ms['6'] if not s['rle']]
    for s, text in zip(rows, M['players']):
        assert len(text) <= 16
        segs.append(seg(s['addr'], bold_words(text, M.get('file_prop', 0x38), T.BOLD_MENU_DIGITS)))
    arr[6] = T.stripe_build(segs)
    # overworld save prompt: rows must stay inside what stripe 9 clears (17 / 21 tiles)
    a, b = ms['10']
    assert len(M['save_prompt'][0]) <= 17 and len(M['save_prompt'][1]) <= 21
    arr[10] = T.stripe_build([seg(a['addr'], bold_words(M['save_prompt'][0], a['prop'])),
                              seg(b['addr'], bold_words(M['save_prompt'][1], b['prop']))])


# ---------------------------------------------------------------- file select
def build_fileselect(spec, S):
    fs, M = spec['fileselect'], S['menus']
    out = bytearray()
    for n, st in enumerate(fs['streams']):
        segs = st['segs']
        assert len(out) == st['off']
        # six row clears (36 bytes: the file rows must start at buffer byte 36). Ours start one tile
        # further left (stream 0) or two (stream 1) and run to the same right edge.
        assert all(s['rle'] for s in segs[:6])
        built = [dict(rle_seg(s), addr=s['addr'] - 1 - n, n=s['rle_n'] + 2 + 2 * n, data=[0x3CFC]) for s in segs[:6]]
        prop = M.get('file_prop', 0x38)
        # the three file rows: their byte layout is fixed (the code patches digits into words 11-15)
        for f, s in enumerate(segs[6:9]):
            assert s['n'] == 16
            w = bold_words(M['file_name'].ljust(5)[:5] + ' ' + 'ABC'[f] + ' ', prop)
            w += [s['keep'][str(j)] for j in (8, 9, 10)]
            w += bold_words(M['file_empty'].ljust(5)[:5], prop)
            built.append(seg(s['addr'], w))
        rest = segs[9:]
        if n == 0:          # erase screen: an erase mark beside each file, then the leave choice
            for s in rest[:3]:
                built.append(seg(s['addr'], bold_words(M['erase'], prop)))
            built.append(seg(rest[3]['addr'], bold_words(M['erase_done'], prop)))
            assert len(rest) == 4
        else:               # file select: the erase choice
            # must stay inside what the player-select stripe clears afterwards (row ends at column 19)
            assert len(M['erase_title']) <= rest[0]['n'], M['erase_title']
            built.append(seg(rest[0]['addr'], bold_words(M['erase_title'], prop)))
            assert len(rest) == 1
        b = T.stripe_build(built)
        room = (fs['streams'][1]['off'] if n == 0 else fs['size']) - st['off']
        assert len(b) <= min(room, fs['copy']), 'file select stream %d: %d B > %d B' % (n, len(b), room)
        out += b + b'\xff' * (room - len(b))
    assert len(out) == fs['size']
    return bytes(out)


# ---------------------------------------------------------------- big sprite letters
# 8x16 letter cells from the 24 big-letter pieces of sheet 0F as the sprites worker drew them
# (top piece, top prop, bottom piece, bottom prop); 0x80 = vertical flip, 0xC0 = both flips.
CELLS = {
    'I': (0x00, 0x34, 0x00, 0xB4), 'O': (0x03, 0x34, 0x03, 0xB4), 'G': (0x02, 0x34, 0x12, 0x34),
    'A': (0x03, 0x34, 0x13, 0x34), 'M': (0x04, 0x34, 0x14, 0x34), 'E': (0x05, 0x34, 0x05, 0xB4),
    '!': (0x00, 0x34, 0x10, 0x34), 'P': (0x01, 0x34, 0x11, 0x34), 'R': (0x4C, 0x34, 0x5C, 0x34),
    'U': (0x4A, 0x34, 0x03, 0xB4), 'V': (0x4A, 0x34, 0x5A, 0x34), 'T': (0x4D, 0x34, 0x00, 0xB4),
    'L': (0x4E, 0x34, 0x5E, 0x34), 'S': (0x5D, 0x34, 0x5D, 0xF4), 'B': (0x4C, 0x34, 0x4C, 0xB4),
    'K': (0x5C, 0xB4, 0x5C, 0x34), ' ': (0xFF, 0x34, 0xFF, 0x34),
}
# slot groups as the code reads them (smw_00.c DrawLoadingLetters / death message), each drawn right to left
LOAD_GROUPS = [('shared', range(0, 8)), ('p1', range(8, 14)), ('p2', range(14, 20)),
               ('over_r', range(20, 24)), ('over_l', range(24, 29)), ('time_r', range(29, 33)),
               ('time_l', range(33, 38)), ('bonus', range(38, 52))]


def build_loading(spec, S, items):
    L = S['loading']
    tabs = [bytearray(52) for _ in range(4)]
    assert spec['loading']['n'] == 52
    for key, slots in LOAD_GROUPS:
        word = L[key]
        assert len(word) <= len(slots), (key, word)
        word = word.rjust(len(slots)) if L.get('align_' + key, 'r') == 'r' else word.ljust(len(slots))
        for k, ch in zip(slots, reversed(word)):
            top, tprop, bot, bprop = CELLS[ch]
            tabs[0][k], tabs[1][k], tabs[2][k], tabs[3][k] = top, bot, tprop, bprop
    return {n: bytes(t) for n, t in zip(ENTRIES[10:14], tabs)}


# ---------------------------------------------------------------- small stripes we own
def build_small_stripes(spec, S, arr):
    """71 THE END (big two-row letters), 8 the clear of the free-scroll arrows, 9 the prompt clear."""
    text = S['the_end']
    col = (32 - len(text)) // 2
    codes = T.enc(T.BIG_CHARS, text, 'the end')
    top = [0x20FC if c == 0xFC else 0x2000 | c for c in codes]
    bot = [0x20FC if c == 0xFC else 0x2000 | (c + 0x10) for c in codes]
    arr[71] = T.stripe_build([seg(0x50E0 + col, top), seg(0x5100 + col, bot)])
    # arrows sit in 2x2 tile blocks at (row 6, col 15), (row 14, col 3), (row 14, col 27): clear by columns
    segs = []
    for r, c in ((14, 27), (14, 3), (6, 15)):
        for dc in (1, 0):
            segs.append(dict(addr=0x5000 + 32 * r + c + dc, vert=True, rle=True, n=3, data=[0x3CFC]))
    arr[8] = T.stripe_build(segs)
    # prompt rows 14 / 16 / 17 / 18: cleared from column 3 to 28 (inside the map border)
    segs = []
    for r, c0, c1 in ((18, 3, 28), (17, 3, 28), (16, 3, 28), (14, 3, 28)):
        w = c1 - c0 + 1
        segs.append(dict(addr=0x5000 + 32 * r + c0, vert=False, rle=True, n=2 * w - 1, data=[0x3CFC]))
    arr[9] = T.stripe_build(segs)
    # 3: the message-window clear (layer-3 rows 6-13 from column 7): same cells, split from the bottom up
    segs = [dict(addr=0x5000 + 32 * r + c0, vert=False, rle=True, n=2 * (c1 - c0 + 1) - 1, data=[0x3CFC])
            for r, c0, c1 in reversed(spec['stripes']['msgclear'])]
    arr[3] = T.stripe_build(segs)


# ---------------------------------------------------------------- entry point
def build(items, kept, spec_dir):
    spec, S = load(spec_dir)
    out = {'kDisplayMessage_DATA_05A5D9': build_messages(spec, S)}
    ln, _ = build_levelnames(spec, S)
    out.update(ln)
    out['kGameMode1B_EndingCinema_Tilemaps'], out['kGameMode1B_EndingCinema_RowPointers'] = build_credits(
        spec, S, len(items['kGameMode1B_EndingCinema_Tilemaps']))
    arr = A.unpack_array(items['kLoadStripeImagePtrs'])
    build_castle(spec, S, arr)
    build_rollcall(spec, S, arr)
    build_menus(spec, S, arr)
    build_small_stripes(spec, S, arr)
    out['kLoadStripeImagePtrs'] = A.pack_array(arr)
    out['kFileSelectText_EraseFile'] = build_fileselect(spec, S)
    out.update(build_loading(spec, S, items))
    return out


if __name__ == '__main__':          # dry run against the current clean file: sizes + level names
    import sys
    from collections import Counter
    it = dict(A.read(sys.argv[1] if len(sys.argv) > 1 else 'D:/n64work/smw/clean/smw_assets.dat'))
    spec_dir = os.path.join(HERE, 'spec')
    o = build(it, None, spec_dir)
    for k, v in o.items():
        print('  %-42s %5d B (was %5d)' % (k, len(v), len(it[k])))
    spec, S = load(spec_dir)
    _, names = build_levelnames(spec, S)
    c = Counter(n for n in names if n)
    print('  %d distinct level names; longest %r' % (len(c), max(c, key=len)))
