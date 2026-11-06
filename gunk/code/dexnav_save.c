/* DexNav search levels, saved for the last DEXNAV_LEVEL_SPECIES species searched.

   The main save has no free block, but each block sits in its own 0x100-aligned slot, and Black never writes the
   end of a slot past the block's footer: a save leaves those bytes alone on the flash, and loading a half reads the
   whole half into the save buffer, tails and all (checked in the emulator). Block 64 (0x23900) holds 0x10 bytes
   and a 4-byte footer, which leaves 0xEC bytes: two copies of the levels' record (A at +0x18, B at +0x80, 0x68
   bytes each), with their own magic, CRC-16 and the trainer ID they belong to.

   The record lives in the save buffer, so it is kept, lost or loaded exactly as the rest of the save is; only its
   writing is ours. Gunk_SaveMain wraps the game's per-frame save step (GFL's, called from SaveData_SaveAsyncMain at
   0x02007186): once the game's own save has finished (result 2), the record goes to flash with the game's own
   asynchronous write (FUN_020336b8, polled by FUN_020337b8): A then B in half 0, then A then B in half 1. The game
   keeps showing "Saving..." until the last write is done. A power cut part-way leaves at least one good copy in
   the half the game loads (or an older one, from the save before). Reading: the half the game loaded is in the
   buffer; the first good copy for this trainer is used; with none, the levels start from zero (a new game, an
   old save, or both copies damaged). */
#include "dexnav.h"

#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)
#define GflSave_Main ((u32 (*)(void *))0x02031BB4)                      /* ARM */
#define Flash_Write ((u32 (*)(u32, const void *, u32, u32))0x020336B8) /* ARM: dst, src, size -> lock id */
#define Flash_Poll ((u32 (*)(u32, u32 *, u32))0x020337B8)               /* ARM: 1 once that write is over */
#define FLASH_CTX (*(u32 *)(*(u8 **)0x02146994 + 0x208))                /* what the game passes with both */

#define SAVE_LAST 1              /* GFL's results: 0 and 1 still saving, 2 done, 3 failed */
#define SAVE_OK 2
#define HALF_SIZE 0x24000        /* the second half mirrors the first */
#define TRAINER_ID 0x19414       /* in the save buffer: trainer ID, then secret ID */
#define RECORD_A 0x23918         /* block 64 (0x23900): 0x10 bytes, the footer, then the slot's tail */
#define RECORD_B 0x23980
#define RECORD_MAGIC 0x4E44      /* "DN" */
#define DEXNAV_LEVEL_SPECIES 32
#define LEVEL_MAX 255

struct LevelRecord {
    u16 magic;
    u16 crc;                      /* CRC-16-CCITT of everything after it */
    u32 trainer;
    u16 species[DEXNAV_LEVEL_SPECIES];  /* most recently searched first; 0 = empty */
    u8 level[DEXNAV_LEVEL_SPECIES];
};

static u8 sWriteStep;            /* 1-4: which of the four writes is under way */
static u32 sWriteLock;

static u8 *Buffer(void)
{
    return SaveData_GetBlock(SaveData_Ptr, 0);  /* block 0 starts the buffer, laid out like a flash half */
}

static u16 Crc16(const u8 *p, u32 n)
{
    u16 crc = 0xFFFF;
    int b;

    while (n--) {
        crc ^= *p++ << 8;
        for (b = 0; b < 8; b++)
            crc = crc & 0x8000 ? crc << 1 ^ 0x1021 : crc << 1;
    }
    return crc;
}

static u16 RecordCrc(const struct LevelRecord *r)
{
    return Crc16((const u8 *)&r->trainer, sizeof(*r) - 4);
}

static void Copy(void *dst, const void *src, u32 n)
{
    u8 *d = dst;
    const u8 *s = src;

    while (n--)
        *d++ = *s++;
}

/* copy A, made good: B when A is bad, empty levels when both are (or belong to another trainer) */
static struct LevelRecord *Record(void)
{
    u8 *buf = Buffer();
    struct LevelRecord *a = (struct LevelRecord *)(buf + RECORD_A);
    struct LevelRecord *b = (struct LevelRecord *)(buf + RECORD_B);
    u32 trainer = *(u32 *)(buf + TRAINER_ID);
    u32 i;

    if (a->magic == RECORD_MAGIC && a->trainer == trainer && a->crc == RecordCrc(a))
        return a;
    if (b->magic == RECORD_MAGIC && b->trainer == trainer && b->crc == RecordCrc(b)) {
        Copy(a, b, sizeof(*a));
        return a;
    }
    for (i = 0; i < sizeof(*a); i++)
        ((u8 *)a)[i] = 0;
    a->magic = RECORD_MAGIC;
    a->trainer = trainer;
    a->crc = RecordCrc(a);
    Copy(b, a, sizeof(*a));
    return a;
}

u8 DexNav_Level(u16 species)
{
    struct LevelRecord *r = Record();
    int i;

    for (i = 0; i < DEXNAV_LEVEL_SPECIES; i++)
        if (r->species[i] == species)
            return r->level[i];
    return 0;
}

/* one more search for species: it moves to the front, and the species searched longest ago drops off a full list */
void DexNav_RaiseLevel(u16 species)
{
    struct LevelRecord *r = Record();
    u8 level = 0;
    int i;

    for (i = 0; i < DEXNAV_LEVEL_SPECIES - 1; i++)
        if (r->species[i] == species)
            break;
    if (r->species[i] == species)
        level = r->level[i];
    for (; i > 0; i--) {
        r->species[i] = r->species[i - 1];
        r->level[i] = r->level[i - 1];
    }
    r->species[0] = species;
    r->level[0] = level < LEVEL_MAX ? level + 1 : LEVEL_MAX;
    r->crc = RecordCrc(r);
    Copy(Buffer() + RECORD_B, r, sizeof(*r));
}

static u32 StartWrite(u32 step)
{
    u32 at = (step & 1 ? RECORD_A : RECORD_B) + (step > 2 ? HALF_SIZE : 0);

    return Flash_Write(at, Buffer() + (step & 1 ? RECORD_A : RECORD_B), sizeof(struct LevelRecord), FLASH_CTX);
}

u32 Gunk_SaveMain(void *ctrl)
{
    u32 ok = 0;

    if (!sWriteStep) {
        u32 result = GflSave_Main(ctrl);

        if (result != SAVE_OK)
            return result;
        Copy(Buffer() + RECORD_B, Record(), sizeof(struct LevelRecord));  /* both copies good and the same */
        sWriteStep = 1;
        sWriteLock = StartWrite(sWriteStep);
        return SAVE_LAST;
    }
    if (!Flash_Poll(sWriteLock, &ok, FLASH_CTX))
        return SAVE_LAST;
    if (++sWriteStep > 4) {
        sWriteStep = 0;
        return SAVE_OK;
    }
    sWriteLock = StartWrite(sWriteStep);
    return SAVE_LAST;
}
