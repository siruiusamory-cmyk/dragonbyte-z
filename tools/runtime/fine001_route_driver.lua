local OBSERVER_NAME = "fine001_probe_watch%.lua$"
local ACTIVE_MAP_PTR = 0x03001980
local MAP_ENTRY_BASE = 0x0808E2E0
local MAP_ENTRY_SIZE = 0x38
local MAP_INDEX_LIMIT = 451
local BG1_VOFS = 0x04000016
local KEY_RIGHT = 0x10
local KEY_LEFT = 0x20
local KEY_UP = 0x40

local SCHEDULE = {
    { name = "start_map40", want_map = 40, want_vofs = -1, expect = -1, hold = 0, mask = 0x00, budget = 900 },
    { name = "leave_to_39", want_map = 39, want_vofs = -1, expect = 40, hold = 0, mask = KEY_LEFT, budget = 1500 },
    { name = "release_in_39", want_map = 40, want_vofs = -1, expect = -1, hold = 20, mask = 0x00, budget = 20 },
    { name = "step_east", want_map = 40, want_vofs = -1, expect = -1, hold = 45, mask = KEY_RIGHT, budget = 45 },
    { name = "return_to_40", want_map = 40, want_vofs = -1, expect = 39, hold = 0, mask = KEY_LEFT, budget = 1200 },
    { name = "settle_40", want_map = -1, want_vofs = -1, expect = 40, hold = 300, mask = 0x00, budget = 300 },
    { name = "camera_top", want_map = -1, want_vofs = 0, expect = 40, hold = 0, mask = KEY_UP, budget = 900 },
    { name = "hold_capture", want_map = -1, want_vofs = -1, expect = 40, hold = 300, mask = 0x00, budget = 300 }
}

local run_dir = nil
if type(rom011_marker_path) == "string" then
    run_dir = rom011_marker_path:match("^(.*)/[^/]*$")
end
assert(run_dir ~= nil, "rom011_marker_path must name the run directory")

local function in_run(name)
    return run_dir .. "/" .. name
end

local observer = os.getenv("FINE001_OBSERVER")
assert(observer ~= nil and observer ~= "", "FINE001_OBSERVER must name the observer")
assert(observer:match(OBSERVER_NAME) ~= nil,
    "FINE001_OBSERVER must name fine001_probe_watch.lua, not " .. tostring(observer))
dofile(observer)

assert(emu ~= nil, "mGBA did not attach the emulation core")

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

local function read_map()
    local entry = safe32(ACTIVE_MAP_PTR)
    if entry == nil or entry < MAP_ENTRY_BASE then return nil, entry end
    local offset = entry - MAP_ENTRY_BASE
    if offset % MAP_ENTRY_SIZE ~= 0 then return nil, entry end
    local index = offset // MAP_ENTRY_SIZE
    if index < 0 or index > MAP_INDEX_LIMIT then return nil, entry end
    return index, entry
end

local log = assert(io.open(in_run("route-log.csv"), "w"), "cannot open route log")
log:write("frame,step,event,mask,map_index,map_entry_ptr,bg1_vofs\n")
log:flush()

local function note(frame, step, event, mask, map_index, entry, vofs)
    log:write(string.format(
        "%d,%s,%s,0x%02X,%s,%s,%s\n",
        frame, step, event, mask,
        map_index and tostring(map_index) or "",
        entry and string.format("0x%08X", entry) or "",
        vofs and tostring(vofs) or ""))
    log:flush()
end

local function status(text)
    local f = io.open(in_run("route-status.txt"), "w")
    if f then
        f:write(text, "\n")
        f:close()
    end
end

local rom_sha256 = os.getenv("LOG1_MGBA_ROM_SHA256") or ""
local state_sha256 = os.getenv("FINE001_STATE_SHA256") or ""
local label = run_dir:match("[^/]+$") or ""
local identity = io.open(in_run("inputs.json"), "w")
if identity then
    identity:write(string.format(
        '{\n  "label": "%s",\n  "tool": "DRAGONBYTE-FINE-001",\n'
        .. '  "rom_sha256": "%s",\n  "state_sha256": "%s",\n'
        .. '  "input_log": "route-log.csv",\n  "schedule": "map40_return"\n}\n',
        label, rom_sha256, state_sha256))
    identity:close()
end

local frame = 0
local step_index = 1
local frames_in_step = 0
local current_mask = 0
local last_map = nil
local callback_id

local function stop()
    emu:setKeys(0)
    current_mask = 0
    if callback_id ~= nil then
        callbacks:remove(callback_id)
        callback_id = nil
    end
end

local function step_fail(step, reason, map_index)
    note(frame, step.name, "fail_" .. reason, current_mask, map_index, nil, nil)
    status(string.format("ROUTE FAIL step=%s reason=%s frame=%d map=%s",
        step.name, reason, frame, map_index and tostring(map_index) or "none"))
    stop()
end

emu:setKeys(0)
status("ROUTE STARTED schedule=map40_return steps=" .. tostring(#SCHEDULE))
if rom_sha256 == "" or state_sha256 == "" then
    note(0, "identity", "missing_digest", 0, nil, nil, nil)
end

callback_id = callbacks:add("frame", function()
    frame = frame + 1
    local step = SCHEDULE[step_index]
    if step == nil then return end

    if frames_in_step == 0 then
        current_mask = step.mask
        emu:setKeys(current_mask)
        note(frame, step.name, "step", current_mask, nil, nil, nil)
    end
    frames_in_step = frames_in_step + 1

    local map_index, entry = read_map()
    local vofs = safe16(BG1_VOFS)

    if map_index ~= last_map then
        note(frame, step.name, "map", current_mask, map_index, entry, vofs)
        if last_map ~= nil and step.expect >= 0 and map_index ~= nil
            and map_index ~= step.expect and map_index ~= step.want_map then
            step_fail(step, "unexpected_map", map_index)
            return
        end
        last_map = map_index
    end

    local met = false
    if step.want_map >= 0 and map_index == step.want_map then met = true end
    if step.want_vofs >= 0 and vofs == step.want_vofs then met = true end
    if step.hold > 0 and frames_in_step >= step.hold then met = true end

    if met then
        note(frame, step.name, "met", current_mask, map_index, entry, vofs)
        step_index = step_index + 1
        frames_in_step = 0
        if step_index > #SCHEDULE then
            local final_index = map_index
            stop()
            note(frame, "route", "done", 0, final_index, entry, vofs)
            status(string.format("ROUTE DONE frame=%d map=%s",
                frame, final_index and tostring(final_index) or "none"))
        end
        return
    end

    if frames_in_step >= step.budget then
        step_fail(step, "timeout", map_index)
    end
end)
