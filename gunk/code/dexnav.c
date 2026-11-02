/* DexNav (first version): R in tall grass searches for a Pokémon from this route that you haven't caught yet, and
   meets it right away. Encounters stay legal: species, form and level come from one of the route's own grass
   slots, and the game generates the Pokémon as for any wild one.

   Field overlay (21):
   - Gunk_FieldInput wraps the field's per-frame input routine (FUN_overlay_d_21__021a2df0, called through a
     table) and notes R.
   - Gunk_StepEncount wraps the per-frame step-encounter check (FUN_overlay_d_21__0218b208), whose result tells
     the field to start the battle: with R noted it tries a forced encounter the way Sweet Scent does
     (FUN_overlay_d_21__021a9f40, type 1), which only succeeds where wild Pokémon live.
   - Gunk_DexNav_PickSlots wraps that encounter's slot pick and, during a search, puts the target in the first
     record. */
#include "gunk.h"

#define PAD_R 0x0100

#define ENC_GRASS 8          /* the zone's encounter table (a/1/2/6, 232 bytes): rates, then 4-byte slots */
#define ENC_DARK_GRASS 0x38
#define ENC_SLOTS 12
#define ENC_LOADED 0x80      /* byte 7 */

#define SAVE_BLOCK_DEX 55
#define DEX_CAUGHT 0x08      /* one bit per species, from #1 */

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

#define FieldInput ((void (*)(void *))(0x021A2DF0 | 1))
#define StepEncount ((u32 (*)(void *, void *, void *))(0x0218B208 | 1))
#define FieldSys_GetEncount ((void *(*)(void *))(0x02188CE8 | 1))
#define Encount_Try ((u32 (*)(void *, u32))(0x021A9F40 | 1))
#define Encount_PickSlots ((u32 (*)(const u8 *, void *, void *, struct EncRecord *))(0x021A954C | 1))
#define Key_GetTrg ((u32 (*)(void))0x020362DC)
#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)

static u16 sTarget;       /* species being searched for (0: no search running) */
static u8 sRequested;     /* R was pressed */
static u8 sNext;          /* where the next pick starts, so every species on the route comes up in turn */

static int Caught(u32 species)
{
    const u8 *dex = SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_DEX) + DEX_CAUGHT;

    return species && (dex[(species - 1) / 8] >> ((species - 1) % 8)) & 1;
}

static const struct EncSlot *Slots(const u8 *table)
{
    return (const struct EncSlot *)(table + ENC_GRASS);
}

/* the first grass species (from sNext) not caught yet; if all are, simply the next one */
static u16 PickTarget(const u8 *table)
{
    const struct EncSlot *slot = Slots(table);
    int i, fallback = -1;

    for (i = 0; i < ENC_SLOTS; i++) {
        int k = sNext + i >= ENC_SLOTS ? sNext + i - ENC_SLOTS : sNext + i;
        u16 species = slot[k].species & 0x7FF;

        if (!species)
            continue;
        if (fallback < 0)
            fallback = k;
        if (!Caught(species)) {
            sNext = k + 1 == ENC_SLOTS ? 0 : k + 1;
            return species;
        }
    }
    if (fallback < 0)
        return 0;
    sNext = fallback + 1 == ENC_SLOTS ? 0 : fallback + 1;
    return slot[fallback].species & 0x7FF;
}

void Gunk_FieldInput(void *fieldSys)
{
    if (Key_GetTrg() & PAD_R)
        sRequested = 1;
    FieldInput(fieldSys);
}

u32 Gunk_StepEncount(void *state, void *x, void *fieldSys)
{
    void *enc;
    const u8 *table;
    u32 started = 0;

    if (!sRequested)
        return StepEncount(state, x, fieldSys);
    sRequested = 0;
    enc = FieldSys_GetEncount(fieldSys);
    table = *(const u8 **)((u8 *)enc + 0xC);
    if (table && (table[7] & ENC_LOADED)) {
        sTarget = PickTarget(table);
        if (sTarget)
            started = Encount_Try(enc, 1);
        sTarget = 0;
    }
    return started ? started : StepEncount(state, x, fieldSys);
}

u32 Gunk_DexNav_PickSlots(const u8 *table, void *params, void *x, struct EncRecord *out)
{
    u32 found = Encount_PickSlots(table, params, x, out);
    const struct EncSlot *slot;
    int i;

    if (!found || !sTarget)
        return found;
    slot = Slots(table);
    for (i = 0; i < ENC_SLOTS; i++)
        if ((slot[i].species & 0x7FF) == sTarget) {
            out[0].species = sTarget;
            out[0].form = slot[i].species >> 11;
            out[0].level = slot[i].min;
            break;
        }
    return found;
}
