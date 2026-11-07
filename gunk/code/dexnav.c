/* DexNav: R opens the DexNav screen, which lists this spot's Pokémon (script 10146, patches.dexnav_screen). Picking
   one makes Black's own effect for the terrain come out 2-4 tiles away (rustling grass, a dust cloud in a cave,
   rippling water while surfing; dark grass, which Black never rustles, gets the grass rustle), and walking into it
   within 10 seconds meets the Pokémon. Searching for the same species again and again builds a chain (a wild
   encounter with another species ends it, one with the chain's species keeps it, and running from a wild battle
   ends it): each link rerolls the personality value once more for a shiny (up to 40), and chains of 10, 20 and 30
   give 1, 2 and 3 perfect IVs. Each DexNav encounter also raises the species' search level (saved, dexnav_save.c):
   every 10 levels add one more shiny reroll, and every 2 levels one more set of IVs to keep the best of.

   The spot's terrain picks the encounter tables (each zone's table has seven, see ENC_KINDS): on water the surf and
   rippling-water ones, in dark grass the dark grass and rustling ones, anywhere else (grass, cave floor) the grass
   (a cave's walking) and rustling (a cave's dust cloud) ones. Encounters stay legal: one of the target's slots in
   its own table, with that table's slot odds (each slot has its own level), is made into the encounter by the
   game's own code (level from the slot's range, its form rule, the lead's Pressure/Hustle/Vital Spirit level
   boost), the game generates the Pokémon as for any wild one, and a Gen 5 personality value is an independent
   random number (shininess comes from it alone, so the IVs set afterwards can't change it).

   Field overlay (21):
   - DexNav_Input runs with the field's per-frame input (field.c) and notes R.
   - Gunk_StepEncount wraps the per-frame step-encounter check (FUN_overlay_d_21__0218b208): with R noted it builds
     the spot's list and starts the screen; after a pick it starts the effect near the player (see PlacePatch).
   - Gunk_DexNav_EffectEncount wraps the effect's encounter (FUN_overlay_d_21__021a9f40, type 1) and makes the
     search's meet the target; Gunk_DexNav_EffectRoll makes its dust cloud a Pokémon rather than an item.
   - Gunk_DexNav_ScanKind wraps the effect module's tile scan, for dark grass.
   - Gunk_DexNav_PickSlots wraps that encounter's slot pick and puts the target in the first record.
   - Gunk_DexNav_Pid wraps the personality-value roll (FUN_overlay_d_21__021a9d30) and Gunk_DexNav_Create the
     building of the wild Pokémon (FUN_overlay_d_21__021a96b8).
   Script overlay (10):
   - Gunk_DexNav_BattleResult wraps the wild battle event's read of the battle's result (FUN_02012a44, at
     0x0216E744) and ends the chain when the player ran. */
#include "dexnav.h"

#define PAD_R 0x0100
#define PAD_L 0x0200

#define ENC_KINDS 7          /* the zone's encounter table (a/1/2/6, 232 bytes): 7 rates, flags, then 4-byte slots */
#define ENC_LOADED 0x80      /* byte 7 */
#define KIND_GRASS 0         /* the tables, in FUN_overlay_d_21__021a9a5c's order */
#define KIND_DARK 1
#define KIND_RUSTLE 2        /* rustling grass, and a cave's dust cloud */
#define KIND_SURF 3
#define KIND_RIPPLE 4        /* rippling water */

#define SAVE_BLOCK_DEX 55
#define DEX_CAUGHT 0x08      /* one bit per species, from #1 */
#define DEX_SEEN 0x5C        /* four such sets (male, female, shiny male, shiny female), 0x54 bytes each */
#define DEX_BITS 0x54

#define CHAIN_MAX 40
#define PARAM_IV_HP 70       /* 70-75 */
#define IV_MAX 31
#define FRAME_COUNTER (*(volatile u32 *)0x020AA1A0)

struct EncSlot {
    u16 species;             /* low 11 bits; the form in the top 5 */
    u8 min, max;
};

struct EncRecord {           /* what the slot pick fills in, 20 bytes each */
    u16 species;
    u16 item;
    u8 level;
    u8 form;
    u8 rest[14];
};

