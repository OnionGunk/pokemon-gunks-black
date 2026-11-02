/* Overworld sprite per species, gender and form: Black's own table (a/2/1/1, the sprites Poké Transfer uses for
   #1-493). Placeholder here; patches.code_home copies the table in before the code goes into the ROM, closed by
   species 0. Its own file, so nothing that reads it can fold the placeholder in. */
#include "follower.h"

const struct FollowerSprite gGunkFollowerSprites[FOLLOWER_SPRITES_MAX] = { { 0xFFFF } };
