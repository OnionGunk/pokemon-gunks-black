/* HM moves without the move: a Pokémon can use Cut, Fly, Surf, Strength, Waterfall or Dive in the field if it knows
   it, or if the bag holds that HM and the Pokémon could learn it. Badges still apply (the scripts check them).
   Replaces FUN_overlay_d_10__0215b500, the "does it know this move" test behind the field-move script commands
   and the field's own check. The party menu (overlay 91) lists such moves too: its field-move entries are move
   slots 0-3, as entries 0x10 + slot (FUN_overlay_d_91__021b99e4 maps a slot to a field skill), so
   Gunk_PartyFieldSkill adds slots 6-11 for HM01-06 (entries 0x16-0x1B: 0x14 and 0x15 are other menu actions),
   while the Pokémon has fewer than four field moves listed. */
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
static const u8 sHmSkills[HM_COUNT] = { 0x0B, 0x0F, 0x0C, 0x0E, 0x0D, 0x15 };  /* the party menu's skill ids */

#define PartyMenu_FieldSkill ((u32 (*)(void *, u32))(0x021B99E4 | 1))  /* overlay 91 */
#define MOVE_SLOTS 4
#define HM_SLOTS 6  /* the party menu's pseudo slots for HM01-06 start here */
#define MENU_FIELD_MOVES_MAX 4

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

static int Knows(void *pp, u16 move)
{
    int i;

    for (i = 0; i < MOVE_SLOTS; i++)
        if (PP_Get(pp, PARAM_MOVE1 + i, 0) == move)
            return 1;
    return 0;
}

/* can use HM `hm` without knowing it: the bag holds it and the species can learn it */
static int CanUseHm(void *pp, int hm)
{
    u32 species = PP_Get(pp, PARAM_SPECIES, 0);

    return HasHm(hm) && species < SPECIES_COUNT && (gGunkHmCompat[species] >> hm) & 1;
}

u32 Gunk_KnowsFieldMove(void *pp, u16 move)
{
    int i;

    if (PP_Get(pp, PARAM_IS_EGG, 0))
        return 0;
    if (Knows(pp, move))
        return 1;
    for (i = 0; i < HM_COUNT; i++)
        if (sHmMoves[i] == move)
            return CanUseHm(pp, i);
    return 0;
}

static int ListsHm(void *pp, int hm)
{
    return !PP_Get(pp, PARAM_IS_EGG, 0) && !Knows(pp, sHmMoves[hm]) && CanUseHm(pp, hm);
}

/* the party menu names a field-move entry after the move in its slot (FUN_overlay_d_91__021bbd98 reads move
   parameter 0x36 + slot): for slots 6-11, the HM's move */
u32 Gunk_PartyEntryMove(void *pp, u32 param, u32 arg)
{
    if (param >= PARAM_MOVE1 + HM_SLOTS && param < PARAM_MOVE1 + HM_SLOTS + HM_COUNT)
        return sHmMoves[param - PARAM_MOVE1 - HM_SLOTS];
    return PP_Get(pp, param, arg);
}

/* replaces the party menu's calls to FUN_overlay_d_91__021b99e4: slots 6-11 are HM01-06 */
u32 Gunk_PartyFieldSkill(void *pp, u32 slot)
{
    int listed = 0, i, hm = slot - HM_SLOTS;

    if (slot < MOVE_SLOTS)
        return PartyMenu_FieldSkill(pp, slot);
    if (hm < 0 || hm >= HM_COUNT || !ListsHm(pp, hm))
        return 0;
    for (i = 0; i < MOVE_SLOTS; i++)
        listed += PartyMenu_FieldSkill(pp, i) != 0;
    for (i = 0; i < hm; i++)
        listed += ListsHm(pp, i);
    return listed < MENU_FIELD_MOVES_MAX ? sHmSkills[hm] : 0;
}
