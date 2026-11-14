local trace = os.getenv("DBZ_TRACE_SCRIPT")
assert(trace ~= nil and #trace > 0, "DBZ_TRACE_SCRIPT must name the trace script")

local marker = rom011_marker_path
assert(type(marker) == "string" and #marker > 0, "the launcher did not set rom011_marker_path")
local run_dir = marker:match("^(.*)/[^/]*$") or "."

if os.getenv("COMBAT001_OUT") == nil or os.getenv("COMBAT001_OUT") == "" then
    COMBAT001_OUT = run_dir .. "/combat001-trace.txt"
end

local KEYS = { A = 1, B = 2, SELECT = 4, START = 8, RIGHT = 16, LEFT = 32, UP = 64, DOWN = 128 }
local HOLDS = { LEFT = true, RIGHT = true, UP = true, DOWN = true, WAIT = true, MASH = true,
    UNTIL = true, TALK = true, PEEK = true }
local PLAYER_POINTER = 0x03001B94
local PLAYER_HEALTH = 0x03001574
local FLAG_BYTES = 0x030010BD
local TALK_LIMIT, TALK_GAP = 900, 20
local POS_X, POS_Y = 0x1A0, 0x1A4
local NEAR, GOTO_LIMIT, PRESS_FRAMES, PRESS_GAP, MASH_GAP, LOG_EVERY = 6, 600, 6, 24, 10, 15
local PLAN_FROM = 900

local function parse(text)
    local plan = {}
    for token in text:gmatch("[^,%s]+") do
        local name, first, second = token:match("^(%u+):?(%-?%d*):?(%-?%d*)$")
        assert(name ~= nil, "unreadable plan token " .. token)
        local step = { name = name, text = token, a = tonumber(first), b = tonumber(second) }
        if name == "GOTO" then
            assert(step.a ~= nil and step.b ~= nil, "GOTO needs x and y: " .. token)
        elseif HOLDS[name] then
            assert(step.a ~= nil and step.a > 0 and step.b == nil, name .. " needs one frame count: " .. token)
        elseif name == "SHOT" then
            assert(step.a == nil, "SHOT takes no number: " .. token)
        else
            assert(KEYS[name] ~= nil, "unknown plan token " .. token)
            step.a = step.a or 1
            assert(step.a > 0 and step.b == nil, name .. " takes one repeat count: " .. token)
        end
        plan[#plan + 1] = step
    end
    return plan
end

local sample = parse("MASH:30,LEFT:4,GOTO:10:-2,A,START:2,WAIT:5,SHOT,UNTIL:40,TALK:158,PEEK:157")
assert(#sample == 10 and sample[3].a == 10 and sample[3].b == -2 and sample[5].a == 2
        and sample[9].a == 158,
    "the plan reader failed its own sample")
assert(not pcall(parse, "JUMP:3"), "the plan reader accepted an unknown token")
assert(not pcall(parse, "GOTO:4"), "the plan reader accepted a GOTO without y")

local plan = parse(os.getenv("COMBAT001_PLAN") or "")

dofile(trace)

local route = assert(io.open(run_dir .. "/combat001-route.txt", "w"))
local function note(frame, event, step, x, y, text)
    route:write(table.concat({ tostring(frame), event, step or "", x and tostring(x) or "",
        y and tostring(y) or "", text or "" }, ",") .. "\n")
    route:flush()
end
note(0, "PLAN", "", nil, nil, "steps=" .. #plan)

local function signed(value)
    if value == nil then return nil end
    if value >= 0x80000000 then return value - 0x100000000 end
    return value
end

local function player()
    local ok, base = pcall(function() return emu:read32(PLAYER_POINTER) end)
    if not ok or base == nil or base < 0x02000000 or base >= 0x02040000 then return nil end
    local x = signed(emu:read32(base + POS_X))
    local y = signed(emu:read32(base + POS_Y))
    return x >> 8, y >> 8
end

local frame, index, started, held, finished = 0, 0, 0, 0, false

local function hold(mask)
    if held ~= 0 then emu:clearKeys(held) end
    held = mask
    if mask ~= 0 then emu:addKeys(mask) end
end

local function advance()
    hold(0)
    index = index + 1
    started = frame + 1
    local step = plan[index]
    if step == nil then
        finished = true
        local x, y = player()
        note(frame, "DONE", "", x, y, "plan finished")
        return
    end
    local x, y = player()
    note(frame, "STEP", step.text, x, y, "index=" .. index)
    if step.name == "SHOT" then
        local path = string.format("%s/shot-%05d.png", run_dir, frame)
        pcall(function() emu:screenshot(path) end)
        note(frame, "SHOT", step.text, x, y, path)
    end
end

local function flag_set(number)
    local ok, byte = pcall(function() return emu:read8(FLAG_BYTES + (number >> 3)) end)
    return ok and (byte & (1 << (number & 7))) ~= 0
end

local function talk(step)
    local spent = frame - started
    if flag_set(step.a) then
        hold(0)
        local x, y = player()
        note(frame, "TALKED", step.text, x, y, "flag " .. step.a .. " set after " .. spent .. " frames")
        return true
    end
    if spent >= TALK_LIMIT then
        hold(0)
        local x, y = player()
        note(frame, "EXPIRE", step.text, x, y, "flag " .. step.a .. " still clear")
        return true
    end
    local phase = spent % TALK_GAP
    if phase == 0 then hold(KEYS.A) elseif phase == PRESS_FRAMES then hold(0) end
    return false
end

local function steer(step)
    local x, y = player()
    if x == nil then return false end
    local dx, dy = step.a - x, step.b - y
    if math.abs(dx) <= NEAR and math.abs(dy) <= NEAR then
        note(frame, "ARRIVE", step.text, x, y, "")
        return true
    end
    if frame - started >= GOTO_LIMIT then
        note(frame, "EXPIRE", step.text, x, y, "")
        return true
    end
    local mask = 0
    if dx > NEAR then mask = mask | KEYS.RIGHT elseif dx < -NEAR then mask = mask | KEYS.LEFT end
    if dy > NEAR then mask = mask | KEYS.DOWN elseif dy < -NEAR then mask = mask | KEYS.UP end
    if mask ~= held then hold(mask) end
    return false
end

local function run(step)
    local spent = frame - started
    if step.name == "SHOT" then return true end
    if step.name == "GOTO" then return steer(step) end
    if step.name == "TALK" then return talk(step) end
    if step.name == "PEEK" then
        local x, y = player()
        note(frame, "PEEK", step.text, x, y, "flag " .. step.a .. (flag_set(step.a) and " set" or " clear"))
        return true
    end
    if step.name == "WAIT" then return spent >= step.a end
    if step.name == "UNTIL" then return frame >= step.a end
    if step.name == "MASH" then
        local phase = spent % MASH_GAP
        if phase == 0 then hold(KEYS.A) elseif phase == PRESS_FRAMES then hold(0) end
        return spent >= step.a
    end
    if KEYS[step.name] and HOLDS[step.name] then
        if spent == 0 then hold(KEYS[step.name]) end
        return spent >= step.a
    end
    local cycle = PRESS_FRAMES + PRESS_GAP
    local phase = spent % cycle
    if phase == 0 then hold(KEYS[step.name]) elseif phase == PRESS_FRAMES then hold(0) end
    return spent >= cycle * step.a
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame == 720 or frame == 760 then hold(KEYS.START) end
    if frame == 780 then hold(KEYS.A) end
    if frame == 726 or frame == 766 or frame == 786 then hold(0) end
    if frame % LOG_EVERY == 0 and not finished then
        local x, y = player()
        local ok, health = pcall(function() return emu:read32(PLAYER_HEALTH) end)
        if x ~= nil then
            local step = plan[index] and plan[index].text or ""
            note(frame, "POS", step, x, y, ok and ("hp=" .. (health >> 16)) or "")
        end
    end
    if frame < PLAN_FROM or finished then return end
    if index == 0 then
        advance()
        return
    end
    if run(plan[index]) then advance() end
end)

print([[combat001 route driver armed]])
