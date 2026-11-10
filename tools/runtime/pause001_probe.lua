local done_path = rom011_marker_path
assert(done_path and #done_path > 0, "marker path not provided")
local DIR = done_path:gsub("[^/\\]+$", "")
local TAG = os.getenv("C_UI_TAG") or "c"
local LIMIT = tonumber(os.getenv("C_UI_LIMIT") or "") or 6000
local SHOT_EVERY = tonumber(os.getenv("C_UI_SHOT_EVERY") or "") or 20
local SHOT_FROM = tonumber(os.getenv("C_UI_SHOT_FROM") or "") or 600
local KEY_WORD = 0x03003D14
local SHADOW_OAM = 0x0202BE24

local A, B, SELECT, START = 0x01, 0x02, 0x04, 0x08
local RIGHT, LEFT, UP, DOWN = 0x10, 0x20, 0x40, 0x80
local R_SHOULDER, L_SHOULDER = 0x100, 0x200

local PAGE = 2300
local PRESSES = { { 2320, START }, { 2380, R_SHOULDER }, { 2440, R_SHOULDER },
                  { 2500, L_SHOULDER }, { 2520, B } }
local RAM_FRAMES = {}
for token in string.gmatch(os.getenv("C_UI_RAM_FRAMES") or "", "[^,]+") do
    RAM_FRAMES[tonumber(token)] = true
end
local BG_FRAMES = {}
for token in string.gmatch(os.getenv("C_UI_BG_FRAME") or "", "[^,]+") do
    BG_FRAMES[tonumber(token)] = true
end
local START_AT = tonumber(os.getenv("C_UI_START_AT") or "") or 0
local START_EVERY = tonumber(os.getenv("C_UI_START_EVERY") or "") or 0
local STATE_FRAME = tonumber(os.getenv("C_UI_STATE_FRAME") or "") or 0
local STATE_PATH = os.getenv("C_UI_STATE_PATH") or ""

local function row_keys(frame)
    for _, press in ipairs(PRESSES) do
        if frame >= press[1] and frame < press[1] + 4 then return press[2] end
    end
    return 0
end

local ROUTE = os.getenv("C_UI_ROUTE") or "save"
local TAP_FROM = tonumber(os.getenv("C_UI_TAP_FROM") or "") or 200
local TAP_TO = tonumber(os.getenv("C_UI_TAP_TO") or "") or 760
local DOWN_AT = tonumber(os.getenv("C_UI_DOWN_AT") or "") or 0
local A_AT = tonumber(os.getenv("C_UI_A_AT") or "") or 0
local DUMP_FRAMES = {}
for token in string.gmatch(os.getenv("C_UI_DUMP_FRAMES") or "", "[^,]+") do
    DUMP_FRAMES[tonumber(token)] = true
end
local MIRROR = 0x02029b94
local PROFILE = 0x03000028
local PC_WATCH = os.getenv("C_UI_PC_WATCH") or ""
local pc_hits = 0
local pc_frame = 0
local pc_log = nil
if PC_WATCH ~= "" then
    pc_log = assert(io.open(DIR .. TAG .. "-pcwatch.csv", "w"), "cannot open the pc watch log")
    pc_log:write("frame,hit_pc,pc,lr\n")
    pc_log:flush()
    for token in string.gmatch(PC_WATCH, "[^,]+") do
        local site = tonumber(token, 16)
        local ok = pcall(function()
            emu:setBreakpoint(function()
                pc_hits = pc_hits + 1
                local pc = "?"
                local lr = "?"
                pcall(function() pc = string.format("%08X", emu:readRegister("pc")) end)
                pcall(function() lr = string.format("%08X", emu:readRegister("lr")) end)
                pc_log:write(string.format("%d,%08X,%s,%s\n", pc_frame, site, pc, lr))
                pc_log:flush()
            end, site)
        end)
        if not ok then
            pc_log:write(string.format("arm-failed,%08X\n", site))
            pc_log:flush()
        end
    end
end
local keys_log = assert(io.open(DIR .. TAG .. "-keys.csv", "w"), "cannot open the key log")
keys_log:write("frame,keyinput,menu_key,keys_sent\n")
keys_log:flush()

local frame_log = assert(io.open(DIR .. TAG .. "-frame.csv", "w"), "cannot open the frame log")
frame_log:write("frame,dispcnt,bldcnt,bldalpha,bldy,state_word,pause_state,outer_state,map_word,key_word,bgpal14_xor,bgpal15_xor,objpal14_xor,objpal15_xor,close_word\n")
frame_log:flush()

local use_native_read32 = pcall(function() return emu:read32(0x03003B64) end)
local function read32(addr)
    if use_native_read32 then return emu:read32(addr) end
    return emu:read16(addr) | (emu:read16(addr + 2) << 16)
end

local function note_error(where, err)
    local handle = io.open(DIR .. TAG .. "-errors.txt", "a")
    if handle then
        handle:write(string.format("%s frame=%s error=%s\n", where, tostring(frame), tostring(err)))
        handle:close()
    end
end

local function bank_xor(base)
    local value = 0
    for i = 0, 15 do
        value = value ~ emu:read16(base + i * 2)
    end
    return value
end

local frame_errors = 0
local function frame_sample(n)
    local ok, err = pcall(function()
        frame_log:write(string.format("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
            n, emu:read16(0x04000000), emu:read16(0x04000050), emu:read16(0x04000052),
            emu:read16(0x04000054), read32(0x03003B64), read32(0x03000598),
            read32(0x03000590), read32(0x03000600), emu:read16(KEY_WORD),
            bank_xor(0x050001C0), bank_xor(0x050001E0), bank_xor(0x050003C0), bank_xor(0x050003E0),
            emu:read16(0x02029DA8)))
    end)
    if not ok then
        frame_errors = frame_errors + 1
        if frame_errors <= 20 then note_error("frame_sample", err) end
    end
    frame_log:flush()
end

local function dump_state(frame)
    local path = string.format("%sstate-%s-%05d.csv", DIR, TAG, frame)
    local handle = io.open(path, "w")
    if not handle then return end
    handle:write("space,offset,value\n")
    for offset = 0, 0x1FF do
        handle:write(string.format("mirror,%d,%d\n", offset, emu:read8(MIRROR + offset)))
    end
    for offset = 0, 0xA7 do
        handle:write(string.format("profile,%d,%d\n", offset, emu:read8(PROFILE + offset)))
    end
    handle:write(string.format("value,0,%d\n", read32(0x03000988)))
    handle:write(string.format("value,1,%d\n", read32(0x030007D8)))
    handle:write(string.format("value,2,%d\n", read32(0x03000984)))
    handle:write(string.format("value,3,%d\n", read32(0x030007D0)))
    handle:write(string.format("value,4,%d\n", read32(0x030007CC)))
    handle:write(string.format("value,5,%d\n", read32(0x030007C8)))
    handle:write(string.format("value,6,%d\n", read32(0x030007C4)))
    handle:write(string.format("value,7,%d\n", read32(0x030046B8)))
    handle:write(string.format("value,8,%d\n", read32(0x03000020)))
    for slot = 0, 33 do
        handle:write(string.format("item%d,%d,%d\n", slot, slot, emu:read8(0x0300004E + slot)))
    end
    handle:close()
end

local function keys_for(frame)
    if ROUTE == "field" then
        if frame >= 300 and frame < 1900 and frame % 60 < 6 then return START end
        if frame >= 2320 and frame < 2326 then return START end
        if frame >= 2380 and frame < 2386 then return R_SHOULDER end
        if frame >= 2440 and frame < 2446 then return R_SHOULDER end
        if frame >= 2500 and frame < 2506 then return R_SHOULDER end
        if frame >= 2580 and frame < 2586 then return B end
        return 0
    end
    if ROUTE == "front" then
        if frame >= TAP_FROM and frame < TAP_TO and frame % 24 < 3 then return A end
        if START_AT > 0 and frame >= START_AT and frame < START_AT + 6 then return START end
        if START_EVERY > 0 and frame >= START_AT and frame < TAP_TO and frame % START_EVERY < 6 then
            return START
        end
        if DOWN_AT > 0 and frame >= DOWN_AT and frame < DOWN_AT + 6 then return DOWN end
        if A_AT > 0 and frame >= A_AT and frame < A_AT + 6 then return A end
        return 0
    end
    if ROUTE == "load" then
        if frame >= 200 and frame < 950 and frame % 90 < 6 then return START end
        if frame >= 1000 and frame < 1006 then return DOWN end
        if frame >= 1100 and frame < 1106 then return A end
        return 0
    end
    if ROUTE == "state" then
        local extra = os.getenv("C_UI_STATE_KEYS") or ""
        for at, key in extra:gmatch("(%d+)=(%d+)") do if frame >= tonumber(at) and frame < tonumber(at) + 4 then return tonumber(key) end end
        if frame >= 20 and frame < 26 then return START end
        if frame >= 80 and frame < 86 then return R_SHOULDER end
        if frame >= 120 and frame < 126 then return R_SHOULDER end
        if frame >= 160 and frame < 166 then return L_SHOULDER end
        if frame >= 200 and frame < 206 then return R_SHOULDER end
        if frame >= 240 and frame < 246 then return R_SHOULDER end
        if frame >= 300 and frame < 306 then return B end
        return 0
    end
    if frame < 600 then return 0 end
    if frame < PAGE then
        local keys = 0
        if frame % 90 < 6 then keys = keys | START end
        if frame % 24 < 3 then keys = keys | A end
        return keys
    end
    return row_keys(frame)
end

local log = assert(io.open(DIR .. TAG .. "-scene.csv", "w"), "cannot open the scene log")
log:write("frame,vcount,keyinput,dispcnt,oam_active,shadow_active,oam_x0,oam_y0,menu_key,bg_pal_xor,obj_pal_xor,keys_sent,note,bldcnt,bldalpha,bldy,state_word,pause_state,outer_state,map_word,key_word,bgpal14_xor,bgpal15_xor,objpal14_xor,objpal15_xor\n")
log:flush()

local function oam_scan(window)
    local active, x0, y0 = 0, -1, -1
    for i = 0, 127 do
        local base = window + i * 8
        local a0 = emu:read16(base)
        local a1 = emu:read16(base + 2)
        local y = a0 & 0xFF
        local x = a1 & 0x1FF
        local disabled = (a0 & 0x0300) == 0x0200
        if not disabled and y < 160 then
            active = active + 1
            if y > 16 and x > 16 and x0 < 0 then x0, y0 = x, y end
        end
    end
    return active, x0, y0
end

local function palette_xor(base)
    local value = 0
    for i = 0, 255 do
        value = value ~ emu:read16(base + i * 2)
    end
    return value
end

local function dump_oam(frame)
    local path = string.format("%soam-%s-%05d.csv", DIR, TAG, frame)
    local handle = io.open(path, "w")
    if not handle then return end
    handle:write("window,entry,attr0,attr1,attr2,attr3,y,x,tile,palette,shape,size,affine\n")
    for _, window in ipairs({ 0x07000000, SHADOW_OAM }) do
        for i = 0, 127 do
            local base = window + i * 8
            local a0 = emu:read16(base)
            local a1 = emu:read16(base + 2)
            local a2 = emu:read16(base + 4)
            local a3 = emu:read16(base + 6)
            handle:write(string.format("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n", window, i, a0, a1, a2, a3,
                a0 & 0xFF, a1 & 0x1FF, a2 & 0x3FF, (a2 >> 12) & 0xF,
                (a0 >> 14) & 3, (a1 >> 14) & 3, (a0 >> 8) & 1))
        end
    end
    handle:close()
end

local function dump_palette(frame)
    local path = string.format("%spal-%s-%05d.csv", DIR, TAG, frame)
    local handle = io.open(path, "w")
    if not handle then return end
    handle:write("bank,index,value\n")
    for bank = 0, 1 do
        for i = 0, 255 do
            handle:write(string.format("%d,%d,%d\n", bank, i, emu:read16(0x05000000 + bank * 0x200 + i * 2)))
        end
    end
    handle:close()
end

local REGS = {
    { 0x04000000, 16, "DISPCNT" }, { 0x04000004, 16, "DISPSTAT" },
    { 0x04000008, 16, "BG0CNT" }, { 0x0400000A, 16, "BG1CNT" },
    { 0x0400000C, 16, "BG2CNT" }, { 0x0400000E, 16, "BG3CNT" },
    { 0x04000010, 16, "BG0HOFS" }, { 0x04000012, 16, "BG0VOFS" },
    { 0x04000014, 16, "BG1HOFS" }, { 0x04000016, 16, "BG1VOFS" },
    { 0x04000018, 16, "BG2HOFS" }, { 0x0400001A, 16, "BG2VOFS" },
    { 0x0400001C, 16, "BG3HOFS" }, { 0x0400001E, 16, "BG3VOFS" },
    { 0x04000040, 16, "WIN0H" }, { 0x04000048, 16, "WININ" },
    { 0x04000050, 16, "BLDCNT" }, { 0x04000052, 16, "BLDALPHA" }, { 0x04000054, 16, "BLDY" },
    { 0x03003B60, 16, "word_03003B60" }, { 0x03003B64, 32, "state_word" },
    { 0x03000590, 32, "outer_state" }, { 0x03000598, 32, "pause_state" },
    { 0x0300010C, 32, "field_state" }, { 0x03000600, 32, "map_word" },
    { 0x03000608, 32, "word_03000608" },
    { 0x03003D10, 16, "key_word_3D10" }, { 0x03003D12, 16, "key_word_3D12" },
    { 0x03003D14, 16, "key_word_3D14" }, { 0x03003D16, 16, "key_word_3D16" }
}

local function dump_regs(frame)
    local path = string.format("%sregs-%s-%05d.csv", DIR, TAG, frame)
    local handle = io.open(path, "w")
    if not handle then return end
    handle:write("address,width,name,value\n")
    for _, reg in ipairs(REGS) do
        local value
        if reg[2] == 32 then value = read32(reg[1]) else value = emu:read16(reg[1]) end
        handle:write(string.format("0x%08X,%d,%s,0x%X\n", reg[1], reg[2], reg[3], value))
    end
    handle:close()
end

local VRAM_WINDOWS = {
    { 0x06000000, 0xC000, "bg_char_block0_2" },
    { 0x0600C000, 0x4000, "bg_char_block3" },
    { 0x0600E000, 0x2000, "bg_screen_28_31" },
    { 0x06010000, 0x4000, "obj_tiles" }
}

local function dump_ram(frame)
    local windows = {
        { 0x03000000, 0x800, "iwram-low" },
        { 0x03004000, 0x800, "iwram-high" },
        { 0x02013000, 0x1000, "ewram-stats" }
    }
    local handle = io.open(string.format("%sram-%s-%05d.bin", DIR, TAG, frame), "wb")
    if not handle then return end
    local index = io.open(string.format("%sram-%s-%05d.windows.txt", DIR, TAG, frame), "w")
    if index then index:write("offset,length,name\n") end
    local position = 0
    for _, window in ipairs(windows) do
        local chunk = {}
        for offset = 0, window[2] - 1 do
            chunk[#chunk + 1] = string.char(emu:read8(window[1] + offset))
            if #chunk == 512 then handle:write(table.concat(chunk)); chunk = {} end
        end
        if #chunk > 0 then handle:write(table.concat(chunk)) end
        if index then
            index:write(string.format("%d,0x%X,%s\n", position, window[2], window[3]))
            index:flush()
        end
        position = position + window[2]
    end
    handle:close()
    if index then index:close() end
end

local function dump_vram(frame)
    local handle = io.open(string.format("%svram-%s-%05d.bin", DIR, TAG, frame), "wb")
    if not handle then return end
    local index = io.open(string.format("%svram-%s-%05d.windows.txt", DIR, TAG, frame), "w")
    if index then index:write("offset,length,name\n") end
    local position = 0
    for _, window in ipairs(VRAM_WINDOWS) do
        local length = window[2]
        local chunk = {}
        for offset = 0, length - 1 do
            chunk[#chunk + 1] = string.char(emu:read8(window[1] + offset))
            if #chunk == 512 then handle:write(table.concat(chunk)); chunk = {} end
        end
        if #chunk > 0 then handle:write(table.concat(chunk)) end
        if index then
            index:write(string.format("%d,0x%X,%s\n", position, length, window[3]))
            index:flush()
        end
        position = position + length
    end
    handle:close()
    if index then index:close() end
end

local function dump_bg(frame)
    local state = io.open(string.format("%sbg-%s-%05d-state.csv", DIR, TAG, frame), "w")
    if not state then return end
    state:write("bg,cnt,screen_base,char_base,hofs,vofs,priority,enabled,tile\n")
    state:write(string.format("dispcnt,%d,,,,,,,\n", emu:read16(0x04000000)))
    for bg = 0, 3 do
        local cnt = emu:read16(0x04000008 + bg * 2)
        local hofs = emu:read16(0x04000010 + bg * 4)
        local vofs = emu:read16(0x04000012 + bg * 4)
        local screen = ((cnt >> 8) & 0x1F) * 0x800
        local chars = ((cnt >> 2) & 3) * 0x4000
        state:write(string.format("%d,%d,%d,%d,%d,%d,%d,%d,\n", bg, cnt, screen, chars, hofs, vofs,
            cnt & 3, cnt >> 14))
    end
    state:close()
    for bg = 0, 3 do
        local cnt = emu:read16(0x04000008 + bg * 2)
        local screen = 0x06000000 + ((cnt >> 8) & 0x1F) * 0x800
        local chars = 0x06000000 + ((cnt >> 2) & 3) * 0x4000
        local map = io.open(string.format("%sbg-%s-%05d-map%d.csv", DIR, TAG, frame, bg), "w")
        if map then
            map:write("cell,tile,palette,hflip,vflip\n")
            local used = {}
            for cell = 0, 1023 do
                local word = emu:read16(screen + cell * 2)
                local tile = word & 0x3FF
                map:write(string.format("%d,%d,%d,%d,%d\n", cell, tile, (word >> 12) & 0xF,
                    (word >> 10) & 1, (word >> 11) & 1))
                used[tile] = (used[tile] or 0) + 1
            end
            map:close()
            local order = {}
            for tile, count in pairs(used) do order[#order + 1] = { tile, count } end
            table.sort(order, function(a, b) return a[2] > b[2] end)
            local tiles = io.open(string.format("%sbg-%s-%05d-tiles%d.csv", DIR, TAG, frame, bg), "w")
            if tiles then
                tiles:write("tile,count,halfword\n")
                for index = 1, math.min(48, #order) do
                    local tile = order[index][1]
                    for word = 0, 15 do
                        tiles:write(string.format("%d,%d,%d\n", tile, order[index][2],
                            emu:read16(chars + tile * 32 + word * 2)))
                    end
                end
                tiles:close()
            end
        end
    end
end

local frame = 0
local callback_id
local shots = 0
local shot_failures = 0

local function dump_chars(frame)
    local handle = io.open(string.format("%schars-%s-%05d.csv", DIR, TAG, frame), "w")
    if not handle then return end
    handle:write("offset,halfword\n")
    for offset = 0, 0x1FFE, 2 do
        handle:write(string.format("%d,%d\n", offset, emu:read16(0x0600C000 + offset)))
    end
    handle:close()
end

local function sample(note, sent, n)
    local active, x0, y0 = oam_scan(0x07000000)
    local shadow_active = oam_scan(SHADOW_OAM)
    log:write(string.format("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
        n or frame, emu:read16(0x04000006), emu:read16(0x04000130), emu:read16(0x04000000),
        active, shadow_active, x0, y0, emu:read16(KEY_WORD),
        palette_xor(0x05000000), palette_xor(0x05000200), sent, note,
        emu:read16(0x04000050), emu:read16(0x04000052), emu:read16(0x04000054),
        read32(0x03003B64), read32(0x03000598), read32(0x03000590),
        read32(0x03000600), emu:read16(KEY_WORD),
        bank_xor(0x050001C0), bank_xor(0x050001E0), bank_xor(0x050003C0), bank_xor(0x050003E0)))
    log:flush()
end

local function shot()
    local path = string.format("%sshot-%s-%05d.png", DIR, TAG, frame)
    local ok = pcall(function() emu:screenshot(path) end)
    if ok then
        shots = shots + 1
    else
        shot_failures = shot_failures + 1
    end
end

local function finish()
    emu:setKeys(0)
    sample("route-complete", 0, frame)
    log:close()
    keys_log:close()
    frame_log:close()
    if callback_id ~= nil then
        callbacks:remove(callback_id)
        callback_id = nil
    end
    local marker = assert(io.open(done_path, "w"))
    marker:write(string.format("done frames=%d shots=%d failures=%d\n", frame, shots, shot_failures))
    marker:close()
end

emu:setKeys(0)
sample("route-start", 0, 0)

callback_id = callbacks:add("frame", function()
    frame = frame + 1
    pc_frame = frame
    local tick_ok, tick_err = xpcall(frame_tick, debug.traceback)
    if not tick_ok then note_error("frame_tick", tick_err) end
end)

function frame_tick()
    local sent = keys_for(frame)
    emu:setKeys(sent)
    keys_log:write(string.format("%d,%d,%d,%d\n", frame, emu:read16(0x04000130),
        emu:read16(KEY_WORD), sent))
    frame_sample(frame)

    if frame % 60 == 0 then
        sample("running", sent, frame)
    end
    if frame >= SHOT_FROM then
        if frame % SHOT_EVERY == 0 then shot() end
    elseif frame % 100 == 0 then
        shot()
    end
    if frame >= 5400 and frame % 200 == 0 then
        dump_oam(frame)
        dump_palette(frame)
    end
    if BG_FRAMES[frame] then
        dump_oam(frame)
        dump_palette(frame)
        dump_bg(frame)
        dump_chars(frame)
    end
    if RAM_FRAMES[frame] then
        dump_ram(frame)
    end
    if DUMP_FRAMES[frame] then
        dump_state(frame)
        dump_regs(frame)
        dump_palette(frame)
        dump_oam(frame)
        dump_vram(frame)
    end
    if STATE_FRAME > 0 and frame == STATE_FRAME and #STATE_PATH > 0 then
        local ok, err = pcall(function() emu:saveStateFile(STATE_PATH) end)
        local note = assert(io.open(DIR .. TAG .. '-state-save.txt', 'w'))
        note:write(string.format('frame=%d path=%s ok=%s err=%s\n', frame, STATE_PATH,
            tostring(ok), tostring(err)))
        note:close()
    end
    if frame >= LIMIT then finish() end
end