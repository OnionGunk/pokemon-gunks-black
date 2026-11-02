r"""Shared helpers for the Black emulator test suite: drive BizHawk through bridge.lua, read game RAM, check the
save file's checksums, and detect crashes and hangs.

Adapted from the HeartGold suite (C:\Projects\hg-tools\emu\suite\lib.py). Black has no linker map, so RAM
addresses are found at run time (find_frame_counter) or come from the pokeblack disassembly.

Black's save (PKHeX SaveBlockAccessor5BW): 512 KB flash, main save 0x00000-0x23FFF mirrored at 0x24000. Every
block is CRC-16-CCITT checked; the CRC sits at the block's chk offset and again in the table block at 0x23F00.
"""
import os
import struct
import subprocess
import sys
import time

SUITE = os.path.dirname(os.path.abspath(__file__))
EMU_DIR = os.path.dirname(SUITE)
ROOT = os.path.dirname(EMU_DIR)  # C:\Projects\pokemon-black-gunk
OUT = os.path.join(SUITE, 'out')
BIZHAWK = r'C:\Projects\bizhawk-black'  # Black's own copy (see emu.py)
SAVERAM_DIR = os.path.join(BIZHAWK, 'NDS', 'SaveRAM')
BUS = 'ARM9_System_Bus'
ROMS = {
    'gunk': os.path.join(ROOT, 'build', 'gunk-black.nds'),
    'vanilla': os.path.join(ROOT, 'build', 'vanilla-black.nds'),
}
# BizHawk names the save after its game database entry when it recognises the ROM (vanilla = retail)
SAVERAM_NAMES = {}

