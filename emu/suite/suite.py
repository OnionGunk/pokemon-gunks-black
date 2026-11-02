"""Black save-safety suite (adapted from the HeartGold and Platinum hacks' suites).

  py -3 suite.py make_start             power on, play the real intro to the bedroom (Save works there), keep a state
  py -3 suite.py save_cycles torn_save   run these tests (default: all)
  py -3 suite.py --rom vanilla ...      the same tests on the unmodified build (the control)

Results: out/report_<rom>.md; screenshots: out/<test>_*.png. Exit code 0 means every test passed. Every test also
fails if the game's frame counter stops (crash or hang).

Black has no linker map, so the checks go through the save itself. Black writes the whole save to both flash halves
every time (main, then backup), and the checksum-table block's footer holds a save counter. "Continued where it was
saved" is checked by saving again right after Continue: the counter must go up by one, and the position, party,
bag and boxes must be the same as in the save that was loaded.
"""
import os
import struct
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import HALF, OUT, ROOT, TABLE, Game, TestFailure, block, check, footer, half_ok, half_status  # noqa: E402

TESTS = []
FRAME_COUNTER = 0x020AA1A0  # +0xC in the main system struct at 0x020AA194 (TwlMain), counts main-loop frames
# blocks that must survive a reload unchanged: box names, boxes 1-24, inventory, party, position
KEPT = list(range(0, 27)) + [28]
POSITION = 28

# X menu, SAVE (bottom screen, left column, second row), A on YES, A to confirm; Black never asks to overwrite
SAVE_PRESSES = ['press X 4', 'wait 60', 'touch 64 93', 'wait 120', 'press A 4', 'wait 60', 'press A 4']
SAVE_DONE = 900  # frames until "Saving..." is over and the menu has closed
# power on: skip the intro movie, title screen, CONTINUE (first entry when a save exists), season card
BOOT_PRESSES = ['wait 1500'] + ['press Start 4', 'wait 400'] * 3  # Start on the menu does nothing
CONTINUE_PRESSES = ['press A 4', 'wait 700']


def test(fn):
    TESTS.append(fn)
    return fn


def log(msg):
    print('   ' + msg, flush=True)


def start_state(g):
    return os.path.join(OUT, f'start_{g.rom}.state')


# --- save format --------------------------------------------------------------------------------

def counter(data, half):
    return struct.unpack_from('<I', footer(data, half, TABLE))[0]


def newest(data):
    """(half, counter) of the newest valid half, or None."""
    good = [(counter(data, h), h) for h in (0, 1) if half_ok(data, h)]
    return (max(good)[1], max(good)[0]) if good else None


def describe(data):
    out = []
    for h in (0, 1):
        bad = [i for i, (ok, _, _) in enumerate(half_status(data, h)) if not ok]
        out.append(f'half {h} #{counter(data, h)} ' + ('ok' if not bad else f'{len(bad)} bad block(s) {bad[:5]}'))
    return ', '.join(out)


def kept(data, half):
    return {i: block(data, half, i) for i in KEPT}


# --- shared steps -------------------------------------------------------------------------------

def new_game(g):
    g.counter = FRAME_COUNTER
    return g


def from_start(g):
    """Fresh cart, then the savestate made by make_start (an unsaved new game in the bedroom)."""
    path = start_state(g)
    check(os.path.exists(path), f'no start state: run "suite.py --rom {g.rom} make_start" first')
    g.start(fresh_save=True)
    g.run('wait 60', 'load ' + path.replace(os.sep, '/'), 'wait 30')
    g.alive()


def save_and_check(g, label):
    """In-game save, write the cart to disk, check both halves. Returns the cart bytes."""
    g.run(*SAVE_PRESSES, f'wait {SAVE_DONE}')
    g.alive()
    data = g.flush()
    log(f'{label}: {describe(data)}')
    check(half_ok(data, 0) and half_ok(data, 1), f'{label}: a flash half has a bad block after a completed save')
    check(counter(data, 0) == counter(data, 1), f'{label}: the two halves hold different saves')
    return data


def boot_continue(g, saveram=None):
    """Power on (with this cart file, or the cart as it is) and Continue."""
    g.stop()
    g.start(saveram=saveram)
    g.run(*BOOT_PRESSES)
    g.shot('_boot_menu')
    g.run(*CONTINUE_PRESSES)
    g.alive()


