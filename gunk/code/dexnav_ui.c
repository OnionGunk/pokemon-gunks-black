/* The DexNav screen as a start-menu app: the spot's species as a grid of icons (a cursor, caught/seen marks, the
   cursor's name below; A searches, B goes back), drawn with Black's own BG, window, font and archive routines, set up the
   way the Bag sets up its screen (overlay 70, proc 0x021BB96C). The start menu runs it like its other apps (table
   gGunkMenuApps, app DEXNAV_APP), with the field shut down; B closes it and the menu comes back. L+R in the field
   opens the same screen through its own event (DexNavUi_FieldEvent below: fade out, close the field, run the proc, reopen
   the field, fade in), the sequence the start menu uses; B there returns to the field.
   Routines (found from the Bag's proc; see docs/GUNK_CHANGES.md row 9): ARM ones without |1. */
#include "dexnav.h"

/* heap, proc */
#define Heap_Create ((void (*)(u32, u32, u32))0x0203064C)           /* parent, id, size */
#define Heap_Delete ((void (*)(u32))0x020306F0)
#define Heap_Free ((void (*)(void *))0x020307B0)
#define Proc_AllocWork ((void *(*)(void *, u32, u32))0x0203159C)    /* proc, size, heap */
#define Proc_FreeWork ((void (*)(void *))0x020315D4)
#define MemFill ((void (*)(void *, u32, u32))0x02082BCC)
#define Key_GetTrg ((u32 (*)(void))0x020362DC)
/* display, BG */
#define BgSys_Init ((void (*)(u32))0x0203F8F4)
#define BgSys_Exit ((void (*)(void))0x0203F9B4)
#define Disp_SetBank ((void (*)(const u32 *))0x020433E0)
#define Bg_SetMode ((void (*)(const u32 *))0x0203FC28)
#define Bg_SetControl ((void (*)(u32, const void *, u32))0x0203FCA0)
#define Bg_ClearScreen ((void (*)(u32))0x020414AC)
#define Bg_LoadScreenReq ((void (*)(u32))0x020409B4)
/* windows, text */
#define BmpWinSys_Init ((void (*)(u32))0x02045088)
#define BmpWinSys_Exit ((void (*)(void))0x020450C8)
#define BmpWin_Create ((void *(*)(u32, u32, u32, u32, u32, u32, u32))0x020450F0)  /* frame, x, y, w, h, pal, dir */
#define BmpWin_Delete ((void (*)(void *))0x020452E8)
#define BmpWin_TransChar ((void (*)(void *))0x02045334)
#define BmpWin_MakeScreen ((void (*)(void *))0x02045374)  /* into the frame's screen buffer; 0x020456F8 clears it */
#define BmpWin_GetBmp ((struct Bmp *(*)(void *))0x02045770)
#define Msg_Create ((void *(*)(u32, u32, u32, u32))0x02045B38)       /* 0, archive, file, heap */
#define Msg_Delete ((void (*)(void *))0x02045C04)
#define Msg_GetString ((void (*)(void *, u32, void *))0x02045CAC)
#define Str_Create ((void *(*)(u32, u32))0x020457B0)                /* length, heap */
#define Str_Delete ((void (*)(void *))0x02045808)
#define Font_Create ((void *(*)(u32, u32, u32, u32, u32))(0x0201D7EC | 1))  /* archive, file, 0, 0, heap */
#define Font_Delete ((void (*)(void *))(0x0201D83C | 1))
#define Print ((void (*)(struct Bmp *, u32, u32, void *, void *, u32))(0x0201C7D0 | 1))  /* x, y, str, font, colour */
/* archives */
#define Arc_Open ((void *(*)(u32, u32))0x020490F4)                  /* archive, heap */
#define Arc_Close ((void (*)(void *))0x02049238)
#define Arc_LoadAlloc ((u8 *(*)(void *, u32, u32))0x02049250)       /* handle, file, heap */

