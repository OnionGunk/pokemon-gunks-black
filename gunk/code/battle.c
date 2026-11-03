/* Battle view (overlay 94): the EXP bar fills twice as fast. */
#include "gunk.h"

#define GAUGE_DONE (-1)

/* FUN_overlay_d_94__02207f6c: moves a bar's shown value one step toward cur - delta (one pixel; the caller works
   out the step), and returns GAUGE_DONE once it is there. Shared by the HP and EXP bars. */
#define Gauge_Step ((s32 (*)(s32, s32, s32, s32 *, u32, u32))(0x02207F6C | 1))

/* replaces the EXP bar's call to Gauge_Step (FUN_overlay_d_94__02207ef0): two steps a frame */
s32 Gunk_ExpGauge_Step(s32 max, s32 cur, s32 delta, s32 *shown, u32 cells, u32 step)
{
    s32 r = Gauge_Step(max, cur, delta, shown, cells, step);

    if (r != GAUGE_DONE)
        r = Gauge_Step(max, cur, delta, shown, cells, step);
    return r;
}

/* Quick Run and Quick Ball, in the action menu (FIGHT / BAG / POKéMON / RUN):
   - R runs. The bottom screen's button handler (FUN_overlay_d_94__02202dc4) asks the touch panel which button is
     touched (FUN_02035c08 on its touch rects, at 0x02202E82); Gunk_BattleTouch answers RUN when R is pressed, so
     the game takes it as a tap on RUN (in a trainer battle it says you can't run).
   - L throws a ball: Gunk_BattleTouch answers BAG, then Gunk_TouchUpdate (after the touch panel's per-frame update,
     FUN_020358a0) taps POKé BALLS, the ball and USE, so the game does the rest as if the player had (the count,
     the trainer-battle refusal, the catch). The ball is the last one thrown this way, else the first in the bag;
     holding L, Left and Right pick another (L thrown when let go without picking). Only the first page of the
     battle bag's balls (6) can be picked. */
#define TouchPanel_Hit ((u32 (*)(void *))0x02035C08)  /* ARM */
#define TouchPanel_Update ((void (*)(u8 *))0x020358A0)  /* ARM */
#define Key_GetTrg ((u32 (*)(void))0x020362DC)
#define Key_GetCont ((u32 (*)(void))0x0203630C)
#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)
#define PAD_RIGHT 0x0010
#define PAD_LEFT 0x0020
#define PAD_R 0x0100
#define PAD_L 0x0200
#define BTLV_MENU 0x58         /* u32: which menu the bottom screen shows */
#define MENU_ACTION 1
#define MENU_ACTION_DOUBLE 4
#define BUTTON_BAG 1
#define BUTTON_RUN 3
#define TOUCH_NONE 0xFFFFFFFF

#define TouchPanel (*(u8 **)0x021469C4)  /* its state: u16 x, y, triggered, held at +0x5C (+0x64 in mode 0x1E) */
#define TP_STATE 0x5C
#define TP_STATE_ALT 0x64
#define UI_TP_MODE 0x3D        /* u8, on the object the update gets */
#define TP_MODE_ALT 0x1E

#define SAVE_BLOCK_BAG 25      /* the items pocket comes first: 310 entries of u16 item, u16 count */
#define POCKET_ITEMS 310
#define ITEM_DREAM_BALL 576
#define BALL_PAGE 6

struct Tap {
    u16 frame, x, y;
};

/* frames after the action menu answered BAG: POKé BALLS, the ball (filled in), USE */
static struct Tap sTaps[3] = { { 60, 192, 48 }, { 110, 0, 0 }, { 160, 110, 173 } };
static const u8 sSlotX[2] = { 64, 192 };
static const u8 sSlotY[3] = { 40, 88, 136 };
static u16 sBall;        /* the ball L throws (0: none picked yet) */
static u8 sPicked;       /* Left or Right while L was held */
static u8 sLHeld;
static u16 sFrame;       /* frames since the throw started; 0: none running */

static int IsBall(u32 item)
{
    return (item >= 1 && item <= 16) || item == ITEM_DREAM_BALL;
}

/* the balls in the bag, in the battle bag's order (the items pocket's), up to BALL_PAGE */
static int Balls(u16 *out)
{
    const u16 *pocket = (const u16 *)SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_BAG);
    int i, n = 0;

    for (i = 0; i < POCKET_ITEMS && n < BALL_PAGE; i++)
        if (pocket[i * 2 + 1] && IsBall(pocket[i * 2]))
            out[n++] = pocket[i * 2];
    return n;
}

/* the chosen ball's place in the list, after making sure it is still in the bag (-1: no balls) */
static int BallSlot(void)
{
    u16 balls[BALL_PAGE];
    int n = Balls(balls), i;

    for (i = 0; i < n; i++)
        if (balls[i] == sBall)
            return i;
    if (!n)
        return -1;
    sBall = balls[0];
    return 0;
}

