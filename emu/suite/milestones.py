"""Story milestones toward a v1.0 playthrough test: .venv/Scripts/python emu/suite/milestones.py [names...]

Each milestone starts from a real save made after the starter (out/_starter.sav; `starter` plays the opening from the
suite's start state to make it), edited to that point of the story: party, bag, badges, vars, Repel. The edited save
is put down outside a door of the zone, and Continue steps through that door for real, so the zone loads its own
objects and scripts (a save edited straight into a zone loads none of them). The event is then played with the
buttons, its own check must hold, and the game is saved, power-cycled and continued: the player must come back in
the same zone on the same tile.

Milestones: mom_gifts (Route 2 gate: the Endless Repel and Exp. All), cut (the Route 2 tree), surf (zone 370's
shore, with A), strength (zone 224's cave, Tepig). The gyms through the Champion come next, one by one.
"""
import os
import struct
import sys
import time
import traceback
from collections import deque

SUITE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [SUITE, os.path.join(os.path.dirname(os.path.dirname(SUITE)), 'tools')]
import lib  # noqa: E402
import mapdata  # noqa: E402
import pk5  # noqa: E402
import suite  # noqa: E402
from lib import OUT, ROOT, Game, TestFailure, check  # noqa: E402
from ndsrom import Rom  # noqa: E402

MILESTONES = []
STARTER = os.path.join(OUT, '_starter.sav')
SAVE_RAM = 0x0221BBAC  # the save as the game keeps it in RAM: the blocks at their flash offsets
MMDL_LIST, MMDL_SIZE, MMDL_COUNT = 0x022521E4, 0x100, 24  # field objects: status +0, id +8, tile +0x3C/+0x40
PLAYER = 0xFF
PARTY, BAG, VARS_FLAGS, BADGES, REPEL = 26, 25, 45, 52, 56  # save blocks
KEY_POCKET, TM_POCKET = 0x4D8, 0x624
# X menu, SAVE (right column once the menu has POKéMON), YES, then the confirmation
SAVE_PRESSES = ['press X 4', 'wait 60', 'touch 192 93', 'wait 120', 'press A 4', 'wait 60', 'press A 4', 'wait 900']
ITEM_HM01, ITEM_HM03, ITEM_HM04 = 420, 422, 423
ITEM_ENDLESS_REPEL, ITEM_EXP_ALL = 426, 427
SPECIES_TEPIG, SPECIES_OSHAWOTT = 498, 501
MOVE_TACKLE, MOVE_SURF = 33, 57
EXP = {5: 125, 50: 117360}  # medium-slow


def milestone(fn):
    MILESTONES.append(fn)
    return fn


def log(msg):
    print('   ' + msg, flush=True)


# --- save edits -----------------------------------------------------------------------------

def make_mon(species, level=5, move2=0, pid=0x12345678):
    """A party Pokémon (PK5, 220 bytes): Tackle (and move2), OT AAAAAA, some IVs."""
    p = bytearray(220)
    struct.pack_into('<I', p, 0, pid)
    struct.pack_into('<HHHHI', p, 0x08, species, 0, 12345, 54321, EXP[level])
    p[0x14], p[0x15], p[0x17] = 70, 1, 2  # friendship, ability 1, language
    struct.pack_into('<4H', p, 0x28, MOVE_TACKLE, move2, 0, 0)
    p[0x30] = 35
    struct.pack_into('<I', p, 0x38, 0x0F7BDEF)
    name = 'GUNK'.encode('utf-16le') + b'\xff\xff'
    p[0x48:0x48 + len(name)] = name
    p[0x5F] = 21  # Black
    ot = 'AAAAAA'.encode('utf-16le') + b'\xff\xff'
    p[0x68:0x68 + len(ot)] = ot
    p[0x83], p[0x84] = 4, 5  # Poké Ball, met level
    struct.pack_into('<IBBHHHHHHH', p, 0x88, 0, level, 0, 20, 20, 10, 10, 10, 10, 10)
    return pk5.encrypt(p)


