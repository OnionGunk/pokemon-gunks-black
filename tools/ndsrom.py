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
        self.holes = [[FREE_START, FREE_END]]  # free ROM space: the digest tables, then slots files moved out of
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

    def _alloc(self, size):
        """Best fit among the holes (smallest that is big enough)."""
        fits = [h for h in self.holes if h[1] - h[0] >= size]
        if not fits:
            raise ValueError(f'ROM full: need {size:#x}, holes {[(hex(a), hex(b - a)) for a, b in self.holes]}')
        hole = min(fits, key=lambda h: h[1] - h[0])
        start = hole[0]
        hole[0] = min((start + size + ALIGN - 1) & ~(ALIGN - 1), hole[1])
        return start

    def _release(self, start, end):
        """A slot a file moved out of becomes free space (it is inside the DS-mode readable area); neighbouring
        holes merge."""
        self.data[start:end] = b'\xFF' * (end - start)
        self.holes.append([start, end])
        self.holes.sort()
        merged = [self.holes[0]]
        for h in self.holes[1:]:
            if h[0] <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], h[1])
            else:
                merged.append(h)
        self.holes = [h for h in merged if h[1] > h[0]]

    def replace_file(self, fid, new):
        start, end = self.file_range(fid)
        slot = self._slot_end(fid)
        if start + len(new) <= slot:
            self.data[start:slot] = b'\xFF' * (slot - start)
        else:  # free the slot first, so it can merge with free space next to it and be reused
            self._release(start, slot)
            start = self._alloc(len(new))
        self.data[start:start + len(new)] = new
        struct.pack_into('<II', self.data, self.fat_off + fid * 8, start, start + len(new))

    def _move_file(self, fid):
        start, end = self.file_range(fid)
        body = self.file(fid)
        self._release(start, self._slot_end(fid))
        new = self._alloc(len(body))
        self.data[new:new + len(body)] = body
        struct.pack_into('<II', self.data, self.fat_off + fid * 8, new, new + len(body))

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

    # ARM9 static module -------------------------------------------------------------------------
    ARM9_RAM = 0x02004000
    ARM9_MODPARAMS = 0xFB0  # SDK module params (magic 0xDEC00621 at +0x1C), raw in the first 16 KB; +0x14 = compressed static end
    def arm9(self):
        off, _, _, size = struct.unpack_from('<4I', self.data, 0x20)
        return bytes(codeCompression.decompress(bytes(self.data[off:off + size])))

    def _arm9_slot_end(self):
        """Start of the next ROM item after the ARM9 (retail: the ARM9 overlay table at 0x73A00)."""
        off = struct.unpack_from('<I', self.data, 0x20)[0]
        starts = [struct.unpack_from('<I', self.data, h)[0] for h in (0x30, 0x40, 0x48, 0x50, 0x68)]
        starts += [s for s, _ in (self.file_range(i) for i in range(self.nfiles))]
        return min(s for s in starts if s > off)

    def _make_arm9_room(self, end):
        """Move the ARM9 overlay table and the files right after the ARM9 into free space, so the ARM9 can grow in
        place up to `end`. The ARM9 itself stays at 0x4000 (its first 2 KB are the cartridge's secure area)."""
        if self.ovt_off < end:
            table = bytes(self.data[self.ovt_off:self.ovt_off + self.novl * 32])
            self.data[self.ovt_off:self.ovt_off + len(table)] = b'\xFF' * len(table)
            self.ovt_off = self._alloc(len(table))
            self.data[self.ovt_off:self.ovt_off + len(table)] = table
            struct.pack_into('<I', self.data, 0x50, self.ovt_off)
        arm9_off = struct.unpack_from('<I', self.data, 0x20)[0]
        for fid in range(self.nfiles):
            start, _ = self.file_range(fid)
            if arm9_off < start < end:
                self._move_file(fid)

    def replace_arm9(self, code):
        """BLZ-compress the ARM9 again (the secure area and module params stay raw) and fix its sizes."""
        off = struct.unpack_from('<I', self.data, 0x20)[0]
        old_end = off + struct.unpack_from('<I', self.data, 0x2C)[0]
        comp = bytearray(codeCompression.compress(code, isArm9=True))
        if off + len(comp) > self._arm9_slot_end():
            self._make_arm9_room(off + len(comp))
        struct.pack_into('<I', comp, self.ARM9_MODPARAMS + 0x14, self.ARM9_RAM + len(comp))
        self.data[off:old_end] = b'\xFF' * (old_end - off)
        self.data[off:off + len(comp)] = comp
        struct.pack_into('<I', self.data, 0x2C, len(comp))

    def add_autoload(self, code, addr, blob, bss=0):
        """Append an autoload block to the (decompressed) ARM9 `code`: at boot, crt0 copies `blob` to `addr` and
        zeroes `bss` bytes after it, before anything else runs. Autoload data sits at the end of the binary,
        followed by the list of {address, size, static-init table, bss size} entries; the new block goes after
        the retail blocks and its entry after theirs. Returns the new code."""
        mp = self.ARM9_MODPARAMS
        list_start, list_end = struct.unpack_from('<II', code, mp)
        assert list_end == self.ARM9_RAM + len(code), 'the autoload list is not at the end of the ARM9'
        blob = bytes(blob) + b'\0' * (-len(blob) % 4)
        at = list_start - self.ARM9_RAM
        entries = bytes(code[at:])
        out = bytearray(code[:at]) + blob + entries + struct.pack('<4I', addr, len(blob), 0, bss)
        struct.pack_into('<II', out, mp, list_start + len(blob), list_end + len(blob) + 16)
        return bytes(out)

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
