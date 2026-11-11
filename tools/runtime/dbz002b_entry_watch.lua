local ACTIVE_MAP_PTR = 0x03001980
local MAP_ENTRY_SIZE = 0x38
local TABLE_BASE_POOL = 0x08008A58
local COUNT_HELPER = 0x080125E0
local COUNT_HELPER_FIRST = 0x20FF
local COUNT_HELPER_BASE = 0xFF

local DIALOGUE_CTOR = 0x0801227E
local SAVE_FLAG_SET = 0x08004380
local FLAG_BYTE_FROM_OBJECT = 0x55
local MAP_LOOKUP = 0x080089FC
local DIALOGUE_ARRAY_READ = 0x08012530
local VM_ENTRY = 0x08004038
local DIALOGUE_POOL_LOW = 0x0877C5A4
local DIALOGUE_POOL_HIGH = 0x0879B704

local ROM_BASE = 0x08000000
local CANONICAL = { size = 8388608, sha256 = "940ad5f01db4465b8877dfe739510cbf34f4ea3d390f3df13519808bc36f059e" }
local DECLARED = (os.getenv("LOG1_MGBA_ROM_SHA256") or ""):lower()
local DERIVATIVE = (os.getenv("DBZ002B_DERIVATIVE_SHA256") or ""):lower()
local DERIVATIVE_SIZE = tonumber(os.getenv("DBZ002B_ROM_SIZE") or "0")

local MAX_FRAMES = tonumber(os.getenv("DBZ002B_MAX_FRAMES") or "4600")
local HEARTBEAT_EVERY = 60
local SHOT_EVERY = 120
local MAX_SHOTS = 60

assert(emu ~= nil, "mGBA did not attach the emulation core")
assert(emu.setBreakpoint and emu.clearBreakpoint, "requires the 0.11 breakpoint API")
local game_code = emu:getGameCode()
assert(game_code == "BG3E" or game_code == "AGB-BG3E", "unexpected game code: " .. tostring(game_code))
local rom_size = emu:romSize()
local allowed = (DECLARED == CANONICAL.sha256 and rom_size == CANONICAL.size)
if not allowed and DERIVATIVE ~= "" then
    allowed = (DECLARED == DERIVATIVE and rom_size == DERIVATIVE_SIZE)
end
assert(allowed, "refused: image is not the canonical build or the launcher-declared derivative; size="
    .. tostring(rom_size) .. ", declared=" .. tostring(DECLARED)
    .. ", derivative=" .. tostring(DERIVATIVE))
local ROM_END = ROM_BASE + rom_size

local function r8(a)
    local ok, v = pcall(function() return emu:read8(a) end)
    if ok then return v end
end
local function r16(a)
    local ok, v = pcall(function() return emu:read16(a) end)
    if ok then return v end
end
local function r32(a)
    local ok, v = pcall(function() return emu:read32(a) end)
    if ok then return v end
end
local function reg(name)
    local ok, v = pcall(function() return tonumber(emu:readRegister(name)) end)
    if ok then return v end
end
local function hx(v) if v == nil then return "" end return string.format("0x%08X", v) end
local function h2(v) if v == nil then return "" end return string.format("0x%02X", v) end

local function in_rom(p)
    return p ~= nil and p >= ROM_BASE and p < ROM_END
end

local function engine_table_base()
    local base = r32(TABLE_BASE_POOL)
    if not in_rom(base) then return nil end
    return base
end

local function engine_row_bound()
    if r16(COUNT_HELPER) ~= COUNT_HELPER_FIRST then return nil end
    local imm = r8(COUNT_HELPER + 2)
    if imm == nil then return nil end
    return COUNT_HELPER_BASE + imm
end

local function live_map()
    local entry = r32(ACTIVE_MAP_PTR)
    if not in_rom(entry) then return nil end
    local base = engine_table_base()
    local row = { entry = entry, key_hi = r8(entry), key_lo = r8(entry + 1), base = base }
    if base ~= nil and entry >= base then
        local offset = entry - base
        if offset % MAP_ENTRY_SIZE == 0 then
            local index = offset // MAP_ENTRY_SIZE
            local bound = engine_row_bound()
            if bound == nil or index < bound then row.index = index end
        end
    end
    return row
