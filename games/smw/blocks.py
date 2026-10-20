"""Map16 block behaviour table for the snesrev/smw port (CODE-DERIVED, no retail data).

How a block acts depends only on its number (and the level tileset for a few numbers);
the picture comes from kMap16Data*. Sources in the C port (D:/n64work/smw/pristine/src):
  smw_00.c RunPlayerBlockCode_EB77 / _00F28C / _00F2C9 / _00F309 / _00F3E9 /
           CheckIfPlayerTouchingHurtBlock / CheckIfBlockWasHit(+_Entry3) / ModifyMap16IDForSpecialBlocks,
           kCheckIfBlockWasHit_DATA_00F05C (bounce kind) + _00F080 (item) + _00F0A4 (hit sides),
           kRunPlayerBlockCode_WaterSlopeMap16Numbers, kSlopeSteepness_e55e/e5c8, kSlopeDataTables_*;
  smw_02.c SpawnBounceSprite, kSpawnBounceSprite_SpriteInBlock, kBounceSpriteGFXRt_Tiles;
  smw_05.c InitializeMap16Pointers (which numbers are common / tileset specific);
  smw_0d.c object routines -> spec/objects.json (python -m games.smw.extract_objects).

API
  cls(block, tileset=0)      -> class name (see CLASSES)
  info(block, tileset=0)     -> dict(cls=..., item=..., hit=..., slope=..., notes=...)
  blocks_of(cls, tileset=0)  -> sorted list of block numbers (0x000-0x1FF)
  slope_mask(block, tileset) -> 16x16 bool numpy array of the solid part (slopes only), else None
  objects()                  -> spec/objects.json (object -> blocks it writes, approximate)
  family(tileset)            -> 'grass' | 'castle' | 'rope' | 'underground' | 'ghost' | 'switch' | 'forest'
  is_common(block)           -> True when the block comes from the shared part of kMap16Data
"""
import os, json

SPEC = os.path.join(os.path.dirname(__file__), 'spec')

CLASSES = {
    'empty': 'air, nothing happens',
    'decor': 'page-0 picture block, passable, no behaviour',
    'water': 'water (swim)', 'lava': 'lava (0x005 kills)',
    'vine': 'climbable vine', 'net': 'climbable net / fence',
    'door': 'door (press up)', 'pswitch_door': 'door that exists only while the blue P switch runs',
    'boss_door': 'castle boss door (page 0 0x09C in tileset 1)',
    'invisible_block': 'invisible block, appears when hit from below (item in info)',
    'pswitch_invisible': 'invisible until the blue P switch runs',
    'coin': 'coin', 'pswitch_coin': 'coin that exists only while the blue P switch runs',
    'dragon_coin': 'big coin, two blocks tall (bottom / top)',
    'midway': 'midway tape (touch = checkpoint + mushroom)',
    'moon': '3-up moon', 'checkpoint_1up': 'hidden 1-up checkpoint (touch all 4 in order)',
    'berry': 'berry Yoshi can eat (0x045 red, 0x046 pink, 0x047 green)',
    'palace_switch': 'switch palace big-switch tiles (act as used block, set switch colour)',
    'ledge': 'solid from above only (platform tops, ledges)',
    'conveyor_ledge': 'ledge that pushes the player (rope tilesets)',
    'note_block': 'bouncy note block', 'turn_block': 'turn block (spin-breakable, may hold an item)',
    'question_block': 'prize block (item in info)', 'side_block': 'block hit from the sides (item in info)',
    'onoff_block': 'ON/OFF switch block', 'glass_block': 'translucent block', 'star_block': 'green star block (coin / 1-up)',
    'throw_block': 'grab-and-throw block', 'muncher': 'hurts on touch (silver P switch turns it into a coin)',
    'used_block': 'used prize block (blue P switch turns it into a coin)', 'cement': 'plain solid block',
    'pipe': 'pipe part (see info notes: which part, enterable or not)',
    'shooter': 'bullet shooter', 'solid': 'solid ground / wall', 'hurt': 'solid block that hurts (spikes)',
    'lava_surface': 'sink-in lava surface (underground tilesets)',
    'slope': 'slope (slope kind in info; slope_mask gives the solid part)',
    'water_slope': 'slope with water above the surface', 'lava_slope': 'sloped lava (underground)',
    'slope_support': 'solid filler below / beside slopes (passes the player to the slope above or below)',
    'kill': 'instant death (lava floor)',
}

