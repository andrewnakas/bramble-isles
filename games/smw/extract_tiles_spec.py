"""DIRTY ROOM (structural facts only). Reads the retail smw_assets.dat and writes
games/smw/spec/tiles.json for the tiles module:
  - bg_tilemaps: for each layer-2 tilemap table entry with the BG flag: decoded length, hi byte,
    and which tilesets / BG palettes / sky colours the levels pair it with (counts only);
  - anim: gfx33 tile groups that kLevelTileAnimations_FrameData points at (tile numbers only);
  - sizes of the entries this module rebuilds.
No pictures, outlines, colours or arrangements are written."""
import sys, os, json, struct, collections
from games.smw import assetfile as A

SPEC = os.path.join(os.path.dirname(__file__), 'spec')
BGTABLES = ['kLevelData_Layer2', 'kEntranceData_Layer2', 'kChoclateIsland2_Layer2',
            'kRollCallData_Layer2', 'kBufferCreditsBackgrounds_Layer2']


def rle_len(src):
    i = n = 0
    while True:
        r = src[i]; i += 1
        if r & 0x80:
            n += (r & 0x7F) + 1; i += 1
        else:
            n += r + 1; i += r + 1
        if src[i] == 0xFF and src[i + 1] == 0xFF:
            return n, i + 2


SHEETS = {0: (0x14, 0x17, 0x19, 0x15), 1: (0x14, 0x17, 0x1B, 0x18), 2: (0x14, 0x17, 0x1B, 0x16),
          3: (0x14, 0x17, 0x0C, 0x1A), 4: (0x14, 0x17, 0x1B, 0x08), 5: (0x14, 0x17, 0x0C, 0x07),
          6: (0x14, 0x17, 0x0C, 0x16), 7: (0x14, 0x17, 0x1B, 0x15), 8: (0x14, 0x17, 0x19, 0x16),
          9: (0x14, 0x17, 0x0D, 0x1A), 10: (0x14, 0x17, 0x1B, 0x08), 11: (0x14, 0x17, 0x1B, 0x18),
          12: (0x14, 0x17, 0x19, 0x1F), 13: (0x14, 0x17, 0x0D, 0x07), 14: (0x14, 0x17, 0x19, 0x1A)}
MASK = [0xff] * 14 + [0xe0] + [0] * 17 + [0xfe, 0x0, 0x7f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
                                         0xe0, 0x0, 0x0, 0x3] + [0xff] * 18
TSPTR = [0x8b70, 0xbc00, 0xc800, 0xd400, 0xe300, 0xe300, 0xc800, 0x8b70, 0xc800, 0xd400, 0xd400, 0xd400, 0x8b70, 0xe300, 0xd400]


def map16_words(it, addr):
    for base, name in ((0xe300, 'kMap16Data_GhostHouse'), (0xd400, 'kMap16Data_Underground'), (0xc800, 'kMap16Data_Rope'),
                       (0xbc00, 'kMap16Data_Castle'), (0x8000, 'kMap16Data')):
        if addr >= base:
            return struct.unpack_from('<4H', it[name], addr - base)


def rle(src):
    out, i = bytearray(), 0
    while True:
        r = src[i]; i += 1
        if r & 0x80:
            out += bytes([src[i]]) * ((r & 0x7F) + 1); i += 1
        else:
            out += src[i:i + r + 1]; i += r + 1
        if src[i] == 0xFF and src[i + 1] == 0xFF:
            return bytes(out)


def usage(it, out):
    """Which 8x8 tiles of each FG/BG sheet the retail Map16 / BG tilemaps reference (tile numbers only)."""
    use = collections.defaultdict(lambda: {'fg': set(), 'bg': set()})
    for ts, sh in SHEETS.items():
        c, t = 0x8000, TSPTR[ts]
        for b in range(0x200):
            if MASK[b >> 3] & (0x80 >> (b & 7)):
                a = c; c += 8
            else:
                a = t; t += 8
            for w in map16_words(it, a):
                n = w & 0x3FF
                if n < 0x200:
                    use['%02X' % sh[n >> 7]]['fg'].add(n & 0x7F)
    # BG Map16 blocks used by each level BG and the tilesets they are paired with
    l1 = A.unpack_array(it['kLevelData_Layer1'])
    l2 = A.unpack_array(it['kLevelData_Layer2'])
    for k, (a, b) in enumerate(zip(l1, l2)):
        f = it['kLevelData_Layer2_IsBg'][k]
        if not a or not b or not (f & 2):
            continue
        sh = SHEETS.get(a[4] & 0xF)
        dec = rle(b)
        hi = f >> 4
        for i in range(min(len(dec), 864)):
            blk = (dec[i] | hi << 8) & 0x1FF
            for w in struct.unpack_from('<4H', it['kMap16Data'], 0x1100 + 8 * blk):
                n = w & 0x3FF
                if n < 0x200:
                    use['%02X' % sh[n >> 7]]['bg'].add(n & 0x7F)
    return {s: {'fg': sorted(u['fg']), 'bg': sorted(u['bg'])} for s, u in use.items()}