HALF = 0x24000
# (offset, length, checksum offset, checksum-table offset) per block, from PKHeX
BLOCKS = [
    (0x00000, 0x03E0, 0x003E2, 0x23F00),  # 00 Box Names
    (0x00400, 0x0FF0, 0x013F2, 0x23F02),  # 01 Box 1
    (0x01400, 0x0FF0, 0x023F2, 0x23F04),  # 02 Box 2
    (0x02400, 0x0FF0, 0x033F2, 0x23F06),  # 03 Box 3
    (0x03400, 0x0FF0, 0x043F2, 0x23F08),  # 04 Box 4
    (0x04400, 0x0FF0, 0x053F2, 0x23F0A),  # 05 Box 5
    (0x05400, 0x0FF0, 0x063F2, 0x23F0C),  # 06 Box 6
    (0x06400, 0x0FF0, 0x073F2, 0x23F0E),  # 07 Box 7
    (0x07400, 0x0FF0, 0x083F2, 0x23F10),  # 08 Box 8
    (0x08400, 0x0FF0, 0x093F2, 0x23F12),  # 09 Box 9
    (0x09400, 0x0FF0, 0x0A3F2, 0x23F14),  # 10 Box 10
    (0x0A400, 0x0FF0, 0x0B3F2, 0x23F16),  # 11 Box 11
    (0x0B400, 0x0FF0, 0x0C3F2, 0x23F18),  # 12 Box 12
    (0x0C400, 0x0FF0, 0x0D3F2, 0x23F1A),  # 13 Box 13
    (0x0D400, 0x0FF0, 0x0E3F2, 0x23F1C),  # 14 Box 14
    (0x0E400, 0x0FF0, 0x0F3F2, 0x23F1E),  # 15 Box 15
    (0x0F400, 0x0FF0, 0x103F2, 0x23F20),  # 16 Box 16
    (0x10400, 0x0FF0, 0x113F2, 0x23F22),  # 17 Box 17
    (0x11400, 0x0FF0, 0x123F2, 0x23F24),  # 18 Box 18
    (0x12400, 0x0FF0, 0x133F2, 0x23F26),  # 19 Box 19
    (0x13400, 0x0FF0, 0x143F2, 0x23F28),  # 20 Box 20
    (0x14400, 0x0FF0, 0x153F2, 0x23F2A),  # 21 Box 21
    (0x15400, 0x0FF0, 0x163F2, 0x23F2C),  # 22 Box 22
    (0x16400, 0x0FF0, 0x173F2, 0x23F2E),  # 23 Box 23
    (0x17400, 0x0FF0, 0x183F2, 0x23F30),  # 24 Box 24
    (0x18400, 0x09C0, 0x18DC2, 0x23F32),  # 25 Inventory
    (0x18E00, 0x0534, 0x19336, 0x23F34),  # 26 Party Pokémon
    (0x19400, 0x0068, 0x1946A, 0x23F36),  # 27 Trainer Data
    (0x19500, 0x009C, 0x1959E, 0x23F38),  # 28 Trainer Position
    (0x19600, 0x1338, 0x1A93A, 0x23F3A),  # 29 Unity Tower and survey stuff
    (0x1AA00, 0x07C4, 0x1B1C6, 0x23F3C),  # 30 Pal Pad Player Data
    (0x1B200, 0x0D54, 0x1BF56, 0x23F3E),  # 31 Pal Pad Friend Data
    (0x1C000, 0x002C, 0x1C02E, 0x23F40),  # 32 Skin Info
    (0x1C100, 0x0658, 0x1C75A, 0x23F42),  # 33 ??? Gym badge data
    (0x1C800, 0x0A94, 0x1D296, 0x23F44),  # 34 Mystery Gift
    (0x1D300, 0x01AC, 0x1D4AE, 0x23F46),  # 35 Dream World Stuff (Catalog)
    (0x1D500, 0x03EC, 0x1D8EE, 0x23F48),  # 36 Chatter
    (0x1D900, 0x005C, 0x1D95E, 0x23F4A),  # 37 Adventure Info
    (0x1DA00, 0x01E0, 0x1DBE2, 0x23F4C),  # 38 Trainer Card Records
    (0x1DC00, 0x00A8, 0x1DCAA, 0x23F4E),  # 39 ???
    (0x1DD00, 0x0460, 0x1E162, 0x23F50),  # 40 Mail
    (0x1E200, 0x1400, 0x1F602, 0x23F52),  # 41 Overworld State
    (0x1F700, 0x02A4, 0x1F9A6, 0x23F54),  # 42 Musical
    (0x1FA00, 0x02DC, 0x1FCDE, 0x23F56),  # 43 White Forest + Black City Data
    (0x1FD00, 0x034C, 0x2004E, 0x23F58),  # 44 IR
    (0x20100, 0x03EC, 0x204EE, 0x23F5A),  # 45 EventWork
    (0x20500, 0x00F8, 0x205FA, 0x23F5C),  # 46 GTS
    (0x20600, 0x02FC, 0x208FE, 0x23F5E),  # 47 Regulation Tournament
    (0x20900, 0x0094, 0x20996, 0x23F60),  # 48 Gimmick
    (0x20A00, 0x035C, 0x20D5E, 0x23F62),  # 49 Battle Box
    (0x20E00, 0x01CC, 0x20FCE, 0x23F64),  # 50 Daycare
    (0x21000, 0x0168, 0x2116A, 0x23F66),  # 51 Strength Boulder Status
    (0x21200, 0x00EC, 0x212EE, 0x23F68),  # 52 Badge Flags, Money, Trainer Sayings
    (0x21300, 0x01B0, 0x214B2, 0x23F6A),  # 53 Entralink (Level & Powers etc)
    (0x21500, 0x001C, 0x2151E, 0x23F6C),  # 54 ???
    (0x21600, 0x04D4, 0x21AD6, 0x23F6E),  # 55 Pokedex
    (0x21B00, 0x0034, 0x21B36, 0x23F70),  # 56 Encount Swarm and other overworld info - 2C - swarm, 2D - repel steps, 2E repel type
    (0x21C00, 0x003C, 0x21C3E, 0x23F72),  # 57 Battle Subway Play Info
    (0x21D00, 0x01AC, 0x21EAE, 0x23F74),  # 58 Battle Subway Score Info
    (0x21F00, 0x0B90, 0x22A92, 0x23F76),  # 59 Battle Subway Wi-Fi Info
    (0x22B00, 0x009C, 0x22B9E, 0x23F78),  # 60 Online Records
    (0x22C00, 0x0850, 0x23452, 0x23F7A),  # 61 Entralink Forest pokémon data
    (0x23500, 0x0028, 0x2352A, 0x23F7C),  # 62 ???
    (0x23600, 0x0284, 0x23886, 0x23F7E),  # 63 Answered Questions
    (0x23900, 0x0010, 0x23912, 0x23F80),  # 64 Unity Tower
    (0x23A00, 0x005C, 0x23A5E, 0x23F82),  # 65 Battle Institute
    (0x23B00, 0x016C, 0x23C6E, 0x23F84),  # 66 ???
    (0x23D00, 0x0040, 0x23D42, 0x23F86),  # 67 ???
    (0x23E00, 0x00FC, 0x23EFE, 0x23F88),  # 68 ???
    (0x23F00, 0x008C, 0x23F9A, 0x23F9A),  # 69 Checksums
]
TABLE = 69  # the block holding every other block's CRC


