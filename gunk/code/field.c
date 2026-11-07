/* The field's per-frame input routine (FUN_overlay_d_21__021a2df0, called through its table at 0x021D8900) is
   wrapped by Gunk_FieldInput, for the features that watch the field every frame. */
#include "gunk.h"

#define FieldInput ((void (*)(void *))(0x021A2DF0 | 1))

void DexNav_Input(void);           /* dexnav.c */
void DexNav_Frame(void *field);    /* dexnav.c */
void Follower_Frame(void *field);  /* follower.c */

void DexNav_FieldStart(void);      /* dexnav.c */

/* the table entry (patches.dexnav) is Gunk_FieldInput in the overlay as loaded; the first call points it at
   FieldInputRunning, so the entry is back at Gunk_FieldInput only after the field has been loaded again (a menu,
   a battle): what the field had made (windows, objects) is gone then */
#define FIELD_INPUT_ENTRY (*(volatile u32 *)0x021D8900)

static void FieldInputRunning(void *fieldSys)
{
    DexNav_Input();
    DexNav_Frame(fieldSys);
    Follower_Frame(fieldSys);
    FieldInput(fieldSys);
}

void Gunk_FieldInput(void *fieldSys)
{
    FIELD_INPUT_ENTRY = (u32)FieldInputRunning;
    DexNav_FieldStart();
    FieldInputRunning(fieldSys);
}
