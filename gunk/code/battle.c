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

/* Quick Run: R in the action menu (FIGHT / BAG / POKéMON / RUN) runs. The bottom screen's button handler
   (FUN_overlay_d_94__02202dc4) asks the touch panel which button is touched (FUN_02035c08 on its touch rects,
   at 0x02202E82); Gunk_BattleTouch answers RUN when nothing is touched and R is pressed in that menu, so the game
   takes it exactly as a tap on RUN (in a trainer battle it says you can't run). */
#define TouchPanel_Hit ((u32 (*)(void *))0x02035C08)  /* ARM */
#define Key_GetTrg ((u32 (*)(void))0x020362DC)
#define PAD_R 0x0100
#define BTLV_MENU 0x58         /* u32: which menu the bottom screen shows */
#define MENU_ACTION 1
#define MENU_ACTION_DOUBLE 4
#define BUTTON_RUN 3
#define TOUCH_NONE 0xFFFFFFFF

u32 Gunk_BattleTouch(void **rects, u8 *view)
{
    u32 hit = TouchPanel_Hit(*rects);
    u32 menu = *(u32 *)(view + BTLV_MENU);

    if (hit == TOUCH_NONE && (Key_GetTrg() & PAD_R) && (menu == MENU_ACTION || menu == MENU_ACTION_DOUBLE))
        return BUTTON_RUN;
    return hit;
}