def main(path='D:/n64work/smw/dirty/smw_assets.dat'):
    it = dict(A.read(path))
    out = {'bg_tilemaps': {}, 'sizes': {}}
    for t in BGTABLES:
        arr = A.unpack_array(it[t])
        isbg = it[t + '_IsBg']
        ent = []
        for k, blob in enumerate(arr):
            f = isbg[k] if k < len(isbg) else 0
            if not (f & 2) or not blob:
                ent.append(None)
                continue
            n, used = rle_len(blob)
            ent.append({'flag': f, 'len': n, 'bytes': len(blob)})
        out['bg_tilemaps'][t] = ent
    # level pairing: header of each level's layer-1 data (tileset, BG palette, sky colour)
    l1 = A.unpack_array(it['kLevelData_Layer1'])
    l2 = A.unpack_array(it['kLevelData_Layer2'])
    pair = collections.defaultdict(lambda: collections.Counter())
    uniq = {}
    for k, (a, b) in enumerate(zip(l1, l2)):
        if not a or not (it['kLevelData_Layer2_IsBg'][k] & 2):
            continue
        key = uniq.setdefault(bytes(b), len(uniq))
        pair[key]['ts%d' % (a[4] & 0xF)] += 1
        pair[key]['bgpal%d' % (a[0] >> 5)] += 1
        pair[key]['sky%d' % (a[1] >> 5)] += 1
        pair[key]['fgpal%d' % (a[3] & 7)] += 1
        pair[key].setdefault('entries', [])
    # map each level entry to its unique BG id
    out['level_bg_id'] = [uniq.get(bytes(b)) if (it['kLevelData_Layer2_IsBg'][k] & 2) and b else None
                          for k, b in enumerate(l2)]
    out['bg_pairing'] = {str(k): dict(v) for k, v in pair.items()}
    fd = struct.unpack('<%dH' % (len(it['kLevelTileAnimations_FrameData']) // 2), it['kLevelTileAnimations_FrameData'])
    out['anim'] = [[(a - 0x7D00) // 32 for a in fd[v * 4:v * 4 + 4]] for v in range(len(fd) // 4)]
    for n in ('kMap16Data', 'kMap16Data_Castle', 'kMap16Data_Rope', 'kMap16Data_Underground', 'kMap16Data_GhostHouse',
              'kGfx33', 'kInitializeMode7TilemapsAndPalettes_TilemapData', 'kOwTileAnimations_TileNumbers') + tuple(BGTABLES):
        out['sizes'][n] = len(it[n])
    ow = struct.unpack('<%dH' % (len(it['kOwTileAnimations_TileNumbers']) // 2), it['kOwTileAnimations_TileNumbers'])
    out['ow_anim_src'] = [(a - 0x7D00) // 32 for a in ow]
    out['usage'] = usage(it, out)
    # per 8x8 tile of the sheets that other scenes use as sprite / picture sheets: 0 empty, 1 has
    # clear pixels, 2 fully opaque (one number per tile; no pixels kept)
    from cleanroom.snes import lz2, tiles as TL
    raw = [lz2.decompress(c) for c in A.unpack_array(it['kGraphicsPtrs'])]
    out['tileuse'] = {}
    for s in (0x0D, 0x0E, 0x0F, 0x2C, 0x08, 0x07):
        t = TL.decode(raw[s], 3)
        out['tileuse']['%02X' % s] = ''.join('0' if not x.any() else ('2' if x.all() else '1') for x in t)
    json.dump(out, open(os.path.join(SPEC, 'tiles.json'), 'w'), indent=0)
    for s, u in sorted(out['usage'].items()):
        print('sheet %s: fg %3d tiles, bg %3d tiles' % (s, len(u['fg']), len(u['bg'])))
    for t, e in out['bg_tilemaps'].items():
        print('%-36s %3d entries, %3d BG, unique lens %s' % (t, len(e), sum(1 for x in e if x),
              sorted({x['len'] for x in e if x})))
    print('unique level BGs:', len(uniq))
    for k, v in sorted(out['bg_pairing'].items(), key=lambda kv: int(kv[0])):
        print(' bg', k, {a: b for a, b in v.items() if a.startswith('ts')})
    print('ow anim gfx33 tiles:', sorted(set(out['ow_anim_src'])))


if __name__ == '__main__':
    main(*sys.argv[1:])
