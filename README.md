# Pokémon Gunk's Black Version

A Pokémon Black (USA/Europe, v1.0) ROM hack that carries over the changes of Pokémon Gunk's Platinum Version
(and its HeartGold sibling) for long playthroughs. No difficulty changes.

- What changes and why: [docs/GUNK_CHANGES.md](docs/GUNK_CHANGES.md)
- How it's built and why this toolchain: [docs/TOOLCHAIN.md](docs/TOOLCHAIN.md)

## Build

Needs your own dump of Pokémon Black (SHA-1 `26ad0b9967aa279c4a266ee69f52b9b2332399a5`). No ROM is in this repo.

```
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install ndspy
echo C:/path/to/black.nds > baserom.txt
.venv/Scripts/python build.py            # build/gunk-black.nds
.venv/Scripts/python build.py --vanilla  # build/vanilla-black.nds, must equal the base ROM
```

## Test

`emu/suite/suite.py` (BizHawk, minimized): save cycles, power cycle, crash after save, crash during a save,
damaged-save recovery. See `emu/suite/README.md`.
