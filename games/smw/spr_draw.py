"""CLEAN ROOM. Small vector-to-pixel kit for our sprite drawings.

A Fig collects filled parts (masks, back to front) with a colour ramp each, shades every part with
light from the upper left, outlines the union, then lays decals (eyes, marks) on top. Nothing here
reads retail data; sizes come from the caller.

Ramps are (light, mid, dark) palette indices; a single int means a flat fill.
"""
import numpy as np
from PIL import Image, ImageDraw

# 3bpp sprite palette convention (our own, used by every row we design in spr_pal):
WHITE, LINE, LIGHT, MID, DARK, ACC, ACCD = 1, 2, 3, 4, 5, 6, 7
MAIN = (LIGHT, MID, DARK)
ACCENT = (ACC, ACC, ACCD)
PALE = (WHITE, WHITE, ACC)
INK = (LINE, LINE, LINE)


def _grid(w, h, ss=1):
    y, x = np.mgrid[0:h * ss, 0:w * ss]
    return (x + 0.5) / ss, (y + 0.5) / ss


def ellipse_mask(w, h, cx, cy, rx, ry, rot=0.0):
    x, y = _grid(w, h)
    dx, dy = x - cx, y - cy
    if rot:
        c, s = np.cos(rot), np.sin(rot)
        dx, dy = c * dx + s * dy, -s * dx + c * dy
    return (dx / max(rx, 0.3)) ** 2 + (dy / max(ry, 0.3)) ** 2 <= 1.0


def poly_mask(w, h, pts):
    im = Image.new('1', (w * 4, h * 4), 0)
    ImageDraw.Draw(im).polygon([(x * 4, y * 4) for x, y in pts], fill=1)
    a = np.asarray(im, np.float32).reshape(h, 4, w, 4).mean((1, 3))
    return a >= 0.5


def line_mask(w, h, pts, width=1.0):
    im = Image.new('1', (w * 4, h * 4), 0)
    d = ImageDraw.Draw(im)
    d.line([(x * 4, y * 4) for x, y in pts], fill=1, width=max(1, int(round(width * 4))), joint='curve')
    for x, y in (pts[0], pts[-1]):
        r = width * 2
        d.ellipse([x * 4 - r, y * 4 - r, x * 4 + r, y * 4 + r], fill=1)
    a = np.asarray(im, np.float32).reshape(h, 4, w, 4).mean((1, 3))
    return a >= 0.45


def rect_mask(w, h, x0, y0, x1, y1):
    m = np.zeros((h, w), bool)
    m[max(0, int(y0)):max(0, int(y1)), max(0, int(x0)):max(0, int(x1))] = True
    return m


def grow(m, n=1):
    for _ in range(n):
        p = np.pad(m, 1)
        m = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m


def grow8(m):
    p = np.pad(m, 1)
    out = m.copy()
    for dy in range(3):
        for dx in range(3):
            out |= p[dy:dy + m.shape[0], dx:dx + m.shape[1]]
    return out


def shrink(m, n=1):
    return ~grow(~m, n)


def shade(m, ramp, light=(-1.0, -1.0), soft=0.5):
    """Indices for mask m: light on the side facing `light`, dark on the far side."""
    if isinstance(ramp, int):
        return np.where(m, ramp, 0).astype(np.uint8)
    lo, mid, hi = ramp
    ys, xs = np.nonzero(m)
    out = np.zeros(m.shape, np.uint8)
    if not len(ys):
        return out
    cy, cx = ys.mean(), xs.mean()
    ry, rx = max(1.0, ys.std() * 1.7), max(1.0, xs.std() * 1.7)
    lx, ly = light
    t = ((xs - cx) / rx * lx + (ys - cy) / ry * ly) / np.hypot(lx, ly)
    v = np.full(len(ys), mid, np.uint8)
    v[t > soft] = lo
    v[t < -soft * 1.25] = hi
    # rim: pixels on the dark-side edge get the dark shade too
    e = m & ~shrink(m)
    out[ys, xs] = v
    far = np.zeros(m.shape, bool)
    far[ys[t < -0.1], xs[t < -0.1]] = True
    out[e & far] = hi
    return out


