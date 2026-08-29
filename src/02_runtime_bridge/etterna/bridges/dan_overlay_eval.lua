--[[
    dan_overlay_eval.lua — Precision Evaluation Bridge for ScreenEvaluation.
    Extracts the official Wife% score directly from SCOREMAN / PlayerStageStats / Replay rescorer.
--]]

local PRIMARY_FILE = "Save/DanOverlayEval.txt"
local COMPAT_FILE = "Save/DanielEval.txt"

local function writeEvalState()
    local percent = 0.0
    local grade = ""
    local failed = 0
    local judge = 4

    pcall(function()
        if GetTimingDifficulty ~= nil then
            judge = GetTimingDifficulty()
        end
    end)

    -- 1. Try to get score from SCOREMAN (the official Etterna HighScore object)
    local score = nil
    pcall(function()
        if SCOREMAN ~= nil and SCOREMAN.GetMostRecentScore ~= nil then
            score = SCOREMAN:GetMostRecentScore()
        end
        if score == nil and SCOREMAN ~= nil and SCOREMAN.GetTempReplayScore ~= nil then
            score = SCOREMAN:GetTempReplayScore()
        end
    end)

    local pss = nil
    pcall(function()
        if STATSMAN ~= nil and STATSMAN.GetCurStageStats ~= nil then
            local ss = STATSMAN:GetCurStageStats()
            if ss ~= nil and ss.GetPlayerStageStats ~= nil then
                pss = ss:GetPlayerStageStats(PLAYER_1)
            end
        end
    end)

    -- Try to compute the exact Wife3 score matching the active Judge (J4, J5, J6, etc.)
    if score ~= nil and getRescoredWife3Judge ~= nil then
        pcall(function()
            local replay = nil
            if score.GetReplay ~= nil then
                replay = score:GetReplay()
            end
            if replay ~= nil then
                if replay.LoadAllData ~= nil then
                    replay:LoadAllData()
                end
                local dvtTmp = {}
                if replay.GetOffsetVector ~= nil then
                    dvtTmp = replay:GetOffsetVector() or {}
                end
                local tvt = {}
                if replay.GetTapNoteTypeVector ~= nil then
                    tvt = replay:GetTapNoteTypeVector() or {}
                end
                local dvt = {}
                if #tvt > 0 then
                    for i, d in ipairs(dvtTmp) do
                        local ty = tvt[i]
                        if ty == "TapNoteType_Tap" or ty == "TapNoteType_HoldHead" or ty == "TapNoteType_Lift" then
                            dvt[#dvt+1] = d
                        end
                    end
                else
                    dvt = dvtTmp
                end

                local totalTaps = 0
                local tapJudgments = {
                    "TapNoteScore_W1", "TapNoteScore_W2", "TapNoteScore_W3",
                    "TapNoteScore_W4", "TapNoteScore_W5", "TapNoteScore_Miss"
                }
                for _, j in ipairs(tapJudgments) do
                    if score.GetTapNoteScore ~= nil then
                        totalTaps = totalTaps + (score:GetTapNoteScore(j) or 0)
                    end
                end

                local totalHolds = 0
                local holdsHit = 0
                if pss ~= nil and pss.GetRadarPossible ~= nil and pss.GetRadarActual ~= nil then
                    totalHolds = (pss:GetRadarPossible():GetValue("RadarCategory_Holds") or 0) + (pss:GetRadarPossible():GetValue("RadarCategory_Rolls") or 0)
                    holdsHit = (pss:GetRadarActual():GetValue("RadarCategory_Holds") or 0) + (pss:GetRadarActual():GetValue("RadarCategory_Rolls") or 0)
                end
                local holdsMissed = math.max(0, totalHolds - holdsHit)

                local minesHit = 0
                local mineV = {}
                if replay.GetMineHitVector ~= nil then
                    mineV = replay:GetMineHitVector() or {}
                end
                if #mineV > 0 then
                    minesHit = #mineV
                elseif pss ~= nil and pss.GetRadarPossible ~= nil and pss.GetRadarActual ~= nil then
                    minesHit = (pss:GetRadarPossible():GetValue("RadarCategory_Mines") or 0) - (pss:GetRadarActual():GetValue("RadarCategory_Mines") or 0)
                end

                local rst = {
                    dvt = dvt,
                    totalHolds = totalHolds,
                    holdsHit = holdsHit,
                    holdsMissed = holdsMissed,
                    minesHit = minesHit,
                    totalTaps = totalTaps
                }

                local rescored = getRescoredWife3Judge(3, judge, rst)
                if rescored ~= nil and rescored > 0 then
                    percent = rescored
                end
            end
        end)
    end

    -- Fallback 1: score:GetWifeScore()
    if percent <= 0.0 and score ~= nil then
        pcall(function()
            if score.GetWifeScore ~= nil then
                percent = score:GetWifeScore() * 100.0
            end
        end)
    end

    -- Fallback 2: pss:GetCurWifeScore()
    if percent <= 0.0 and pss ~= nil then
        pcall(function()
            if pss.GetCurWifeScore ~= nil then
                percent = pss:GetCurWifeScore() * 100.0
            elseif pss.GetWifeScore ~= nil then
                percent = pss:GetWifeScore() * 100.0
            elseif pss.GetPercentDancePoints ~= nil then
                percent = pss:GetPercentDancePoints() * 100.0
            end
        end)
    end

    if score ~= nil then
        pcall(function()
            if score.GetFailed ~= nil and score:GetFailed() then
                failed = 1
            end
            if score.GetGrade ~= nil then
                grade = tostring(score:GetGrade() or "")
            end
        end)
    elseif pss ~= nil then
        pcall(function()
            if pss.GetFailed ~= nil and pss:GetFailed() then
                failed = 1
            end
            if pss.GetGrade ~= nil then
                grade = tostring(pss:GetGrade() or "")
            end
        end)
    end

    local song = nil
    local title = ""
    local artist = ""
    pcall(function()
        if GAMESTATE ~= nil and GAMESTATE.GetCurrentSong ~= nil then
            song = GAMESTATE:GetCurrentSong()
            if song ~= nil then
                if song.GetDisplayMainTitle ~= nil then title = song:GetDisplayMainTitle() or "" end
                if song.GetDisplayArtist ~= nil then artist = song:GetDisplayArtist() or "" end
            end
        end
    end)

    local rate = 1.0
    pcall(function()
        if getCurRateValue ~= nil then rate = getCurRateValue() end
        if getCurRate ~= nil then rate = getCurRate() end
    end)

    local output =
        "state=7\n" ..
        "accuracy=" .. string.format("%.4f", percent) .. "\n" ..
        "failed=" .. tostring(failed) .. "\n" ..
        "grade=" .. grade .. "\n" ..
        "judge=" .. tostring(judge) .. "\n" ..
        "title=" .. title .. "\n" ..
        "artist=" .. artist .. "\n" ..
        "rate=" .. tostring(rate) .. "\n" ..
        "timestamp=" .. tostring(os.time()) .. "\n"

    pcall(function()
        File.Write(PRIMARY_FILE, output)
        File.Write(COMPAT_FILE, output)
    end)
end

return Def.ActorFrame {
    BeginCommand = function(self)
        writeEvalState()
    end,
    OnCommand = function(self)
        writeEvalState()
    end,
    InitCommand = function(self)
        self:queuecommand("DelayedWrite")
    end,
    DelayedWriteCommand = function(self)
        writeEvalState()
    end
}
