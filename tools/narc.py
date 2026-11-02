"""Minimal NARC access that keeps the archive byte-for-byte (ndspy's NARC.save() re-lays it out)."""
import struct


class Narc:
    def __init__(self, data):
        self.data = bytearray(data)
        assert self.data[:4] == b'NARC'
        off = struct.unpack_from('<H', self.data, 0xC)[0]
        assert self.data[off:off + 4] == b'BTAF'
        self.count = struct.unpack_from('<H', self.data, off + 8)[0]
        self.fat = off + 12
        btaf_size = struct.unpack_from('<I', self.data, off + 4)[0]
        btnf = off + btaf_size
        assert self.data[btnf:btnf + 4] == b'BTNF'
        gmif = btnf + struct.unpack_from('<I', self.data, btnf + 4)[0]
        assert self.data[gmif:gmif + 4] == b'GMIF'
        self.img = gmif + 8

    def range(self, i):
        s, e = struct.unpack_from('<II', self.data, self.fat + i * 8)
        return self.img + s, self.img + e

    def file(self, i):
        s, e = self.range(i)
        return bytes(self.data[s:e])

    def set_file(self, i, new):
        """Same-size replacement only (enough for the fixed-size data tables)."""
        s, e = self.range(i)
        assert len(new) == e - s, f'file {i}: size {len(new)} != {e - s}'
        self.data[s:e] = new

    def resize_file(self, i, new):
        """Replace file i with data of any size: the files after it shift (keeping 4-byte alignment, padded with
        0xFF) and the FAT, GMIF and archive sizes follow."""
        s, e = self.range(i)
        new = bytes(new)
        old_span = (e - s + 3) & ~3
        span = new + b'\xFF' * (-len(new) % 4)
        delta = len(span) - old_span
        self.data[s:s + old_span] = span
        for j in range(self.count):
            fs, fe = struct.unpack_from('<II', self.data, self.fat + j * 8)
            if j == i:
                struct.pack_into('<II', self.data, self.fat + j * 8, fs, fs + len(new))
            elif fs >= e - self.img:
                struct.pack_into('<II', self.data, self.fat + j * 8, fs + delta, fe + delta)
        gmif = self.img - 8
        struct.pack_into('<I', self.data, gmif + 4, struct.unpack_from('<I', self.data, gmif + 4)[0] + delta)
        struct.pack_into('<I', self.data, 8, len(self.data))

    def save(self):
        return bytes(self.data)
