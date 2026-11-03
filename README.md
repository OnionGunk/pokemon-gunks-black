# Pokémon Gunk's Black Version

A quality-of-life hack of Pokémon Black, the sibling of Pokémon Gunk's Platinum Version and Gunk's HeartGold.
It keeps the game's difficulty and story as they are and takes the grind and friction out, for long playthroughs.

**Status: in development.** There's no release yet; the repo holds the source and the build. The full list of
planned changes, with what Black already has, is in [docs/GUNK_CHANGES.md](docs/GUNK_CHANGES.md).

## Features so far

- **Eggs hatch twice as fast** (four times with Flame Body or Magma Armor).
- **Trade evolutions without trading.** Kadabra evolves at level 36. Machoke, Graveler, Haunter, Boldore and
  Gurdurr evolve at 37. Karrablast and Shelmet evolve by levelling up with the other one in the party. Items that
  trigger a trade evolution (Metal Coat, King's Rock, Up-Grade and the rest) can be used like evolution stones.
  Trading still works.
- **Vitamins work up to 252 EVs** in a stat. The 510 total stays.
- **INSTANT text:** in Options, tap FAST again to switch to INSTANT. New games start on FAST.
- **The EXP bar fills twice as fast** in battle.
- **IVs and EVs on the summary:** press A on the STATS page to cycle stats, IVs and EVs.
- **Endless Repel and Exp. All:** key items from Mom (with the Running Shoes); use them to switch them on or
  off. With the Exp. All on, Pokémon that didn't battle get half the EXP, and the EVs.
- **Repel prompt:** when a Repel wears off and you have another, the game offers to use it.
- **Move Tutor in every Pokémon Center:** the Move Deleter and the move reminder, who now works for free.
- **HM moves without teaching them** (in, not yet seen in the game): a Pokémon that could learn an HM you
  own can use it in the field.
- **DexNav:** press R in tall grass to meet a Pokémon of that route, starting with one you haven't caught; L+R
  switches to the next. Searching for the same one again builds a chain for better IVs and shiny odds.
- **Auto-run:** once you have the Running Shoes you run without holding B; hold B to walk.
- **Follower Pokémon:** the first Pokémon in your party walks behind you: every species #1-649. #1-493 use
  Black's own overworld sprites, #494-649 the community-made HGSS-style Unova overworlds (credits below). It goes
  back in its ball while you cycle or surf.

## Play it

Releases will ship a **BPS patch**, not a ROM. You need your own dump of
**Pokémon Black (USA, Europe) (NDSi Enhanced), v1.0**:

```
sha1: 26ad0b9967aa279c4a266ee69f52b9b2332399a5
```

1. Download the `.bps` file from [Releases](../../releases).
2. Apply it to your ROM with [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/) (in the browser),
   Floating IPS, or `py tools/patch/bps.py apply <black.nds> <patch.bps> <out.nds>`.
3. Play it in a DS emulator or on a flash cart, in DS mode. A real DSi in DSi mode rejects modified DSi-enhanced
   ROMs.

## Build it

Python 3.13, `arm-none-eabi-gcc` for the new code (MSYS2: `pacman -S mingw-w64-ucrt-x86_64-arm-none-eabi-gcc`;
set `ARM_GCC_BIN` if it isn't in `C:\msys64\ucrt64\bin` or on PATH), plus your own Black dump (the build checks
its SHA-1 and refuses any other):

```
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install ndspy capstone pillow
echo C:/path/to/black.nds > baserom.txt
.venv/Scripts/python build.py            # build/gunk-black.nds and build/gunk-black.bps (verified)
.venv/Scripts/python build.py --vanilla  # the same pipeline with no patches: must equal the base ROM
```

How it works, and why it patches the retail ROM rather than building from a decompilation, is in
[docs/TOOLCHAIN.md](docs/TOOLCHAIN.md). Save-safety tests: `emu/suite/` (BizHawk).

## Credits

- [pokeblack](https://github.com/squiddonaut/pokeblack) by squiddonaut and contributors. Its disassembly is the map
  every code patch here is written against.
- [ndspy](https://github.com/RoadrunnerWMC/ndspy) by RoadrunnerWMC, for the ROM's file system and overlay compression.
- [PKHeX](https://github.com/kwsch/PKHeX), for the documented Gen 5 save layout the tests check.
- [BizHawk](https://github.com/TASEmulators/BizHawk) and melonDS, for the emulator tests.
- The DS Pokémon Hacking community's [Gen V documentation](https://ds-pokemon-hacking.github.io/).
- The Gen 5 follower sprites: the community HGSS-style Unova overworlds by hamsterSKULL (myumorph),
  Pokegirl4ever, Kyle-Dove, Phyromatical and the artists of the Pokémon Essentials follower set. The full list is in
  [gunk/followers/CREDITS.md](gunk/followers/CREDITS.md).
- The DexNav idea comes from later Pokémon games and fan hacks such as Pokémon Unbound.

Pokémon is © Nintendo, Creatures Inc. and GAME FREAK inc. This is a non-commercial fan project and contains no ROM data; the follower sprites are fan art (see their credits).
