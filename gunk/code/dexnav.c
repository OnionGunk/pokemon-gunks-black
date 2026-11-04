/* DexNav: R in tall grass searches for one Pokémon of this route: a patch of grass nearby shakes, and walking up to
   it within 10 seconds meets the Pokémon. The target is the first
   species of the route you haven't caught; it stays the target until you switch with L+R (the next species of the
   route). Searching for the same species again and again builds a chain (a wild encounter with another species
   ends it, one with the chain's species keeps it, and running from a wild battle ends it): each link rerolls the
   personality value once more for a shiny (up to 40), and chains of 10, 20 and 30 give 1, 2 and 3 perfect IVs.
   Encounters stay legal: one of the target's grass slots (with the slots' own odds, as each has its own level) is made into the
   encounter by the game's own code (level from the slot's range,
   its form rule, the lead's Pressure/Hustle/Vital Spirit level boost), the game generates the Pokémon as for any
   wild one, and a Gen 5 personality value is an independent random number (shininess comes from it alone, so the
   IVs set afterwards can't change it).

   Field overlay (21):
   - DexNav_Input runs with the field's per-frame input (field.c) and notes R (and L).
   - Gunk_StepEncount wraps the per-frame step-encounter check (FUN_overlay_d_21__0218b208): with R noted it starts
     Black's own shaking grass near the player (see PlacePatch).
   - Gunk_DexNav_EffectEncount wraps the shaking grass's encounter, the one Sweet Scent uses
     (FUN_overlay_d_21__021a9f40, type 1), and makes the search's meet the target.
   - Gunk_DexNav_PickSlots wraps that encounter's slot pick and puts the target in the first record.
   - Gunk_DexNav_Pid wraps the personality-value roll (FUN_overlay_d_21__021a9d30) and Gunk_DexNav_Create the
     building of the wild Pokémon (FUN_overlay_d_21__021a96b8).
   Script overlay (10):
   - Gunk_DexNav_BattleResult wraps the wild battle event's read of the battle's result (FUN_02012a44, at
     0x0216E744) and ends the chain when the player ran. */
#include "gunk.h"

#define PAD_R 0x0100
#define PAD_L 0x0200

#define ENC_GRASS 8          /* the zone's encounter table (a/1/2/6, 232 bytes): rates, then 4-byte slots */
#define ENC_SLOTS 12
#define ENC_LOADED 0x80      /* byte 7 */

#define SAVE_BLOCK_DEX 55
#define DEX_CAUGHT 0x08      /* one bit per species, from #1 */

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
#define PP_Put ((void (*)(void *, u32, u32))(0x02017E40 | 1))
#define PP_CalcStats ((void (*)(void *))(0x02018A7C | 1))  /* stats (and HP) from level, IVs, EVs, nature */
#define Key_GetTrg ((u32 (*)(void))0x020362DC)
#define Key_GetCont ((u32 (*)(void))0x0203630C)
#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)
#define BattleParam_GetResult ((u32 (*)(void *))(0x02012A44 | 1))
#define BTL_RESULT_RUN 3     /* 0 lost, 1 won, 3 ran, 5 caught */

static u16 sTarget;       /* species being searched for right now (0: no search running) */
static u16 sCurrent;      /* the route's chosen target */
static const u8 *sTable;  /* the route sCurrent belongs to */
static u8 sRequested;     /* R was pressed; 2 with L held */
static u16 sChainSpecies;
static u8 sChain;
static u32 sRand;

static int Caught(u32 species)
{
    const u8 *dex = SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_DEX) + DEX_CAUGHT;

    return species && (dex[(species - 1) / 8] >> ((species - 1) % 8)) & 1;
}

static u16 SlotSpecies(const u8 *table, int i)
{
    return ((const struct EncSlot *)(table + ENC_GRASS))[i].species & 0x7FF;
}

static int SlotOf(const u8 *table, u16 species)
{
    int i;

    for (i = 0; i < ENC_SLOTS; i++)
        if (species && SlotSpecies(table, i) == species)
            return i;
    return -1;
}

/* the route's species after `species` (slot order, skipping repeats), wrapping round */
static u16 NextSpecies(const u8 *table, u16 species)
{
    int start = SlotOf(table, species), i;

    for (i = 1; i <= ENC_SLOTS; i++) {
        int k = start + i >= ENC_SLOTS ? start + i - ENC_SLOTS : start + i;
        u16 next;

        if (k < 0)
            k += ENC_SLOTS;
        next = SlotSpecies(table, k);
        if (next && SlotOf(table, next) == k && next != species)
            return next;
    }
    return SlotOf(table, species) >= 0 ? species : 0;
}

