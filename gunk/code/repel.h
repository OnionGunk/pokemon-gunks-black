/* Key items that switch on and off (Endless Repel, Exp. All): shared by bag.c, script.c and expall.c. */
#ifndef REPEL_H
#define REPEL_H
#include "gunk.h"

#define ITEM_ENDLESS_REPEL 426  /* an unused item slot */
#define ENDLESS_REPEL_STEPS 250

#define ITEM_EXP_ALL 427  /* an unused item slot */

int EndlessRepel_IsOn(void);
int ExpAll_IsOn(void);
void ExpAll_Set(int on);
void EndlessRepel_Set(int on);
void Repel_SetSteps(u8 steps);

#endif
