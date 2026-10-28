-- ---------- the window's own pages: the Overview, the installed mods and the Tools ----------
-- Part of the host's script (menu.host_script pastes this in), so they use its locals: Menu, SETTINGS,
-- THEME, valid, log, HOST (the status line), pageList, GROUP_LABEL, size, fit and win. Each part is in a
-- function of its own, which keeps the host's main chunk under Lua's 200-local limit. The pages about the
-- game (your cat, the world, quests, fights, cheats) are the Menu pages mod's, added like any mod's.

-- ---------- Home: Overview and Installed mods ----------
;(function()
local function show_value(ui, label, v, depth)
    depth = depth or 0
    if type(v) ~= "table" then
        ui.field(string.rep("   ", depth) .. label, tostring(v))
        return
    end
    local keys = {}
    for k in pairs(v) do keys[#keys + 1] = k end
    table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
    if #keys == 0 then
        ui.field(string.rep("   ", depth) .. label, "(none)")
        return
    end
    local simple = #v > 0
    for _, x in ipairs(v) do if type(x) == "table" then simple = false end end
    if simple then
        local parts = {}
        for i, x in ipairs(v) do parts[i] = tostring(x) end
        ui.field(string.rep("   ", depth) .. label, table.concat(parts, ", "))
        return
    end
    if label ~= "" then ui.field(string.rep("   ", depth) .. label, "") end
    for i, k in ipairs(keys) do
        if i > 40 then
            ui.note(string.format("... and %d more", #keys - 40))
            break
        end
        show_value(ui, tostring(k), v[k], depth + 1)
    end
end

Menu.page("Overview", function(ui)
    ui.heading("Overview")
    -- Scripts that didn't start this time (the script bootstrap lists them: "<name>\t<why>" a line).
    local failed = Menu.shared("failed")
    if type(failed) == "string" then
        for line in failed:gmatch("[^\n]+") do
            local name, why = line:match("^([^\t]*)\t(.*)$")
            if name then ui.text(name .. " didn't start: " .. why .. " (Tools, Log, says more)", { color = THEME.danger }) end
        end
    end
    local okN, N = pcall(require, "WCModsNames")
    if okN and type(N) == "table" and N.loaded and N.loaded() == false then
        ui.text("The game isn't showing the names your mods add: it isn't reading wcmods' pak (~mods/zzz_WCMods_P.pak), " ..
                "so a renamed cat shows as <MISSING STRING TABLE ENTRY>. In Clan Mod Studio, check the game folder under " ..
                "Get set up and Apply again, or put your save back from Backups and repair.", { color = THEME.heading })
    end
    -- Without the Menu pages mod (or with it off), how to get the pages about the game.
    if SETTINGS.pages_note ~= "" then ui.text(SETTINGS.pages_note, { color = THEME.heading }) end
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
        -- Each group of the side bar, with its pages.
        local groups, titles = {}, {}
        for _, p in ipairs(pageList()) do
            if not titles[p.group] then
                titles[p.group] = {}
                groups[#groups + 1] = p.group
            end
            local list = titles[p.group]
            list[#list + 1] = p.title
        end
        for _, g in ipairs(groups) do ui.field(GROUP_LABEL[g] or g, table.concat(titles[g], ", ")) end
    end, { id = "overview-where", open = true })
end, { order = 0, group = "home" })

Menu.page("Installed mods", function(ui)
    ui.heading("Installed mods")
    ui.note("Built " .. SETTINGS.built .. ". Turn mods on and off and change what they do in Clan Mod Studio, " ..
            "then install again. Mods with live settings have pages of their own in this menu.")
    if #SETTINGS.mods == 0 then ui.text("No mods are on.") end
    for _, m in ipairs(SETTINGS.mods) do
        ui.section(m.name, function()
            if m.description ~= "" then ui.text(m.description) end
            ui.field("Folder", "mods/" .. m.id)
            ui.field("Contains", #m.kinds > 0 and table.concat(m.kinds, ", ") or "nothing yet")
            ui.field("Priority", m.priority)
        end, { id = "mod:" .. m.id, open = false })
    end
    ui.separator()
    ui.heading("What the build set up")
    for _, s in ipairs(SETTINGS.sections) do
        ui.section(s.title, function()
            ui.field("From", table.concat(s.mods, ", "))
            if s.status ~= "ok" then ui.text("Status: " .. s.status, { color = THEME.danger }) end
            for _, err in ipairs(s.errors) do ui.text(err, { color = THEME.danger }) end
            -- A mod the section had but left out (a script, with mods that run code off), or whose script won't
            -- load: said in the danger colour, not as if it went in.
            for _, id in ipairs(s.mods) do
                local note = type(s.notes) == "table" and s.notes[id]
                if type(note) == "table" and note["left out"] then
                    ui.text(id .. ": left out, " .. tostring(note["left out"]), { color = THEME.danger })
                end
                if type(note) == "table" and type(note.problems) == "table" then
                    for _, p in ipairs(note.problems) do ui.text(id .. ": " .. tostring(p), { color = THEME.danger }) end
                end
            end
            if s.notes then show_value(ui, "", s.notes) end
        end, { id = "section:" .. s.id, open = false })
    end
    if #SETTINGS.warnings > 0 then
        ui.section("Build warnings", function()
            for _, w in ipairs(SETTINGS.warnings) do ui.note(w) end
        end, { open = false })
    end
end, { order = 2, group = "home" })
end)()

-- ---------- Tools: the log and this menu ----------
;(function()
local logView = { mode = "Mods", lines = {}, at = -1, paused = false }
local function readLog()
    local f = SETTINGS.log ~= "" and io.open(SETTINGS.log, "rb")
    if not f then return { "No log found" .. (SETTINGS.log ~= "" and (" at " .. SETTINGS.log) or "") .. "." } end
    local size = f:seek("end")
    f:seek("set", math.max(0, size - 60000))
    local text = f:read("a")
    f:close()
    local out = {}
    for line in text:gmatch("[^\r\n]+") do out[#out + 1] = line end
    return out
end
-- What the filters keep. Mods: every line a script printed (a plain print too), not UE4SS's own start-up lines.
-- Errors: a script's error and what goes with it, not the start-up dump's names that have "Error" in them
-- ("FArchiveState::ArIsError = 0x29").
local function fromAScript(line)
    return line:find("[Lua] ", 1, true) ~= nil and not line:find("[Lua] Exposing size of", 1, true)
           and not line:find("[Lua] Failed to expose size of", 1, true)
end
local ERRORS = { "error:", "attempt to ", "can't load", "stack traceback", "didn't start" }
local function anError(line)
    local l = line:lower()
    for _, e in ipairs(ERRORS) do
        if l:find(e, 1, true) then return true end
    end
    return false
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
        local keep = logView.mode == "Everything" or (logView.mode == "Mods" and fromAScript(line))
                     or (logView.mode == "Errors" and anError(line))
        if keep then
            shown[#shown + 1] = (line:gsub("^%[%d+%-%d+%-%d+ (%d+:%d+:%d+)[%.%d]*%] ", "%1  "):gsub("%[Lua%] ", ""))
            if #shown >= 40 then break end
        end
    end
    if #shown == 0 then ui.note("Nothing to show.") end
    for _, line in ipairs(shown) do ui.note(line) end
end, { order = 92, group = "tools" })

Menu.page("Menu", function(ui)
    ui.heading("This menu")
    ui.field("Opens with", SETTINGS.key_name .. ", and Escape closes it")
    if SETTINGS.pad ~= "" then ui.field("On a controller", SETTINGS.pad_name .. ", and B closes it; the game pauses") end
    ui.note("To change the key or the button, use Options on the Settings and repair page in Clan Mod Studio, then " ..
            "Apply to game.")
    local sz = ui.slider("Size", size, SETTINGS.size_min, SETTINGS.size_max, { step = 0.05, format = "x%.2f" })
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
end)()

-- ---------- Tools: the inspector and the console (with code mods allowed) ----------
;(function()
if not SETTINGS.dev then return end
local okGame, Game = pcall(require, "WCModsGame")
if not okGame then
    log("WCModsGame didn't load, so the Inspector and the Lua console are left out: %s", tostring(Game))
    return
end
local INTEGER = { IntProperty = true, Int8Property = true, Int16Property = true, Int64Property = true, UInt16Property = true,
                  UInt32Property = true, UInt64Property = true, ByteProperty = true, EnumProperty = true }
-- A number for a property of this type: whole for integers, bytes and enums.
local function asType(v, t) return INTEGER[t] and math.floor(v + 0.5) or v end

local insp = { stack = {}, find = "", found = {}, foundCount = 0, findNote = nil, filter = "", cache = nil, cacheFor = nil,
               cacheAt = -1, results = {} }
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
-- Classes so wide that finding them means reading thousands of objects, which has crashed the game (above all
-- just after a level loads): Find asks for a narrower one instead.
local TOO_WIDE = { Object = true, Actor = true, Pawn = true, Character = true, ActorComponent = true,
                   SceneComponent = true, PrimitiveComponent = true, MeshComponent = true, Widget = true,
                   UserWidget = true, PanelWidget = true, TextBlock = true, Image = true, Button = true,
                   Texture2D = true, Material = true, MaterialInstanceDynamic = true, StaticMesh = true }
local FOUND_SHOWN = 30
local function find(class)
    class = class:gsub("^%s+", ""):gsub("%s+$", "")
    insp.found, insp.foundCount, insp.findNote = {}, 0, nil
    if TOO_WIDE[class] then
        insp.findNote = class .. " is the start of thousands of the game's objects, and reading them all can crash the " ..
                        "game. Find a narrower class, e.g. WrcRoamingEnemy."
        return
    end
    if not Game.player() then
        insp.findNote = "Find works once your cat is in the world (reading objects while a level loads can crash the game)."
        return
    end
    local all = Game.findAll(class)
    insp.foundCount = #all
    for i, o in ipairs(all) do
        if i > FOUND_SHOWN then break end
        local name = Game.name(o) or "?"
        insp.found[i] = { obj = o, name = name, label = string.format("%s  (%s)", name, Game.className(o) or "?") }
    end
    if #all == 0 then insp.findNote = "None found. Class names are the game's own, e.g. WrcRoamingEnemy (the Inspector shows an object's)." end
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
    if ui.button("Find") and insp.find ~= "" then find(insp.find) end
    if insp.findNote then ui.note(insp.findNote) end
    if #insp.found > 0 then
        ui.section(string.format("Found %d", insp.foundCount), function()
            -- The names were read once, when Find was pressed: not again each frame across every object.
            for _, e in ipairs(insp.found) do
                if valid(e.obj) and ui.button(e.label) then
                    insp.stack = {}
                    open(e.name, e.obj)
                end
            end
            if insp.foundCount > #insp.found then ui.note(string.format("... and %d more", insp.foundCount - #insp.found)) end
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

-- A Lua console in the game, for people who write scripts: type a line, Run, see what it printed and returned.
-- Titled "Lua (advanced)", as the game's own command window (~) and the studio's Try Lua in the game are other
-- things; its id stays "Lua console", which the agent's tests open it by.
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
Menu.page("Lua (advanced)", function(ui)
    ui.heading("Lua (advanced)")
    ui.note("For people who write scripts: runs a line of Lua in the game, with WCModsGame as Game " ..
            "(docs/scripting.md). An expression shows its value: Game.cat():health(). Globals you set stay for the " ..
            "next line. Nothing here is saved into a mod.")
    con.code = ui.input("Lua", con.code, { hint = "Game.cat():name()" })
    local hit = ui.buttons({ "Run", "Clear" }, { kinds = { "primary" } })
    if hit == 1 and con.code ~= "" then run(con.code)
    elseif hit == 2 then con.lines = {} end
    for _, l in ipairs(con.lines) do ui.note(l) end
end, { order = 91, group = "tools", id = "Lua console" })
end)()
