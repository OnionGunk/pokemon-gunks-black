"""Turn the title logo artwork into gunk/title/title_logo.png, the indexed picture patches.title_logo builds in.

    .venv/Scripts/python tools/titlelogo.py <artwork.png>

The artwork may be any size and RGB: the black around the lettering (reached from the picture's edges) becomes
transparent, the rest is scaled to fit the logo's place on the top screen (LOGO_BOX, Black's own logo's size)
and cut to the colours the layer has free (palette indexes 1-224, 15-bit colour).
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'gunk', 'title', 'title_logo.png')
LOGO_BOX = (196, 119)  # Black's logo; it sits at x 29, y 33 on the 256 x 192 top screen
COLOURS = 224
DARK = 40  # the background: pixels this close to black, joined to the picture's edge


def main(src):
    art = Image.open(src).convert('RGB')
    # mark the background: flood the dark area from every edge pixel
    mask = Image.eval(art.convert('L'), lambda v: 255 if v < DARK else 0)
    w, h = art.size
    for x, y in [(x, 0) for x in range(0, w, 4)] + [(x, h - 1) for x in range(0, w, 4)] + \
                [(0, y) for y in range(0, h, 4)] + [(w - 1, y) for y in range(0, h, 4)]:
        if mask.getpixel((x, y)) == 255:
            ImageDraw.floodfill(mask, (x, y), 128)
    alpha = Image.eval(mask, lambda v: 0 if v == 128 else 255)
    rgba = art.copy()
    rgba.putalpha(alpha)
    rgba = rgba.crop(alpha.getbbox())
    scale = min(LOGO_BOX[0] / rgba.width, LOGO_BOX[1] / rgba.height)
    size = (round(rgba.width * scale), round(rgba.height * scale))
    small = rgba.resize(size, Image.LANCZOS)
    keep = small.getchannel('A').point(lambda v: 255 if v >= 128 else 0)
    rgb = small.convert('RGB').point(lambda v: v & 0xF8)
    q = rgb.quantize(COLOURS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[:COLOURS * 3]
    out = Image.new('P', size, 0)
    out.putpalette([0, 0, 0] + pal + [0, 0, 0] * (255 - COLOURS))
    data = [i + 1 if a else 0 for i, a in zip(q.get_flattened_data(), keep.get_flattened_data())]
    out.putdata(data)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, transparency=0, optimize=True)
    print(OUT, size)


if __name__ == '__main__':
    main(sys.argv[1])