end

local header = { "frame", "event", "a", "b", "c", "d", "note" }
local run_dir = nil
if type(rom011_marker_path) == "string" then
    run_dir = rom011_marker_path:match("^(.*)/[^/]*$")
end
local function in_run(name)
    if run_dir then return run_dir .. "/" .. name end
    return name
end
local out_path = in_run("dbz002b-observation.csv")
local file = assert(io.open(out_path, "w"), "cannot open " .. tostring(out_path))
file:write(table.concat(header, ",") .. "\n")
file:flush()

local frames = 0
local shots = 0
local dialogue_hits = 0
local flag_hits = 0
local last_index = nil
local pending_flags = {}
local pending_shot = nil

local function row(t)
    local parts = { tostring(t.frame or frames), t.event or "" }
    for i = 3, #header do
        parts[i] = t[header[i]] ~= nil and tostring(t[header[i]]) or ""
    end
    file:write(table.concat(parts, ",") .. "\n")
    file:flush()
end

local function shot(tag)
    if shots >= MAX_SHOTS then return end
    shots = shots + 1
    pcall(function()
        emu:screenshot(string.format("%s%s_%05d.png", in_run(""), tag, frames))
    end)
end

local function stack_returns()
    local sp = reg("sp") or reg("r13")
    if sp == nil then return "" end
    local words = {}
    for i = 0, 23 do
        local value = r32(sp + i * 4)
        if in_rom(value) then
            words[#words + 1] = string.format("%08X", value - ROM_BASE + 0x08000000)
        end
        if #words >= 6 then break end
    end
    return table.concat(words, " ")
end

local bp_dialogue = emu:setBreakpoint(function(info)
    dialogue_hits = dialogue_hits + 1
    local ptr = reg("r1")
    local map = live_map()
    local lr = reg("lr") or reg("r14")
    if not in_rom(ptr) then
        row({ event = "DIALOGUE_NOT_ROM", b = hx(ptr), note = "record pointer outside the image" })
        return
    end
    row({ event = "DIALOGUE", frame = frames,
          a = hx(ptr),
          b = "file=0x" .. string.format("%06X", ptr - ROM_BASE),
          c = string.format("kind=%d portrait=%d next=%d", r8(ptr + 2) or -1, r8(ptr + 3) or -1, r8(ptr) or -1),
          d = string.format("handle=0x%08X lr=0x%08X", r32(ptr + 4) or 0, lr or 0),
          note = string.format("map_index=%s key=%s%02x stack=%s",
              tostring(map and map.index),
              map and map.key_hi and string.format("%02x", map.key_hi) or "",
              map and map.key_lo or 0, stack_returns()) })
    shot("dialogue")
    pending_shot = frames + 30
end, DIALOGUE_CTOR)

local bp_flag = emu:setBreakpoint(function(info)
    flag_hits = flag_hits + 1
    local obj = reg("r0")
    local flag = reg("r1")
    if obj == nil or flag == nil then return end
    local addr = obj + FLAG_BYTE_FROM_OBJECT + (flag >> 3)
    local before = r8(addr)
    row({ event = "FLAG_SET", frame = frames,
          a = string.format("flag=%d", flag), b = hx(addr),
          c = string.format("bit=%d", flag & 7), d = string.format("before=%s", h2(before)),
          note = "handler 0x08004380: save object + 0x55 + (flag>>3), not the pool base at +0x50" })
    pending_flags[#pending_flags + 1] = { flag = flag, addr = addr, before = before, at = frames + 2 }
end, SAVE_FLAG_SET)

local bp_lookup = emu:setBreakpoint(function(info)
    local map = live_map()
    row({ event = "MAP_LOOKUP", frame = frames,
          a = hx(reg("r0")), b = hx(reg("r1")),
          c = string.format("lr=0x%08X", reg("lr") or 0),
          d = string.format("map_index=%s", tostring(map and map.index)),
          note = "map table lookup entry 0x080089FC" })
end, MAP_LOOKUP)

local array_hits = 0
local MAX_ARRAY_ROWS = 40
local bp_array = emu:setBreakpoint(function(info)
    array_hits = array_hits + 1
    if array_hits > MAX_ARRAY_ROWS then return end
    local runner = reg("r4")
    if runner == nil then return end
    local array = r32(runner)
    local index = r16(runner + 8)
    local word_a = nil
    local word_b = nil
    if array ~= nil then
        word_a = r32(array + 4 * (index or 0))
        word_b = r32(array + 4 * ((index or 0) + 1))
    end
    row({ event = "DIALOGUE_ARRAY", frame = frames,
          a = hx(runner), b = hx(array),
          c = string.format("index=%s word0=0x%08X word1=0x%08X",
              tostring(index), word_a or 0, word_b or 0),
          d = string.format("array_rom=%s lr=0x%08X",
              tostring(in_rom(array)), reg("lr") or 0),
          note = "runner +0 word array; a word with a nonzero high half is a record pointer" })
end, DIALOGUE_ARRAY_READ)

local vm_pool_hits = 0
local bp_vm = emu:setBreakpoint(function(info)
    local cursor = reg("r1")
    if cursor == nil or cursor < DIALOGUE_POOL_LOW or cursor >= DIALOGUE_POOL_HIGH then return end
    if vm_pool_hits >= 20 then return end
    vm_pool_hits = vm_pool_hits + 1
    local bytes = {}
    for i = 0, 7 do
        bytes[#bytes + 1] = string.format("%02X", r8(cursor + i) or 0)
    end
    row({ event = "VM_POOL", frame = frames,
          a = hx(cursor), b = "file=0x" .. string.format("%06X", cursor - ROM_BASE),
          c = table.concat(bytes, " "),
          d = string.format("lr=0x%08X state=0x%08X", reg("lr") or 0, reg("r0") or 0),
          note = "VM interpreter entered with a cursor inside the dialogue pool" })
end, VM_ENTRY)

local cid
cid = callbacks:add("frame", function()
    frames = frames + 1

    for i = #pending_flags, 1, -1 do
        local p = pending_flags[i]
        if frames >= p.at then
            row({ event = "FLAG_AFTER", frame = frames,
                  a = string.format("flag=%d", p.flag), b = hx(p.addr),
                  c = string.format("before=%s", h2(p.before)),
                  d = string.format("after=%s", h2(r8(p.addr))),
                  note = "same byte after the store" })
            table.remove(pending_flags, i)
        end
    end

    local map = live_map()
    if map and map.index ~= nil and map.index ~= last_index then
        row({ event = "MAP_ROW", frame = frames,
              a = tostring(map.index),
              b = string.format("%02x%02x", map.key_hi or 0, map.key_lo or 0),
              c = hx(map.entry),
              note = last_index == nil and "first observed row" or "row changed" })
        shot("map")
        last_index = map.index
    end

    if frames % HEARTBEAT_EVERY == 0 then
        row({ event = "HEARTBEAT", frame = frames,
              a = tostring(map and map.index),
              b = map and string.format("%02x%02x", map.key_hi or 0, map.key_lo or 0) or "",
              c = string.format("dialogue_hits=%d flag_hits=%d", dialogue_hits, flag_hits),
              d = string.format("bound=%s", tostring(engine_row_bound() or "?")) })
    end

    if pending_shot ~= nil and frames >= pending_shot then
        shot("page")
        pending_shot = nil
    end

    if frames % SHOT_EVERY == 0 then
        shot("tick")
    end

    if frames == 1 and type(rom011_marker_path) == "string" then
        local mk = io.open(rom011_marker_path, "w")
        if mk then mk:write("armed\n") mk:close() end
    end

    if frames >= MAX_FRAMES then
        row({ event = "END", frame = frames,
              c = string.format("dialogue_hits=%d flag_hits=%d", dialogue_hits, flag_hits),
              note = "frame budget reached" })
        emu:clearBreakpoint(bp_dialogue)
        emu:clearBreakpoint(bp_flag)
        emu:clearBreakpoint(bp_lookup)
        emu:clearBreakpoint(bp_array)
        emu:clearBreakpoint(bp_vm)
        callbacks:remove(cid)
        file:close()
        os.exit(0)
    end
end)
