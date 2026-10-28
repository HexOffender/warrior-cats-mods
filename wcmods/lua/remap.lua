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
--
-- The game's pictures of keys (prompts such as Travel and Talk, the menus' Back and Confirm, the pause
-- screen's Controls tab) follow too: see "Key pictures" below.
local PLAN = @PLAN@
-- PLAN.play and PLAN.menu: what applies while you explore (the controller and the HUD) and in the game's
-- menus. In each, send = {key = {command, ...}}: pressing the key sends those commands;
-- drop = {command = {key, ...}}: the game's own command is dropped when it comes from one of these keys.
-- PLAN.keys: {action = {key, ...}}: every key each changed action is on now, for other scripts.
-- PLAN.icons.play and .menu: {command = {key, ...}}: the keys its pictures show now, the first that has one.
-- PLAN.menu_keys: {{key, what it does now}, ...}: the mod menu's Overview lists these beside its own keys.

local PRESSED, RELEASED = 0, 1   -- EInputEvent: IE_Pressed, IE_Released
-- The game's own enum numbers this script needs, read by name from the game in setup(); these are build
-- 26184573's, kept for when that read fails.
local NO_COMMAND = 0   -- ECommands::NoCommand
local UI_PC = 1        -- EGuiConsolesTypes::UI_PC: the PC's entry in the controller picture tables

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

-- The mod menu's Overview lists the keys that do something new ("F: Interact (was E)"), beside Insert and
-- F6, when the menu is there (the player may have none of it).
local okMenu, Menu = pcall(require, "WCModsMenu")
if okMenu and type(Menu) == "table" and Menu.key then
    for _, line in ipairs(PLAN.menu_keys or {}) do pcall(Menu.key, line[1], line[2]) end
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

-- One of the game's enums by name ("/Script/SwtEngine.ECommands" -> {Player_Interact = 67, ...}), or nil when
-- the game has no such enum. A smaller copy of WCModsGame's Game.enumNames, which this script runs without:
-- {name = number} only, <Enum>_MAX included, no order, and the setup's one pcall around it rather than one for
-- each name (it only looks up names it knows).
local function enumNames(path)
    local e = StaticFindObject(path)
    if not valid(e) then return nil end   -- asking a missing object anything crashes the game
    local byName = {}
    e:ForEachName(function(name, value)
        byName[(name:ToString():gsub("^.*::", ""))] = value
    end)
    return byName
end

-- Command numbers by name, from the game's ECommands enum (its numbers moved in patch 1.1, so they're
-- never written down here).
local function commands() return enumNames("/Script/SwtEngine.ECommands") end

