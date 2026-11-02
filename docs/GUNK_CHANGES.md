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
| 4 | 21 PC boxes (7713e967) | **skip: Black already has enough** | Goal (decided 2026-11-02): a living dex through Gen 5 plus a box or two. Black has **24** boxes (720 slots). The 649 species fill 22 boxes (21 full + 19), which leaves 71 slots: 2 spare boxes plus 11. No save change needed. A 25th box wouldn't fit in the main save anyway (see "Save budget"). The save half is packed solid, with 70 blocks from 0x00000 to 0x23F8C and a mirror copy at 0x24000. | — |
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
| 11-15 | Following Platinum's followers, interactions, cutscene edits, Surf/bike/door handling, crash fixes | **adapt: very large, wanted** (decided 2026-11-02) | Black has no follower system and almost no Pokémon overworld sprites. Sprites, in this order: **(1)** #1-493 come from HeartGold's own follower sprites, extracted at build time from the user's HeartGold dump (`C:\Projects\hg-baserom`), so the repo and the patch carry no extracted art beyond what the BPS needs. HGSS sprites are 32×32 / 64×64 four-direction walk sheets, the same frame grid as Black's NPCs. **(2)** #494-649: a community Gen 5 follower sprite pack in the HGSS style (the packs made for HGSS-style follower projects and Essentials resources), used only with the artists' permission and credited by name in the README. If a gap remains, flag those species and don't ship placeholders silently. Code: a field-object follower in Black's map-object system, movement that copies the player, Surf/bike/door/warp handling, and cutscene hiding, ported from the Platinum design. It goes after the QoL ports and DexNav, because it touches the most systems. | ⏳ |
| 16 | Movement-end handler fix (c026a1c9) | skip | Fixes the Platinum follower port's interaction with screen effects. Black has no followers, so the bug can't happen. Revisit only with #11. | — |

## Quality of life

| # | Change | Verdict | Black plan | Status |
|---|---|---|---|---|
| 17 | INSTANT text speed; new games start on FAST (c0644cff, 9c1ccbc6) | port | **FAST default done** (`text_fast_default`): the options' new-game defaults (`FUN_02008320`, ARM9) set text speed 2 instead of 1. Checked: a new game's options word is 0x0202 (retail 0x0201), and the suite passes. INSTANT still needs new code (the text printer's per-frame loop) and a fourth choice on the Options row. | FAST ✅, INSTANT ⏳ |
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
| 28 | Vitamins up to 252 EVs (2957e59d) | port | `vitamins_to_252`: overlay 91's can-use test (`FUN_overlay_d_91__021bdd78`, one "EV < 100" per stat) and its EV calculation (`021be948`, clamp to 100) now use 252. The 510 total and the wings' 255 stay. | ✅ |
| 29 | Bag: Start sorts the open pocket (2957e59d) | port | Black lets you drag items around on the touch screen, but has no automatic sort. | ⏳ |
| 30 | Two registered items: Y and Select (2957e59d) | skip: Black has it | Black registers any number of items to Y; with more than one, Y opens a chooser. | — |
| 31 | Honey tree timer (2957e59d) | skip | No honey trees in Black. | — |
| 32 | Poké Radar chain length (2957e59d) | skip | No Poké Radar in Black. | — |
| 33 | Eggs hatch twice as fast (2957e59d) | port | `faster_eggs`: Black's `Party_GetEggCyclesToSubtract` (overlay 21, 0x0218AA2C) returns 2/1, patched to 4/2. | ✅ |
| 34 | Trade evolutions by level; trade items used like stones (2957e59d) | port | `trade_evolutions`: Kadabra 36; Machoke, Graveler, Haunter 37; Gen 5's **Boldore and Gurdurr 37**. **Karrablast/Shelmet** (trade for each other) level up with the other one in the party (Gen 5's Mantyke-style method 22). Every trade-with-item species also evolves by using the item (method 8), and those 11 items get the evolution stones' use settings. Trading still works. | ✅ |
| 35 | UNLOCK FPS option (211b80ef) | skip (ask) | Came with the follower port, not a request. | — |

## Test infrastructure

