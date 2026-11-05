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
    ue4ss = here:match("/Mods/([^/]+)/") or "",   -- this UE4SS mod's folder (the mod menu tells pages apart by it)
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
    -- Without WCModsMenu (an install gone wrong), WCModsGame writes it, whole or not at all as Menu.saveJson does:
    -- to settings.json.new, checked, then in the old one's place (moved aside first: Windows won't rename over it).
    local okG, G = pcall(require, "WCModsGame")
    if not okG then return false, "neither WCModsMenu nor WCModsGame is installed" end
    local okText, text = pcall(G.json.encode, MOD.settings)
    if not okText then return false, tostring(text) end
    local path, tmp, old = MOD.settingsFile, MOD.settingsFile .. ".new", MOD.settingsFile .. ".old"
    local f, err = io.open(tmp, "wb")
    if not f then return false, tostring(err) end
    local wrote, werr = f:write(text, "\n")
    local closed, cerr = f:close()
    if not wrote or not closed then
        os.remove(tmp)
        return false, tostring(werr or cerr)
    end
    -- The old file aside only when there is one: a settings.json.old with no settings.json is a stopped save's,
    -- and is kept. A read-only settings.json isn't replaced.
    local had = false
    local cur = io.open(path, "rb")
    if cur then
        cur:close()
        local rw = io.open(path, "r+b")
        if not rw then os.remove(tmp) return false, path .. " can't be written (is it read-only?)" end
        rw:close()
        local gone, gerr, code = os.remove(old)
        if not gone and code ~= 2 then os.remove(tmp) return false, "couldn't remove " .. old .. " (" .. tostring(gerr) .. ")" end
        local aside, aerr = os.rename(path, old)
        if not aside then os.remove(tmp) return false, "couldn't move " .. path .. " aside (" .. tostring(aerr) .. ")" end
        had = true
    end
    local moved, merr = os.rename(tmp, path)
    if not moved then
        local restored = not had or os.rename(old, path)
        os.remove(tmp)
        return false, "couldn't replace " .. path .. " (" .. tostring(merr) .. ")" ..
                      (restored and "" or "; the previous file is now at " .. old)
    end
    if had then os.remove(old) end
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
    -- Lua on the game thread only (SDK.md, "Rules that keep the game running"): UE4SS runs LoopAsync and
    -- ExecuteWithDelay on a thread of their own and key binds on its event loop, while the game thread runs this
    -- state's timers and hooks, and two threads in one Lua state break it ("Ref was not function", then a crash).
    -- So a script's own calls to them go to the game thread: the loops to UE4SS's game-thread ones, a key bind to
    -- Game.onKey, whose bind only counts the press.
    if LoopInGameThreadWithDelay ~= nil and CancelDelayedAction ~= nil then
        LoopAsync = function(ms, fn)
            local handle
            handle = LoopInGameThreadWithDelay(ms, function()
                local okRun, stop = pcall(fn)
                if not okRun then
                    MOD.log("error in LoopAsync: %s", tostring(stop))
                elseif stop == true then
                    CancelDelayedAction(handle)
                end
            end)
        end
    end
    if ExecuteInGameThreadWithDelay ~= nil then
        ExecuteWithDelay = function(ms, fn) ExecuteInGameThreadWithDelay(ms, fn) end
    end
    RegisterKeyBind = function(key, a, b)
        if b == nil then Game.onKey(key, a) else Game.onKey(key, b, a) end
    end
else
    MOD.log("WCModsGame didn't load: %s", tostring(game))
end

