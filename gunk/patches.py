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


PATCHES = [identity, faster_eggs]
