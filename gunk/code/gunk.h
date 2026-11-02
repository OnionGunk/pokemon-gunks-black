/* Pokémon Gunk's Black: shared definitions for the code in the code home. */
#ifndef GUNK_H
#define GUNK_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed char s8;
typedef signed short s16;
typedef signed int s32;

#define GUNK_MAGIC 0x4B4E5547 /* "GUNK" */

struct GunkInfo {
    u32 magic;
    u32 version;
};

#endif
