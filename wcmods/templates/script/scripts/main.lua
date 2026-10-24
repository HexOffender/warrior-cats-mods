-- An in-game script. Game is WCModsGame and MOD is this mod (its settings in MOD.settings); see
-- docs/scripting.md for every call. Needs "allow_code_mods": true in wcmods.json and an install.
local S = MOD.settings

Game.on("player", function(cat)
    if cat and S.enabled then MOD.log("%s (%s)", S.message, Game.cat():name() or "your cat") end
end)