#define HEAP_DEXNAV 0xE          /* the Bag's heap: free while another app runs */
#define HEAP_PARENT 1
#define HEAP_SIZE 0x20000
#define ARC_TEXT 3               /* a/0/0/3 */
#define TEXT_FIELD_COMMON 263
#define MSG_ASK 16               /* "Which Pokémon will you search for?" (patches.dexnav_screen) */
#define MSG_UNSEEN 17            /* "?????" */
#define MSG_NOT_SEEN 26          /* "You haven't seen that Pokémon yet." */
#define ARC_SYSTEM_TEXT 2        /* a/0/0/2 */
#define TEXT_SPECIES 70
#define ARC_FONT 0x17            /* a/0/2/3 */
#define ARC_ICONS 7              /* a/0/0/7: palettes in file 0, species N's 32x32 icon in file 7 + 2N */
#define ICON_FILE(sp) (7 + 2 * (sp))
#define ICON_PALETTES 0
#define ICON_PALETTE ((const u8 *)0x0209E474)  /* arm9: a byte per icon, its palette (0-2) in each nibble */
#define RGCN_DATA 0x30
#define RLCN_DATA 0x28
#define ICON_BYTES 0x400
#define FRAME_ICONS 0            /* in front: the icons, scrolled 4 pixels to sit in their cells */
#define FRAME_PANELS 1
#define BG_PALETTES ((u16 *)0x05000000)
#define PAL_UI 0
#define PAL_ICON 1               /* 1-3: the icon palettes */
#define PAL_SILHOUETTE 4         /* a Pokémon not seen yet */
#define REG_DISPCNT (*(volatile u32 *)0x04000000)
#define REG_POWCNT (*(volatile u16 *)0x04000304)
#define POWCNT_MAIN_ON_TOP 0x8000
#define REG_BLDCNT (*(volatile u16 *)0x04000050)
#define REG_MASTER_BRIGHT (*(volatile u16 *)0x0400006C)
#define REG_MASTER_BRIGHT_SUB (*(volatile u16 *)0x0400106C)
#define DISPCNT_BG0 0x100
#define DISPCNT_BG1 0x200
#define DISPCNT_LAYERS 0x1F00    /* BG0-3, OBJ */
#define REG_DISPCNT_SUB (*(volatile u32 *)0x04001000)
#define SUB_BG_PALETTES ((u16 *)0x05000400)
#define PAD_A 0x0001
#define PAD_B 0x0002
#define PAD_RIGHT 0x0010
#define PAD_LEFT 0x0020
#define PAD_UP 0x0040
#define PAD_DOWN 0x0080
#define COLOUR(letter, shadow, back) ((letter) << 10 | (shadow) << 5 | (back))

/* the grid: DEXNAV_LIST_MAX cells, COLUMNS a row, each a CELL x CELL-tile panel with the icon in it */
#define COLUMNS 6
#define CELL 5
#define GRID_X 1
#define GRID_Y 5
#define ROW_GAP 6

/* GFL's bitmap: 4bpp pixels in 8x8 characters, left to right then down */
struct Bmp {
    u8 *data;
    u16 w, h;
    u16 charBytes;
};

struct DexNavUi {
    void *title, *info;
    void *cell[DEXNAV_LIST_MAX], *icon[DEXNAV_LIST_MAX];
    void *font, *msg, *names, *str;
    u32 count, cursor;
};

/* the Bag's tables (overlay 70: 0x021BBBE0 VRAM banks, mode 1 with BG mode 0, 0x021BBB40 frame 0 control: scroll,
   screen size 0x800, 256x256, screen base 0x1C, character base 0, 0x8000 of characters, priority 3); the panels'
   frame has its own screen (0x1D) and characters (base 4: 0x10000) */
static const u32 sBanks[12] = { 1, 0, 4, 0, 2, 0, 8, 0, 0, 0, 0x200010, 0x200010 };
static const u32 sMode[4] = { 1, 0, 0, 0 };
static const u8 sFrameIcons[32] = { 0xFC, 0xFF, 0xFF, 0xFF, 0xFC, 0xFF, 0xFF, 0xFF, 0, 8, 0, 0, 0, 0, 0, 0,
                                    1, 0, 0x1C, 0, 0, 0x80, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0 };
