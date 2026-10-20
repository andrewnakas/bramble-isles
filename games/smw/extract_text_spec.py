"""DIRTY ROOM. Structural facts of the text-bearing entries -> games/smw/spec/text.json.

    python -m games.smw.extract_text_spec D:/n64work/smw/dirty/smw_assets.dat

Kept (no words, no letters): message slot boundaries; level-name table sizes and, per level,
which fragment slots it combines (slot numbers only) + the spare high bit; credits row grid
(which row slots carry a one-row line or a two-row big line, and their palette byte); the
VRAM address, length and palette of every text segment of the stripe images we own (castle
text, roll-call names, menus); the byte layout of the file-select stripe (where the code
patches in digits). Letters themselves are never written.
"""
import json
import os
import struct
import sys

from games.smw import assetfile as A, textfmt as T

SPEC = os.path.join(os.path.dirname(__file__), 'spec')
HUDTXT = set(range(0x29)) | {0x78, 0x85, 0x86, 0xFC}


def seg_info(s):
    ws = s['data']
    letters = [w for w in ws if (w & 0x3FF) != 0xFC]
    prop = letters[0] >> 8 & 0xFC if letters else 0x38
    return dict(addr=s['addr'], vert=s['vert'], n=len(ws), prop=prop)


def main(path):
    it = dict(A.read(path))
    out = {}
    # ---- messages: boundaries come from the code table; check every slot parses inside its bounds
    b = it['kDisplayMessage_DATA_05A5D9']
    assert len(b) == T.MSG_BLOB_SIZE
    slots = []
    for a, e in T.msg_slots():
        _, p = T.msg_lines(b, a)
        assert p <= e
        slots.append([a, e, [i for i, s in enumerate(T.MSG_STARTS) if s == a]])
    out['msg'] = dict(slots=slots, size=len(b), lines=8, width=18)

    # ---- level names: table sizes + per-level slot triple
    L = struct.unpack('<256H', it['kLevelNames'])
    out['levelnames'] = dict(
        nprefix=len(it['kUpdateLevelName_DATA_049C91']) // 2, nmiddle=len(it['kUpdateLevelName_DATA_049CCF']) // 2,
        nsuffix=len(it['kUpdateLevelName_DATA_049CED']) // 2, blob=len(it['kUpdateLevelName_LevelNameStrings']),
        width=19, levels=[[v >> 8 & 0x7F, v >> 4 & 15, v & 15, v >> 15] for v in L])

    # ---- credits: row grid
    tm = it['kGameMode1B_EndingCinema_Tilemaps']
    rp = struct.unpack('<%dH' % (len(it['kGameMode1B_EndingCinema_RowPointers']) // 2),
                       it['kGameMode1B_EndingCinema_RowPointers'])
    rows, k = [], 0
    while k < len(rp):
        p = rp[k]
        if tm[p] == 0xFF:
            k += 1
            continue
        n = tm[p + 1]
        ws = struct.unpack_from('<%dH' % (n // 2 + 1), tm, p + 2)
        let = [w for w in ws if (w & 0x3FF) != 0xFC]
        big = all(0xC0 <= (w & 0x3FF) < 0x100 for w in let)
        if big:
            rows.append([k, 'big', let[0] >> 8])
            k += 2
        else:
            assert all((w & 0x3FF) in HUDTXT for w in ws)
            rows.append([k, 'line', let[0] >> 8])
            k += 1
    out['credits'] = dict(nrows=len(rp), blob=len(tm), slots=rows)

    # ---- stripe images
    arr = A.unpack_array(it['kLoadStripeImagePtrs'])
    castle = {}
    for i in range(11, 67):
        segs, _ = T.stripe_parse(arr[i])
        castle[i] = [seg_info(s) for s in segs]
        assert all(T.is_layer3(s['addr']) for s in segs)
    roll = {}
    for i in range(72, 85):
        segs, _ = T.stripe_parse(arr[i])
        roll[i] = [seg_info(s) for s in segs if T.is_layer3(s['addr']) and not s['rle']
                   and all((w & 0x3FF) in HUDTXT for w in s['data'])]
    # roll-call room frames on layers 1/2: a fill mask (one fill word per stripe) as address runs
    frames = {}
    for i in range(72, 85):
        segs, _ = T.stripe_parse(arr[i])
        cells = T.stripe_cells([s for s in segs if not T.is_layer3(s['addr'])])
        words = set(cells.values())
        assert len(words) == 1
        runs, a0 = [], None
        for a in sorted(cells):
            if runs and a == runs[-1][0] + runs[-1][1]:
                runs[-1][1] += 1
            else:
                runs.append([a, 1])
        frames[i] = dict(word=words.pop(), runs=runs)
    # message-window clear (stripe 3): rows of layer-3 cells
    cells = T.stripe_cells(T.stripe_parse(arr[3])[0])
    msgclear = []
    for a in sorted(cells):
        r, c = (a - 0x5000) // 32, (a - 0x5000) % 32
        if msgclear and msgclear[-1][0] == r and msgclear[-1][2] == c - 1:
            msgclear[-1][2] = c
        else:
            msgclear.append([r, c, c])
    menus = {}
    for i in (4, 6, 10):
        segs, _ = T.stripe_parse(arr[i])
        menus[i] = [dict(seg_info(s), rle=s['rle'], rle_n=s['n'] if s['rle'] else 0,
                         word=s['data'][0] if s['rle'] else None) for s in segs]
    out['stripes'] = dict(castle=castle, rollcall=roll, menus=menus, frames=frames, msgclear=msgclear)

    # ---- file select: two stripe streams inside one entry (code copies 204 bytes from 0 or 0xCB)
    fs = it['kFileSelectText_EraseFile']
    fsel = []
    for off in (0, 0xCB):
        segs, _ = T.stripe_parse(fs[off:])
        fsel.append(dict(off=off, segs=[dict(seg_info(s), rle=s['rle'], rle_n=s['n'] if s['rle'] else 0,
                                             word=s['data'][0] if s['rle'] else None,
                                             # HUD-font placeholder words the code leaves in place (dots)
                                             keep={j: w for j, w in enumerate(s['data']) if (w & 0x3FF) == 0x24})
                                        for s in segs]))
    out['fileselect'] = dict(size=len(fs), copy=204, streams=fsel)

    # ---- big sprite letters (DrawLoadingLetters): slot counts per word
    out['loading'] = dict(n=len(it['kDrawLoadingLetters_TileData']), mario=list(range(0, 14)),
                          luigi=list(range(0, 8)) + list(range(14, 20)))
    os.makedirs(SPEC, exist_ok=True)
    json.dump(out, open(os.path.join(SPEC, 'text.json'), 'w'), indent=None, separators=(',', ':'))
    print('text.json: %d msg slots, %d named levels, %d credit slots, %d castle stripes, %d roll-call segs, fs %d B' % (
        len(slots), sum(1 for v in L if v & 0x7FFF), len(rows), len(castle), sum(len(v) for v in roll.values()), len(fs)))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'D:/n64work/smw/dirty/smw_assets.dat')