class Fig:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = np.zeros((h, w), np.uint8)
        self.sil = np.zeros((h, w), bool)
        self.decals = []

    # ---- parts (back to front); `edge` draws the part's own border in a colour where it lies over others
    def part(self, m, ramp, edge=None, light=(-1.0, -1.0), soft=0.5):
        m = m & ~np.zeros_like(m)
        if not m.any():
            return m
        col = shade(m, ramp, light, soft)
        self.img[m] = col[m]
        if edge is not None:
            e = m & ~shrink(m) & self.sil
            self.img[e] = edge
        self.sil |= m
        return m

    def ellipse(self, cx, cy, rx, ry, ramp, rot=0.0, **k):
        return self.part(ellipse_mask(self.w, self.h, cx, cy, rx, ry, rot), ramp, **k)

    def poly(self, pts, ramp, **k):
        return self.part(poly_mask(self.w, self.h, pts), ramp, **k)

    def line(self, pts, width, ramp, **k):
        return self.part(line_mask(self.w, self.h, pts, width), ramp, **k)

    def rect(self, x0, y0, x1, y1, ramp, **k):
        return self.part(rect_mask(self.w, self.h, x0, y0, x1, y1), ramp, **k)

    def cut(self, m):
        """Remove pixels (holes, gaps)."""
        self.img[m] = 0
        self.sil &= ~m

    # ---- decals (after the outline)
    def px(self, x, y, c):
        self.decals.append(('px', int(round(x)), int(round(y)), c))

    def dmask(self, m, c):
        self.decals.append(('m', m, c))

    def dline(self, pts, c, width=0.6):
        self.decals.append(('m', line_mask(self.w, self.h, pts, width), c))

    def eye(self, x, y, r=1.5, look=(-1, 0), white=WHITE, pupil=LINE, shine=True):
        """Round eye: white disc, pupil shifted toward `look`."""
        x0, y0 = x, y
        if r < 1.2:
            self.px(x0, y0, pupil)
            return
        self.dmask(ellipse_mask(self.w, self.h, x0, y0, r, r * 1.15), white)
        pr = max(0.6, r * 0.55)
        self.dmask(ellipse_mask(self.w, self.h, x0 + look[0] * r * 0.4, y0 + look[1] * r * 0.4 + 0.2, pr, pr * 1.2), pupil)

    def render(self, outline=LINE, outline8=False):
        out = self.img.copy()
        if outline is not None:
            g = grow8(self.sil) if outline8 else grow(self.sil)
            ring = g & ~self.sil
            out[ring] = outline
        for d in self.decals:
            if d[0] == 'px':
                _, x, y, c = d
                if 0 <= x < self.w and 0 <= y < self.h:
                    out[y, x] = c
            else:
                _, m, c = d
                out[m] = c
        return out


def mirror(a):
    return a[:, ::-1].copy()


def fit(a, w, h, ax=0.5, ay=1.0):
    """Place array a into a w x h canvas (cropping if needed); ax/ay anchor (0 left/top .. 1 right/bottom)."""
    out = np.zeros((h, w), a.dtype)
    ah, aw = a.shape
    ox, oy = int(round((w - aw) * ax)), int(round((h - ah) * ay))
    sx0, sy0 = max(0, -ox), max(0, -oy)
    dx0, dy0 = max(0, ox), max(0, oy)
    cw, ch = min(aw - sx0, w - dx0), min(ah - sy0, h - dy0)
    if cw > 0 and ch > 0:
        out[dy0:dy0 + ch, dx0:dx0 + cw] = a[sy0:sy0 + ch, sx0:sx0 + cw]
    return out


def remap(a, table):
    """Index remap {old: new}."""
    out = a.copy()
    for o, n in table.items():
        out[a == o] = n
    return out
