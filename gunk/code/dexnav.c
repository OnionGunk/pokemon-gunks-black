/* DexNav: R in tall grass searches for one Pokémon of this route and meets it right away. The target is the first
   species of the route you haven't caught; it stays the target until you switch with L+R (the next species of the
   route). Searching for the same species again and again builds a chain: each link rerolls the personality value
   once more for a shiny (up to 40), and chains of 10, 20 and 30 give 1, 2 and 3 perfect IVs. Encounters stay
   legal: species, form and level come from the route's own grass slot, the game generates the Pokémon as for any
   wild one, and a Gen 5 personality value is an independent random number.

   Field overlay (21):
   - DexNav_Input runs with the field's per-frame input (field.c) and notes R (and L).
   - Gunk_StepEncount wraps the per-frame step-encounter check (FUN_overlay_d_21__0218b208), whose result tells
     the field to start the battle: with R noted it tries a forced encounter the way Sweet Scent does
     (FUN_overlay_d_21__021a9f40, type 1), which only succeeds where wild Pokémon live.
   - Gunk_DexNav_PickSlots wraps that encounter's slot pick and puts the target in the first record.
   - Gunk_DexNav_Pid wraps the personality-value roll (FUN_overlay_d_21__021a9d30) and Gunk_DexNav_Create the
     building of the wild Pokémon (FUN_overlay_d_21__021a96b8). */
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
#define Encount_RollPid ((u32 (*)(u8 *, void *, struct EncRecord *))(0x021A9D30 | 1))
#define Encount_CreateMon ((void (*)(void *, void *, struct EncRecord *))(0x021A96B8 | 1))
#define PP_Put ((void (*)(void *, u32, u32))(0x02017E40 | 1))
#define Key_GetTrg ((u32 (*)(void))0x020362DC)
#define Key_GetCont ((u32 (*)(void))0x0203630C)
#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)

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

u32 Gunk_StepEncount(void *state, void *x, void *fieldSys)
{
    void *enc;
    const u8 *table;
    u32 started = 0;
    int switchTarget = sRequested == 2;

    if (!sRequested)
        return StepEncount(state, x, fieldSys);
    sRequested = 0;
    enc = FieldSys_GetEncount(fieldSys);
    table = *(const u8 **)((u8 *)enc + 0xC);
    if (table && (table[7] & ENC_LOADED)) {
        sTarget = ChooseTarget(table, switchTarget);
        if (sTarget) {
            if (sTarget == sChainSpecies) {
                if (sChain < CHAIN_MAX)
                    sChain++;
            } else {
                sChainSpecies = sTarget;
                sChain = 1;
            }
            started = Encount_Try(enc, 1);
        }
        sTarget = 0;
    }
    return started ? started : StepEncount(state, x, fieldSys);
}

u32 Gunk_DexNav_PickSlots(const u8 *table, void *params, void *x, struct EncRecord *out)
{
    u32 found = Encount_PickSlots(table, params, x, out);
    int i;

    if (!found || !sTarget)
        return found;
    i = SlotOf(table, sTarget);
    if (i >= 0) {
        const struct EncSlot *slot = (const struct EncSlot *)(table + ENC_GRASS) + i;

        out[0].species = sTarget;
        out[0].form = slot->species >> 11;
        out[0].level = slot->min;
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
    if (!sTarget || rec->species != sTarget)
        return;
    perfect = sChain >= 30 ? 3 : sChain >= 20 ? 2 : sChain >= 10 ? 1 : 0;
    while (perfect) {
        u32 stat = Random() & 7;

        if (stat >= 6 || (set >> stat) & 1)
            continue;
        set |= 1 << stat;
        PP_Put(pp, PARAM_IV_HP + stat, IV_MAX);
        perfect--;
    }
}
