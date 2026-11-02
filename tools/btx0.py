"""Minimal NSBTX (BTX0 / TEX0) reader: texture and palette names, formats and sizes."""
import struct

FORMATS = {1: 'a3i5', 2: '2bpp', 3: '4bpp', 4: '8bpp', 5: '4x4', 6: 'a5i3', 7: 'direct'}


def _dict(buf, off):
    """NNS info dictionary: returns [(name, entry bytes)]."""
    count = buf[off + 1]
    tree_size = 4 + (count + 1) * 4
    info = off + 4 + tree_size
    unit, sect = struct.unpack_from('<HH', buf, info)
    names_off = info + sect
    out = []
    for i in range(count):
        entry = buf[info + 4 + i * unit:info + 4 + (i + 1) * unit]
        name = buf[names_off + i * 16:names_off + (i + 1) * 16].rstrip(b'\0').decode('latin1')
        out.append((name, entry))
    return out


def read(data):
    """Returns (textures, palettes, tex0 block): textures as dicts of name, fmt, w, h, off, size;
    palettes as dicts of name, off."""
    tex0 = struct.unpack_from('<I', data, 0x10)[0]
    t = data[tex0:]
    assert t[:4] == b'TEX0'
    tex_data_size = struct.unpack_from('<H', t, 0x0C)[0] << 3
    tex_dict = struct.unpack_from('<H', t, 0x0E)[0]
    tex_data = struct.unpack_from('<I', t, 0x14)[0]
    pal_dict = struct.unpack_from('<H', t, 0x34)[0]
    pal_data = struct.unpack_from('<I', t, 0x38)[0]
    texs = []
    for name, e in _dict(t, tex_dict):
        param = struct.unpack_from('<I', e)[0]
        fmt = param >> 26 & 7
        w = 8 << (param >> 20 & 7)
        h = 8 << (param >> 23 & 7)
        bpp = {1: 8, 2: 2, 3: 4, 4: 8, 5: 2, 6: 8, 7: 16}[fmt]
        texs.append(dict(name=name, fmt=FORMATS[fmt], w=w, h=h, off=tex_data + ((param & 0xFFFF) << 3),
                         size=w * h * bpp // 8))
    pals = []
    for name, e in _dict(t, pal_dict):
        pals.append(dict(name=name, off=pal_data + (struct.unpack_from('<H', e)[0] << 3)))
    return texs, pals, t
