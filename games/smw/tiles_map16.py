"""CLEAN ROOM. Map16 assembly for the tiles module: block number -> our own 2x2 tile picture,
chosen from the block's code-derived behaviour (blocks.py) and from where the port's object
routines put it (spec/object_grids.json)."""
import struct
import numpy as np
from games.smw import blocks as B, tilekit as K
from games.smw.tiles import (Data, Store, ANIM, TABLES, FG3_SHEETS, COMP_SHEETS, FG3_COMPONENT, THEME, THEMED,
                             PAL_GROUND, PAL_SECOND, PAL_SLATE, PAL_GREEN, PAL_GOLD, PAL_BERRY,
                             quads, terrain_block, render_class, pic_vine, pic_net, pic_door, pic_dragon, pic_moon,
                             pic_post, pic_berry, pic_palace, pic_glass, pic_star_block, pic_throw, pic_cement,
                             pic_pipe, pic_shooter, pic_spike, pic_leaf, pic_cloud, pic_weed, pic_line, pic_donut, pic_outline)


def pic_thorns():
    p = np.zeros((16, 16), np.uint8)
    y, x = np.mgrid[0:16, 0:16]
    p[:, :] = K.D
    for cx in (2, 7, 12):
        for yy in range(9):
            w = yy * 0.35
            p[yy, max(0, int(cx - w)):int(cx + w) + 1] = K.L if yy < 3 else K.M
    p[(x * 3 + y * 7) % 13 == 0] = K.O
    p[0:2, :][p[0:2, :] == K.D] = 0
    p[K.outline(p > 0) & (y < 9)] = K.O
    return p


