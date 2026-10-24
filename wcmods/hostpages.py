"""The mod menu's pages built on WCModsGame: the overview, your cat, the world, travel, items, quests, the
fight, the game's developer switches, the log and the menu's own settings, and (with code mods allowed)
an inspector and a Lua console.

They're part of the menu host's script (menu.host_script puts them in), so they use its locals: Menu,
SETTINGS, THEME, valid, log, HOST (the status line), everySecond (work done once a second), size, fit,
win and setPaused. Each page is in a function of its own, which keeps the host's main chunk under Lua's
200-local limit. data() is what the build hands them from the game's tables: area names and quest titles.
"""
import os

# Items the Items page can drop by your cat: every consumable and material in the game's tables.
ITEMS = (
    "Consumable.SmallHealingHerb", "Consumable.MediumHealingHerb", "Consumable.BigHealingHerb",
    "Consumable.FullHealingHerb", "Consumable.SuperHealingHerb", "Consumable.HealingHerbPouch",
    "Consumable.SmallCatnip", "Consumable.MediumCatnip", "Consumable.BigCatnip", "Consumable.CatnipPouch",
    "Consumable.ThistlePouch", "Consumable.FishScalePouch", "Consumable.CatThymePouch", "Consumable.FeatherPouch",
    "Consumable.HerbSpicesPouch", "Consumable.EyewortPouch", "Consumable.ChamomilePouch",
    "Consumable.AntidoteHerbPouch", "Consumable.ValerianRootPouch", "Consumable.PeppermintPouch",
    "Consumable.GingerRootPouch", "Consumable.ChestnutPouch", "Consumable.LavenderPouch", "Consumable.TurmericPouch",
    "Consumable.SagePouch",
    "Materials.BerryFern", "Materials.Birdnest", "Materials.Bone", "Materials.Borage", "Materials.Broom",
    "Materials.Burdock", "Materials.CattailReed", "Materials.Cobwebs", "Materials.Comfrey", "Materials.Cotton",
    "Materials.Dandelion", "Materials.DirtMound", "Materials.Fur", "Materials.Goldenrod", "Materials.Heather",
    "Materials.Ivy", "Materials.Juniper", "Materials.Leaves", "Materials.Moss", "Materials.Oakgall", "Materials.Pine",
    "Materials.Poppy", "Materials.Rock", "Materials.Rope", "Materials.SharpeningTreeBark", "Materials.Thyme",
    "Materials.Willow",
)


def data(read_text=None, cfg=None):
    """What the pages need from the game and the install: area names by code ("R-05" -> "Willow-Weep"),
    quest titles by tag and rank, and where the UE4SS log and the saved travel spots are. Without the
    game's files (no Oodle DLL) the names are left out, and the pages show codes and tags instead."""
    from . import csvdata
    out = {"areas": {}, "quests": {}, "items": list(ITEMS), "log": "", "places": ""}
    if cfg is not None:
        try:
            out["log"] = os.path.join(cfg.win64_dir, "ue4ss", "UE4SS.log")
        except Exception:   # no game found
            pass
        out["places"] = os.path.join(os.path.dirname(os.path.normpath(cfg.save_dir)), "WCMods", "places.json")
    if read_text is None:
        return out
    try:
        strings = csvdata.Table(read_text("Wrc/Content/Gameplay/Strings/NonAsset/Strings_EN.csv"))
        en = {r.fields[0]: r.fields[1] for r in strings.rows if len(r.fields) > 1}
        base = "Wrc/Content/Gameplay/DataTables/NonAsset/"
        locations = csvdata.Table(read_text(base + "LocationsData.csv"))
        code, name = locations.column("Code"), locations.column("IdStrName")
        for r in locations.rows:
            if len(r.fields) > max(code, name):
                out["areas"][r.fields[code]] = en.get(r.fields[name], r.fields[code])
        dialogues = csvdata.Table(read_text(base + "QuestDialogues.csv"))
        key = dialogues.column("StringKey")
        for r in dialogues.rows:
            tag = r.fields[0] if r.fields else ""
            if tag.endswith(".Title") and len(r.fields) > key:
                quest, _, rank = tag[:-len(".Title")].rpartition(".")
                out["quests"].setdefault(quest, {})[rank] = en.get(r.fields[key], r.fields[key])
    except Exception:   # a table that can't be read leaves those names out
        pass
    return out


