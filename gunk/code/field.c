/* The field's per-frame input routine (FUN_overlay_d_21__021a2df0, called through its table at 0x021D8900) is
   wrapped by Gunk_FieldInput, for the features that watch the field every frame. */
#include "gunk.h"

#define FieldInput ((void (*)(void *))(0x021A2DF0 | 1))

void DexNav_Input(void);           /* dexnav.c */
void DexNav_Frame(void *field);    /* dexnav.c */
void Follower_Frame(void *field);  /* follower.c */

void Gunk_FieldInput(void *fieldSys)
{
    DexNav_Input();
    DexNav_Frame(fieldSys);
    Follower_Frame(fieldSys);
    FieldInput(fieldSys);
}
