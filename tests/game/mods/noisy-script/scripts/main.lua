-- A throwaway script for tests/game/test_scripts.py. Each part is something a creator's script gets wrong.

-- A frame function that fails every frame: the log should say so once, with this mod's name, not once a frame.
-- Only its first 300 frames: one failing all session long is said again once a minute, and that line would land
-- in whichever test is running then, which fails it (agent test fails a test on a script error in the log).
local frames = 0
Game.onFrame(function()
    frames = frames + 1
    if frames > 300 then return end
    local cat = nil
    return cat.whiskers
end)

-- A key name UE4SS doesn't know (its names are in capitals): a line in the log, false back, and the script goes on.
NOISY_KEY = Game.onKey("f6", function() MOD.log("f6 pressed") end)

MOD.log("still here")