static u16 FirstUncaught(const u8 *table)
{
    int i;

    for (i = 0; i < ENC_SLOTS; i++)
        if (SlotSpecies(table, i) && !Caught(SlotSpecies(table, i)))
            return SlotSpecies(table, i);
    return SlotSpecies(table, 0);
}

static u16 ChooseTarget(const u8 *table, int switchTarget)
{
    if (table != sTable || SlotOf(table, sCurrent) < 0) {
        sTable = table;
        sCurrent = FirstUncaught(table);
    } else if (switchTarget) {
        sCurrent = NextSpecies(table, sCurrent);
    }
    return sCurrent;
}

static u32 Random(void)
{
    sRand = sRand * 0x41C64E6D + 0x6073 + FRAME_COUNTER;
    return sRand >> 16;
}

/* with the field's per-frame input (field.c) */
void DexNav_Input(void)
{
    if (Key_GetTrg() & PAD_R)
        sRequested = (Key_GetCont() & PAD_L) ? 2 : 1;
}

/* The search's shaking grass is Black's own (its "effect_encount" module, overlay 21, the one that makes grass
   rustle every so often): R fills the module's list of candidate tiles around the player
   (FUN_overlay_d_21__021aacd4), keeps those 2-4 tiles away in the same kind of grass as the player's, and lets the
   module pick one and start the effect there (FUN_overlay_d_21__021aae34), sound and all. Stepping into it runs the
   module's own encounter (FUN_overlay_d_21__021aa944, which calls the Sweet Scent encounter, type 1, at 0x021AA9EA:
   Gunk_DexNav_EffectEncount wraps that call and makes it the target). After PATCH_FRAMES the effect is cleared
   (FUN_overlay_d_21__021aafa0), the chain ends and script DEXNAV_GOT_AWAY_SCRIPT says so. */
#define DEXNAV_GOT_AWAY_SCRIPT 10145  /* script file 872's entry 15 (patches.dexnav_got_away) */
#define PATCH_FRAMES 600
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

/* the encounter's effect module: its tile list hangs off the encounter (+0x10), the effect on the map off the game
   data (+8) */
#define ENC_GAMEDATA 0x08
#define ENC_EFFECTS 0x10
#define EFFECTS_COUNT 0x04       /* u16, then 12-byte tiles: u8 kind, s16 x at +2, s16 z at +6 */
#define EFFECTS_TILES 0x08
#define EFFECT_TILE_SIZE 12
#define EFFECT_NONE 8            /* the kind of a tile with no effect */
#define EFFECT_STATE 0x1D        /* in the game data's effect record: low 4 bits non-zero while one is out */
#define Effect_Record ((u8 *(*)(void *))(0x02012A38 | 1))
#define Effect_Collect ((void (*)(void *, u8 *))(0x021AACD4 | 1))
#define Effect_Create ((void (*)(void *, u8 *))(0x021AAE34 | 1))
#define Effect_Clear ((void (*)(void *, u8 *))(0x021AAFA0 | 1))
#define Effect_Kind ((u32 (*)(u32))(0x021AB504 | 1))  /* a tile attribute's kind of effect */

static u8 sPatch;          /* 1 while the search's shaking grass is out */
static u32 sPatchStart;   /* FRAME_COUNTER when it came out */
static u16 sPatchSpecies;
static u8 sGotAway;

static int EffectOut(void *enc)
{
    return Effect_Record(*(void **)((u8 *)enc + ENC_GAMEDATA))[EFFECT_STATE] & 0xF;
}

