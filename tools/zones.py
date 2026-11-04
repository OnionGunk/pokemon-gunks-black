"""Black's zones, for tests: headers (a/0/1/2) and event files (a/1/2/5): NPCs and warps.

    .venv/Scripts/python tools/zones.py <rom> <zone>...    # header, NPCs and warps of each zone

A zone header is 48 bytes (24 u16): [2] matrix, [3] script file, [5] text file, [11] event file, [12] parent zone
(the city or route a building belongs to), [13] low byte: location name (a/0/0/2 file 89). An event file is u32 size,
u8 counts of furniture (20 bytes each), NPCs (36), warps (20) and triggers, then those entries. An NPC is 18 u16: id,
sprite, movement, type, flag, script, facing, ..., [14] x, [15] z. A warp: u16 target zone, u16 target warp, ...,
[6] x (u16 at +12)... see warps() for the fields used.
"""
import struct
import sys

from narc import Narc
from ndsrom import Rom
import text5


class Zones:
    def __init__(self, rom):
        self.headers = Narc(rom.file(rom.file_id('a/0/1/2'))).file(0)
        self.events = Narc(rom.file(rom.file_id('a/1/2/5')))
        self.names = text5.read(Narc(rom.file(rom.file_id('a/0/0/2'))).file(89))

    def header(self, zone):
        return struct.unpack_from('<24H', self.headers, zone * 48)

    def name(self, zone):
        return text5.to_str(self.names[self.header(zone)[13] & 0xFF])

    def parent(self, zone):
        return self.header(zone)[12]

    def _counts(self, zone):
        d = self.events.file(self.header(zone)[11])
        return d, d[4], d[5], d[6], d[7]

    def npcs(self, zone):
        """[(id, sprite, script, x, z)]"""
        d, furn, npcs, _, _ = self._counts(zone)
        out = []
        for k in range(npcs):
            v = struct.unpack_from('<18H', d, 8 + furn * 20 + k * 36)
            out.append((v[0], v[1], v[5], v[14], v[15]))
        return out

    def warps(self, zone):
        """[(target zone, target warp, raw u16s)]"""
        d, furn, npcs, warps, _ = self._counts(zone)
        base = 8 + furn * 20 + npcs * 36
        return [struct.unpack_from('<10H', d, base + k * 20) for k in range(warps)]


if __name__ == '__main__':
    zones = Zones(Rom(open(sys.argv[1], 'rb').read()))
    for z in map(int, sys.argv[2:]):
        h = zones.header(z)
        print(f'zone {z}: {zones.name(z)!r} parent {h[12]} scripts {h[3]} texts {h[5]} events {h[11]}')
        for n in zones.npcs(z):
            print('   npc id %d sprite %d script %d at (%d, %d)' % n)
        for w in zones.warps(z):
            print('   warp', ' '.join(str(v) for v in w))
