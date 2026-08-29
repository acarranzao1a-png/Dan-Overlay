local PRIMARY_FILE = "Save/DanOverlayBridge.txt"
local COMPAT_FILE = "Save/DanielBridge.txt"

local lastChartKey = ""
local lastRateVal = 1.0

local function writeBridgeState(song, steps)
    if song == nil then
        return
    end

    if steps == nil then
        steps = GAMESTATE:GetCurrentSteps()
    end

    local title = song:GetDisplayMainTitle() or ""
    local artist = song:GetDisplayArtist() or ""
    local song_dir = song:GetSongDir() or ""

    local difficulty = ""
    local meter = ""
    local stepstype = ""
    local description = ""
    local step_file = ""

    if steps ~= nil then
        difficulty = tostring(steps:GetDifficulty() or "")
        meter = tostring(steps:GetMeter() or "")
        stepstype = tostring(steps:GetStepsType() or "")
        description = steps:GetDescription() or ""
        step_file = steps:GetFilename() or ""
    end

    local rate = 1.0
    local ok_rate, rate_val = pcall(function()
        if getCurRateValue then return getCurRateValue() end
        if getCurRate then return getCurRate() end
        return 1.0
    end)
    if ok_rate and type(rate_val) == "number" and rate_val > 0 then
        rate = rate_val
    end

    local msd_overall = 0
    local msd_stream = 0
    local msd_jumpstream = 0
    local msd_handstream = 0
    local msd_stamina = 0
    local msd_jackspeed = 0
    local msd_chordjack = 0
    local msd_technical = 0

    if steps ~= nil then
        local function safeMSD(index)
            local ok, value = pcall(function()
                return steps:GetMSD(rate, index)
            end)
            if ok and type(value) == "number" then
                return value
            end
            return 0
        end

        msd_overall = safeMSD(1)
        msd_stream = safeMSD(2)
        msd_jumpstream = safeMSD(3)
        msd_handstream = safeMSD(4)
        msd_stamina = safeMSD(5)
        msd_jackspeed = safeMSD(6)
        msd_chordjack = safeMSD(7)
        msd_technical = safeMSD(8)
    end

    local output =
        "bridge_version=5\n" ..
        "game=etterna\n" ..
        "title=" .. title .. "\n" ..
        "artist=" .. artist .. "\n" ..
        "song_dir=" .. song_dir .. "\n" ..
        "step_file=" .. step_file .. "\n" ..
        "description=" .. description .. "\n" ..
        "difficulty=" .. difficulty .. "\n" ..
        "meter=" .. meter .. "\n" ..
        "stepstype=" .. stepstype .. "\n" ..
        "rate=" .. tostring(rate) .. "\n" ..
        "msd_overall=" .. tostring(msd_overall) .. "\n" ..
        "msd_stream=" .. tostring(msd_stream) .. "\n" ..
        "msd_jumpstream=" .. tostring(msd_jumpstream) .. "\n" ..
        "msd_handstream=" .. tostring(msd_handstream) .. "\n" ..
        "msd_stamina=" .. tostring(msd_stamina) .. "\n" ..
        "msd_jackspeed=" .. tostring(msd_jackspeed) .. "\n" ..
        "msd_chordjack=" .. tostring(msd_chordjack) .. "\n" ..
        "msd_technical=" .. tostring(msd_technical) .. "\n"

    pcall(function()
        File.Write(PRIMARY_FILE, output)
        File.Write(COMPAT_FILE, output)
    end)
end

local function checkAndUpdate()
    local song = GAMESTATE:GetCurrentSong()
    local steps = GAMESTATE:GetCurrentSteps()
    if not song then return end

    local songDir = song:GetSongDir() or ""
    local stepFile = steps and (steps:GetFilename() or "") or ""

    -- If steps belong to a different song during rapid wheel scrolling, fetch matching steps from current song
    if songDir ~= "" and (stepFile == "" or not string.find(stepFile, songDir, 1, true)) then
        local allSteps = song:GetAllSteps()
        if allSteps and #allSteps > 0 then
            local curDiff = steps and steps:GetDifficulty()
            local matched = false
            for _, s in ipairs(allSteps) do
                if curDiff and s:GetDifficulty() == curDiff then
                    steps = s
                    stepFile = s:GetFilename() or ""
                    matched = true
                    break
                end
            end
            if not matched then
                steps = allSteps[1]
                stepFile = steps:GetFilename() or ""
            end
        end
    end

    if not steps then return end

    local chartKey = (song:GetDisplayMainTitle() or "") .. "::" .. stepFile .. "::" .. tostring(steps:GetDifficulty() or "") .. "::" .. tostring(steps:GetMeter() or "")
    local rate = 1.0
    pcall(function()
        if getCurRateValue then rate = getCurRateValue() end
    end)

    if chartKey ~= lastChartKey or rate ~= lastRateVal then
        lastChartKey = chartKey
        lastRateVal = rate
        writeBridgeState(song, steps)
    end
end

return Def.ActorFrame {
    BeginCommand = function(self)
        checkAndUpdate()
        local elapsed = 0
        self:SetUpdateFunction(function(actor, delta)
            elapsed = elapsed + delta
            if elapsed >= 0.08 then
                elapsed = 0
                checkAndUpdate()
            end
        end)
    end,

    CurrentSongChangedMessageCommand = function(self) checkAndUpdate() end,
    CurrentStepsChangedMessageCommand = function(self) checkAndUpdate() end,
    DelayedChartUpdateMessageCommand = function(self) checkAndUpdate() end,
    WheelSettledMessageCommand = function(self) checkAndUpdate() end,
    ChangedStepsMessageCommand = function(self) checkAndUpdate() end,
    CurrentRateChangedMessageCommand = function(self) checkAndUpdate() end,
    SortOrderChangedMessageCommand = function(self) checkAndUpdate() end,
    TabChangedMessageCommand = function(self) checkAndUpdate() end,
}
