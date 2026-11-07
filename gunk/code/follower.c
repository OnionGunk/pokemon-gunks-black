/* Follower Pokémon: the party's first Pokémon walks behind the player.

   Black keeps Gen 4's "pair" movement type (0x30, unused by any map): an object with it records where the player
   is and steps after them. The follower is such an object (id FOLLOWER_ID) with the lead Pokémon's overworld
   sprite: Black's own sprites for #1-493 and the added Gen 5 ones (followertab.c). An egg or a fainted lead has no
   follower, and it goes back in its ball while the player cycles or surfs.
   - Gunk_LoadZoneObjects wraps the field's loading of a zone's objects when the player crosses into another
     zone (FUN_overlay_d_21__021894e0), Gunk_LoadWarpObjects the loading after a warp (FUN_overlay_d_20__021858e4,
     doors, stairs, Fly). A zone crossing keeps the follower (in the new zone); a warp takes it back in its ball.
   - Follower_Frame runs with the field's per-frame input (field.c): it swaps the sprite when the lead changes, and
     when the follower is missing (after a warp, a save from before, getting off the bike) it comes out on the tile
     the player is stepping off, so it never stands on the player. */
#include "follower.h"

#define FOLLOWER_ID 0xF5
#define MOVE_PAIR 0x30
#define DIR_DOWN 1

#define MMDL_ZONE 0x0A       /* u16 */
#define MMDL_CODE 0x0C       /* u16 */
#define MMDL_SCRIPT 0x14     /* u16: the script talking to it runs */
#define FOLLOWER_SCRIPT 10144  /* script file 872's entry 14 (patches.follower_talk) */
#define MMDL_OLD_GRID_X 0x36 /* s16: the tile it is stepping off (its own tile when it stands, stale after a load) */
#define MMDL_OLD_GRID_Z 0x3A
#define FIELD_GAMEDATA 0x08
#define FIELD_MMDLSYS 0x38
#define GAMEDATA_MMDLSYS 0x1A8
#define GAMEDATA_LOCATION 0x110
#define LOCATION_ZONE 0x04   /* s16 */

#define SAVE_BLOCK_PARTY 26
#define PARTY_COUNT 0x04
#define PARTY_MONS 0x08

#define PARAM_SPECIES 5
#define PARAM_IS_EGG 76
#define PARAM_GENDER 110  /* worked out from species, personality and form */
#define PARAM_FORM 111
#define PARAM_HP 0xA0

#define LoadZoneObjects ((void (*)(void *, void *, void *, u32))(0x021894E0 | 1))
#define LoadWarpObjects ((void (*)(void *, u8 *))(0x021858E4 | 1))
#define MMdlSys_AddParam ((void *(*)(void *, s32, s32, u32, u32, u32, u32, u32))(0x0216CE6C | 1))
#define MMdlSys_Player ((void *(*)(void *))(0x0216DEE0 | 1))
#define MMdlSys_Search ((void *(*)(void *, u32))(0x0216DE94 | 1))
#define MMdl_Delete ((void (*)(void *))(0x0216CF2C | 1))
#define MMdl_GridX ((u32 (*)(void *))(0x0216D83C | 1))
#define MMdl_GridZ ((u32 (*)(void *))(0x0216D86C | 1))
#define PP_Get ((u32 (*)(void *, u32, u32))(0x02017E1C | 1))
#define SaveData_GetBlock ((u8 *(*)(void *, u32))(0x020071CC | 1))
#define SaveData_Ptr (*(void **)0x020A7298)
#define REFRESH_CALLS 8      /* how often the field checks the lead */

/* the player's object codes on the bicycle and surfing (hero, heroine; 1 and 4 are on foot) */
#define CODE_HERO_CYCLE 2
#define CODE_HERO_SWIM 3
#define CODE_HEROINE_CYCLE 5
#define CODE_HEROINE_SWIM 6

extern const struct FollowerSprite gGunkFollowerSprites[FOLLOWER_SPRITES_MAX];  /* followertab.c */

static u32 sCalls;
static u16 sLeadCode;  /* FollowerCode(), as of the last check */

static void *Lead(void)
{
    u8 *party = SaveData_GetBlock(SaveData_Ptr, SAVE_BLOCK_PARTY);

    return *(u32 *)(party + PARTY_COUNT) ? party + PARTY_MONS : 0;
}

