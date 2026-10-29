local ACTIVE_MAP_PTR = 0x03001980
local MAP_ENTRY_BASE = 0x0808E2E0
local MAP_ENTRY_SIZE = 0x38
local MAP_ENTRY_SOURCE = 0x2C
local ROOT_LAYER_SLOTS = { 0x14, 0x18, 0x1C, 0x20 }
local LAYER_CHUNK_X = 0x14
local LAYER_CHUNK_Y = 0x15
local LAYER_WINDOW = 0x18
local MAX_CELLS = 8
local CAMERA_STATE = 0x030019A4
local CAMERA_MAX_X = 0x9C
local CAMERA_MAX_Y = 0x9E
local DISPCNT = 0x04000000
local BGCNT = { 0x04000008, 0x0400000A, 0x0400000C, 0x0400000E }
local BGOFS = { 0x04000010, 0x04000014, 0x04000018, 0x0400001C }
local SCREENBLOCK_BYTES = 0x800
local SCREENBLOCK_ENTRIES = 1024
local CANONICAL_ROM_BYTES = 8388608
local GENERATED_ROM_BYTES = 16777216
local SAMPLE_EVERY = 30
local MAX_ROWS = 256
local HEARTBEAT_EVERY = 60

local run_dir = nil
if type(rom011_marker_path) == "string" then
    run_dir = rom011_marker_path:match("^(.*)/[^/]*$")
end

local function in_run(name)
    if run_dir then return run_dir .. "/" .. name end
    return name
end

assert(emu ~= nil, "mGBA did not attach the emulation core")
local game_code = emu:getGameCode()
assert(game_code == "BG3E" or game_code == "AGB-BG3E",
    "unexpected game code: " .. tostring(game_code))
local rom_size = emu:romSize()
assert(rom_size == CANONICAL_ROM_BYTES or rom_size == GENERATED_ROM_BYTES,
    "unexpected ROM size: " .. tostring(rom_size))

local function safe8(addr)
    local ok, v = pcall(function() return emu:read8(addr) end)
    if ok and v then return v end
    return nil
end

local function safe16(addr)
    local ok, v = pcall(function() return emu:read16(addr) end)
    if ok and v then return v end
    return nil
end

local function safe32(addr)
    local ok, v = pcall(function() return emu:read32(addr) end)
    if ok and v then return v end
    return nil
end

local function hex_or_blank(value, digits)
    if value == nil then return "" end
    return string.format("0x%0" .. tostring(digits) .. "X", value)
end

local function current_index(entry)
    if entry == nil or entry < MAP_ENTRY_BASE then return nil end
    local offset = entry - MAP_ENTRY_BASE
    if offset % MAP_ENTRY_SIZE ~= 0 then return nil end
    local index = offset // MAP_ENTRY_SIZE
    if index < 0 or index > 451 then return nil end
    return index
end

local function read_screenblock(base)
    local values = {}
    local signature = 0
    for index = 0, SCREENBLOCK_ENTRIES - 1 do
        local v = safe16(base + index * 2) or 0
        values[index + 1] = v
        signature = (signature * 31 + v) % 4294967296
    end
    return values, signature
end

local function write_screenblock(path, values)
    local f = assert(io.open(path, "wb"), "cannot open output: " .. tostring(path))
    for index = 1, SCREENBLOCK_ENTRIES do
        local v = values[index]
        f:write(string.char(v & 0xFF, (v >> 8) & 0xFF))
    end
    f:close()
end

local function screen_bases(dispcnt, bg)
    local bases = {}
    for i = 1, 4 do
        local n = i - 1
        local enabled = 0
        if dispcnt ~= nil then enabled = (dispcnt >> (8 + n)) & 0x1 end
        local cnt = bg[i]
        if enabled == 1 and cnt ~= nil then
            bases[n] = 0x06000000 + (((cnt >> 8) & 0x1F) * SCREENBLOCK_BYTES)
        end
    end
    return bases
end

local snapshots_file = assert(io.open(in_run("snapshots.csv"), "w"), "cannot open index")
snapshots_file:write(
    "snapshot,frame,map_index,map_entry_ptr,rom_size,dispcnt,"
    .. "bg0cnt,bg1cnt,bg2cnt,bg3cnt,"
    .. "bg0hofs,bg0vofs,bg1hofs,bg1vofs,bg2hofs,bg2vofs,bg3hofs,bg3vofs,"
    .. "camera_max_x,camera_max_y,shot\n")
snapshots_file:flush()

local layers_file = assert(io.open(in_run("layers.csv"), "w"), "cannot open layers")
layers_file:write(
    "snapshot,map_index,slot,record,handler,chunk_x,chunk_y,cells,pointers\n")
layers_file:flush()

local heartbeat_file = assert(io.open(in_run("heartbeat.csv"), "w"), "cannot open heartbeat")
heartbeat_file:write("frame,map_index,map_entry_ptr,cell0_pointer\n")
heartbeat_file:flush()

local frame = 0
local snapshots = 0
local last_signature = {}
local last_index = nil

