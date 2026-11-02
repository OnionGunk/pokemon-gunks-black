"""Gen 5 Pokémon data (PK5, 220 bytes in the party): decrypt, edit, re-encrypt, so tests can read and set EVs.

Layout (PKHeX PK5): PID u32 at 0, checksum u16 at 6, then four 32-byte blocks (A, B, C, D) shuffled by the PID
and encrypted with the Gen 3+ LCG seeded by the checksum; the party-only stats (0x88-0xDB) are encrypted with the
LCG seeded by the PID. Block A holds species (+0x08), EXP (+0x10), EVs (+0x18..+0x1D).
"""
import struct

ORDERS = ['ABCD', 'ABDC', 'ACBD', 'ACDB', 'ADBC', 'ADCB', 'BACD', 'BADC', 'BCAD', 'BCDA', 'BDAC', 'BDCA',
          'CABD', 'CADB', 'CBAD', 'CBDA', 'CDAB', 'CDBA', 'DABC', 'DACB', 'DBAC', 'DBCA', 'DCAB', 'DCBA']


def _crypt(data, seed):
    out = bytearray(data)
    for i in range(0, len(out), 2):
        seed = (seed * 0x41C64E6D + 0x6073) & 0xFFFFFFFF
        v = struct.unpack_from('<H', out, i)[0] ^ (seed >> 16)
        struct.pack_into('<H', out, i, v)
    return out


def decrypt(pk):
    pid, chk = struct.unpack_from('<I', pk, 0)[0], struct.unpack_from('<H', pk, 6)[0]
    body = _crypt(pk[8:136], chk)
    order = ORDERS[((pid >> 13) & 31) % 24]
    blocks = {order[i]: body[i * 32:(i + 1) * 32] for i in range(4)}
    out = bytearray(pk[:8]) + b''.join(blocks[c] for c in 'ABCD')
    if len(pk) > 136:
        out += _crypt(pk[136:], pid)
    return out


def encrypt(plain):
    pid = struct.unpack_from('<I', plain, 0)[0]
    body = plain[8:136]
    chk = sum(struct.unpack_from('<64H', body)) & 0xFFFF
    order = ORDERS[((pid >> 13) & 31) % 24]
    blocks = {c: body[i * 32:(i + 1) * 32] for i, c in enumerate('ABCD')}
    shuffled = b''.join(blocks[c] for c in order)
    out = bytearray(plain[:8])
    struct.pack_into('<H', out, 6, chk)
    out += _crypt(shuffled, chk)
    if len(plain) > 136:
        out += _crypt(plain[136:], pid)
    return bytes(out)


def species(plain):
    return struct.unpack_from('<H', plain, 0x08)[0]


def evs(plain):
    return list(plain[0x18:0x1E])


def set_evs(plain, values):
    plain = bytearray(plain)
    plain[0x18:0x1E] = bytes(values)
    return plain
