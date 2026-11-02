# Pokémon Gunk's Black Version: change list

This file lists every change in Pokémon Gunk's Platinum Version. That's `pkplat-dexnav`, 23 commits on top of
pret/pokeplatinum `6eeb1b04`, classified the same way as the HeartGold port in
`pokemon-heartgold-gunk/docs/GUNK_CHANGES.md`. Each change has a verdict for Black:

- **port**: the same feature, rebuilt against Black's code or data.
- **adapt**: the same goal, but Black needs a different shape.
- **skip**: Black already has it, or the thing it changes doesn't exist in Black.

Each "Black has / lacks" claim was checked against retail Black, not B2W2. Several features people associate
with Gen 5, like the Repel prompt and the Running Shoes button, only arrived in Black 2 / White 2.

Rules carried over: no difficulty changes; no change to save layout unless a feature needs it; every patch checks
the retail bytes it replaces.

Status: ✅ done and tested in the emulator · 🟡 built and passes the save suite, feature itself not yet exercised
in-game · ⏳ planned · — skipped.

## Identity

| # | Change (Platinum commit) | Verdict | Black plan | Status |
|---|---|---|---|---|
| 1 | Name in the DS menu banner and end credits (8fa30cda) | port | Banner "Pokémon Gunk's / Black Version / Nintendo" in every language slot (`identity`). End credits: Black's staff roll title needs locating (text or graphic). | banner ✅, credits ⏳ |
| 2 | ROM header title `GUNK PL` (3f119584); game code kept | port | `GUNK B` (GUNK + the retail short code `POKEMON B`); the game code stays `IRBO` so emulators keep the 512 KB flash save type. | ✅ |
| 3 | Title-screen logo (24f96c51) | adapt | Black's title screen is a 3D/2D scene (`titledemo.narc`); needs new logo art in its format. | ⏳ |

## Save and storage

| # | Change | Verdict | Black plan | Status |
|---|---|---|---|---|
| 4 | 21 PC boxes (7713e967) | **adapt: needs your decision** | Black has **24** boxes. 649 species need 22, so 24 gives 2 spare boxes plus 11 slots. 25 doesn't fit in the main save (see "Save budget"). Black's save half is packed solid: 70 blocks from 0x00000 to 0x23F8C, a mirror copy at 0x24000, and extra saves (Battle Videos, C-Gear skin, Musical download, Pokédex skin, Hall of Fame) filling 0x4A000-0x80000. A 25th box could only live outside the main save, e.g. in the 128 KB Musical-download area (Wi-Fi/IR content), with its own two alternating copies and CRCs so a torn save can't lose it, plus the PC app's 24-box limits. That's a large, save-critical change for one box. **Recommendation: keep 24.** | ⏳ ask |
| 5 | Save table grown for DexNav search levels (5985a222) | adapt | There's no room in the main save (see #4). The slack at the end of each block's 0x100 slot is tens of bytes, which is not enough for 649 levels. Options: store levels only for the last N species searched (fits in slack), or use an extra-save slot with its own double-buffering. Decide with DexNav. | ⏳ |
| 6 | Static check that the save fits in one flash half | port | A build-time check in `patches.py` that any block we grow still ends before the next block and the checksum table. | ⏳ |

## DexNav

| # | Change | Verdict | Black plan | Status |
|---|---|---|---|---|
| 7 | DexNav key item, R search, chains, search levels, search bar (5985a222) | adapt | Black's encounters (`a/1/2/6`) have **four seasons** × grass / dark grass / rustling grass / surf / ripples / fishing. Build the species list from the current season's table. Black has no R-button field action, so R is free. | ⏳ |
| 8 | Legal encounters via one Method J sequence (941125b5) | adapt | Gen 5 wild Pokémon take their PID from the 64-bit LCG and their IVs from the Mersenne Twister, with no PID↔IV link. Reroll through Black's own wild-generation function and the result is legal. Simpler than Gen 4. | ⏳ |
| 9 | DexNav Pokétch app (b5551c4f, 7890b973) | adapt | Black has no Pokétch. The bottom screen is the C-Gear (fixed layout, wireless features). Plan: the key item's own touch-screen grid (caught / seen silhouette / unseen "?"), the same plan as HeartGold. | ⏳ |
| 10 | DexNav gift after the catching tutorial (b5551c4f) | adapt | Black's equivalent: Bianca's mom / Juniper's catching demo on Route 1, or Juniper in Nuvema. | ⏳ |

## Followers

| # | Change | Verdict | Status |
|---|---|---|---|
| 11-15 | Following Platinum's followers, interactions, cutscene edits, Surf/bike/door handling, crash fixes | **adapt: very large** | Black has no follower system and no overworld sprites for Pokémon (Gen 5 overworld sprites exist only for a few story Pokémon). It needs 649 sprite sets, a renderer, movement and every cutscene. This is the single largest item. Proposal: last, after everything else, and only if you want it. | ⏳ ask |
| 16 | Movement-end handler fix (c026a1c9) | skip | Fixes the Platinum follower port's interaction with screen effects. Black has no followers, so the bug can't happen. Revisit only with #11. | — |

## Quality of life

