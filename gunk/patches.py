"""Pokémon Gunk's Black Version: every change to the retail ROM, applied in order by build.py.

Each patch checks the retail bytes it replaces, so a different base ROM fails loudly instead of building a broken
hack. Addresses come from the pokeblack disassembly (C:\\Projects\\pokeblack-ref, squiddonaut/pokeblack), which
assembles to the same bytes as retail.
"""
import os
import struct

from narc import Narc
import script5
import text5
from ndsrom import patch

# --- identity ------------------------------------------------------------------------------------------------------


def identity(rom):
    """Header title GUNK B (series pattern: GUNK + the retail short code), DS menu banner text.
    The game code stays IRBO so emulators keep picking the right save type."""
    rom.set_title('GUNK B')
    rom.set_banner_title("Pokémon Gunk's\nBlack Version\nNintendo")


# --- quality of life -----------------------------------------------------------------------------------------------

OVL_FIELD = 21  # loads with the overworld at 0x02187F00
OVL_MAP_CHANGE = 20  # warps: loads the new zone, at 0x02183B60


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


OVL_ITEM_USE = 91  # the party menu and its item use, at 0x021B6240


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


OPTIONS_MSG, OPTIONS_MSG_FAST, OPTIONS_MSG_INSTANT, OPTIONS_MSG_SPEED_HELP = 29, 12, 19, 25
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

    # Options text (a/0/0/2 #29): "INSTANT" in an unused empty string, and the text-speed help line
    fid = rom.file_id('a/0/0/2')
    narc = Narc(rom.file(fid))
    items = text5.entries(narc.file(OPTIONS_MSG))
    assert text5.to_str(items[OPTIONS_MSG_FAST][0]) == 'FAST' and items[OPTIONS_MSG_INSTANT][0] == []
    items[OPTIONS_MSG_INSTANT] = (text5.chars('INSTANT'), items[OPTIONS_MSG_FAST][1])
    items[OPTIONS_MSG_SPEED_HELP] = (text5.chars('Choose a text speed. Tap FAST again\nto switch to INSTANT.'),
                                     items[OPTIONS_MSG_SPEED_HELP][1])
    narc.resize_file(OPTIONS_MSG, text5.write(items))
    rom.replace_file(fid, narc.save())


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
    blob = bytearray(blob)
    if 'gGunkHmCompat' in syms:  # fieldmove.c: per species, which HMs it can learn (TM/HM bits 95-100)
        personal = Narc(rom.file(rom.file_id('a/0/1/6')))
        at = syms['gGunkHmCompat'] - CODE_HOME
        for sp in range(650):
            bits = int.from_bytes(personal.file(sp)[0x28:0x38], 'little')
            blob[at + sp] = bits >> 95 & 0x3F
    if 'gGunkFollowerSprites' in syms:  # follower.c: Black's species/gender/form -> overworld sprite table
        table = Narc(rom.file(rom.file_id('a/2/1/1'))).file(0)
        assert len(table) // 8 < 600 and len(table) % 8 == 0
        at = syms['gGunkFollowerSprites'] - CODE_HOME
        blob[at:at + len(table) + 8] = table + bytes(8)
    open(os.path.join(cc.OUT, 'gunk.bin'), 'wb').write(blob)  # what the suite compares the RAM against
    code = bytearray(rom.arm9())
    patch(code, 0x020865CC - ARM9, 'a4009f05', '8f07a003')  # ldreq r0, =0x023E0000 -> moveq r0, #0x023C0000
    rom.replace_arm9(rom.add_autoload(code, CODE_HOME, blob, bss))
    code_syms.update(syms)


OVL_OPTIONS = 68  # the Options menu, at 0x021B95A0


def thumb_bl(src, dst):
    """A Thumb BL at src to dst, as hex bytes."""
    off = (dst & ~1) - (src + 4)
    assert -0x400000 <= off < 0x400000, 'BL out of range'
    h1 = 0xF000 | (off >> 12) & 0x7FF
    h2 = 0xF800 | (off >> 1) & 0x7FF
    return struct.pack('<HH', h1, h2).hex()


