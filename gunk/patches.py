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


def auto_run(rom):
    """Run without holding B; hold B to walk. Only where running is allowed already: the Running Shoes (event flag
    0x963, FUN_overlay_d_21__021a35bc) still have to be in the bag, and bike, surf and the rest are untouched.
    - FUN_overlay_d_21__021a4dc0 picks the on-foot step on grid maps: shoes and B held -> run (0x58), else walk (0x0C).
    - The state picker before it skips the turn-in-place when you set off running in a new direction.
    - FUN_overlay_d_21__021a5edc is the same choice on rail maps (B held -> 0x58)."""
    code = bytearray(rom.overlay(OVL_FIELD))
    base = rom.overlay_base(OVL_FIELD)
    patch(code, 0x021A4DE4 - base, '24d0', '24d1')  # tst B, held keys; beq walk -> bne walk
    patch(code, 0x021A457E - base, '01d1', '01d0')  # bne no-turn -> beq no-turn
    patch(code, 0x021A5EF0 - base, '01d0', '01d1')  # rail: beq walk -> bne walk
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


OVL_ITEM_USE = 91  # party-menu item use


def _thumb_imm_patch(code, base, lo, hi, old, new, count):
    """Rewrite every Thumb instruction halfword `old` in [lo, hi) to `new`; there must be exactly `count`."""
    hits = [a for a in range(lo, hi, 2) if code[a - base:a - base + 2] == old.to_bytes(2, 'little')]
    assert len(hits) == count, f'{len(hits)} hits for {old:#06x} in {lo:#x}-{hi:#x}, expected {count}'
    for a in hits:
        code[a - base:a - base + 2] = new.to_bytes(2, 'little')


def vitamins_to_252(rom):
    """Vitamins work up to 252 EVs in a stat (retail stops at 100); the 510 total and the wings' 255 stay.
    FUN_overlay_d_91__021bdd78 decides whether an item can be used (one "EV < 100" test per stat, after 0x021BDECA) and
    FUN_overlay_d_91__021be948 computes the new EV (clamped to 100 for vitamins)."""
    code = bytearray(rom.overlay(OVL_ITEM_USE))
    base = rom.overlay_base(OVL_ITEM_USE)
    for reg in range(8):  # cmp rN, #100 -> #252
        old = 0x2800 | reg << 8 | 0x64
        n = {0: 4, 5: 1, 7: 1}.get(reg, 0)
        _thumb_imm_patch(code, base, 0x021BDECA, 0x021BE2B4, old, old & 0xFF00 | 0xFC, n)
    _thumb_imm_patch(code, base, 0x021BE948, 0x021BE9BC, 0x2864, 0x28FC, 2)  # cmp r0, #100
    _thumb_imm_patch(code, base, 0x021BE948, 0x021BE9BC, 0x2064, 0x20FC, 1)  # mov r0, #100
    rom.replace_overlay(OVL_ITEM_USE, bytes(code))

ARM9 = 0x02004000


def text_fast_default(rom):
    """New games start on FAST text instead of MID. FUN_02008320 (the options' new-game defaults) sets text
    speed, the low 4 bits of the options u16, with `mov r0, #1; orr r1, r0`, and reuses that r0 = 1 for the next
    field (`lsl r0, r0, #9`). So: `add r1, #2` (the bits were just cleared), then `mov r0, #1`."""
    code = bytearray(rom.arm9())
    patch(code, 0x02008332 - ARM9, '01200143', '02310120')
    rom.replace_arm9(bytes(code))


TEXT_WAITS = 0x0209DFB0  # s8[5] + padding: frames per character, or characters per frame when negative
INSTANT_WAIT = -127


def text_instant(rom):
    """INSTANT text speed: option value 3 (after SLOW, MID, FAST). Every printer gets its speed from the wait table
    through one of three mappers (FUN_02012ffc: option as index; FUN_02013020: option + 1, for faster contexts;
    FUN_02013050: 0,1,2 -> 4,0,1, for slower ones), the last two through FUN_02013080, which clamps the index to 4.
    The table's padding byte 5 becomes the INSTANT wait, the clamps let 5 through, and every mapper sends 3 to 5.
    The new mapper bodies were assembled with arm-none-eabi-as (source in the comments)."""
    code = bytearray(rom.arm9())
    a = lambda addr: addr - ARM9  # noqa: E731
    patch(code, a(TEXT_WAITS + 5), '00', struct.pack('<b', INSTANT_WAIT).hex())
    patch(code, a(0x0201300A), '052800d30420', '032800d30520')  # cmp r0, #3; blo; movs r0, #5 (was #5, #4)
    patch(code, a(0x02013080), '0528', '0628')  # FUN_02013080: cmp r0, #6 (was #5)
    # FUN_02013020: cmp r0, #3; blo 1f; movs r0, #4; 1: adds r0, #1; nop x8
    patch(code, a(0x0201302E), '002804d0012804d0022804d004e0012002e0022000e00320',
          '032800d304200130' + 'c046' * 8)
    # FUN_02013050: cmp r0, #3; bhs 3f; subs r0, #1; bpl 4f; movs r0, #4; b 4f; 3: movs r0, #5; 4: nop x5
    patch(code, a(0x0201305E), '002804d0012804d0022804d004e0042002e0002000e00120',
          '032803d2013802d5042000e00520' + 'c046' * 5)
    rom.replace_arm9(bytes(code))


# --- code home --------------------------------------------------------------------------------------------------

CODE_HOME = 0x023C0000  # 128 KB up to 0x023E0000, where the ARM7's part of main RAM starts
code_syms = {}  # symbol -> address of the compiled code, for hooks


def code_home(rom):
    """Room for new code: gunk/code/*.c, compiled by tools/cc.py, goes in as a fifth ARM9 autoload block, which
    crt0 copies to 0x023C0000 at boot before anything else runs. The main arena's top drops from 0x023E0000 to the
    same address, so no heap can be made over it: OS_GetInitArenaHi (FUN_02086594) returns it for the main arena
    from a literal it shares with another case, so the `ldreq` becomes a `moveq` with the new value. After the
    game makes its heaps the arena's free part was 0x023B47F0-0x023E0000 (measured in the field); 46 KB of it stay
    free."""
    import cc
    blob, bss, syms = cc.build()
    assert CODE_HOME + len(blob) == syms['__bss_start'], 'gunk/code: .bss does not follow the code'
    assert len(blob) + bss <= 0x20000, 'gunk/code: over 128 KB'
    code = bytearray(rom.arm9())
    patch(code, 0x020865CC - ARM9, 'a4009f05', '8f07a003')  # ldreq r0, =0x023E0000 -> moveq r0, #0x023C0000
    rom.replace_arm9(rom.add_autoload(code, CODE_HOME, blob, bss))
    code_syms.update(syms)


PATCHES = [identity, faster_eggs, auto_run, trade_evolutions, vitamins_to_252, text_fast_default, text_instant,
           code_home]
