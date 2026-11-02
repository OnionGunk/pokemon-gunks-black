/* Endless Repel and Exp. All state: event flags no retail script uses; and the Repel counter. */
#include "repel.h"

#define SAVE_BLOCK_EVENTS 45
#define EVENTS_FLAGS 0x27C
#define FLAG_ENDLESS_REPEL 0xB50
#define FLAG_EXP_ALL 0xB51
#define SAVE_BLOCK_ENCOUNT 56
#define ENCOUNT_REPEL_STEPS 0x31

#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)

static u8 *FlagByte(u32 flag)
{
    return SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_EVENTS) + EVENTS_FLAGS + flag / 8;
}

static int GetFlag(u32 flag)
{
    return (*FlagByte(flag) >> (flag % 8)) & 1;
}

static void SetFlag(u32 flag, int on)
{
    u8 bit = 1 << (flag % 8);

    *FlagByte(flag) = on ? *FlagByte(flag) | bit : *FlagByte(flag) & ~bit;
}

int EndlessRepel_IsOn(void)
{
    return GetFlag(FLAG_ENDLESS_REPEL);
}

void EndlessRepel_Set(int on)
{
    SetFlag(FLAG_ENDLESS_REPEL, on);
    Repel_SetSteps(on ? ENDLESS_REPEL_STEPS : 0);
}

int ExpAll_IsOn(void)
{
    return GetFlag(FLAG_EXP_ALL);
}

void ExpAll_Set(int on)
{
    SetFlag(FLAG_EXP_ALL, on);
}

void Repel_SetSteps(u8 steps)
{
    SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_ENCOUNT)[ENCOUNT_REPEL_STEPS] = steps;
}
