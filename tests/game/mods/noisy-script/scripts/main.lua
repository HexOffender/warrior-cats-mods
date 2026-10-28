-- A throwaway script for tests/game/test_scripts.py. Each part is something a creator's script gets wrong.

-- A frame function that fails every frame: the log should say so once, with this mod's name, then once a minute.
Game.onFrame(function()
    local cat = nil
    return cat.whiskers
end)

-- A key name UE4SS doesn't know (its names are in capitals): a line in the log, false back, and the script goes on.
NOISY_KEY = Game.onKey("f6", function() MOD.log("f6 pressed") end)

MOD.log("still here")
