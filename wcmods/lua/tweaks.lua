-- Tweaks for Warrior Cats: Clans of the Forest. Written by wcmods from the tweaks.json of your mods (the studio's
-- Tweaks page): change that and install again rather than editing this. No mod's own code runs here: the mods
-- hold the settings, and this, wcmods' own script, acts on them with WCModsGame, as Game Tweaks (the example script
-- in wcmods-examples) does. docs/formats.md, "tweaks.json", says what each one does.
local SETTINGS = @SETTINGS@
-- Where the page in the mod menu saves them: the top mod's tweaks.json, keeping its notes; nil for nowhere.
local SAVE = @SAVE@
local HEAL_KEYS = @HEAL_KEYS@
local NARRATIVE = "Gameplay.Narrative."   -- the story's scenes, by their tag (as Sandbox mode skips them)
local SKIP_HOLD = 2.5                     -- seconds the game's skip is held: long enough for its hold to fill

local okGame, Game = pcall(require, "WCModsGame")
if not okGame then
    print("[Tweaks] WCModsGame didn't load, so the tweaks are off: " .. tostring(Game) .. "\n")
    return
end
Game.modName = "Tweaks"   -- its errors in the log say so
local S = SETTINGS

-- Twice a second: stamina topped up, the clock held, the fresh-kill pile kept up.
Game.every(0.5, function()
    local cat = Game.cat()
    if not cat then return end   -- menus, loading
    if S.keep_stamina_full then
        local max = cat:maxStamina()
        if max then cat:setStamina(max) end
    end
    if S.hold_time then Game.time.setSeconds(math.floor(S.time_of_day * 3600 + 0.5)) end
    if S.min_fresh_kill > 0 then
        local pile = Game.freshKill.value()
        if pile and pile < S.min_fresh_kill then Game.freshKill.set(S.min_fresh_kill) end
    end
end)

-- The heal key, in the game's own input, read each frame: a key changed on the page works at once, it only
-- hears the key while the game has the focus, and it fires once a press.
local held = false
Game.onFrame(function()
    local key = S.heal_key
    if type(key) ~= "string" or key == "" then return end
    if held then
        if not Game.keyDown(key) then held = false end
        return
    end
    if not Game.pressed(key) then return end
    held = true
    local cat = Game.cat()
    if not cat then return end
    cat:heal()
    local max = cat:maxStamina()
    if max then cat:setStamina(max) end
end)

-- Whether Sandbox mode has a cat of its own in the forest: it skips that cat's scenes itself, with the same hold,
-- so the tweak leaves them to it (two holds on one skip haven't been tried). Sandbox mode says so through UE4SS's
-- shared variables, as its sandbox_api.lua reads them.
local function sandboxCat()
    local ok, v = pcall(function() return ModRef:GetSharedVariable("Sandbox.active") end)
    return ok and v == true
end

-- The story's scenes: while one plays and the game offers its skip, hold the skip (the game's own hold-to-skip,
-- as Sandbox mode does for its cats). Not offered yet: whether the skip keeps what a scene does at its end (a quest
-- step, a ceremony's rank) hasn't been checked on a story cat (tweaks.UNCHECKED), so only an install made for that
-- check turns it on.
local holding
Game.every(0.25, function()
    if not holding and (not S.skip_scenes or sandboxCat()) then return end
    local story
    pcall(function()
        local active = Game.get(Game.manager("sequencer"), "ActiveSequences")
        if active then
            active:ForEach(function(k)
                local tag = Game.tagName(k:get())
                if tag and tag:sub(1, #NARRATIVE) == NARRATIVE then story = tag end
            end)
        end
    end)
    local popup = Game.find("GuiPopupSkipQuest")
    local okShown, shown = pcall(function() return Game.valid(popup) and popup:IsVisible() end)
    shown = okShown and shown
    if holding then
        if not (story and shown) or os.clock() - holding.at >= SKIP_HOLD then
            if Game.valid(holding.popup) then Game.call(holding.popup, "OnListenCommand", holding.command, 1, Game.controller()) end
            holding = nil
        end
        return
    end
    if not (S.skip_scenes and story and shown) then return end
    local b = Game.get(popup, "mcGuiHoldButtonSkip")
    local command = Game.valid(b) and Game.get(b, "ButtonCommand")
    if not command then return end
    Game.log("skipping the story's %s", story)
    Game.call(popup, "OnListenCommand", command, 0, Game.controller())
    holding = { popup = popup, command = command, at = os.clock() }
end)

if S.heal_key ~= "" then pcall(function() require("WCModsMenu").key(S.heal_key, "Tweaks: heal your cat") end) end
Game.log("on: %s", (function()
    local on = {}
    if S.keep_stamina_full then on[#on + 1] = "stamina full" end
    if S.heal_key ~= "" then on[#on + 1] = "heal on " .. S.heal_key end
    if S.hold_time then on[#on + 1] = string.format("the clock held at %.1f", S.time_of_day) end
    if S.min_fresh_kill > 0 then on[#on + 1] = "fresh-kill pile at least " .. S.min_fresh_kill end
    if S.skip_scenes then on[#on + 1] = "the story's scenes skipped" end
    return #on > 0 and table.concat(on, ", ") or "none"
end)())

-- A page in the mod menu (Insert) to change them while you play; Save writes the top mod's tweaks.json, so
-- installing again keeps them. The page is extra: without the menu, the tweaks work as before.
local okMenu, Menu = pcall(require, "WCModsMenu")
if okMenu then pcall(function()
    local installed, status = {}, nil
    for k, v in pairs(SETTINGS) do installed[k] = v end
    local keyNames = { "none" }
    for _, k in ipairs(HEAL_KEYS) do keyNames[#keyNames + 1] = k end
    Menu.page("Tweaks", function(ui)
        ui.heading("Tweaks")
        ui.note("Changes apply as you make them." .. (SAVE and (" Save writes them to " .. SAVE.file ..
                ", so installing again keeps them.") or ""))
        S.keep_stamina_full = ui.switch("Keep my cat's stamina full", S.keep_stamina_full)
        local key = ui.choice("Heal my cat with a key", S.heal_key ~= "" and S.heal_key or "none", keyNames)
        S.heal_key = key == "none" and "" or key
        S.hold_time = ui.switch("Hold the clock", S.hold_time)
        S.time_of_day = ui.slider("At", S.time_of_day, 0, 24, { step = 0.25, format = "%.2f h" })
        S.min_fresh_kill = math.floor(ui.slider("Keep the fresh-kill pile at least", S.min_fresh_kill, 0, 100,
                                                { step = 1, format = "%.0f" }) + 0.5)
        -- (Only when the install turned it on: it isn't available yet, tweaks.UNCHECKED.)
        if installed.skip_scenes then S.skip_scenes = ui.switch("Skip the story's scenes", S.skip_scenes) end
        ui.space(6)
        local hit = ui.buttons(SAVE and { "Save", "Back to installed" } or { "Back to installed" }, { kinds = { "primary" } })
        if hit and SAVE and hit == 1 then
            local out = {}
            for k, v in pairs(SAVE.keep or {}) do out[k] = v end
            for k, v in pairs(S) do out[k] = v end
            out.time_of_day = out.time_of_day + 0.0   -- hours with a point, as the file has them
            local ok, err = Menu.saveJson(SAVE.path, out)
            status = ok and ("Saved to " .. SAVE.file .. ".") or ("Couldn't save: " .. tostring(err))
        elseif hit then
            for k, v in pairs(installed) do S[k] = v end
            status = "Back to the installed tweaks."
        end
        if status then ui.note(status) end
    end, { order = 20, group = "mods" })
end) end