static const u8 sFramePanels[32] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 0, 0, 0, 0, 0, 0,
                                     1, 0, 0x1D, 4, 0, 0x80, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0 };
/* Black's dark menus: transparent, text, its shadow, frame, panel, backdrop, cursor, a cell, marks */
static const u16 sPalette[9] = { 0x0000, 0x7FFF, 0x294A, 0x4E73, 0x2529, 0x14A5, 0x7E40, 0x318C, 0x7FFF };
#define C_TEXT 1
#define C_SHADOW 2
#define C_FRAME 3
#define C_PANEL 4
#define C_BACKDROP 5
#define C_CURSOR 6
#define C_CELL 7
#define C_MARK 8
#define SILHOUETTE 0x0C63

/* DEXNAV_LIST_MAX is two rows (and there is no division routine to link) */
static u32 RowStart(u32 i)
{
    return i >= COLUMNS ? COLUMNS : 0;
}

static void SetPixel(struct Bmp *b, u32 x, u32 y, u32 c)
{
    u8 *p = b->data + ((y >> 3) * (b->w >> 3) + (x >> 3)) * 32 + (y & 7) * 4 + ((x & 7) >> 1);

    *p = x & 1 ? (*p & 0x0F) | c << 4 : (*p & 0xF0) | c;
}

static void Fill(struct Bmp *b, u32 x0, u32 y0, u32 x1, u32 y1, u32 c)
{
    u32 x, y;

    for (y = y0; y < y1; y++)
        for (x = x0; x < x1; x++)
            SetPixel(b, x, y, c);
}

/* a framed panel: a 2-pixel frame with rounded corners around the inside colour */
static void Panel(struct Bmp *b, u32 frame, u32 inside)
{
    Fill(b, 0, 0, b->w, b->h, 0);
    Fill(b, 1, 0, b->w - 1, b->h, frame);
    Fill(b, 0, 1, b->w, b->h - 1, frame);
    Fill(b, 2, 2, b->w - 2, b->h - 2, inside);
}

static void Show(void *win)
{
    BmpWin_TransChar(win);
    BmpWin_MakeScreen(win);
}

static void PrintMsg(struct DexNavUi *ui, void *win, void *msg, u32 id, u32 x, u32 y)
{
    Msg_GetString(msg, id, ui->str);
    Print(BmpWin_GetBmp(win), x, y, ui->str, ui->font, COLOUR(C_TEXT, C_SHADOW, C_PANEL));
}

/* row i's icon into its window (the window's palette: the icons' or the silhouette's) */
static void Icon(struct DexNavUi *ui, void *arc, u32 i)
{
    u8 *chars = Arc_LoadAlloc(arc, ICON_FILE(DexNav_ListSpecies(i)), HEAP_DEXNAV);
    struct Bmp *b = BmpWin_GetBmp(ui->icon[i]);
    u32 k;

    for (k = 0; k < ICON_BYTES; k++)
        b->data[k] = chars[RGCN_DATA + k];
    Heap_Free(chars);
    Show(ui->icon[i]);
}

/* a cell's panel: the cursor's in the cursor colour; a dot for caught, a ring for seen */
static void Cell(struct DexNavUi *ui, u32 i)
{
    struct Bmp *b = BmpWin_GetBmp(ui->cell[i]);
    u32 mark = DexNav_ListMark(i);

    Panel(b, i == ui->cursor ? C_CURSOR : C_FRAME, C_CELL);
    if (mark >= 2) {
        Fill(b, b->w - 8, b->h - 8, b->w - 4, b->h - 4, C_MARK);
        if (mark == 2)
            Fill(b, b->w - 7, b->h - 7, b->w - 5, b->h - 5, C_CELL);
    }
    Show(ui->cell[i]);
}

/* the info panel: the cursor's species (????? when not seen), and a message under it */
static void Info(struct DexNavUi *ui, u32 msgId)
{
    Panel(BmpWin_GetBmp(ui->info), C_FRAME, C_PANEL);
    if (DexNav_ListMark(ui->cursor) >= 2)
        PrintMsg(ui, ui->info, ui->names, DexNav_ListSpecies(ui->cursor), 12, 6);
    else
        PrintMsg(ui, ui->info, ui->msg, MSG_UNSEEN, 12, 6);
    if (msgId)
        PrintMsg(ui, ui->info, ui->msg, msgId, 12, 22);
    Show(ui->info);
}