/* start the shaking grass on a tile PATCH_NEAR-PATCH_FAR tiles away in the same kind of grass as the player's */
static int PlacePatch(void *fieldSys, void *enc)
{
    u8 *effects = *(u8 **)((u8 *)enc + ENC_EFFECTS);
    u8 *player = MMdlSys_Player(*(void **)((u8 *)fieldSys + FIELD_MMDLSYS));
    s32 pos[3], px, pz;
    u32 kind;
    int i, n, kept = 0;

    if (!effects || !player || EffectOut(enc))
        return 0;
    FieldPlayer_GetPos(*(void **)((u8 *)fieldSys + FIELD_PLAYER), pos);
    kind = Effect_Kind(Map_GetAttr(*(void **)((u8 *)fieldSys + FIELD_MAPPER), pos));
    if (kind == EFFECT_NONE)
        return 0;  /* not in grass that can shake */
    px = MMdl_GridX(player);
    pz = MMdl_GridZ(player);
    Effect_Collect(enc, effects);
    n = *(u16 *)(effects + EFFECTS_COUNT);
    for (i = 0; i < n; i++) {
        u8 *t = effects + EFFECTS_TILES + i * EFFECT_TILE_SIZE;
        s32 dx = *(s16 *)(t + 2) - px, dz = *(s16 *)(t + 6) - pz;
        s32 d = (dx < 0 ? -dx : dx) + (dz < 0 ? -dz : dz);
        int k;

        if (t[0] != kind || d < PATCH_NEAR || d > PATCH_FAR)
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
    return EffectOut(enc);
}

/* with the field's per-frame input (field.c): the shaking grass goes after PATCH_FRAMES */
void DexNav_Frame(void *fieldSys)
{
    void *enc;

    if (!sPatch)
        return;
    enc = FieldSys_GetEncount(fieldSys);
    if (!EffectOut(enc)) {  /* walked into, or gone with a battle or a new map */
        sPatch = 0;
        return;
    }
    if (FRAME_COUNTER - sPatchStart >= PATCH_FRAMES) {
        Effect_Clear(enc, *(u8 **)((u8 *)enc + ENC_EFFECTS));
        sPatch = 0;
        sChain = 0;
        sChainSpecies = 0;
        sGotAway = 1;
    }
}

/* the effect module's encounter (stepping into shaking grass): the search's meets the target */
u32 Gunk_DexNav_EffectEncount(void *enc, u32 type)
{
    u32 started;

    if (!sPatch)
        return Encount_Try(enc, type);
    sPatch = 0;
    sTarget = sPatchSpecies;
    if (sTarget == sChainSpecies) {
        if (sChain < CHAIN_MAX)
            sChain++;
    } else {
        sChainSpecies = sTarget;
        sChain = 1;
    }
    started = Encount_Try(enc, type);
    sTarget = 0;
    return started;
}

u32 Gunk_StepEncount(void *state, void *x, void *fieldSys)
{
    void *enc = FieldSys_GetEncount(fieldSys);
    const u8 *table = *(const u8 **)((u8 *)enc + 0xC);
    int switchTarget = sRequested == 2;

    if (sGotAway) {
        sGotAway = 0;
        return Event_Script(*(void **)((u8 *)fieldSys + FIELD_GSYS), DEXNAV_GOT_AWAY_SCRIPT, 0,
                            *(u16 *)((u8 *)fieldSys + FIELD_ZONE));
    }
    if (!sRequested)
        return StepEncount(state, x, fieldSys);
    sRequested = 0;
    if (!sPatch && table && (table[7] & ENC_LOADED)) {
        sPatchSpecies = ChooseTarget(table, switchTarget);
        if (sPatchSpecies && PlacePatch(fieldSys, enc)) {
            sPatch = 1;
            sPatchStart = FRAME_COUNTER;
        }
    }
    return StepEncount(state, x, fieldSys);
}

/* one of the target's grass slots, with the slots' own odds (each slot has its own level) */
static int TargetSlot(const u8 *table, u16 species)
{
    static const u8 rate[ENC_SLOTS] = { 20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1 };
    u32 total = 0, roll;
    int i;

    for (i = 0; i < ENC_SLOTS; i++)
        if (SlotSpecies(table, i) == species)
            total += rate[i];
    if (!total)
        return -1;
    roll = Random() * total >> 16;  /* Random() is 16 bits */
    for (i = 0; i < ENC_SLOTS; i++) {
        if (SlotSpecies(table, i) != species)
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
    i = TargetSlot(table, sTarget);
    if (i >= 0) {  /* as FUN_overlay_d_21__021a9c58 does with the slot it rolled */
        const struct EncSlot *slots = (const struct EncSlot *)(table + ENC_GRASS);

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
        for (n = 0; n < sChain && !Shiny(pid, id); n++)
            pid = Encount_RollPid(params, personal, rec);
    return pid;
}

void Gunk_DexNav_Create(void *pp, void *params, struct EncRecord *rec)
{
    int perfect, set = 0;

    Encount_CreateMon(pp, params, rec);
    if (!sTarget || rec->species != sTarget) {
        /* any other wild encounter: one of the chain's species keeps the chain, any other species ends it */
        if (rec->species != sChainSpecies) {
            sChain = 0;
            sChainSpecies = 0;
        }
        return;
    }
    perfect = sChain >= 30 ? 3 : sChain >= 20 ? 2 : sChain >= 10 ? 1 : 0;
    if (!perfect)
        return;
    while (perfect) {
        u32 stat = Random() & 7;

        if (stat >= 6 || (set >> stat) & 1)
            continue;
        set |= 1 << stat;
        PP_Put(pp, PARAM_IV_HP + stat, IV_MAX);
        perfect--;
    }
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