def paint_sign(w, h):
    p = np.zeros((h, w), np.uint8)
    p[16:, w // 2 - 2:w // 2 + 2] = K.D; p[16:, w // 2 - 2] = K.O; p[16:, w // 2 + 1] = K.O
    p[2:18, 1:w - 1] = K.M; p[2, 1:w - 1] = K.L
    p[2:18, 1] = K.O; p[2:18, w - 2] = K.O; p[1, 2:w - 2] = K.O; p[18, 2:w - 2] = K.O
    for k in range(5):          # chevron pointing right
        p[6 + k, 10 + k:13 + k] = K.H; p[14 - k, 10 + k:13 + k] = K.H
    p[5, 4:w - 4:5] = K.D
    return p


def paint_window(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(float)
    p = np.zeros((h, w), np.uint8)
    m = (y >= 10) | (((x - (w - 1) / 2) / (w / 2 - 1)) ** 2 + ((y - 10) / 9) ** 2 <= 1)
    m &= (x >= 1) & (x <= w - 2) & (y <= h - 2)
    p[m] = K.D
    inner = (y >= 11) | (((x - (w - 1) / 2) / (w / 2 - 3)) ** 2 + ((y - 11) / 7) ** 2 <= 1)
    inner &= (x >= 3) & (x <= w - 4) & (y <= h - 4)
    p[inner] = K.L
    p[inner & (x + y < 28)] = K.H
    p[:, w // 2 - 1:w // 2 + 1][inner[:, w // 2 - 1:w // 2 + 1]] = K.D
    p[18:20, :][inner[18:20, :]] = K.D
    p[K.outline(m)] = K.O
    return p


def paint_clock(w, h):
    p = np.zeros((h, w), np.uint8)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    r = min(w, h) / 2 - 2
    p[K.disc(max(w, h), cx, cy, r)[:h, :w]] = K.M
    p[K.disc(max(w, h), cx, cy, r - 3)[:h, :w]] = K.H
    for a in range(12):
        t = a * np.pi / 6
        p[int(cy + (r - 5) * np.sin(t)), int(cx + (r - 5) * np.cos(t))] = K.O
    K.line(p, int(cx), int(cy), int(cx), int(cy - r + 8), K.O)
    K.line(p, int(cx), int(cy), int(cx + r - 10), int(cy + 4), K.O)
    p[K.outline(K.disc(max(w, h), cx, cy, r)[:h, :w])] = K.O
    return p


def paint_web(w, h):
    p = np.zeros((h, w), np.uint8)
    for a in np.linspace(0, np.pi / 2, 5):
        K.line(p, 0, 0, int((w - 1) * np.cos(a)), int((h - 1) * np.sin(a)), K.L)
    for rr in (8, 15, 22, 29):
        for a in np.linspace(0, np.pi / 2, 30):
            xx, yy = int(rr * np.cos(a)), int(rr * np.sin(a))
            if xx < w and yy < h:
                p[yy, xx] = K.H
    return p


PICTURES = {'sign': ('E86', PAL_GOLD, paint_sign), 'window': ('E8F', PAL_SLATE, paint_window),
            'clock': ('E61', PAL_GOLD, paint_clock), 'web': ('E65', PAL_SLATE, paint_web)}


class Builder:
    def __init__(self, spec):
        self.d = Data(spec)
        self.st = Store()
        self.fg3_common_next = 0
        self.fg3_comp_next = {c: 127 for c in COMP_SHEETS}
        self.fg3_render = {}     # (space, key) -> (index, (code, mat) or None)
        self.blank = None

    # ---------------- tile helpers
    def px(self, img8, pal, prio=0, group=None):
        t = np.asarray(img8, np.uint8)
        full = not self.st.free['fg1'] and not self.st.free['fg2']
        if full and not any(np.ascontiguousarray(t[::-1 if vf else 1, ::-1 if hf else 1]).tobytes() in self.st.px[g]
                            for g in ('fg1', 'fg2') for hf in (0, 1) for vf in (0, 1)):
            k = np.ascontiguousarray(t).tobytes()          # spill into the shared FG3 region (same in every FG3 sheet)
            return self.fg3key('common', ('px', k), ('px', k), pal) | prio << 13
        g, i, hf, vf = self.st.pixel(group, img8)
        base = 0x080 if g == 'fg2' else 0x000
        return (base + i) | pal << 10 | prio << 13 | hf << 14 | vf << 15

    def fg3key(self, space, key, render, pal, hf=0, vf=0):
        sk = (space, key)
        if sk not in self.fg3_render:
            if space == 'common':
                i = self.fg3_common_next
                if i > min(self.fg3_comp_next.values()):
                    self.st.overflow['fg3:common'] += 1
                    i = 0
                else:
                    self.fg3_common_next += 1
            else:
                i = self.fg3_comp_next[space]
                if i < self.fg3_common_next:
                    self.st.overflow['fg3:' + space] += 1
                    i = 127
                else:
                    self.fg3_comp_next[space] -= 1
            self.fg3_render[sk] = (i, render)
        i = self.fg3_render[sk][0]
        return (0x180 + i) | pal << 10 | hf << 14 | vf << 15

    def anim(self, name, k, pal, hf=0, vf=0):
        return (ANIM[name] + k) | pal << 10 | hf << 14 | vf << 15

    def pic(self, img16, pal, prio=0):
        return [self.px(q, pal, prio) for q in quads(img16)]

    def classmap(self, c16, mat, space, pal):
        """Themed autotile: class map -> 4 FG3 keys (mirrored maps reuse a tile with h-flip)."""
        out = []
        for q in quads(c16):
            code = np.ascontiguousarray(q).tobytes()
            flip = np.ascontiguousarray(q[:, ::-1]).tobytes()
            if (space, ('cm', mat, code)) not in self.fg3_render and (space, ('cm', mat, flip)) in self.fg3_render:
                out.append(self.fg3key(space, ('cm', mat, flip), None, pal, hf=1))
                continue
            out.append(self.fg3key(space, ('cm', mat, code), (code, mat), pal))
        return out

    # ---------------- per block
    def liquid(self, name, top, pal):
        q = [self.anim(name, 0, pal), self.anim(name, 1, pal)] if top else [self.anim(name, 2, pal), self.anim(name, 3, pal)]
        return q + [self.anim(name, 2, pal), self.anim(name, 3, pal)]

    def paint(self, b, fam, ts, common):
        info = B.info(b, ts)
        c = info['cls']
        opn = self.d.open(fam, b)
        st = self.d.stats(fam, b)
        mat = self.d.material(fam, b)
        space = 'common' if common else FG3_COMPONENT[fam]
        blank = self.px(np.zeros((8, 8), np.uint8), 0)
        if c in ('empty', 'checkpoint_1up', 'invisible_block'):
            return [blank] * 4
        if c == 'pswitch_invisible':
            return [self.anim('pblock', k, PAL_GOLD) for k in range(4)]
        if c in ('water', 'water_slope') and c == 'water':
            return self.liquid('water', st is not None and st['open']['u'] > 0.5, PAL_SLATE)
        if c == 'kill':                      # deadly floor: a static bramble-thorn bed (reads as danger in every set)
            return self.pic(pic_thorns(), PAL_BERRY)
        if c in ('lava', 'lava_surface'):
            top = (st is not None and st['open']['u'] > 0.5) or b == 0x004 or c == 'lava_surface'
            return self.liquid('lava', top, PAL_GOLD)
        if c == 'vine':
            return self.pic(pic_vine(), PAL_GREEN)
        if c == 'net':
            return self.pic(pic_net(opn), PAL_SLATE)
        if c == 'door':
            return self.pic(pic_door(b == 0x01F), PAL_BERRY)
        if c == 'boss_door':
            return self.pic(pic_door(False), PAL_BERRY)
        if c == 'pswitch_door':
            return [self.anim('pdoor', k, PAL_BERRY) for k in range(4)]
        if c == 'coin':
            return [self.anim('coin', k, PAL_GOLD) for k in range(4)]
        if c == 'pswitch_coin':
            return [self.anim('pcoin', k, PAL_SLATE) for k in range(4)]
        if c == 'dragon_coin':
            return self.pic(pic_dragon(info.get('notes') == 'top'), PAL_GOLD)
        if c == 'moon':
            return self.pic(pic_moon(), PAL_GOLD)
        if c == 'midway':
            return self.pic(pic_post('tape'), PAL_BERRY)
        if c == 'berry':
            return self.pic(pic_berry(), {'red': PAL_BERRY, 'pink': PAL_BERRY, 'green': PAL_GREEN}[info['notes']])
        if c == 'palace_switch':
            k = b - 0xEC
            return self.pic(pic_palace(k % 4), [PAL_GOLD, PAL_GREEN, PAL_SLATE, PAL_BERRY][(k // 4) % 4])
        if c == 'decor' and 0x6A <= b <= 0x6D:     # switch-palace outline blocks
            return self.pic(pic_outline(), [PAL_GREEN, PAL_GOLD, PAL_SLATE, PAL_BERRY][b - 0x6A])
        if c == 'question_block':
            return [self.anim('prize', k, PAL_GOLD) for k in range(4)]
        if c == 'note_block':
            return [self.anim('note', k, PAL_BERRY) for k in range(4)]
        if c == 'turn_block':
            return [self.anim('turn', k, PAL_GOLD) for k in range(4)]
        if c == 'side_block':
            return [self.anim('turn', k, PAL_SLATE) for k in range(4)]
        if c == 'onoff_block':
            return [self.anim('onoff', k, PAL_BERRY) for k in range(4)]
        if c == 'glass_block':
            return self.pic(pic_glass(), PAL_SLATE)
        if c == 'star_block':
            return self.pic(pic_star_block(), PAL_GREEN)
        if c == 'throw_block':
            return self.pic(pic_throw(), PAL_SLATE)
        if c == 'muncher':
            return [self.anim('muncher', k, PAL_BERRY) for k in range(4)]
        if c == 'used_block':
            return [self.anim('used', k, PAL_GOLD) for k in range(4)]
        if c == 'cement':
            return self.pic(pic_cement(), PAL_SLATE)
        if c == 'pipe':
            n = info['notes']
            hor = 'horizontal' in n
            if hor:
                part = ('end' if 'end' in n else 'shaft') + ('L' if 'top row' in n else 'R')
            else:
                part = ('end' if 'end' in n else 'shaft') + ('L' if 'left' in n else 'R')
            return self.pic(pic_pipe(part, hor), PAL_GREEN)
        if c == 'shooter':
            return self.pic(pic_shooter(['top', 'middle', 'bottom'].index(info['notes'])), PAL_SLATE)
        if c == 'hurt':
            return self.pic(pic_spike(down=not opn['u'] and opn['d']), PAL_SLATE)
        if c in ('slope', 'water_slope', 'lava_slope'):
            mask = B.slope_mask(b, ts)
            cm = terrain_block(mask, dict(u=True, d=opn['d'], l=False, r=False))
            return self.classmap(cm, 'ground', space, PAL_GROUND)
        if c == 'slope_support':
            cm = terrain_block(np.ones((16, 16), bool), dict(u=False, d=opn['d'], l=opn['l'] and not opn['u'],
                                                                r=opn['r'] and not opn['u']), band=False)
            return self.classmap(cm, 'ground', space, PAL_GROUND)
        # ---- ledges, solids and page-0 pictures: by the objects that place them
        if mat is None:
            if c in ('ledge', 'solid', 'conveyor_ledge'):
                mat = 'ground'
            else:
                return [blank] * 4
        if mat == 'pipe':
            return self.pic(pic_pipe('shaftL' if (b & 1) else 'shaftR'), PAL_GREEN)
        if mat == 'leaf':
            return self.pic(pic_leaf(opn), PAL_GREEN)
        if mat == 'cloud':
            return self.pic(pic_cloud(opn), PAL_SLATE)
        if mat == 'weed':
            return self.pic(pic_weed(), PAL_GREEN)
        if mat == 'spike':
            return self.pic(pic_spike(down=not opn['u'] and opn['d']), PAL_SLATE)
        if mat == 'line':
            return self.pic(pic_line(opn), PAL_SLATE)
        if mat == 'donut':
            return self.pic(pic_donut(), PAL_GOLD)
        if mat == 'post':
            return self.pic(pic_post('top' if opn['u'] else 'pole'), PAL_SLATE)
        if mat in PICTURES:
            pic = self.picture(fam, b, mat)
            if pic is not None:
                return self.pic(pic, PICTURES[mat][1])
        if mat in ('web', 'clock', 'window', 'facade', 'house', 'sign', 'palace', 'launcher'):
            mat = 'stone' if c != 'decor' else 'wallbg'
        if mat not in THEMED:
            mat = 'ground'
        cm = terrain_block(np.ones((16, 16), bool), opn, band=(mat == 'ground' and opn['u']))
        pal = PAL_GROUND if mat in ('ground', 'lavarock', 'trunk', 'log', 'wood', 'beam', 'stem', 'column') else PAL_SECOND
        return self.classmap(cm, mat, space, pal)

    def picture(self, fam, b, mat):
        obj, painter = PICTURES[mat][0], PICTURES[mat][2]
        lay = self.d.grids.get(fam + ':layouts', {}).get(obj)
        if not lay:
            return None
        Wd = max(x for x, y, _ in lay) + 1; Ht = max(y for x, y, _ in lay) + 1
        hit = [(x, y) for x, y, bb in lay if bb == b]
        if not hit:
            return None
        canvas = painter(Wd * 16, Ht * 16)
        x, y = hit[0]
        return canvas[y * 16:y * 16 + 16, x * 16:x * 16 + 16]

    # ---------------- tables
    def words(self, b, fam, ts, common):
        q = self.paint(b, fam, ts, common)
        return struct.pack('<4H', q[0], q[2], q[1], q[3])      # Map16 order: TL, BL, TR, BR

    def best_family(self, b):
        best, n = 'grass', -1
        for fam in TABLES:
            st = self.d.stats(fam, b)
            if st and st['n'] > n:
                best, n = fam, st['n']
        return best

    def build_map16(self, items):
        out = {}
        fg = bytearray()
        for b in [b for b in range(0x200) if B.is_common(b)]:
            fam = self.best_family(b)
            fg += self.words(b, fam, 1, True)
        assert len(fg) == 334 * 8
        for b in list(range(0x1C4, 0x1C8)) + list(range(0x1EC, 0x1F0)):   # grass-only overrides (8 blocks)
            fg += self.words(b, 'grass', 0, True)
        for pal in (PAL_GOLD, PAL_SLATE, PAL_BERRY):                       # three more pipe colour sets
            for b in range(0x133, 0x13B):
                w = bytearray(self.words(b, 'grass', 0, True))
                for k in range(4):
                    v = struct.unpack_from('<H', w, 2 * k)[0]
                    struct.pack_into('<H', w, 2 * k, v & ~(7 << 10) | pal << 10)
                fg += w
        spec_order = [b for b in range(0x200) if not B.is_common(b)]
        for fam, (name, base, ts) in TABLES.items():
            data = bytearray()
            for b in spec_order:
                data += self.words(b, fam, ts, False)
            if name == 'kMap16Data':
                fg += data
            else:
                assert len(data) == len(items[name]), (name, len(data), len(items[name]))
                out[name] = bytes(data)
        assert len(fg) == 0x1100, hex(len(fg))
        out['kMap16Data'] = bytes(fg)
        return out

    # ---------------- sheets
    def fg3_sheets(self):
        sheets = {}
        for s in FG3_SHEETS:
            th = THEME[s]
            comp = [c for c, ss in COMP_SHEETS.items() if s in ss]
            img = np.zeros((128, 8, 8), np.uint8)
            for (space, key), (i, rd) in self.fg3_render.items():
                if rd is None or (space != 'common' and space not in comp):
                    continue
                code, mat = rd
                img[i] = np.frombuffer(mat, np.uint8).reshape(8, 8) if code == 'px' else render_class(code, th, mat)
            sheets[s] = img
        return sheets

    def fg12_sheets(self):
        out = {}
        for g, sid in (('fg1', 0x14), ('fg2', 0x17)):
            img = np.zeros((128, 8, 8), np.uint8)
            for k, i in self.st.px[g].items():
                img[i] = np.frombuffer(k, np.uint8).reshape(8, 8)
            out[sid] = img
        return out