static void Redraw(void)
{
    Bg_LoadScreenReq(FRAME_PANELS);
    Bg_LoadScreenReq(FRAME_ICONS);
}

s32 DexNavUi_Init(void *proc, s32 *seq, void *param, void *work)
{
    struct DexNavUi *ui;
    void *arc;
    u8 *pals;
    u32 i;

    Heap_Create(HEAP_PARENT, HEAP_DEXNAV, HEAP_SIZE);
    ui = Proc_AllocWork(proc, sizeof(*ui), HEAP_DEXNAV);
    MemFill(ui, 0, sizeof(*ui));
    REG_BLDCNT = 0;
    BgSys_Init(HEAP_DEXNAV);
    BmpWinSys_Init(HEAP_DEXNAV);
    Disp_SetBank(sBanks);
    Bg_SetMode(sMode);
    Bg_SetControl(FRAME_ICONS, sFrameIcons, 0);
    Bg_SetControl(FRAME_PANELS, sFramePanels, 0);
    Bg_ClearScreen(FRAME_ICONS);
    Bg_ClearScreen(FRAME_PANELS);
    for (i = 0; i < 9; i++)
        BG_PALETTES[PAL_UI * 16 + i] = sPalette[i];
    BG_PALETTES[0] = sPalette[C_BACKDROP];
    arc = Arc_Open(ARC_ICONS, HEAP_DEXNAV);
    pals = Arc_LoadAlloc(arc, ICON_PALETTES, HEAP_DEXNAV);
    for (i = 0; i < 3 * 16; i++)  /* the icons' three palettes */
        BG_PALETTES[PAL_ICON * 16 + i] = ((u16 *)(pals + RLCN_DATA))[i];
    for (i = 1; i < 16; i++)
        BG_PALETTES[PAL_SILHOUETTE * 16 + i] = SILHOUETTE;
    Heap_Free(pals);

    ui->font = Font_Create(ARC_FONT, 0, 0, 0, HEAP_DEXNAV);
    ui->msg = Msg_Create(0, ARC_TEXT, TEXT_FIELD_COMMON, HEAP_DEXNAV);
    ui->names = Msg_Create(0, ARC_SYSTEM_TEXT, TEXT_SPECIES, HEAP_DEXNAV);
    ui->str = Str_Create(0x80, HEAP_DEXNAV);
    ui->count = DexNav_ListCount();
    ui->cursor = DexNav_ListCursor();

    ui->title = BmpWin_Create(FRAME_PANELS, 1, 1, 30, 3, PAL_UI, 1);
    Panel(BmpWin_GetBmp(ui->title), C_FRAME, C_PANEL);
    PrintMsg(ui, ui->title, ui->msg, MSG_ASK, 8, 4);
    Show(ui->title);
    for (i = 0; i < ui->count; i++) {
        u32 x = GRID_X + (i - RowStart(i)) * CELL, y = GRID_Y + (i >= COLUMNS) * ROW_GAP;

        ui->cell[i] = BmpWin_Create(FRAME_PANELS, x, y, CELL, CELL, PAL_UI, 1);
        Cell(ui, i);
        ui->icon[i] = BmpWin_Create(FRAME_ICONS, x, y, 4, 4, DexNav_ListMark(i) >= 2 ?
                                    PAL_ICON + (ICON_PALETTE[DexNav_ListSpecies(i)] & 0xF) : PAL_SILHOUETTE, 1);
        Icon(ui, arc, i);
    }
    Arc_Close(arc);
    ui->info = BmpWin_Create(FRAME_PANELS, 1, 18, 30, 5, PAL_UI, 1);
    Info(ui, 0);
    Redraw();
    /* only our frames on the main screen; the sub screen just its backdrop (for now) */
    REG_DISPCNT = (REG_DISPCNT & ~DISPCNT_LAYERS) | DISPCNT_BG0 | DISPCNT_BG1;
    REG_DISPCNT_SUB &= ~DISPCNT_LAYERS;
    SUB_BG_PALETTES[0] = sPalette[C_BACKDROP];
    REG_POWCNT &= ~POWCNT_MAIN_ON_TOP;  /* the main screen at the bottom (the field has it on top) */
    REG_MASTER_BRIGHT = 0;
    REG_MASTER_BRIGHT_SUB = 0;
    return 1;
}

