typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

#define REG16(address) (*(volatile u16 *)(address))
#define REG_DISPCNT REG16(0x04000000)
#define REG_BG1CNT REG16(0x0400000A)
#define REG_BG2CNT REG16(0x0400000C)
#define REG_BG3CNT REG16(0x0400000E)
#define REG_BG1HOFS REG16(0x04000014)
#define REG_BG1VOFS REG16(0x04000016)
#define REG_BG2HOFS REG16(0x04000018)
#define REG_BG2VOFS REG16(0x0400001A)
#define REG_BG3HOFS REG16(0x0400001C)
#define REG_BG3VOFS REG16(0x0400001E)
#define REG_BLDCNT REG16(0x04000050)
#define REG_BLDALPHA REG16(0x04000052)
#define REG_BLDY REG16(0x04000054)
#define KEYS_PRESSED REG16(0x03003D14)

#define LEVEL_INDEX (*(volatile u32 *)0x03000988)
#define EXPERIENCE (*(volatile u32 *)0x030007D8)
#define EXPERIENCE_MIRROR (*(volatile u32 *)0x03000984)
#define HP_CURRENT REG16(0x030007D0)
#define HP_MAXIMUM REG16(0x030007CC)
#define KI_CURRENT REG16(0x030007C8)
#define KI_MAXIMUM REG16(0x030007C4)
#define OPTION_BYTES ((volatile u8 *)0x03000020)
#define ITEM_COUNTS ((volatile u8 *)0x0300004E)
#define ITEM_TYPES 0x081C7A84u
#define ITEM_RECORDS 0x081C6224u
#define ITEM_UNNAMED 12u
#define QUEST_RECORDS 0x085439E0u
#define QUEST_TOTAL 75u
#define COMPLETED_BITS ((volatile u8 *)0x03000038)
#define LIST_ROWS 9u
#define LIST_ROW_HEIGHT 8
#define LIST_TOP 40
#define LIST_X 24
#define FADE_FRAMES 0x10u

#define LEVEL_TABLE 0x080114A8u
#define LEVEL_LAST 24
#define ITEM_SLOTS 34

#define PALETTE_BASE 0x05000000u
#define VRAM_BASE 0x06000000u
#define MAP_UPPER 0x0600E800u
#define MAP_LOWER 0x0600F000u
#define MAP_BACKDROP 0x0600F800u
#define PAGE_STATE ((volatile u16 *)0x0600E7FCu)
#define CLOSE_FLAG (*(volatile u16 *)0x03006000u)
#define PAGE_DRAWN 0x5A00u
#define PAGE_TILE 256u

#define CNT_UPPER 0x1D83
#define CNT_LOWER 0x1E83
#define CNT_BACKDROP 0x1F83
#define DISPLAY_PAGE 0x0E00
#define DISPLAY_FIELD 0x1F40
#define BLEND_CONTROL 0x0844
#define FADE_CONTROL 0x00FFu
#define BLEND_ALPHA 0x0010
#define BLEND_ALPHA_RETAIL 0x0C10

#define INK_SHADOW 1u
#define INK_WHITE 2u
#define INK_GREEN 4u
#define INK_RED 5u
#define INK_GOLD 0x29u

#define PANEL_X 16
#define PANEL_Y 32
#define PANEL_WIDTH 208
#define TITLE_X 32
#define TITLE_WIDTH 64
#define LEVEL_Y 18
#define BAR_X 78
#define BAR_WIDTH 75u
#define BAR_HEIGHT 8
#define HP_BAR_Y 40
#define EP_BAR_Y 56
#define RATIO_RIGHT 152
#define HP_RATIO_Y 43
#define EP_RATIO_Y 59
#define VALUE_RIGHT 224
#define EXP_Y 99
#define NEXT_Y 107
#define LIST_Y 64
#define OPTION_ROWS 3u
#define OPTION_TOTAL 4u
#define OPTION_SAVE_ROW 3u
#define OPTION_ROW_HEIGHT 24
#define OPTION_ROW_TILES 78u
#define KNOB_X 144
#define KNOB_TRAVEL 56u
#define KNOB_WIDTH 8
#define KNOB_HEIGHT 16