#define StepEncount ((u32 (*)(void *, void *, void *))(0x0218B208 | 1))
#define FieldSys_GetEncount ((void *(*)(void *))(0x02188CE8 | 1))
#define Encount_Try ((u32 (*)(void *, u32))(0x021A9F40 | 1))
#define Encount_PickSlots ((u32 (*)(const u8 *, void *, void *, struct EncRecord *))(0x021A954C | 1))
#define Encount_SlotRecord ((void (*)(const struct EncSlot *, struct EncRecord *))(0x021A9B00 | 1))
#define Encount_LeadLevel ((void (*)(void *, const struct EncSlot *, struct EncRecord *))(0x021A9BE8 | 1))
#define Encount_RollPid ((u32 (*)(u8 *, void *, struct EncRecord *))(0x021A9D30 | 1))
#define Encount_CreateMon ((void (*)(void *, void *, struct EncRecord *))(0x021A96B8 | 1))
#define PP_Get ((u32 (*)(void *, u32, void *))(0x02017E1C | 1))
#define PP_Put ((void (*)(void *, u32, u32))(0x02017E40 | 1))
#define PP_CalcStats ((void (*)(void *))(0x02018A7C | 1))  /* stats (and HP) from level, IVs, EVs, nature */
#define Key_GetTrg ((u32 (*)(void))0x020362DC)
#define Key_GetCont ((u32 (*)(void))0x0203630C)
#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)
#define BattleParam_GetResult ((u32 (*)(void *))(0x02012A44 | 1))
#define BTL_RESULT_RUN 3     /* 0 lost, 1 won, 3 ran, 5 caught */
#define Random1000 ((u32 (*)(u32))(0x02005728 | 1))
#define WordSet_SpeciesName ((void (*)(void *, u32, u32))(0x0201EE60 | 1))

/* each table's place, slot count and slot odds */
static const u8 sKindOffset[ENC_KINDS] = { 0x08, 0x38, 0x68, 0x98, 0xAC, 0xC0, 0xD4 };
static const u8 sKindSlots[ENC_KINDS] = { 12, 12, 12, 5, 5, 5, 5 };
static const u8 sLandRate[12] = { 20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1 };
static const u8 sWaterRate[5] = { 60, 30, 5, 4, 1 };

struct ListEntry {
    u16 species;
    u8 kind;                  /* its table */
};

static struct ListEntry sList[DEXNAV_LIST_MAX];
static u32 sListSpot;        /* the zone and tile it was last built for by DexNav_Frame */
static u8 sListCount;
static const u8 *sListTable;  /* the table the list was built from */
static u8 sPick;              /* 1 + the row picked on the screen, until the effect is placed */

static u16 sTarget;       /* species being searched for right now (0: no search running) */
static u8 sTargetKind;
static u16 sLastPick;     /* the last species searched, for the screen's cursor */
static u8 sRequested;     /* R was pressed; 2 with L held */
static u8 sMessage;       /* a DexNav message to show (MSG_*), about sMessageSpecies */
static u16 sMessageSpecies;
static u16 sChainSpecies;
static u8 sChain;
static u8 sSearchLevel;   /* the target's search level when its search started */
static u32 sRand;

static int DexBit(int offset, u32 species)
{
    const u8 *dex = SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_DEX) + offset;

    return species && (dex[(species - 1) / 8] >> ((species - 1) % 8)) & 1;
}

static int Caught(u32 species)
{
    return DexBit(DEX_CAUGHT, species);
}

static int Seen(u32 species)
{
    int k;

    for (k = 0; k < 4; k++)
        if (DexBit(DEX_SEEN + k * DEX_BITS, species))
            return 1;
    return 0;
}

static const struct EncSlot *Slots(const u8 *table, int kind)
{
    return (const struct EncSlot *)(table + sKindOffset[kind]);
}

static u16 SlotSpecies(const u8 *table, int kind, int i)
{
    return Slots(table, kind)[i].species & 0x7FF;
}

static u32 Random(void)
{
    sRand = sRand * 0x41C64E6D + 0x6073 + FRAME_COUNTER;
    return sRand >> 16;
}

#define SAVE_BLOCK_BAG 25
#define SAVE_BLOCK_VARS 45       /* u16 vars from 0x4000 */
#define BAG_KEY_ITEMS 0x4D8      /* {u16 item, u16 count} */
#define BAG_KEY_SLOTS 83
#define VAR_ROUTE1_SCENE 0x407C  /* 1 once Juniper's catching lesson on Route 1 is over (script 634) */