| # | Change | Verdict | Black plan | Status |
|---|---|---|---|---|
| 17 | INSTANT text speed; new games start on FAST (c0644cff, 9c1ccbc6) | port | Black has SLOW/MID/FAST. Add INSTANT (needs new code: the text printer's per-frame loop). | ⏳ |
| 18 | EXP bar twice as fast (c0644cff) | port | Battle gauge code in the battle overlays. Constant or small code patch. | ⏳ |
| 19 | HP bars one pixel per frame (566793ec) | port | Same gauge code as #18. | ⏳ |
| 20 | Auto-run, hold B to walk (c0644cff) | port | Black has **no** run toggle (it's hold B only; B2W2 doesn't add one either). Field input patch: invert B for running (only where running is allowed already). | ⏳ |
| 21 | Repel prompt when a Repel wears off (c0644cff) | port | Black has **no** prompt (B2W2 added it). The repel step counter is in the Encount block (0x21B00 +0x2D steps, +0x2E type). New field script + script command. | ⏳ |
| 22 | Endless Repel key item from Mom (c0644cff) | port | New item: Black's item table has 627 entries (0-626) and unused IDs inside it. A key item with a script; Mom gives it at the start. | ⏳ |
| 23 | Reusable TMs (e8f1b80d) | skip: Black has it | Gen 5 TMs are reusable. | — |
| 24 | Field moves without the move (e8f1b80d) | port | Black's HMs: Cut, Fly, Surf, Strength, Waterfall, Dive. Party-menu field-move list + the field checks. | ⏳ |
| 25 | Move Tutor in every Pokémon Center (e8f1b80d) | adapt | Black's Move Relearner is in Mistralton City (Heart Scale). Add a free relearner/deleter NPC to the Pokémon Center layout (Black's Centers share a script set). | ⏳ |
| 26 | Summary: A on Skills cycles stats / IVs / EVs (2957e59d) | port | Black's summary shows no IVs/EVs. New code in the summary overlay. | ⏳ |
| 27 | Exp. All key item: half EXP and EVs to party members that didn't battle (2957e59d) | port | Black's Exp. Share is the Gen 4 held item (split EXP with the holder). There's no party-wide option, despite what the brief assumed (that arrived in Gen 6). Battle EXP code + a key item toggle. | ⏳ |
| 28 | Vitamins up to 252 EVs (2957e59d) | port | Black caps vitamins at 100 EVs. Constant in the item-use code. | ⏳ |
| 29 | Bag: Start sorts the open pocket (2957e59d) | port | Black lets you drag items around on the touch screen, but has no automatic sort. | ⏳ |
| 30 | Two registered items: Y and Select (2957e59d) | skip: Black has it | Black registers any number of items to Y; with more than one, Y opens a chooser. | — |
| 31 | Honey tree timer (2957e59d) | skip | No honey trees in Black. | — |
| 32 | Poké Radar chain length (2957e59d) | skip | No Poké Radar in Black. | — |
| 33 | Eggs hatch twice as fast (2957e59d) | port | `faster_eggs`: Black's `Party_GetEggCyclesToSubtract` (overlay 21, 0x0218AA2C) returns 2/1, patched to 4/2. | 🟡 |
| 34 | Trade evolutions by level; trade items used like stones (2957e59d) | port | `trade_evolutions`: Kadabra 36; Machoke, Graveler, Haunter 37; Gen 5's **Boldore and Gurdurr 37**. **Karrablast/Shelmet** (trade for each other) level up with the other one in the party (Gen 5's Mantyke-style method 22). Every trade-with-item species also evolves by using the item (method 8), and those 11 items get the evolution stones' use settings. Trading still works. | 🟡 |
| 35 | UNLOCK FPS option (211b80ef) | skip (ask) | Came with the follower port, not a request. | — |

## Test infrastructure

| # | Change | Verdict | Black plan | Status |
|---|---|---|---|---|
| 36 | `gHeapAllocFails` counter (9c1ccbc6) | port | Needs new code (a counter bumped on Black's GFL heap allocation-failure path), so it comes with the first code port. Until then the suite checks for hangs and crashes. | ⏳ |
| 37 | Test builds: start points, warp anywhere | adapt | Later, with new code. | ⏳ |
| 38 | BizHawk harness and save suite | adapt | `emu/` (from `hg-tools/emu`), Black's save format in `emu/suite/lib.py`. | see results |

## Save budget (Black, from PKHeX `SaveBlockAccessor5BW`)

- 512 KB flash. Main save 0x00000-0x23FFF and a mirror at 0x24000-0x47FFF. Each block is CRC-16-CCITT checked, with
  the CRC in its footer (`offset + length + 2`) and again in the table block at 0x23F00 (+2 per block).
- Blocks: box names/wallpapers 0x00000 (0x3E0); boxes 1-24 at 0x00400 + n·0x1000 (0xFF0 each, 30 × 136 B);
  then inventory 0x18400, party 0x18E00, trainer 0x19400 … 70 blocks, the checksum table at 0x23F00 (0x8C).
  The blocks are 0x100-aligned, so the only slack is the tail of each block's 0x100 slot (a few to ~0xF0 bytes).
- Extra saves (single copy): 0x4A000 battle videos (×4, 0x2000), 0x52000 C-Gear skin, 0x55000 battle test,
  0x56000 Musical download (0x20000), 0x76000 Pokédex skin, 0x7C800/0x7E000 Hall of Fame, 0x7F800/0x7FC00 link.