static void Move(struct DexNavUi *ui, u32 to)
{
    u32 from = ui->cursor;

    if (to >= ui->count || to == from)
        return;
    ui->cursor = to;
    Cell(ui, from);
    Cell(ui, to);
    Info(ui, 0);
    Redraw();
}

/* 1 closes: B, or a pick (the parameter word set to 1) */
s32 DexNavUi_Main(void *proc, s32 *seq, void *param, void *work)
{
    struct DexNavUi *ui = work;
    u32 trg = Key_GetTrg(), c = ui->cursor, first = RowStart(c);
    u32 last = first + COLUMNS - 1 < ui->count ? first + COLUMNS - 1 : ui->count - 1;

    if (trg & PAD_B)
        return 1;
    if (trg & PAD_A) {
        if (DexNav_ListPick(c) == 1) {
            *(u32 *)param = 1;
            return 1;
        }
        Info(ui, MSG_NOT_SEEN);
        Redraw();
    } else if (trg & PAD_RIGHT) {
        Move(ui, c < last ? c + 1 : first);
    } else if (trg & PAD_LEFT) {
        Move(ui, c > first ? c - 1 : last);
    } else if (trg & (PAD_UP | PAD_DOWN)) {
        Move(ui, c >= COLUMNS ? c - COLUMNS : c + COLUMNS < ui->count ? c + COLUMNS : ui->count - 1);
    }
    return 0;
}

s32 DexNavUi_Exit(void *proc, s32 *seq, void *param, void *work)
{
    struct DexNavUi *ui = work;
    u32 i;

    for (i = 0; i < ui->count; i++) {
        BmpWin_Delete(ui->icon[i]);
        BmpWin_Delete(ui->cell[i]);
    }
    BmpWin_Delete(ui->info);
    BmpWin_Delete(ui->title);
    Str_Delete(ui->str);
    Msg_Delete(ui->names);
    Msg_Delete(ui->msg);
    Font_Delete(ui->font);
    BmpWinSys_Exit();
    BgSys_Exit();
    Proc_FreeWork(proc);
    Heap_Delete(HEAP_DEXNAV);
    return 1;
}

const u32 gDexNavUiProc[3] = { (u32)DexNavUi_Init, (u32)DexNavUi_Main, (u32)DexNavUi_Exit };

#define NO_OVERLAY_PROC 0xFFFFFFFF

/* the menu's side: the app's parameters (a static word the menu's free step leaves alone: 1 when a row was picked)
   and its return (0: back to the menu; a pick closes the menu for the search) */
static u32 sParam;

void *DexNavUi_Setup(void *menu)
{
    sParam = 0;
    return &sParam;
}

void DexNavUi_Free(void *param)
{
}

u32 DexNavUi_Return(void *menu, void *param)
{
    return *(u32 *)param ? Gunk_MenuClose(menu, ITEM_EVENT_DEXNAV_PICK) : 0;
}

/* L+R in the field: the screen as an event of its own, the way the start menu's event runs an app (overlay 10,
   FUN_overlay_d_10__021607e0): fade out, close the field, run the screen's proc, open the field, fade in. A pick has
   set sPick, so the search starts once the field runs again. */