def thumb_jump(dst):
    """8 bytes replacing a whole Thumb function (at a 4-aligned address): ldr r3, [pc, #0]; bx r3; .word dst."""
    return '004b1847' + struct.pack('<I', dst | 1).hex()


def options_instant(rom):
    """Pick INSTANT in Options: tap FAST while it's on (gunk/code/options.c). Replaces the menu's tap handler and its
    is-selected test, and wraps its label setup and the D-pad's store call so the button can read INSTANT."""
    code = bytearray(rom.overlay(OVL_OPTIONS))
    base = rom.overlay_base(OVL_OPTIONS)
    sym = code_syms
    patch(code, 0x021BAFD8 - base, '10b518220b1c5343', thumb_jump(sym['Gunk_Options_Tap']))
    patch(code, 0x021BB0AC - base, '18224a4305498958', thumb_jump(sym['Gunk_Options_IsSelected']))
    patch(code, 0x021B9B54 - base, '00f056f8', thumb_bl(0x021B9B54, sym['Gunk_Options_InitLabels']))
    patch(code, 0x021BB08E - base, 'fff78bff', thumb_bl(0x021BB08E, sym['Gunk_Options_StoreKey']))
    rom.replace_overlay(OVL_OPTIONS, bytes(code))


OVL_BATTLE_VIEW = 94  # at 0x021F6560


def exp_bar_x2(rom):
    """The battle EXP bar fills twice as fast. Its per-frame update (FUN_overlay_d_94__02207ef0) steps the bar one
    pixel a frame through the stepper it shares with the HP bar; the call now goes through
    Gunk_ExpGauge_Step (gunk/code/battle.c), which steps twice. The HP bar already moves one pixel a frame in Black
    (its step is the damage over the pixels it moves), so it stays as it is."""
    code = bytearray(rom.overlay(OVL_BATTLE_VIEW))
    base = rom.overlay_base(OVL_BATTLE_VIEW)
    new = thumb_bl(0x02207F3A, code_syms['Gunk_ExpGauge_Step'])
    patch(code, 0x02207F3A - base, thumb_bl(0x02207F3A, 0x02207F6C), new)  # bl Gauge_Step -> bl Gunk_ExpGauge_Step
    rom.replace_overlay(OVL_BATTLE_VIEW, bytes(code))


OVL_SUMMARY = 131  # at 0x021D4240
SUMMARY_STAT_READS = [0x021DA0EC, 0x021DA140, 0x021DA19E, 0x021DA1FC, 0x021DA25A, 0x021DA2B8, 0x021DA316]


def summary_iv_ev(rom):
    """Summary: A on the stats page cycles stats, IVs and EVs (gunk/code/summary.c). The stats page's seven reads
    of HP, max HP and the stats (FUN_overlay_d_131__021da0b0) go through Gunk_Summary_StatValue, and the summary's
    call to its key handler goes through Gunk_Summary_Keys, which takes A on that page."""
    code = bytearray(rom.overlay(OVL_SUMMARY))
    base = rom.overlay_base(OVL_SUMMARY)
    for site in SUMMARY_STAT_READS:  # bl PP_Get (FUN_02017e1c) -> bl Gunk_Summary_StatValue
        patch(code, site - base, thumb_bl(site, 0x02017E1C), thumb_bl(site, code_syms['Gunk_Summary_StatValue']))
    keys = thumb_bl(0x021D52C2, code_syms['Gunk_Summary_Keys'])
    patch(code, 0x021D52C2 - base, thumb_bl(0x021D52C2, 0x021D52D4), keys)  # bl the key handler -> the wrapper
    rom.replace_overlay(OVL_SUMMARY, bytes(code))


OVL_SCRIPT = 10  # the script engine, at 0x02155160
SCRIPT_TABLE = 0x0217062C


