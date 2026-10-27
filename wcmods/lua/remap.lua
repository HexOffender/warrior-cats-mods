-- Key remaps inside the game, for Warrior Cats: Clans of the Forest. Written by wcmods from your mods'
-- controls.json: change those (or the studio's Controls page) and install again rather than editing this.
--
-- The game keeps its bindings in native code (the player's input mappings and its rebinding screen aren't
-- reflected), so they can't be changed from a script. What is reflected is the step after them: each key
-- the game sees goes to its listeners (the player controller, and each screen that's open) as
-- OnKeyPressed(key), and each of the game's actions bound to that key goes to them as
-- OnListenCommand(command, event). So this script works there:
-- - when a listener hears a key that now stands for an action, the action's command is sent to it, the
--   same way the game sends its own (through the controller's input component, or to the screen);
-- - when one of the game's own commands arrives from the key its action moved away from, it's turned into
--   NoCommand, which every listener ignores.
-- Movement and the camera are axes, read by the game every frame rather than sent as commands, so they
-- can't be moved here; the key remapper outside the game (`wcmods play`) does those.
local PLAN = @PLAN@
-- PLAN.send: {key = {action, ...}}: pressing the key sends those actions' commands.
-- PLAN.drop: {action = {key, ...}}: the game's own command for the action is dropped when it comes from one
-- of these keys. PLAN.keys: {action = {key, ...}}: every key each moved action is on now, for other scripts.

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

local send, drop = {}, {}   -- key -> {command numbers}; command number -> {FKey}
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

local injecting = false
local held = {}   -- listener address .. key -> {listener, key, commands, how}

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
        local list = name and send[name]
        if not list then return end
        local listener = ctx:get()
        local from = fromParam and fromParam:get() or nil
        local id = tostring(listener:GetAddress()) .. name
        if event == PRESSED then
            held[id] = { listener = listener, key = name, how = how, from = from, controller = how == "controller" and listener or from }
        elseif not held[id] then
            return   -- a release whose press this listener didn't get (it was in another screen)
        else
            held[id] = nil
        end
        for _, command in ipairs(list) do
            debug("%s %s -> command %d (%s)", name, event == PRESSED and "pressed" or "released", command, how)
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
        local keys = drop[command]
        if not keys then return end
        local pc = how == "controller" and ctx:get() or (fromParam and fromParam:get())
        local event = eventParam:get()
        if fromKeys(pc, keys, event) then
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
                for _, command in ipairs(send[h.key] or {}) do deliver(h.listener, h.how, command, RELEASED, h.from) end
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
    for key, actions in pairs(PLAN.send) do
        send[key] = {}
        for _, action in ipairs(actions) do
            local n = byName[action]
            if n then send[key][#send[key] + 1] = n else log("the game has no action %s", action) end
        end
    end
    for action, keys in pairs(PLAN.drop) do
        local n = byName[action]
        if n then
            drop[n] = {}
            for i, k in ipairs(keys) do drop[n][i] = fkey(k) end
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
    log("remapping in game: %d keys", (function() local n = 0 for _ in pairs(send) do n = n + 1 end return n end)())
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