#define Event_Create ((void *(*)(void *, void *, void *, u32))(0x020122C0 | 1))  /* gsys, parent, func, work size */
#define Event_GetWork ((void *(*)(void *))(0x020124E8 | 1))
#define Event_Call ((void (*)(void *, void *))(0x02012374 | 1))                /* event, sub-event */
#define GameSys_CallProc ((void (*)(void *, u32, const void *, void *))(0x020120B4 | 1))  /* overlay, proc, param */
#define GameSys_ProcRunning ((u32 (*)(void *))(0x020120F0 | 1))
#define GameSys_FieldSys ((void *(*)(void *))(0x0201210C | 1))
#define Event_FieldClose ((void *(*)(void *, void *))(0x020144DC | 1))           /* gsys, fieldSys */
#define Event_FieldOpen ((void *(*)(void *))(0x020145CC | 1))                    /* gsys */
#define Event_FadeOut ((void *(*)(void *, void *, u32, u32))(0x021BE8D4 | 1))    /* gsys, fieldSys, 0, 0 */
#define Event_FadeIn ((void *(*)(void *, void *, u32, u32, u32, u32, u32))(0x021BE92C | 1))
#define Field_Restore ((void (*)(void))(0x02188DA0 | 1))  /* what the menu runs after opening the field */
#define Field_RestoreDisplay ((void (*)(void *))(0x02188DB0 | 1))

struct FieldScreen {
    void *gsys, *fieldSys;
};

static u32 FieldScreenEvent(void *event, s32 *seq, void *work)
{
    struct FieldScreen *w = work;

    switch (*seq) {
    case 0:
        Event_Call(event, Event_FadeOut(w->gsys, w->fieldSys, 0, 0));
        break;
    case 1:
        Event_Call(event, Event_FieldClose(w->gsys, w->fieldSys));
        break;
    case 2:
        GameSys_CallProc(w->gsys, NO_OVERLAY_PROC, gDexNavUiProc, DexNavUi_Setup(0));
        break;
    case 3:
        if (GameSys_ProcRunning(w->gsys))
            return 0;
        Event_Call(event, Event_FieldOpen(w->gsys));
        break;
    case 4:
        w->fieldSys = GameSys_FieldSys(w->gsys);
        Field_Restore();
        Field_RestoreDisplay(w->fieldSys);
        Event_Call(event, Event_FadeIn(w->gsys, w->fieldSys, 0, 0, 0, 0, 0));
        break;
    default:
        return 1;
    }
    ++*seq;
    return 0;
}

void *DexNavUi_FieldEvent(void *gsys, void *fieldSys)
{
    void *event = Event_Create(gsys, 0, FieldScreenEvent, sizeof(struct FieldScreen));
    struct FieldScreen *w = Event_GetWork(event);

    w->gsys = gsys;
    w->fieldSys = fieldSys;
    return event;
}

/* the start menu's apps (retail table at 0x021712CC: overlay, proc data, setup, return, alt, free), the DexNav last */
#define NO_OVERLAY 0xFFFFFFFF
#define APP_FREE 0x0216171D
const u32 gGunkMenuApps[DEXNAV_APP + 1][6] = {
    { 0x5B, 0x021BED00, 0x02160A95, 0x02160C89, 0, APP_FREE },
    { 0xD4, 0x021C9938, 0x02160D6D, 0x02160DDD, 0, APP_FREE },
    { 0x46, 0x021BB96C, 0x02160FE1, (u32)Gunk_BagReturn, 0, APP_FREE },  /* the bag; retail return 0x02161071 */
    { 0x6F, 0x02172614, 0x0216117D, 0x021611E1, 0, APP_FREE },
    { 0, 0, 0, 0, 0x02161351, APP_FREE },
    { 0x44, 0x021BB5C8, 0x02161309, 0x02161341, 0, APP_FREE },
    { 0x83, 0x021DC800, 0x02160E09, 0x02160F89, 0, APP_FREE },
    { 0x48, 0x021BBB80, 0x02161215, 0x02161281, 0, APP_FREE },
    { 0x80, 0x021CA658, 0x02161379, 0x021613A5, 0, APP_FREE },
    { NO_OVERLAY, 0x021C7768, 0x021613CD, 0x02161485, 0, 0x02161535 },
    { 0xC3, 0x02208C40, 0x02161555, 0x02161611, 0, APP_FREE },
    { 0xBB, 0x0220B294, 0x0216163D, 0x02161669, 0, APP_FREE },
    { NO_OVERLAY, (u32)gDexNavUiProc, (u32)DexNavUi_Setup, (u32)DexNavUi_Return, 0, (u32)DexNavUi_Free },
};
