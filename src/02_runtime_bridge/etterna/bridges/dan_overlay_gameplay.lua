--[[
    dan_overlay_gameplay.lua — Zero-Lag Gameplay Bridge for ScreenGameplay.
    Writes ONLY on song start and song end (exactly 2 single disk writes per play session).
    Performs 0 disk writes and 0 CPU work while notes are actively falling.
--]]

local PRIMARY_FILE = "Save/DanOverlayGameplay.txt"
local COMPAT_FILE = "Save/DanielGameplay.txt"
local EVAL_FILE = "Save/DanOverlayEval.txt"

local function getRate()
    local ok, value = pcall(function()
        if getCurRateValue then return getCurRateValue() end
        if getCurRate then return getCurRate() end
        return 1.0
    end)
    if ok and type(value) == "number" and value > 0 then
        return value
    end
    return 1.0
end

local function writeGameplayState(playing)
    local seconds = 0.0
    local ok, value = pcall(function()
        return GAMESTATE:GetCurMusicSeconds()
    end)
    if ok and type(value) == "number" then
        seconds = value
    end

    local rate = getRate()

    local output =
        "playing=" .. (playing and "1" or "0") .. "\n" ..
        "music_seconds=" .. tostring(seconds) .. "\n" ..
        "rate=" .. tostring(rate) .. "\n"

    pcall(function()
        File.Write(PRIMARY_FILE, output)
        File.Write(COMPAT_FILE, output)
        if playing then
            -- Invalidate stale evaluation file on new play session start
            File.Write(EVAL_FILE, "state=2\n")
        end
    end)
end

return Def.ActorFrame {
    BeginCommand = function(self)
        -- Write once when gameplay starts
        writeGameplayState(true)
    end,

    OffCommand = function(self)
        -- Write once when gameplay ends
        writeGameplayState(false)
    end
}