class Save:
    """Edits to both halves of a .sav image."""

    def __init__(self, path=STARTER):
        check(os.path.exists(path), f'no {os.path.basename(path)}: run "milestones.py starter" first')
        self.data = bytearray(open(path, 'rb').read())

    def edit(self, i, fn):
        for half in (0, 1):
            b = bytearray(lib.block(self.data, half, i))
            fn(b)
            lib.set_block(self.data, half, i, bytes(b))
        return self

    def party(self, *mons):
        def f(b):
            struct.pack_into('<I', b, 4, len(mons))
            for k, m in enumerate(mons):
                b[8 + k * 220:8 + (k + 1) * 220] = m
        return self.edit(PARTY, f)

    def items(self, pocket, *items):
        def f(b):
            for k, item in enumerate(items):
                struct.pack_into('<HH', b, pocket + k * 4, item, 1)
        return self.edit(BAG, f)

    def badges(self, bits):
        return self.edit(BADGES, lambda b: struct.pack_into('<I', b, 4, bits))

    def var(self, var, value):
        return self.edit(VARS_FLAGS, lambda b: struct.pack_into('<H', b, (var - 0x4000) * 2, value))

    def repel(self, steps):
        return self.edit(REPEL, lambda b: b.__setitem__(0x31, steps))

    def put(self, zone, x, z, height=0):
        """Continue at tile (x, z) of zone, standing at height (the tile layer's), with no saved objects but the
        player's: the zone's own come back when a door loads it."""
        def pos(b):
            struct.pack_into('<H', b, 0x80, zone)
            struct.pack_into('<iii', b, 0x84, (x << 16) | 0x8000, height << 12, (z << 16) | 0x8000)

        def objs(b):
            recs = [b[k * 0x50:(k + 1) * 0x50] for k in range(64)]
            keep = [r for r in recs if r != bytes(0x50) and struct.unpack_from('<H', r, 8)[0] == PLAYER]
            out = b''.join(keep) + bytes(0x50 * (64 - len(keep)))
            b[:len(out)] = out
            struct.pack_into('<HxxH', b, 0x20, x, z)
            struct.pack_into('<HxxH', b, 0x26, x, z)
        return self.edit(lib.POSITION, pos).edit(lib.OBJECTS, objs)

    def write(self, name):
        path = os.path.join(OUT, name + '.sav')
        open(path, 'wb').write(self.data)
        return path


def field_move_save(species=SPECIES_OSHAWOTT, level=5, move2=0):
    """The starter save with one Pokémon, HM01/03/04 in the bag and every badge."""
    return (Save().party(make_mon(species, level, move2)).items(TM_POCKET, ITEM_HM01, ITEM_HM03, ITEM_HM04)
            .badges(0xFF))


# --- in the game --------------------------------------------------------------------------------

def objects(g):
    """(id, x, z) of every field object in use."""
    d = g.read(MMDL_LIST, MMDL_SIZE * MMDL_COUNT)
    out = []
    for k in range(MMDL_COUNT):
        o = d[k * MMDL_SIZE:(k + 1) * MMDL_SIZE]
        if o[0] & 1:
            out.append((struct.unpack_from('<H', o, 8)[0],
                        struct.unpack_from('<h', o, 0x3C)[0], struct.unpack_from('<h', o, 0x40)[0]))
    return out


def player(g):
    """(x, z) of the player."""
    me = [o for o in objects(g) if o[0] == PLAYER]
    check(me, 'no player object')
    return me[0][1:]


def save_ram(g, i, off, length):
    return g.read(SAVE_RAM + lib.BLOCKS[i][0] + off, length)


def through_door(g, direction):
    """Walk until the player is somewhere else: through the door the save was put beside."""
    g.run('wait 30')
    start = player(g)
    for _ in range(10):
        g.run(f'press {direction} 16', 'wait 220')
        p = player(g)
        if abs(p[0] - start[0]) + abs(p[1] - start[1]) > 3:
            return p
    raise TestFailure(f'no door {direction} of {start}')


_world = None


def world():
    global _world
    if _world is None:
        _world = mapdata.World(Rom(open(os.path.join(ROOT, 'build', 'gunk-black.nds'), 'rb').read()))
    return _world


STEPS = {(1, 0): 'Right', (-1, 0): 'Left', (0, 1): 'Down', (0, -1): 'Up'}


def plan(start, goal, avoid):
    w = world()
    prev, queue = {start: None}, deque([start])
    while queue:
        p = queue.popleft()
        if p == goal:
            moves = []
            while prev[p]:
                b = prev[p]
                moves.append(STEPS[(p[0] - b[0], p[1] - b[1])])
                p = b
            return moves[::-1]
        for dx, dz in STEPS:
            n = (p[0] + dx, p[1] + dz)
            t = w.tile(*n)
            if n in prev or n in avoid or not mapdata.walkable(t) or t[1] != w.tile(*p)[1]:
                continue
            prev[n] = p
            queue.append(n)
    return None


