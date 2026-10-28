-- Written by wcmods: starts @NAME@'s in-game script (mods/@ID@/scripts/main.lua) with its settings.
-- Change the mod's own files and install again rather than editing this. See docs/scripting.md.
local here = debug.getinfo(1, "S").source:gsub("^@", ""):gsub("\\", "/"):match("^(.*/)") or @FALLBACK@
package.path = here .. "mod/?.lua;" .. here .. "mod/?/init.lua;" .. package.path

MOD = {
    id = @ID_LUA@,
    name = @NAME_LUA@,
    folder = @FOLDER_LUA@,           -- the mod's folder in mods/
    settings = @SETTINGS@,           -- settings.json (an empty table without one; read again below)
    settingsFile = @SETTINGS_FILE@,  -- where MOD.save() writes them, or nil
}

function MOD.log(fmt, ...)
    print("[" .. MOD.name .. "] " .. string.format(fmt, ...) .. "\n")
end

-- Write MOD.settings back to the mod's settings.json (keys sorted, notes like "_help" kept first), so
-- the next install starts with them. Returns true, or false and why.
function MOD.save()
    if not MOD.settingsFile then return false, "this mod has no settings.json" end
    local ok, Menu = pcall(require, "WCModsMenu")
    if ok then return Menu.saveJson(MOD.settingsFile, MOD.settings) end
    -- Without WCModsMenu (an install gone wrong), WCModsGame writes it.
    local okG, G = pcall(require, "WCModsGame")
    if not okG then return false, "neither WCModsMenu nor WCModsGame is installed" end
    local f, err = io.open(MOD.settingsFile, "wb")
    if not f then return false, tostring(err) end
    f:write(G.json.encode(MOD.settings), "\n")
    f:close()
    return true
end

-- A mod menu page for this mod: MOD.page(function(ui) ... end, { title, order, group }). Making one replaces
-- the page wcmods would make for the settings, even made later (from a timer): the two share the id
-- "script:<mod id>", and the mod menu keeps one page for an id. Returns false when WCModsMenu isn't there (it's
-- installed with UE4SS, as this script is, so that's an install gone wrong).
local pageMade = false
function MOD.page(fn, opts)
    pageMade = true
    opts = opts or {}
    local ok, Menu = pcall(require, "WCModsMenu")
    if not ok then return false end
    Menu.page(opts.title or MOD.name, fn, { order = opts.order or 40, group = opts.group,
                                            id = opts.id or ("script:" .. MOD.id) })
    return true
end

-- The mod's own Lua files, loaded under the names they have in the mod ("scripts/main.lua"), so an error says
-- "scripts/main.lua:12: ..." rather than the game folder's long path. A byte order mark (Notepad's) and a first
-- line for a shell ("#!...") are passed over, as loadfile does.
local BOM = "\239\187\191"
local function loadOwn(rel)
    local f, err = io.open(here .. "mod/" .. rel, "rb")
    if not f then return nil, "scripts/" .. rel .. " isn't there (" .. tostring(err) .. ")" end
    local text = f:read("a")
    f:close()
    if text:sub(1, 3) == BOM then text = text:sub(4) end
    if text:sub(1, 1) == "#" then text = "--" .. text end
    return load(text, "@scripts/" .. rel)
end
-- require("name") finds the mod's own files the same way (scripts/name.lua, or scripts/name/init.lua).
table.insert(package.searchers, 2, function(name)
    local rel = name:gsub("%.", "/")
    for _, file in ipairs({ rel .. ".lua", rel .. "/init.lua" }) do
        local f = io.open(here .. "mod/" .. file, "rb")
        if f then
            f:close()
            local fn, err = loadOwn(file)
            if not fn then error(string.format("error loading module '%s' from file 'scripts/%s':\n\t%s", name, file, err), 0) end
            return fn, "scripts/" .. file
        end
    end
    return nil
end)

local okGame, game = pcall(require, "WCModsGame")
if okGame then
    Game = game
    -- WCModsGame's own lines in the log (a timer's or a key's error, a cat that couldn't be spawned) say whose
    -- script it was. Each UE4SS mod has a Lua state of its own, so the name is this mod's alone.
    Game.modName = MOD.name
else
    MOD.log("WCModsGame didn't load: %s", tostring(game))
end