/* the player has the DexNav. Juniper gives it at the end of her lesson on Route 1; a save from before it was added
   to the game, already past that lesson, gets it here. */
static int HaveDexNav(void)
{
    u16 *key = (u16 *)(SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_BAG) + BAG_KEY_ITEMS);
    u16 *vars = (u16 *)SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_VARS);
    int i;

    for (i = 0; i < BAG_KEY_SLOTS && key[2 * i]; i++)
        if (key[2 * i] == ITEM_DEXNAV)
            return 1;
    if (!vars[VAR_ROUTE1_SCENE - 0x4000] || i == BAG_KEY_SLOTS)
        return 0;
    key[2 * i] = ITEM_DEXNAV;
    key[2 * i + 1] = 1;
    return 1;
}

/* with the field's per-frame input (field.c) */
void DexNav_Input(void)
{
    if ((Key_GetTrg() & PAD_R) && HaveDexNav())
        sRequested = (Key_GetCont() & PAD_L) ? 2 : 1;
}

/* The search's effect is Black's own (its "effect_encount" module, overlay 21, the one that makes grass rustle
   every so often): DexNav fills the module's list of candidate tiles around the player (FUN_overlay_d_21__021aacd4),
   keeps those 2-4 tiles away of the terrain's kind, and lets the module pick one and start the effect there
   (FUN_overlay_d_21__021aae34), sound and all. Stepping into it runs the module's own encounter
   (FUN_overlay_d_21__021aa944, which calls the encounter of type 1 at 0x021AA9EA: Gunk_DexNav_EffectEncount wraps
   that call and makes it the target). After PATCH_FRAMES the effect is cleared (FUN_overlay_d_21__021aafa0), the
   chain ends and script DEXNAV_GOT_AWAY_SCRIPT says so. */
#define DEXNAV_GOT_AWAY_SCRIPT 10145  /* script file 872's entry 15 (patches.dexnav_got_away) */
#define DEXNAV_SCREEN_SCRIPT 10146    /* entry 16 (patches.dexnav_screen) */
#define DEXNAV_NOTHING_SCRIPT 10147   /* entry 17: "There are no Pokémon to search for here." */
#define DEXNAV_NOWHERE_SCRIPT 10148   /* entry 18: "There's nowhere nearby for it to appear..." */
#define DEXNAV_MESSAGE_SCRIPT 10149   /* entry 19: the message sMessage names (patches.dexnav_screen) */
#define MSG_NOT_HERE 1            /* "<species> isn't found around here." */
#define MSG_SURF 2                /* "Look for <species> while surfing." */
#define MSG_LAND 3                /* "Look for <species> away from the water." */
#define MSG_FISHING 4             /* "<species> can only be found by fishing here." */
#define PATCH_FRAMES 600          /* 10 seconds of field time */
#define PAUSE_GAP 4               /* frames between two field frames past which the field was stopped (a menu, a script) */
#define PAUSE_COUNT 2
#define PATCH_NEAR 2
#define PATCH_FAR 4
#define FIELD_MMDLSYS 0x38
#define FIELD_PLAYER 0x8C
#define FIELD_MAPPER 0x48
#define MMdlSys_Player ((void *(*)(void *))(0x0216DEE0 | 1))
#define MMdl_GridX ((u32 (*)(void *))(0x0216D83C | 1))
#define MMdl_GridZ ((u32 (*)(void *))(0x0216D86C | 1))
#define FieldPlayer_GetPos ((void (*)(void *, s32 *))(0x021A3038 | 1))   /* x, y, z, 16.16 */
#define Map_GetAttr ((u32 (*)(void *, const s32 *))(0x021AB0D4 | 1))
#define Event_Script ((u32 (*)(void *, u32, void *, u32))(0x02158768 | 1))
#define FIELD_GSYS 0x04
#define FIELD_ZONE 0x00          /* u16 */

/* a tile attribute: behaviour in the low half, flags in the high half (FUN_overlay_d_21__021aa35c's tests) */
#define ATTR_WATER 0x20000
#define ATTR_ENCOUNTER 0x40000
#define TERRAIN_LAND 0
#define TERRAIN_DARK 1
#define TERRAIN_WATER 2

/* the encounter's effect module: its tile list hangs off the encounter (+0x10), the effect on the map off the game
   data (+8) */
