local CLEAN_SIZE = 16777216
local GAME_CODE = "AGB-ALFE"
local PRESS_FRAMES = 1800
local DIALOGUE_FRAMES = 3600
local WALK_UNTIL = 5400
local SAMPLE_EVERY = 60
local STOP_FRAME = 5520

assert(emu ~= nil, "mGBA did not attach the emulation core")
local code = emu:getGameCode()
assert(code == GAME_CODE or code == "ALFE",
    "unexpected game code: " .. tostring(code))
assert(emu:romSize() == CLEAN_SIZE,
    "expected the clean 16 MiB image, got " .. tostring(emu:romSize()))

local out_path = os.getenv("O1_ROUTE_OUT")
assert(out_path and #out_path > 0, "O1_ROUTE_OUT not provided")
local file = assert(io.open(out_path, "w"), "cannot open route log")
file:write("frame,vcount,keyinput,bg0hofs,bg0vofs,bg1hofs,bg2hofs,dispcnt,oam_active,oam0x,oam0y,note\n")
file:flush()

local frame = 0
local callback_id
local pressed = false
local shot_errors = 0
local shot_prefix = os.getenv("O1_SHOT_PREFIX") or "o1-route"

local function sample(note)
    local vcount = emu:read16(0x04000006)
    local keys = emu:read16(0x04000130)
    local hofs = emu:read16(0x04000010)
    local vofs = emu:read16(0x04000012)
    local b1 = emu:read16(0x04000014)
    local b2 = emu:read16(0x04000018)
    local dispcnt = emu:read16(0x04000000)
    local active, x0, y0 = 0, -1, -1
    for i = 0, 127 do
        local base = 0x07000000 + i * 8
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
    file:write(string.format("%d,%d,0x%04X,%d,%d,%d,%d,0x%04X,%d,%d,%d,%s\n",
        frame, vcount, keys, hofs, vofs, b1, b2, dispcnt, active, x0, y0, note))
    file:flush()
    if frame % 300 == 0 or (note ~= "advancing" and note ~= "dialogue") then
        local shot = string.format("%s-%06d.png", shot_prefix, frame)
        local ok, err = pcall(function() emu:screenshot(shot) end)
        if not ok then
            shot_errors = shot_errors + 1
            if shot_errors == 1 then
                file:write(string.format("# screenshot failed: %s\n", tostring(err)))
                file:flush()
            end
        end
    end
end

local function finish()
    emu:setKeys(0)
    sample("route-complete")
    file:close()
    if callback_id ~= nil then
        callbacks:remove(callback_id)
        callback_id = nil
    end
end

emu:setKeys(0)
sample("route-start")

callback_id = callbacks:add("frame", function()
    frame = frame + 1

    if frame <= PRESS_FRAMES then
        if not pressed and frame % 40 == 0 then
            emu:addKey(C.GBA_KEY.A)
            emu:addKey(C.GBA_KEY.START)
            pressed = true
        elseif pressed and frame % 40 == 20 then
            emu:clearKey(C.GBA_KEY.A)
            emu:clearKey(C.GBA_KEY.START)
            pressed = false
        end
    elseif frame == PRESS_FRAMES + 1 then
        emu:setKeys(0)
        sample("input-released")
    elseif frame <= DIALOGUE_FRAMES then
        local phase = frame % 20
        if phase == 0 then
            emu:addKey(C.GBA_KEY.A)
        elseif phase == 10 then
            emu:clearKey(C.GBA_KEY.A)
        end
    elseif frame == DIALOGUE_FRAMES + 1 then
        emu:setKeys(0)
        sample("dialogue-cleared")
    elseif frame > DIALOGUE_FRAMES + 60 and frame <= WALK_UNTIL then
        local phase = (frame - DIALOGUE_FRAMES) % 1200
        if phase == 0 then
            emu:setKeys(0)
            emu:addKey(C.GBA_KEY.LEFT)
        elseif phase == 300 then
            emu:setKeys(0)
            emu:addKey(C.GBA_KEY.UP)
        elseif phase == 600 then
            emu:setKeys(0)
            emu:addKey(C.GBA_KEY.RIGHT)
        elseif phase == 900 then
            emu:setKeys(0)
            emu:addKey(C.GBA_KEY.DOWN)
        end
    elseif frame == WALK_UNTIL + 1 then
        emu:setKeys(0)
    end

    if frame % SAMPLE_EVERY == 0 then
        local phase_note = "advancing"
        if frame > WALK_UNTIL then
            phase_note = "settled"
        elseif frame > DIALOGUE_FRAMES then
            phase_note = "walking"
        elseif frame > PRESS_FRAMES then
            phase_note = "dialogue"
        end
        sample(phase_note)
    end

    if frame == STOP_FRAME then
        finish()
    end
end)