static void Cycle(int step)
{
    u16 balls[BALL_PAGE];
    int n = Balls(balls), i = BallSlot();

    if (i < 0)
        return;
    i += step;
    sBall = balls[i < 0 ? n - 1 : i >= n ? 0 : i];
}

u32 Gunk_BattleTouch(void **rects, u8 *view)
{
    u32 hit = TouchPanel_Hit(*rects);
    u32 menu = *(u32 *)(view + BTLV_MENU);
    u32 trg = Key_GetTrg(), cont = Key_GetCont();
    int slot;

    if (hit != TOUCH_NONE || (menu != MENU_ACTION && menu != MENU_ACTION_DOUBLE) || sFrame)
        return hit;
    if (trg & PAD_R)
        return BUTTON_RUN;
    if (cont & PAD_L) {
        if (trg & PAD_L)
            sPicked = 0;
        sLHeld = 1;
        if (trg & (PAD_LEFT | PAD_RIGHT)) {
            Cycle(trg & PAD_LEFT ? -1 : 1);
            sPicked = 1;
        }
        return hit;
    }
    if (!sLHeld)
        return hit;
    sLHeld = 0;  /* L let go: throw, unless Left or Right picked a ball meanwhile */
    if (sPicked || (slot = BallSlot()) < 0)
        return hit;
    sTaps[1].x = sSlotX[slot % 2];
    sTaps[1].y = sSlotY[slot / 2];
    sFrame = 1;
    return BUTTON_BAG;
}

void Gunk_TouchUpdate(u8 *ui)
{
    int i;

    TouchPanel_Update(ui);
    if (!sFrame)
        return;
    sFrame++;
    for (i = 0; i < 3; i++)
        if (sFrame == sTaps[i].frame) {
            u16 *tp = (u16 *)(TouchPanel + (ui[UI_TP_MODE] == TP_MODE_ALT ? TP_STATE_ALT : TP_STATE));

            tp[0] = sTaps[i].x;
            tp[1] = sTaps[i].y;
            tp[2] = 1;  /* triggered */
            tp[3] = 1;  /* held */
        }
    if (sFrame > sTaps[2].frame)
        sFrame = 0;
}

/* Quick Ball's line on the action prompt: in a wild battle with a ball in the bag, "What will X do?" gets a second
   line "L: <ball> x<count>" (message MSG_WHAT_WILL_BALL, added to a/0/0/2 #15: the ball name tag reads argument 1,
   the 2-digit number argument 2). Gunk_ActionPrompt replaces FUN_overlay_d_93__021ce0f8, which builds the prompt's
   message: kind 1 (standard), message 0x45 with the Pokémon's battle slot, or 0x46 with the player for a link
   battle. */
#define BtlMain_Competitor ((u32 (*)(void *))(0x021B8588 | 1))
#define BtlStr_Setup ((void (*)(void *, u32, u32))(0x021EAF18 | 1))
#define BtlStr_AddArg ((void (*)(void *, u32))(0x021EAF50 | 1))
#define BtlStr_Finish ((void (*)(void *, u32))(0x021EAF78 | 1))
#define BattleMon_GetBattleSlot ((u32 (*)(void *))(0x021D5440 | 1))
#define COMPETITOR_WILD 0
#define COMPETITOR_LINK 3
#define CLIENT_PLAYER 0x1A6    /* u8 */
#define STR_STANDARD 1
#define MSG_WHAT_WILL 0x45
#define MSG_WHAT_WILL_PLAYER 0x46
#define MSG_WHAT_WILL_BALL 200
#define COUNT_MAX 99

static u32 BallCount(u16 item)
{
    const u16 *pocket = (const u16 *)SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_BAG);
    int i;

    for (i = 0; i < POCKET_ITEMS; i++)
        if (pocket[i * 2] == item)
            return pocket[i * 2 + 1];
    return 0;
}

void Gunk_ActionPrompt(void **client, void *mon, void *param)
{
    u32 competitor = BtlMain_Competitor(*client);
    u32 count;

    if (competitor == COMPETITOR_LINK) {
        BtlStr_Setup(param, STR_STANDARD, MSG_WHAT_WILL_PLAYER);
        BtlStr_AddArg(param, ((u8 *)client)[CLIENT_PLAYER]);
    } else if (competitor == COMPETITOR_WILD && BallSlot() >= 0) {
        count = BallCount(sBall);
        BtlStr_Setup(param, STR_STANDARD, MSG_WHAT_WILL_BALL);
        BtlStr_AddArg(param, BattleMon_GetBattleSlot(mon));
        BtlStr_AddArg(param, sBall);
        BtlStr_AddArg(param, count > COUNT_MAX ? COUNT_MAX : count);
    } else {
        BtlStr_Setup(param, STR_STANDARD, MSG_WHAT_WILL);
        BtlStr_AddArg(param, BattleMon_GetBattleSlot(mon));
    }
    BtlStr_Finish(param, 0);
}