#define ENC_GAMEDATA 0x08
#define ENC_EFFECTS 0x10
#define EFFECTS_COUNT 0x04       /* u16, then 12-byte tiles: u8 kind, s16 x at +2, s16 z at +6, height at +8 */
#define EFFECTS_TILES 0x08
#define EFFECT_TILE_SIZE 12
#define EFFECT_GRASS 0           /* kinds (FUN_overlay_d_21__021ab504): 0 grass, 3 Route 7's long grass, 4 dust, */
#define EFFECT_DUST 4            /* 5 and 6 water, 7 a bridge's shadow, 8 none */
#define EFFECT_NONE 8
#define EFFECT_STATE 0x1D        /* in the game data's effect record: low 4 bits non-zero while one is out */
#define EFFECT_KIND 0x1C         /* and its kind */
#define EFFECT_X 0x12            /* and its tile */
#define EFFECT_Z 0x16
#define Effect_Record ((u8 *(*)(void *))(0x02012A38 | 1))
#define Effect_Collect ((void (*)(void *, u8 *))(0x021AACD4 | 1))
#define Effect_Create ((void (*)(void *, u8 *))(0x021AAE34 | 1))
#define Effect_Clear ((void (*)(void *, u8 *))(0x021AAFA0 | 1))
#define Effect_Kind ((u32 (*)(u32))(0x021AB504 | 1))  /* a tile attribute's kind of effect */

static u8 sPatch;          /* 1 while the search's effect is out */
static u32 sPatchTick;    /* FRAME_COUNTER at the last field frame */
static u32 sPatchTime;    /* field frames since it came out */
static u16 sPatchSpecies;
static u8 sPatchKind;
static volatile s16 sPatchX, sPatchZ;  /* its tile (read by the tests) */
static u8 sGotAway;
static u8 sScanDark;      /* the tile scan is looking for dark grass */

static int IsDark(u32 attr)  /* FUN_overlay_d_21__021ab29c */
{
    u32 behaviour = attr & 0xFFFF;

    return behaviour == 6 || behaviour == 7 || behaviour == 9 || behaviour == 0x22;
}

static u32 PlayerAttr(void *fieldSys)
{
    s32 pos[3];

    FieldPlayer_GetPos(*(void **)((u8 *)fieldSys + FIELD_PLAYER), pos);
    return Map_GetAttr(*(void **)((u8 *)fieldSys + FIELD_MAPPER), pos);
}

static int Terrain(u32 attr)
{
    if (attr & ATTR_WATER)
        return TERRAIN_WATER;
    if ((attr & ATTR_ENCOUNTER) && IsDark(attr))
        return TERRAIN_DARK;
    return TERRAIN_LAND;
}

/* the effect module's scan reads each tile's kind through this (at 0x021AADBC): while DexNav looks for dark
   grass, dark grass counts as grass that can rustle and nothing else counts */
u32 Gunk_DexNav_ScanKind(u32 attr)
{
    if (sScanDark)
        return (attr & ATTR_ENCOUNTER) && IsDark(attr) ? EFFECT_GRASS : EFFECT_NONE;
    return Effect_Kind(attr);
}

static int EffectOut(void *enc)
{
    return Effect_Record(*(void **)((u8 *)enc + ENC_GAMEDATA))[EFFECT_STATE] & 0xF;
}

static int KindFits(u32 kind, int terrain, u32 own)
{
    if (terrain == TERRAIN_WATER)
        return kind == 5 || kind == 6;
    if (terrain == TERRAIN_DARK)
        return kind == EFFECT_GRASS;
    if (own != EFFECT_NONE)
        return kind == own;  /* the same kind as the player's tile: grass, long grass, a cave floor's dust */
    return kind == EFFECT_GRASS || kind == 3 || kind == EFFECT_DUST;  /* off the grass: any nearby */
}