class TestFailure(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise TestFailure(msg)


try:
    import binascii

    def crc16_ccitt(data, crc=0xFFFF):
        return binascii.crc_hqx(bytes(data), crc)
except ImportError:  # pragma: no cover
    def crc16_ccitt(data, crc=0xFFFF):
        for b in data:
            crc ^= b << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
        return crc


def half_status(data, half):
    """Per block of one flash half: (ok, stored crc, computed crc). ok means the block's own CRC and the table's
    copy both match its data."""
    base = half * HALF
    res = []
    for i, (off, length, chk, tab) in enumerate(BLOCKS):
        calc = crc16_ccitt(data[base + off:base + off + length])
        own = struct.unpack_from('<H', data, base + chk)[0]
        table = struct.unpack_from('<H', data, base + tab)[0]
        res.append((calc == own and (i == TABLE or calc == table), own, calc))
    return res


def half_ok(data, half):
    return all(ok for ok, _, _ in half_status(data, half))


def block(data, half, i):
    off, length, _, _ = BLOCKS[i]
    return bytes(data[half * HALF + off:half * HALF + off + length])


def footer(data, half, i):
    """The 0x10 bytes after a block's data (save counter, CRC …)."""
    off, length, _, _ = BLOCKS[i]
    base = half * HALF + off + length
    return bytes(data[base:base + 0x10])


# --- emulator --------------------------------------------------------------------------------

class Game:
    def __init__(self, rom='gunk'):
        self.rom = rom
        name = SAVERAM_NAMES.get(rom, os.path.basename(ROMS[rom])[:-4])
        self.saveram = os.path.join(SAVERAM_DIR, name + '.SaveRAM')
        self.counter = None
        os.makedirs(OUT, exist_ok=True)

    def stop(self):
        subprocess.run([sys.executable, '-I', os.path.join(EMU_DIR, 'emu.py'), 'stop'], capture_output=True)  # this harness's BizHawk only
        for f in ('cmd.txt', 'done.txt', 'buttons.txt'):
            p = os.path.join(EMU_DIR, f)
            if os.path.exists(p):
                os.remove(p)

    def start(self, fresh_save=False, saveram=None):
        """Power on. fresh_save wipes the cart; saveram (a path) puts that save file on the cart first."""
        self.stop()
        base = self.saveram[:-len('.SaveRAM')]
        auto = base + '.AutoSaveRAM.SaveRAM'
        if fresh_save or saveram:
            if os.path.exists(self.saveram) and not os.path.exists(self.saveram + '.before-tests'):
                os.replace(self.saveram, self.saveram + '.before-tests')
            for path in (self.saveram, auto, auto + '.bak'):
                if os.path.exists(path):
                    os.remove(path)
            if saveram:
                os.makedirs(SAVERAM_DIR, exist_ok=True)
                open(self.saveram, 'wb').write(open(saveram, 'rb').read())
        elif os.path.exists(auto):
            # a newer autosave makes BizHawk stop at a "Load autosaved SaveRAM?" box: do what Yes does
            if not os.path.exists(self.saveram) or os.path.getmtime(auto) > os.path.getmtime(self.saveram):
                os.replace(auto, self.saveram)
            else:
                os.remove(auto)
            if os.path.exists(auto + '.bak'):
                os.remove(auto + '.bak')
        r = subprocess.run([sys.executable, '-I', os.path.join(EMU_DIR, 'emu.py'), 'start', ROMS[self.rom]],
                           capture_output=True, text=True, timeout=120)
        check('ready' in r.stdout, 'emulator did not start: ' + (r.stdout + r.stderr).strip()[-300:])
        self.run('speed 3200')

    def run(self, *cmds, timeout=900):
        r = subprocess.run([sys.executable, '-I', os.path.join(EMU_DIR, 'emu.py'), 'run', *cmds],
                           capture_output=True, text=True, timeout=timeout)
        if 'ERROR' in r.stdout:
            raise TestFailure('bridge error: ' + r.stdout.strip())
        if r.returncode:
            raise TestFailure('emulator: ' + (r.stderr.strip() or f'exit {r.returncode}')[-300:])
        return r.stdout

    def read(self, addr, length):
        out = self.run(f'readdom {BUS} {addr} {length}')
        return bytes(int(h, 16) for h in out.splitlines()[0].split())

    def u32(self, addr):
        return struct.unpack('<I', self.read(addr, 4))[0]

    def dump(self, addr, length, path):
        self.run(f'dump {BUS} {addr} {length} {path.replace(os.sep, "/")}')
        return open(path, 'rb').read()

    def shot(self, name):
        path = os.path.join(OUT, name + '.png')
        self.run('shot ' + path.replace(os.sep, '/'))
        return path

    def find_frame_counters(self):
        """u32s in main RAM that rise by the same 6-9 per 7-frame wait across three samples: frame counts. The
        first one is used as the "still running" signal (a crash or hang stops it)."""
        dumps = []
        for n in range(3):
            dumps.append(self.dump(0x02000000, 0x400000, os.path.join(OUT, f'_ram{n}.bin')))
            self.run('wait 7')
        cands = []
        for i in range(0, 0x400000, 4):
            a, b, c = (struct.unpack_from('<I', d, i)[0] for d in dumps)
            if b - a == c - b and 6 <= b - a <= 9 and a > 60:
                cands.append(0x02000000 + i)
        check(cands, 'no frame counter found')
        return cands

    def alive(self, frames=120):
        """Run `frames` frames; fail if the game's frame counter stopped (crash or hard hang)."""
        out = self.run(f'alive {self.counter} {frames}')
        line = [l for l in out.splitlines() if l.startswith('alive')][0]
        moved, pc = int(line.split()[1]), line.split()[2]
        if moved == 0:
            # a save writes flash for a few seconds; give it 30 s before calling it a hang
            line = [l for l in self.run(f'alive {self.counter} 1800').splitlines() if l.startswith('alive')][0]
            moved, pc = int(line.split()[1]), line.split()[2]
        check(moved > 0, f'game froze (frame counter stopped, {pc})')
        return moved

    def flush(self):
        """Write the emulated cart to the .SaveRAM file now and return its bytes."""
        self.run('flushsave', 'wait 2')
        return open(self.saveram, 'rb').read()
