"""Play state for the key remapper: a UE4SS script that writes "play" or "menu" to a file.

The remapper runs outside the game, so it can't tell exploring from a menu or the name screen.
Windows doesn't help: the game draws its own cursor, which Windows reports as shown in menus and
in play alike. The game knows, though, so this script writes "play" while you explore with the
cursor hidden (the same test mouse look uses) and "menu" otherwise. The controls section ships
it whenever there are keyboard remaps.
"""
import json
import os

UE4SS_MOD_NAME = "WCModsPlayState"
STATE_FILE = "state.txt"


def state_path(cfg):
    """Where the script writes, or None without UE4SS."""
    mods_dir = cfg.ue4ss_mods_dir
    return os.path.join(mods_dir, UE4SS_MOD_NAME, STATE_FILE) if mods_dir else None


def script(path):
    return LUA_TEMPLATE.replace("@PATH@", json.dumps(path, ensure_ascii=False))


LUA_TEMPLATE = r'''-- Tells the wcmods key remapper whether you're playing (exploring with the cursor hidden) or in a
-- menu, by writing "play" or "menu" to a file it reads. Written by wcmods; see README, "Remapping keys".
local STATE_FILE = @PATH@

local function log(fmt, ...) print(string.format("[PlayState] " .. fmt .. "\n", ...)) end
if io == nil then
    log("this UE4SS has no io library, so the key remapper can't tell menus from play")
    return
end

local function write(state)
    local f = io.open(STATE_FILE, "w")
    if f then
        f:write(state)
        f:close()
    end
end

local function valid(o) return o ~= nil and o:IsValid() end
local pc, search, current = nil, 0, nil

local function playing()
    if not valid(pc) then
        pc, search = nil, search - 1
        if search > 0 then return false end
        search = 10   -- looking for the controller is slow; once a second until it exists
        for _, c in ipairs(FindAllOf("PlayerController") or {}) do
            if valid(c) and valid(c.Player) then
                pc = c
                break
            end
        end
        if not pc then return false end
    end
    if pc.bShowMouseCursor then return false end
    local pawn = pc.Pawn
    return valid(pawn) and pawn:GetClass():GetFName():ToString():find("Exploration_Character_Player", 1, true) ~= nil
end

write("menu")
LoopAsync(100, function()
    ExecuteInGameThread(function()
        local ok, now = pcall(playing)
        local state = (ok and now) and "play" or "menu"
        if state ~= current then
            current = state
            write(state)
        end
    end)
    return false
end)
log("loaded; writing to %s", STATE_FILE)
'''
