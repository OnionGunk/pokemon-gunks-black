"""Gen 5 message files (the a/0/0/2 and a/0/0/3 NARCs): read and write their strings.

A file: u16 block count, u16 entry count, u32 size of block 0, u32 0, u32 block offsets. Block 0: u32 size, then
per entry {u32 offset from the block start, u16 length in chars, u16 0}, then the strings. Each string is u16
chars ending in 0xFFFF, XORed with a key that rotates by 3 bits per char; the key for the last char is
0xFFFF ^ (its stored value), so decoding runs backwards from the terminator.
"""
import struct


def _crypt(chars, key):
    out = list(chars)
    for i in range(len(out) - 1, -1, -1):
        out[i] ^= key
        key = ((key >> 3) | (key << 13)) & 0xFFFF
    return out


def read(data):
    nblocks, nentries, _, _ = struct.unpack_from('<HHII', data, 0)
    block = struct.unpack_from('<I', data, 12)[0]
    out = []
    for i in range(nentries):
        off, n, _ = struct.unpack_from('<IHH', data, block + 4 + i * 8)
        enc = struct.unpack_from(f'<{n}H', data, block + off)
        dec = _crypt(enc, enc[-1] ^ 0xFFFF)
        out.append(dec[:-1] if dec and dec[-1] == 0xFFFF else dec)
    return out


def to_str(chars):
    return ''.join(chr(c) if 0x20 <= c < 0xFFFE else '\\x%04x' % c for c in chars)


def entries(data):
    """[(chars, attribute)] for every string, the attribute being each entry's second u16 (kept as is)."""
    block = struct.unpack_from('<I', data, 12)[0]
    attrs = [struct.unpack_from('<H', data, block + 4 + i * 8 + 6)[0] for i in range(struct.unpack_from('<H', data, 2)[0])]
    return list(zip(read(data), attrs))


def write(items):
    """Build a one-block message file from [(chars, attribute)], encrypted the way the game decrypts: string i's
    first char with 0x7C89 + i * 0x2983, the key rotating left by 3 bits per char."""
    table, body = bytearray(), bytearray()
    first = 4 + 8 * len(items)
    for i, (chars, attr) in enumerate(items):
        plain = list(chars) + [0xFFFF]
        key, enc = (0x7C89 + i * 0x2983) & 0xFFFF, []
        for c in plain:
            enc.append(c ^ key)
            key = ((key << 3) | (key >> 13)) & 0xFFFF
        table += struct.pack('<IHH', first + len(body), len(plain), attr)
        body += struct.pack(f'<{len(plain)}H', *enc)
    # blocks are padded to 4 bytes; retail fills the pad with bytes that follow no pattern found here (the game never
    # reads them), so a rewritten file matches retail everywhere but those two bytes
    body += bytes(-(first + len(body)) % 4)
    block = struct.pack('<I', first + len(body)) + table + body
    return struct.pack('<HHIII', 1, len(items), len(block), 0, 0x10) + block


def chars(text):
    """Plain text to chars; a newline becomes the game's line break (0xFFFE)."""
    return [0xFFFE if c == '\n' else ord(c) for c in text]