def script_command(rom):
    """Script opcode 0x25E (unused in retail) runs Gunk_ScriptCommand (gunk/code/script.c) instead of its debug
    handler. Its argument layout is (sub-command u16, value u16)."""
    code = bytearray(rom.overlay(OVL_SCRIPT))
    slot = SCRIPT_TABLE + script5.OP_GUNK * 4 - rom.overlay_base(OVL_SCRIPT)
    patch(code, slot, 'ddf21502', struct.pack('<I', code_syms['Gunk_ScriptCommand'] | 1).hex())
    rom.replace_overlay(OVL_SCRIPT, bytes(code))


def _edit_text(rom, narc_path, fid, edit):
    """Rewrite one message file: edit(items) changes the [(chars, attribute)] list in place."""
    archive = rom.file_id(narc_path)
    narc = Narc(rom.file(archive))
    items = text5.entries(narc.file(fid))
    edit(items)
    narc.resize_file(fid, text5.write(items))
    rom.replace_file(archive, narc.save())


def _edit_script(rom, fid, edit):
    archive = rom.file_id(script5.SCRIPTS)
    narc = Narc(rom.file(archive))
    sf = script5.ScriptFile(narc.file(fid))
    edit(sf)
    narc.resize_file(fid, sf.save())
    rom.replace_file(archive, narc.save())


SCRIPT_FIELD_COMMON, TEXT_FIELD_COMMON = 872, 263  # Repel, Sweet Scent, fishing, Entralink
MSG_REPEL_WORE_OFF, MSG_REPEL_AGAIN = 0, 13
ITEM_SUPER_REPEL, ITEM_MAX_REPEL, ITEM_REPEL = 76, 77, 79
ENDLESS_REPEL_STEPS = 250
VAR_A, VAR_B = 0x8020, 0x8021  # temporary script variables
GUNK_SET_REPEL, GUNK_ENDLESS_REPEL = 0, 1  # gunk/code/script.c sub-commands


def repel_prompt(rom):
    """When a Repel wears off and the bag has another, ask to use one (the cheapest the bag has: Repel, then Super,
    then Max). Script 872 entry 0 is the wore-off message; it now starts at new code appended to the file, which
    falls back to the retail message when the bag has none. With the Endless Repel on, the counter is quietly
    topped up instead."""
    def text(items):
        assert text5.to_str(items[MSG_REPEL_WORE_OFF][0]) == "Repel's effect wore off..." and len(items) == MSG_REPEL_AGAIN
        items.append((text5.chars("Repel's effect wore off...\nUse another Repel?"), items[MSG_REPEL_WORE_OFF][1]))
    _edit_text(rom, 'a/0/0/3', TEXT_FIELD_COMMON, text)

    S = script5

    def script(sf):
        retail = S.entries(sf.data)[0]
        assert sf.data[retail:retail + 8] == bytes.fromhex('2e00340000000200')  # lock; message 0, plain
        program = [(S.OP_LOCK,),
                   (S.OP_GUNK, GUNK_ENDLESS_REPEL, 0, VAR_A), (S.OP_PUSH_VAR, VAR_A), (S.OP_PUSH_VALUE, 0),
                   (S.OP_COMPARE, 1), (S.OP_IF, ('u8', S.IF_DIFFERENT), ('label', 'endless'))]
        for item, label in ((ITEM_REPEL, 'repel'), (ITEM_SUPER_REPEL, 'super'), (ITEM_MAX_REPEL, 'max')):
            program += [(S.OP_CHECK_ITEM, item, 1, VAR_A), (S.OP_PUSH_VAR, VAR_A), (S.OP_PUSH_VALUE, 0),
                        (S.OP_COMPARE, 1), (S.OP_IF, ('u8', S.IF_DIFFERENT), ('label', label))]
        program += [(S.OP_JUMP, ('to', retail + 2))]  # none: the retail message
        for item, label in ((ITEM_REPEL, 'repel'), (ITEM_SUPER_REPEL, 'super'), (ITEM_MAX_REPEL, 'max')):
            program += [label, (S.OP_SET_VAR, VAR_B, item), (S.OP_JUMP, ('label', 'ask'))]
        program += ['ask', (S.OP_MESSAGE, MSG_REPEL_AGAIN, 2), (S.OP_YES_NO, VAR_A),
                    (S.OP_PUSH_VAR, VAR_A), (S.OP_PUSH_VALUE, 1), (S.OP_COMPARE, 1),
                    (S.OP_IF, ('u8', S.IF_DIFFERENT), ('label', 'yes')),  # YES is 0
                    (S.OP_CLOSE,), (S.OP_RELEASE_A,), (S.OP_RELEASE_B,), (S.OP_END,),
                    'yes', (S.OP_TAKE_ITEM, VAR_B, 1, VAR_A), (S.OP_GUNK, GUNK_SET_REPEL, VAR_B, VAR_A),
                    (S.OP_CLOSE,), (S.OP_RELEASE_A,), (S.OP_RELEASE_B,), (S.OP_END,),
                    'endless', (S.OP_RELEASE_A,), (S.OP_RELEASE_B,), (S.OP_END,)]  # topped up, nothing shown
        at = len(sf.data) + len(sf.data) % 2
        sf.set_entry(0, sf.append(S.assemble(at, program)))
    _edit_script(rom, SCRIPT_FIELD_COMMON, script)


