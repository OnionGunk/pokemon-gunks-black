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


PATCHES = [identity]