# tileset 0..14 -> family; Map16 table used: 0,7,12 grass (0x8B70 inside kMap16Data); 1 castle; 2,6,8 rope;
# 3,9,10,11,14 underground table; 4,5,13 ghost-house table (kInitializeMap16Pointers_TilesetMap16Ptrs).
FAMILY = ['grass', 'castle', 'rope', 'underground', 'switch', 'ghost', 'rope', 'grass', 'rope',
          'underground', 'switch', 'castle', 'forest', 'ghost', 'underground']
MAP16_TABLE = ['kMap16Data', 'kMap16Data_Castle', 'kMap16Data_Rope', 'kMap16Data_Underground',
               'kMap16Data_GhostHouse', 'kMap16Data_GhostHouse', 'kMap16Data_Rope', 'kMap16Data',
               'kMap16Data_Rope', 'kMap16Data_Underground', 'kMap16Data_Underground', 'kMap16Data_Underground',
               'kMap16Data', 'kMap16Data_GhostHouse', 'kMap16Data_Underground']
# FG/BG sheets per tileset (kUploadGraphicsFiles_FGAndBGGFXList): VRAM tiles 0x000 FG1, 0x080 FG2, 0x100 BG1, 0x180 FG3
SHEETS = {0: (0x14, 0x17, 0x19, 0x15), 1: (0x14, 0x17, 0x1B, 0x18), 2: (0x14, 0x17, 0x1B, 0x16),
          3: (0x14, 0x17, 0x0C, 0x1A), 4: (0x14, 0x17, 0x1B, 0x08), 5: (0x14, 0x17, 0x0C, 0x07),
          6: (0x14, 0x17, 0x0C, 0x16), 7: (0x14, 0x17, 0x1B, 0x15), 8: (0x14, 0x17, 0x19, 0x16),
          9: (0x14, 0x17, 0x0D, 0x1A), 10: (0x14, 0x17, 0x1B, 0x08), 11: (0x14, 0x17, 0x1B, 0x18),
          12: (0x14, 0x17, 0x19, 0x1F), 13: (0x14, 0x17, 0x0D, 0x07), 14: (0x14, 0x17, 0x19, 0x1A)}

ITEMS = ['none', 'mushroom', 'flower', 'star', 'feather', '1up', 'coin', 'multi_coin', 'vine', 'none9',
         'pswitch', 'pballoon', 'yoshi_egg', 'green_shell', 'changing_item', 'directional_coins', 'key']
_BOUNCE = ['turn_block', 'note_block', 'question_block', 'side_block', 'glass_block', 'onoff_block', 'turn_block']
# kCheckIfBlockWasHit_DATA_00F05C / _00F080 / _00F0A4, index = block - 0x111 (0..28), 29..32 = page-0 0x021..0x024,
# 34, 35 = 0x16A, 0x16B (tilesets whose kInitializeLevelRAM_DATA_00A625 & 3 == 0)
_HIT_KIND = [0x1, 0x5, 0x1, 0x2, 0x1, 0x1, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x6, 0x2, 0x2, 0x2, 0x2, 0x2, 0x2,
             0x2, 0x2, 0x2, 0x2, 0x2, 0x3, 0x3, 0x4, 0x2, 0x2, 0x2, 0x1, 0x1, 0x7, 0x11, 0x10]
_HIT_ITEM = [0x80, 0x0, 0x0, 0x1e, 0x0, 0x0, 0x5, 0x9, 0x6, 0x81, 0xe, 0xc, 0x14, 0x0, 0x5, 0x9, 0x6, 0x7, 0xe, 0xc,
             0x16, 0x18, 0x1a, 0x1a, 0x0, 0x9, 0x0, 0x0, 0xff, 0xc, 0xa, 0x0, 0x0, 0x0, 0x8, 0x2]
_HIT_SIDES = [0xc, 0x8, 0xc, 0x8, 0xc, 0xf, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8,
              0x8, 0x8, 0x8, 0x8, 0x8, 0x3, 0x3, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x4, 0x8, 0x8]
