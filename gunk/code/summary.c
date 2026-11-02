/* Summary screen (overlay 131): A on the stats page cycles the numbers between the stats, the IVs and the EVs.
   The HP line reads IV/31 or EV/252 in those views; the HP bar always shows the real HP. */
#include "gunk.h"

#define PAD_A 0x0001
#define PAGE_STATS 1
#define SE_PAGE 0x665  /* the sound the summary plays when it turns a page */

enum { VIEW_STATS, VIEW_IVS, VIEW_EVS, VIEW_COUNT };

/* Pokémon parameters (FUN_02017e1c), Gen 4's numbering for the low ones */
#define PARAM_EV_HP 13  /* 13-18: HP, Attack, Defense, Speed, Sp. Atk, Sp. Def */
#define PARAM_IV_HP 70  /* 70-75: the same order */
#define PARAM_HP 0xA0
#define PARAM_MAX_HP 0xA1
#define PARAM_ATTACK 0xA2  /* 0xA2-0xA6: Attack, Defense, Speed, Sp. Atk, Sp. Def */

struct SummaryWork {
    u8 pad0[0x38];
    u32 busy;      /* +0x38: non-zero while a sub-mode (move swap, ...) is open; pages don't turn then */
    u8 pad1[0x58 - 0x3C];
    u32 page;      /* +0x58 */
};

#define PP_Get ((u32 (*)(void *, u32, u32))(0x02017E1C | 1))
#define Key_GetTrg ((u32 (*)(void))0x020362DC)
#define Sound_Play ((void (*)(u32))(0x020061E4 | 1))
#define Summary_Keys ((s32 (*)(struct SummaryWork *))(0x021D52D4 | 1))
#define Summary_Redraw ((void (*)(struct SummaryWork *))(0x021D5C98 | 1))

static u8 sView;
static struct SummaryWork *sWork;

/* replaces the stats page's seven reads of HP, max HP and the five stats (FUN_overlay_d_131__021da0b0) */
u32 Gunk_Summary_StatValue(void *pp, u32 param, u32 arg)
{
    u32 stat;

    if (sView == VIEW_STATS)
        return PP_Get(pp, param, arg);
    if (param == PARAM_MAX_HP)
        return sView == VIEW_IVS ? 31 : 252;
    stat = param == PARAM_HP ? 0 : param - PARAM_ATTACK + 1;
    return PP_Get(pp, (sView == VIEW_IVS ? PARAM_IV_HP : PARAM_EV_HP) + stat, arg);
}

/* replaces the summary's call to its key handler (FUN_overlay_d_131__021d52d4); non-zero = key used */
s32 Gunk_Summary_Keys(struct SummaryWork *work)
{
    if (work != sWork || work->page != PAGE_STATS) {  /* a summary just opened, or another page: back to stats */
        sWork = work;
        sView = VIEW_STATS;
    }
    if (work->page == PAGE_STATS && !work->busy && (Key_GetTrg() & PAD_A)) {
        sView = sView + 1 == VIEW_COUNT ? VIEW_STATS : sView + 1;
        Summary_Redraw(work);
        Sound_Play(SE_PAGE);
        return 1;
    }
    return Summary_Keys(work);
}
