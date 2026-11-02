/* Options menu (overlay 68): INSTANT text speed. Tapping FAST while FAST is already on switches to INSTANT (text
   speed 3, see patches.text_instant) and relabels that button; tapping it again goes back to FAST. The D-pad
   moves between SLOW, MID and FAST only (from INSTANT, Left goes to MID). */
#include "gunk.h"

struct OptButton {  /* 0x021BB704, 11 entries: one per touch button */
    u32 field;      /* index into the menu's option bytes: 0 = text speed */
    u32 value;
    u8 rest[0x10];
};

struct OptLabel {   /* 0x021BB820, 16 entries: one text window per label */
    u32 msg;        /* string in message file 29 */
    u8 x, y, w, h;  /* tiles */
};

#define OPT_BUTTONS ((const struct OptButton *)0x021BB704)
#define OPT_LABELS ((const struct OptLabel *)0x021BB820)

#define TEXT_SPEED_FAST 2
#define TEXT_SPEED_INSTANT 3
#define LABEL_FAST 2        /* label and window index of FAST */
#define MSG_FAST 12
#define MSG_INSTANT 19      /* an empty string in retail; patches.text_instant writes "INSTANT" there */
#define FAST_PAD 2          /* px before the text, as the menu draws FAST */
#define LABEL_TILES 6       /* wide enough for INSTANT, and FAST at 26 + 6 ends at the screen edge */
#define HEAP_OPTIONS 0x1C

/* overlay 68 */
#define Options_Store ((void (*)(u8 *))(0x021BAFA8 | 1))
#define Options_InitLabels ((void (*)(void **))(0x021B9C04 | 1))
/* ARM9 */
#define Font_Create ((void *(*)(u32, u32, u32, u32, u32))(0x0201D7EC | 1))
#define Font_Delete ((void (*)(void *))(0x0201D83C | 1))
#define Print_ToBmp ((void (*)(void *, s16, s16, void *, void *))(0x0201C7A4 | 1))
#define Msg_Create ((void *(*)(u32, u32, u32, u32))0x02045B38)
#define Msg_Delete ((void (*)(void *))0x02045C04)
#define Msg_GetString ((void *(*)(void *, u32))0x02045EC0)
#define Str_Delete ((void (*)(void *))0x02045808)
#define Win_Create ((void *(*)(u32, u32, u32, u32, u32, u32, u32))0x020450F0)
#define Win_Delete ((void (*)(void *))0x020452E8)
#define Win_GetBmp ((void *(*)(void *))0x02045770)
#define Win_GetFrame ((u32 (*)(void *))0x02045730)
#define Win_TransferChars ((void (*)(void *))0x02045334)
#define Win_TransferScreen ((void (*)(void *))0x02045374)
#define Bmp_Fill ((void (*)(void *, u32))0x02043B5C)
#define Bg_RequestTransfer ((void (*)(u32))0x02041B6C)
#define GameData_Ptr (*(void **)0x020A7298)
#define GameData_GetOptions ((void *(*)(void *))(0x0200873C | 1))
#define Options_GetTextSpeed ((u32 (*)(void *))(0x02008374 | 1))

static void **sLabelWindows;  /* the menu's label windows while it is open */
static u8 sShownInstant;      /* what the FAST button's label says now */

static void Relabel(u32 speed)
{
    const struct OptLabel *label = &OPT_LABELS[LABEL_FAST];
    void *font = Font_Create(0x17, 0, 0, 0, HEAP_OPTIONS);
    void *msg = Msg_Create(0, 2, 29, HEAP_OPTIONS);
    void *str = Msg_GetString(msg, speed == TEXT_SPEED_INSTANT ? MSG_INSTANT : MSG_FAST);
    void *win;

    sShownInstant = speed == TEXT_SPEED_INSTANT;
    Win_Delete(sLabelWindows[LABEL_FAST]);
    win = Win_Create(1, label->x, label->y, LABEL_TILES, label->h, 0, 1);
    sLabelWindows[LABEL_FAST] = win;
    Bmp_Fill(Win_GetBmp(win), 0);
    Print_ToBmp(Win_GetBmp(win), FAST_PAD, 0, str, font);
    Win_TransferChars(win);
    Win_TransferScreen(win);
    Bg_RequestTransfer(Win_GetFrame(win));
    Str_Delete(str);
    Msg_Delete(msg);
    Font_Delete(font);
}

/* replaces the menu's call to its label setup: the windows are kept, and FAST gets its wider window at once */
void Gunk_Options_InitLabels(void **windows)
{
    Options_InitLabels(windows);
    sLabelWindows = windows;
    Relabel(Options_GetTextSpeed(GameData_GetOptions(GameData_Ptr)));
}

/* replaces FUN_overlay_d_68__021bb0ac: is button idx shown as selected */
int Gunk_Options_IsSelected(const u8 *state, int idx)
{
    u32 field = OPT_BUTTONS[idx].field, value = OPT_BUTTONS[idx].value;

    if (field == 0 && value == TEXT_SPEED_FAST && state[0] == TEXT_SPEED_INSTANT)
        return 1;
    return state[field] == value;
}

/* replaces FUN_overlay_d_68__021bafd8: button idx was tapped */
void Gunk_Options_Tap(u8 *state, int idx)
{
    u32 field = OPT_BUTTONS[idx].field, value = OPT_BUTTONS[idx].value;

    if (field == 0 && value == TEXT_SPEED_FAST && (state[0] == TEXT_SPEED_FAST || state[0] == TEXT_SPEED_INSTANT))
        value = state[0] == TEXT_SPEED_FAST ? TEXT_SPEED_INSTANT : TEXT_SPEED_FAST;
    if (state[field] == value)
        return;
    state[field] = value;
    state[5] = idx;
    Options_Store(state);
    if (sLabelWindows && sShownInstant != (state[0] == TEXT_SPEED_INSTANT))
        Relabel(state[0]);
}

/* replaces the D-pad handler's call to Options_Store: Left from INSTANT puts the FAST label back */
void Gunk_Options_StoreKey(u8 *state)
{
    Options_Store(state);
    if (sLabelWindows && sShownInstant != (state[0] == TEXT_SPEED_INSTANT))
        Relabel(state[0]);
}
