"""CLEAN ROOM. Bramble Isles tile kit: palettes and 8x8 / 16x16 pixel painters for the level
tiles, animated tiles and backgrounds (games/smw/tiles.py assembles them). All shapes and
colours here are our own; nothing is read from retail data.

Pixel indices inside a palette row (3bpp layer tiles): 0 clear, 1 white (fixed by the game),
2 outline / darkest, 3 dark, 4 mid, 5 light, 6 highlight, 7 accent."""
import numpy as np

T, W, O, D, M, L, H, A = range(8)


def rgb15(c):
    r, g, b = (int(c[i:i + 2], 16) >> 3 for i in (0, 2, 4))
    return r | g << 5 | b << 10


def pal_bytes(cols):
    return np.array([rgb15(c) for c in cols], '<u2').tobytes()


# ----------------------------------------------------------------- palettes (our own picks)
SKY = ['a8d8f0', 'c8f0e0', '2868a8', '000000', '584878', '182040', '80d0d8', 'f8f8f8',
       '507868', '608878', '709888', '80a898', '90b8a8', 'a0c8b8', 'f8f8f8', '000000']
# 8 BG palette sets, rows 0 and 1, colours 2..7 (dark -> light, accent)
BG = [
    ['306848', '488858', '60a070', '80b888', 'a8d0a8', 'd8f0c8', '286070', '408898', '60a8b8', '88c8d0', 'b8e0e8', 'e8f8f8'],  # green hills
    ['183858', '285878', '407898', '6098b0', '88b8c8', 'b8d8e0', '183858', '305070', '506888', '7088a0', '98b0c0', 'c8d8e0'],  # deep blue
    ['887858', 'a09070', 'b8a888', 'd0c0a0', 'e0d8b8', 'f0e8d0', '987860', 'b89878', 'd0b090', 'e0c8a8', 'f0e0c8', 'f8f0e0'],  # sand
    ['202838', '384050', '505868', '687080', '8890a0', 'b0b8c0', '302830', '483848', '605060', '806878', 'a08898', 'c8b0c0'],  # dusk stone
    ['281848', '403068', '584888', '7868a8', '9888c0', 'c0b0e0', '204060', '305880', '4878a0', '6898b8', '98b8d0', 'd0e0f0'],  # violet night
    ['081028', '182848', '284068', '405888', '6880a8', 'a0b8d8', '000000', 'd8d0a0', 'f0e8c0', 'c0d8f0', 'e0f0f8', 'f8f8f8'],  # night sky + stars
    ['181010', '302420', '483830', '605040', '807058', 'a09078', '101818', '182828', '283838', '384848', '506060', '687878'],  # ghost brown
    ['184818', '286020', '407830', '589040', '78a858', 'a0c878', '204010', '306018', '488028', '68a038', '90c060', 'c0e090'],  # forest
]
# 8 FG palette sets: row 2 = ground (outline, soil x3, moss x2), row 3 = plants / second material
FG = [
    ['301808', '684020', '905830', 'b88048', '48a028', '88d040', '183818', '307828', '58a838', 'e04860', 'f888a0', 'f8d848'],  # loam + moss
    ['182030', '384860', '587088', '7898a8', '309880', '70d0a8', '202830', '405060', '607888', 'c05030', 'e88050', 'f8c070'],  # slate + teal moss
    ['381818', '784028', 'a86038', 'd09058', 'c04878', 'f080a8', '402010', '805828', 'b08040', '50a0d0', '90d0f0', 'f0f0f0'],  # red clay
    ['283850', '587090', '88a8c8', 'b0d0e8', 'e0f0f8', 'f8f8f8', '203048', '486078', '7090a8', '58b0c8', '98e0f0', 'd8f8f8'],  # ice
    ['281808', '583818', '805828', 'a87840', 'c8a060', 'e8c888', '201810', '483828', '685040', '887060', 'a89080', 'd0b8a0'],  # timber
    ['301838', '604068', '885890', 'b080b8', 'd8a8e0', 'f8d8f8', '283048', '506080', '7088b0', 'f0c040', 'f8e080', 'f8f8c8'],  # lilac stone
    ['202808', '485018', '687028', '889838', '609028', 'a0d050', '182010', '304820', '487030', '889048', 'c0c868', 'f0f0a0'],  # olive forest
    ['181818', '383838', '585050', '787068', 'c07020', 'f0b048', '201818', '403030', '604848', '806060', 'a88080', 'd0b0a8'],  # charcoal + ember
]
# objects rows 4..7 (layer tiles) and 8..13 (sprite rows 0..5: same roles as before, new colours)
OBJ = [
    ['304870', '486898', '6890c0', '98bce0', 'd0e8f8', '58c8d8'],  # 4 steel blue: water, cement, nets, clouds
    ['104820', '207830', '38a040', '60c858', 'a0e888', 'f0d070'],  # 5 leaf green: pipes, vines
    ['603000', '985800', 'd09000', 'f0c030', 'f8e888', 'f86030'],  # 6 gold (col 4 flashes): prize blocks, coins
    ['301850', '583890', '8060c0', 'a890e0', 'd8c8f8', 'e85088'],  # 7 berry violet: notes, doors, switches
    ['000000', '704818', 'b88838', 'e8c060', 'f8f8f0', 'f0f0e8'],  # 8 sprite: brown / cream
    ['000000', '606870', '9098a0', 'b8c0c8', 'e0e8f0', 'e03070'],  # 9 sprite: grey + rose
    ['000000', 'e86010', 'f8a820', 'f8e040', 'a83010', 'f09060'],  # 10 sprite: orange / yellow, skin
    ['000000', '3048c0', '5070e0', '80a0f8', 'a83010', 'f09060'],  # 11 sprite: blue, skin
    ['000000', '781010', 'b02018', 'e84030', 'a83010', 'f09060'],  # 12 sprite: red, skin
    ['000000', '106818', '20a830', '50e050', 'a83010', 'f09060'],  # 13 sprite: green, skin
]
FLASH = ['f8a800', 'f8c820', 'f8e858', 'f8f8b0', 'f8f8e8', 'f8f8b0', 'f8e858', 'f8c820',
         'f87000', 'f84000', 'd82010', 'b81010', 'b81010', 'd82010', 'f84000', 'f87000']