/* start the effect on a tile PATCH_NEAR-PATCH_FAR tiles away that fits the terrain */
static int PlacePatch(void *fieldSys, void *enc)
{
    u8 *effects = *(u8 **)((u8 *)enc + ENC_EFFECTS);
    u8 *player = MMdlSys_Player(*(void **)((u8 *)fieldSys + FIELD_MMDLSYS));
    u32 attr, own;
    s32 px, pz;
    int i, n, terrain, kept = 0;

    if (!effects || !player)
        return 0;
    if (EffectOut(enc))  /* a natural one (with a badge the module spawns them): the search's takes its place */
        Effect_Clear(enc, effects);
    attr = PlayerAttr(fieldSys);
    terrain = Terrain(attr);
    own = Effect_Kind(attr);
    px = MMdl_GridX(player);
    pz = MMdl_GridZ(player);
    sScanDark = terrain == TERRAIN_DARK;
    Effect_Collect(enc, effects);
    sScanDark = 0;
    n = *(u16 *)(effects + EFFECTS_COUNT);
    for (i = 0; i < n; i++) {
        u8 *t = effects + EFFECTS_TILES + i * EFFECT_TILE_SIZE;
        s32 dx = *(s16 *)(t + 2) - px, dz = *(s16 *)(t + 6) - pz;
        s32 d = (dx < 0 ? -dx : dx) + (dz < 0 ? -dz : dz);
        int k;

        if (!KindFits(t[0], terrain, own) || d < PATCH_NEAR || d > PATCH_FAR)
            continue;
        if (kept != i)
            for (k = 0; k < EFFECT_TILE_SIZE; k++)
                effects[EFFECTS_TILES + kept * EFFECT_TILE_SIZE + k] = t[k];
        kept++;
    }
    *(u16 *)(effects + EFFECTS_COUNT) = kept;
    if (!kept)
        return 0;
    Effect_Create(enc, effects);
    if (!EffectOut(enc))
        return 0;
    sPatchX = *(s16 *)(Effect_Record(*(void **)((u8 *)enc + ENC_GAMEDATA)) + EFFECT_X);
    sPatchZ = *(s16 *)(Effect_Record(*(void **)((u8 *)enc + ENC_GAMEDATA)) + EFFECT_Z);
    return 1;
}

/* with the field's per-frame input (field.c): the effect goes after PATCH_FRAMES */
static u32 sBarKey;  /* what the search bar shows (0: no bar) */

void DexNav_FieldStart(void)
{
    sBarKey = 0;
    DexNavUi_BarForget();
}

/* the search bar for the search that is out: its species, search level, the chain it would extend and the perfect
   IVs that link would give (Gunk_DexNav_EffectEncount / Gunk_DexNav_Create) */
static void Bar(void)
{
    u32 chain = sPatchSpecies == sChainSpecies ? sChain : 0, next = chain < CHAIN_MAX ? chain + 1 : chain;
    u32 perfect = next >= 30 ? 3 : next >= 20 ? 2 : next >= 10 ? 1 : 0;
    u32 key = sPatch ? 1 | sPatchSpecies << 1 | (u32)sSearchLevel << 12 | chain << 20 : 0;

    if (key == sBarKey)
        return;
    sBarKey = key;
    if (key)
        DexNavUi_Bar(sPatchSpecies, sSearchLevel, chain, perfect);
    else
        DexNavUi_BarRemove();
}

void DexNav_Frame(void *fieldSys)
{
    void *enc;
    u32 gap;

    /* the start menu shuts the field down (and takes X before this runs): the list for the bag's USE (the
       graphical screen) is kept up to date here, rebuilt when the player is on another tile */
    if (DEXNAV_GRAPHICAL) {
        u8 *player = MMdlSys_Player(*(void **)((u8 *)fieldSys + FIELD_MMDLSYS));
        u32 spot = player ? (u32)*(u16 *)((u8 *)fieldSys + FIELD_ZONE) << 20 ^ MMdl_GridX(player) << 10 ^
                            MMdl_GridZ(player) : 0;

        if (spot != sListSpot) {
            sListSpot = spot;
            DexNav_BuildList(fieldSys);
        }
    }
    if (DEXNAV_GRAPHICAL)
        Bar();
    if (!sPatch)
        return;
    enc = FieldSys_GetEncount(fieldSys);
    if (!EffectOut(enc)) {  /* walked into, or gone with a battle or a new map */
        sPatch = 0;
        return;
    }
    gap = FRAME_COUNTER - sPatchTick;
    sPatchTick = FRAME_COUNTER;
    sPatchTime += gap > PAUSE_GAP ? PAUSE_COUNT : gap;  /* time with the field stopped doesn't count */
    if (sPatchTime >= PATCH_FRAMES) {
        Effect_Clear(enc, *(u8 **)((u8 *)enc + ENC_EFFECTS));
        sPatch = 0;
        sChain = 0;
        sChainSpecies = 0;
        sGotAway = 1;
    }
}