def walk_to(g, goal, avoid=()):
    """Walk to tile goal by the map data, a few steps at a time. When the player doesn't move, a trainer or a
    sign is talking or a battle started: A through it (FIGHT, the first move, A) and, if that keeps happening,
    treat the next tile as blocked."""
    blocked, stuck = set(avoid), 0
    for _ in range(80):
        p = player(g)
        if p == goal:
            return
        moves = plan(p, goal, blocked)
        check(moves, f'no path from {p} to {goal}')
        g.run(*[f'press {d} 16' for d in moves[:4]], 'wait 10')
        if player(g) != p:
            stuck = 0
            continue
        g.run(*['press A 4', 'wait 40'] * 6,
              *['touch 128 80', 'wait 60', 'touch 64 40', 'wait 300', 'press A 4', 'wait 60', 'press A 4', 'wait 60'] * 4)
        stuck += 1
        if stuck >= 2:
            dx, dz = {v: k for k, v in STEPS.items()}[moves[0]]
            blocked.add((p[0] + dx, p[1] + dz))
            stuck = 0
    raise TestFailure(f'did not reach {goal}, at {player(g)}')


def use_field_move(g, face):
    """Face the thing and A through "use the move?" and the move's scene."""
    g.run(f'press {face} 3', 'wait 20')
    for w in (90, 90, 120, 150, 150):
        g.run('press A 4', f'wait {w}')


def save_reboot_same(g, name):
    """Save in the game (B first, to close anything still open), power-cycle, Continue: the save took (its counter
    went up), it holds the player's tile, and the game comes back on that tile."""
    before = player(g)
    old = suite.newest(g.flush())[1]
    g.run(*['press B 4', 'wait 30'] * 4, *SAVE_PRESSES)
    data = g.flush()
    half, count = suite.newest(data)
    check(count > old, f'{name}: the save did not take (counter {old} -> {count})')
    b = lib.block(data, half, lib.POSITION)
    x, z = struct.unpack_from('<i', b, 0x84)[0] >> 16, struct.unpack_from('<i', b, 0x8C)[0] >> 16
    check((x, z) == before, f'{name}: the save holds tile {(x, z)}, the player was at {before}')
    keep = os.path.join(OUT, f'_ms_{name}_saved.sav')
    open(keep, 'wb').write(data)
    suite.boot_continue(g, saveram=keep)
    g.run('wait 30')
    after = player(g)
    check(after == before, f'{name}: saved at {before}, continued at {after}')
    log(f'saved and continued in zone {struct.unpack_from("<H", b, 0x80)[0]} at {(x, z)}')


# --- milestones -------------------------------------------------------------------------------

def starter(g):
    """From the suite's start state (bedroom, new game): A through choosing the starter and both battles with
    Cheren and Bianca, until the player can walk again; save there. Remake it after a change to the opening."""
    suite.from_start(g)
    g.run('press Down 3', 'wait 20')  # the start state faces away from the gift box
    for rnd in range(200):  # about 700 presses
        g.run(*['press A 4', 'wait 40'] * 6)
        party = struct.unpack('<I', save_ram(g, PARTY, 4, 4))[0]
        if rnd % 10 == 9:
            log(f'round {rnd + 1}: party {party}, player {player(g)}, {g.shot("_ms_starter")}')
        if not party:
            continue
        # can the player walk? Down then always Up: in a battle that puts the cursor back on FIGHT
        p = player(g)
        g.run('press Down 16', 'wait 20')
        moved = player(g) != p
        g.run('press Up 16', 'wait 20')
        if moved:
            break
    else:
        raise TestFailure('the opening never gave control back')
    g.run(*SAVE_PRESSES)
    data = g.flush()
    check(suite.newest(data), 'starter: the save did not take')
    open(STARTER, 'wb').write(data)
    log(f'starter save after {rnd + 1} rounds: {suite.describe(data)}')


