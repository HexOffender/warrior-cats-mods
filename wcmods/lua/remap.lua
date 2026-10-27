-- Key remaps inside the game, for Warrior Cats: Clans of the Forest. Written by wcmods from your mods'
-- controls.json: change those (or the studio's Controls page) and install again rather than editing this.
--
-- The game keeps its bindings in native code (the player's input mappings and its rebinding screen aren't
-- reflected), so they can't be changed from a script. What is reflected is the step after them: each key
-- the game sees goes to its listeners (the player controller, and each screen that's open, the HUD's too)
-- as OnKeyPressed(key), and each of the game's commands bound to that key goes to them as
-- OnListenCommand(command, event): Interact and Pounce while you play, Up, Confirm and Back in menus. So
-- this script works there:
-- - when a listener hears a key that now stands for a command, the command is sent to it, the same way
--   the game sends its own (through the controller's input component, or to the screen);
-- - when one of the game's own commands arrives from a key it moved away from, it's turned into
--   NoCommand, which every listener ignores.
-- Movement and the camera are axes, read by the game every frame rather than sent as commands, so they
-- can't be moved here; the key remapper outside the game (`wcmods play`) does those.
local PLAN = @PLAN@
-- PLAN.play and PLAN.menu: what applies while you explore (the controller and the HUD) and in the game's
-- menus. In each, send = {key = {command, ...}}: pressing the key sends those commands;
-- drop = {command = {key, ...}}: the game's own command is dropped when it comes from one of these keys.
-- PLAN.keys: {action = {key, ...}}: every key each changed action is on now, for other scripts.

local PRESSED, RELEASED = 0, 1   -- EInputEvent
local NO_COMMAND = 0

local function log(fmt, ...) print(string.format("[Remap] " .. fmt .. "\n", ...)) end
local function debug(fmt, ...) if PLAN.debug then log(fmt, ...) end end

local reported, nreported = {}, 0
local function report(where, err)
    local key = where .. tostring(err)
    if reported[key] or nreported >= 20 then return end
    reported[key], nreported = true, nreported + 1
    log("error in %s: %s", where, tostring(err))
end

local function valid(o) return o ~= nil and o:IsValid() end

-- Other scripts (WCModsGame's Game.npcs, which listens to Interact itself) read where an action is now.
for action, keys in pairs(PLAN.keys) do
    pcall(function() ModRef:SetSharedVariable("WCModsRemap." .. action, table.concat(keys, ",")) end)
end

local send = { play = {}, menu = {} }   -- key -> {command numbers}
local drop = { play = {}, menu = {} }   -- command number -> {FKey}
local fkeys = {}
local function fkey(name)
    local k = fkeys[name]
    if not k then
        k = { KeyName = FName(name) }
        fkeys[name] = k
    end
    return k
end

-- Command numbers by name, from the game's ECommands enum (its numbers moved in patch 1.1, so they're
-- never written down here).
local function commands()
    local e = StaticFindObject("/Script/SwtEngine.ECommands")
    if not valid(e) then return nil end
    local byName = {}
    e:ForEachName(function(name, value)
        byName[(name:ToString():gsub("^ECommands::", ""))] = value
    end)
    return byName
end

-- Which set applies to a listener. While you explore, the keys go to the controller and the HUD's two
-- screens; with a menu open, only to the menu's screen; in a fight, to all of those and the fight's
-- menu, which counts as a menu. (The game draws its own cursor, so the engine's
-- cursor flag can't tell: it reads false in the pause menu and the map too.)
local PLAY_SCREENS = { WBP_GuiHudGameWrc_C = true, WBP_GuiScreenOnlineOver_C = true }
local function where(how, listener)
    if how == "controller" then return "play" end
    local ok, name = pcall(function() return listener:GetClass():GetFName():ToString() end)
    return (ok and PLAY_SCREENS[name]) and "play" or "menu"
end

local injecting = false
local held = {}   -- listener address .. key -> {listener, key, how, from, controller, where}

-- Send one command to a listener: the controller through its input component (which reaches every
-- listener of the controller's input), a screen to the screen itself.
local function deliver(listener, how, command, event, from)
    injecting = true
    local ok, err = pcall(function()
        if how == "controller" then
            listener.InputComponent:OnListenCommandInternal(command, event)
        else
            listener:OnListenCommand(command, event, from)
        end
    end)
    injecting = false
    if not ok then report("sending a command", err) end
end

local function keyName(param)
    local ok, name = pcall(function() return param:get().KeyName:ToString() end)
    return ok and name or nil
end

local function onKey(how, event)
    return function(ctx, keyParam, fromParam)
        local name = keyName(keyParam)
        if not (name and (send.play[name] or send.menu[name])) then return end
        local listener = ctx:get()
        local from = fromParam and fromParam:get() or nil
        local pc = how == "controller" and listener or from
        local id = tostring(listener:GetAddress()) .. name
        local h = held[id]
        if event == PRESSED then
            -- A press finishes as it started: its release goes to the same set, even if a menu opened.
            h = { listener = listener, key = name, how = how, from = from, controller = pc, where = where(how, listener) }
            held[id] = h
        elseif not h then
            return   -- a release whose press this listener didn't get (it was in another screen)
        else
            held[id] = nil
        end
        for _, command in ipairs(send[h.where][name] or {}) do
            debug("%s %s -> command %d (%s, %s)", name, event == PRESSED and "pressed" or "released", command, how, h.where)
            deliver(listener, how, command, event, from)
        end
    end
end

-- Whether a command the game sent came from one of these keys: the one that went down (or up) this frame.
local function fromKeys(pc, keys, event)
    if not valid(pc) then return false end
    for _, k in ipairs(keys) do
        local ok, yes = pcall(function()
            if event == PRESSED then return pc:WasInputKeyJustPressed(k) end
            if event == RELEASED then return pc:WasInputKeyJustReleased(k) end
            return pc:IsInputKeyDown(k)
        end)
        if ok and yes then return true end
    end
    return false
end

local function onCommand(how)
    return function(ctx, commandParam, eventParam, fromParam)
        if injecting then return end
        local command = commandParam:get()
        if not (drop.play[command] or drop.menu[command]) then return end
        local listener = ctx:get()
        local pc = how == "controller" and listener or (fromParam and fromParam:get())
        local keys = drop[where(how, listener)][command]
        local event = eventParam:get()
        if keys and fromKeys(pc, keys, event) then
            debug("dropped the game's command %d (event %d, %s)", command, event, how)
            commandParam:set(NO_COMMAND)
        end
    end
end

-- A key let go while a screen had it, so its listener never heard the release: release it anyway, or an
-- action that's held (Run, Crouch) would stay on.
local function releaseLost()
    for id, h in pairs(held) do
        local down = false
        local ok = pcall(function() down = valid(h.listener) and valid(h.controller) and h.controller:IsInputKeyDown(fkey(h.key)) end)
        if not (ok and down) then
            held[id] = nil
            if ok and valid(h.listener) then
                for _, command in ipairs(send[h.where][h.key] or {}) do deliver(h.listener, h.how, command, RELEASED, h.from) end
            end
        end
    end
end

local HOOKS = {
    { "/Script/SwtEngine.SwtPlayerController:OnKeyPressed", onKey("controller", PRESSED) },
    { "/Script/SwtEngine.SwtPlayerController:OnKeyReleased", onKey("controller", RELEASED) },
    { "/Script/SwtEngine.SwtPlayerController:OnListenCommand", onCommand("controller") },
    { "/Script/SwtEngine.SwtScreen:OnKeyPressed", onKey("screen", PRESSED) },
    { "/Script/SwtEngine.SwtScreen:OnKeyReleased", onKey("screen", RELEASED) },
    { "/Script/SwtEngine.SwtScreen:OnListenCommand", onCommand("screen") },
}

local function setup()
    local byName = commands()
    if not byName then return false end
    local nkeys = 0
    for _, set in ipairs({ "play", "menu" }) do
        for key, names in pairs(PLAN[set].send) do
            send[set][key] = {}
            nkeys = nkeys + 1
            for _, name in ipairs(names) do
                local n = byName[name]
                if n then send[set][key][#send[set][key] + 1] = n else log("the game has no command %s", name) end
            end
        end
        for name, keys in pairs(PLAN[set].drop) do
            local n = byName[name]
            if n then
                drop[set][n] = {}
                for i, k in ipairs(keys) do drop[set][n][i] = fkey(k) end
            end
        end
    end
    for _, h in ipairs(HOOKS) do
        local path, fn = h[1], h[2]
        local ok, err = pcall(RegisterHook, path, function(...)
            local okCall, e = pcall(fn, ...)
            if not okCall then report(path, e) end
        end)
        if not ok then log("can't hook %s: %s", path, tostring(err)) end
    end
    log("remapping in game: %d keys in play and menus", nkeys)
    return true
end

-- Everything runs on the game thread, where the hooks do (two threads in one Lua state crash the game).
-- The game's classes are there once it has started, so the hooks go in on the first tick that finds them.
local ready, failed = false, false
local function tick()
    if not ready and not failed then
        local ok, done = pcall(setup)
        if not ok then report("setup", done) end
        ready, failed = ok and done, not ok
    end
    if next(held) then
        local ok, err = pcall(releaseLost)
        if not ok then report("letting go of keys", err) end
    end
end
if LoopInGameThreadAfterFrames == nil or not pcall(LoopInGameThreadAfterFrames, 6, tick) then
    LoopAsync(100, function()
        ExecuteInGameThread(tick)
        return false
    end)
end
