/* A script command of our own: opcode 0x25E (no retail script uses it) runs Gunk_ScriptCommand, which takes a u16
   sub-command, a u16 value (a variable or a literal) and the variable for its result. patches.script_command
   points the table slot here. */
#include "dexnav.h"
#include "repel.h"

enum {
    GUNK_CMD_SET_REPEL,      /* value = Repel, Super Repel or Max Repel: the counter restarts for that item */
    GUNK_CMD_ENDLESS_REPEL,  /* result = 1 and the counter back at 250 if the Endless Repel is on, else 0 */
    GUNK_CMD_DEXNAV_COUNT,   /* result = the rows on the DexNav screen */
    GUNK_CMD_DEXNAV_CURSOR,  /* result = the row its cursor starts on */
    GUNK_CMD_DEXNAV_ENTRY,   /* value = a row: its name in buffer 0, result = 0 past the end, else 1 + its mark */
    GUNK_CMD_DEXNAV_PICK,    /* value = the row picked: the search starts once the screen is closed; result 1, 2 not seen, 0 B */
    GUNK_CMD_DEXNAV_MESSAGE, /* result = which DexNav message to show, its species in buffer 0 */
};

#define ITEM_SUPER_REPEL 76
#define ITEM_MAX_REPEL 77

#define Script_ReadU16 ((u16 (*)(void *))(0x02011330 | 1))
#define Script_ReadValue ((u16 (*)(void *, void *))(0x02159B10 | 1))  /* overlay 10 */
#define Script_ReadVar ((u16 *(*)(void *, void *))(0x02159AE8 | 1))   /* overlay 10 */
#define Script_Work ((void *(*)(void *))(0x0215A5F4 | 1))              /* overlay 10 */
#define ScriptWork_WordSet ((void *(*)(void *))(0x02158F74 | 1))      /* overlay 10 */

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
    u16 *result = Script_ReadVar(vm, ctx);

    if (cmd == GUNK_CMD_SET_REPEL) {
        Repel_SetSteps(RepelSteps(value));
        *result = 1;
    } else if (cmd == GUNK_CMD_ENDLESS_REPEL) {
        *result = EndlessRepel_IsOn();
        if (*result)
            Repel_SetSteps(ENDLESS_REPEL_STEPS);
    } else if (cmd == GUNK_CMD_DEXNAV_COUNT) {
        *result = DexNav_ListCount();
    } else if (cmd == GUNK_CMD_DEXNAV_CURSOR) {
        *result = DexNav_ListCursor();
    } else if (cmd == GUNK_CMD_DEXNAV_ENTRY) {
        *result = DexNav_ListEntry(value, ScriptWork_WordSet(Script_Work(ctx)));
    } else if (cmd == GUNK_CMD_DEXNAV_PICK) {
        *result = DexNav_ListPick(value);
    } else if (cmd == GUNK_CMD_DEXNAV_MESSAGE) {
        *result = DexNav_Message(ScriptWork_WordSet(Script_Work(ctx)));
    }
    return 0;
}
