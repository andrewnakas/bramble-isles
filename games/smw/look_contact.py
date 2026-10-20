"""Dev: one contact sheet from several PNGs. usage: look_contact out.png cols width img..."""
import sys
from PIL import Image
out, cols, w = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ims = [Image.open(p).convert('RGB') for p in sys.argv[4:]]
ims = [im.resize((w, im.height * w // im.width), Image.NEAREST) for im in ims]
h = max(im.height for im in ims)
rows = -(-len(ims) // cols)
sheet = Image.new('RGB', (cols * (w + 4), rows * (h + 4)), (90, 0, 90))
for k, im in enumerate(ims):
    sheet.paste(im, (k % cols * (w + 4), k // cols * (h + 4)))
sheet.save(out)
print(out, sheet.size)
