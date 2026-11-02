/* Exp. All: while it is on, party members that didn't battle (and haven't fainted) get half a participant's EXP,
   and so the EVs that come with it. Battle server (overlay 93), FUN_overlay_d_93__021cb2d4: it fills one 12-byte
   record per party slot, EXP first; Exp. Share holders get their split, then each participant its share. The
   hook runs between that and the level scaling, so the new EXP is scaled like the rest. */
#include "repel.h"

#define PARAM_IS_EGG 76

#define BattleParty_Get ((void *(*)(void *, u8))(0x021B9C00 | 1))
#define BattleMon_IsFainted ((u32 (*)(void *))(0x021D5B68 | 1))
#define BattleMon_GetPP ((void *(*)(void *))(0x021D5844 | 1))
#define PP_Get ((u32 (*)(void *, u32, u32))(0x02017E1C | 1))

struct ExpRecord {
    u32 exp;
    u8 rest[8];
};

void Gunk_ExpAll(struct ExpRecord *out, u32 share, void *party, u32 count)
{
    u32 i;

    if (!ExpAll_IsOn())
        return;
    for (i = 0; i < count; i++) {
        void *mon = BattleParty_Get(party, i);

        if (out[i].exp || BattleMon_IsFainted(mon) || PP_Get(BattleMon_GetPP(mon), PARAM_IS_EGG, 0))
            continue;
        out[i].exp = share / 2 ? share / 2 : 1;
    }
}

/* placed over `ldr r0, [sp, #0x1c]; movs r6, #0` at 0x021CB464: r5 = the records, and the routine's locals are on
   its stack (share at +0x18, party at +4, party size at +0x1C); redoes the two instructions on the way out */
__attribute__((naked)) void Gunk_ExpAll_Hook(void)
{
    asm volatile(
        "push {lr}\n"
        "mov r0, r5\n"
        "ldr r1, [sp, #0x1c]\n"  /* 0x18 + the pushed lr */
        "ldr r2, [sp, #0x8]\n"
        "ldr r3, [sp, #0x20]\n"
        "bl Gunk_ExpAll\n"
        "ldr r0, [sp, #0x20]\n"
        "movs r6, #0\n"
        "pop {pc}\n");
}
