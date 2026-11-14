assert(emu ~= nil, "mGBA did not attach the emulation core")
assert(emu.setBreakpoint and emu.clearBreakpoint,
    "this observer needs the 0.11 breakpoint API")

local DECLARED = (os.getenv("LOG1_MGBA_ROM_SHA256") or ""):lower()
assert(#DECLARED == 64, "no ROM identity in the environment: LOG1_MGBA_ROM_SHA256 is unset")

local function number_from_env(name, default)
    local raw = os.getenv(name)
    if raw == nil or raw == "" then return default end
    local text = raw:gsub("^0[xX]", "")
    local value = tonumber(text)
    if value == nil then value = tonumber(text, 16) end
    return value or default
end

local marker = rom011_marker_path
assert(type(marker) == "string" and #marker > 0, "the launcher did not set rom011_marker_path")
local run_dir = marker:match("^(.*)/[^/]*$") or "."

local OUT = COMBAT001_OUT
if OUT == nil or OUT == "" then OUT = os.getenv("COMBAT001_OUT") end
if OUT == nil or OUT == "" then OUT = run_dir .. "/combat001-trace.txt" end
local DONE = OUT:gsub("%.txt$", "") .. ".done"
local STAT = number_from_env("COMBAT001_STAT", 0)
local HORIZON = number_from_env("COMBAT001_FRAMES", 4000)

assert(STAT ~= 0, "COMBAT001_STAT must name the enemy type record to track")

local CONSTRUCT_SITE = 0x08008CC0
local MAP_LOAD_SITE = 0x08008B30
local FLAG_SET_SITE = 0x08004380
local EWRAM_LO, EWRAM_HI = 0x02000000, 0x02040000
local STAT_FIELD, HP_FIELD, POS_X, POS_Y = 0x224, 0x28C, 0x1A0, 0x1A4
local SAVE_BASE, ZENI_OFFSET = 0x03001068, 0x4F4
local XP_ADDRESS = 0x03001584
local HEARTBEAT = 300
local SCAN_STRIDE = 15
local STAT_TABLE = 0x08711274
local STAT_ROW = (STAT - STAT_TABLE) // 28

local log = assert(io.open(OUT, "w"))
local function line(text)
    log:write(text .. "\n")
    log:flush()
end
line("frame,event,actor,record,type,id,pos_x,pos_y,hp,hp_shown,xp,zeni,note")

local function r8(a)
    local ok, v = pcall(function() return emu:read8(a) end)
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

local function signed(value)
    if value == nil then return nil end
    if value >= 0x80000000 then return value - 0x100000000 end
    return value
end

local frames, actor, constructed, lethal_at, removed_at = 0, nil, nil, nil, nil
local hp_prev, xp_prev, zeni_prev = nil, nil, nil
local finished, armed = false, false

local function hex(value)
    if value == nil then return "" end
    return string.format("0x%08X", value)
end

local function shown(raw)
    if raw == nil then return "" end
    return tostring((raw + 1023) // 1024)
end

local function row(event, fields, note)
    line(table.concat({
        tostring(frames), event,
        fields.actor or "", fields.record or "", fields.type or "", fields.id or "",
        fields.pos_x or "", fields.pos_y or "", fields.hp or "", fields.hp_shown or "",
        fields.xp or "", fields.zeni or "", note or "",
    }, ","))
end

local function finish(reason)
    if finished then return end
    finished = true
    row("SUMMARY", {hp = tostring(hp_prev or ""), hp_shown = shown(hp_prev),
        xp = tostring(xp_prev or ""), zeni = tostring(zeni_prev or "")},
        "frames=" .. frames .. " constructed=" .. tostring(constructed ~= nil)
        .. " lethal_frame=" .. tostring(lethal_at) .. " removed_frame=" .. tostring(removed_at)
        .. " reason=" .. reason)
    row("DONE", {}, reason)
    log:close()
    local done = io.open(DONE, "w")
    if done then done:write("done " .. reason .. "\n") done:close() end
end

local function scan_for_actor()
    local found, address = 0, EWRAM_LO
    while address < EWRAM_HI do
        if r32(address + STAT_FIELD) == STAT then
            found = found + 1
            if actor == nil then actor = address end
        end
        address = address + 4
    end
    return found
end

local function arm()
    if armed then return end
    armed = true
    emu:setBreakpoint(function()
        local record = reg("r0")
        if record == nil or record < 0x08000000 then return end
        local position = r32(record + 0x0C)
        row("CONSTRUCT", {
            record = hex(record), type = tostring(r32(record + 0x08) or ""),
            id = tostring(r32(record + 0x10) or ""),
            pos_x = position and tostring(position & 0xFFFF) or "",
            pos_y = position and tostring(position >> 16) or "",
            xp = tostring(xp_prev or ""), zeni = tostring(zeni_prev or ""),
        }, "loader construct call site")
        local type_row = r32(record + 0x08)
        if constructed == nil and type_row ~= nil and type_row == STAT_ROW then
            constructed = record
        end
    end, CONSTRUCT_SITE)
    emu:setBreakpoint(function()
        row("LOAD", {record = hex(reg("r1")), xp = tostring(xp_prev or ""),
            zeni = tostring(zeni_prev or "")}, "liveness channel")
    end, MAP_LOAD_SITE)
    emu:setBreakpoint(function()
        local flag = reg("r1")
        if flag == nil then return end
        local at = SAVE_BASE + 0x55 + (flag >> 3)
        row("FLAG-SET", {xp = tostring(xp_prev or ""), zeni = tostring(zeni_prev or "")},
            "flag=" .. tostring(flag) .. " byte=" .. string.format("0x%02X", r8(at) or 0))
    end, FLAG_SET_SITE)
end

local callback
callback = callbacks:add("frame", function()
    local ok, err = xpcall(function()
        if finished then return end
        frames = frames + 1
        if not armed then arm() end

        local xp = r32(XP_ADDRESS)
        local zeni = r32(SAVE_BASE + ZENI_OFFSET)
        if xp ~= nil and xp ~= xp_prev then
            row("XP", {xp = tostring(xp), zeni = tostring(zeni or ""),
                hp = tostring(hp_prev or ""), hp_shown = shown(hp_prev)}, "experience paid")
        end
        if zeni ~= nil and zeni ~= zeni_prev then
            row("ZENI", {zeni = tostring(zeni), xp = tostring(xp or ""),
                hp = tostring(hp_prev or ""), hp_shown = shown(hp_prev)}, "zeni paid")
        end
        xp_prev, zeni_prev = xp or xp_prev, zeni or zeni_prev

        if actor == nil and frames % SCAN_STRIDE == 1 then
            local found = scan_for_actor()
            if actor ~= nil then
                local px, py = signed(r32(actor + POS_X)), signed(r32(actor + POS_Y))
                row("ACTOR", {actor = hex(actor), record = hex(constructed),
                    hp = tostring(r32(actor + HP_FIELD) or ""),
                    hp_shown = shown(signed(r32(actor + HP_FIELD))),
                    pos_x = px and tostring(px >> 8) or "",
                    pos_y = py and tostring(py >> 8) or ""},
                    "actors_with_stat=" .. tostring(found))
            end
        end

        if actor ~= nil then
            local raw = signed(r32(actor + HP_FIELD))
            if raw ~= nil and raw ~= hp_prev then
                local event = "HP"
                if raw <= 0 and (hp_prev == nil or hp_prev > 0) then
                    event = "LETHAL"
                    lethal_at = frames
                end
                row(event, {actor = hex(actor), record = hex(constructed),
                    hp = tostring(raw), hp_shown = shown(raw),
                    xp = tostring(xp or ""), zeni = tostring(zeni or "")}, "hp write")
                hp_prev = raw
            end
            local latch = r32(actor + STAT_FIELD)
            if lethal_at and lethal_at < frames and removed_at == nil
                    and latch ~= nil and latch ~= STAT then
                row("REMOVED", {actor = hex(actor), record = hex(constructed),
                    hp = tostring(hp_prev or ""), hp_shown = shown(hp_prev)},
                    "the slot no longer carries this stat record")
                removed_at = frames
                actor = nil
            end
        end

        if frames % HEARTBEAT == 0 then
            row("HEARTBEAT", {record = hex(constructed), hp = tostring(hp_prev or ""),
                hp_shown = shown(hp_prev), xp = tostring(xp_prev or ""),
                zeni = tostring(zeni_prev or "")},
                "actor=" .. tostring(actor ~= nil))
        end

        if removed_at and frames > removed_at + 120 then
            finish("removal")
        elseif frames >= HORIZON then
            finish("frame-budget")
        end
    end, function(e)
        return tostring(e) .. "\n" .. debug.traceback(e, 2)
    end)
    if not ok then
        row("ERROR", {}, err)
        callbacks:remove(callback)
        finish("error")
    end
end)

local code = "unknown"
local ok, value = pcall(function() return emu:getGameCode() end)
if ok and value then code = tostring(value) end
row("READY", {}, "game_code=" .. code .. " stat=" .. hex(STAT)
    .. " horizon=" .. tostring(HORIZON))

print([[combat001 trace armed]])