B5EC = ['a0d8e8', '000000', 'f8e830', 'd8c098', 'a0d8e8', 'b09068', '987850', '806040',
        'a0d8e8', 'd8c098', 'f8f8f8', '000000', 'a0d8e8', '000000', 'd8c098', '5890f0']


def palettes():
    return {
        'kGlobalPalettes_Sky': pal_bytes(SKY),
        'kGlobalPalettes_Background': pal_bytes(sum(BG, [])),
        'kGlobalPalettes_Foreground': pal_bytes(sum(FG, [])),
        'kGlobalPalettes_Objects': pal_bytes(sum(OBJ, [])),
        'kGlobalPalettes_Flashing': pal_bytes(FLASH),
        'kGlobalPalettes_B5EC': pal_bytes(B5EC),
    }


# ----------------------------------------------------------------- pixel helpers
def rng(seed):
    return np.random.default_rng(seed)


def outline(mask, inside=None, col=O):
    """Indices: mask interior unchanged, the border pixels of mask become col."""
    m = mask.astype(bool)
    p = np.pad(m, 1, constant_values=False)
    edge = m & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    return edge


def disc(n, cx, cy, r):
    y, x = np.mgrid[0:n, 0:n]
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def ring(n, cx, cy, r0, r1):
    y, x = np.mgrid[0:n, 0:n]
    d = (x - cx) ** 2 + (y - cy) ** 2
    return (d <= r1 * r1) & (d >= r0 * r0)


def line(img, x0, y0, x1, y1, c):
    n = max(abs(x1 - x0), abs(y1 - y0)) + 1
    for t in np.linspace(0, 1, n):
        x, y = int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t))
        if 0 <= y < img.shape[0] and 0 <= x < img.shape[1]:
            img[y, x] = c