-- settings.json as it is now rather than as it was at install, so what MOD.save() wrote last time (a
-- quest's progress, where a cat stands) is still there after the game restarts. The copy from the
-- install is kept when the file can't be read.
if okGame and MOD.settingsFile then
    -- A settings file's object; or nil and why not, or nil and nil when there's no such file. Not a file holding
    -- just null either: that's Game.json.null, a table every null read in this Lua state shares, and the first
    -- setting a page set would go into it.
    local function readSettings(file)
        local f = io.open(file, "rb")
        if not f then return nil, nil end
        local text = f:read("a")
        f:close()
        if text:sub(1, 3) == BOM then text = text:sub(4) end
        local ok, data, err = pcall(Game.json.decode, text)
        if not ok then return nil, tostring(data) end
        if err == nil and (type(data) ~= "table" or data == Game.json.null) then err = "it doesn't hold an object" end
        if err ~= nil then return nil, tostring(err) end
        return data
    end
    local data, err = readSettings(MOD.settingsFile)
    local from = "settings.json"
    if data == nil and err == nil then
        -- No settings.json: a Save that stopped between its two renames (the game closed, say) left the settings it
        -- saved in settings.json.new, written whole (and, through Menu.saveJson, read back), and the ones before it
        -- in settings.json.old. The newer is read when it holds an object, else the older. (A .new that didn't get
        -- that far is half written, and doesn't decode.) A .new that's read is put in settings.json's place, which
        -- finishes the stopped Save: the next Save writes a .new of its own first, and if that failed or stopped,
        -- the last Save would go with it. The .old is left for the next Save to remove.
        local newErr
        data, newErr = readSettings(MOD.settingsFile .. ".new")
        if data ~= nil then
            local moved, merr = os.rename(MOD.settingsFile .. ".new", MOD.settingsFile)
            MOD.log("settings.json is missing; read settings.json.new, the last Save, which stopped before it took settings.json's place%s",
                    moved and ", and put it there" or ("; couldn't put it there (" .. tostring(merr) .. ")"))
        else
            from = "settings.json.old"
            data, err = readSettings(MOD.settingsFile .. ".old")
            if data ~= nil then
                MOD.log("settings.json is missing; reading settings.json.old, the settings before a Save that stopped part way%s",
                        newErr and (" (settings.json.new is no good: " .. newErr .. ")") or "")
            elseif err == nil and newErr ~= nil then
                from, err = "settings.json.new", newErr
            elseif err ~= nil and newErr ~= nil then
                err = err .. "; settings.json.new is no good either: " .. newErr
            end
        end
    end
    if data ~= nil then
        MOD.settings = data
    elseif err ~= nil then
        MOD.log("couldn't read %s (%s); using the settings from the install", from, err)
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
        list = type(list) == "string" and list or ""
        local entry = (MOD.name:gsub("[\t\n]", " ")) .. "\t" .. (first:gsub("[\t\n]", " ")) .. "\n"
        if not list:find(entry, 1, true) then ModRef:SetSharedVariable("WCModsMenu.failed", list .. entry) end
    end)
    if not okGame then return end
    local okDraw, Draw = pcall(require, "WCModsDraw")
    if not okDraw then return end
    local file, line = first:match("(scripts/[^:]+):(%d+):")
    local waiting
    waiting = Game.every(0.5, function()
        if not Game.player() then return end
        Game.cancel(waiting)
        -- The menu's key, as its window shares it (by now: the window has started long before your cat is in).
        local okKey, key = pcall(function() return ModRef:GetSharedVariable("WCModsMenu.key_name") end)
        if not (okKey and type(key) == "string" and key ~= "") then key = "Insert" end
        local said = MOD.name .. " didn't start: " .. (file and (file .. ", line " .. line) or first:sub(1, 80)) ..
                     ". The mod menu (" .. key .. "), Tools, Log says more."
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
-- under it whether the file was written. "_help_<key>" shows under that key's row, and "_min_<key>" and
-- "_max_<key>" bound its number (the studio's Settings on the mod's card reads them the same way).
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
        -- A key that goes with another's row: its help, or a bound of its number.
        local function partOf(k)
            local target = type(k) == "string" and (k:match("^_help_(.+)$") or k:match("^_min_(.+)$") or k:match("^_max_(.+)$"))
            return target and MOD.settings[target] ~= nil
        end
        local status = nil   -- what the last Save did: "Saved to settings.json." or "Couldn't save: <why>"
        Menu.page(MOD.name, function(ui)
            ui.heading(MOD.name)
            for _, k in ipairs(keys) do
                local v = MOD.settings[k]
                if partOf(k) then
                    -- shown with its row, or used by it
                elseif type(k) == "string" and k:sub(1, 1) == "_" then
                    if type(v) == "string" then ui.note(v) end
                elseif type(v) == "boolean" then
                    MOD.settings[k] = ui.switch(label(k), v)
                elseif type(v) == "number" then
                    local whole = math.type(v) == "integer"
                    local lo, hi = MOD.settings["_min_" .. tostring(k)], MOD.settings["_max_" .. tostring(k)]
                    local n = ui.number(label(k), v, { step = whole and 1 or 0.1, whole = whole,
                                                       min = type(lo) == "number" and lo or nil,
                                                       max = type(hi) == "number" and hi or nil })
                    MOD.settings[k] = whole and math.floor(n + 0.5) or n
                elseif type(v) == "string" and v:match("^#%x%x%x%x%x%x$") then
                    MOD.settings[k] = ui.color(label(k), v)
                elseif type(v) == "string" then
                    MOD.settings[k] = ui.input(label(k), v)
                else
                    ui.field(label(k), Menu.json(v))
                end
                local help = type(k) == "string" and k:sub(1, 1) ~= "_" and MOD.settings["_help_" .. k]
                if type(help) == "string" then ui.note(help) end
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
