"""Makes and applies BPS patches (the format Floating IPS, Rom Patcher JS and most emulators read).

    py bps.py make <original.nds> <modified.nds> <out.bps>
    py bps.py apply <original.nds> <patch.bps> <out.nds>

Releases ship a patch instead of the ROM. NDS files move around inside the ROM in 0x200 steps when one of
them grows, so besides copying unchanged spans in place, the encoder finds moved data through an index of
the original and copies it from there.
"""
import sys
import zlib

SOURCE_READ, TARGET_READ, SOURCE_COPY, TARGET_COPY = range(4)
INDEX_STRIDE = 64
KEY = 16
MIN_COPY = 32


def write_number(out, n):
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return
        out.append(x)
        n -= 1


def read_number(data, pos):
    n, shift = 0, 1
    while True:
        x = data[pos]
        pos += 1
        n += (x & 0x7F) * shift
        if x & 0x80:
            return n, pos
        shift <<= 7
        n += shift


def match_length(a, ai, b, bi):
    """How many bytes a[ai:] and b[bi:] have in common, comparing big chunks first."""
    limit = min(len(a) - ai, len(b) - bi)
    n, step = 0, 1 << 16
    while step and n < limit:
        s = min(step, limit - n)
        if a[ai + n:ai + n + s] == b[bi + n:bi + n + s]:
            n += s
        else:
            step >>= 2
    return n


def make(source, target):
    index = {}
    for p in range(len(source) - KEY, -1, -INDEX_STRIDE):  # backwards, so the earliest offset wins
        index[source[p:p + KEY]] = p

    out = bytearray(b'BPS1')
    write_number(out, len(source))
    write_number(out, len(target))
    write_number(out, 0)
    source_rel = 0
    literal = 0  # start of the pending TargetRead run
    t = 0

    def flush_literal(end):
        nonlocal literal
        if end > literal:
            write_number(out, ((end - literal - 1) << 2) | TARGET_READ)
            out.extend(target[literal:end])
        literal = end

    while t < len(target):
        n = match_length(source, t, target, t) if t < len(source) else 0
        if n >= MIN_COPY:
            flush_literal(t)
            write_number(out, ((n - 1) << 2) | SOURCE_READ)
            t += n
            literal = t
            continue
        p = index.get(target[t:t + KEY])
        if p is not None:
            start, sp = t, p
            while start > literal and sp > 0 and target[start - 1] == source[sp - 1]:
                start -= 1
                sp -= 1
            n = match_length(source, sp, target, start)
            if n >= MIN_COPY:
                flush_literal(start)
                write_number(out, ((n - 1) << 2) | SOURCE_COPY)
                delta = sp - source_rel
                write_number(out, (abs(delta) << 1) | (delta < 0))
                source_rel = sp + n
                t = start + n
                literal = t
                continue
        t += 1
    flush_literal(len(target))

    out += zlib.crc32(source).to_bytes(4, 'little')
    out += zlib.crc32(target).to_bytes(4, 'little')
    out += zlib.crc32(out).to_bytes(4, 'little')
    return bytes(out)


def apply(source, patch):
    if patch[:4] != b'BPS1':
        raise ValueError('not a BPS patch')
    if zlib.crc32(patch[:-4]) != int.from_bytes(patch[-4:], 'little'):
        raise ValueError('the patch file is damaged')
    if zlib.crc32(source) != int.from_bytes(patch[-12:-8], 'little'):
        raise ValueError('this is not the ROM the patch was made for')
    pos = 4
    source_size, pos = read_number(patch, pos)
    target_size, pos = read_number(patch, pos)
    meta, pos = read_number(patch, pos)
    pos += meta
    target = bytearray(target_size)
    t = source_rel = target_rel = 0
    end = len(patch) - 12
    while pos < end:
        data, pos = read_number(patch, pos)
        cmd, n = data & 3, (data >> 2) + 1
        if cmd == SOURCE_READ:
            target[t:t + n] = source[t:t + n]
        elif cmd == TARGET_READ:
            target[t:t + n] = patch[pos:pos + n]
            pos += n
        else:
            d, pos = read_number(patch, pos)
            d = -(d >> 1) if d & 1 else d >> 1
            if cmd == SOURCE_COPY:
                source_rel += d
                target[t:t + n] = source[source_rel:source_rel + n]
                source_rel += n
            else:
                target_rel += d
                for i in range(n):  # may overlap the bytes it writes
                    target[t + i] = target[target_rel + i]
                target_rel += n
        t += n
    if t != target_size or zlib.crc32(target) != int.from_bytes(patch[-8:-4], 'little'):
        raise ValueError('patching produced the wrong result')
    return bytes(target)


def main():
    cmd, a, b, out = sys.argv[1:5]
    first, second = open(a, 'rb').read(), open(b, 'rb').read()
    result = make(first, second) if cmd == 'make' else apply(first, second)
    open(out, 'wb').write(result)
    print(f'{out}: {len(result):,} bytes')


if __name__ == '__main__':
    main()
