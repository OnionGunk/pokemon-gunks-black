"""Pokémon Black field scripts (the a/0/5/7 NARC, 899 files): read, list and extend them.

A script file starts with a table of s32 offsets, each relative to the end of its own field, closed by the u16
0xFD13; every offset is a script's entry point. A script is u16 opcodes, each followed by its arguments, with
jumps and calls as s32 offsets relative to the end of the command.

The interpreter (ARM9 FUN_02011298) runs opcodes through a 609-entry handler table in overlay 10 (0x0217062C).
Argument sizes aren't stored anywhere, so `command_sizes` works them out from the handlers' code: the bytes each
reads through the u16/u32 readers (FUN_02011330, FUN_0201134C), inline byte reads (the script pointer at +0x14
moved by 1), and whatever the functions it calls or tail-jumps to read. Checked by parsing every script: 99 % of
the 12 000 reachable paths end cleanly. The rest run into data placed after code (movement lists and the like).

Edits never move existing code: new code goes at the end of a file and an entry offset (or a jump) is pointed at
it, so offsets this module can't parse stay valid.

    python tools/script5.py <base rom> dis <file>     # list a file's entries and disassemble them
"""
import struct
import sys

import capstone

from ndsrom import Rom
from narc import Narc

SCRIPTS = 'a/0/5/7'
TABLE, COUNT = 0x0217062C, 609  # overlay 10
OVL_SCRIPT, OVL_FIELD = 10, 21
READ16, READ32 = 0x02011330, 0x0201134C
END_OF_TABLE = 0xFD13

OP_END, OP_RETURN, OP_CALL, OP_JUMP, OP_IF = 0x02, 0x05, 0x04, 0x1E, 0x1F
TARGETS = {OP_CALL: 0, OP_JUMP: 0, OP_IF: 1}  # opcode -> offset of its s32 target within the arguments
STOPS = {OP_END, OP_RETURN, OP_JUMP, 0x137}  # nothing after these runs (0x137 hands control to a callback)
SIZE_FIXES = {0x1C: 2}  # where reading the handler gets it wrong (it counts a callee's reads); fits every script


def command_sizes(rom):
    """{opcode: argument bytes}, worked out from the handlers (see the module docstring)."""
    regions = [(Rom.ARM9_RAM, rom.arm9()), (rom.overlay_base(OVL_SCRIPT), rom.overlay(OVL_SCRIPT)),
               (rom.overlay_base(OVL_FIELD), rom.overlay(OVL_FIELD))]
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

    def mem(addr, n):
        for base, buf in regions:
            if base <= addr < base + len(buf):
                return buf[addr - base:addr - base + n]
        return None

    memo = {READ16: 2, READ32: 4}

    def reads(addr, depth=0):
        if addr in memo:
            return memo[addr]
        if depth > 3:
            return 0
        memo[addr] = 0
        code = mem(addr, 0x400)
        if code is None:
            return 0
        total, lits = 0, {}
        insns = list(md.disasm(code, addr))
        for k, i in enumerate(insns):
            if i.mnemonic == 'ldr' and '[pc, #' in i.op_str:
                v = mem(((i.address + 4) & ~3) + int(i.op_str.split('#')[-1].rstrip(']'), 16), 4)
                if v:
                    lits[i.op_str.split(',')[0]] = struct.unpack('<I', v)[0]
            if i.mnemonic == 'bx' and i.op_str in lits:  # tail jump through a literal
                total += reads(lits[i.op_str] & ~1, depth + 1)
                break
            if i.mnemonic in ('bl', 'blx') and i.op_str.startswith('#'):
                total += reads(int(i.op_str[1:], 16), depth + 1)
            elif i.mnemonic == 'str' and i.op_str.endswith('#0x14]') and any(
                    j.mnemonic == 'adds' and j.op_str.endswith('#1') and j.op_str.split(',')[0] == i.op_str.split(',')[0]
                    for j in insns[max(0, k - 3):k]):
                total += 1
            if i.mnemonic == 'bx' or (i.mnemonic == 'pop' and 'pc' in i.op_str):
                break
        memo[addr] = total
        return total

    handlers = struct.unpack(f'<{COUNT}I', mem(TABLE, COUNT * 4))
    sizes = {op: reads(h & ~1) for op, h in enumerate(handlers)}
    sizes.update(SIZE_FIXES)
    return sizes


def entries(data):
    """Entry points (file offsets) of a script file, in table order."""
    out, i = [], 0
    while i + 4 <= len(data) and struct.unpack_from('<H', data, i)[0] != END_OF_TABLE:
        out.append(i + 4 + struct.unpack_from('<i', data, i)[0])
        i += 4
    return out


