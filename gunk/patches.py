"""Pokémon Gunk's Black Version: every change to the retail ROM, applied in order by build.py.

Each patch checks the retail bytes it replaces, so a different base ROM fails loudly instead of building a broken
hack. Addresses come from the pokeblack disassembly (C:\\Projects\\pokeblack-ref, squiddonaut/pokeblack), which
assembles to the same bytes as retail.
"""
import struct

from narc import Narc
from ndsrom import patch

# --- identity ------------------------------------------------------------------------------------------------------


def identity(rom):
    """Header title GUNK B (series pattern: GUNK + the retail short code), DS menu banner text.
    The game code stays IRBO so emulators keep picking the right save type."""
    rom.set_title('GUNK B')
    rom.set_banner_title("Pokémon Gunk's\nBlack Version\nNintendo")


# --- quality of life -----------------------------------------------------------------------------------------------

OVL_FIELD = 21  # loads with the overworld at 0x02187F00


def faster_eggs(rom):
    """Eggs hatch twice as fast: 2 egg cycles per 256 steps, 4 with Flame Body or Magma Armor (retail 1 and 2).
    FUN_overlay_d_21__0218aa2c is Gen 5's Party_GetEggCyclesToSubtract."""
    code = bytearray(rom.overlay(OVL_FIELD))
    base = rom.overlay_base(OVL_FIELD)
    patch(code, 0x0218AA66 - base, '0220', '0420')  # mov r0, #2 -> #4 (Flame Body / Magma Armor)
    patch(code, 0x0218AA70 - base, '0120', '0220')  # mov r0, #1 -> #2
    rom.replace_overlay(OVL_FIELD, bytes(code))


# evolution methods (a/0/1/9: 7 entries of method, param, target per species)
EVO_LEVEL, EVO_TRADE, EVO_TRADE_ITEM, EVO_TRADE_SPECIES, EVO_ITEM, EVO_LEVEL_WITH_PARTNER = 4, 5, 6, 7, 8, 22

# species that evolve by trade alone get a level evolution as well (Platinum: Kadabra 36, the others 37)
TRADE_LEVELS = {64: 36, 67: 37, 75: 37, 93: 37,  # Kadabra, Machoke, Graveler, Haunter
                525: 37, 533: 37}  # Boldore, Gurdurr (Gen 5)
# Karrablast and Shelmet evolve when traded for each other: level up with the other one in the party instead
TRADE_PARTNERS = {588: 616, 616: 588}

ITEM_STONE_TEMPLATE = 82  # Fire Stone


def trade_evolutions(rom):
    """Trade evolutions without trading. The trade stays a valid way too; the new entries sit in free slots.
    Trade-with-item evolutions also work by using the item like an evolution stone."""
    fid = rom.file_id('a/0/1/9')
    evo = Narc(rom.file(fid))
    items = set()

    def entries(sp):
        f = evo.file(sp)
        return [list(struct.unpack_from('<HHH', f, i * 6)) for i in range(7)]

    def store(sp, ents):
        evo.set_file(sp, b''.join(struct.pack('<HHH', *e) for e in ents))

    def add(ents, entry):
        free = next(i for i, e in enumerate(ents) if e[0] == 0)
        ents[free] = entry

    for sp in range(evo.count):
        ents = entries(sp)
        changed = False
        for method, param, target in [e for e in ents if e[0]]:
            if method == EVO_TRADE and sp in TRADE_LEVELS:
                add(ents, [EVO_LEVEL, TRADE_LEVELS[sp], target])
                changed = True
            elif method == EVO_TRADE_ITEM:
                add(ents, [EVO_ITEM, param, target])
                items.add(param)
                changed = True
            elif method == EVO_TRADE_SPECIES:
                add(ents, [EVO_LEVEL_WITH_PARTNER, TRADE_PARTNERS[sp], target])
                changed = True
        if changed:
            store(sp, ents)
    for sp in TRADE_LEVELS:
        assert any(e[0] == EVO_LEVEL for e in entries(sp)), sp
    rom.replace_file(fid, evo.save())

    # the trade items get the evolution stones' use settings (field use 0x0A, use type 0x0C/0x0D, party-use flag
    # 0x11); held effect, price and bag sort order stay
    fid = rom.file_id('a/0/2/4')
    itemdata = Narc(rom.file(fid))
    stone = itemdata.file(ITEM_STONE_TEMPLATE)
    for item in sorted(items):
        d = bytearray(itemdata.file(item))
        assert d[0x0A] == 0 and d[0x11] == 0, f'item {item} already has a use'
        for off in (0x0A, 0x0C, 0x0D, 0x11):
            d[off] = stone[off]
        itemdata.set_file(item, bytes(d))
    rom.replace_file(fid, itemdata.save())


PATCHES = [identity, faster_eggs, trade_evolutions]