def periodic_noise(shape, seed, period=8, octaves=((4, 1.0), (2, 0.5))):
    """Smooth value noise that tiles with the given period (so 8x8 fills join seamlessly)."""
    r = rng(seed)
    h, w = shape
    out = np.zeros(shape)
    for cell, amp in octaves:
        n = period // cell
        g = r.random((n, n))
        y, x = np.mgrid[0:h, 0:w] / cell
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = x - x0, y - y0
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a = g[y0 % n, x0 % n]; b = g[y0 % n, (x0 + 1) % n]
        c = g[(y0 + 1) % n, x0 % n]; d = g[(y0 + 1) % n, (x0 + 1) % n]
        out += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
    out -= out.min()
    return out / max(out.max(), 1e-9)


BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0


def shade(v, levels):
    """Map 0..1 values to the given index levels with ordered dithering."""
    h, w = v.shape
    b = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w]
    k = np.clip((v * (len(levels) - 1) + b - 0.5).round().astype(int), 0, len(levels) - 1)
    return np.array(levels, np.uint8)[k]


# ----------------------------------------------------------------- animated 16x16 frames
def block_base(bevel=True, round_=True):
    """Rounded square block with a 1 px outline and a bevel: returns 16x16 indices."""
    b = np.full((16, 16), M, np.uint8)
    y, x = np.mgrid[0:16, 0:16]
    b[(x + y) < 9] = L
    b[(x + y) > 21] = D
    b[1:3, 1:14] = H; b[1:14, 1:3] = np.where(b[1:14, 1:3] == M, L, b[1:14, 1:3])
    b[0, :] = O; b[15, :] = O; b[:, 0] = O; b[:, 15] = O
    if round_:
        for (yy, xx) in ((0, 0), (0, 15), (15, 0), (15, 15)):
            b[yy, xx] = T
        b[1, 1] = O; b[1, 14] = O; b[14, 1] = O; b[14, 14] = O
    return b


def sparkle(n, cx, cy, r, diag=False):
    """Four-point star mask."""
    y, x = np.mgrid[0:n, 0:n].astype(float)
    dx, dy = x - cx, y - cy
    if diag:
        dx, dy = (dx + dy) / 1.414, (dx - dy) / 1.414
    return (np.abs(dx) * np.abs(dy) <= r * 0.55) & (np.abs(dx) + np.abs(dy) <= r * 1.6)


def prize_frame(f):
    b = block_base()
    r = [4.2, 3.6, 3.0, 3.6][f]
    m = sparkle(16, 7.5, 7.5, r, diag=(f % 2 == 1))
    b[m] = W
    b[outline(m) & ~m] = O if False else b[outline(m) & ~m]
    e = np.zeros((16, 16), bool)
    p = np.pad(m, 1)
    e = (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]) & ~m
    b[e & (b != O) & (b != T)] = D
    b[7:9, 7:9] = H if f != 2 else A
    return b


def note_frame(f):
    b = block_base()
    off = [0, 1, 0, -1][f]
    rr = ring(16, 7.5, 7.5 + off, 3.2, 5.2)
    b[rr] = D
    inner = disc(16, 7.5, 7.5 + off, 3.2)
    b[inner] = L
    b[disc(16, 6.5, 6.5 + off, 1.2)] = W
    b[disc(16, 7.5, 7.5 + off, 5.2) & ~disc(16, 7.5, 7.5 + off, 4.6)] = O
    return b


def turn_frame(f):
    """Slatted crate block; frames squash horizontally (turning)."""
    w = [16, 10, 4, 10][f]
    b = np.zeros((16, 16), np.uint8)
    full = block_base()
    for yy in (4, 8, 12):
        full[yy, 1:15] = D
    full[2:14, 7] = np.where(full[2:14, 7] != O, D, O)
    if w == 16:
        return full
    xs = np.linspace(0, 15, w).round().astype(int)
    x0 = (16 - w) // 2
    b[:, x0:x0 + w] = full[:, xs]
    b[:, x0] = O; b[:, x0 + w - 1] = O
    if f == 3:
        b = b[:, ::-1]
    return b