#define KEY_A 0x0001
#define KEY_B 0x0002
#define KEY_RIGHT 0x0010
#define KEY_LEFT 0x0020
#define KEY_UP 0x0040
#define KEY_DOWN 0x0080
#define KEY_R 0x0100
#define KEY_L 0x0200

#define SOUND 0x0800ACFFu
#define LEAVE 0x08009799u
#define OPTIONS_PERSIST 0x08000785u
#define SFX_VOLUME 0x0800A9A3u
#define MUSIC_VOLUME 0x0800A9CDu
#define OPTIONS_PERSIST_SAVE 0x08000785u
#define SAVE_CHECK 0x0800084Bu
#define SAVE_WRITE 0x080008B5u
#define PROFILE_BASE 0x03000028u
#define SAVE_SLOT 0u

#define TAB_OPTIONS 0u
#define TAB_QUESTS 1u
#define TAB_STATUS 2u
#define TAB_ITEMS 3u

#define STR_LEVEL 0
#define STR_EMPTY 1
#define STR_NO_QUESTS 2

#define LAYOUT_SURFACE_TILE 0
#define LAYOUT_PANEL_TILE 1
#define LAYOUT_PAGE_WORDS 2
#define LAYOUT_ROW_WORDS 3

extern const u32 asset_palette[128];
extern const u32 asset_starfield[4096];
extern const u32 asset_page[];
extern const u32 asset_option_rows[];
extern const u16 asset_map[1200];
extern const u16 asset_font[];
extern const u8 asset_knob[256];
extern const u16 asset_layout[4];
extern const u16 asset_string_offset[];
extern const u8 asset_strings[];

static const char save_label[] = "SAVE GAME";
static const char save_confirm[] = "OVERWRITE SLOT 1?";
static const u8 option_byte[OPTION_ROWS] = {0, 2, 1};
static const u8 option_limit[OPTION_ROWS] = {2, 8, 8};
static const u32 decimal_scale[10] = {1000000000u, 100000000u, 10000000u, 1000000u,
                                      100000u, 10000u, 1000u, 100u, 10u, 1u};

static void copy_words(u32 address, const u32 *from, u32 count) {
    volatile u32 *to = (volatile u32 *)address;
    while (count--) {
        to[0] = from[0];
        to++;
        from++;
    }
}

static u32 divide(u32 value, u32 by) {
    u32 quotient = 0;
    if (by == 0) {
        return 0;
    }
    while (value >= by) {
        value -= by;
        quotient++;
    }
    return quotient;
}

static void plot(int x, int y, u32 colour) {
    volatile u16 *map = (volatile u16 *)MAP_LOWER;
    volatile u16 *pair;
    u32 tile;
    u32 value;
    if ((u32)x >= 240 || (u32)y >= 160) {
        return;
    }
    tile = map[(y >> 3) * 32 + (x >> 3)];
    if (tile < asset_layout[LAYOUT_SURFACE_TILE]) {
        return;
    }
    pair = (volatile u16 *)(VRAM_BASE + tile * 64 + (y & 7) * 8 + (x & 6));
    value = pair[0];
    if (x & 1) {
        value = (value & 0x00FF) | (colour << 8);
    } else {
        value = (value & 0xFF00) | colour;
    }
    pair[0] = (u16)value;
}

static u32 glyph_width(u32 code) {
    u32 index = asset_font[code & 0xFF];
    return index ? asset_font[index] : 0;
}

static u32 text_advance(const char *text) {
    u32 total = 0;
    while (text[0]) {
        total += glyph_width((u8)text[0]) + 1;
        text++;
    }
    return total;
}

static void draw_text(int x, int y, const char *text, u32 ink) {
    while (text[0]) {
        u32 index = asset_font[(u8)text[0]];
        u32 width = index ? asset_font[index] : 0;
        u32 pass;
        for (pass = 0; pass < 2; pass++) {
            u32 column;
            for (column = 0; column < width; column++) {
                u32 mask = asset_font[index + 1 + column];
                int row;
                for (row = 0; mask; row++, mask >>= 1) {
                    if (mask & 1) {
                        plot(x + (int)column + 1 - (int)pass, y + row + 1 - (int)pass,
                             pass ? ink : INK_SHADOW);
                    }
                }
            }
        }
        x += (int)width + 1;
        text++;
    }
}