_SIDES = {8: 'below', 4: 'above', 0xc: 'above+below', 3: 'left+right', 0xf: 'all'}
WATER_SLOPES = {0x100 | v for v in (0x71, 0x72, 0x76, 0x77, 0x7b, 0x7c, 0x81, 0x86, 0x8a, 0x8b, 0x8f, 0x90, 0x94, 0x95,
                                     0x99, 0x9a, 0x9e, 0x9f, 0xa3, 0xa4, 0xa8, 0xa9, 0xad, 0xae, 0xb2, 0xb3)}
# kInitializeMap16Pointers_DATA_0581BB: bit set = block taken from the shared part of kMap16Data
_COMMON_MASK = [0xff] * 14 + [0xe0] + [0] * 17 + [0xfe, 0x0, 0x7f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
                                                   0xe0, 0x0, 0x0, 0x3] + [0xff] * 18
_A625 = [0x0, 0x80, 0x40, 0x0, 0x1, 0x2, 0x40, 0x0, 0x40, 0x0, 0x0, 0x0, 0x0, 0x2, 0x0, 0x0]
_PIPE = {0x133: 'vertical pipe end, left half (not enterable)', 0x134: 'vertical pipe end, right half (not enterable)',
         0x135: 'vertical pipe shaft, left', 0x136: 'vertical pipe shaft, right',
         0x137: 'vertical pipe end, left half (ENTERABLE)', 0x138: 'vertical pipe end, right half (ENTERABLE)',
         0x139: 'vertical pipe end, left (small/both-way)', 0x13A: 'vertical pipe end, right (small/both-way)',
         0x13B: 'horizontal pipe end, top row', 0x13C: 'horizontal pipe end, bottom row (not enterable)',
         0x13D: 'horizontal pipe shaft, top row', 0x13E: 'horizontal pipe shaft, bottom row',
         0x13F: 'horizontal pipe end, bottom row (ENTERABLE)',
         0x168: 'vertical pipe shaft, left (pipe object type 5)', 0x169: 'vertical pipe shaft, right (pipe object type 5)'}
_OBJ = None


def family(ts):
    return FAMILY[ts]


def is_common(block):
    return bool(_COMMON_MASK[block >> 3] & (0x80 >> (block & 7)))


def _steep(ts):
    d = objects()['slopes']
    return d['kSlopeSteepness_e5c8'] if ts in (0, 7) else d['kSlopeSteepness_e55e']


