local trace = os.getenv("DBZ_TRACE_SCRIPT")
assert(trace ~= nil and #trace > 0, "DBZ_TRACE_SCRIPT must name the trace script")

local marker = rom011_marker_path
assert(type(marker) == "string" and #marker > 0, "the launcher did not set rom011_marker_path")
local run_dir = marker:match("^(.*)/[^/]*$") or "."

if os.getenv("COMBAT001_OUT") == nil or os.getenv("COMBAT001_OUT") == "" then
    COMBAT001_OUT = run_dir .. "/combat001-trace.txt"
end

dofile(trace)

local KEY_A, KEY_START = 1, 8
local MASH_FROM = 900
local MASH_TO = tonumber(os.getenv("COMBAT001_FRAMES") or "4000") or 4000
local MASH_GAP = 10
local PRESS_FRAMES = 6

local frame = 0
local last_press = -99
local pending = nil

local function press(mask)
    emu:addKeys(mask)
    pending = { mask = mask, off = frame + PRESS_FRAMES }
end

callbacks:add("frame", function()
    frame = frame + 1
    if pending ~= nil and frame >= pending.off then
        emu:clearKeys(pending.mask)
        pending = nil
    end
    if frame == 720 or frame == 760 then press(KEY_START) end
    if frame == 780 then press(KEY_A) end
    if pending == nil and frame >= MASH_FROM and frame <= MASH_TO
            and frame - last_press >= MASH_GAP then
        last_press = frame
        press(KEY_A)
    end
end)

print([[combat001 input driver armed]])