static void draw_right(int right, int y, const char *text, u32 ink) {
    draw_text(right - (int)text_advance(text), y, text, ink);
}

static void draw_centred(int x, int width, int y, const char *text, u32 ink) {
    draw_text(x + (width - (int)text_advance(text)) / 2, y, text, ink);
}

static char *put_number(char *out, u32 value) {
    u32 place;
    u32 started = 0;
    for (place = 0; place < 10; place++) {
        u32 scale = decimal_scale[place];
        u32 digit = 0;
        while (value >= scale) {
            value -= scale;
            digit++;
        }
        if (digit || started || place == 9) {
            out[0] = (char)('0' + digit);
            out++;
            started = 1;
        }
    }
    out[0] = 0;
    return out;
}

static const char *string_at(u32 index) {
    return (const char *)asset_strings + asset_string_offset[index];
}

static void draw_bar(int y, u32 current, u32 maximum, u32 colour) {
    u32 width;
    u32 column;
    int row;
    if (current > maximum) {
        current = maximum;
    }
    width = divide(current * BAR_WIDTH, maximum);
    for (row = 0; row < BAR_HEIGHT; row++) {
        for (column = 0; column < width; column++) {
            plot(BAR_X + (int)column, y + row, colour);
        }
    }
}

static void draw_ratio(int y, u32 current, u32 maximum) {
    char text[24];
    char *end = put_number(text, current);
    end[0] = '/';
    put_number(end + 1, maximum);
    draw_right(RATIO_RIGHT, y, text, INK_WHITE);
}

static void draw_value(int y, u32 value) {
    char text[12];
    put_number(text, value);
    draw_right(VALUE_RIGHT, y, text, INK_WHITE);
}

static u32 next_level_threshold(void) {
    u32 index = LEVEL_INDEX;
    const u32 *row;
    if (index > LEVEL_LAST) {
        index = LEVEL_LAST;
    }
    row = (const u32 *)(LEVEL_TABLE + index * 16 + 16);
    return row[0];
}

static void draw_status(void) {
    char text[32];
    const char *format = string_at(STR_LEVEL);
    char *out = text;
    while (format[0] && format[0] != '%') {
        out[0] = format[0];
        out++;
        format++;
    }
    put_number(out, LEVEL_INDEX + 1);
    draw_centred(TITLE_X, TITLE_WIDTH, LEVEL_Y, text, INK_GOLD);
    draw_bar(HP_BAR_Y, HP_CURRENT, HP_MAXIMUM, INK_RED);
    draw_ratio(HP_RATIO_Y, HP_CURRENT, HP_MAXIMUM);
    draw_bar(EP_BAR_Y, KI_CURRENT, KI_MAXIMUM, INK_GREEN);
    draw_ratio(EP_RATIO_Y, KI_CURRENT, KI_MAXIMUM);
    draw_value(EXP_Y, EXPERIENCE);
    draw_value(NEXT_Y, next_level_threshold() - EXPERIENCE_MIRROR);
}

static void draw_options(u32 selected, u8 *state) {
    u32 row;
    for (row = 0; row < OPTION_ROWS; row++) {
        u32 idle = row != selected;
        u32 value = OPTION_BYTES[option_byte[row]];
        const u8 *knob = asset_knob + idle * KNOB_WIDTH * KNOB_HEIGHT;
        int x;
        int y = PANEL_Y + (int)row * OPTION_ROW_HEIGHT + (int)idle;
        int line;
        int column;
        if (!idle) {
            u32 words = asset_layout[LAYOUT_ROW_WORDS];
            copy_words(VRAM_BASE + (asset_layout[LAYOUT_PANEL_TILE] + row * OPTION_ROW_TILES) * 64,
                       asset_option_rows + row * words, words);
        }
        if (value > option_limit[row]) {
            value = option_limit[row];
        }
        x = KNOB_X + (int)divide(value * KNOB_TRAVEL, option_limit[row]);
        for (line = 0; line < KNOB_HEIGHT; line++) {
            for (column = 0; column < KNOB_WIDTH; column++) {
                u32 colour = knob[line * KNOB_WIDTH + column];
                if (colour) {
                    plot(x + column, y + line, colour);
                }
            }
        }
    }
    {
        u32 idle = selected != OPTION_SAVE_ROW;
        draw_text(LIST_X, PANEL_Y + (int)OPTION_SAVE_ROW * OPTION_ROW_HEIGHT + (int)idle,
                  state[5] ? save_confirm : save_label,
                  idle ? INK_WHITE : INK_GOLD);
    }
}