ITEM_ENDLESS_REPEL = 426  # an unused slot ("???") next to the key items
POCKET_KEY = 4
SCRIPT_RUNNING_SHOES, TEXT_RUNNING_SHOES = 638, 351  # zone 319: Mom's Running Shoes scene
MSG_SHOES_EXPLAINED = 6
OP_FANFARE, OP_FANFARE_WAIT, OP_ADD_ITEM = 0xA9, 0xAA, 0xB5
FANFARE_KEY_ITEM = 0x0517


def endless_repel(rom):
    """Endless Repel: a key item (gunk/code/bag.c, repel.c) that switches on and off from the bag. While on, the
    Repel counter is set to 250 and topped up whenever it runs out (repel_prompt's script). Mom gives it right after
    the Running Shoes, together with the Exp. All (exp_all)."""
    items = Narc(rom.file(rom.file_id('a/0/2/4')))
    data = bytearray(items.file(ITEM_REPEL))
    struct.pack_into('<H', data, 0, 0)  # no price
    data[3] = ENDLESS_REPEL_STEPS
    flags = struct.unpack_from('<H', data, 8)[0]
    struct.pack_into('<H', data, 8, flags & ~(0xF << 7) | POCKET_KEY << 7)
    assert items.file(ITEM_ENDLESS_REPEL)[:4] == bytes(4)
    items.set_file(ITEM_ENDLESS_REPEL, bytes(data))
    rom.replace_file(rom.file_id('a/0/2/4'), items.save())

    def name(fid, text):
        def edit(texts):
            assert text5.to_str(texts[ITEM_ENDLESS_REPEL][0]) in ('???', '')
            texts[ITEM_ENDLESS_REPEL] = (text, texts[ITEM_ENDLESS_REPEL][1])
        _edit_text(rom, 'a/0/0/2', fid, edit)
    name(54, text5.chars('Endless Repel'))
    name(280, text5.chars('Endless Repels'))
    name(279, [0xF000, 0xBD01, 0x0] + text5.chars('an ') + [0xF000, 0xFF00, 0x1, 0xFF] + text5.chars('Endless Repel'))
    name(53, text5.chars('Keeps weak wild Pokémon away for as long\nas it is on. Use it to switch it on or off.'))

    def bag_text(texts):
        assert len(texts) == 140
        texts += [(text5.chars('The Endless Repel is now on.'), texts[63][1]),
                  (text5.chars('The Endless Repel is now off.'), texts[63][1])]
    _edit_text(rom, 'a/0/0/2', 3, bag_text)

    code = bytearray(rom.overlay(70))
    base = rom.overlay_base(70)
    table = code_syms['gGunkBagSpecial']
    patch(code, 0x021B6EF4 - base, struct.pack('<I', 0x021BB9C4).hex(), struct.pack('<I', table).hex())
    patch(code, 0x021B710C - base, struct.pack('<I', 0x021BB9C8).hex(), struct.pack('<I', table + 4).hex())
    patch(code, 0x021B6EE8 - base, '082d', '0a2d')  # cmp r5, #8 -> #10: the Endless Repel and the Exp. All
    rom.replace_overlay(70, bytes(code))

    # Mom: after explaining the Running Shoes (message 6), she gives the Endless Repel
    def gift_text(texts):
        received = [c for c in texts[4][0]]  # "<player> received a pair of\n<Running Shoes>!"
        pair = text5.chars('a pair of')
        at = next(i for i in range(len(received)) if received[i:i + len(pair)] == pair)
        received = received[:at] + text5.chars('the') + received[at + len(pair):]
        shoes = text5.chars('Running Shoes')
        at = next(i for i in range(len(received)) if received[i:i + len(shoes)] == shoes)
        texts += [(received[:at] + text5.chars('Endless Repel') + received[at + len(shoes):], texts[4][1]),
                  (text5.chars('And this keeps weak wild Pokémon away.\nSwitch it on or off from the Key Items!'),
                   texts[MSG_SHOES_EXPLAINED][1]),
                  (received[:at] + text5.chars('Exp. All') + received[at + len(shoes):], texts[4][1]),
                  (text5.chars('With that on, your whole team learns\nfrom every battle, even from the bench!'),
                   texts[MSG_SHOES_EXPLAINED][1])]
        return len(texts) - 4
    msg = {}
    _edit_text(rom, 'a/0/0/3', TEXT_RUNNING_SHOES, lambda t: msg.setdefault('recv', gift_text(t)))

    S = script5

    def script(sf):
        hook = 0x510  # message 6, then 0x3E (14 bytes) at the end of the Running Shoes scene
        assert sf.data[hook:hook + 14] == bytes.fromhex('3c0000040600fb0000000000' + '3e00')
        explained = bytes(sf.data[hook:hook + 12])
        at = len(sf.data) + len(sf.data) % 2
        program = [(0x3C, ('u8', 0), ('u8', 4), MSG_SHOES_EXPLAINED, 0xFB, 0, 0),
                   (OP_ADD_ITEM, ITEM_ENDLESS_REPEL, 1, VAR_A), (OP_FANFARE, FANFARE_KEY_ITEM),
                   (S.OP_MESSAGE, msg['recv'], 2), (OP_FANFARE_WAIT,), (S.OP_CLOSE,),
                   (0x3C, ('u8', 0), ('u8', 4), msg['recv'] + 1, 0xFB, 0, 0),
                   (OP_ADD_ITEM, ITEM_EXP_ALL, 1, VAR_A), (OP_FANFARE, FANFARE_KEY_ITEM),
                   (S.OP_MESSAGE, msg['recv'] + 2, 2), (OP_FANFARE_WAIT,), (S.OP_CLOSE,),
                   (0x3C, ('u8', 0), ('u8', 4), msg['recv'] + 3, 0xFB, 0, 0),
                   (0x3E,), (S.OP_JUMP, ('to', hook + 14))]
        code = S.assemble(at, program)
        assert code[:12] == explained
        new = sf.append(code)
        assert new == at
        sf.data[hook:hook + 6] = S.jump_to(hook, at)
    _edit_script(rom, SCRIPT_RUNNING_SHOES, script)


