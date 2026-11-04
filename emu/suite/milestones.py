"""Story milestones toward a v1.0 playthrough test: .venv/Scripts/python emu/suite/milestones.py [names...]

Each milestone starts from a real save made after the starter (out/_starter.sav; `starter` plays the opening from the
suite's start state to make it), edited to that point of the story: party, bag, badges, vars, Repel. The edited save
is put down outside a door of the zone, and Continue steps through that door for real, so the zone loads its own
objects and scripts (a save edited straight into a zone loads none of them). The event is then played with the
buttons, its own check must hold, and the game is saved, power-cycled and continued: the player must come back in
the same zone on the same tile.

Milestones: mom_gifts (Route 2 gate: the Endless Repel and Exp. All), cut (the Route 2 tree), surf (zone 370's
shore, with A), strength (zone 224's cave, Tepig); the gyms, each with a test-only Lv. 100 Mewtwo: striaton,
nacrene, castelia, nimbasa.
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
import zones  # noqa: E402
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
# a test-only battler: Mewtwo, Lv. 100 (slow growth), every stat 999, Dark Pulse first (no type is immune to it)
SPECIES_MEWTWO, MOVE_DARK_PULSE, EXP_SLOW_100 = 150, 399, 1250000


def milestone(fn):
    MILESTONES.append(fn)
    return fn


def log(msg):
    print('   ' + msg, flush=True)


# --- save edits -----------------------------------------------------------------------------

TRAINER = 27  # save block: +4 name (8 UTF-16 units, 0xFFFF-terminated), +0x14 trainer ID, +0x16 secret ID


def trainer():
    """(TID, SID, name bytes with terminator) of the starter save's player."""
    if not os.path.exists(STARTER):
        return 12345, 54321, 'AAAAAAA'.encode('utf-16le') + b'\xff\xff'
    b = lib.block(open(STARTER, 'rb').read(), 0, TRAINER)
    name = b[4:20]
    end = next((i for i in range(0, 16, 2) if name[i:i + 2] == b'\xff\xff'), 14) + 2
    return *struct.unpack_from('<HH', b, 0x14), bytes(name[:end])


def make_mon(species, level=5, move2=0, pid=0x12345678, moves=None, exp=None, stats=None):
    """A party Pokémon (PK5, 220 bytes): Tackle (and move2) or these moves, the starter save's player as OT (a foreign
    OT makes a high level disobey: "began to nap!"), some IVs; stats (HP, Atk, Def, Spe, SpA, SpD) are the party copy
    the game battles with."""
    tid, sid, ot = trainer()
    p = bytearray(220)
    struct.pack_into('<I', p, 0, pid)
    struct.pack_into('<HHHHI', p, 0x08, species, 0, tid, sid, EXP[level] if exp is None else exp)
    p[0x14], p[0x15], p[0x17] = 70, 1, 2  # friendship, ability 1, language
    moves = moves or (MOVE_TACKLE, move2, 0, 0)
    struct.pack_into('<4H', p, 0x28, *moves)
    for k, m in enumerate(moves):
        p[0x30 + k] = 35 if m else 0
    struct.pack_into('<I', p, 0x38, 0x0F7BDEF)
    name = 'GUNK'.encode('utf-16le') + b'\xff\xff'
    p[0x48:0x48 + len(name)] = name
    p[0x5F] = 21  # Black
    p[0x68:0x68 + len(ot)] = ot
    p[0x83], p[0x84] = 4, 5  # Poké Ball, met level
    hp, *rest = stats or (20, 10, 10, 10, 10, 10)
    struct.pack_into('<IBBHHHHHHH', p, 0x88, 0, level, 0, hp, hp, *rest)
    return pk5.encrypt(p)


