"""Convert the Gen 5 follower sprites from a Pokémon Essentials "Followers" folder into gunk/followers.

    .venv/Scripts/python tools/followers5.py <Followers folder>

The Essentials sheets are 4x4 cells (rows down, left, right, up; columns two poses, each twice) drawn at twice
the DS's size: the same art as HeartGold's and Black's own overworld Pokémon (Black's sprites for #1-493 come
out of these sheets pixel for pixel). Each sprite becomes one strip of frames in Black's order (up, up, down,
down, left, left, right, right; the 64x64 ones drop the right-facing pair, which Black mirrors), at the DS's
size, in 16 colours with index 0 transparent: gunk/followers/<species>[-f|-<form>].png. patches.followers puts
them in the ROM. The art and its credits: gunk/followers/CREDITS.md.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'gunk', 'followers')

# Black's species #494-649, in the Essentials file names
NAMES = '''VICTINI SNIVY SERVINE SERPERIOR TEPIG PIGNITE EMBOAR OSHAWOTT DEWOTT SAMUROTT PATRAT WATCHOG LILLIPUP HERDIER
STOUTLAND PURRLOIN LIEPARD PANSAGE SIMISAGE PANSEAR SIMISEAR PANPOUR SIMIPOUR MUNNA MUSHARNA PIDOVE TRANQUILL UNFEZANT
BLITZLE ZEBSTRIKA ROGGENROLA BOLDORE GIGALITH WOOBAT SWOOBAT DRILBUR EXCADRILL AUDINO TIMBURR GURDURR CONKELDURR
TYMPOLE PALPITOAD SEISMITOAD THROH SAWK SEWADDLE SWADLOON LEAVANNY VENIPEDE WHIRLIPEDE SCOLIPEDE COTTONEE WHIMSICOTT
PETILIL LILLIGANT BASCULIN SANDILE KROKOROK KROOKODILE DARUMAKA DARMANITAN MARACTUS DWEBBLE CRUSTLE SCRAGGY SCRAFTY
SIGILYPH YAMASK COFAGRIGUS TIRTOUGA CARRACOSTA ARCHEN ARCHEOPS TRUBBISH GARBODOR ZORUA ZOROARK MINCCINO CINCCINO
GOTHITA GOTHORITA GOTHITELLE SOLOSIS DUOSION REUNICLUS DUCKLETT SWANNA VANILLITE VANILLISH VANILLUXE DEERLING
SAWSBUCK EMOLGA KARRABLAST ESCAVALIER FOONGUS AMOONGUSS FRILLISH JELLICENT ALOMOMOLA JOLTIK GALVANTULA FERROSEED
FERROTHORN KLINK KLANG KLINKLANG TYNAMO EELEKTRIK EELEKTROSS ELGYEM BEHEEYEM LITWICK LAMPENT CHANDELURE AXEW FRAXURE
HAXORUS CUBCHOO BEARTIC CRYOGONAL SHELMET ACCELGOR STUNFISK MIENFOO MIENSHAO DRUDDIGON GOLETT GOLURK PAWNIARD
BISHARP BOUFFALANT RUFFLET BRAVIARY VULLABY MANDIBUZZ HEATMOR DURANT DEINO ZWEILOUS HYDREIGON LARVESTA VOLCARONA
COBALION TERRAKION VIRIZION TORNADUS THUNDURUS RESHIRAM ZEKROM LANDORUS KYUREM KELDEO MELOETTA GENESECT'''.split()
assert len(NAMES) == 156

# forms and female sprites that Black has: (Essentials suffix, output suffix)
EXTRA = {'UNFEZANT': [('_female', '-f')], 'FRILLISH': [('_female', '-f')], 'JELLICENT': [('_female', '-f')],
         'BASCULIN': [('_1', '-1')], 'DEERLING': [('_1', '-1'), ('_2', '-2'), ('_3', '-3')],
         'SAWSBUCK': [('_1', '-1'), ('_2', '-2'), ('_3', '-3')], 'MELOETTA': [('_1', '-1')],
         'GENESECT': [('_1', '-1'), ('_2', '-2'), ('_3', '-3'), ('_4', '-4')]}

# Black's frames as (sheet row, column): up, down, left, right; the right-facing poses come in the other order
FRAMES = [(3, 0), (3, 2), (0, 0), (0, 2), (1, 0), (1, 2), (2, 2), (2, 0)]


def half(cell):
    """The cell at the DS's size: the 2x2 blocks are read from whichever pixel phase they line up on."""
    px = cell.load()
    w, h = cell.size

    def misses(ox, oy):
        return sum(1 for y in range(oy, h - 1, 2) for x in range(ox, w - 1, 2)
                   if not px[x, y] == px[x + 1, y] == px[x, y + 1] == px[x + 1, y + 1])

    ox, oy = min(((0, 0), (1, 0), (0, 1), (1, 1)), key=lambda o: misses(*o))
    small = Image.new('RGBA', (w // 2, h // 2))
    for y in range(h // 2):
        for x in range(w // 2):
            sx, sy = min(2 * x + ox, w - 1), min(2 * y + oy, h - 1)
            small.putpixel((x, y), px[sx, sy])
    return small


def convert(path):
    sheet = Image.open(path).convert('RGBA')
    cell = sheet.width // 4
    native = cell // 2
    size = 32 if native <= 32 else 64
    frames = FRAMES if size == 32 else FRAMES[:6]
    strip = Image.new('RGBA', (size * len(frames), size))
    for k, (row, col) in enumerate(frames):
        small = half(sheet.crop((col * cell, row * cell, col * cell + cell, row * cell + cell)))
        # the cells stand on their bottom centre, like Black's frames
        strip.paste(small, (k * size + (size - native) // 2, size - native))
    # 15 colours (in the DS's 5 bits per channel) and transparency at index 0
    opaque = Image.new('RGB', strip.size)
    alpha = strip.getchannel('A')
    opaque.paste(strip.convert('RGB').point(lambda v: v & 0xF8), mask=alpha)
    colours = sorted({c for c, a in zip(opaque.get_flattened_data(), alpha.get_flattened_data()) if a >= 128})
    if len(colours) > 15:
        print(f'{os.path.basename(path)}: {len(colours)} colours, reduced to 15')
        sample = Image.new('RGB', (len(colours), 1))
        sample.putdata(colours)
        colours = sorted({c for c in sample.quantize(15, method=Image.Quantize.MEDIANCUT).convert('RGB')
                         .point(lambda v: v & 0xF8).get_flattened_data()})
    out = Image.new('P', strip.size, 0)
    out.putpalette([0x98, 0xD0, 0xB8] + [v for c in colours for v in c] + [0] * 3 * (15 - len(colours)))
    near = {}
    for y in range(strip.height):
        for x in range(strip.width):
            if alpha.getpixel((x, y)) < 128:
                continue
            c = opaque.getpixel((x, y))
            if c not in near:
                near[c] = 1 + min(range(len(colours)), key=lambda i: sum((a - b) ** 2 for a, b in zip(c, colours[i])))
            out.putpixel((x, y), near[c])
    return out


def main(src):
    os.makedirs(OUT, exist_ok=True)
    for i, name in enumerate(NAMES):
        species = 494 + i
        for essentials, suffix in [('', '')] + EXTRA.get(name, []):
            img = convert(os.path.join(src, name + essentials + '.png'))
            img.save(os.path.join(OUT, f'{species}{suffix}.png'), transparency=0, optimize=True)


if __name__ == '__main__':
    main(sys.argv[1])
