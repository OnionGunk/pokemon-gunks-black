/* bit n = the species can learn HM0(n+1). Placeholder bytes here; patches.code_home fills the table from the
   personal data (a/0/1/6, TM/HM bits 95-100) before the code goes into the ROM. Its own file, so nothing that
   reads it can fold the placeholder in. */
#include "gunk.h"

const u8 gGunkHmCompat[650] = { 0xFF };
