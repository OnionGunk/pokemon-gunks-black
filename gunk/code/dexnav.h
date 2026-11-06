/* DexNav (dexnav.c) as the script command (script.c) and the save (dexnav_save.c) see it. */
#ifndef DEXNAV_H
#define DEXNAV_H
#include "gunk.h"

#define DEXNAV_LIST_MAX 12   /* species on the DexNav screen */

/* the screen (script 10146, patches.dexnav_screen): the list R built for the player's spot */
u32 DexNav_ListCount(void);
u32 DexNav_ListCursor(void);              /* the row to start on: the last pick, else the first not caught */
u32 DexNav_ListEntry(u32 i, void *ws);    /* puts row i's name in buffer 0; 0 past the end, else 1 + its mark */
u32 DexNav_ListPick(u32 i);               /* starts the search for row i: 1; 2 not seen (no search); 0 past the end */
u32 DexNav_Message(void *ws);             /* the pending message (its species in buffer 0) */

/* search levels, kept for the last DEXNAV_LEVEL_SPECIES species searched (dexnav_save.c) */
u8 DexNav_Level(u16 species);
void DexNav_RaiseLevel(u16 species);

#endif
