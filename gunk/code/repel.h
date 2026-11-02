/* Endless Repel: shared by the bag (bag.c) and the script command (script.c). */
#ifndef REPEL_H
#define REPEL_H
#include "gunk.h"

#define ITEM_ENDLESS_REPEL 426  /* an unused item slot */
#define ENDLESS_REPEL_STEPS 250

int EndlessRepel_IsOn(void);
void EndlessRepel_Set(int on);
void Repel_SetSteps(u8 steps);

#endif