def info(block, ts=0):
    page, lo = block >> 8, block & 0xFF
    r = {'cls': 'decor' if page == 0 else 'solid'}
    if page == 0:
        if lo <= 3: r['cls'] = 'water'
        elif lo <= 5: r['cls'] = 'lava'
        elif lo == 6: r['cls'] = 'vine'
        elif lo <= 0x1C: r['cls'] = 'net'
        elif lo in (0x1F, 0x20): r.update(cls='door', notes='top (small player only)' if lo == 0x1F else 'bottom')
        elif 0x21 <= lo <= 0x24:
            k = lo - 4             # CheckIfBlockWasHit_Entry3(lo - 4): table index 29..32
            r.update(cls='invisible_block', hit_kind=_BOUNCE[_HIT_KIND[k]] if _HIT_KIND[k] < 7 else 'brick',
                     item=_item(_HIT_ITEM[k]))
        elif lo == 0x25: r['cls'] = 'empty'
        elif lo in (0x27, 0x28): r['cls'] = 'pswitch_door'
        elif lo == 0x29: r['cls'] = 'pswitch_invisible'
        elif lo == 0x2A: r['cls'] = 'pswitch_coin'
        elif lo in (0x2B, 0x2C): r['cls'] = 'coin'
        elif lo in (0x2D, 0x2E): r.update(cls='dragon_coin', notes='bottom' if lo == 0x2D else 'top')
        elif lo == 0x38: r['cls'] = 'midway'
        elif lo == 0x6E: r['cls'] = 'moon'
        elif 0x6F <= lo <= 0x72: r.update(cls='checkpoint_1up', notes='order %d' % (lo - 0x6F))
        elif 0xEC <= lo <= 0xFB: r['cls'] = 'palace_switch'
        elif lo == 0x9C and ts == 1: r['cls'] = 'boss_door'
        elif 0x45 <= lo <= 0x47: r.update(cls='berry', notes=['red', 'pink', 'green'][lo - 0x45])
        return r
    if lo <= 0x10:
        r['cls'] = 'conveyor_ledge' if (ts in (2, 8) and lo in (0x0C, 0x0D)) else 'ledge'
    elif lo <= 0x2D:
        k = lo - 0x11
        r.update(cls=_BOUNCE[_HIT_KIND[k]], item=_item(_HIT_ITEM[k]), hit=_SIDES.get(_HIT_SIDES[k], hex(_HIT_SIDES[k])))
        if block == 0x11E: r['notes'] = 'plain turn block, spin-breakable'
        if block == 0x12D: r.update(cls='star_block', item='coin_or_1up')
    elif lo == 0x2E: r['cls'] = 'throw_block'
    elif lo == 0x2F: r['cls'] = 'muncher'
    elif lo in (0x30, 0x31): r['cls'] = 'cement'
    elif lo == 0x32: r['cls'] = 'used_block'
    elif block in _PIPE: r.update(cls='pipe', notes=_PIPE[block])
    elif lo in (0x40,): r['cls'] = 'solid'
    elif 0x41 <= lo <= 0x43: r.update(cls='shooter', notes=['top', 'middle', 'bottom'][lo - 0x41])
    elif lo < 0x6E:
        if FAMILY[ts] == 'castle' and ts == 1 and (0x59 <= lo <= 0x5C or 0x66 <= lo <= 0x69): r['cls'] = 'hurt'
        elif ts in (5, 13) and 0x59 <= lo <= 0x5B: r['cls'] = 'hurt'
        elif ts in (3, 14) and 0x59 <= lo <= 0x5B: r['cls'] = 'lava_surface'
        elif lo in (0x6A, 0x6B) and (_A625[ts] & 3) == 0:
            k = 34 + lo - 0x6A
            r.update(cls='turn_block', item=_item(_HIT_ITEM[k]), hit='below', notes='hidden-item block (bounce looks like a turn block)')
    elif lo < 0xD8:
        k = _steep(ts)[lo - 0x6E]
        r.update(cls='water_slope' if block in WATER_SLOPES else 'slope', slope=k)
        if ts in (3, 14) and lo >= 0xD2: r['cls'] = 'lava_slope'
    elif lo < 0xFB: r['cls'] = 'slope_support'
    else: r['cls'] = 'kill'
    return r


def _item(v):
    if v == 0xff: return 'coin_or_1up'
    if v & 0x80: return 'varies_by_x' + ('_b' if v & 1 else '_a')
    s = ITEMS[v >> 1]
    return s + ('_or_mushroom' if (v & 1) and (v >> 1) != 3 else '')


def cls(block, ts=0):
    return info(block, ts)['cls']


def blocks_of(c, ts=0):
    return [b for b in range(0x200) if cls(b, ts) == c]


def objects():
    global _OBJ
    if _OBJ is None:
        _OBJ = json.load(open(os.path.join(SPEC, 'objects.json')))
    return _OBJ


def slope_shape(k):
    """16 surface heights (signed) for slope kind k (kSlopeDataTables_ShapeOfSlope)."""
    sh = objects()['slopes']['kSlopeDataTables_ShapeOfSlope'][16 * k:16 * k + 16]
    return [v - 256 if v > 127 else v for v in sh]


def slope_mask(block, ts=0):
    import numpy as np
    r = info(block, ts)
    if 'slope' not in r:
        return None
    k = r['slope']
    sh = slope_shape(k)
    y = np.arange(16)[:, None]
    s = np.array(sh)[None, :]
    if 18 <= k <= 23:                    # ceiling slopes: solid above the line
        return y < 16 + s
    return y >= s


if __name__ == '__main__':
    import collections
    for ts in (0, 1, 3, 5):
        c = collections.Counter(cls(b, ts) for b in range(0x200))
        print('tileset %d (%s):' % (ts, FAMILY[ts]), ', '.join('%s %d' % kv for kv in sorted(c.items())))
    for b in (0x111, 0x113, 0x117, 0x11E, 0x11F, 0x124, 0x12D, 0x137, 0x16E, 0x022):
        print(hex(b), info(b))
    print('common blocks:', sum(is_common(b) for b in range(0x200)))
