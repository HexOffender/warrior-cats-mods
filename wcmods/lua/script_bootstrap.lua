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
    -- Without the mod menu (its own mod, which may be off), WCModsGame writes it.
    local okG, G = pcall(require, "WCModsGame")
    if not okG then return false, "neither WCModsMenu nor WCModsGame is installed" end
    local f, err = io.open(MOD.settingsFile, "wb")
    if not f then return false, tostring(err) end
    f:write(G.json.encode(MOD.settings), "\n")
    f:close()
    return true
end

-- A mod menu page for this mod: MOD.page(function(ui) ... end, { title, order, group }). Making one replaces
-- the page wcmods would make for the settings. The mod menu is a mod of its own: when it's off this does
-- nothing and returns false.
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

local okGame, game = pcall(require, "WCModsGame")
if okGame then Game = game else MOD.log("WCModsGame didn't load: %s", tostring(game)) end

-- settings.json as it is now rather than as it was at install, so what MOD.save() wrote last time (a
-- quest's progress, where a cat stands) is still there after the game restarts. The copy from the
-- install is kept when the file can't be read.
if okGame and MOD.settingsFile then
    local f = io.open(MOD.settingsFile, "rb")
    if f then
        local text = f:read("a")
        f:close()
        local ok, data = pcall(Game.json.decode, text)
        if ok and type(data) == "table" then
            MOD.settings = data
        else
            MOD.log("couldn't read settings.json (%s); using the settings from the install", tostring(data))
        end
    end
end

local main, loadErr = loadfile(here .. "mod/main.lua")
if not main then
    MOD.log("can't load scripts/main.lua: %s", tostring(loadErr))
    return
end
local ok, err = xpcall(main, debug.traceback)
if not ok then MOD.log("error: %s", tostring(err)) end

-- Without a page of its own, a script with settings gets one: a row for each setting, and Save.
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
                if not saved then MOD.log("couldn't save: %s", tostring(why)) end
            end
        end, { order = 40, id = "script:" .. MOD.id })
    end
end