def coin_frame(f):
    w = [12, 8, 3, 8][f]
    b = np.zeros((16, 16), np.uint8)
    y, x = np.mgrid[0:16, 0:16].astype(float)
    m = ((x - 7.5) / (w / 2 + 0.01)) ** 2 + ((y - 7.5) / 6.6) ** 2 <= 1
    b[m] = M
    inner = ((x - 7.5) / max(w / 2 - 1.8, 0.4)) ** 2 + ((y - 7.5) / 4.8) ** 2 <= 1
    b[inner] = L
    if w >= 8:   # embossed leaf: a short diagonal with two side ticks
        for k in range(-3, 4):
            xx, yy = int(7.5 + k * w / 14.0), 7 - k
            if 0 <= xx < 16:
                b[yy + 1, xx] = D
        b[6, int(7.5 - w / 7)] = H
    b[outline(m)] = O
    b[(x < 7) & (y < 6) & m & ~outline(m) & (b == L)] = H
    return b


def used_frame():
    b = block_base()
    b[b == H] = L
    b[b == L] = M
    for (yy, xx) in ((3, 3), (3, 12), (12, 3), (12, 12)):
        b[yy, xx] = O; b[yy - 1, xx - 1] = L
    return b


def muncher_frame(f):
    """Thorn pod: dark round body with thorns; mouth slit open / closed."""
    b = np.zeros((16, 16), np.uint8)
    body = disc(16, 7.5, 9, 6.2)
    b[body] = D
    b[disc(16, 6, 7.5, 2.5)] = M
    for (x0, y0, x1, y1) in ((7, 3, 7, 0), (2, 5, 0, 3), (13, 5, 15, 3), (1, 10, 0, 10), (14, 10, 15, 10)):
        line(b, x0, y0, x1, y1, L)
        b[y1, x1] = W
    if f == 0:
        b[9:11, 4:12] = O
        b[9, 5:11:2] = W
    else:
        b[10, 4:12] = O
    b[outline(body)] = O
    return b