def battler():
    return make_mon(SPECIES_MEWTWO, 100, moves=(MOVE_DARK_PULSE, MOVE_SURF, 0, 0), exp=EXP_SLOW_100,
                    stats=(999,) * 6, pid=0x2468ACE0)


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

    def put(self, zone, x, z, height=None):
        """Continue at tile (x, z) of zone, standing at height (the tile layer's, looked up when not given), with no
        saved objects but the player's: the zone's own come back when a door loads it."""
        if height is None:
            height = world(zone_info().header(zone)[2]).tile(x, z)[1]

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


_rom, _worlds, _zones = None, {}, None


def rom():
    global _rom
    if _rom is None:
        _rom = Rom(open(os.path.join(ROOT, 'build', 'gunk-black.nds'), 'rb').read())
    return _rom


def zone_info():
    global _zones
    if _zones is None:
        _zones = zones.Zones(rom())
    return _zones


def world(matrix=0):
    """Matrix 0 is the outdoor world; a building's is its zone header's [2] (tools/zones.py)."""
    if matrix not in _worlds:
        _worlds[matrix] = mapdata.World(rom(), matrix)
    return _worlds[matrix]


# A battle turn without A (a walk's direction presses can leave the cursor on POKéMON, and A would open it): B out of
# any message (B also advances text), then tap FIGHT and the first move (Dark Pulse on the battler) over and over. The
# action menu can take 600+ frames to accept a tap, and a B between the two taps backs out of the move screen, so the
# taps repeat densely with no B among them; on the move screen (128, 80) is an empty slot and on the action menu
# (64, 40) is nothing, so a tap that comes early or late does nothing.
BATTLE_ROUND = (['press B 4', 'wait 40'] * 2 + ['touch 128 80', 'wait 20', 'touch 64 40', 'wait 20'] * 16)
STEPS = {(1, 0): 'Right', (-1, 0): 'Left', (0, 1): 'Down', (0, -1): 'Up'}


def plan(start, goal, avoid, matrix=0):
    """Outdoors a step keeps to one height layer (bridges); in a building stairs change it."""
    w = world(matrix)
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
            if n in prev or n in avoid or not mapdata.walkable(t) or (matrix == 0 and t[1] != w.tile(*p)[1]):
                continue
            prev[n] = p
            queue.append(n)
    return None


HONEY_HOLD = 300  # frames: the honey gives way to a push held this long (Castelia Gym)


def walk_to(g, goal, avoid=(), matrix=0, rounds=80, honey=()):
    """Walk to tile goal by the map data, a few steps at a time. When the player stops short, a trainer or a sign
    is talking or a battle started: B through it (FIGHT, the first move, B); a tile the player fails to enter twice
    is treated as blocked (a person, a curtain). A step into a honey tile is one hold of HONEY_HOLD frames: shorter
    holds bounce the player back, longer ones walk on through the next open wall."""
    blocked, fails = set(avoid), {}
    for _ in range(rounds):
        p = player(g)
        if p == goal:
            return
        moves = plan(p, goal, blocked, matrix)
        if not moves and blocked != set(avoid):  # guessed wrong (a battle made it look blocked): forget the guesses
            blocked, fails = set(avoid), {}
            moves = plan(p, goal, blocked, matrix)
        check(moves, f'no path from {p} to {goal}')
        if os.environ.get('MS_VERBOSE'):
            log(f'walk {p} -> {goal}: {"".join(m[0] for m in moves)} {g.shot("_ms_walk")}')
        path, at = [], p
        for m in moves[:4]:
            dx, dz = {v: k for k, v in STEPS.items()}[m]
            at = (at[0] + dx, at[1] + dz)
            if at in honey and path:  # walk up to the honey; the push is a step of its own
                break
            path.append(at)
            if at in honey:
                break
        pushing = path[-1] in honey
        g.run(*[f'press {d} {HONEY_HOLD if pushing else 16}' for d in moves[:len(path)]], 'wait 10')
        now = player(g)
        if now == path[-1] or pushing and now != p:  # a push can carry the player a tile or two past the honey
            continue
        stuck_at = path[path.index(now) + 1] if now in path else path[0] if now == p else None
        g.run(*['press B 4', 'wait 40'] * 6, *BATTLE_ROUND * 4)
        if stuck_at:
            fails[stuck_at] = fails.get(stuck_at, 0) + 1
            if fails[stuck_at] >= 2:
                blocked.add(stuck_at)
    raise TestFailure(f'did not reach {goal}, at {player(g)}')