ITEM_EXP_ALL = 427  # the other unused slot next to the key items
OVL_BATTLE = 93  # the battle server, at 0x021B6100


def _key_item(rom, item, name, plural, article, desc):
    """An unused item slot becomes a key item that the bag can USE (Repel's data, no price, key pocket)."""
    items = Narc(rom.file(rom.file_id('a/0/2/4')))
    data = bytearray(items.file(ITEM_REPEL))
    struct.pack_into('<H', data, 0, 0)
    flags = struct.unpack_from('<H', data, 8)[0]
    struct.pack_into('<H', data, 8, flags & ~(0xF << 7) | POCKET_KEY << 7)
    assert items.file(item)[:4] == bytes(4)
    items.set_file(item, bytes(data))
    rom.replace_file(rom.file_id('a/0/2/4'), items.save())

    def text(fid, chars):
        def edit(texts):
            assert text5.to_str(texts[item][0]) in ('???', '')
            texts[item] = (chars, texts[item][1])
        _edit_text(rom, 'a/0/0/2', fid, edit)
    text(54, text5.chars(name))
    text(280, text5.chars(plural))
    text(279, [0xF000, 0xBD01, 0x0] + text5.chars(article + ' ') + [0xF000, 0xFF00, 0x1, 0xFF] + text5.chars(name))
    text(53, text5.chars(desc))
    return data


