/* DexNav (dexnav.c) as the script command (script.c) and the save (dexnav_save.c) see it. */
#ifndef DEXNAV_H
#define DEXNAV_H
#include "gunk.h"

#define DEXNAV_LIST_MAX 12   /* species on the DexNav screen */
#define ITEM_DEXNAV 431      /* the Poké Radar's slot, which Black never gives out (patches.dexnav_item) */

/* the graphical screen (dexnav_ui.c, in progress): a start-menu app after the retail 12 */
#define DEXNAV_APP 12
#ifndef DEXNAV_GRAPHICAL
#define DEXNAV_GRAPHICAL 1   /* 1: the bag's USE opens it instead of the list menu */
#endif

u32 Gunk_BagReturn(u8 *menu, u8 *param);  /* bag.c: the start menu's return handler for the bag */
u32 Gunk_MenuClose(u8 *menu, u32 event);
void *DexNavUi_FieldEvent(void *gsys, void *fieldSys);  /* bag.c: an app's return: close the menu for that item event */
#define ITEM_EVENT_DEXNAV_PICK 7

/* the bag's USE on the DexNav (bag.c): the screen for the player's spot, as an event */
u32 DexNav_ItemEvent(void *fieldSys);
u32 DexNav_BuildList(void *fieldSys);     /* the list for the player's spot: its length */
u32 DexNav_PickEvent(void *fieldSys);     /* the graphical screen picked a row: close for the search */
u32 DexNav_ListSpecies(u32 i);            /* 0 past the end */
u32 DexNav_ListMark(u32 i);               /* 0 past the end, 1 not seen, 2 seen, 3 caught */

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