/* the effect module's encounter (stepping into the effect): the search's meets the target */
u32 Gunk_DexNav_EffectEncount(void *enc, u32 type)
{
    u32 started;

    if (!sPatch)
        return Encount_Try(enc, type);
    sPatch = 0;
    sTarget = sPatchSpecies;
    sTargetKind = sPatchKind;
    if (sTarget == sChainSpecies) {
        if (sChain < CHAIN_MAX)
            sChain++;
    } else {
        sChainSpecies = sTarget;
        sChain = 1;
    }
    started = Encount_Try(enc, type);
    if (started)
        DexNav_RaiseLevel(sTarget);
    sTarget = 0;
    return started;
}

/* the effect module's item-or-Pokémon roll (out of 1000, at 0x021AA9AC): a dust cloud gives an item from 400 up
   and a bridge's shadow from 200 up; the search's always holds the Pokémon */
u32 Gunk_DexNav_EffectRoll(u32 range)
{
    return sPatch ? 0 : Random1000(range);
}

/* the spot's list: the species of its normal table, then those only in its rustling or rippling one */
static void BuildList(const u8 *table, int terrain)
{
    static const u8 kinds[3][2] = { { KIND_GRASS, KIND_RUSTLE }, { KIND_DARK, KIND_RUSTLE },
                                    { KIND_SURF, KIND_RIPPLE } };
    int t, i, k;

    sListCount = 0;
    sListTable = table;
    for (t = 0; t < 2; t++) {
        int kind = kinds[terrain][t];

        if (!table[kind])  /* no encounters of that kind here */
            continue;
        for (i = 0; i < sKindSlots[kind] && sListCount < DEXNAV_LIST_MAX; i++) {
            u16 species = SlotSpecies(table, kind, i);

            for (k = 0; k < sListCount && sList[k].species != species; k++)
                ;
            if (!species || k < sListCount)
                continue;
            sList[sListCount].species = species;
            sList[sListCount].kind = kind;
            sListCount++;
        }
    }
}

u32 DexNav_ListCount(void)
{
    return sListCount;
}

u32 DexNav_ListCursor(void)
{
    u32 i;

    for (i = 0; i < sListCount; i++)
        if (sList[i].species == sLastPick)
            return i;
    for (i = 0; i < sListCount; i++)
        if (!Caught(sList[i].species))
            return i;
    return 0;
}

/* the message script's: the species goes in buffer 0, the result says which message */
u32 DexNav_Message(void *ws)
{
    u32 msg = sMessage;

    sMessage = 0;
    WordSet_SpeciesName(ws, 0, sMessageSpecies);
    return msg;
}

u32 DexNav_ListSpecies(u32 i)
{
    return i < sListCount ? sList[i].species : 0;
}

u32 DexNav_ListMark(u32 i)
{
    u16 species = DexNav_ListSpecies(i);

    if (!species)
        return 0;
    return Caught(species) ? 3 : Seen(species) ? 2 : 1;
}

u32 DexNav_ListEntry(u32 i, void *ws)
{
    if (i >= sListCount)
        return 0;
    WordSet_SpeciesName(ws, 0, sList[i].species);
    return DexNav_ListMark(i);
}

u32 DexNav_ListPick(u32 i)
{
    if (i >= sListCount)
        return 0;  /* B */
    if (!Seen(sList[i].species))
        return 2;  /* only Pokémon you've seen can be searched for */
    sPick = i + 1;
    return 1;
}

/* why the registered species can't be searched for at this spot (MSG_*): it lives on the other terrain here, only
   in the fishing tables, or not here at all */
static int NotHere(const u8 *table, int terrain, u16 species)
{
    int kind, i;

    if (!table)
        return MSG_NOT_HERE;
    for (kind = 0; kind < ENC_KINDS; kind++)
        for (i = 0; i < sKindSlots[kind]; i++)
            if (table[kind] && SlotSpecies(table, kind, i) == species && kind < 5)
                return kind >= KIND_SURF ? MSG_SURF : terrain == TERRAIN_WATER ? MSG_LAND : MSG_NOT_HERE;
    for (kind = 5; kind < ENC_KINDS; kind++)
        for (i = 0; i < sKindSlots[kind]; i++)
            if (table[kind] && SlotSpecies(table, kind, i) == species)
                return MSG_FISHING;
    return MSG_NOT_HERE;
}

