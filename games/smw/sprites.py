"""CLEAN ROOM. Module `sprites` of the originality rebuild: characters, sprites, fonts, title.

    build(items, kept, spec_dir) -> {entry: bytes}

Redraws from nothing (every pixel of an owned sheet comes from our drawing code):
  sprite sheets OWN_SHEETS (3bpp), the player sheet kGfx32 (TOBI, 4bpp), the ZEEP slots of kGfx33,
  the layer-3 sheets 28-2B, 2F (fonts, HUD, pictures), our palettes (spr_pal), the title logo stripe.
Structure used (games/smw/spec/sprite_slots.json, from the dirty extractor): sheet sizes, which 8x8
tiles are in use and each 16x16 unit's bounding box. Roles per slot (what a slot is) are our own
labels in spr_roles. Nothing here reads retail pixels, outlines or colours.
"""
import json
import os

import numpy as np

from cleanroom.snes import lz2, tiles
from games.smw import assetfile as A, layout as L
from games.smw import spr_cast as C, spr_pal, spr_roles

OWN_SHEETS = [*range(0x00, 0x07), 0x09, 0x0A, 0x0B, *range(0x10, 0x14), *range(0x20, 0x28), 0x2D, 0x2E, 0x30, 0x31]
LAYER3_SHEETS = [0x28, 0x29, 0x2A, 0x2B, 0x2F]


def apply(i, img, spec):          # legacy hook used by drawn.py: no stamping any more
    return img


def load_slots(spec_dir):
    return json.load(open(os.path.join(spec_dir, 'sprite_slots.json')))


