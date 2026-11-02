"""In-place editing of a DSi-enhanced NDS ROM (Pokémon Black).

The ROM is never re-laid out: every byte not touched by a patch stays where retail put it, including the TWL
(DSi) region. A file that still fits in its slot is rewritten in place (the rest of the slot padded with 0xFF); a
file that grows moves into the space of the DSi digest tables and its FAT entry is pointed there. Header and banner
CRCs are recomputed on save.

The DSi digests (header 0x1E0..0x1FF, HMACs at 0x300) go stale with any change anyway, so a patched ROM boots in DS
mode only (every emulator's default; flash carts run DS mode too), and nothing in DS mode reads the digest tables.
That makes them the free space: the sector and block hash tables, 0xBFD9C00-0xC3B8C78 (~3.8 MB), inside the area a
DS-mode game can read. The space after the TWL region looks free but isn't usable: in DS mode a DSi-enhanced cart
doesn't serve reads from the TWL area onward (0xC403000+), and melonDS emulates that. Files moved there read back
as garbage, and the game hangs on a white screen when it loads the field overlay.
"""
import struct

from ndspy import codeCompression

FREE_START = 0xBFD9C00  # header 0x1F0: the DSi sector hashtable, then the block hashtable (0x1F8)
FREE_END = 0xC3B8C78  # end of the block hashtable; the DS-mode ROM area ends at 0xC3B8E00 (header 0x80)
ALIGN = 0x200


def crc16(data, crc=0xFFFF):
    """CRC-16/MODBUS, as used by the header and banner checksums."""
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class Rom:
    def __init__(self, data):
        self.data = bytearray(data)
        self.fat_off, fat_size = struct.unpack_from('<II', self.data, 0x48)
        self.nfiles = fat_size // 8
        self.ovt_off, ovt_size = struct.unpack_from('<II', self.data, 0x50)
        self.novl = ovt_size // 32
        self.banner_off = struct.unpack_from('<I', self.data, 0x68)[0]
        self.free = FREE_START
        self._names = None

    # files ---------------------------------------------------------------------------------
    def file_range(self, fid):
        return struct.unpack_from('<II', self.data, self.fat_off + fid * 8)

    def file(self, fid):
        start, end = self.file_range(fid)
        return bytes(self.data[start:end])

    def file_id(self, path):
        if self._names is None:
            from ndspy import fnt
            fnt_off, fnt_size = struct.unpack_from('<II', self.data, 0x40)
            self._names = fnt.load(bytes(self.data[fnt_off:fnt_off + fnt_size]))
        fid = self._names.idOf(path)
        if fid is None:
            raise KeyError(path)
        return fid

    def _slot_end(self, fid):
        """End of the space a file may use in place: up to the next file's start (or its own end, aligned)."""
        start, end = self.file_range(fid)
        if start >= FREE_START:
            return (end + ALIGN - 1) & ~(ALIGN - 1)
        nxt = min((s for s, _ in (self.file_range(i) for i in range(self.nfiles)) if s >= end), default=end)
        return min(nxt, (end + ALIGN - 1) & ~(ALIGN - 1))

    def replace_file(self, fid, new):
        start, end = self.file_range(fid)
        if start + len(new) <= self._slot_end(fid):
            self.data[start:self._slot_end(fid)] = b'\xFF' * (self._slot_end(fid) - start)
        else:
            self.data[start:end] = b'\xFF' * (end - start)
            start = self.free
            self.free = (start + len(new) + ALIGN - 1) & ~(ALIGN - 1)
            if self.free > FREE_END:
                raise ValueError('ROM full')
        self.data[start:start + len(new)] = new
        struct.pack_into('<II', self.data, self.fat_off + fid * 8, start, start + len(new))

    # overlays ------------------------------------------------------------------------------
    def overlay_entry(self, n):
        return list(struct.unpack_from('<8I', self.data, self.ovt_off + n * 32))

    def overlay(self, n):
        """Overlay n's code, decompressed."""
        e = self.overlay_entry(n)
        raw = self.file(e[6])
        return bytes(codeCompression.decompress(raw)) if e[7] >> 24 & 1 else raw

    def overlay_base(self, n):
        return self.overlay_entry(n)[1]

    def replace_overlay(self, n, code):
        """Store overlay n uncompressed (it loads the same; the file only gets bigger)."""
        e = self.overlay_entry(n)
        self.replace_file(e[6], code)
        e[7] = len(code) & 0xFFFFFF  # compressed flag clear
        struct.pack_into('<8I', self.data, self.ovt_off + n * 32, *e)

    # header and banner ---------------------------------------------------------------------
    def set_title(self, title):
        b = title.encode('ascii')
        assert len(b) <= 12
        self.data[0:12] = b.ljust(12, b'\0')

    def set_banner_title(self, text):
        """Same title in every language slot that retail fills (JP, EN, FR, DE, IT, ES, KO; Chinese stays empty)."""
        b = self.banner_off
        enc = text.encode('utf-16le')
        assert len(enc) <= 0x100
        for lang in range(8):
            slot = b + 0x240 + lang * 0x100
            if any(self.data[slot:slot + 2]):
                self.data[slot:slot + 0x100] = enc.ljust(0x100, b'\0')

    def save(self):
        b = self.banner_off
        version = struct.unpack_from('<H', self.data, b)[0]
        # banner CRCs: v1 0x20-0x83F, v2 0x20-0x93F, v3 0x20-0xA3F, v0x103 animated icon 0x1240-0x23BF
        spans = [(2, 0x20, 0x840), (4, 0x20, 0x940), (6, 0x20, 0xA40), (8, 0x1240, 0x23C0)]
        have = {1: 1, 2: 2, 3: 3, 0x103: 4}[version]
        for pos, lo, hi in spans[:have]:
            struct.pack_into('<H', self.data, b + pos, crc16(self.data[b + lo:b + hi]))
        struct.pack_into('<H', self.data, 0x15E, crc16(self.data[:0x15E]))
        return bytes(self.data)


def read_u16(buf, off):
    return struct.unpack_from('<H', buf, off)[0]


def patch(buf, off, old, new):
    """Replace bytes at off, checking they are what retail has there first."""
    old, new = bytes.fromhex(old), bytes.fromhex(new)
    assert len(old) == len(new)
    have = bytes(buf[off:off + len(old)])
    if have != old:
        raise ValueError(f'unexpected bytes at {off:#x}: {have.hex()} (expected {old.hex()})')
    buf[off:off + len(new)] = new
