/* HM moves without the move: a Pokémon can use Cut, Fly, Surf, Strength, Waterfall or Dive in the field if it knows
   it, or if the bag holds that HM and the Pokémon could learn it. Badges still apply (the scripts check them).
   Replaces FUN_overlay_d_10__0215b500, the "does it know this move" test behind the field-move script commands
   and the field's own check. */
#include "gunk.h"

#define HM_COUNT 6
#define ITEM_HM01 420
#define SPECIES_COUNT 650

#define PARAM_SPECIES 5
#define PARAM_MOVE1 0x36  /* 0x36-0x39 */
#define PARAM_IS_EGG 76

#define SAVE_BLOCK_BAG 25
#define BAG_TMS 0x624     /* the TMs & HMs pocket: {u16 item, u16 count} x 109 */
#define BAG_TMS_SLOTS 109

#define PP_Get ((u32 (*)(void *, u32, u32))(0x02017E1C | 1))
#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)

static const u16 sHmMoves[HM_COUNT] = { 15, 19, 57, 70, 127, 291 };  /* Cut, Fly, Surf, Strength, Waterfall, Dive */

extern const u8 gGunkHmCompat[SPECIES_COUNT];  /* hmcompat.c */

static int HasHm(int hm)
{
    const u16 *slot = (const u16 *)(SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_BAG) + BAG_TMS);
    int i;

    for (i = 0; i < BAG_TMS_SLOTS; i++)
        if (slot[i * 2] == ITEM_HM01 + hm && slot[i * 2 + 1])
            return 1;
    return 0;
}

u32 Gunk_KnowsFieldMove(void *pp, u16 move)
{
    u32 species;
    int i;

    if (PP_Get(pp, PARAM_IS_EGG, 0))
        return 0;
    for (i = 0; i < 4; i++)
        if (PP_Get(pp, PARAM_MOVE1 + i, 0) == move)
            return 1;
    for (i = 0; i < HM_COUNT; i++)
        if (sHmMoves[i] == move)
            break;
    if (i == HM_COUNT || !HasHm(i))
        return 0;
    species = PP_Get(pp, PARAM_SPECIES, 0);
    return species < SPECIES_COUNT && (gGunkHmCompat[species] >> i) & 1;
}