LUA = r'''
-- ---------- pages built on WCModsGame ----------
local okGame, Game = pcall(require, "WCModsGame")
if not okGame then
    log("WCModsGame didn't load, so the pages about the game are left out: %s", tostring(Game))
    Game = nil
end

;(function()
    if not Game then return end
    local DATA = @DATA@

    -- ---------- helpers ----------
    local INTEGER = { IntProperty = true, Int8Property = true, Int16Property = true, Int64Property = true, UInt16Property = true,
                      UInt32Property = true, UInt64Property = true, ByteProperty = true, EnumProperty = true }
    -- A number for a property of this type: whole for integers, bytes and enums.
    local function asType(v, t) return INTEGER[t] and math.floor(v + 0.5) or v end
    local function changed(a, b) return a ~= nil and b ~= nil and math.abs(a - b) > 1e-4 end
    local function words(s) return (tostring(s):gsub("_", " "):gsub("(%l)(%u)", "%1 %2"):gsub("(%u)(%u%l)", "%1 %2")) end
    -- "Gameplay.Inventory.Consumable.SmallHealingHerb" -> "Small Healing Herb"
    local function itemName(tag) return words(tostring(tag):match("([^%.]+)$") or tag) end
    local function rankOf(level)
        if not level then return nil end
        if level <= 6 then return "Apprentice" elseif level <= 11 then return "Warrior" elseif level <= 15 then return "Deputy" end
        return "Leader"
    end
    local TERRITORY = { "ThunderClan", "ShadowClan", "RiverClan", "WindClan", "Moonpool", "the Island" }   -- ELocationsType 1-6
    local function areaName(code) return code and code ~= "" and (DATA.areas[code] or code) or nil end

    -- Where your cat is: the territory the game puts it in, and the last area whose name the game showed
    -- (the area gates tell the game when the cat crosses into one).
    local lastArea = nil
    Game.hook("/Script/Wrc.WrcZoneNameTrigger:OnOverlapBegin", function(self, _, other)
        local p = Game.player()
        if p and valid(other) and other:GetAddress() == p:GetAddress() then lastArea = Game.str(self.ZoneCode) end
    end)
    local function territory()
        local lib, loc, px = Game.library("AdventureGameState"), {}, {}
        local ok, found = pcall(function() return lib:GetCharacterLocationType(Game.player(), loc, px) end)
        if ok and found then return TERRITORY[loc.Location] end
        return nil
    end

    -- The cat and the world, read twice a second for the pages and the status line.
    local snap = { at = -1 }
    local function now()
        if os.clock() - snap.at < 0.5 then return snap end
        local s = { at = os.clock() }
        local cat = Game.cat()
        s.cat = cat
        if cat then
            s.name, s.clan, s.level = cat:name(), cat:clan(), cat:level()
            s.rank = rankOf(s.level)
            s.hp, s.maxhp, s.st, s.maxst = cat:health(), cat:maxHealth(), cat:stamina(), cat:maxStamina()
            s.xp, s.xpNeeded = cat:xp(), cat:xpNeeded()
            s.territory, s.area = territory(), areaName(lastArea)
        end
        s.h, s.m = Game.time.get()
        s.secs = Game.time.seconds()
        s.fk, s.fkLevel = Game.freshKill.value(), Game.freshKill.level()
        s.fight = Game.fight()
        snap = s
        return s
    end
    local function refresh() snap.at = -1 end

    HOST.status = function()
        local s = now()
        if not s.cat then return "Not in the world yet.   " .. SETTINGS.opens .. " opens and closes this menu." end
        local parts = { string.format("%s, level %s %s", s.name or "Your cat", tostring(s.level or "?"), s.rank or "") }
        if s.hp then parts[#parts + 1] = string.format("health %.0f/%.0f", s.hp, s.maxhp or s.hp) end
        if s.st then parts[#parts + 1] = string.format("stamina %.0f", s.st) end
        if s.territory then parts[#parts + 1] = s.territory .. (s.area and (", " .. s.area) or "") end
        if s.h then parts[#parts + 1] = string.format("%02d:%02d", s.h, s.m or 0) end
        if s.fk then parts[#parts + 1] = string.format("fresh-kill %.0f (%s)", s.fk, s.fkLevel or "?") end
        if s.fight then parts[#parts + 1] = "IN A FIGHT" end
        return table.concat(parts, "   |   ")
    end

    -- Held values: the World page can hold the time of day and keep the fresh-kill pile up, even with the
    -- menu closed.
    local hold = { time = false, timeAt = 12 * 3600, pile = false, pileAt = 100 }
    everySecond[#everySecond + 1] = function()
        if hold.time then Game.time.setSeconds(hold.timeAt) end
        if hold.pile then
            local v = Game.freshKill.value()
            if v and v < hold.pileAt then Game.freshKill.set(hold.pileAt) end
        end
    end

    -- Travel: jump to a place (onto the ground below it), and back again.
    local travel = { back = nil, note = nil }
    local function ground(x, y, z)
        local ks, hit = Game.library("KismetSystemLibrary"), {}
        local none = { R = 0, G = 0, B = 0, A = 0 }
        local ok, found = pcall(function()
            return ks:LineTraceSingle(Game.player(), { X = x, Y = y, Z = z + 200 }, { X = x, Y = y, Z = z - 20000 }, 0, false, {}, 0,
                                      hit, true, none, none, 0)
        end)
        if ok and found and hit.ImpactPoint then return hit.ImpactPoint.Z end
        return nil
    end
    local function jump(to, label, onGround)
        local cat = Game.cat()
        if not (cat and to) then return false end
        travel.back = cat:location()
        local z = to.Z
        if not onGround then z = ground(to.X, to.Y, to.Z) or to.Z end
        local ok = cat:teleport(to.X, to.Y, z + 60)
        travel.note = (ok and "Went to " or "Couldn't go to ") .. label
        refresh()
        return ok
    end

    -- Quests: titles from the game's quest text (for your cat's rank), and each quest's objectives.
    local function questTitle(q)
        local titles = q.tag and DATA.quests[q.tag]
        if titles then
            return titles[now().rank or ""] or titles.Apprentice or titles.Warrior or titles.Deputy or titles.Leader or select(2, next(titles))
        end
        return words(q.id or "?")
    end
    local STATUS_TEXT = { None = "not started", QuestAvailable = "available", OngoingQuest = "in progress",
                          QuestComplete = "ready to hand in", QuestTurnedIn = "done", DialogueProgress = "talking" }
    local questCache = { at = -1, list = {} }
    local function quests()
        if os.clock() - questCache.at > 1 then questCache = { at = os.clock(), list = Game.quests.all() } end
        return questCache.list
    end

    -- ---------- Home: Overview ----------
    Menu.page("Overview", function(ui)
        ui.heading("Overview")
        local s = now()
        if not s.cat then
            ui.text("Not in the world yet. The pages about your cat and the world fill in once you're playing.")
        else
            ui.columns({ { "Cat", s.name or "?" }, { "Clan", s.clan or "?" }, { "Level", s.level }, { "Rank", s.rank or "?" } })
            if s.hp and s.maxhp and s.maxhp > 0 then
                ui.progress("Health", s.hp / s.maxhp, { color = "#e06c6c", format = string.format("%.0f / %.0f", s.hp, s.maxhp) })
            end
            if s.st and s.maxst and s.maxst > 0 then
                ui.progress("Stamina", s.st / s.maxst, { color = "#6cc58a", format = string.format("%.0f / %.0f", s.st, s.maxst) })
            end
            if s.xpNeeded and s.xpNeeded > 0 then
                ui.progress("Experience", (s.xp or 0) / s.xpNeeded, { format = string.format("%.0f / %.0f", s.xp or 0, s.xpNeeded) })
            else
                ui.field("Experience", s.level == 20 and "top level" or tostring(s.xp or "?"))
            end
            ui.columns({ { "Territory", s.territory or "?" }, { "Area", s.area or "(shows once you cross into one)" },
                         { "Time", s.h and string.format("%02d:%02d", s.h, s.m or 0) or "?" },
                         { "Fresh-kill pile", s.fk and string.format("%.0f, %s", s.fk, s.fkLevel or "?") or "?" } })
            local tracked = Game.quests.tracked()
            local followed = nil
            if tracked then followed = questTitle(Game.quests.describe(tracked)) end
            ui.field("Following", followed or "no quest")
            if s.fight then ui.text("You're in a fight. The Fight page has both sides.", { color = THEME.heading }) end
            local hit = ui.buttons({ "Heal", "Full stamina", "Morning", "Evening" }, { kinds = { "good" } })
            if hit == 1 then s.cat:heal()
            elseif hit == 2 and s.maxst then s.cat:setStamina(s.maxst)
            elseif hit == 3 then Game.time.set(7, 0)
            elseif hit == 4 then Game.time.set(19, 0) end
            if hit then refresh() end
        end
        ui.section("Keys", function()
            ui.field(SETTINGS.key_name, "Open and close this menu")
            ui.field("Escape", "Close this menu")
            if SETTINGS.pad ~= "" then ui.field(SETTINGS.pad_name .. " on a controller", "Open and close this menu; B closes it too") end
            for line in (Menu.shared("keys") or ""):gmatch("[^\n]+") do
                local k, what = line:match("^([^\t]*)\t(.*)$")
                if k then ui.field(k, what) end
            end
        end, { id = "overview-keys", open = true })
        ui.section("What's where", function()
            ui.field("Your cat", "Stats: health, stamina, level and stats. Colours and Mouse look, when those mods are on.")
            ui.field("World", "The time of day and the fresh-kill pile; Travel; what's Nearby; your Items.")
            ui.field("Story", "Quests: the one you follow, its objectives, and every quest's state.")
            ui.field("Fight", "Both sides of a fight while you're in one.")
            ui.field("Cheats", "The engine's cheats, and the game's own developer switches.")
            ui.field("Mods", "Pages from the mods you have on.")
            ui.field("Tools", "The log, this menu's settings" .. (SETTINGS.dev and ", the Inspector and the Console." or "."))
        end, { id = "overview-where", open = false })
    end, { order = 0, group = "home" })

    -- ---------- Your cat: Stats ----------
    Menu.page("Stats", function(ui)
        ui.heading("Your cat")
        local s = now()
        local cat = s.cat
        if not cat then
            ui.text("Not in the world yet.")
            return
        end
        ui.note("Live values. A change applies at once and lasts until the game changes it again (a level-up, a fight, " ..
                "loading); the game saves what it holds at its next save.")
        ui.columns({ { "Name", s.name or "?" }, { "Clan", s.clan or "?" }, { "Rank", s.rank or "?" },
                     { "Traits", table.concat(cat:traits(), ", ") } })
        if s.hp and s.maxhp then
            local hp = ui.slider("Health", s.hp, 0, s.maxhp, { step = 1, format = "%.0f", color = "#e06c6c" })
            if changed(hp, s.hp) then cat:setHealth(hp) refresh() end
        end
        if s.st and s.maxst then
            local st = ui.slider("Stamina", s.st, 0, s.maxst, { step = 1, format = "%.0f", color = "#6cc58a" })
            if changed(st, s.st) then cat:setStamina(st) refresh() end
        end
        local regen = cat:staminaRegen()
        if regen then
            local r = ui.number("Stamina back per second", regen, { min = 0, max = 500, step = 1 })
            if changed(r, regen) then cat:setStaminaRegen(r) end
        end
        ui.field("Fight stamina", string.format("%s (0.4 x Prowess + Stamina)", tostring(cat:maxCombatStamina())))
        local scale = cat:scale()
        if scale then
            local size = ui.slider("Size", scale, 0.25, 4, { step = 0.05, format = "x%.2f" })
            if changed(size, scale) then cat:setScale(size) end
        end
        ui.section("Level and experience", function()
            local lv = ui.number("Level", s.level or 1, { min = 1, max = 20, step = 1, whole = true })
            if changed(lv, s.level) then cat:setLevel(math.floor(lv + 0.5)) refresh() end
            if s.xpNeeded and s.xpNeeded > 0 then
                local xp = ui.number("Experience", s.xp or 0, { min = 0, max = s.xpNeeded, step = 10, whole = true })
                if changed(xp, s.xp) then cat:setXp(xp) refresh() end
                ui.field("Needed for the next level", string.format("%.0f", s.xpNeeded))
            end
        end, { id = "stats-level", open = true })
        ui.section("Stats", function()
            ui.note("Kept with the level; a level-up works them out again from the growth tables " ..
                    "(docs/mechanics/progression.md). Prowess is health.")
            local stats = cat:stats() or {}
            for _, name in ipairs(Game.statNames) do
                local v = stats[name]
                if v then
                    local nv = ui.number(name, v, { min = 0, max = 2000, step = 1, whole = true })
                    if changed(nv, v) then cat:setStat(name, nv) end
                end
            end
        end, { id = "stats-stats", open = true })
        ui.section("Looks", function()
            local look = cat:customization() or {}
            ui.columns({ { "Body", look.BodyValue }, { "Ears", look.EarIdx }, { "Face", look.FaceValue }, { "Tail", look.TailIdx } })
            ui.columns({ { "Coat colour", look.FurColorIdx }, { "Pattern", look.PatternIdx }, { "Markings", look.MarkingIdx },
                         { "Eyes", tostring(look.EyeLeftColorIdx) .. " / " .. tostring(look.EyeRightColorIdx) } })
            ui.note("Your cat's colours have a page of their own when the colours mod is on (Colours).")
        end, { id = "stats-looks", open = false })
    end, { order = 10, group = "cat" })

    -- ---------- World: time and the fresh-kill pile ----------
    Menu.page("World", function(ui)
        ui.heading("The world")
        local s = now()
        if not s.secs then
            ui.text("Not in the world yet.")
            return
        end
        ui.columns({ { "Territory", s.territory or "?" }, { "Area", s.area or "(shows once you cross into one)" },
                     { "Time", string.format("%02d:%02d", s.h or 0, s.m or 0) }, { "Level", Game.levelName() or "?" } })
        ui.section("Time of day", function()
            local hours = ui.slider("Clock", s.secs / 3600, 0, 23.99, { step = 0.25, format = "%.2f h" })
            if math.abs(hours - s.secs / 3600) > 0.2 then
                Game.time.setSeconds(hours * 3600)
                hold.timeAt = hours * 3600
                refresh()
            end
            local hit = ui.buttons({ "Dawn 6:00", "Noon", "Dusk 19:00", "Night 23:00" })
            local at = ({ 6, 12, 19, 23 })[hit or 0]
            if at then
                Game.time.set(at, 0)
                hold.timeAt = at * 3600
                refresh()
            end
            local holding = ui.switch("Hold this time", hold.time)
            if holding and not hold.time then hold.timeAt = s.secs end
            hold.time = holding
            ui.note("A game day passes in about 20 minutes (DayNight.ClockSpeed 72).")
        end, { id = "world-time", open = true })
        ui.section("Fresh-kill pile", function()
            if not s.fk then
                ui.text("No fresh-kill pile here.")
                return
            end
            local fk = ui.slider("Pile", s.fk, 0, 100, { step = 1, format = "%.0f" })
            if changed(fk, s.fk) then
                Game.freshKill.set(fk)
                hold.pileAt = fk
                refresh()
            end
            ui.field("The pile is", s.fkLevel or "?")
            local t, every = Game.freshKill.timer(), Game.freshKill.decayTime()
            if t and every then ui.field("Goes down by 1", string.format("in %.0f s (every %.0f s)", math.max(0, every - t), every)) end
            local holding = ui.switch("Keep it at least here", hold.pile)
            if holding and not hold.pile then hold.pileAt = s.fk end
            hold.pile = holding
            ui.note("Full (90+) and Abundant (70+) give your cat bonuses; Scarcity (below 50) and Critical (below 25) cost it " ..
                    "(docs/mechanics/clan-life.md).")
        end, { id = "world-pile", open = true })
    end, { order = 20, group = "world" })

    -- ---------- World: Travel ----------
    local places = { list = nil, name = "" }
    local function loadPlaces()
        if places.list then return places.list end
        places.list = {}
        local f = DATA.places ~= "" and io.open(DATA.places, "rb")
        if f then
            local data = Game.json.decode(f:read("a"))
            f:close()
            if type(data) == "table" then places.list = data end
        end
        return places.list
    end
    local function savePlaces()
        if DATA.places == "" then return end
        local ok, err = Menu.saveJson(DATA.places, Menu.list(places.list))
        if not ok then travel.note = "Couldn't save the spots: " .. tostring(err) end
    end
    local spots = { at = -1, checkpoints = {}, areas = {} }
    local function findSpots()
        if os.clock() - spots.at < 5 then return spots end
        local s = { at = os.clock(), checkpoints = {}, areas = {} }
        for _, c in ipairs(Game.findAll("SwtQuestCheckpoint")) do
            local code = Game.str(Game.get(c, "ZoneCode", ""))
            local ok, l = pcall(function() return c:K2_GetActorLocation() end)
            if ok then s.checkpoints[#s.checkpoints + 1] = { code = code, label = areaName(code) or Game.name(c), at = { X = l.X, Y = l.Y, Z = l.Z } } end
        end
        table.sort(s.checkpoints, function(a, b) return a.code < b.code end)
        local seen = {}
        for _, z in ipairs(Game.findAll("WrcZoneNameTrigger")) do
            local code = Game.str(Game.get(z, "ZoneCode", ""))
            if code ~= "" and not seen[code] then
                local ok, l = pcall(function() return z:K2_GetActorLocation() end)
                if ok then
                    seen[code] = true
                    s.areas[#s.areas + 1] = { code = code, label = areaName(code), at = { X = l.X, Y = l.Y, Z = l.Z } }
                end
            end
        end
        table.sort(s.areas, function(a, b) return a.code < b.code end)
        spots = s
        return s
    end
    local TERRITORY_OF = { T = "ThunderClan", S = "ShadowClan", R = "RiverClan", W = "WindClan", M = "Moonpool", I = "the Island" }

    Menu.page("Travel", function(ui)
        ui.heading("Travel")
        local cat = Game.cat()
        if not cat then
            ui.text("Not in the world yet.")
            return
        end
        local here = cat:location()
        local s = now()
        ui.field("You're at", string.format("%.0f, %.0f, %.0f   (%s%s)", here.X, here.Y, here.Z, s.territory or "?",
                                             s.area and (", " .. s.area) or ""))
        if travel.note then ui.note(travel.note) end
        local hit = ui.buttons({ "Back", "Save this spot" })
        if hit == 1 and travel.back then jump(travel.back, "where you were", true) end
        if hit == 2 then
            local list = loadPlaces()
            local name = places.name ~= "" and places.name or string.format("Spot %d", #list + 1)
            list[#list + 1] = { name = name, level = Game.levelName(), X = here.X, Y = here.Y, Z = here.Z }
            savePlaces()
            travel.note = "Saved " .. name
            places.name = ""
        end
        places.name = ui.input("Name for a saved spot", places.name, { hint = "e.g. the big oak" })

        ui.section("Saved spots", function()
            local list, level, shown = loadPlaces(), Game.levelName(), 0
            for i, p in ipairs(list) do
                if p.level == level then
                    shown = shown + 1
                    local h = ui.buttons({ "Go: " .. tostring(p.name), "Forget" }, { kinds = { "primary", "danger" } })
                    if h == 1 then jump({ X = p.X, Y = p.Y, Z = p.Z }, tostring(p.name), true)
                    elseif h == 2 then
                        table.remove(list, i)
                        savePlaces()
                        break
                    end
                end
            end
            if shown == 0 then ui.note("None yet. Name a spot above and press Save this spot.") end
            ui.note("Kept in " .. (DATA.places ~= "" and DATA.places or "(no folder)") .. ".")
        end, { id = "travel-saved", open = true })

        local found = findSpots()
        ui.section("Checkpoints", function()
            ui.note("The game's own checkpoints, by area.")
            for _, c in ipairs(found.checkpoints) do
                if ui.button(string.format("%s  (%s)", c.label, c.code)) then jump(c.at, c.label, true) end
            end
        end, { id = "travel-checkpoints", open = false })
        for _, letter in ipairs({ "T", "S", "R", "W", "M", "I" }) do
            local list = {}
            for _, a in ipairs(found.areas) do
                if a.code:sub(1, 1) == letter then list[#list + 1] = a end
            end
            if #list > 0 then
                ui.section("Areas: " .. TERRITORY_OF[letter], function()
                    for _, a in ipairs(list) do
                        if ui.button(string.format("%s  (%s)", a.label or a.code, a.code)) then jump(a.at, a.label or a.code) end
                    end
                end, { id = "travel-" .. letter, open = false })
            end
        end
        ui.note("A jump puts your cat on the ground at the place (an area's own entrance). Back returns to where you " ..
                "were. Quest objectives you can travel to are on the Quests page.")
    end, { order = 21, group = "world" })

    -- ---------- World: Items ----------
    local drop = { item = DATA.items[1], count = 1, note = nil }
    local CATEGORY = { Consumable = "Herbs and pouches", Materials = "Materials", Cosmetic = "Accessories", Decoration = "Den decorations" }
    Menu.page("Items", function(ui)
        ui.heading("Items")
        if not Game.cat() then
            ui.text("Not in the world yet.")
            return
        end
        ui.note("As of the game's last save, with what you've picked up since.")
        local items, groups = Game.items.list(), {}
        for tag, n in pairs(items) do
            local cat = tostring(tag):match("^Gameplay%.Inventory%.(%w+)%.") or "Other"
            groups[cat] = groups[cat] or {}
            groups[cat][#groups[cat] + 1] = { tag = tag, n = n }
        end
        local any = false
        for _, cat in ipairs({ "Consumable", "Materials", "Cosmetic", "Decoration", "Other" }) do
            local list = groups[cat]
            if list then
                any = true
                table.sort(list, function(a, b) return a.tag < b.tag end)
                ui.section(CATEGORY[cat] or cat, function()
                    for _, it in ipairs(list) do ui.field(itemName(it.tag), it.n) end
                end, { id = "items-" .. cat, open = true })
            end
        end
        if not any then ui.text("Nothing yet.") end
        ui.separator()
        ui.heading("Get some")
        local function label(t) return itemName(t) .. "  (" .. (CATEGORY[tostring(t):match("^(%w+)%.") or ""] or "Other") .. ")" end
        local names, byName = {}, {}
        for i, t in ipairs(DATA.items) do names[i] = label(t) byName[names[i]] = t end
        drop.item = byName[ui.choice("Item", label(drop.item), names)] or drop.item
        drop.count = ui.number("How many", drop.count, { min = 1, max = 99, step = 1, whole = true })
        if ui.button("Put it by my cat", { kind = "primary" }) then
            local a, err = Game.items.drop("Gameplay.Inventory." .. drop.item, math.floor(drop.count + 0.5))
            drop.note = a and ("A pickup with " .. math.floor(drop.count + 0.5) .. " " .. itemName(drop.item) .. " is by your cat.")
                        or ("Couldn't: " .. tostring(err))
        end
        if drop.note then ui.note(drop.note) end
        ui.note("It's a pickup on the ground: walk to it and pick it up as usual.")
    end, { order = 23, group = "world" })

    -- ---------- Story: Quests ----------
    local questView = { filter = "Active" }
    local FILTER = { Active = { OngoingQuest = true, QuestComplete = true, DialogueProgress = true }, Available = { QuestAvailable = true },
                     Done = { QuestTurnedIn = true } }
    Menu.page("Quests", function(ui)
        ui.heading("Quests")
        if not Game.cat() then
            ui.text("Not in the world yet.")
            return
        end
        local tracked = Game.quests.tracked()
        ui.section("The quest you follow", function()
            if not tracked then
                ui.text("You aren't following a quest. Follow one below, or in the game's quest log.")
                return
            end
            local q = Game.quests.describe(tracked)
            ui.columns({ { "Quest", questTitle(q) }, { "State", STATUS_TEXT[q.status] or q.status or "?" }, { "Kind", q.type or "?" } })
            for i, o in ipairs(Game.quests.objectives(tracked)) do
                local label = string.format("Objective %d", i)
                local progress = (o.target and o.target > 0) and string.format("%d / %d", o.current or 0, o.target) or ""
                ui.field(label, (o.status or "?") .. (progress ~= "" and ("   " .. progress) or ""))
                if o.point and ui.button("Go to objective " .. i) then jump(Game.cat(o.point):location(), "the objective") end
            end
        end, { id = "quests-tracked", open = true })
        questView.filter = ui.radio("Show", questView.filter, { "Active", "Available", "Done", "All" })
        local list, n = quests(), 0
        for _, q in ipairs(list) do
            if questView.filter == "All" or (FILTER[questView.filter] or {})[q.status or ""] then
                n = n + 1
                ui.field(questTitle(q), STATUS_TEXT[q.status] or q.status or "?")
                if FILTER.Active[q.status or ""] and not q.tracked and ui.button("Follow " .. questTitle(q)) then
                    Game.quests.track(q.quest, true)
                    questCache.at = -1
                end
            end
        end
        if n == 0 then ui.note("None.") end
        ui.note(string.format("%d quests in all. Their titles are the game's own, for your cat's rank.", #list))
    end, { order = 30, group = "story" })

    -- ---------- Fight ----------
    local function fighterRows(ui, x, enemy)
        local cat = x:cat()
        if not cat then return end
        local label = cat:name() or words(cat:kind() or "?")
        ui.text(label .. (enemy and ("   (" .. words(cat:kind() or "") .. ")") or ""), { color = THEME.heading })
        local hp, maxhp = cat:health(), cat:maxHealth()
        if hp and maxhp and maxhp > 0 then
            ui.progress("Health", hp / maxhp, { color = "#e06c6c", format = string.format("%.0f / %.0f", hp, maxhp) })
        end
        local cs, maxcs = cat:combatStamina(), cat:maxCombatStamina()
        if cs and maxcs and maxcs > 0 then
            ui.progress("Stamina", cs / maxcs, { color = "#6cc58a", format = string.format("%.0f / %.0f", cs, maxcs) })
        end
        local st = x:stats()
        ui.columns({ { "Level", x:level() }, { "Stance", x:stance() or "?" }, { "Prowess", st.Prowess }, { "Strength", st.Strength },
                     { "Resilience", st.Resilience }, { "Instinct", st.Instinct }, { "Agility", st.Agility } })
        local move = x:moveTag()
        if move and move ~= "None" and move ~= "" then ui.field("Move", move:gsub("^Gameplay%.Combat%.Attack%.", "")) end
        local hit = ui.buttons({ "Heal", "Weaken", "Cure status" }, { kinds = { "good", "danger" } })
        if hit == 1 then cat:heal()
        elseif hit == 2 then cat:setHealth(1)
        elseif hit == 3 then cat:clearStatus() end
        if enemy then
            local drops = cat:rewards()
            local parts = {}
            for tag, n in pairs(drops) do parts[#parts + 1] = string.format("%d %s", n, itemName(tag)) end
            if #parts > 0 then
                ui.field("Drops", table.concat(parts, ", "))
                if ui.button("Double what it drops") then
                    for tag, n in pairs(drops) do drops[tag] = n * 2 end
                    cat:setRewards(drops)
                end
            end
        end
        ui.space(6)
    end
    Menu.page("Fight", function(ui)
        ui.heading("Fight")
        local f = Game.fight()
        if not f then
            ui.text("No fight now. During one, this page shows both sides (health, stamina, stats, stance and moves) and " ..
                    "lets you heal or weaken them.")
            ui.note("The game's own switches for fights (attacks that always land, a forced difficulty) are on Game switches.")
            return
        end
        local order = {}
        for _, c in ipairs(f:turnOrder()) do order[#order + 1] = c:name() or words(c:kind() or "?") end
        local cur = f:current()
        ui.columns({ { "Fight", words((f:kind() or ""):gsub("^BP_", ""):gsub("_C$", "")) }, { "Turn order", table.concat(order, ", ") },
                     { "Whose turn", cur and (cur:name() or words(cur:kind() or "?")) or "?" } })
        ui.section("Your side", function()
            for _, x in ipairs(f:players()) do fighterRows(ui, x, false) end
        end, { id = "fight-players", open = true })
        ui.section("Against you", function()
            for _, x in ipairs(f:enemies()) do fighterRows(ui, x, true) end
        end, { id = "fight-enemies", open = true })
        ui.note("Damage comes from the move, both fighters' stats and levels, and the stances (docs/mechanics/combat.md).")
    end, { order = 40, group = "fight" })

    -- ---------- Cheats: the game's developer switches ----------
    local FULL = { "Health", "Stamina", "StaminaCombat", "FreshKill", "Currency", "Level" }
    local FULL_LABEL = { Health = "Health", Stamina = "Stamina", StaminaCombat = "Fight stamina", FreshKill = "Fresh-kill pile",
                         Currency = "Currency", Level = "Experience" }
    local switches, switchesAt = {}, -1
    Menu.page("Game switches", function(ui)
        ui.heading("The game's developer switches")
        ui.note("The developers' own settings in the game's cheats manager. The release build obeys some of them and ignores " ..
                "others; some can break a quest or a save, so back up first (Mods page in Clan Mod Studio). They reset when " ..
                "the game restarts.")
        local m = Game.dev.manager()
        if not m then
            ui.text("No cheats manager yet.")
            return
        end
        ui.section("Always full", function()
            local full = Game.map(Game.get(m, "AlwaysHasFullResource"))
            for _, kind in ipairs(FULL) do
                local key = Game.enums.resource[kind]
                local was = full[key] == true
                local on = ui.toggle(FULL_LABEL[kind], was)
                if on ~= was then Game.dev.fullResource(kind, on) end
            end
        end, { id = "switches-full", open = true })
        ui.section("Every switch", function()
            if os.clock() - switchesAt > 1 then switches, switchesAt = Game.dev.list(), os.clock() end
            for _, p in ipairs(switches) do
                if p.type == "BoolProperty" then
                    local on = ui.toggle(words(p.name:gsub("^b", "")), p.value == true)
                    if on ~= (p.value == true) then Game.dev.set(p.name, on) switchesAt = -1 end
                elseif type(p.value) == "number" then
                    local v = ui.number(words(p.name), p.value, { step = 1, whole = INTEGER[p.type] })
                    if math.abs(v - p.value) > 1e-6 then Game.dev.set(p.name, asType(v, p.type)) switchesAt = -1 end
                end
            end
        end, { id = "switches-all", open = false })
    end, { order = 51, group = "cheats" })

    -- ---------- Tools: the log ----------
    local logView = { mode = "Mods", lines = {}, at = -1, paused = false }
    local function readLog()
        local f = DATA.log ~= "" and io.open(DATA.log, "rb")
        if not f then return { "No log found" .. (DATA.log ~= "" and (" at " .. DATA.log) or "") .. "." } end
        local size = f:seek("end")
        f:seek("set", math.max(0, size - 60000))
        local text = f:read("a")
        f:close()
        local out = {}
        for line in text:gmatch("[^\r\n]+") do out[#out + 1] = line end
        return out
    end
    Menu.page("Log", function(ui)
        ui.heading("Log")
        ui.note("The end of UE4SS's log, newest first: what the mods' scripts say, and their errors.")
        logView.mode = ui.radio("Show", logView.mode, { "Mods", "Errors", "Everything" })
        logView.paused = ui.switch("Hold still", logView.paused)
        if not logView.paused and os.clock() - logView.at > 1 then logView.lines, logView.at = readLog(), os.clock() end
        local shown = {}
        for i = #logView.lines, 1, -1 do
            local line = logView.lines[i]
            local keep = logView.mode == "Everything" or (logView.mode == "Mods" and line:find("[Lua] [", 1, true))
                         or (logView.mode == "Errors" and line:lower():find("error", 1, true))
            if keep then
                shown[#shown + 1] = (line:gsub("^%[%d+%-%d+%-%d+ (%d+:%d+:%d+)[%.%d]*%] ", "%1  "):gsub("%[Lua%] ", ""))
                if #shown >= 40 then break end
            end
        end
        if #shown == 0 then ui.note("Nothing to show.") end
        for _, line in ipairs(shown) do ui.note(line) end
    end, { order = 92, group = "tools" })

    -- ---------- Tools: this menu ----------
    Menu.page("Menu", function(ui)
        ui.heading("This menu")
        ui.field("Opens with", SETTINGS.key_name .. ", and Escape closes it")
        if SETTINGS.pad ~= "" then ui.field("On a controller", SETTINGS.pad_name .. ", and B closes it; the game pauses") end
        ui.note("To change the key or the button, use Clan Mod Studio (Mods page, In game), then install again.")
        local sz = ui.slider("Size", size, 0.6, 2.2, { step = 0.05, format = "x%.2f" })
        if math.abs(sz - size) > 1e-3 then
            size = sz
            fit()
        end
        local paused = win.pause:IsChecked()
        local p = ui.switch("Pause the game while it's open", paused)
        if p ~= paused then win.pause:SetIsChecked(p) end
        HOST.statusOn = ui.switch("Status line under the title", HOST.statusOn)
        ui.note("The size here (and A- / A+ at the top) lasts until the game closes; the studio sets the size it starts at.")
    end, { order = 93, group = "tools" })

    -- ---------- Tools: the inspector and the console (with code mods allowed) ----------
    if not SETTINGS.dev then return end
    local insp = { stack = {}, find = "", found = {}, filter = "", cache = nil, cacheFor = nil, cacheAt = -1, results = {} }
    local ROOTS = {
        { "Your cat", function() return Game.player() end },
        { "Player state", function() return Game.get(Game.controller(), "PlayerState") end },
        { "Controller", function() return Game.controller() end },
        { "Game state", function() return Game.gameState() end },
        { "Game instance", function() return Game.gameInstance() end },
        { "The fight", function() return Game.combatDirector() end },
    }
    local ROOT_LABELS = {}
    for i, r in ipairs(ROOTS) do ROOT_LABELS[i] = r[1] end
    local function open(label, o)
        if valid(o) then
            insp.stack[#insp.stack + 1] = { label = label, obj = o }
            insp.cache, insp.filter = nil, ""
        end
    end
    local function current()
        while #insp.stack > 0 and not valid(insp.stack[#insp.stack].obj) do insp.stack[#insp.stack] = nil end
        local top = insp.stack[#insp.stack]
        return top and top.obj or nil
    end
    local function members(o)
        if insp.cacheFor ~= o or os.clock() - insp.cacheAt > 0.5 or not insp.cache then
            insp.cache = { props = Game.properties(o), funcs = Game.functions(o) }
            insp.cacheFor, insp.cacheAt = o, os.clock()
        end
        return insp.cache
    end

    Menu.page("Inspector", function(ui)
        ui.heading("Inspector")
        ui.note("Browse the game's objects: what each holds and what it can do. Numbers, switches and text can be changed " ..
                "in place, and objects open with a click. Calling a function runs the game's own code with no arguments.")
        local hit = ui.buttons(ROOT_LABELS)
        if hit then
            insp.stack = {}
            open(ROOTS[hit][1], ROOTS[hit][2]())
        end
        ui.section("Managers", function()
            local names = {}
            for name in pairs(Game.managers) do names[#names + 1] = name end
            table.sort(names)
            for _, name in ipairs(names) do
                if ui.button(name) then
                    insp.stack = {}
                    open(name, Game.manager(name))
                end
            end
        end, { id = "insp-managers", open = false })
        insp.find = ui.input("Find by class", insp.find, { hint = "e.g. WrcRoamingEnemy" })
        if ui.button("Find") and insp.find ~= "" then insp.found = Game.findAll(insp.find) end
        if #insp.found > 0 then
            ui.section(string.format("Found %d", #insp.found), function()
                for i, o in ipairs(insp.found) do
                    if i > 30 then ui.note(string.format("... and %d more", #insp.found - 30)) break end
                    if valid(o) and ui.button(string.format("%s  (%s)", Game.name(o) or "?", Game.className(o) or "?")) then
                        insp.stack = {}
                        open(Game.name(o), o)
                    end
                end
            end, { id = "insp-found", open = true })
        end
        ui.separator()
        local o = current()
        if not o then
            ui.text("Pick something above.")
            return
        end
        local path = {}
        for i, e in ipairs(insp.stack) do path[i] = e.label end
        ui.field("Looking at", table.concat(path, " > "))
        ui.field("Class", table.concat(Game.parents(o), " < "))
        if #insp.stack > 1 and ui.button("Back") then
            insp.stack[#insp.stack] = nil
            insp.cache = nil
            return
        end
        insp.filter = ui.input("Filter", insp.filter, { hint = "part of a name" })
        local m = members(o)
        local shown, wanted = 0, insp.filter:lower()
        ui.section("Properties", function()
            for _, p in ipairs(m.props) do
                if wanted == "" or p.name:lower():find(wanted, 1, true) then
                    shown = shown + 1
                    if shown > 60 then ui.note("... more; use the filter") break end
                    local label = p.name
                    if p.type == "BoolProperty" then
                        local v = ui.toggle(label, p.value == true)
                        if v ~= (p.value == true) then Game.set(o, p.name, v) insp.cacheAt = -1 end
                    elseif type(p.value) == "number" then
                        local v = ui.number(label, p.value, { step = 1, whole = INTEGER[p.type] })
                        if math.abs(v - p.value) > 1e-6 then Game.set(o, p.name, asType(v, p.type)) insp.cacheAt = -1 end
                    elseif valid(p.value) then
                        if ui.button(label .. ": " .. (Game.name(p.value) or "?") .. " (" .. (Game.className(p.value) or "?") .. ")") then
                            open(p.name, p.value)
                        end
                    else
                        ui.field(label, Game.show(p.value):sub(1, 120))
                    end
                end
            end
        end, { id = "insp-props", open = true })
        ui.section("Functions", function()
            local n = 0
            for _, f in ipairs(m.funcs) do
                if wanted == "" or f.name:lower():find(wanted, 1, true) then
                    n = n + 1
                    if n > 60 then ui.note("... more; use the filter") break end
                    local params = {}
                    for i, p in ipairs(f.params) do params[i] = p.name .. ": " .. p.type:gsub("Property$", "") end
                    local sig = f.name .. "(" .. table.concat(params, ", ") .. ")" .. (f.returns and (" -> " .. f.returns:gsub("Property$", "")) or "")
                    if #f.params == 0 then
                        if ui.button("Call " .. sig) then
                            local ok, r = Game.call(o, f.name)
                            insp.results[f.name] = (ok and "returned " or "error: ") .. Game.show(r)
                        end
                        if insp.results[f.name] then ui.note(insp.results[f.name]) end
                    else
                        ui.field(f.owner, sig)
                    end
                end
            end
        end, { id = "insp-funcs", open = false })
    end, { order = 90, group = "tools" })

    -- A Lua console in the game: type a line, Run, see what it printed and returned.
    local con = { code = "", lines = {} }
    local env = setmetatable({ Game = Game, Menu = Menu }, { __index = _G })
    env.print = function(...)
        local parts = table.pack(...)
        for i = 1, parts.n do parts[i] = Game.show(parts[i]) end
        con.lines[#con.lines + 1] = table.concat(parts, "  ", 1, parts.n)
    end
    local function run(code)
        con.lines[#con.lines + 1] = "> " .. code
        local fn = load("return " .. code, "=console", "t", env)
        local err
        if not fn then fn, err = load(code, "=console", "t", env) end
        if not fn then
            con.lines[#con.lines + 1] = "error: " .. tostring(err)
            return
        end
        local res = table.pack(pcall(fn))
        if not res[1] then
            con.lines[#con.lines + 1] = "error: " .. tostring(res[2])
        elseif res.n > 1 then
            local parts = {}
            for i = 2, res.n do parts[#parts + 1] = Game.show(res[i]) end
            con.lines[#con.lines + 1] = "= " .. table.concat(parts, ", ")
        end
        while #con.lines > 40 do table.remove(con.lines, 1) end
    end
    Menu.page("Console", function(ui)
        ui.heading("Lua console")
        ui.note("Runs Lua in the game, with WCModsGame as Game (docs/scripting.md). An expression shows its value: " ..
                "Game.cat():health(). Globals you set stay for the next line.")
        con.code = ui.input("Lua", con.code, { hint = "Game.cat():name()" })
        local hit = ui.buttons({ "Run", "Clear" }, { kinds = { "primary" } })
        if hit == 1 and con.code ~= "" then run(con.code)
        elseif hit == 2 then con.lines = {} end
        for _, l in ipairs(con.lines) do ui.note(l) end
    end, { order = 91, group = "tools" })
end)()
'''


def lua(info=None):
    """The pages' Lua, with what data() found (or nothing: codes and tags show instead of names)."""
    from .sdk import lua_value
    return LUA.replace("@DATA@", lua_value(info if info is not None else data()))