@milestone
def mom_gifts(g):
    """Route 2's gate: Mom explains the Running Shoes, then gives the Endless Repel and the Exp. All."""
    path = field_move_save().put(320, 2, 4).write('_ms_mom')
    suite.boot_continue(g, saveram=path)
    through_door(g, 'Left')
    g.run(*['press Left 16', 'wait 10'] * 7)
    g.run(*['press A 4', 'wait 70'] * 36)
    pocket = save_ram(g, BAG, KEY_POCKET, 40)
    keys = [struct.unpack_from('<H', pocket, k * 4)[0] for k in range(10)]
    check(ITEM_ENDLESS_REPEL in keys and ITEM_EXP_ALL in keys, f'mom_gifts: key pocket {keys}')
    save_reboot_same(g, 'mom_gifts')


VAR_ROUTE2_MOM = 0x407D  # 1 once Mom's Route 2 scene is over (else she stops the player at the gate)
CUT_TREE = (773, 618)


@milestone
def cut(g):
    """Route 2's tree, walked to through the gate from zone 320 with a Lv. 50 lead and Repel on."""
    path = field_move_save(level=50).var(VAR_ROUTE2_MOM, 1).repel(250).put(320, 2, 4).write('_ms_cut')
    suite.boot_continue(g, saveram=path)
    through_door(g, 'Left')
    walk_to(g, (CUT_TREE[0] + 1, CUT_TREE[1]), avoid={CUT_TREE})
    use_field_move(g, 'Left')
    g.run('press Left 16', 'wait 40')
    check(player(g) == CUT_TREE, f'cut: not on the tree\'s tile, at {player(g)}')
    save_reboot_same(g, 'cut')


SURF_SHORE, SURF_HEIGHT = (700, 186), 595  # zone 370, water to the south


@milestone
def surf(g):
    """Zone 370's shore: A at the water asks to Surf, and the player swims off."""
    path = field_move_save(move2=MOVE_SURF).put(370, *SURF_SHORE, SURF_HEIGHT).write('_ms_surf')
    suite.boot_continue(g, saveram=path)
    g.run('wait 30')
    use_field_move(g, 'Down')
    g.run(*['press Down 16', 'wait 40'] * 2)
    x, z = player(g)
    t = world().tile(x, z)
    check(z > SURF_SHORE[1] and t and t[2] == mapdata.WATER, f'surf: at {(x, z)}, tile {t}')
    save_reboot_same(g, 'surf')


@milestone
def strength(g):
    """Zone 224's cave, entered from zone 225: Tepig pushes the boulder below the entrance."""
    path = field_move_save(SPECIES_TEPIG).put(225, 6, 12).write('_ms_str')
    suite.boot_continue(g, saveram=path)
    through_door(g, 'Left')
    g.run(*['press Down 16', 'wait 10'] * 2)
    before = {o[0]: o[1:] for o in objects(g) if o[0] != PLAYER}
    use_field_move(g, 'Down')
    g.run(*['press Down 16', 'wait 60'] * 2)
    after = {o[0]: o[1:] for o in objects(g) if o[0] != PLAYER}
    moved = {k: (before[k], v) for k, v in after.items() if k in before and before[k] != v}
    check(moved, f'strength: nothing moved (objects {after}, player {player(g)})')
    log(f'boulder moved: {moved}')
    save_reboot_same(g, 'strength')


def main():
    args = sys.argv[1:]
    g = Game('gunk')
    g.counter = suite.FRAME_COUNTER
    if args == ['starter'] or not os.path.exists(STARTER):
        print('== starter', flush=True)
        try:
            starter(g)
        finally:
            g.stop()
        if args == ['starter']:
            return 0
    chosen = [m for m in MILESTONES if not args or m.__name__ in args]
    report = ['# Black milestones', '', time.strftime('%Y-%m-%d %H:%M'), '']
    failed = 0
    for m in chosen:
        print(f'== {m.__name__}', flush=True)
        t0 = time.time()
        try:
            m(g)
            report.append(f'- PASS {m.__name__} ({time.time() - t0:.0f} s)')
            print('   PASS', flush=True)
        except Exception as e:  # noqa: BLE001
            failed += 1
            try:
                g.shot(f'ms_{m.__name__}_fail')
            except Exception:  # noqa: BLE001
                pass
            msg = str(e) if isinstance(e, TestFailure) else traceback.format_exc()
            report.append(f'- FAIL {m.__name__}: {msg}')
            print('   FAIL ' + msg, flush=True)
        finally:
            g.stop()
    open(os.path.join(OUT, 'report_milestones.md'), 'w', encoding='utf-8').write('\n'.join(report) + '\n')
    print(f'{len(chosen) - failed}/{len(chosen)} passed', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