/* the lead's object code, 0 for none */
static u16 FollowerCode(void)
{
    void *pp = Lead();
    u32 species, gender, form;
    u16 code = 0;
    int i;

    if (!pp || PP_Get(pp, PARAM_IS_EGG, 0) || !PP_Get(pp, PARAM_HP, 0))
        return 0;
    species = PP_Get(pp, PARAM_SPECIES, 0);
    gender = PP_Get(pp, PARAM_GENDER, 0);
    form = PP_Get(pp, PARAM_FORM, 0);
    for (i = 0; i < FOLLOWER_SPRITES_MAX && gGunkFollowerSprites[i].species; i++) {
        const struct FollowerSprite *s = &gGunkFollowerSprites[i];

        if (s->species != species)
            continue;
        if (s->form == form && (s->gender == 2 || s->gender == gender))
            return s->code;
        if (!code && s->form == 0)
            code = s->code;  /* a form or gender without its own sprite looks like the first one */
    }
    return code;
}

static int OnFoot(u8 *player)
{
    u16 code = *(u16 *)(player + MMDL_CODE);

    return code != CODE_HERO_CYCLE && code != CODE_HERO_SWIM && code != CODE_HEROINE_CYCLE &&
           code != CODE_HEROINE_SWIM;
}

/* make the follower match the lead: a new lead's follower takes the old one's place; a missing one comes out on the
   tile the player is stepping off (none while the player stands). It belongs to the current zone, so the field
   doesn't clear it away with the last zone's objects. */
static void Refresh(void *mmdlSys, u32 zone)
{
    u8 *follower = MMdlSys_Search(mmdlSys, FOLLOWER_ID);
    u8 *player = MMdlSys_Player(mmdlSys);
    u16 code = player && OnFoot(player) ? sLeadCode : 0;
    s32 x = 0, z = 0;

    if (follower && *(u16 *)(follower + MMDL_CODE) == code) {
        *(u16 *)(follower + MMDL_ZONE) = zone;
        *(u16 *)(follower + MMDL_SCRIPT) = FOLLOWER_SCRIPT;
        return;
    }
    if (follower) {
        x = MMdl_GridX(follower);
        z = MMdl_GridZ(follower);
        MMdl_Delete(follower);
    } else if (player) {
        x = *(s16 *)(player + MMDL_OLD_GRID_X);
        z = *(s16 *)(player + MMDL_OLD_GRID_Z);
        /* one step away; right after a load the old tile can be anything */
        if ((x - (s32)MMdl_GridX(player)) * (x - (s32)MMdl_GridX(player)) +
            (z - (s32)MMdl_GridZ(player)) * (z - (s32)MMdl_GridZ(player)) != 1)
            return;
    }
    if (code)
        MMdlSys_AddParam(mmdlSys, x, z, DIR_DOWN, FOLLOWER_ID, code, MOVE_PAIR, zone);
}

void Gunk_LoadZoneObjects(void *gameData, void *mmdlSys, void *events, u32 zone)
{
    LoadZoneObjects(gameData, mmdlSys, events, zone);
    sLeadCode = FollowerCode();
    Refresh(mmdlSys, zone);
}

void Gunk_LoadWarpObjects(u8 *gameData, u8 *location)
{
    u8 *follower;

    LoadWarpObjects(gameData, location);
    /* the field would put the follower on the player's tile: it goes back in its ball, and Follower_Frame brings
       it out behind the player's first step */
    follower = MMdlSys_Search(*(void **)(gameData + GAMEDATA_MMDLSYS), FOLLOWER_ID);
    if (follower)
        MMdl_Delete(follower);
}

/* A cutscene: a script moving anyone (command 0x64, ApplyMovement; FUN_overlay_d_21__021b1698) takes the follower
   back in its ball first. The field's input doesn't run during a script, so the follower would stand where it was
   and trail the player afterwards; this way Follower_Frame brings it out again behind the player's first step
   once the script is over. */
#define ScrWork_MMdlSys ((void *(*)(void *))(0x0215A5EC | 1))
#define ScrCmd_ApplyMovement ((u32 (*)(void *, void *))(0x021B1698 | 1))

u32 Gunk_ScrApplyMovement(void *ctx, void *work)
{
    void *follower = MMdlSys_Search(ScrWork_MMdlSys(work), FOLLOWER_ID);

    if (follower)
        MMdl_Delete(follower);
    return ScrCmd_ApplyMovement(ctx, work);
}

void Follower_Frame(void *fieldSys)
{
    void *mmdlSys = *(void **)((u8 *)fieldSys + FIELD_MMDLSYS);
    u8 *gameData = *(u8 **)((u8 *)fieldSys + FIELD_GAMEDATA);

    if (!mmdlSys || !gameData)
        return;
    if (!(sCalls++ & (REFRESH_CALLS - 1)))
        sLeadCode = FollowerCode();
    Refresh(mmdlSys, *(s16 *)(gameData + GAMEDATA_LOCATION + LOCATION_ZONE));
}