def var(g, v):
    return struct.unpack('<H', save_ram(g, VARS_FLAGS, (v - 0x4000) * 2, 2))[0]


def badges(g):
    return struct.unpack('<I', save_ram(g, BADGES, 4, 4))[0]


def talk_and_fight(g, face, done, rounds=20):
    """Face someone, A to talk, then battle rounds and B through what follows until done(g)."""
    g.run(f'press {face} 3', 'wait 20', 'press A 4', 'wait 50')
    for _ in range(rounds):
        g.run(*['press B 4', 'wait 50'] * 4, *BATTLE_ROUND)
        if done(g):
            g.run(*['press B 4', 'wait 60'] * 12)  # the badge, the TM, the leader's last lines
            return
    raise TestFailure(f'still not done after {rounds} rounds, at {player(g)}')


def use_field_move(g, face):
    """Face the thing and A through "use the move?" and the move's scene."""
    g.run(f'press {face} 3', 'wait 20')
    for w in (90, 90, 120, 150, 150):
        g.run('press A 4', f'wait {w}')


def settle(g, rounds=40):
    """B through whatever follows (a leader's speech, a cutscene that walks the player off) until a step moves the
    player; step back."""
    back = {'Down': 'Up', 'Up': 'Down', 'Left': 'Right', 'Right': 'Left'}
    for _ in range(rounds):
        g.run(*['press B 4', 'wait 40'] * 4)
        for d in ('Down', 'Up', 'Left', 'Right'):
            p = player(g)
            g.run(f'press {d} 16', 'wait 20')
            if player(g) != p:
                g.run(f'press {back[d]} 16', 'wait 20')
                return
    raise TestFailure(f'never got control back, at {player(g)}')


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


# --- gyms ---------------------------------------------------------------------------------------
# Each gym starts from the starter save with the badges before it and the test battler (battler()), put outside the
# gym's door (tools/zones.py lists a zone's warps: the door is the warp tile, the save goes on the tile in front).

def gym_save(badge_count):
    return Save().party(battler()).badges((1 << badge_count) - 1)


def got_badge(n):
    return lambda g: badges(g) >> n & 1


STRIATON_GYM = 51  # zone 7's matrix
VAR_STRIATON_CURTAINS = 0x4082  # 1 after the waiter's welcome, +1 per curtain opened


@milestone
def striaton(g):
    """Striaton Gym (zone 7, door at (788, 586) in zone 6): each curtain opens on the switch of the type that beats
    it (water, grass, fire: x 15, 9, 12), then the leader the starter chose; the Trio Badge."""
    path = gym_save(0).put(6, 788, 587).write('_ms_striaton')
    suite.boot_continue(g, saveram=path)
    through_door(g, 'Up')
    switches = {(sx, row) for row in (36, 26, 16) for sx in (9, 12, 15)}
    for row, x in ((36, 15), (26, 9), (16, 12)):
        before = var(g, VAR_STRIATON_CURTAINS)
        try:
            walk_to(g, (x, row), avoid=switches - {(x, row)}, matrix=STRIATON_GYM)
        except TestFailure:  # the last curtain's scene can leave the player past the switch: the var says
            pass
        g.run(*['press B 4', 'wait 50'] * 6)
        check(var(g, VAR_STRIATON_CURTAINS) > before, f'striaton: the switch at {(x, row)} opened nothing')
    walk_to(g, (12, 4), avoid=switches, matrix=STRIATON_GYM)
    talk_and_fight(g, 'Up', got_badge(0))
    save_reboot_same(g, 'striaton')


