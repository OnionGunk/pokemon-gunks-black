"""Build Pokémon Gunk's Black Version from your own Pokémon Black (USA/Europe) dump.

    .venv/Scripts/python build.py [--baserom PATH] [--vanilla]

The base ROM path comes from --baserom, else the BLACK_BASEROM environment variable, else baserom.txt (one line,
gitignored). Output: build/gunk-black.nds (or build/vanilla-black.nds with --vanilla: the same pipeline with no
patches, which must reproduce the base ROM byte for byte).
"""
import argparse
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(ROOT, 'tools'), os.path.join(ROOT, 'gunk')]

import ndsrom  # noqa: E402
import patches  # noqa: E402

BASE_SHA1 = '26ad0b9967aa279c4a266ee69f52b9b2332399a5'  # Pokémon Black (USA, Europe) (NDSi Enhanced), v1.0


def baserom_path(arg):
    if arg:
        return arg
    if os.environ.get('BLACK_BASEROM'):
        return os.environ['BLACK_BASEROM']
    txt = os.path.join(ROOT, 'baserom.txt')
    if os.path.exists(txt):
        return open(txt, encoding='utf-8').read().strip()
    sys.exit('no base ROM: pass --baserom, set BLACK_BASEROM or write the path to baserom.txt')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baserom')
    ap.add_argument('--vanilla', action='store_true')
    args = ap.parse_args()

    data = open(baserom_path(args.baserom), 'rb').read()
    sha = hashlib.sha1(data).hexdigest()
    if sha != BASE_SHA1:
        sys.exit(f'base ROM SHA-1 is {sha}, expected {BASE_SHA1} (Pokémon Black USA/Europe v1.0)')

    rom = ndsrom.Rom(data)
    if not args.vanilla:
        for p in patches.PATCHES:
            p(rom)
            print('applied', p.__name__)
    out = rom.save()

    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    path = os.path.join(ROOT, 'build', 'vanilla-black.nds' if args.vanilla else 'gunk-black.nds')
    open(path, 'wb').write(out)
    sha = hashlib.sha1(out).hexdigest()
    print(path, sha)
    if args.vanilla and sha != BASE_SHA1:
        sys.exit('vanilla build differs from the base ROM')


if __name__ == '__main__':
    main()
