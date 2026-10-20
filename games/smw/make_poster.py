"""poster.png (16:9) for the catalogue: a scene from the CLEAN build with the title typeset by us.

    python -m games.smw.make_poster <clean screenshot.png> poster.png
"""
import sys
import numpy as np
from PIL import Image
from cleanroom.gfx import pixfont

W, H = 1280, 720


def text(canvas, s, x, y, scale, col, shadow=(16, 18, 28)):
    m = pixfont.line(s, True, 1).repeat(scale, 0).repeat(scale, 1)
    h, w = m.shape
    if x is None:
        x = (W - w) // 2
    for dx, dy, c in ((scale, scale, shadow), (0, 0, col)):
        reg = canvas[y + dy:y + dy + h, x + dx:x + dx + w]
        reg[m[:reg.shape[0], :reg.shape[1]]] = c


def main(shot, out, mode='typeset'):
    im = Image.open(shot).convert('RGB')
    if mode == 'title':                      # the clean title screen already carries our logo: frame it, add a caption
        im = im.crop((int(im.width * 0.06), int(im.height * 0.03), int(im.width * 0.94), int(im.height * 0.61)))
        s = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * s + .5), int(im.height * s + .5)), Image.NEAREST)
        x0, y0 = (im.width - W) // 2, (im.height - H) // 2
        a = np.array(im)[y0:y0 + H, x0:x0 + W].copy()
        band = a[H - 96:].astype(float)
        a[H - 96:] = (band * 0.3 + np.array([20, 24, 40]) * 0.7).astype(np.uint8)
        text(a, 'BUILT ON THE SMW DECOMP', None, H - 72, 6, (232, 230, 225))
    else:
        s = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * s + .5), int(im.height * s + .5)), Image.NEAREST)
        x0, y0 = (im.width - W) // 2, int((im.height - H) * 0.75)
        a = np.array(im)[y0:y0 + H, x0:x0 + W].copy()
        band = a[60:330].astype(float)
        a[60:330] = (band * 0.35 + np.array([20, 24, 40]) * 0.65).astype(np.uint8)
        text(a, 'BRAMBLE', None, 92, 10, (240, 84, 60))
        text(a, 'ISLES', None, 178, 13, (250, 214, 70))
        text(a, 'BUILT ON THE SMW DECOMP', None, 286, 4, (232, 230, 225))
    Image.fromarray(a).save(out)
    print('poster ->', out, a.shape)


if __name__ == '__main__':
    main(*sys.argv[1:])
