/* Follower Pokémon: shared between follower.c and its sprite table. */
#ifndef FOLLOWER_H
#define FOLLOWER_H

#include "gunk.h"

#define FOLLOWER_SPRITES_MAX 600

struct FollowerSprite {
    u16 species;
    u16 gender;  /* 0 male, 1 female, 2 either */
    u16 form;
    u16 code;    /* object code: its sprite parameters in a/0/4/8 */
};

#endif