NACRENE_MUSEUM, NACRENE_GYM, NACRENE_BASEMENT = 52, 55, 120  # zones 17, 18, 19
NACRENE_READER = 2  # the School Kid sitting at (13, 11), in front of the switch book
VAR_NACRENE_MEMOS = 0x408A  # Lenora's library quiz: 6 once the four memos and the quiz trainers are done


@milestone
def nacrene(g):
    """Nacrene Gym: through the museum (door (644, 581) in zone 16) to the library behind it. The four-memo quiz is a
    chain of book reads and yes/no answers; the save starts it solved (var 6), and the run does the rest: the School Kid
    sitting in front of the book at (13, 10), the switch in it, the hidden staircase at (12, 9) (entered from (11, 9),
    moving Right), Lenora below; the Basic Badge."""
    path = gym_save(1).var(VAR_NACRENE_MEMOS, 6).put(16, 644, 582).write('_ms_nacrene')
    suite.boot_continue(g, saveram=path)
    through_door(g, 'Up')
    walk_to(g, (11, 3), matrix=NACRENE_MUSEUM)
    through_door(g, 'Up')
    walk_to(g, (12, 11), matrix=NACRENE_GYM)
    talk_and_fight(g, 'Right', lambda g: (NACRENE_READER, 14, 12) in objects(g))  # beaten, she gets up and steps aside
    walk_to(g, (13, 12), matrix=NACRENE_GYM)
    g.run('press Up 16', 'wait 30', 'press Up 3', 'wait 20')  # her chair: only enterable from below
    for _ in range(25):  # the book, its memo and the shelves sliding aside: about 17 messages
        g.run('press A 4', 'wait 120')
        if var(g, VAR_NACRENE_MEMOS) == 7:
            break
    check(var(g, VAR_NACRENE_MEMOS) == 7, f'nacrene: the switch book did nothing (var {var(g, VAR_NACRENE_MEMOS)})')
    g.run(*['press B 4', 'wait 60'] * 6)
    g.run('press Down 16', 'wait 30')
    walk_to(g, (11, 9), matrix=NACRENE_GYM)
    through_door(g, 'Right')  # the staircase at (12, 9) is entered from the side
    walk_to(g, (5, 11), matrix=NACRENE_BASEMENT)
    talk_and_fight(g, 'Up', got_badge(1))
    settle(g)  # Lenora's win runs straight into the museum break-in scene
    save_reboot_same(g, 'nacrene')


CASTELIA_GYM = 56  # zone 29
CASTELIA_HONEY = {(32, 33), (38, 29), (26, 29), (20, 25), (26, 21), (38, 21), (32, 17)}  # the walls' blocker objects
# Each room's centre tile is a switch (script file 58: command 0x18d sets switch k, overlay 38 0x021F42BC). A honey
# wall opens once its switch, or both of its pair, are set (overlay 38 tables 0x021F4628 partners and 0x021F4632
# walls): (38, 29) needs (32, 29) and (44, 29); (38, 21) needs (32, 21) and (44, 21); (26, 21) needs (32, 21) and
# (20, 21); (26, 29) and (20, 25) need (26, 25) and (32, 29), one each; the last wall, (32, 17), needs both side
# rooms, (26, 17) and (38, 17). A closed wall doesn't give way however long the push.
CASTELIA_ROUTE = [  # (tile, the honey walls open once the player has stood there)
    ((32, 29), set()), ((44, 29), {(38, 29)}), ((26, 25), set()), ((32, 21), {(26, 29), (20, 25)}),
    ((44, 21), {(38, 21)}), ((20, 21), {(26, 21)}), ((38, 17), set()), ((26, 17), {(32, 17)}), ((32, 5), set())]
VAR_BURGH_BACK = 0x40D7  # 1 once Burgh is back from Prime Pier (script file 112); until then he isn't in the Gym