-- Which set applies to a listener. While you explore, the keys go to the controller and the HUD's two
-- screens; with a menu open, only to the menu's screen; in a fight, to all of those and the fight's
-- menu, which counts as a menu. (The game draws its own cursor, so the engine's
-- cursor flag can't tell: it reads false in the pause menu and the map too.)
local PLAY_SCREENS = { WBP_GuiHudGameWrc_C = true, WBP_GuiScreenOnlineOver_C = true }
local function screenSet(screen)
    local ok, name = pcall(function() return screen:GetClass():GetFName():ToString() end)
    return (ok and PLAY_SCREENS[name]) and "play" or "menu"
end
local function where(how, listener)
    if how == "controller" then return "play" end
    return screenSet(listener)
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

-- Key pictures. Each picture of a key the game draws is a button widget holding a command:
-- GuiActionButtonControl (ActionCommand: the prompts, the Controls tab's keys) or GuiCommandButtonControl
-- (ButtonCommand: the menus' footers and tab keys). When the game sets one up (as it's made, when the
-- controller or keyboard takes over, and all the time for the HUD's prompts), native code finds the key
-- bound to the command and puts that key's picture on the widget's mcGuiButtonImage, from the GUI
-- manager's tables (DT_Keys for the keyboard and mouse, one per controller). Neither step can be changed,
-- but the widget reaches its image through that property: pointed at an image of the script's own, which
-- is never drawn, the game's picture goes there. The one on screen then shows what this script puts on it: the
-- picture of the command's new key from the table the game's came from, or the game's own when the
-- command didn't move or its new key has no picture there (a controller's picture while it moved on the
-- keyboard, say).
local icons = { play = {}, menu = {} }   -- command number -> {key, ...}
local pictures                           -- {kinds = {kind = {key = {image, hud}}}, of = {texture = {kind, ...}}}
local found, buttons, taken = {}, {}, {} -- widgets made since the last look; those followed; those swapped
local imageClass, userWidgetClass, screenClass, controlsClass

local function softPath(ptr)
    local ok, p = pcall(function() return ptr:GetObjectID():GetAssetPathName():ToString() end)
    if ok and p ~= "" and p ~= "None" then return p end
end

-- Every picture in the game's tables, by kind ("keyboard", or the controller's table) and key, and the
-- kinds each texture is in. The keyboard's are DT_Keys and the "PC" controller table.
local function readPictures(gm)
    local kinds, of = {}, {}
    local function read(kind, dt)
        local byKey = kinds[kind] or {}
        kinds[kind] = byKey
        dt:ForEachRow(function(_, row)
            local key = row.Key.KeyName:ToString()
            local image, hud = softPath(row.Image), softPath(row.HudImage)
            if key ~= "None" and image and not byKey[key] then byKey[key] = { image = image, hud = hud or image } end
            for _, p in ipairs({ image, hud }) do
                local name = p and p:match("[^%.]+$")
                if name then
                    of[name] = of[name] or {}
                    local seen = false
                    for _, k in ipairs(of[name]) do seen = seen or k == kind end
                    if not seen then of[name][#of[name] + 1] = kind end
                end
            end
        end)
    end
    read("keyboard", gm.DataKeysMap)
    gm.GamepadButtonsMap.DataGamepadButtonsMap:ForEach(function(console, dt)
        dt = dt:get()
        read(console:get() == UI_PC and "keyboard" or dt:GetFName():ToString(), dt)
    end)
    return { kinds = kinds, of = of }
end

-- Found again each time rather than kept: a texture nothing shows can be freed, and a kept handle to it
-- could then point at another object.
local function texture(path)
    local t = StaticFindObject(path)
    if not valid(t) then pcall(function() t = LoadAsset(path) end) end
    return t
end

-- The screen a widget is on (the first one up its outers, which hears the keys), and the game instance
-- past it.
local function screenOf(w)
    local cur, screen = w, nil
    for _ = 1, 40 do
        local ok, outer = pcall(function() return cur:GetOuter() end)
        if not (ok and valid(outer)) then return screen, nil end
        if not screen and outer:IsA(screenClass) then screen = outer end
        if outer:GetClass():GetFName():ToString() ~= "WidgetTree" and not outer:IsA(userWidgetClass) then
            return screen, outer
        end
        cur = outer
    end
    return screen, nil
end

local function command(b)
    if b.action then return b.w.ActionCommand end
    return b.w.ButtonCommand
end

-- Point the widget at an image of the script's own, so the game's picture lands there.
local function take(b)
    local real = b.w.mcGuiButtonImage
    if not valid(real) then return false end
    if not pictures then
        local _, beyond = screenOf(b.w)
        local gm
        pcall(function() gm = beyond.GuiManager end)
        if not valid(gm) then pcall(function() gm = FindFirstOf("BP_WrcGameInstance_C").GuiManager end) end
        if not valid(gm) then return false end
        local ok, read = pcall(readPictures, gm)
        if not ok then
            log("can't read the game's key pictures, so they show its own keys: %s", tostring(read))
            icons = { play = {}, menu = {} }
            return false
        end
        pictures = read
    end
    local decoy = StaticConstructObject(imageClass, b.w)
    pcall(function() decoy:SetBrushResourceObject(real.Brush.ResourceObject) end)
    b.w.mcGuiButtonImage = decoy
    b.real, b.decoy, b.hud = real, decoy, b.w.bUseHudButtonImage
    pcall(function() b.set = real.Brush.ResourceObject:GetFName():ToString() end)
    taken[#taken + 1] = b
    debug("key picture for command %d (%s) on %s", command(b), b.where, b.w:GetFullName())
    return true
end

-- What the game chose, or the new key's picture in the same table.
local function show(b)
    local now = b.real.Brush.ResourceObject
    local nowName = valid(now) and now:GetFName():ToString() or nil
    -- A picture the game was still loading when the image was swapped lands on the image it was asked
    -- for, the one on screen (the first pause screen's Back kept the widget's default otherwise): a key's
    -- picture there that this script didn't put is the game's choice.
    if nowName and nowName ~= b.set and pictures.of[nowName] then
        b.decoy:SetBrushResourceObject(now)
        b.set = nowName
    end
    local tex = b.decoy.Brush.ResourceObject
    if not valid(tex) then return end
    local name = tex:GetFName():ToString()
    local path
    local keys = icons[b.where][command(b)]
    local kinds = keys and pictures.of[name]
    if kinds then
        for _, key in ipairs(keys) do
            for _, kind in ipairs(kinds) do
                local p = pictures.kinds[kind][key]
                if p then path = b.hud and p.hud or p.image break end
            end
            if path then break end
        end
    end
    -- Checked against the image itself: the widgets' animations reach it by its name, not the property,
    -- and one blanked a prompt that showed again without its picture.
    local want = path and path:match("[^%.]+$") or name
    if nowName == want then b.set = want return end
    local t = path and texture(path) or tex
    if valid(t) then
        debug("key picture %s for command %d (the game's %s)", want, command(b), name)
        b.real:SetBrushFromTexture(t, false)
        b.set = want
    end
end

local function followNew()
    local new = found
    found = {}
    for _, f in ipairs(new) do
        local w, action = f[1], f[2]
        local ok, name = pcall(function() return w:GetFullName() end)
        -- The game's own templates live in its packages; the ones on screen in the transient package.
        if ok and name:find(" /Engine/Transient%.") then buttons[#buttons + 1] = { w = w, action = action } end
    end
end

local function lookAtButtons()
    followNew()
    local keep = {}
    for _, b in ipairs(buttons) do
        if valid(b.w) then
            local c = command(b)
            if c ~= NO_COMMAND and (icons.play[c] or icons.menu[c]) then
                -- The Controls tab shows what keys do while you play, on a menu; prompts outside any screen
                -- are play's too.
                if not b.where then
                    local screen = not b.w:IsA(controlsClass) and screenOf(b.w)
                    b.where = screen and screenSet(screen) or "play"
                end
                if not (icons[b.where][c] and take(b)) then keep[#keep + 1] = b end
            else
                keep[#keep + 1] = b
            end
        end
    end
    buttons = keep
end

local function showPictures()
    local keep = {}
    for _, b in ipairs(taken) do
        if valid(b.w) and valid(b.real) and valid(b.decoy) then
            keep[#keep + 1] = b
            local ok, err = pcall(show, b)
            if not ok then report("showing a key picture", err) end
        end
    end
    taken = keep
end

if next(PLAN.icons.play) or next(PLAN.icons.menu) then
    for _, h in ipairs({ { "/Script/SwtEngine.GuiActionButtonControl", true },
                         { "/Script/SwtEngine.GuiCommandButtonControl", false } }) do
        local ok, err = pcall(NotifyOnNewObject, h[1], function(w) found[#found + 1] = { w, h[2] } end)
        if not ok then log("can't follow %s: %s", h[1], tostring(err)) end
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
    if byName.NoCommand then
        NO_COMMAND = byName.NoCommand
    else
        log("the game has no command NoCommand; using %d", NO_COMMAND)
    end
    local okConsoles, consoles = pcall(enumNames, "/Script/SwtEngine.EGuiConsolesTypes")
    if okConsoles and consoles and consoles.UI_PC then
        UI_PC = consoles.UI_PC
    else
        log("can't read UI_PC from the game's EGuiConsolesTypes; using %d, build 26184573's", UI_PC)
    end
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
    imageClass = StaticFindObject("/Script/UMG.Image")
    userWidgetClass = StaticFindObject("/Script/UMG.UserWidget")
    screenClass = StaticFindObject("/Script/SwtEngine.SwtScreen")
    controlsClass = StaticFindObject("/Script/Wrc.GuiConfigButtonControl")
    if valid(imageClass) and valid(userWidgetClass) and valid(screenClass) and valid(controlsClass) then
        for _, set in ipairs({ "play", "menu" }) do
            for name, keys in pairs(PLAN.icons[set]) do
                if byName[name] then icons[set][byName[name]] = keys end
            end
        end
    else
        log("can't find the classes to show key pictures with")
    end
    log("remapping in game: %d keys in play and menus", nkeys)
    return true
end

-- Everything runs on the game thread, where the hooks do (two threads in one Lua state crash the game).
-- The game's classes are there once it has started, so the hooks go in on the first tick that finds them.
-- Key pictures are kept up every frame, the rest every sixth.
local ready, failed = false, false
local every, frame = 6, 0
local function tick()
    if not ready and not failed then
        local ok, done = pcall(setup)
        if not ok then report("setup", done) end
        ready, failed = ok and done, not ok
    end
    frame = frame + 1
    if frame % every == 0 then
        if next(held) then
            local ok, err = pcall(releaseLost)
            if not ok then report("letting go of keys", err) end
        end
        if ready and (next(found) or next(buttons)) then
            local ok, err = pcall(lookAtButtons)
            if not ok then report("looking at key pictures", err) end
        end
    end
    if next(taken) then showPictures() end
end
if LoopInGameThreadAfterFrames == nil or not pcall(LoopInGameThreadAfterFrames, 1, tick) then
    every = 1
    LoopAsync(100, function()
        ExecuteInGameThread(tick)
        return false
    end)
end