def used_mask(s):
    """Per-pixel mask of the 8x8 tiles in use, sheet shaped."""
    nt = s['bytes'] // tiles.TILE_BYTES[s['bpp']]
    bits = np.unpackbits(np.frombuffer(bytes.fromhex(s['used']), np.uint8))[:nt].astype(bool)
    rows = -(-nt // 16)
    m = np.zeros((rows * 8, 128), bool)
    for t in np.nonzero(bits)[0]:
        m[t // 16 * 8:t // 16 * 8 + 8, t % 16 * 8:t % 16 * 8 + 8] = True
    if m.shape[0] % 16:
        m = np.vstack([m, np.zeros((16 - m.shape[0] % 16, 128), bool)])
    return m


def unit_xy(k):
    return k % 8 * 16, k // 8 * 16


def draw_sheet(sid, s, roles):
    """Index image of one sheet: labelled groups from spr_roles, the rest automatic."""
    h = len(s['units']) // 8 * 16
    img = np.zeros((h, 128), np.uint8)
    done = set()
    rng = np.random.default_rng(0xB5A0 + sid)
    fams = [C.family(rng), C.family(rng)]
    for ent in roles.get(sid, []):
        units, art = spr_roles.render(ent, s, rng)
        x0 = min(unit_xy(u)[0] for u in units)
        y0 = min(unit_xy(u)[1] for u in units)
        for u in units:
            ux, uy = unit_xy(u)
            img[uy:uy + 16, ux:ux + 16] = art[uy - y0:uy - y0 + 16, ux - x0:ux - x0 + 16]
            done.add(u)
    for k, b in enumerate(s['units']):
        if b is None or k in done:
            continue
        ux, uy = unit_xy(k)
        if k in s['opaque']:
            img[uy:uy + 16, ux:ux + 16] = C.interior(16, 16, k, rng)
            continue
        x0, y0, x1, y1 = b
        w, hh = x1 - x0 + 1, y1 - y0 + 1
        edges = {e for e, t in (('T', y0 == 0 and hh >= 6), ('B', y1 == 15 and hh >= 6), ('L', x0 == 0 and w >= 6),
                                ('R', x1 == 15 and w >= 6)) if t}
        art = None
        if edges and len(edges) < 4 and w * hh >= 80:
            art = C.piece(edges, fams[k // 8 % 2], k % 4, rng)
        if art is not None:
            box = np.zeros((16, 16), bool)
            box[y0:y1 + 1, x0:x1 + 1] = True
            img[uy:uy + 16, ux:ux + 16] = np.where(box, art, 0)
        elif w < 5 or hh < 5:          # a thin sliver: our own small figure over the slot's tiles instead
            img[uy:uy + 16, ux:ux + 16] = np.pad(C.auto(12, 12, rng), 2)
        else:
            img[uy + y0:uy + y0 + hh, ux + x0:ux + x0 + w] = C.auto(w, hh, rng)
    img &= np.where(used_mask(s)[:h], 0xFF, 0).astype(np.uint8)
    return img


# 8x8 tiles of sheet 00 that the player routine adds to some poses (kPlayerGFXRt_Tiles, code): TOBI's
# hands / boot tips, drawn in the player palette (row 8: 2 outline, 5 skin, 6 skin shade, 3/4 boot)
PLAYER_EXTRA = {0x0A: 'hand', 0x0B: 'hand', 0x0C: 'hand', 0x0D: 'hand', 0x1A: 'hand', 0x1B: 'boot', 0x20: 'hand',
                0x21: 'hand', 0x22: 'hand', 0x23: 'hand', 0x30: 'boot', 0x31: 'boot', 0x32: 'boot', 0x33: 'boot', 0x7E: 'hand'}
HAND = ["........", "..2222..", ".255552.", ".255552.", ".256652.", "..2222..", "........", "........"]
BOOT = ["........", "........", "..22222.", ".2444332", ".2333332", "..222222", "........", "........"]


def player_extras(img):
    for t, kind in PLAYER_EXTRA.items():
        art = np.array([[0 if c == '.' else int(c) for c in row] for row in (HAND if kind == 'hand' else BOOT)], np.uint8)
        img[t // 16 * 8:t // 16 * 8 + 8, t % 16 * 8:t % 16 * 8 + 8] = art


def encode(img, s):
    nt = s['bytes'] // tiles.TILE_BYTES[s['bpp']]
    out = tiles.encode(tiles.unsheet(img)[:nt], s['bpp'])
    assert len(out) == s['bytes']
    return out


def build(items, kept, spec_dir):
    slots = load_slots(spec_dir)
    slots['_struct'] = json.load(open(os.path.join(spec_dir, 'sprite_struct.json')))
    roles = spr_roles.ROLES
    out = {}
    arr = A.unpack_array(items['kGraphicsPtrs'])
    from games.smw import spr_player, spr_text
    imgs = {sid: draw_sheet(sid, slots['%02X' % sid], roles) for sid in OWN_SHEETS}
    player_extras(imgs[0x00])
    spr_player.paint_ow(imgs[0x10])                         # TOBI walking on the map
    from games.smw import spr_mode7                         # Mode-7 boss sheets + our arrangement table
    imgs[0x0B], imgs[0x21], out['kInitializeMode7TilemapsAndPalettes_TilemapData'] = spr_mode7.build(slots['_struct']['mode7'])
    skip_text = os.environ.get('SPR_SKIP_TEXT')             # dev only: while the text half is being edited
    if not skip_text:
        spr_text.patch_sprite_text(imgs, slots, kept)       # words / numbers inside sprite sheets
    for sid in OWN_SHEETS:
        arr[sid] = lz2.compress(encode(imgs[sid], slots['%02X' % sid]))
    out['kGfx32'] = spr_player.build_sheet(slots['32'], kept)
    out['kGfx33'] = spr_player.patch_gfx33(items['kGfx33'], slots['33'])
    if not skip_text:
        out.update(spr_text.build(items, kept, slots, arr))  # layer-3 sheets go into arr, stripes into out
    out['kGraphicsPtrs'] = A.pack_array(arr)
    out.update(spr_pal.build(items))
    return out
