/* Bag (overlay 70): using the Endless Repel or the Exp. All switches it on or off. The bag looks items with their
   own USE handler up in an 8-entry table (0x021BB9C4: first item, count, handler); patches.endless_repel points
   the bag at this copy, which adds the two key items after the retail entries. */
#include "repel.h"

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

const struct BagSpecial gGunkBagSpecial[10] = {
    { 450, 1, 0x021B6AF1 }, { 442, 1, 0x021B6BC5 }, { 437, 1, 0x021B6C31 }, { 94, 1, 0x021B6D01 },
    { 447, 1, 0x021B6D71 }, { 465, 1, 0x021B6C99 }, { 471, 1, 0x021B6DD9 }, { 78, 1, 0x021B6E4D },
    { ITEM_ENDLESS_REPEL, 1, (u32)Gunk_Bag_EndlessRepel }, { ITEM_EXP_ALL, 1, (u32)Gunk_Bag_ExpAll },
};
