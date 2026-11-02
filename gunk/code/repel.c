/* Endless Repel state: an event flag no retail script uses, and the Repel counter it keeps topped up. */
#include "repel.h"

#define SAVE_BLOCK_EVENTS 45
#define EVENTS_FLAGS 0x27C
#define FLAG_ENDLESS_REPEL 0xB50
#define SAVE_BLOCK_ENCOUNT 56
#define ENCOUNT_REPEL_STEPS 0x31

#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)

static u8 *FlagByte(void)
{
    return SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_EVENTS) + EVENTS_FLAGS + FLAG_ENDLESS_REPEL / 8;
}

int EndlessRepel_IsOn(void)
{
    return (*FlagByte() >> (FLAG_ENDLESS_REPEL % 8)) & 1;
}

void EndlessRepel_Set(int on)
{
    u8 bit = 1 << (FLAG_ENDLESS_REPEL % 8);

    *FlagByte() = on ? *FlagByte() | bit : *FlagByte() & ~bit;
    Repel_SetSteps(on ? ENDLESS_REPEL_STEPS : 0);
}

void Repel_SetSteps(u8 steps)
{
    SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_ENCOUNT)[ENCOUNT_REPEL_STEPS] = steps;
}
