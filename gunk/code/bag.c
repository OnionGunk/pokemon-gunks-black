/* Bag (overlay 70): using the Endless Repel or the Exp. All switches it on or off, and the DexNav opens its screen.
   The bag looks items with their own USE handler up in an 8-entry table (0x021BB9C4: first item, count, handler);
   patches.endless_repel points the bag at this copy, which adds the key items after the retail entries. */
#include "repel.h"
#include "dexnav.h"

struct BagSpecial {
    u16 first, count;
    u32 handler;
};

#define MSG_ENDLESS_ON 140   /* added to the bag's message file (a/0/0/2 #3) by patches.endless_repel */
#define MSG_ENDLESS_OFF 141
#define MSG_EXP_ALL_ON 142   /* and by patches.exp_all */
#define MSG_EXP_ALL_OFF 143

#define BAG_MSGDATA 0x51C
#define BAG_WORDSET 0x520
#define BAG_STRBUF 0x524
#define BAG_EXPANDED 0x528
#define BAG_STATUS 8
#define BAG_RETURN 0x844         /* the code the bag closes with (Bicycle 0xA, Escape Rope 0xE, ... up to 0x14) */
#define BAG_RETURN_DEXNAV 0x15

#define Msg_GetStringTo ((void (*)(void *, u32, void *))0x02045CAC)
#define WordSet_PlayerName ((void (*)(void *, u32, void *))(0x0201F02C | 1))
#define WordSet_Expand ((void (*)(void *, void *, void *))(0x0201F250 | 1))
#define Bag_SetState ((void (*)(u8 *, u32))(0x021B6100 | 1))
#define BAG_STATE_SHOW_MESSAGE (0x021B6AD8 | 1)

#define WORD(bag, off) (*(void **)((bag) + (off)))

/* the message path Honey's handler takes */
static s32 ShowMessage(u8 *bag, u32 msg)
{
    Msg_GetStringTo(WORD(bag, BAG_MSGDATA), msg, WORD(bag, BAG_STRBUF));
    WordSet_PlayerName(WORD(bag, BAG_WORDSET), 0, WORD(bag, BAG_STATUS));
    WordSet_Expand(WORD(bag, BAG_WORDSET), WORD(bag, BAG_EXPANDED), WORD(bag, BAG_STRBUF));
    Bag_SetState(bag, BAG_STATE_SHOW_MESSAGE);
    return 0;
}

/* the bag's USE on the Endless Repel */
s32 Gunk_Bag_EndlessRepel(u8 *bag)
{
    int on = !EndlessRepel_IsOn();

    EndlessRepel_Set(on);
    return ShowMessage(bag, on ? MSG_ENDLESS_ON : MSG_ENDLESS_OFF);
}

/* the bag's USE on the Exp. All */
s32 Gunk_Bag_ExpAll(u8 *bag)
{
    int on = !ExpAll_IsOn();

    ExpAll_Set(on);
    return ShowMessage(bag, on ? MSG_EXP_ALL_ON : MSG_EXP_ALL_OFF);
}

/* the bag's USE on the DexNav: like the Bicycle's, the bag closes with a code (BAG_RETURN, here one retail doesn't
   use) and the start menu turns it into an item event once it has closed (Gunk_BagReturn, Gunk_ItemEvent) */
s32 Gunk_Bag_DexNav(u8 *bag)
{
    *(u32 *)(bag + BAG_RETURN) = BAG_RETURN_DEXNAV;
    Bag_SetState(bag, 0);
    return 1;
}

const struct BagSpecial gGunkBagSpecial[11] = {
    { 450, 1, 0x021B6AF1 }, { 442, 1, 0x021B6BC5 }, { 437, 1, 0x021B6C31 }, { 94, 1, 0x021B6D01 },
    { 447, 1, 0x021B6D71 }, { 465, 1, 0x021B6C99 }, { 471, 1, 0x021B6DD9 }, { 78, 1, 0x021B6E4D },
    { ITEM_ENDLESS_REPEL, 1, (u32)Gunk_Bag_EndlessRepel }, { ITEM_EXP_ALL, 1, (u32)Gunk_Bag_ExpAll },
    { ITEM_DEXNAV, 1, (u32)Gunk_Bag_DexNav },
};

/* Start menu (overlay 10). The bag is one of its apps (table at 0x021712C0: overlay, proc, setup, return handler,
   ...); the bag's return handler (FUN_overlay_d_10__02161070) reads the code the bag closed with (+0x34 of the
   bag's parameters) and, for an item used on the field, notes an item event in the menu event's work and returns
   3: the menu closes, and its event (FUN_overlay_d_10__0215fd0c, state 7) starts the item event that
   FUN_overlay_d_10__021644f4 makes (retail 0-5: bike, ..., Escape Rope, Dowsing Machine). The DexNav is event 6. */
#define BagReturn_Retail ((u32 (*)(u8 *, u8 *))(0x02161070 | 1))
#define ItemEvent_Retail ((u32 (*)(u32, void *, void *))(0x021644F4 | 1))
#define BAG_PARAM_RETURN 0x34
#define MENU_WORK 0x18           /* the menu event's work (from +0x1C): the item event at +0x28 */
#define MENU_ITEM_EVENT 0x28
#define MENU_CLOSE_FOR_ITEM 3
#define ITEM_EVENT_DEXNAV 6

u32 Gunk_BagReturn(u8 *menu, u8 *param)
{
    if (*(u32 *)(param + BAG_PARAM_RETURN) != BAG_RETURN_DEXNAV)
        return BagReturn_Retail(menu, param);
    *(u32 *)(*(u8 **)(menu + MENU_WORK) + MENU_ITEM_EVENT) = ITEM_EVENT_DEXNAV;
    return MENU_CLOSE_FOR_ITEM;
}

u32 Gunk_ItemEvent(u32 event, void *gsys, void *fieldSys)
{
    if (event == ITEM_EVENT_DEXNAV)
        return DexNav_ItemEvent(fieldSys);
    return ItemEvent_Retail(event, gsys, fieldSys);
}