/* the list for the player's spot (none where the zone has no wild Pokémon); the spot's terrain */
static int SpotList(const u8 *table, void *fieldSys)
{
    int terrain;

    if (!table) {
        sListCount = 0;
        return TERRAIN_LAND;
    }
    terrain = Terrain(PlayerAttr(fieldSys));
    BuildList(table, terrain);
    return terrain;
}

/* the bag's USE on the DexNav: the screen, as L+R opens it (a pick starts the search once the field runs again) */
u32 DexNav_BuildList(void *fieldSys)
{
    const u8 *table = *(const u8 **)((u8 *)FieldSys_GetEncount(fieldSys) + 0xC);

    SpotList(table && (table[7] & ENC_LOADED) ? table : 0, fieldSys);
    return sListCount;
}

u32 DexNav_ItemEvent(void *fieldSys)
{
    return Event_Script(*(void **)((u8 *)fieldSys + FIELD_GSYS),
                        DexNav_BuildList(fieldSys) ? DEXNAV_SCREEN_SCRIPT : DEXNAV_NOTHING_SCRIPT,
                        0, *(u16 *)((u8 *)fieldSys + FIELD_ZONE));
}

/* the graphical screen's pick (dexnav_ui.c): the menu closes through this event, the message script with no message
   pending, and the search starts once the field runs again */
u32 DexNav_PickEvent(void *fieldSys)
{
    sMessage = 0;
    return Event_Script(*(void **)((u8 *)fieldSys + FIELD_GSYS), DEXNAV_MESSAGE_SCRIPT, 0,
                        *(u16 *)((u8 *)fieldSys + FIELD_ZONE));
}

u32 Gunk_StepEncount(void *state, void *x, void *fieldSys)
{
    void *enc = FieldSys_GetEncount(fieldSys);
    const u8 *table = *(const u8 **)((u8 *)enc + 0xC);
    void *gsys = *(void **)((u8 *)fieldSys + FIELD_GSYS);
    u16 zone = *(u16 *)((u8 *)fieldSys + FIELD_ZONE);
    int terrain = TERRAIN_LAND;
    u32 request;

    if (sGotAway) {
        sGotAway = 0;
        return Event_Script(gsys, DEXNAV_GOT_AWAY_SCRIPT, 0, zone);
    }
    if (sPick) {
        struct ListEntry *e = &sList[sPick - 1];

        sPick = 0;
        if (sPatch || table != sListTable)
            return StepEncount(state, x, fieldSys);
        sPatchSpecies = e->species;
        sPatchKind = e->kind;
        sLastPick = e->species;
        if (!PlacePatch(fieldSys, enc))
            return Event_Script(gsys, DEXNAV_NOWHERE_SCRIPT, 0, zone);
        sPatch = 1;
        sPatchTick = FRAME_COUNTER;
        sPatchTime = 0;
        sSearchLevel = DexNav_Level(e->species);
        return StepEncount(state, x, fieldSys);
    }
    if (!sRequested)
        return StepEncount(state, x, fieldSys);
    request = sRequested;
    sRequested = 0;
    if (sPatch)  /* one search at a time */
        return StepEncount(state, x, fieldSys);
    if (table && !(table[7] & ENC_LOADED))
        table = 0;
    terrain = SpotList(table, fieldSys);
    /* R searches for the registered Pokémon at once; L+R, or R with none registered, opens the screen */
    if (request == 1 && sLastPick) {
        u32 i;

        for (i = 0; i < sListCount && sList[i].species != sLastPick; i++)
            ;
        if (i < sListCount) {
            sPick = i + 1;
            return Gunk_StepEncount(state, x, fieldSys);
        }
        sMessage = NotHere(table, terrain, sLastPick);
        sMessageSpecies = sLastPick;
        return Event_Script(gsys, DEXNAV_MESSAGE_SCRIPT, 0, zone);
    }
    if (DEXNAV_GRAPHICAL && sListCount)
        return (u32)DexNavUi_FieldEvent(gsys, fieldSys);
    return Event_Script(gsys, sListCount ? DEXNAV_SCREEN_SCRIPT : DEXNAV_NOTHING_SCRIPT, 0, zone);
}

