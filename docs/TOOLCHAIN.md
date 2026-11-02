# Toolchain decision (2026-11-02)

**Decision:** patch the retail ROM with a Python build script in this repo (`build.py` + `gunk/patches.py`), using
the pokeblack disassembly as a read-only map of the code. New code, once it's needed, will be C/asm compiled with
MSYS2's `arm-none-eabi-gcc` and linked at fixed addresses. No CTRMap project and no decomp fork.

## What exists for Gen 5 (checked 2026-11-02)

| Option | State for Black (BW1) | Verdict |
|---|---|---|
| **squiddonaut/pokeblack** (decomp, github, 68★, last push 2026-10-17) | Builds a byte-identical Black USA ROM, but decomp.dev reports **0.03 % of the code decompiled** (19 of 363 functions). The rest is ndsdisasm output that refers to in-overlay data via absolute `ADDR_0217xxxx` symbols, so the code **isn't shiftable**: inserting code moves nothing it references. The build needs the proprietary TWL-SDK (`makelcf.exe`, `makerom.TWL.exe`), which is handed out on its Discord, plus Wine or MSYS2 and Metroskrew's mwcc. | Not a base for a long hack yet. **Used as a reference**: its asm gives every function boundary and the retail bytes, with a few names (`Heap_AllocDebug`, `MI_CpuCopy8`, …). Cloned sparse to `C:\Projects\pokeblack-ref`. |
| **fuddlesworth/pokebw2** | Decomp of **Black 2 / White 2**, not Black. | Wrong game. |
| **CTRMap-CE + CTRMapV, PMC / NitroKernel code injection** | CTRMap *edits* BW1 data (maps, scripts, text, zones). Its code injection (PMC, `swan` headers, ESDB symbol databases) is **B2W2 only**: there's no BW1 PMC build and no BW1 headers or symbol database, and the docs say so ("Code Injection … CTRMap (B2W2 only)"). | Not usable for code on BW1 without porting PMC and writing an ESDB first. It's a GUI project format, which is hard to diff and review, but it's fine for one-off data inspection. |
| **armips / G4Patcher-style patches** | Generic. G4Patcher is Gen 4 only. There's no BW1 hook framework or free-space map. | The approach we use, scripted in Python, so the checks and data edits live in the same place. |
| **Data editors** (Pokeweb, SwissArmyKnife, Tinke, NitroPaint) | Work on BW1 data. | Use them to *look*. Every shipped change is a script in this repo, so the build is reproducible. |

## Why this approach

1. **Reproducible and reviewable.** `build.py` takes the user's dump and checks it against SHA-1 `26ad0b99…`.
   It applies each patch in order and writes `build/gunk-black.nds`. Each patch is a short Python function, and it
   checks the retail bytes it replaces (`ndsrom.patch(..., old, new)`), so a wrong base ROM or a bad address fails
   the build instead of producing a broken ROM. `--vanilla` runs the same pipeline with no patches and must
   reproduce the base ROM byte for byte; it does.
2. **No layout churn.** `tools/ndsrom.py` edits the ROM in place. A grown file moves into the DSi digest tables
   (0xBFD9C00-0xC3B8C78, ~3.8 MB), which DS mode never reads, and nothing else moves. Compressed overlays that we
   patch are stored uncompressed. The 60 MB after the DSi region looks free but can't be used: a DSi-enhanced cart
   in DS mode doesn't serve reads from 0xC403000 onward, and melonDS emulates that. The first build put overlay 21
   there and hung on a white screen. If the 3.8 MB runs out, recompress the patched overlays (BLZ) before going
   further.
3. **Save safety.** Nothing here touches the save code unless a patch does it on purpose. The save layout is
   documented in `GUNK_CHANGES.md` (from PKHeX's `SaveBlockAccessor5BW`).
4. **Upgrade path.** If pokeblack becomes shiftable and largely decompiled, the patches are small and documented
   with retail addresses, so they can be re-expressed as source edits.

## Known limits

- **DS mode only.** The DSi digests and HMACs in the header go stale with any change. Emulators (melonDS, BizHawk,
  DeSmuME, Android emulators) run DS mode by default, and so do flash carts. A real DSi in DSi mode would reject
  the ROM. Black's DSi enhancements are minor.
- **New code needs a home.** The first ports only change constants and data. Instant text, Exp. All, the IV/EV
  view, the Repel prompt, DexNav and the other bigger ports need free RAM for new code. The plan is to reserve
  some at boot: lower the main arena's high end in the ARM9 init, then load a new code blob from the ROM there.
  That has to be measured in the emulator (the arena's free space, and that the heaps never touch it) before the
  first code port. See the plan in `GUNK_CHANGES.md`.

## Layout

- `build.py`: entry point. `baserom.txt` (gitignored) holds the base ROM path.
- `tools/ndsrom.py`: ROM file table, overlays (BLZ via ndspy), header and banner with CRCs.
- `tools/narc.py`: same-size edits inside NARCs, keeping every other byte.
- `tools/patch/bps.py`: BPS patches (from the Platinum hack); `build.py` makes `build/gunk-black.bps` and checks it reproduces the ROM.
- `gunk/patches.py`: the hack, one function per change.
- `emu/`: BizHawk harness (from the Platinum and HeartGold hacks) and `emu/suite/` save tests.
- Python: `.venv` (Python 3.13 + `ndspy`). Create it with `py -3.13 -m venv .venv && .venv/Scripts/python -m pip install ndspy`.