def disassemble(data, start, sizes):
    """[(offset, opcode, argument bytes)] from start to the first command nothing runs after."""
    out, pc = [], start
    while pc + 2 <= len(data):
        op = struct.unpack_from('<H', data, pc)[0]
        if op >= COUNT:
            out.append((pc, op, b''))
            break
        n = sizes[op]
        out.append((pc, op, bytes(data[pc + 2:pc + 2 + n])))
        pc += 2 + n
        if op in STOPS:
            break
    return out


def target(offset, op, args):
    """Where a call or jump at offset goes (file offset)."""
    return offset + 2 + len(args) + struct.unpack_from('<i', args, TARGETS[op])[0]


class ScriptFile:
    """One script file, extended only by appending."""

    def __init__(self, data):
        self.data = bytearray(data)

    def append(self, code):
        """Add code (bytes) at the end, 2-byte aligned; returns its offset."""
        if len(self.data) % 2:
            self.data += b'\0'
        at = len(self.data)
        self.data += code
        return at

    def set_entry(self, index, offset):
        """Point entry `index` at `offset`."""
        struct.pack_into('<i', self.data, index * 4, offset - (index * 4 + 4))

    def save(self):
        return bytes(self.data)


def jump_to(at, offset):
    """Bytes of a Jump command placed at `at` going to `offset`."""
    return struct.pack('<Hi', OP_JUMP, offset - (at + 6))


# commands the patches use (opcode, argument layout); 'L' is an s32 jump target given as a label or file offset
OP_LOCK, OP_RELEASE_A, OP_RELEASE_B, OP_WAIT_A, OP_CLOSE = 0x2E, 0x30, 0x2F, 0x32, 0x36
OP_MESSAGE = 0x34          # (msg u16, type u16): a line from the script's text file, type 2 = plain field text
OP_SET_VAR = 0x28          # (var u16, value u16)
OP_PUSH_VAR, OP_PUSH_VALUE, OP_COMPARE = 0x09, 0x08, 0x11
IF_DIFFERENT = 0xFF  # push var, push value, compare 1, If 0xFF: jumps when they differ (checked in the game)
OP_YES_NO = 0x47           # (var u16): 0 = YES
OP_TAKE_ITEM, OP_CHECK_ITEM = 0xB6, 0xB8  # (item u16, count u16, result var u16); check: 1 = have that many
OP_GUNK = 0x25E            # (sub u16, value u16): gunk/code/script.c


def assemble(at, program):
    """Bytes for `program` placed at file offset `at`. Items: (opcode, *args) with args as ints (u16), ('u8', n),
    ('label', name) or an int file offset tagged ('to', n) for s32 jump targets; a bare string defines a label."""
    def walk(labels):
        out = bytearray()
        for item in program:
            if isinstance(item, str):
                labels[item] = at + len(out)
                continue
            op, *args = item
            out += struct.pack('<H', op)
            for a in args:
                if isinstance(a, tuple) and a[0] == 'u8':
                    out += struct.pack('<B', a[1])
                elif isinstance(a, tuple):
                    dest = labels.get(a[1], 0) if a[0] == 'label' else a[1]
                    out += struct.pack('<i', 0)
                    fixups.append((len(out) - 4, dest, a))
                else:
                    out += struct.pack('<H', a)
        return out

    labels = {}
    fixups = []
    walk(labels)  # first pass: label positions
    fixups.clear()
    out = walk(labels)
    for pos, _, a in fixups:
        dest = labels[a[1]] if a[0] == 'label' else a[1]
        # targets are relative to the end of the command; every jump argument ends its command here
        struct.pack_into('<i', out, pos, dest - (at + pos + 4))
    return bytes(out)


def main():
    rom = Rom(open(sys.argv[1], 'rb').read())
    if sys.argv[2] == 'dis':
        f = int(sys.argv[3])
        data = Narc(rom.file(rom.file_id(SCRIPTS))).file(f)
        sizes = command_sizes(rom)
        for n, e in enumerate(entries(data)):
            print(f'--- entry {n} @ {e:#x}')
            for pc, op, args in disassemble(data, e, sizes):
                extra = f'  -> {target(pc, op, args):#x}' if op in TARGETS and len(args) >= TARGETS[op] + 4 else ''
                print(f'  {pc:#06x}: {op:#05x} {args.hex()}{extra}')


if __name__ == '__main__':
    sys.path.insert(0, __file__.rsplit('\\', 1)[0])
    main()