/* one of the target's slots in its table, with the table's slot odds (each slot has its own level) */
static int TargetSlot(const u8 *table, int kind, u16 species)
{
    const u8 *rate = sKindSlots[kind] == 12 ? sLandRate : sWaterRate;
    u32 total = 0, roll;
    int i;

    for (i = 0; i < sKindSlots[kind]; i++)
        if (SlotSpecies(table, kind, i) == species)
            total += rate[i];
    if (!total)
        return -1;
    roll = Random() * total >> 16;  /* Random() is 16 bits */
    for (i = 0; i < sKindSlots[kind]; i++) {
        if (SlotSpecies(table, kind, i) != species)
            continue;
        if (roll < rate[i])
            return i;
        roll -= rate[i];
    }
    return -1;
}

u32 Gunk_DexNav_PickSlots(const u8 *table, void *params, void *x, struct EncRecord *out)
{
    u32 found = Encount_PickSlots(table, params, x, out);
    int i;

    if (!found || !sTarget)
        return found;
    i = TargetSlot(table, sTargetKind, sTarget);
    if (i >= 0) {  /* as FUN_overlay_d_21__021a9c58 does with the slot it rolled */
        const struct EncSlot *slots = Slots(table, sTargetKind);

        Encount_SlotRecord(slots + i, &out[0]);
        Encount_LeadLevel(params, slots, &out[0]);
    }
    return found;
}

static int Shiny(u32 pid, u32 id)
{
    return ((id >> 16) ^ (id & 0xFFFF) ^ (pid >> 16) ^ (pid & 0xFFFF)) < 8;
}

/* params + 0x20 holds the trainer ID (low half) and secret ID (high half) */
u32 Gunk_DexNav_Pid(u8 *params, void *personal, struct EncRecord *rec)
{
    u32 pid = Encount_RollPid(params, personal, rec);
    u32 id = *(u32 *)(params + 0x20);
    int n;

    if (sTarget && rec->species == sTarget)
        for (n = 0; n < sChain + (sSearchLevel * 205 >> 11) && !Shiny(pid, id); n++)  /* level / 10 */
            pid = Encount_RollPid(params, personal, rec);
    return pid;
}

/* the best of the game's IVs and search level / 2 more random sets (the highest total) */
static int BestIVs(void *pp)
{
    u8 best[6];
    int stat, n, total = 0, changed = 0;

    for (stat = 0; stat < 6; stat++) {
        best[stat] = PP_Get(pp, PARAM_IV_HP + stat, 0);
        total += best[stat];
    }
    for (n = 0; n < sSearchLevel / 2; n++) {
        u8 ivs[6];
        int sum = 0;

        for (stat = 0; stat < 6; stat++) {
            ivs[stat] = Random() & IV_MAX;
            sum += ivs[stat];
        }
        if (sum <= total)
            continue;
        total = sum;
        changed = 1;
        for (stat = 0; stat < 6; stat++)
            best[stat] = ivs[stat];
    }
    if (changed)
        for (stat = 0; stat < 6; stat++)
            PP_Put(pp, PARAM_IV_HP + stat, best[stat]);
    return changed;
}

void Gunk_DexNav_Create(void *pp, void *params, struct EncRecord *rec)
{
    int perfect, set = 0, changed;

    Encount_CreateMon(pp, params, rec);
    if (!sTarget || rec->species != sTarget) {
        /* any other wild encounter: one of the chain's species keeps the chain, any other species ends it */
        if (rec->species != sChainSpecies) {
            sChain = 0;
            sChainSpecies = 0;
        }
        return;
    }
    changed = BestIVs(pp);
    perfect = sChain >= 30 ? 3 : sChain >= 20 ? 2 : sChain >= 10 ? 1 : 0;
    while (perfect) {
        u32 stat = Random() & 7;

        if (stat >= 6 || (set >> stat) & 1)
            continue;
        set |= 1 << stat;
        PP_Put(pp, PARAM_IV_HP + stat, IV_MAX);
        perfect--;
        changed = 1;
    }
    if (changed)
        PP_CalcStats(pp);  /* the game worked the stats out from the old IVs */
}

u32 Gunk_DexNav_BattleResult(void *param)
{
    u32 result = BattleParam_GetResult(param);

    if (result == BTL_RESULT_RUN) {
        sChain = 0;
        sChainSpecies = 0;
    }
    return result;
}
