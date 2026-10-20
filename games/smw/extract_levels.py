"""DIRTY ROOM. Structural facts + gameplay anchors of every level, for the level generator.

    python -m games.smw.extract_levels [D:/n64work/smw/dirty/smw_assets.dat]

Writes games/smw/spec/levels.json. Kept per distinct level (slots that share one layout stay
grouped): the 5-byte header (screens, mode, tileset, palettes, music, timer = settings), the
sprite-list header byte, screen exits (screen -> destination, flags) with the KIND of trigger the
retail level had in that screen (door / pipe / other: an anchor type, not a position), how the
level ends (goal tape, keyhole, orb, boss, ...), the roster of sprite numbers it uses (which
enemies fit its sprite graphics set; positions are not kept), and the boss/special sprites whose
positions the code depends on. No object shapes, tile positions or enemy placements are kept.
"""
import json
import os
import struct
import sys
from collections import defaultdict

from games.smw import assetfile as A, lvlfmt as F

SPEC = os.path.join(os.path.dirname(__file__), 'spec')

END_SPRITES = {0x7B: 'goal', 0x0E: 'keyhole', 0x80: 'key', 0x4A: 'orb', 0x29: 'koopakid', 0xA9: 'reznor',
               0xA0: 'bowser', 0xC5: 'bigboo', 0x82: 'bonusgame', 0x60: 'palace_switch'}
# sprites whose position is tied to code or to a layout feature: kept with position (anchors)
ANCHOR_SPRITES = {0x29, 0xA9, 0xA0, 0xC5, 0x89, 0x8C, 0x8D, 0x60, 0x82, 0xC6, 0xC8, 0x19, 0xB9, 0x7C, 0x8A, 0x8B}
# whole-level behaviour sprites (scrolling layers, auto scroll, generators): kept without position
BEHAVIOUR_MIN = 0xC9
DOOR_EXT = set([0x47, 0x48] + list(range(0x98, 0x100)))
GHOST_EXIT_EXT = {0x49}
SWITCH_EXT = {0x8A, 0x8B, 0x8C, 0x8D}


def exit_kind(objs, screen):
    kinds = set()
    for o in objs:
        if o.screen != screen:
            continue
        if o.num == 0 and o.ext in DOOR_EXT:
            kinds.add('door')
        elif o.num == 0x0F and (o.size & 0xF) in (1, 4):
            kinds.add('pipe_v')
        elif o.num == 0x10:
            kinds.add('pipe_h')
        elif o.num == 0 and o.ext in GHOST_EXIT_EXT:
            kinds.add('ghost_exit')
    return sorted(kinds) or ['other']


