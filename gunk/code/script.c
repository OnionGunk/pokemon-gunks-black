/* A script command of our own: opcode 0x25E (no retail script uses it) runs Gunk_ScriptCommand, which takes a u16
   sub-command and a u16 value (a variable or a literal). patches.script_command points the table slot here. */
#include "gunk.h"

enum {
    GUNK_CMD_SET_REPEL,  /* value = Repel, Super Repel or Max Repel: the Repel counter restarts for that item */
};

#define ITEM_SUPER_REPEL 76
#define ITEM_MAX_REPEL 77
#define ITEM_REPEL 79

#define SAVE_BLOCK_ENCOUNT 56
#define ENCOUNT_REPEL_STEPS 0x31

#define Script_ReadU16 ((u16 (*)(void *))(0x02011330 | 1))
#define Script_ReadValue ((u16 (*)(void *, void *))(0x02159B10 | 1))  /* overlay 10 */
#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)

static u8 RepelSteps(u16 item)
{
    switch (item) {
    case ITEM_MAX_REPEL:
        return 250;
    case ITEM_SUPER_REPEL:
        return 200;
    default:
        return 100;
    }
}

u32 Gunk_ScriptCommand(void *vm, void *ctx)
{
    u16 cmd = Script_ReadU16(vm);
    u16 value = Script_ReadValue(vm, ctx);

    switch (cmd) {
    case GUNK_CMD_SET_REPEL:
        SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_ENCOUNT)[ENCOUNT_REPEL_STEPS] = RepelSteps(value);
        break;
    }
    return 0;
}