def exp_all(rom):
    """Exp. All: a key item (gunk/code/expall.c) that switches on and off from the bag. While on, party members that
    didn't battle get half a participant's EXP (and the EVs with it). The battle server's EXP routine
    (FUN_overlay_d_93__021cb2d4) calls Gunk_ExpAll_Hook between handing out the shares and scaling them by level.
    Mom gives it with the Endless Repel."""
    _key_item(rom, ITEM_EXP_ALL, 'Exp. All', 'Exp. Alls', 'an',
              "While it is on, Pokémon that didn't battle\nstill get half the Exp. Points. Use it to switch.")

    def bag_text(texts):
        assert len(texts) == 142
        texts += [(text5.chars('The Exp. All is now on.'), texts[63][1]),
                  (text5.chars('The Exp. All is now off.'), texts[63][1])]
    _edit_text(rom, 'a/0/0/2', 3, bag_text)

    code = bytearray(rom.overlay(OVL_BATTLE))
    base = rom.overlay_base(OVL_BATTLE)
    hook = 0x021CB464
    patch(code, hook - base, '07980026', thumb_bl(hook, code_syms['Gunk_ExpAll_Hook']))  # ldr r0, [sp, #0x1c]; movs r6, #0
    rom.replace_overlay(OVL_BATTLE, bytes(code))


OVL_PARTY = OVL_ITEM_USE  # the party menu (the same overlay as its item use)


def field_moves(rom):
    """HM moves without the move (gunk/code/fieldmove.c): FUN_overlay_d_10__0215b500, the "does this Pokémon know
    this move" test behind the field-move script commands (0x116 and its sibling) and the field's own check, now
    also says yes when the bag holds that HM and the species can learn it. Badges are still checked by the
    scripts."""
    code = bytearray(rom.overlay(OVL_SCRIPT))
    base = rom.overlay_base(OVL_SCRIPT)
    patch(code, 0x0215B500 - base, '70b50c1c4c210022', thumb_jump(code_syms['Gunk_KnowsFieldMove']))
    rom.replace_overlay(OVL_SCRIPT, bytes(code))

    # party menu (overlay 91): field-move entries are 0x10 + move slot; slots 6-11 (entries 0x16-0x1B) now stand for
    # HM01-06 (entries 0x14 and 0x15 are other actions)
    code = bytearray(rom.overlay(OVL_PARTY))
    base = rom.overlay_base(OVL_PARTY)
    for site in (0x021B9616, 0x021BBC74):  # bl the slot -> field skill mapper -> Gunk_PartyFieldSkill
        patch(code, site - base, thumb_bl(site, 0x021B99E4), thumb_bl(site, code_syms['Gunk_PartyFieldSkill']))
    patch(code, 0x021BBC94 - base, '042d', '0c2d')  # the menu builds entries for slots 0-11 (was 0-3)
    patch(code, 0x021BBD5A - base, '1328', '1b28')  # field-move entries are 0x10-0x1B (colour)
    patch(code, 0x021BBDA0 - base, '132a', '1b2a')  # and (label), named by Gunk_PartyEntryMove
    patch(code, 0x021B9190 - base, 'cde2', 'fbe1')  # selecting an entry past 0x15 takes the field-move path
    label = thumb_bl(0x021BBDAC, code_syms['Gunk_PartyEntryMove'])
    patch(code, 0x021BBDAC - base, thumb_bl(0x021BBDAC, 0x02017E1C), label)
    rom.replace_overlay(OVL_PARTY, bytes(code))