| # | Change | Verdict | Black plan | Status |
|---|---|---|---|---|
| 36 | `gHeapAllocFails` counter (9c1ccbc6) | port | Needs new code (a counter bumped on Black's GFL heap allocation-failure path), so it comes with the first code port. Until then the suite checks for hangs and crashes. | ⏳ |
| 37 | Test builds: start points, warp anywhere | adapt | Later, with new code. | ⏳ |
| 38 | BizHawk harness and save suite | adapt | `emu/` (from `hg-tools/emu`) on Black's own BizHawk copy (`C:\Projectsizhawk-black\EmuHawkBlack.exe`, renamed so other harnesses' `taskkill /IM EmuHawk.exe` can't hit it). `emu/suite/suite.py` checks Black's save format. | ✅ |

## Save budget (Black, from PKHeX `SaveBlockAccessor5BW`)

- 512 KB flash. Main save 0x00000-0x23FFF and a mirror at 0x24000-0x47FFF. Each block is CRC-16-CCITT checked, with
  the CRC in its footer (`offset + length + 2`) and again in the table block at 0x23F00 (+2 per block).
- Blocks: box names/wallpapers 0x00000 (0x3E0); boxes 1-24 at 0x00400 + n·0x1000 (0xFF0 each, 30 × 136 B);
  then inventory 0x18400, party 0x18E00, trainer 0x19400 … 70 blocks, the checksum table at 0x23F00 (0x8C).
  The blocks are 0x100-aligned, so the only slack is the tail of each block's 0x100 slot (a few to ~0xF0 bytes).
- Extra saves (single copy): 0x4A000 battle videos (×4, 0x2000), 0x52000 C-Gear skin, 0x55000 battle test,
  0x56000 Musical download (0x20000), 0x76000 Pokédex skin, 0x7C800/0x7E000 Hall of Fame, 0x7F800/0x7FC00 link.

## Plan for the remaining ports

In order. Each one gets its own local commit, is built, and is run through `emu/suite` (vanilla as the control)
before the next.

1. **In-game feature tests for the first ports.** Add a second start state after the starter and Bianca's
   battle, and find the party and bag in RAM through the loaded save buffer. Then test HP Up ×26 to 252 EVs;
   a Metal Coat on Onix; Kadabra at 36 via EXP; and an egg's cycle counter dropping 2 per 256 steps. These move
   #28, #33 and #34 from 🟡 to ✅.
2. **A home for new code.** Measured 2026-11-02 in the field after a battle, the bag, the party menu and
   evolution scenes. The SDK's arena table (0x02FFFDA0: lo[9], then hi[9]) puts the main arena at
   **0x023B47F0-0x023E0000** (~178 KB) once the game has made its heaps, and that whole range was zero. Design:
   - Put new code at the top, **0x023D0000-0x023E0000 (64 KB)**, as a new ARM9 overlay. Append an overlay-table
     entry (#237, RAM 0x023D0000) and a FAT entry (file id 484, after the last named file; the table and FAT move
     to free ROM space and the header's 0x48/0x50 pointers follow).
   - One early hook in the boot code (after the heaps are made) calls the SDK's `FS_LoadOverlay` for #237 and
     lowers the main arena's hi pointer to 0x023D0000, so nothing the SDK allocates later can land on the code.
   - Code: C built with MSYS2's `arm-none-eabi-gcc -mthumb -march=armv5te -Os`, linked at 0x023D0000 against a
     symbol file of retail addresses from pokeblack. Hooks are written by `patches.py` with the same retail-bytes
     check.
   - Before relying on it, add a suite check: fill 0x023B47F0-0x023D0000 with a canary at the start and confirm
     it survives every test, with battle, PC, Pokédex and C-Gear scenes added to the tour.
   - First users: #36 `gHeapAllocFails` (a counter on GFL's allocation-failure path), then INSTANT text.
3. **Text and bars (#17-19):** INSTANT text speed in Options (and new games start on FAST); EXP bar ×2; HP bars
   1 px/frame. Find the text printer's per-frame step and the battle gauge code in the disassembly.
4. **Auto-run (#20):** invert B for running in the field input code. Found so far: the held-buttons word is a u16
   at **0x0214C360** (ARM9 .bss), written each frame by a copy at 0x020858A4 (lr 0x020851E8). No literal in the
   disassembly points at it, so code reaches it through a struct pointer, and melonDS's read callbacks don't fire,
   so `watchread` can't find the readers. Next: break on the field's movement-speed choice instead. Watch the
   player object's speed or animation field with `watchwrite` while walking and running, then follow pc/lr back to
   the B test.

Debug tools added to `emu/bridge.lua`: `watchwrite <addr> <path>` (logs every write with pc, lr and r0-r3; this
found the options defaults), `holddump <Btn> <frames> <addr> <len> <path>`, and `watchread` (no effect on this core).
Useful addresses (retail = Gunk's): the save buffer is at 0x0221BBAC in the field, laid out like the flash save,
with the party at +0x18E00, the bag at +0x18400 (Medicine pocket +0x7D8), and options/trainer at +0x19400. The
main system struct is at 0x020AA194, with the frame counter at +0xC.
5. **Summary IV/EV view (#26)** and **bag sorting (#29).**
6. **Field moves without the move (#24)** and the **Move Tutor in every Pokémon Center (#25)**. That needs
   Black's script format: CTRMap's PokéScript or SwissArmyKnife docs for the event and script NARCs.
7. **New key items: Endless Repel (#22), Exp. All (#27), the Repel prompt (#21).** Black's item table has 627
   entries with unused IDs inside it, so new items take free IDs instead of growing the table. Mom gives them in
   Nuvema. Exp. All needs the battle EXP code.
8. **DexNav (#7-#10)** on the seasonal encounter tables, with the key-item touch grid. The search-level storage
   is decided then (see #5).
9. **Followers (#11-15):** sprites from the user's HeartGold dump for #1-493, a credited Gen 5 pack for
   #494-649, then the follower object and its movement, Surf, bike, door and cutscene handling.
10. **Title logo (#3)** and **credits name (#1).**

## Test results (2026-11-02)

`emu/suite`, Black's own BizHawk (melonDS core), minimized. Both builds start from the real intro (title, Juniper,
name, bedroom); there are no test hooks in the ROM.

| Test | vanilla (= retail) | Gunk's Black at 34e21de |
|---|---|---|
| save_cycles (3 saves at different spots, each followed by a power cycle, Continue and a re-save: counter +1, same position, party, bag, boxes) | pass | pass |
| crash_after_save (emulator killed after the save, no flush) | pass | pass |
| torn_save (crash at 10 points during a save) | pass | pass |
| backup_recovery (each flash half damaged in turn) | pass | pass |

How a torn save behaves (identical in both builds): Black writes the main half first (from about +280 frames
after the confirming A, block by block, with the checksum table last at about +330), then the backup half (about
+350 to +410). A cut anywhere leaves at most one half torn. The game loads the other half, so you continue from the
previous save (cut before about +330) or the new one (cut after). The next save rewrites both halves.

The first Gunk's build hung on a white screen entering the field. Overlay 21 had been moved past the DSi region,
which a DS-mode cart can't read. Fixed in 34e21de; see TOOLCHAIN.md.

### Features in the game (Gunk's Black, 2026-11-02)

The Pokémon and items were set up in RAM, through `emu/suite/pk5.py` and the live save buffer at 0x0221BBAC: the
party is at +0x18E00 and the bag at +0x18400, with the Medicine pocket at +0x7D8. Everything else used the real
game UI (bag, party menu, evolution scenes).

- **Vitamins:** HP EVs set to 100, then HP Ups from the bag. "Tepig's base HP rose!" took it to 110, and on up to
  exactly 252 (16 used). The next one: "It won't have any effect."
- **Trade item as a stone:** a Metal Coat on an Onix showed ABLE! in the party menu and evolved it into Steelix
  (the coat was used up). A Metal Coat on a Kadabra showed UNABLE!.
- **Trade evolution by level:** a Kadabra at level 35 plus a Rare Candy reached level 36 and evolved into Alakazam.
- **Eggs:** an egg with 10 cycles left had 8 left after about 300 steps, one 256-step boundary. Retail drops 1
  per boundary.

Not checked yet: Karrablast/Shelmet (they use the game's own Mantyke method), Boldore/Gurdurr levels, and the DS
menu banner text on a real DS menu.