def resave_matches(g, loaded, label):
    """Save right after Continue and compare with the save that should have loaded (`loaded` = cart bytes and
    half). The counter must be one higher and position, party, bag and boxes unchanged."""
    data, half = loaded
    before = counter(data, half)
    after = save_and_check(g, label + ' re-save')
    check(counter(after, 0) == before + 1,
          f'{label}: re-save has counter {counter(after, 0)}, expected {before + 1} (did Continue reach the field?)')
    a, b = kept(data, half), kept(after, 0)
    diff = [i for i in KEPT if a[i] != b[i]]
    check(not diff, f'{label}: blocks {diff} changed between the loaded save and the re-save (position = 28)')
    return after


def take_steps(g, n):
    """Move somewhere new in the bedroom so each save holds a different position."""
    moves = ['press Left 16', 'press Down 16', 'press Right 16', 'press Up 16']
    g.run(moves[n % 4], 'wait 30')


CODE_HOME, CODE_HOME_END = 0x023C0000, 0x023E0000  # see gunk/patches.py code_home


def check_code_home(g):
    """The code home must still hold exactly the compiled code, then zeros up to 0x023E0000: anything else means
    something in the game wrote over it (a heap or the OS arena reaching into it)."""
    blob = open(os.path.join(ROOT, 'build', 'code', 'gunk.bin'), 'rb').read()
    ram = g.dump(CODE_HOME, CODE_HOME_END - CODE_HOME, os.path.join(OUT, '_home.bin'))
    check(ram[:len(blob)] == blob, 'code home: the code at 0x023C0000 was overwritten')
    dirty = [CODE_HOME + i for i in range(len(blob), len(ram), 4) if ram[i:i + 4] != bytes(4)]
    check(not dirty, f'code home: {len(dirty)} non-zero words after the code, first at {dirty[:1] and hex(dirty[0])}')


# --- tests --------------------------------------------------------------------------------------

def make_start(g):
    """The real ROM from power-on: intro movie, title, NEW GAME, Professor Juniper (boy, name AAAAAA typed with A),
    into the bedroom where Cheren and Bianca arrive. The X menu's Save works from there."""
    g.start(fresh_save=True)
    g.counter = FRAME_COUNTER
    g.run('wait 1500', 'press Start 4', 'wait 300', 'press Start 4', 'wait 300')  # NEW GAME is the only entry
    for _ in range(14):  # Juniper's speech, boy, name (A types "A"), then Start jumps to OK
        g.run(*['press A 4', 'wait 150'] * 3)
    g.run('press Start 4', 'wait 60', 'press A 4', 'wait 200')
    for _ in range(18):  # Cheren and Bianca arrive; the last presses only open and close nothing
        g.run(*['press A 4', 'wait 150'] * 3)
    g.run('wait 600')
    g.shot('make_start')
    g.alive()
    g.run('save ' + start_state(g).replace(os.sep, '/'))
    # check the state can save (the menu opens, Save completes)
    data = save_and_check(g, 'make_start')
    check(counter(data, 0) >= 1, 'make_start: saving from the start state did not work')
    log('start state saved')


@test
def save_cycles(g):
    """Three saves at different positions, each followed by a power cycle, Continue and an immediate re-save."""
    from_start(g)
    for n in (1, 2, 3):
        take_steps(g, n)
        data = save_and_check(g, f'save {n}')
        boot_continue(g)
        resave_matches(g, (data, 0), f'save {n}')
        g.shot(f'save_cycles_{n}')
        log(f'save {n}: power cycle, Continue, re-save: same position, party, bag and boxes')


@test
def crash_after_save(g):
    """A save, then the emulator killed without flushing (a crash or power cut after the save message): the
    save must already be on the cart. BizHawk writes SaveRAM every 600 frames, so wait one interval first."""
    from_start(g)
    take_steps(g, 1)
    g.run(*SAVE_PRESSES, f'wait {SAVE_DONE}', 'wait 700')
    g.alive()
    boot_continue(g)  # stop() is a taskkill /F, no flush
    # the cart that loaded: read it back from the file BizHawk wrote before the kill
    data = open(g.saveram, 'rb').read()
    check(newest(data), 'no valid save on the cart after the crash')
    resave_matches(g, (data, newest(data)[0]), 'after crash')
    log('the save was on the cart before the crash, and Continue loaded it')


