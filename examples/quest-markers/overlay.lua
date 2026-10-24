-- Quest Markers (examples/quest-markers): a custom quest on screen, markers on nearby pickups and a
-- debug panel, drawn with the shared modules wcmods installs (docs/SDK.md, "Overlays"). Written from
-- quest.json by the mod's section.py: change that and install again rather than editing this.
local Draw = require("WCModsDraw")
local World = require("WCModsWorld")
local SETTINGS = @SETTINGS@

local function log(fmt, ...) print(string.format("[QuestMarkers] " .. fmt .. "\n", ...)) end

local steps = SETTINGS.steps
local step, added = 1, 0
local function place(s) return { X = s.at[1], Y = s.at[2], Z = s.at[3] } end

-- Nearby pickups, looked up twice a second rather than every frame.
local pickups, pickupsAt = {}, nil
local function nearbyPickups()
    if pickupsAt == nil or os.clock() - pickupsAt >= 0.5 then
        pickupsAt = os.clock()
        pickups = World.nearby("pickups", SETTINGS.pickup_range)
    end
    return pickups
end

Draw.onFrame(function(d)
    local me = World.player()
    if not me or not d.view then return end
    local here = World.location(me)

    -- The quest: a panel at the top right, and a marker on the current step's place.
    local x, w = d.width - 380, 360
    local y = d.panel(x, 20, w, 84, SETTINGS.title)
    local s = steps[step]
    if s then
        local target = place(s)
        local away = World.distance(here, target)
        d.text(x + 12, y, string.format("%d/%d  %s", step, #steps, s.text), { size = 15, color = "#ffe9a8" })
        d.text(x + 12, y + 22, string.format("%d m away", math.floor(away / 100 + 0.5)), { size = 13, color = "#ffffffb0" })
        d.marker(target, s.text, { edge = true, color = "#ffd166" })
        if away <= (s.radius or 400) then
            log("step %d done: %s", step, s.text)
            step = step + 1
        end
    elseif #steps > 0 then
        d.text(x + 12, y, "Quest complete!", { size = 15, color = "#9ef0a0" })
    else
        d.text(x + 12, y, "No steps yet: press " .. SETTINGS.waypoint_key .. " to add one here.", { size = 13, color = "#ffffffc0" })
    end

    if SETTINGS.pickups then
        for i, it in ipairs(nearbyPickups()) do
            if i > 12 then break end
            if it.actor:IsValid() then d.marker(it.location, it.label, { color = "#8fd3ff", size = 9, textSize = 13 }) end
        end
    end

    if SETTINGS.debug_panel then
        local r = d.view.rotation
        local py = d.panel(20, 20, 320, 116, "Debug")
        d.text(32, py, string.format("You: %.0f, %.0f, %.0f", here.X, here.Y, here.Z), { size = 13 })
        d.text(32, py + 20, string.format("Camera: pitch %.0f, yaw %.0f, fov %.0f", r.Pitch, r.Yaw, d.view.fov), { size = 13 })
        d.text(32, py + 40, string.format("Pickups within %.0f m: %d", SETTINGS.pickup_range / 100, #pickups), { size = 13 })
        d.text(32, py + 60, string.format("Viewport %.0f x %.0f, UI scale %.2f", d.width, d.height, d.scale), { size = 13 })
    end
end)

if SETTINGS.toggle_key ~= "" and Key[SETTINGS.toggle_key] then
    RegisterKeyBind(Key[SETTINGS.toggle_key], function() Draw.setVisible(not Draw.isVisible()) end)
end
if SETTINGS.waypoint_key ~= "" and Key[SETTINGS.waypoint_key] then
    RegisterKeyBind(Key[SETTINGS.waypoint_key], function()
        ExecuteInGameThread(function()
            local me = World.player()
            if not me then return end
            local l = World.location(me)
            added = added + 1
            local s = { text = "Waypoint " .. added, at = { math.floor(l.X), math.floor(l.Y), math.floor(l.Z) }, radius = 400 }
            steps[#steps + 1] = s
            log('step for quest.json: { "text": "%s", "at": [%d, %d, %d], "radius": 400 }', s.text, s.at[1], s.at[2], s.at[3])
        end)
    end)
end
-- A page in the mod menu (Insert): the quest's steps, moving between them, the markers, and Save,
-- which writes the steps (with any added with the waypoint key) back to quest.json.
local SAVE = @SAVE@
local okMenu, Menu = pcall(require, "WCModsMenu")
if okMenu then
    if SETTINGS.toggle_key ~= "" then Menu.key(SETTINGS.toggle_key, "Quest markers: show and hide") end
    if SETTINGS.waypoint_key ~= "" then Menu.key(SETTINGS.waypoint_key, "Quest markers: add a step where your cat stands") end
    local status
    Menu.page("Quest markers", function(ui)
        ui.heading(SETTINGS.title)
        if #steps == 0 then ui.note("No steps yet. Press " .. SETTINGS.waypoint_key .. " in the world to add one where your cat stands.") end
        for i, s in ipairs(steps) do
            local state = i < step and "done" or (i == step and "now" or "")
            ui.field(string.format("%d. %s", i, s.text), string.format("%s  (%d, %d, %d)", state, s.at[1], s.at[2], s.at[3]))
        end
        if #steps > 0 then ui.progress("Progress", (step - 1) / #steps, { format = string.format("%d of %d", math.min(step - 1, #steps), #steps) }) end
        local hit = ui.buttons({ "Back a step", "Skip this step", "Start again" })
        if hit == 1 then step = math.max(1, step - 1)
        elseif hit == 2 then step = math.min(#steps + 1, step + 1)
        elseif hit == 3 then step = 1 end
        ui.separator()
        SETTINGS.pickups = ui.switch("Markers on pickups", SETTINGS.pickups)
        SETTINGS.pickup_range = ui.slider("Pickups within", SETTINGS.pickup_range, 500, 20000, { step = 500, format = "%.0f cm" })
        SETTINGS.debug_panel = ui.switch("Debug panel", SETTINGS.debug_panel)
        SETTINGS.title = ui.input("Quest title", SETTINGS.title)
        if SAVE and ui.button("Save to quest.json", { kind = "primary" }) then
            local doc = SAVE.doc or {}
            for _, k in ipairs({ "title", "pickups", "pickup_range", "debug_panel" }) do doc[k] = SETTINGS[k] end
            doc.steps = Menu.list(steps)
            local ok, err = Menu.saveJson(SAVE.path, doc)
            status = ok and ("Saved to " .. SAVE.file .. "; install again to ship it.") or ("Couldn't save: " .. tostring(err))
        end
        if status then ui.note(status) end
    end, { order = 30, group = "story" })
end

log("loaded: %s, %d step(s)", SETTINGS.title, #steps)
