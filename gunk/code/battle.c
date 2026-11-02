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