def main(dat):
    it = dict(A.read(dat))
    L1 = A.unpack_array(it['kLevelData_Layer1'])
    L2 = A.unpack_array(it['kLevelData_Layer2'])
    isbg = it['kLevelData_Layer2_IsBg']
    ranges = F.unpack_blob(it['kLvlSprBlob'])
    ptrs = struct.unpack('<512H', it['kLoadLevel_SpriteDataPtrs'])
    banks = it['kLmSpritePtrBankByte']
    groups = defaultdict(list)
    for i, d in enumerate(L1):
        groups[(bytes(d), bytes(L2[i]), ptrs[i] | banks[i] << 16)].append(i)
    out = []
    for (d1, d2, sp), members in sorted(groups.items(), key=lambda kv: kv[1][0]):
        hdr, objs = F.parse_objects(d1)
        shdr, sprs = F.parse_sprites(F.blob_at(ranges, sp))
        e = {'members': members, 'hdr': hdr.hex(), 'spr_hdr': shdr,
             'mode': hdr[1] & 0x1F, 'tileset': hdr[4] & 0xF, 'screens': (hdr[0] & 0x1F) + 1,
             'empty': len(objs) == 0,
             'layer2': 'bg' if isbg[members[0]] else ('objects' if len(d2) > 6 else 'empty'),
             'exits': [{'screen': o.screen, 'dest': o.extra, 'flags': o.flags, 'kind': exit_kind(objs, o.screen)}
                       for o in objs if o.num == 0 and o.ext == 0],
             'ends': sorted({END_SPRITES[s.num] for s in sprs if s.num in END_SPRITES} |
                            ({'ghost_exit'} if any(o.num == 0 and o.ext in GHOST_EXIT_EXT for o in objs) else set()) |
                            ({'switch'} if any(o.num == 0 and o.ext in SWITCH_EXT for o in objs) else set())),
             'roster': sorted({s.num for s in sprs if s.num not in END_SPRITES and s.num not in ANCHOR_SPRITES
                               and s.num < BEHAVIOUR_MIN}),
             'behaviour': sorted({s.num for s in sprs if s.num >= BEHAVIOUR_MIN}),
             'anchor_sprites': [[s.num, s.screen, s.x, s.y, s.extra] for s in sprs if s.num in ANCHOR_SPRITES],
             'n_sprites': len(sprs)}
        if set(e['ends']) & {'koopakid', 'reznor', 'bigboo', 'bowser'}:
            # boss rooms: the spots the boss code uses (pipe mouths the kids pop out of) are anchors
            e['anchor_pipes'] = [[o.screen * 16 + o.x, o.y, (o.size >> 4) + 1] for o in objs
                                 if e['tileset'] == 1 and o.num == 0x34]
        out.append(e)
    # the sprite lists the code addresses directly (intro scene, Chocolate Island 2 variants)
    special = {}
    for a in [0x07C3EE] + [0x070000 | x for x in (0xd899, 0xd8a1, 0xd8a1, 0xd7e5, 0xd7ea, 0xd825, 0xd84b, 0xd86e, 0xd888)]:
        shdr, sprs = F.parse_sprites(F.blob_at(ranges, a))
        special['%06X' % a] = {'spr_hdr': shdr, 'roster': sorted({s.num for s in sprs}),
                               'anchor_sprites': [[s.num, s.screen, s.x, s.y, s.extra] for s in sprs if s.num in ANCHOR_SPRITES]}

    def scenes(name):
        res = []
        for d in A.unpack_array(it[name]):
            if len(d) < 6:
                res.append(None)
                continue
            hdr, objs = F.parse_objects(d)
            floors = [o.y for o in objs if o.num in (0x14, 0x21) and o.x == 0] or [max([o.y for o in objs] or [24])]
            res.append({'hdr': hdr.hex(), 'screens': (hdr[0] & 0x1F) + 1, 'tileset': hdr[4] & 0xF, 'mode': hdr[1] & 0x1F,
                        'floor': min(floors), 'empty': len(objs) == 0,
                        'buildings': [[o.ext, o.screen * 16 + o.x, o.y] for o in objs if o.num == 0 and o.ext in (0x80, 0x84, 0x85, 0x86)],
                        'exits': [{'screen': o.screen, 'dest': o.extra, 'flags': o.flags}
                                  for o in objs if o.num == 0 and o.ext == 0]})
        return res
    spec = {'levels': out, 'special_sprite_lists': special,
            'entrance_scenes': scenes('kEntranceData_Layer1'),
            'choco2': scenes('kChoclateIsland2_Layer1'),
            'rollcall': scenes('kRollCallData_Layer1')}
    os.makedirs(SPEC, exist_ok=True)
    json.dump(spec, open(os.path.join(SPEC, 'levels.json'), 'w'), indent=0)
    n_real = sum(1 for e in out if not e['empty'])
    print('levels.json: %d distinct layouts (%d non-empty) for 512 slots; exits %d; ends %s' % (
        len(out), n_real, sum(len(e['exits']) for e in out),
        dict((k, sum(k in e['ends'] for e in out)) for k in ['goal', 'keyhole', 'orb', 'koopakid', 'reznor', 'bowser', 'bigboo', 'ghost_exit', 'switch'])))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'D:/n64work/smw/dirty/smw_assets.dat')