static char *append(char *out, const char *text, u32 room) {
    while (text[0] && room > 1) {
        out[0] = text[0];
        out++;
        text++;
        room--;
    }
    out[0] = 0;
    return out;
}

static void draw_entry(int x, int y, u32 count, const char *name) {
    char text[48];
    char *out = put_number(text, count);
    out[0] = ' ';
    append(out + 1, name, (u32)sizeof(text) - (u32)(out + 1 - text));
    draw_text(x, y, text, INK_WHITE);
}

static u32 item_row_count(void) {
    u32 total = 0;
    u32 slot;
    for (slot = 0; slot < ITEM_SLOTS; slot++) {
        if (ITEM_COUNTS[slot] && *(const u8 *)(ITEM_TYPES + slot) != ITEM_UNNAMED) {
            total++;
        }
    }
    return total;
}

static u32 quest_row_count(void) {
    u32 total = 0;
    u32 record;
    for (record = 0; record < QUEST_TOTAL; record++) {
        if (!*(const u32 *)(QUEST_RECORDS + record * 4)) {
            continue;
        }
        if (!*(const u32 *)(*(const u32 *)(QUEST_RECORDS + record * 4))) {
            continue;
        }
        if (COMPLETED_BITS[record >> 3] & (1u << (record & 7))) {
            total++;
        }
    }
    return total;
}

static void draw_items(u32 start) {
    u32 slot;
    u32 row = 0;
    if (item_row_count() == 0) {
        draw_centred(PANEL_X, PANEL_WIDTH, LIST_Y, string_at(STR_EMPTY), INK_RED);
        return;
    }
    for (slot = 0; slot < ITEM_SLOTS; slot++) {
        u32 count = ITEM_COUNTS[slot];
        u32 type = *(const u8 *)(ITEM_TYPES + slot);
        const u32 *record;
        if (!count || type == ITEM_UNNAMED) {
            continue;
        }
        if (row < start) {
            row++;
            continue;
        }
        if (row - start >= LIST_ROWS) {
            break;
        }
        record = (const u32 *)(ITEM_RECORDS + type * 8);
        draw_entry(LIST_X, LIST_TOP + (int)(row - start) * LIST_ROW_HEIGHT, count,
                   (const char *)(count == 1 ? record[0] : record[1]));
        row++;
    }
}

static void draw_quests(u32 start) {
    u32 record;
    u32 row = 0;
    if (quest_row_count() == 0) {
        draw_centred(PANEL_X, PANEL_WIDTH, LIST_Y, string_at(STR_NO_QUESTS), INK_RED);
        return;
    }
    for (record = 0; record < QUEST_TOTAL; record++) {
        u32 entry = *(const u32 *)(QUEST_RECORDS + record * 4);
        u32 name = entry ? *(const u32 *)entry : 0;
        if (!name || !(COMPLETED_BITS[record >> 3] & (1u << (record & 7)))) {
            continue;
        }
        if (row < start) {
            row++;
            continue;
        }
        if (row - start >= LIST_ROWS) {
            break;
        }
        draw_text(LIST_X, LIST_TOP + (int)(row - start) * LIST_ROW_HEIGHT, (const char *)name,
                  INK_WHITE);
        row++;
    }
}

static u32 list_length(u32 tab) {
    return tab == TAB_ITEMS ? item_row_count() : quest_row_count();
}