# frames after the confirming A at which the cart is captured mid-save
TORN_FRAMES = [60, 200, 280, 300, 330, 350, 370, 390, 410, 520]  # half 0 is written ~280-330f, half 1 after it


@test
def torn_save(g):
    """A crash during the save itself. Save 1 at A, save 2 at B, then start save 3 at C and capture the cart
    part-way through; boot from the capture. The game must continue from a complete save: B, or C if save 3
    finished (the half it reaches must not be torn)."""
    from_start(g)
    take_steps(g, 1)
    save_and_check(g, 'save 1')
    take_steps(g, 2)
    save2 = save_and_check(g, 'save 2')
    take_steps(g, 3)
    mid = os.path.join(OUT, '_before_save3.state')
    g.run('save ' + mid.replace(os.sep, '/'))
    results = []
    for frames in TORN_FRAMES:
        g.run('load ' + mid.replace(os.sep, '/'), 'wait 2', *SAVE_PRESSES, f'wait {frames}')
        torn = g.flush()
        path = os.path.join(OUT, f'_torn_{frames}.sav')
        open(path, 'wb').write(torn)
        state = describe(torn)
        n = newest(torn)
        check(n, f'+{frames}f: neither flash half is valid ({state})')
        boot_continue(g, saveram=path)
        resave_matches(g, (torn, n[0]), f'+{frames}f')
        which = 'save 3' if counter(torn, n[0]) > counter(save2, 0) else 'save 2'
        results.append(f'+{frames}f: continued from {which} ({state})')
        log(results[-1])
        # the next capture starts from the pre-save state again (the savestate carries the cart's contents)
    check(any('save 2' in r for r in results), 'no capture landed before save 3 reached the cart: widen TORN_FRAMES')
    check(any('bad' in r for r in results), 'no capture caught a half mid-write: adjust TORN_FRAMES')


@test
def backup_recovery(g):
    """One flash half damaged (bit rot, or a write cut off): the game must load the other half, and saving again
    must repair both. Done for each half."""
    from_start(g)
    take_steps(g, 1)
    good = save_and_check(g, 'save')
    for half in (0, 1):
        data = bytearray(good)
        at = half * HALF + 0x18E00 + 0x100  # inside the party block
        data[at:at + 64] = bytes(b ^ 0xFF for b in data[at:at + 64])
        path = os.path.join(OUT, f'_damaged_{half}.sav')
        open(path, 'wb').write(bytes(data))
        check(not half_ok(data, half) and half_ok(data, 1 - half), 'damage did not land as intended')
        boot_continue(g, saveram=path)
        g.shot(f'backup_recovery_{half}')
        resave_matches(g, (good, 1 - half), f'half {half} damaged')
        log(f'half {half} damaged: loaded the other half; saving again repaired both')


def main():
    args = sys.argv[1:]
    rom = 'gunk'
    if args[:1] == ['--rom']:
        rom, args = args[1], args[2:]
    os.makedirs(OUT, exist_ok=True)
    if args == ['make_start']:
        g = new_game(Game(rom))
        try:
            make_start(g)
        finally:
            g.stop()
        return 0
    chosen = [t for t in TESTS if not args or t.__name__ in args]
    report = [f'# Black suite ({rom})', '', f'{time.strftime("%Y-%m-%d %H:%M")}', '']
    failed = 0
    for t in chosen:
        print(f'== {t.__name__}', flush=True)
        g = new_game(Game(rom))
        t0 = time.time()
        try:
            t(g)
            if rom == 'gunk':
                check_code_home(g)
            report.append(f'- PASS {t.__name__} ({time.time() - t0:.0f} s)')
            print('   PASS', flush=True)
        except Exception as e:  # noqa: BLE001
            failed += 1
            try:
                g.shot(f'{t.__name__}_fail')
            except Exception:  # noqa: BLE001
                pass
            msg = str(e) if isinstance(e, TestFailure) else traceback.format_exc()
            report.append(f'- FAIL {t.__name__}: {msg}')
            print('   FAIL ' + msg, flush=True)
        finally:
            g.stop()
    open(os.path.join(OUT, f'report_{rom}.md'), 'w', encoding='utf-8').write('\n'.join(report) + '\n')
    print(f'{len(chosen) - failed}/{len(chosen)} passed', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
