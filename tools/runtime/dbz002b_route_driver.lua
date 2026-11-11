local A = 0x01
local START = 0x08
local RIGHT = 0x10
local LEFT = 0x20
local UP = 0x40
local DOWN = 0x80

local LAST = tonumber(os.getenv("DBZ002B_DRIVE_FRAMES") or "1000")
local ROUTE = os.getenv("DBZ002B_ROUTE") or "clone"

local ROUTES = {
    clone = {
        { UP, 180 }, { 0, 15 },
        { DOWN, 720 }, { 0, 15 },
        { 0, 400 },
    },
    office = {
        { UP, 180 }, { 0, 15 },
        { DOWN, 720 }, { 0, 30 },
        { UP, 90 }, { 0, 15 },
        { A, 6 }, { 0, 60 }, { A, 6 }, { 0, 60 },
        { UP, 60 }, { 0, 15 },
        { A, 6 }, { 0, 90 }, { A, 6 }, { 0, 90 },
        { 0, 400 },
    },
    talkend = {
        { UP, 180 }, { 0, 15 },
        { DOWN, 640 }, { 0, 20 },
        { A, 6 }, { 0, 90 }, { A, 6 }, { 0, 90 },
        { A, 6 }, { 0, 90 }, { A, 6 }, { 0, 90 },
        { A, 6 }, { 0, 90 }, { A, 6 }, { 0, 90 },
        { A, 6 }, { 0, 90 }, { A, 6 }, { 0, 90 },
        { A, 6 }, { 0, 90 }, { A, 6 }, { 0, 90 },
        { A, 6 }, { 0, 90 }, { A, 6 }, { 0, 90 },
        { A, 6 }, { 0, 90 }, { A, 6 }, { 0, 90 },
        { 0, 420 },
        { UP, 300 }, { 0, 30 },
        { 0, 700 },
    },
    north = {
        { UP, 2400 }, { 0, 200 },
    },
    menu = {
        { 0, 120 },
        { START, 6 }, { 0, 60 },
        { DOWN, 6 }, { 0, 40 },
        { DOWN, 6 }, { 0, 40 },
        { DOWN, 6 }, { 0, 40 },
        { A, 6 }, { 0, 120 },
        { START, 6 }, { 0, 60 },
    },
    idle = { { 0, 60 } },
    talk = {
        { UP, 180 }, { 0, 15 },
        { DOWN, 640 }, { 0, 20 },
        { A, 6 }, { 0, 70 },
        { A, 6 }, { 0, 70 },
        { A, 6 }, { 0, 70 },
        { A, 6 }, { 0, 70 },
        { A, 6 }, { 0, 70 },
        { A, 6 }, { 0, 70 },
        { A, 6 }, { 0, 70 },
        { 0, 150 },
        { LEFT, 60 }, { 0, 10 },
        { UP, 140 }, { 0, 10 },
        { 0, 400 },
    },
    inside = {
        { UP, 180 }, { 0, 15 },
        { DOWN, 640 }, { 0, 20 },
        { A, 6 }, { 0, 54 }, { RIGHT, 40 }, { 0, 10 },
        { A, 6 }, { 0, 54 }, { LEFT, 80 }, { 0, 10 },
        { A, 6 }, { 0, 54 }, { UP, 40 }, { 0, 10 },
        { A, 6 }, { 0, 54 }, { DOWN, 40 }, { 0, 10 },
        { A, 6 }, { 0, 54 }, { RIGHT, 80 }, { 0, 10 },
        { A, 6 }, { 0, 54 }, { A, 6 }, { 0, 54 },
        { 0, 300 },
    },
}

local MASH_PERIOD = 150
local MASH_START = 32000
local START_FRAME = 240

local schedule = ROUTES[ROUTE]
local frame = 0
local step = 1
local remaining = schedule and schedule[1][2] or 0
local cid

local function release()
    emu:setKeys(0)
    if cid then callbacks:remove(cid) end
end

cid = callbacks:add("frame", function()
    frame = frame + 1
    if frame > LAST then
        release()
        return
    end

    if ROUTE == "mash" then
        if frame == START_FRAME then
            emu:setKeys(START)
        elseif frame == START_FRAME + 6 then
            emu:setKeys(0)
        elseif frame > START_FRAME + 30 and frame <= MASH_START
            and (frame - START_FRAME) % MASH_PERIOD == 0 then
            emu:setKeys(A)
        elseif frame > START_FRAME + 30 and frame <= MASH_START
            and (frame - START_FRAME - 6) % MASH_PERIOD == 0 then
            emu:setKeys(0)
        end
        return
    end

    emu:setKeys(schedule[step][1])
    remaining = remaining - 1
    if remaining <= 0 then
        step = step + 1
        if step > #schedule then
            release()
            return
        end
        remaining = schedule[step][2]
    end
end)
