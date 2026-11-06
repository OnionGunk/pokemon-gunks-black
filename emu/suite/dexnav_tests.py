"""DexNav in the game (gunk/code/dexnav.c, dexnav_save.c): the screen, a search on each kind of terrain, and the
search levels' save record.

    .venv/Scripts/python emu/suite/dexnav_tests.py [test...]      # all of them, or the ones named

Each search test opens the screen with R, picks a row (the cursor starts on the last species searched, so a test
sets that first), walks into the effect and checks the Pokémon met is the one picked, from one of the spot's own
tables, with a chain of 1 and its search level up by one; caught ones are dumped to out/dexnav/*.pk5 for the PKHeX
check. The save tests read the record (two copies, A and B, in block 64's tail of each flash half) from the cart.
Gunk's ROM only: vanilla has no DexNav (the vanilla comparison is `vanilla_loads`: a Gunk save with levels in it
continues in vanilla Black).
"""
import os
import struct
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'tools')]

import lib  # noqa: E402
import milestones as M  # noqa: E402
import pk5  # noqa: E402
import suite  # noqa: E402
from lib import OUT, Game, TestFailure, check  # noqa: E402

TESTS = []
DUMPS = os.path.join(OUT, 'dexnav')
BALLS = os.path.join(OUT, '_balls.sav')  # Route 1, a party and Master Balls
SAVE_BUFFER = 0x0221BBAC
RECORD_A, RECORD_B, HALF = 0x23918, 0x23980, 0x24000
RECORD_SIZE, RECORD_MAGIC, LEVEL_SPECIES = 0x68, 0x4E44, 32
CREATE = 0x021A96B8  # builds a wild Pokémon: r0 is the party-format Pokémon
DEX_BLOCK, DEX_CAUGHT, DEX_SEEN = 55, 0x08, 0x5C
KIND_OFFSET, KIND_SLOTS = (0x08, 0x38, 0x68, 0x98, 0xAC), (12, 12, 12, 5, 5)
SPECIES_PATRAT, SPECIES_LILLIPUP = 504, 506

DARK_SPOT = (321, 727, 589)    # Route 3's dark grass
CAVE_SPOT = (324, 15, 3)       # Wellspring Cave's floor (dust clouds)
DARK_BEHAVIOURS = (6, 7, 9, 0x22)


def test(fn):
    TESTS.append(fn)
    return fn


def log(msg):
    print('   ' + msg, flush=True)


def symbols():
    nm = 'C:/msys64/ucrt64/bin/arm-none-eabi-nm.exe'
    out = subprocess.run([nm, os.path.join(lib.ROOT, 'build', 'code', 'gunk.elf')], capture_output=True, text=True)
    return {l.split()[-1]: int(l.split()[0], 16) for l in out.stdout.splitlines() if len(l.split()) == 3}


SYM = symbols()


def u8(g, name):
    return g.read(SYM[name], 1)[0]


def u16(g, name):
    return struct.unpack('<H', g.read(SYM[name], 2))[0]


def s16(g, name):
    return struct.unpack('<h', g.read(SYM[name], 2))[0]


# --- the record --------------------------------------------------------------------------------

def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = (crc << 1 ^ 0x1021 if crc & 0x8000 else crc << 1) & 0xFFFF
    return crc


def parse(rec):
    """(good, trainer, {species: level}) of a 0x68-byte record."""
    magic, crc, trainer = struct.unpack_from('<HHI', rec, 0)
    species = struct.unpack_from(f'<{LEVEL_SPECIES}H', rec, 8)
    levels = rec[8 + LEVEL_SPECIES * 2:8 + LEVEL_SPECIES * 3]
    good = magic == RECORD_MAGIC and crc == crc16(rec[4:RECORD_SIZE])
    return good, trainer, {s: levels[i] for i, s in enumerate(species) if s}


def cart_records(data):
    """{(half, 'A' or 'B'): parse(...)} from a cart image."""
    return {(h, w): parse(data[h * HALF + at:h * HALF + at + RECORD_SIZE])
            for h in (0, 1) for w, at in (('A', RECORD_A), ('B', RECORD_B))}