POKEMON_CENTERS = [1, 8, 20, 41, 65, 99, 109, 115, 122, 146, 398, 407, 413, 425]  # zones (nurse: script 2100)
SCRIPT_MOVE_TUTORS, TEXT_MOVE_TUTORS = 859, 347  # the Move Deleter (entry 0 = script 2260) and reminder (2261)
SCRIPT_DELETER, SCRIPT_REMINDER = 2260, 2261
SPRITE_DELETER, SPRITE_REMINDER = 28, 14
TUTOR_TILES = [(6, 13), (6, 15)]  # beside the path to the counter; free in every Center (they share one layout)


def move_tutor(rom):
    """The Move Deleter and the move reminder stand in every Pokémon Center, and the reminder works for free (no
    Heart Scale). Their scripts are common (script file 859, IDs 2260 and 2261), so each Center's event file
    (a/1/2/5) just gets two more NPCs. The reminder's Heart Scale check and payment (script 859) become
    `set var = 1` (the same length, padded with a no-op), and her lines lose the Heart Scale."""
    def text(texts):
        intro = texts[31][0]
        old = text5.chars("If you bring me a Heart Scale, I'll make") + [0xFFFE] + text5.chars('a Pokémon remember a move.')
        at = next(i for i in range(len(intro)) if intro[i:i + len(old)] == old)
        texts[31] = (intro[:at] + text5.chars("I'll do it for free, as often") + [0xFFFE] + text5.chars('as you like.')
                     + intro[at + len(old):], texts[31][1])
        paid = texts[29][0]
        texts[29] = (paid[:paid.index(ord(' '))] + text5.chars(' thanked the reminder girl.'), texts[29][1])
        texts[34] = (text5.chars('If any of your Pokémon needs to') + [0xFFFE] + text5.chars('remember a move, just ask me!'),
                     texts[34][1])
    _edit_text(rom, 'a/0/0/3', TEXT_MOVE_TUTORS, text)

    def script(sf):
        for at, var in ((0x29C, 0x802C), (0x453, 0x8033)):  # check / take one Heart Scale (item 93)
            old = struct.pack('<4H', script5.OP_CHECK_ITEM if at == 0x29C else script5.OP_TAKE_ITEM, 93, 1, var)
            assert bytes(sf.data[at:at + 8]) == old
            sf.data[at:at + 8] = struct.pack('<3HH', script5.OP_SET_VAR, var, 1, 0)  # set var = 1; no-op
    _edit_script(rom, SCRIPT_MOVE_TUTORS, script)

    archive = rom.file_id('a/1/2/5')
    events = Narc(rom.file(archive))
    for zone in POKEMON_CENTERS:
        d = bytearray(events.file(zone))
        furniture, npcs = d[4], d[5]
        end = 8 + furniture * 20 + npcs * 36
        assert any(struct.unpack_from('<18H', d, 8 + furniture * 20 + k * 36)[5] == 2100 for k in range(npcs))
        new = b''
        for n, (sprite, scr, (x, y)) in enumerate(((SPRITE_DELETER, SCRIPT_DELETER, TUTOR_TILES[0]),
                                                  (SPRITE_REMINDER, SCRIPT_REMINDER, TUTOR_TILES[1]))):
            # id, sprite, movement (0: stands still), type, flag, script, facing (3: right, into the room), ..., x, y
            new += struct.pack('<18H', npcs + n, sprite, 0, 0, 0, scr, 3, 0, 0, 0, 0, 0, 0, 0, x, y, 0, 0)
        d[end:end] = new
        d[5] = npcs + 2
        struct.pack_into('<I', d, 0, struct.unpack_from('<I', d, 0)[0] + len(new))
        events.resize_file(zone, bytes(d))
    rom.replace_file(archive, events.save())