local function record(entry, map_index, bases)
    local name = string.format("snapshot_%03d", snapshots)
    local dispcnt = safe16(DISPCNT)
    local bg = {}
    local ofs = {}
    for i = 1, 4 do
        bg[i] = safe16(BGCNT[i])
        ofs[i] = { safe16(BGOFS[i]), safe16(BGOFS[i] + 2) }
    end
    for n = 0, 3 do
        local base = bases[n]
        if base ~= nil then
            local values = read_screenblock(base)
            write_screenblock(in_run(name .. string.format("_bg%d.bin", n)), values)
        end
    end
    local shot = ""
    local shot_index = snapshots
    local ok, err = pcall(function()
        return emu:screenshot(in_run(string.format("shot_%03d.png", shot_index)))
    end)
    if ok then shot = string.format("shot_%03d.png", shot_index)
    else shot = "failed: " .. tostring(err) end
    snapshots_file:write(string.format(
        "%d,%d,%s,%s,%d,%s,%s,%s,%s,%s,%d,%d,%d,%d,%d,%d,%d,%d,%s,%s,%s\n",
        snapshots, frame,
        map_index and tostring(map_index) or "",
        hex_or_blank(entry, 8),
        rom_size,
        hex_or_blank(dispcnt, 4),
        hex_or_blank(bg[1], 4), hex_or_blank(bg[2], 4),
        hex_or_blank(bg[3], 4), hex_or_blank(bg[4], 4),
        ofs[1][1] or -1, ofs[1][2] or -1,
        ofs[2][1] or -1, ofs[2][2] or -1,
        ofs[3][1] or -1, ofs[3][2] or -1,
        ofs[4][1] or -1, ofs[4][2] or -1,
        hex_or_blank(safe16(CAMERA_STATE + CAMERA_MAX_X), 4),
        hex_or_blank(safe16(CAMERA_STATE + CAMERA_MAX_Y), 4),
        shot))
    snapshots_file:flush()

    local source = nil
    if entry ~= nil then source = safe32(entry + MAP_ENTRY_SOURCE) end
    local root = nil
    if source ~= nil then root = safe32(source) end
    if root ~= nil then
        for slot = 0, 3 do
            local layer = safe32(root + ROOT_LAYER_SLOTS[slot + 1])
            if layer ~= nil and layer ~= 0 then
                local cx = safe8(layer + LAYER_CHUNK_X)
                local cy = safe8(layer + LAYER_CHUNK_Y)
                local cells = 0
                if cx ~= nil and cy ~= nil then cells = cx * cy end
                local shown = cells
                if shown > MAX_CELLS then shown = MAX_CELLS end
                local pointers = {}
                for cell = 0, shown - 1 do
                    pointers[cell + 1] = hex_or_blank(safe32(layer + LAYER_WINDOW + cell * 4), 8)
                end
                layers_file:write(string.format(
                    "%d,%s,%d,%s,%s,%s,%s,%d,%s\n",
                    snapshots,
                    map_index and tostring(map_index) or "",
                    slot,
                    hex_or_blank(layer, 8),
                    hex_or_blank(safe32(layer), 8),
                    cx and tostring(cx) or "",
                    cy and tostring(cy) or "",
                    cells,
                    table.concat(pointers, " ")))
            end
        end
        layers_file:flush()
    end
    snapshots = snapshots + 1
end

local function watched_cell0(entry, map_index)
    if entry == nil or map_index == nil then return nil end
    local source = safe32(entry + MAP_ENTRY_SOURCE)
    if source == nil then return nil end
    local root = safe32(source)
    if root == nil then return nil end
    local layer = safe32(root + ROOT_LAYER_SLOTS[2])
    if layer == nil or layer == 0 then return nil end
    return safe32(layer + LAYER_WINDOW)
end

callbacks:add("frame", function()
    frame = frame + 1

    if frame == 1 and type(rom011_marker_path) == "string" then
        local mk = io.open(rom011_marker_path, "w")
        if mk then mk:write("armed\n") mk:close() end
    end

    local entry = safe32(ACTIVE_MAP_PTR)
    local map_index = current_index(entry)

    if frame % HEARTBEAT_EVERY == 0 then
        heartbeat_file:write(string.format(
            "%d,%s,%s,%s\n", frame,
            map_index and tostring(map_index) or "",
            hex_or_blank(entry, 8),
            hex_or_blank(watched_cell0(entry, map_index), 8)))
        heartbeat_file:flush()
    end

    if frame % SAMPLE_EVERY == 0 and snapshots < MAX_ROWS then
        local dispcnt = safe16(DISPCNT)
        local bg = {}
        for i = 1, 4 do bg[i] = safe16(BGCNT[i]) end
        local bases = screen_bases(dispcnt, bg)
        local changed = (map_index ~= last_index)
        last_index = map_index
        for n = 0, 3 do
            local base = bases[n]
            if base ~= nil then
                local _values, signature = read_screenblock(base)
                if last_signature[n] ~= signature then
                    last_signature[n] = signature
                    changed = true
                end
            end
        end
        if changed then
            record(entry, map_index, bases)
        end
    end
end)