static u32 list_start(u8 *state, u32 tab) {
    u32 total = list_length(tab);
    u32 room = total > LIST_ROWS ? total - LIST_ROWS : 0;
    u32 start = state[5];
    if (start > room) {
        start = room;
        state[5] = (u8)start;
    }
    return start;
}

static void write_scroll(void) {
    u32 drift = (0u - (PAGE_STATE[1] >> 2)) & 0x7F;
    REG_BG1HOFS = 0;
    REG_BG1VOFS = 0;
    REG_BG2HOFS = 0;
    REG_BG2VOFS = 0;
    REG_BG3HOFS = (u16)drift;
    REG_BG3VOFS = (u16)drift;
}

static void rebuild(u32 tab, u32 selected, u8 *state) {
    volatile u16 *upper = (volatile u16 *)MAP_UPPER;
    volatile u16 *lower = (volatile u16 *)MAP_LOWER;
    volatile u16 *backdrop = (volatile u16 *)MAP_BACKDROP;
    u32 words = asset_layout[LAYOUT_PAGE_WORDS];
    u32 row;
    u32 column;
    u32 index;

    REG_BG1CNT = CNT_UPPER;
    REG_BG2CNT = CNT_LOWER;
    REG_BG3CNT = CNT_BACKDROP;
    copy_words(PALETTE_BASE, asset_palette, 128);
    copy_words(VRAM_BASE, asset_starfield, 4096);
    copy_words(VRAM_BASE + PAGE_TILE * 64, asset_page + tab * words, words);
    for (row = 0; row < 20; row++) {
        for (column = 0; column < 30; column++) {
            upper[row * 32 + column] = asset_map[row * 30 + column];
            lower[row * 32 + column] = asset_map[600 + row * 30 + column];
        }
    }
    for (index = 0; index < 1024; index++) {
        backdrop[index] = (u16)(((index >> 5) & 15) * 16 + (index & 15));
    }
    if (tab == TAB_STATUS) {
        draw_status();
    } else if (tab == TAB_OPTIONS) {
        draw_options(selected, state);
    } else if (tab == TAB_ITEMS) {
        draw_items(list_start(state, TAB_ITEMS));
    } else {
        draw_quests(list_start(state, TAB_QUESTS));
    }
    write_scroll();
    REG_BLDCNT = BLEND_CONTROL;
    REG_BLDALPHA = BLEND_ALPHA;
    REG_DISPCNT = DISPLAY_PAGE;
}

static u32 page_code(u8 *state) {
    u32 code = state[4];
    if (code < 0x80 || (code & 0x70)) {
        code = 0x80 | TAB_STATUS;
        state[4] = (u8)code;
    }
    return code;
}

void menu_install(u8 *state) {
    CLOSE_FLAG = 0;
    state[4] = (u8)(0x80 | TAB_STATUS);
    state[5] = 0;
    state[6] = 0;
    state[7] = 0;
    rebuild(TAB_STATUS, 0, state);
    PAGE_STATE[0] = (u16)(PAGE_DRAWN | TAB_STATUS);
}

void menu_draw(u8 *state) {
    u32 code = page_code(state);
    u32 drawn = PAGE_DRAWN | (code & 0x0F);
    if (REG_BG1CNT != CNT_UPPER || PAGE_STATE[0] != drawn) {
        rebuild(code & 3, (code >> 2) & 3, state);
        PAGE_STATE[0] = (u16)drawn;
    }
}

static void save_game(u8 *state) {
    if (((u32 (*)(u32))SAVE_CHECK)(SAVE_SLOT) && state[5] == 0) {
        state[5] = 1;
        PAGE_STATE[0] = 0;
        return;
    }
    ((void (*)(void))OPTIONS_PERSIST_SAVE)();
    ((void (*)(void *, u32))SAVE_WRITE)((void *)PROFILE_BASE, SAVE_SLOT);
    state[5] = 0;
    PAGE_STATE[0] = 0;
}