def trainer_id(data, half=0):
    return struct.unpack_from('<I', data, half * HALF + 0x19414)[0]


def ram_record(g):
    return parse(g.read(SAVE_BUFFER + RECORD_A, RECORD_SIZE))


def check_cart(data, levels, label):
    """Every copy on the cart is good, for this save's trainer, with these levels."""
    tid = trainer_id(data)
    for where, (good, trainer, got) in cart_records(data).items():
        check(good and trainer == tid, f'{label}: record {where} bad (good {good}, trainer {trainer:08x} vs {tid:08x})')
        check(got == levels, f'{label}: record {where} has {got}, expected {levels}')


# --- saves and the screen ------------------------------------------------------------------------

def base(caught=(), seen=()):
    """The Route 1 save with Mewtwo (level 100) leading and a Repel on, so no wild Pokémon turns up on the way to
    the effect (the effect's own encounter skips the Repel), and these species marked caught (and seen) or seen."""
    def edit(b):
        for sp in caught:
            b[DEX_CAUGHT + (sp - 1) // 8] |= 1 << (sp - 1) % 8
        for sp in tuple(caught) + tuple(seen):
            b[DEX_SEEN + (sp - 1) // 8] |= 1 << (sp - 1) % 8
    return M.Save(BALLS).party(M.battler()).repel(250).edit(DEX_BLOCK, edit)


def screen(g, last=None):
    """L+R: the screen opens with the spot's list. With `last`, the cursor starts on that species."""
    if last is not None:
        g.poke(SYM['sLastPick'], struct.pack('<H', last))
    g.run('press L+R 4', 'wait 90')
    count = u8(g, 'sListCount')
    rows = [struct.unpack_from('<HB', g.read(SYM['sList'] + 4 * i, 3)) for i in range(count)]
    return rows


def search(g, species=None):
    """With species: register it and press R, which searches at once. Without: open the screen and pick the
    cursor's row. (species, table kind, effect tile)"""
    if species is None:
        rows = screen(g)
        check(rows, f'search: empty list at {M.player(g)}')
        g.run('press A 4', 'wait 60')
    else:
        rows = species
        g.poke(SYM['sLastPick'], struct.pack('<H', species))
        g.run('press R 4', 'wait 20')
    check(u8(g, 'sPatch') == 1, f'search: no effect came out (list {rows}, at {M.player(g)}, {g.shot("_dn_nopatch")})')
    picked = (u16(g, 'sPatchSpecies'), u8(g, 'sPatchKind'), (s16(g, 'sPatchX'), s16(g, 'sPatchZ')))
    if species is not None:
        check(picked[0] == species, f'search: picked {picked[0]}, wanted {species}')
    return picked


def meet(g, tile):
    """Walk into the effect at tile: the wild Pokémon met (decrypted), read where the game built it."""
    trace = os.path.join(OUT, '_dn_create.txt').replace(os.sep, '/')
    if os.path.exists(trace):
        os.remove(trace)
    g.run(f'trace {CREATE} {trace}')
    try:
        back = {'Left': 'Right', 'Right': 'Left', 'Up': 'Down', 'Down': 'Up'}
        last = None
        path = []
        for _ in range(30):
            if not u8(g, 'sPatch'):
                break
            x, z = M.player(g)
            path.append((x, z))
            dx, dz = tile[0] - x, tile[1] - z
            if (dx, dz) == (0, 0):
                g.run('wait 30')
                continue
            towards = [d for d, n in (('Right', dx), ('Left', -dx), ('Down', dz), ('Up', -dz)) if n > 0]
            towards.sort(key=lambda d: -abs(dx if d in ('Left', 'Right') else dz))
            # nearer axis first, then around an obstacle (never straight back the way we came)
            for d in towards + [d for d in ('Right', 'Left', 'Down', 'Up') if d not in towards and d != back.get(last)]:
                for _ in range(2):  # the first press may only turn the player
                    g.run(f'press {d} 8', 'wait 12')  # 8 frames: one tile walking, at most one surfing
                    if M.player(g) != (x, z):
                        break
                if M.player(g) != (x, z):
                    last = d
                    break
        g.run('wait 950')
    finally:
        g.run(f'unwatch {CREATE}')
    lines = open(trace).read().splitlines() if os.path.exists(trace) else []
    check(lines, f'meet: no wild Pokémon was made walking to {tile} (at {M.player(g)}, path {path}, '
                 f'{g.shot("_dn_nomeet")})')
    return pk5.decrypt(g.read(int(lines[-1].split()[1], 16), 220))


def flee(g):
    g.run('touch 128 172', 'wait 150', 'press A 4', 'wait 250')
    g.alive()


def catch(g, name):
    """Master Ball from the bag; the catch is dumped to out/dexnav/<name>.pk5 and taken out of the party again."""
    party = SAVE_BUFFER + 0x18E00
    before = struct.unpack('<I', g.read(party + 4, 4))[0]
    g.run('touch 40 168', 'wait 120', 'touch 192 48', 'wait 90', 'touch 64 40', 'wait 90', 'touch 110 173',
          'wait 600', *['press B 4', 'wait 150'] * 4)
    for _ in range(8):
        g.run('touch 128 103', 'wait 200')
        if struct.unpack('<I', g.read(party + 4, 4))[0] == before + 1:
            break
    count = struct.unpack('<I', g.read(party + 4, 4))[0]
    check(count == before + 1, f'catch {name}: party {count}, expected {before + 1} ({g.shot("_dn_nocatch")})')
    os.makedirs(DUMPS, exist_ok=True)
    open(os.path.join(DUMPS, name + '.pk5'), 'wb').write(g.read(party + 8 + 220 * before, 220))
    g.poke(party + 4, struct.pack('<I', before))
    g.run('wait 120')


def table(g):
    """The zone's encounter table, as the game loaded it (the list's)."""
    return g.read(struct.unpack('<I', g.read(SYM['sListTable'], 4))[0], 232)


def species_of(tab, kind):
    return {struct.unpack_from('<H', tab, KIND_OFFSET[kind] + 4 * i)[0] & 0x7FF for i in range(KIND_SLOTS[kind])}


def check_search(g, picked, mon, kinds, label):
    """The Pokémon met is the one picked, it is in the picked row's table, the table fits the terrain, the chain
    is 1 and the species' search level went up."""
    species, kind, _ = picked
    check(pk5.species(mon) == species, f'{label}: met {pk5.species(mon)}, picked {species}')
    check(kind in kinds, f'{label}: table kind {kind}, expected one of {kinds}')
    check(species in species_of(table(g), kind), f'{label}: {species} is not in table {kind}')
    check(u8(g, 'sChain') == 1, f'{label}: chain {u8(g, "sChain")} after one search')
    good, _, levels = ram_record(g)
    check(good and levels.get(species, 0) >= 1, f'{label}: search level {levels} (record good: {good})')
    log(f'{label}: met {species} from table {kind}, level {levels[species]}')


def run_search(g, kinds, label, name, tile_ok=None):
    """Search for each row of the spot in turn (as long as the list goes), catching each: the rows' tables must be
    the terrain's. tile_ok(x, z) checks where the effect came out."""
    rows = screen(g)
    g.run('press B 4', 'wait 60')
    check(rows, f'{label}: empty list at {M.player(g)}')
    check(all(k in kinds for _, k in rows), f'{label}: list {rows} has tables outside {kinds}')
    log(f'{label}: list {rows}')
    for n, (species, kind) in enumerate(rows):
        picked = search(g, species)
        if tile_ok:
            check(tile_ok(*picked[2]), f'{label}: effect at {picked[2]} is not on the right kind of tile')
        mon = meet(g, picked[2])
        check_search(g, picked, mon, kinds, label)
        catch(g, f'{name}_{n}_{species}_k{kind}')
        g.run(*['press B 4', 'wait 40'] * 2)


# --- tests ----------------------------------------------------------------------------------------

@test
def screen_marks(g):
    """The screen on Route 1: its grass and rustling-grass species, caught/seen/unseen marks, the cursor on the first
    not caught (then on the last pick), B closes it with no search."""
    path = base(caught=[SPECIES_PATRAT], seen=[SPECIES_LILLIPUP]).write('_dn_marks')
    suite.boot_continue(g, saveram=path)
    g.run(*['press Up 16'] * 7, 'wait 30')
    rows = screen(g)
    g.shot('dexnav_screen')
    check([s for s, _ in rows][:2] == [SPECIES_PATRAT, SPECIES_LILLIPUP], f'screen: rows {rows}')
    check({k for _, k in rows} <= {0, 2}, f'screen: tables {rows}')
    g.run('press B 4', 'wait 60')
    check(not u8(g, 'sPatch') and not u8(g, 'sPick'), 'screen: B started a search')
    picked = search(g)
    check(picked[0] == SPECIES_LILLIPUP, f'screen: the cursor started on {picked[0]}, not the first not caught')
    log(f'rows {rows}; B closes; the cursor starts on Lillipup (Patrat caught)')


@test
def r_flow(g):
    """Platinum's flow: R with a Pokémon registered searches at once (no screen, no pause); an unseen row can't be
    picked; a species of this zone that lives on the water gets "Look for ... while surfing." instead."""
    suite.boot_continue(g, saveram=base(seen=[SPECIES_LILLIPUP]).write('_dn_rflow'))
    g.run(*['press Up 16'] * 7, 'wait 30')
    g.poke(SYM['sLastPick'], struct.pack('<H', SPECIES_LILLIPUP))
    g.run('press R 4', 'wait 4')
    check(u8(g, 'sPatch') == 1, f'r_flow: R did not search at once ({g.shot("_dn_rflow")})')
    g.run('wait 700')  # it gets away
    g.run(*['press B 4', 'wait 40'] * 3)
    rows = screen(g, SPECIES_PATRAT)  # unseen in this save
    g.run('press A 4', 'wait 60')
    check(not u8(g, 'sPatch') and not u8(g, 'sPick'), 'r_flow: an unseen Pokémon was picked')
    g.shot('dexnav_not_seen')
    g.run(*['press B 4', 'wait 40'] * 3)
    water = [s for s in species_of(table(g), 3) if s][0]
    g.poke(SYM['sLastPick'], struct.pack('<H', water))
    g.run('press R 4', 'wait 60')
    check(not u8(g, 'sPatch'), 'r_flow: a water species was searched for on land')
    g.shot('dexnav_surf_hint')
    g.run(*['press B 4', 'wait 40'] * 3)
    log(f'R searched at once; unseen Patrat refused; {water} on land: surf hint (rows {rows})')


@test
def grass(g):
    """Route 1's grass: each species of the list met from its own table; the level is saved, survives a power
    cycle, and goes up again on the next search."""
    suite.boot_continue(g, saveram=base().write('_dn_base'))
    g.run(*['press Up 16'] * 7, 'wait 30')
    run_search(g, (0, 2), 'grass', 'grass')
    _, _, levels = ram_record(g)
    data = suite.save_and_check(g, 'grass')
    check_cart(data, levels, 'grass')
    path = os.path.join(OUT, '_dn_levels.sav')
    open(path, 'wb').write(data)
    suite.boot_continue(g, saveram=path)
    good, _, after = ram_record(g)
    check(good and after == levels, f'grass: after Continue the levels are {after}, saved {levels}')
    g.run('wait 30')  # saved in the grass, where the last Pokémon was met
    picked = search(g, SPECIES_PATRAT)
    meet(g, picked[2])
    _, _, again = ram_record(g)
    check(again[SPECIES_PATRAT] == levels[SPECIES_PATRAT] + 1, f'grass: level {again} after another search')
    log(f'saved {levels}; after Continue the same; one more search: Patrat {again[SPECIES_PATRAT]}')


@test
def dark_grass(g):
    """Route 3's dark grass: the dark grass and rustling tables, and the grass rustle on a dark grass tile."""
    world = M.world()

    def dark(x, z):
        layer = world._layer(world.maps[(z // 32) * world.w + x // 32])
        return layer[((z % 32) * 32 + x % 32) * 8 + 4] in DARK_BEHAVIOURS
    suite.boot_continue(g, saveram=base().put(*DARK_SPOT).write('_dn_dark'))
    g.run('wait 60')
    run_search(g, (1, 2), 'dark grass', 'dark', dark)


@test
def cave(g):
    """Wellspring Cave's floor: the cave's own and dust-cloud tables, a dust cloud that always holds the Pokémon."""
    suite.boot_continue(g, saveram=base().put(*CAVE_SPOT).write('_dn_cave'))
    g.run('wait 60')
    run_search(g, (0, 2), 'cave', 'cave')


@test
def surf(g):
    """Surfing in zone 370: the surf and rippling-water tables, and rippling water."""
    path = base().badges(0xFF).put(370, *M.SURF_SHORE, M.SURF_HEIGHT).write('_dn_surf')
    suite.boot_continue(g, saveram=path)
    g.run('wait 30')
    M.use_field_move(g, 'Down')
    g.run(*['press Down 16', 'wait 40'] * 3)
    run_search(g, (3, 4), 'surf', 'surf')


@test
def save_copies(g):
    """The record's copies on the cart: A damaged in both halves, the game uses B; both copies damaged, the levels
    start from zero; another trainer's record (a new game over an old cart), zero too. Each time the next save
    writes good copies again."""
    suite.boot_continue(g, saveram=base().write('_dn_base'))
    g.run(*['press Up 16'] * 7, 'wait 30')
    meet(g, search(g, SPECIES_PATRAT)[2])
    flee(g)
    _, _, levels = ram_record(g)
    good = suite.save_and_check(g, 'levels')
    check_cart(good, levels, 'levels')
    for damage, expect in ((('A',), levels), (('A', 'B'), {})):
        data = bytearray(good)
        for h in (0, 1):
            for w in damage:
                at = h * HALF + (RECORD_A if w == 'A' else RECORD_B) + 0x10
                data[at] ^= 0xFF
        path = os.path.join(OUT, f'_dn_damaged_{"".join(damage)}.sav')
        open(path, 'wb').write(bytes(data))
        suite.boot_continue(g, saveram=path)
        check_cart(suite.save_and_check(g, f'{damage} damaged'), expect, f'{damage} damaged, saved again')
        log(f'copy {"+".join(damage)} damaged in both halves: the next save wrote good copies of {expect}')
    # another trainer: the same cart with the trainer ID changed in both halves (as a new game would have it)
    good_path = os.path.join(OUT, '_dn_good.sav')
    open(good_path, 'wb').write(good)
    trainer_block = [k for k, b in enumerate(lib.BLOCKS) if b[0] == 0x19400][0]
    path = M.Save(good_path).edit(trainer_block, lambda b: struct.pack_into('<I', b, 0x14, trainer_id(good) ^ 0x10001))
    path = path.write('_dn_other')
    suite.boot_continue(g, saveram=path)
    check_cart(suite.save_and_check(g, 'other trainer'), {}, 'other trainer')
    log('another trainer\'s record: the levels start from zero')


@test
def new_game(g):
    """A new game started over a cart that holds levels: its first save writes an empty record for the new
    trainer, in both copies of both halves."""
    levels = os.path.join(OUT, '_dn_levels.sav')
    check(os.path.exists(levels), 'new_game: run the grass test first')
    g.start(saveram=levels)
    g.run('wait 60', 'load ' + suite.start_state(g).replace(os.sep, '/'), 'wait 30')
    g.alive()
    data = suite.save_and_check(g, 'new game')
    check_cart(data, {}, 'new game')
    log(f'new game over a cart with levels: empty records for trainer {trainer_id(data):08x}')


# frames after the confirming A: the game's save ends about +410, then the four record writes
TORN_FRAMES = list(range(400, 470, 6))


@test
def torn_record(g):
    """A power cut while the record goes to the cart, after the game's own save: from a save with Patrat at level 1,
    one more search, then the cart captured at frames through the save and the four writes. Each capture must
    continue with a good record holding level 1 (the old) or 2 (the new), never zero or a mix."""
    suite.boot_continue(g, saveram=base().write('_dn_base'))
    g.run(*['press Up 16'] * 7, 'wait 30')
    meet(g, search(g, SPECIES_PATRAT)[2])
    flee(g)
    suite.save_and_check(g, 'level 1')
    meet(g, search(g, SPECIES_PATRAT)[2])
    flee(g)
    mid = os.path.join(OUT, '_dn_before_save.state')
    g.run('save ' + mid.replace(os.sep, '/'))
    seen = []
    for frames in TORN_FRAMES:
        g.run('load ' + mid.replace(os.sep, '/'), 'wait 2', *suite.SAVE_PRESSES, f'wait {frames}')
        torn = g.flush()
        copies = {k: (v[0], v[2].get(SPECIES_PATRAT)) for k, v in cart_records(torn).items()}
        path = os.path.join(OUT, f'_dn_torn_{frames}.sav')
        open(path, 'wb').write(torn)
        suite.boot_continue(g, saveram=path)
        after = suite.save_and_check(g, f'+{frames}f re-save')
        got = cart_records(after)[(0, 'A')][2]
        check_cart(after, got, f'+{frames}f re-save')
        check(got.get(SPECIES_PATRAT) in (1, 2), f'+{frames}f: levels {got} (cart {copies})')
        seen.append((frames, got.get(SPECIES_PATRAT), copies))
        log(f'+{frames}f: continued with level {got.get(SPECIES_PATRAT)} (cart {copies})')
    check(any(lvl == 1 for _, lvl, _ in seen) and any(lvl == 2 for _, lvl, _ in seen),
          'torn_record: the captures never caught both sides of the writes: adjust TORN_FRAMES')


@test
def vanilla_loads(g):
    """A Gunk save holding levels continues in vanilla Black (the record sits outside every block)."""
    levels = os.path.join(OUT, '_dn_levels.sav')
    check(os.path.exists(levels), 'vanilla_loads: run the grass test first')
    v = Game('vanilla')
    v.counter = suite.FRAME_COUNTER
    try:
        suite.boot_continue(v, saveram=levels)
        data = open(levels, 'rb').read()
        n = suite.newest(data)
        suite.resave_matches(v, (data, n[0]), 'vanilla')
        log('vanilla Black continued from the Gunk save with levels and saved again')
    finally:
        v.stop()


def main():
    names = sys.argv[1:]
    g = Game('gunk')
    g.counter = suite.FRAME_COUNTER
    failed = 0
    report = ['# DexNav tests', '', time.strftime('%Y-%m-%d %H:%M'), '']
    try:
        for t in [t for t in TESTS if not names or t.__name__ in names]:
            print(f'== {t.__name__}', flush=True)
            t0 = time.time()
            try:
                t(g)
                report.append(f'- PASS {t.__name__} ({time.time() - t0:.0f} s)')
                print('   PASS', flush=True)
            except Exception as e:  # noqa: BLE001
                failed += 1
                msg = str(e) if isinstance(e, TestFailure) else traceback.format_exc()
                report.append(f'- FAIL {t.__name__}: {msg}')
                print('   FAIL ' + msg, flush=True)
                try:
                    g.shot(f'dexnav_{t.__name__}_fail')
                except Exception:  # noqa: BLE001
                    pass
    finally:
        g.stop()
    open(os.path.join(OUT, 'dexnav_report.md'), 'w', encoding='utf-8').write('\n'.join(report) + '\n')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