@milestone
def castelia(g):
    """Castelia Gym (zone 29, door at (25, 48) on street zone 31): pushing through the honey walls (a long hold
    each), by way of the room switches that unlock them, to Burgh; the Insect Badge. The save has Burgh back from
    Prime Pier."""
    path = gym_save(2).var(VAR_BURGH_BACK, 1).put(31, 24, 48).write('_ms_castelia')
    suite.boot_continue(g, saveram=path)
    through_door(g, 'Right')
    shut = CASTELIA_HONEY - {(32, 33)}
    for stop, opened in CASTELIA_ROUTE:
        walk_to(g, stop, avoid=shut, matrix=CASTELIA_GYM, rounds=60, honey=CASTELIA_HONEY)
        shut -= opened
    talk_and_fight(g, 'Up', got_badge(2))
    save_reboot_same(g, 'castelia')


NIMBASA_LOBBY, NIMBASA_GYM = 107, 57  # zones 64, 63
# Four roller-coaster cars (overlay 39) join the platforms; a car serves the stations in overlay 39's table at
# 0x021F4C58 (0x021F4C0C: station -> car), and the floor switch for car k (script file 126: command 0x180(k)) changes
# where it goes. A at a station calls the car, A and Up board it, it parks two tiles above a station and Down steps out.
NIMBASA_STATIONS = {(14, 39), (22, 39), (16, 27), (16, 15), (41, 40), (49, 40), (34, 8), (22, 8), (5, 39)}
NIMBASA_ROUTE = [  # (station, the car's switch to step on first, where the ride must stop)
    ((14, 39), None, (22, 39)), ((22, 39), (29, 33), (16, 27)), ((16, 15), (13, 16), (41, 40)), ((49, 40), None, (34, 8))]


def coaster(g, station):
    """Call the car to the station, board it and ride to where it parks; Down steps out. A trainer who sees the player
    on the way to the car is fought (the walk breaks off), then the car is called again."""
    for _ in range(4):
        walk_to(g, station, matrix=NIMBASA_GYM, rounds=30)
        g.run('press Up 16', 'wait 30', 'press A 4', 'wait 700')
        for _ in range(10):
            g.run('press A 4', 'wait 80', 'press Up 16', 'wait 40')
            if player(g) != station:
                break
        if player(g)[1] <= station[1] - 2:
            break
        g.run(*['press B 4', 'wait 40'] * 6, *BATTLE_ROUND * 3, *['press B 4', 'wait 50'] * 6)
    else:
        raise TestFailure(f'nimbasa: no car came to {station}')
    seen = []
    for _ in range(80):
        g.run('wait 40')
        seen.append(player(g))
        if len(seen) > 4 and len(set(seen[-4:])) == 1:
            if (seen[-1][0], seen[-1][1] + 2) in NIMBASA_STATIONS:
                break
            g.run(*['press B 4', 'wait 40'] * 6, *BATTLE_ROUND * 2)  # stopped on the track: a trainer
            seen = []
    g.run('press Down 16', 'wait 60')
    return player(g)


@milestone
def nimbasa(g):
    """Nimbasa Gym: through the lobby (door at x 436, z 460-464 in zone 62, entered moving Right) to the coasters, the
    four rides of NIMBASA_ROUTE to the top platform, Elesa; the Bolt Badge."""
    path = gym_save(3).put(62, 435, 462).write('_ms_nimbasa')
    suite.boot_continue(g, saveram=path)
    through_door(g, 'Right')
    walk_to(g, (39, 11), matrix=NIMBASA_LOBBY)
    through_door(g, 'Up')
    for station, switch, stop in NIMBASA_ROUTE:
        if switch:
            walk_to(g, switch, matrix=NIMBASA_GYM, rounds=30)
            g.run(*['press B 4', 'wait 40'] * 4)
        end = coaster(g, station)
        check(end == stop, f'nimbasa: the car from {station} stopped at {end}, not {stop}')
    walk_to(g, (28, 5), matrix=NIMBASA_GYM, rounds=30)
    talk_and_fight(g, 'Up', got_badge(3))
    save_reboot_same(g, 'nimbasa')


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