def dexnav(rom):
    """DexNav (gunk/code/dexnav.c): R in tall grass meets the chosen Pokémon of this route (first the first you
    haven't caught; L+R switches), from its own grass slot, and repeated searches build a chain for shiny odds and
    perfect IVs. Hooks in the field overlay: the per-frame
    input routine in its table at 0x021D8900, the per-frame step-encounter check (FUN_overlay_d_21__0218b208,
    called twice), the encounter's slot pick (FUN_overlay_d_21__021a954c, called at 0x021AA048), its personality
    roll and its building of the wild Pokémon."""
    code = bytearray(rom.overlay(OVL_FIELD))
    base = rom.overlay_base(OVL_FIELD)
    patch(code, 0x021D8900 - base, 'f12d1a02', struct.pack('<I', code_syms['Gunk_FieldInput'] | 1).hex())
    for site in (0x02189CA8, 0x0218A314):  # bl the step-encounter check -> the wrapper
        patch(code, site - base, thumb_bl(site, 0x0218B208), thumb_bl(site, code_syms['Gunk_StepEncount']))
    pick = thumb_bl(0x021AA048, code_syms['Gunk_DexNav_PickSlots'])
    patch(code, 0x021AA048 - base, thumb_bl(0x021AA048, 0x021A954C), pick)  # bl the slot pick -> the wrapper
    for site, retail, sym in ((0x021A96D4, 0x021A9D30, 'Gunk_DexNav_Pid'),  # chains: shiny odds
                              (0x021AA4D8, 0x021A96B8, 'Gunk_DexNav_Create')):  # and perfect IVs
        patch(code, site - base, thumb_bl(site, retail), thumb_bl(site, code_syms[sym]))
    rom.replace_overlay(OVL_FIELD, bytes(code))


def followers(rom):
    """Follower Pokémon (gunk/code/follower.c): after the field loads a zone's objects (FUN_overlay_d_21__021894e0,
    called at 0x021894BC on crossing into another zone) and after a warp (FUN_overlay_d_20__021858e4, called at
    0x021858A2), the follower is added with Black's unused "pair" movement, which walks after the
    player. That movement picks its step's speed from the player's current animation code, but Black's copy reads
    the follower's own (FUN_overlay_d_21__0219ba2c drops the player it just looked up), which is none (0xFF) for a
    follower that hasn't moved yet, so it never steps: the `adds r0, r4` that replaces the player goes."""
    code = bytearray(rom.overlay(OVL_FIELD))
    base = rom.overlay_base(OVL_FIELD)
    site = 0x021894BC
    patch(code, site - base, thumb_bl(site, 0x021894E0), thumb_bl(site, code_syms['Gunk_LoadZoneObjects']))
    patch(code, 0x0219BA38 - base, '201c', 'c046')  # adds r0, r4, #0 -> nop: the player's animation code
    rom.replace_overlay(OVL_FIELD, bytes(code))
    code = bytearray(rom.overlay(OVL_MAP_CHANGE))
    base = rom.overlay_base(OVL_MAP_CHANGE)
    site = 0x021858A2  # after a warp: FUN_overlay_d_20__021858e4 loads the new zone's objects
    patch(code, site - base, thumb_bl(site, 0x021858E4), thumb_bl(site, code_syms['Gunk_LoadWarpObjects']))
    rom.replace_overlay(OVL_MAP_CHANGE, bytes(code))


PATCHES = [identity, faster_eggs, auto_run, trade_evolutions, vitamins_to_252, text_fast_default, text_instant,
           code_home, options_instant, exp_bar_x2, summary_iv_ev, script_command, repel_prompt,
           endless_repel, exp_all, field_moves, move_tutor,
           dexnav, followers]
