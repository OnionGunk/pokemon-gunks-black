"""Black's map layout, enough for tests: which map and zone cover a global tile, and each tile's height and behaviour.

    .venv/Scripts/python tools/mapdata.py <rom> surf     # walkable tiles beside water, at the water's height

The outdoor world is matrix 0 (a/0/0/9; a zone header's u16 at +4 names its matrix): u32 type 1, u16 width, u16
height in 32x32-tile chunks, then width*height u32 map numbers and the same of zone numbers (type 0, a building's
matrix, has no zone numbers). A map (a/0/0/8, "WB")
lists its sections after a u16 count: model, tile layer, collision mesh. The tile layer is u16 32, u16 32, then 8
bytes per tile: u16 at +2 the height layer, u8 at +6 the behaviour (0x80 walkable, 0x81 wall, 0x16 water, 0x24 tall
grass, among others).
"""
import struct
import sys

from narc import Narc
from ndsrom import Rom

WALK, WALL, WATER, GRASS = 0x80, 0x81, 0x16, 0x24


class World:
    def __init__(self, rom, matrix=0):
        mx = Narc(rom.file(rom.file_id('a/0/0/9'))).file(matrix)
        kind, self.w, self.h = struct.unpack_from('<IHH', mx, 0)
        n = self.w * self.h
        self.maps = struct.unpack_from(f'<{n}I', mx, 8)
        # type 1 adds a zone per chunk; type 0 (buildings) has none: their tiles say zone None
        self.zones = struct.unpack_from(f'<{n}I', mx, 8 + n * 4) if kind == 1 else (None,) * n
        self.narc = Narc(rom.file(rom.file_id('a/0/0/8')))
        self._layers = {}

    def _layer(self, m):
        if m not in self._layers:
            f = self.narc.file(m)
            count = struct.unpack_from('<H', f, 2)[0]
            offs = struct.unpack_from(f'<{count + 1}I', f, 4)
            self._layers[m] = f[offs[1] + 4:offs[2]]
        return self._layers[m]

    def tile(self, x, z):
        """(zone, height, behaviour) of global tile (x, z), or None outside the map."""
        cx, cz = x // 32, z // 32
        if not (0 <= cx < self.w and 0 <= cz < self.h) or self.maps[cz * self.w + cx] == 0xFFFFFFFF:
            return None
        layer = self._layer(self.maps[cz * self.w + cx])
        at = ((z % 32) * 32 + x % 32) * 8
        return self.zones[cz * self.w + cx], struct.unpack_from('<H', layer, at + 2)[0], layer[at + 6]


def surf_spots(world):
    """(zone, x, z, direction) for each walkable tile with water next to it at the same height."""
    for cz in range(world.h):
        for cx in range(world.w):
            if world.maps[cz * world.w + cx] == 0xFFFFFFFF:
                continue
            for z in range(cz * 32, cz * 32 + 32):
                for x in range(cx * 32, cx * 32 + 32):
                    t = world.tile(x, z)
                    if t[2] != WALK:
                        continue
                    for dx, dz, d in ((1, 0, 'Right'), (-1, 0, 'Left'), (0, 1, 'Down'), (0, -1, 'Up')):
                        n = world.tile(x + dx, z + dz)
                        if n and n[2] == WATER and n[1] == t[1]:
                            yield t[0], x, z, d


def walkable(t):
    """Behaviours a player walks on: even codes (odd ones block), except water."""
    return t is not None and not t[2] & 1 and t[2] != WATER


def path_from_border(world, goal, zone, limit=4000):
    """Shortest walk (directions) from a tile just outside `zone` into it, ending on `goal`: (start tile, moves)."""
    from collections import deque
    prev = {goal: None}
    queue = deque([goal])
    steps = {(1, 0): 'Right', (-1, 0): 'Left', (0, 1): 'Down', (0, -1): 'Up'}
    while queue and len(prev) < limit:
        x, z = queue.popleft()
        here = world.tile(x, z)
        for (dx, dz) in steps:
            n = (x + dx, z + dz)
            t = world.tile(*n)
            if n in prev or not walkable(t) or t[1] != here[1]:
                continue
            prev[n] = (x, z)
            if t[0] != zone:  # outside: walk back from here to the goal
                moves, at = [], n
                while prev[at] is not None:
                    nxt = prev[at]
                    moves.append(steps[(nxt[0] - at[0], nxt[1] - at[1])])
                    at = nxt
                return n, moves
            queue.append(n)
    return None


if __name__ == '__main__':
    world = World(Rom(open(sys.argv[1], 'rb').read()))
    if sys.argv[2] == 'surf':
        for spot in surf_spots(world):
            print(*spot)