static void step_option(u8 *state, u32 pressed, u32 tab, u32 row) {
    u32 limit = option_limit[row];
    u32 before = OPTION_BYTES[option_byte[row]];
    u32 value = before;
    if (pressed & KEY_UP) {
        if (row > 0) {
            state[4] = (u8)(0x80 | ((row - 1) << 2) | tab);
            ((void (*)(int))SOUND)(0);
        }
        return;
    }
    if (pressed & KEY_DOWN) {
        if (row + 1 < OPTION_TOTAL) {
            state[4] = (u8)(0x80 | ((row + 1) << 2) | tab);
            ((void (*)(int))SOUND)(0);
        }
        return;
    }
    if (row == OPTION_SAVE_ROW) {
        if (pressed & KEY_A) {
            save_game(state);
        }
        return;
    }
    if (pressed & KEY_RIGHT) {
        if (value < limit) {
            value++;
        }
    } else if (pressed & KEY_LEFT) {
        if (value > 0) {
            value--;
        }
    } else if ((pressed & KEY_A) && row == 0) {
        value = value >= limit ? 0 : value + 1;
    }
    if (value == before) {
        return;
    }
    OPTION_BYTES[option_byte[row]] = (u8)value;
    if (row == 1) {
        ((void (*)(u32))SFX_VOLUME)(value);
    } else if (row == 2) {
        ((void (*)(u32))MUSIC_VOLUME)(value);
    }
    ((void (*)(int))SOUND)(0);
    PAGE_STATE[0] = 0;
}

int menu_update(u8 *state) {
    u32 pressed = KEYS_PRESSED;
    u32 code = page_code(state);
    u32 tab = code & 3;
    PAGE_STATE[1] = (u16)(PAGE_STATE[1] + 1);
    write_scroll();
    if (state[7]) {
        REG_BLDCNT = FADE_CONTROL;
        if (state[7] <= FADE_FRAMES) {
            REG_BLDY = state[7];
            state[7]++;
            return 0;
        }
        REG_BLDY = FADE_FRAMES;
        REG_BLDALPHA = BLEND_ALPHA_RETAIL;
        ((void (*)(void))OPTIONS_PERSIST)();
        ((void (*)(int))SOUND)(0);
        CLOSE_FLAG = 1;
        ((void (*)(void))LEAVE)();
        REG_DISPCNT = DISPLAY_FIELD;
        return 0;
    }
    if (state[6]) {
        u32 step = state[6];
        if (step < FADE_FRAMES) {
            REG_BLDALPHA = (u16)((step << 8) | (FADE_FRAMES - step));
            state[6] = (u8)(step + 1);
        } else if (step < 2u * FADE_FRAMES) {
            REG_BLDALPHA = (u16)(((2u * FADE_FRAMES - step) << 8) | (step - FADE_FRAMES));
            state[6] = (u8)(step + 1);
        } else {
            REG_BLDALPHA = BLEND_ALPHA;
            state[6] = 0;
        }
        if (step == FADE_FRAMES) {
            PAGE_STATE[0] = 0;
        }
        return 0;
    }
    if ((pressed & KEY_B) && tab == TAB_OPTIONS && state[5]) {
        state[5] = 0;
        PAGE_STATE[0] = 0;
        return 0;
    }
    if (pressed & KEY_B) {
        state[7] = 1;
        return 0;
    }
    if (pressed & (KEY_L | KEY_R)) {
        tab = (tab + ((pressed & KEY_R) ? 1 : 3)) & 3;
        state[4] = (u8)(0x80 | tab);
        state[5] = 0;
        state[6] = 1;
        return 0;
    }
    if (tab == TAB_OPTIONS) {
        step_option(state, pressed, tab, (code >> 2) & 3);
    } else {
        u32 total = list_length(tab);
        u32 room = total > LIST_ROWS ? total - LIST_ROWS : 0;
        u32 start = state[5];
        if (start > room) {
            start = room;
        }
        if ((pressed & KEY_DOWN) && start < room) {
            start++;
        } else if ((pressed & KEY_UP) && start > 0) {
            start--;
        }
        if (start != state[5]) {
            state[5] = (u8)start;
            PAGE_STATE[0] = 0;
        }
    }
    return 0;
}
