/* The first words of the code home: tests read them to check the block arrived at 0x023C0000. */
#include "gunk.h"

__attribute__((section(".gunk_info"), used)) const struct GunkInfo gGunkInfo = { GUNK_MAGIC, 1 };