def lamp_frame(on):
    b = block_base()
    b[b == H] = L
    if on:
        b[disc(16, 7.5, 7.5, 4.5)] = H
        b[disc(16, 7.5, 7.5, 2.5)] = W
        for k in range(4):
            line(b, 7 + [0, 0, -6, 6][k] // 1, 7 + [-6, 6, 0, 0][k] // 1, 7, 7, H)
    else:
        b[ring(16, 7.5, 7.5, 2.5, 4.5)] = O
        b[disc(16, 7.5, 7.5, 2.4)] = D
    return b


def panel_frame():
    b = block_base()
    m = np.abs(np.mgrid[0:16, 0:16][0] - 7.5) + np.abs(np.mgrid[0:16, 0:16][1] - 7.5) <= 4.5
    b[m] = D
    b[np.abs(np.mgrid[0:16, 0:16][0] - 7.5) + np.abs(np.mgrid[0:16, 0:16][1] - 7.5) <= 2.5] = H
    return b


def liquid_frame(f, kind):
    """Tiles TL,TR = surface (transparent above the crest), BL,BR = body; period 16 in x,
    8 in y for the body so tiles 2,3 repeat downwards. kind 'water' or 'lava'."""
    y, x = np.mgrid[0:16, 0:16].astype(float)
    ph = f * np.pi / 2
    crest = 3.0 + 1.3 * np.sin(2 * np.pi * x / 16 + ph)
    v = 0.5 + 0.25 * np.sin(2 * np.pi * (x + 2 * f) / 16 + 2 * np.pi * y / 8) + \
        0.25 * np.sin(2 * np.pi * (x * 2 - 4 * f) / 16 - 2 * np.pi * y / 8)
    if kind == 'water':
        body = shade(v, [D, M, M, L])
        hi = (np.abs(np.sin(2 * np.pi * (x - 3 * f) / 16 + 2 * np.pi * (y % 8) / 8)) > 0.97)
        body[hi] = H
    else:
        body = shade(v, [O, D, M, M, L])
        bub = ((x - (4 + 2 * f) % 16) ** 2 + ((y % 8) - (6 - f) % 8) ** 2) <= 1.5
        body[bub] = H
    out = body.copy()
    top = out[:8].copy()
    top[y[:8] < crest[:8]] = T
    edge = (y[:8] >= crest[:8]) & (y[:8] < crest[:8] + 1.2)
    top[edge] = W if kind == 'water' else A
    top[(y[:8] >= crest[:8] + 1.2) & (y[:8] < crest[:8] + 2.4)] = L if kind == 'water' else H
    out[:8] = top
    out[8:] = body[8:]
    # tiles 2,3 (bottom row) must tile vertically with period 8: body is periodic in y by 8 already
    return out


def torch_frame(f):
    b = np.zeros((16, 16), np.uint8)
    b[9:16, 6:10] = D; b[9:16, 6] = O; b[9:16, 9] = O; b[8, 5:11] = O
    h = [6, 7, 5, 7][f]; sway = [0, 1, 0, -1][f]
    y, x = np.mgrid[0:16, 0:16].astype(float)
    flame = ((x - 7.5 - sway * (8 - y) / 8) / 2.6) ** 2 + ((y - (8 - h / 2)) / (h / 2 + 0.5)) ** 2 <= 1
    flame &= y < 8
    b[flame] = L
    b[flame & (((x - 7.5 - sway * (8 - y) / 8) / 1.3) ** 2 + ((y - 6) / 2) ** 2 <= 1)] = W
    return b


def orb_frame(f):
    b = np.zeros((16, 16), np.uint8)
    r = [5.5, 6.2, 6.8, 6.2][f]
    b[disc(16, 7.5, 7.5, r)] = D
    b[disc(16, 7.5, 7.5, r - 1.5)] = M
    b[disc(16, 6, 6, 2)] = L
    b[disc(16, 5.5, 5.5, 0.9)] = W
    b[outline(disc(16, 7.5, 7.5, r))] = O
    return b


def belt_frame(f, rope=False):
    """Conveyor belt / moving rope: diagonal chevrons scrolling right 4 px per frame (period 16)."""
    y, x = np.mgrid[0:16, 0:16]
    if rope:
        b = np.zeros((16, 16), np.uint8)
        band = (y >= 5) & (y <= 10)
        tw = ((x + y - 4 * f) % 6) < 3
        b[band] = np.where(tw, L, D)[band]
        b[4, :] = O; b[11, :] = O
        return b
    b = np.full((16, 16), D, np.uint8)
    chev = ((x - 4 * f + np.abs(y - 7.5)) % 8) < 3
    b[chev] = L
    b[0, :] = O; b[15, :] = O; b[1, :] = H; b[14, :] = O
    return b


def drip_frame(f):
    b = np.zeros((16, 16), np.uint8)
    y, x = np.mgrid[0:16, 0:16]
    stream = (np.abs(x - 7.5) < 3.5)
    v = ((y + 4 * f) % 8) / 8.0
    b[stream] = shade(np.broadcast_to(v, (16, 16)).copy(), [M, L, H])[stream]
    b[(np.abs(x - 7.5) >= 3) & (np.abs(x - 7.5) < 4) & stream] = W
    return b


def bubbles_frame(f):
    b = liquid_frame(f, 'lava')
    for (bx, by, r) in ((4, 12 - 3 * f, 1.6), (11, 14 - 2 * f, 1.2)):
        m = disc(16, bx, by % 16, r)
        b[m] = H
    return b


def track_frame(k):
    b = np.zeros((16, 16), np.uint8)
    if k == 0:
        line(b, 0, 7, 7, 0, L); line(b, 0, 6, 6, 0, D)
    else:
        for i in range(0, 16, 3):
            b[7, i] = L
    return b
