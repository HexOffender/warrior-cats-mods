-- Written by wcmods from your mods' animations.json: your cat's emotes, on their keys and on the mod
-- menu's Emotes page. Do not edit; edit animations.json (or the Animations page in Clan Mod Studio) and
-- install again.
-- An emote plays on your cat over what it's doing (WCModsGame's Game.anims). Its key or button again
-- stops it, and so does walking off: the game's walk is under it, so a cat moving in an emote would slide.
local EMOTES = @EMOTES@   -- { { id = "my-mod/Wave", name = "Wave", key = "F6" or nil }, ... }
local MOVING = 40          -- cm a second: faster than this is walking
local GRACE = 0.5          -- seconds after an emote starts before walking stops it

local Game = require("WCModsGame")
local current, startedAt, status = nil, 0, nil

local function stop()
    if current then Game.anims.stop() end
    current = nil
end

local function toggle(e)
    if current == e.id and Game.anims.playing() == e.id then
        stop()
        return
    end
    local montage, why = Game.anims.play(nil, e.id)
    if not montage then
        status = e.name .. ": " .. tostring(why)
        Game.log("emote %s: %s", e.id, tostring(why))
        return
    end
    current, startedAt, status = e.id, os.clock(), nil
end

for _, e in ipairs(EMOTES) do
    if e.key then Game.onPress(e.key, function() toggle(e) end, "Emote: " .. e.name) end
end

-- Walking off stops an emote; one that ended by itself is forgotten.
Game.every(0.15, function()
    if not current then return end
    if Game.anims.playing() ~= current then
        current = nil
        return
    end
    if os.clock() - startedAt < GRACE then return end
    local cat = Game.player()
    if not cat then return end
    local ok, v = pcall(function() return cat:GetVelocity() end)
    if ok and v and v.X * v.X + v.Y * v.Y > MOVING * MOVING then stop() end
end)

-- The page is extra: if the menu can't load or add it, the keys still work.
local okMenu, Menu = pcall(require, "WCModsMenu")
if okMenu then pcall(function()
    Menu.page("Emotes", function(ui)
        ui.heading("Emotes")
        ui.note("Your cat plays one over what it's doing. Click it again, or walk off, to stop it.")
        for _, e in ipairs(EMOTES) do
            local label = e.name .. (e.key and ("   (" .. e.key .. ")") or "")
            if ui.button(label, { kind = current == e.id and "primary" or nil }) then toggle(e) end
        end
        if status then ui.note(status) end
    end, { group = "cat", order = 30, id = "wcmods-emotes" })
end) end
