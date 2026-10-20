"""Gate exporter for text (same code for the dirty and the clean file).

export(items, outdir) writes outdir/<part>.json, each a list of strings:
messages (one per message box), levelnames (every name the map can show, plus the fragments),
castle (one per castle-fall cutscene), rollcall (one per name segment), credits (one per row),
menus (file select, player select, prompts). Unknown tile codes decode as '~'.
"""
import json
import os
import struct

from games.smw import assetfile as A, textfmt as T


def _msg(words):
    return ''.join(T.MSG_DECODE.get(w & 0x7F, '~') if (w & 0x3FF) >= 0x100 else '~' for w in words)


def _hud(words):
    return ''.join(T.HUD_DECODE.get(w & 0x3FF, '~') for w in words)


def _bold(words):
    def one(w):
        t = w & 0x3FF
        if t == 0xFC:
            return ' '
        return T.BOLD_DECODE.get(t, '~')
    return ''.join(one(w) for w in words)


def messages(it):
    b = it['kDisplayMessage_DATA_05A5D9']
    out = []
    for a, e in T.msg_slots():
        rows, _ = T.msg_lines(b, a)
        out.append(' '.join(T.msg_decode(r).strip() for r in rows if T.msg_decode(r).strip()))
    return out


def levelnames(it):
    S = it['kUpdateLevelName_LevelNameStrings']
    tabs = [struct.unpack('<%dH' % (len(it[n]) // 2), it[n]) for n in
            ('kUpdateLevelName_DATA_049C91', 'kUpdateLevelName_DATA_049CCF', 'kUpdateLevelName_DATA_049CED')]

    def frag(j):
        out = []
        while j < len(S):
            out.append(S[j])
            j += 1
            if out[-1] & 0x80:
                break
        return out
    frags = [[frag(j) for j in t] for t in tabs]
    names = set()
    for v in struct.unpack('<%dH' % (len(it['kLevelNames']) // 2), it['kLevelNames']):
        p, m, x = v >> 8 & 0x7F, v >> 4 & 15, v & 15
        if p >= len(tabs[0]) or m >= len(tabs[1]) or x >= len(tabs[2]):
            continue
        s = []
        if not frags[0][p][0] & 0x80:
            s += frags[0][p]
        if frags[1][m] != [0x9F]:
            s += frags[1][m]
        s += frags[2][x]
        names.add(T.msg_decode(s[:19]).strip())
    return sorted(n for n in names if n) + [T.msg_decode(f).strip() for t in frags for f in t if T.msg_decode(f).strip()]


def credits(it):
    tm = it['kGameMode1B_EndingCinema_Tilemaps']
    rp = struct.unpack('<%dH' % (len(it['kGameMode1B_EndingCinema_RowPointers']) // 2),
                       it['kGameMode1B_EndingCinema_RowPointers'])
    out = []
    for p in rp:
        if tm[p] == 0xFF:
            continue
        n = tm[p + 1]
        ws = struct.unpack_from('<%dH' % (n // 2 + 1), tm, p + 2)
        t = [w & 0x3FF for w in ws if (w & 0x3FF) != 0xFC]
        if t and all(0xC0 <= x < 0x100 for x in t):
            if all((x & 0x10) == 0 for x in t):            # top half rows carry the letter codes
                out.append(''.join(T.BIG_DECODE.get(w & 0x3FF, '~') for w in ws))
        else:
            out.append(_hud(ws))
    return [s.strip() for s in out if s.strip()]


def stripes(it):
    arr = A.unpack_array(it['kLoadStripeImagePtrs'])
    castle, roll, menus = [], [], []
    for c in range(7):
        lines = []
        for l in reversed(range(8)):
            segs, _ = T.stripe_parse(arr[11 + 8 * c + l])
            lines += [_msg(s['data']).strip() for s in segs if not s['rle']]
        castle.append(' '.join(x for x in lines if x))
    for i in range(72, 85):
        segs, _ = T.stripe_parse(arr[i])
        for s in segs:
            if T.is_layer3(s['addr']) and not s['rle'] and all((w & 0x3FF) in T.HUD_DECODE for w in s['data']):
                roll.append(_hud(s['data']).strip())
    for i in (4, 6, 10):
        segs, _ = T.stripe_parse(arr[i])
        menus += [_bold(s['data']).strip() for s in segs if not s['rle']]
    fs = it['kFileSelectText_EraseFile']
    for off in (0, 0xCB):
        segs, _ = T.stripe_parse(fs[off:])
        menus += [_bold(s['data']).strip() for s in segs if not s['rle']]
    return castle, [r for r in roll if r], [m for m in menus if m]


def export(items, outdir):
    os.makedirs(outdir, exist_ok=True)
    castle, roll, menus = stripes(items)
    parts = dict(messages=messages(items), levelnames=levelnames(items), credits=credits(items),
                 castle=castle, rollcall=roll, menus=menus)
    for k, v in parts.items():
        json.dump(v, open(os.path.join(outdir, k + '.json'), 'w', encoding='utf8'), indent=0, ensure_ascii=False)
    return len(parts)


if __name__ == '__main__':          # python -m games.smw.orig_text <assets.dat> <outdir>
    import sys
    n = export(dict(A.read(sys.argv[1])), sys.argv[2])
    print('orig_text: %d files -> %s' % (n, sys.argv[2]))
