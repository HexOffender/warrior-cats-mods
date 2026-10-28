-- Tells the wcmods key remapper whether you're playing (exploring, talking to a cat, photo mode) or in one
-- of the game's menus (the pause menu, the map, a fight's menu), by writing "play" or "menu" to a file it
-- reads. Written by wcmods; see docs/remapping.md.
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
local menuAt, menuShown = nil, false

-- One of the game's screens showing (the pause menu, the map, the inventory, a fight's menu) is a menu.
-- The engine's cursor flag can't say: the game draws its own cursor, and the flag reads false in menus.
-- Looked at four times a second at most, as WCModsGame's Game.screens() does.
local function menuShowing()
    if menuAt and os.clock() - menuAt < 0.25 then return menuShown end
    menuAt, menuShown = os.clock(), false
    for _, w in ipairs(FindAllOf("GuiScreenWrc") or {}) do
        local ok, shown = pcall(function() return w:IsVisible() end)
        if ok and shown then
            menuShown = true
            break
        end
    end
    return menuShown
end

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
    if menuShowing() then return false end
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