-- settings.json as it is now rather than as it was at install, so what MOD.save() wrote last time (a
-- quest's progress, where a cat stands) is still there after the game restarts. The copy from the
-- install is kept when the file can't be read.
if okGame and MOD.settingsFile then
    local f = io.open(MOD.settingsFile, "rb")
    if f then
        local text = f:read("a")
        f:close()
        if text:sub(1, 3) == BOM then text = text:sub(4) end
        local ok, data = pcall(Game.json.decode, text)
        if ok and type(data) == "table" then
            MOD.settings = data
        else
            MOD.log("couldn't read settings.json (%s); using the settings from the install", tostring(data))
        end
    end
end

-- A script that didn't start says so where its maker will look: the mod menu's Overview lists it (the shared
-- WCModsMenu.failed, a line per mod: "<name>\t<the error's first line>"), and once your cat is in the world a
-- line at the top of the screen says so for ten seconds.
local function didntStart(err)
    local first = tostring(err):match("^[^\n]*")
    MOD.failed = first
    pcall(function()
        local list = ModRef:GetSharedVariable("WCModsMenu.failed")
        local line = (MOD.name:gsub("[\t\n]", " ")) .. "\t" .. (first:gsub("[\t\n]", " ")) .. "\n"
        ModRef:SetSharedVariable("WCModsMenu.failed", (type(list) == "string" and list or "") .. line)
    end)
    if not okGame then return end
    local okDraw, Draw = pcall(require, "WCModsDraw")
    if not okDraw then return end
    local file, line = first:match("(scripts/[^:]+):(%d+):")
    local okKey, key = pcall(function() return ModRef:GetSharedVariable("WCModsMenu.key_name") end)
    if not (okKey and type(key) == "string" and key ~= "") then key = "Insert" end
    local said = MOD.name .. " didn't start: " .. (file and (file .. ", line " .. line) or first:sub(1, 80)) ..
                 ". The mod menu (" .. key .. "), Tools, Log says more."
    local waiting
    waiting = Game.every(0.5, function()
        if not Game.player() then return end
        Game.cancel(waiting)
        local painter = Draw.onFrame(function(d)
            local w = d.width > 0 and d.width or 1920
            local tw, th = d.measure(said, 20)
            d.rect(w / 2 - tw / 2 - 16, 24, tw + 32, th + 16, { color = "#000000b0" })
            d.text(w / 2, 32, said, { size = 20, align = "center", color = "#ffd98a" })
        end)
        Game.after(10, function() Draw.remove(painter) end)
    end)
end

local main, loadErr = loadOwn("main.lua")
if not main then
    MOD.log("can't load: %s", tostring(loadErr))
    didntStart(loadErr)
    return
end
local ok, err = xpcall(main, debug.traceback)
if not ok then
    MOD.log("error: %s", tostring(err))
    didntStart(err)
end

-- Without a page of its own, a script with settings gets one: a row for each setting, and Save, which says
-- under it whether the file was written.
if not pageMade and @AUTO_PAGE@ and next(MOD.settings) ~= nil then
    local okMenu, Menu = pcall(require, "WCModsMenu")
    if okMenu then
        local keys = {}
        for k in pairs(MOD.settings) do keys[#keys + 1] = k end
        table.sort(keys)
        local function label(k)
            local s = tostring(k):gsub("_", " "):gsub("(%l)(%u)", "%1 %2"):lower()
            return (s:gsub("^%l", string.upper))
        end
        local status = nil   -- what the last Save did: "Saved to settings.json." or "Couldn't save: <why>"
        Menu.page(MOD.name, function(ui)
            ui.heading(MOD.name)
            for _, k in ipairs(keys) do
                local v = MOD.settings[k]
                if type(k) == "string" and k:sub(1, 1) == "_" then
                    if type(v) == "string" then ui.note(v) end
                elseif type(v) == "boolean" then
                    MOD.settings[k] = ui.switch(label(k), v)
                elseif type(v) == "number" then
                    local whole = math.type(v) == "integer"
                    local n = ui.number(label(k), v, { step = whole and 1 or 0.1, whole = whole })
                    MOD.settings[k] = whole and math.floor(n + 0.5) or n
                elseif type(v) == "string" and v:match("^#%x%x%x%x%x%x$") then
                    MOD.settings[k] = ui.color(label(k), v)
                elseif type(v) == "string" then
                    MOD.settings[k] = ui.input(label(k), v)
                else
                    ui.field(label(k), Menu.json(v))
                end
            end
            if ui.button("Save", { kind = "primary" }) then
                local saved, why = MOD.save()
                status = saved and "Saved to settings.json." or ("Couldn't save: " .. tostring(why))
                if not saved then MOD.log("couldn't save: %s", tostring(why)) end
            end
            if status then ui.note(status) end
        end, { order = 40, id = "script:" .. MOD.id })
    end
end
