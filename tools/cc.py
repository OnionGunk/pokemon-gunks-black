"""Compile the code home (gunk/code/*.c) into one blob linked at 0x023C0000.

Needs arm-none-eabi-gcc (MSYS2: `pacman -S mingw-w64-ucrt-x86_64-arm-none-eabi-gcc`). Its folder comes from the
ARM_GCC_BIN environment variable, else PATH, else MSYS2's default ucrt64 folder. Returns the bytes to copy, the
size of the zeroed .bss after them, and every symbol's address, so patches can point hooks at functions by name.
"""
import glob
import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = os.path.join(ROOT, 'gunk', 'code')
OUT = os.path.join(ROOT, 'build', 'code')
CFLAGS = ['-mthumb', '-march=armv5te', '-mtune=arm946e-s', '-Os', '-ffreestanding', '-nostdlib', '-fno-builtin',
          '-ffunction-sections', '-fdata-sections', '-Wall', '-Werror']


def _tool(name):
    for folder in (os.environ.get('ARM_GCC_BIN'), None, r'C:\msys64\ucrt64\bin'):
        path = os.path.join(folder, name + '.exe') if folder else shutil.which(name)
        if path and os.path.exists(path):
            return path
    raise SystemExit(f'{name} not found: install arm-none-eabi-gcc or set ARM_GCC_BIN')


def build():
    sources = sorted(glob.glob(os.path.join(CODE, '*.c')))
    gcc = _tool('arm-none-eabi-gcc')
    # its DLLs on PATH; its scratch files in OUT (gcc fails on the apostrophe in this user's %TEMP%)
    env = dict(os.environ, PATH=os.path.dirname(gcc) + os.pathsep + os.environ.get('PATH', ''), TMP=OUT, TEMP=OUT)
    os.makedirs(OUT, exist_ok=True)
    elf = os.path.join(OUT, 'gunk.elf')
    script = os.path.join(OUT, 'gunk.ld')  # one script: this ld rejects a second one (or an INCLUDE) as a duplicate
    open(script, 'w').write(''.join(open(os.path.join(CODE, n)).read() for n in ('retail.ld', 'link.ld')))
    r = subprocess.run([gcc, *CFLAGS, '-Wl,--gc-sections,--no-warn-rwx-segments', '-T', script, '-o', elf, *sources],
                       cwd=CODE, env=env, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('gunk/code did not build:\n' + r.stdout + r.stderr)
    out = os.path.join(OUT, 'gunk.bin')
    subprocess.run([_tool('arm-none-eabi-objcopy'), '-O', 'binary', '-j', '.text', elf, out], env=env, check=True)
    blob = open(out, 'rb').read()
    nm = subprocess.run([_tool('arm-none-eabi-nm'), elf], capture_output=True, text=True, env=env, check=True).stdout
    syms = {}
    for line in nm.splitlines():
        parts = line.split()
        if len(parts) == 3:
            syms[parts[2]] = int(parts[0], 16)
    bss = syms['__bss_end'] - syms['__bss_start']
    open(os.path.join(OUT, 'gunk.bss'), 'w').write(f'{bss}\n')  # for the suite's code-home check
    return blob, bss, syms
