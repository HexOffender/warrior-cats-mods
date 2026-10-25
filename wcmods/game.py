"""WCModsGame: the shared UE4SS Lua module for scripting the game itself.

The player's cat (stats, health, stamina, level, traits, looks), items, the fresh-kill pile, time of day,
quests, combat (fighters, moves, statuses, damage), the save's live data, the game's managers and its
developer switches, plus the plumbing scripts need: safe object access, timers, keys, hooks and events.
Installed with every build as ue4ss/Mods/shared/WCModsGame/WCModsGame.lua; docs/scripting.md documents
every call.

Most of the game's own C++ state isn't visible to Lua through reflection (its health, stamina, level
and stat components have no reflected members). Where the reverse-engineering notes found a value's
offset (docs/mechanics/), the module maps it with UE4SS's RegisterCustomProperty, so scripts read and
write it like any other property. Everything else goes through what the game does reflect: its
managers, the combat director, the quest and save managers.
"""

SHARED_NAME = "WCModsGame"

# Members the game doesn't reflect, found by reverse-engineering build 24847281 (docs/mechanics/,
# docs/reverse-engineering.md): class, then (property name, offset in the object, type). Rendered into
# the Lua as Game.hidden. They're offsets inside objects, so ASLR doesn't move them, but a game update
# that changes a class's layout does: signatures.py finds them again in a new build, and lua() takes the
# offsets it found.
HIDDEN = [
    # Every resource component (health, stamina, combat stamina, level, fresh-kill pile).
    ("/Script/SwtQuest.SwtQuestResourceComponent", [
        ("WCM_ResourceType", 0x108, "IntProperty"), ("WCM_Value", 0x10C, "FloatProperty"),
        ("WCM_Max", 0x110, "FloatProperty"), ("WCM_Scale", 0x114, "FloatProperty")]),
    ("/Script/SwtQuest.SwtQuestStaminaComponent", [("WCM_Regen", 0x11C, "FloatProperty")]),
    # The player state's level component: level, and the cat's stats out of combat.
    ("/Script/SwtAdventure.SwtAdventureLevelComponent", [
        ("WCM_Level", 0x120, "IntProperty"), ("WCM_LevelShown", 0x124, "IntProperty"),
        ("WCM_Prowess", 0x154, "FloatProperty"), ("WCM_Strength", 0x158, "FloatProperty"),
        ("WCM_Resilience", 0x15C, "FloatProperty"), ("WCM_Instinct", 0x160, "FloatProperty"),
        ("WCM_Agility", 0x164, "FloatProperty"), ("WCM_Stamina", 0x168, "FloatProperty")]),
    ("/Script/SwtAdventure.SwtAdventureFreshKillPileComponent", [
        ("WCM_DecayTimer", 0x130, "FloatProperty"), ("WCM_DecayTime", 0x134, "FloatProperty")]),
    ("/Script/SwtAdventure.SwtAdventureGameplayGameState", [("WCM_DayTime", 0x438, "FloatProperty")]),
    # A fighter's combat component (set up when a fight starts).
    ("/Script/SwtAdventure.TurnBasedCombatComponent", [
        ("WCM_Stance", 0x1A0, "ByteProperty"),
        ("WCM_Prowess", 0x1C4, "FloatProperty"), ("WCM_Strength", 0x1C8, "FloatProperty"),
        ("WCM_Resilience", 0x1CC, "FloatProperty"), ("WCM_Instinct", 0x1D0, "FloatProperty"),
        ("WCM_Agility", 0x1D4, "FloatProperty"), ("WCM_Stamina", 0x1D8, "FloatProperty"),
        ("WCM_Clan", 0x3D8, "ByteProperty"), ("WCM_Level", 0x3DC, "IntProperty"),
        ("WCM_PresetDamage", 0x3E4, "IntProperty")]),
]

LUA = r'''-- WCModsGame: script the game. Installed by wcmods; any UE4SS script can use it:
--
--   local Game = require("WCModsGame")
--   local cat = Game.cat()                       -- your cat
--   print(cat:name(), cat:level(), cat:health())
--   Game.on("combatStart", function(fight) print("A fight!\n") end)
--   Game.every(5, function() cat:setStamina(cat:maxStamina()) end)
--
-- Everything runs on the game thread. Call it from a timer, an event, a key, a menu page or a painter,
-- not from LoopAsync (two threads in one Lua state crash the game). docs/scripting.md has every call.
local Game = { version = 1 }

local function log(fmt, ...) print(string.format("[WCModsGame] " .. fmt .. "\n", ...)) end
Game.log = log

-- ===================================================================================== objects
-- UE4SS hands back invalid objects (not nil) for things it can't find, and a destroyed object's slot
-- can be reused, so everything is checked and guarded. Calling a function on an object that isn't there
-- crashes the game inside UE4SS, where pcall can't catch it: every call below checks the object first.
function Game.valid(o)
    if o == nil or type(o) ~= "userdata" then return false end
    local ok, v = pcall(function() return o:IsValid() end)
    return ok and v == true
end
local valid = Game.valid

-- An object reference that points at nothing (as opposed to a struct, array or map, which have no
-- IsValid of their own).
local function dead(o)
    if type(o) ~= "userdata" then return false end
    local ok, v = pcall(function() return o:IsValid() end)
    return ok and v == false
end
Game.dead = dead

-- The text of an FString, FName or FText (or a Lua string), else "".
function Game.str(v)
    if type(v) == "string" then return v end
    if v == nil then return "" end
    local ok, s = pcall(function() return v:ToString() end)
    if ok and type(s) == "string" then return s end
    return tostring(v)
end
local str = Game.str

function Game.className(o)
    if not valid(o) then return nil end
    local ok, n = pcall(function() return o:GetClass():GetFName():ToString() end)
    return ok and n or nil
end

function Game.name(o)
    if not valid(o) then return nil end
    local ok, n = pcall(function() return o:GetFName():ToString() end)
    return ok and n or nil
end

function Game.fullName(o)
    if not valid(o) then return nil end
    local ok, n = pcall(function() return o:GetFullName() end)
    return ok and n or nil
end

-- The class of an object, then the classes that's made from, up to Object.
function Game.parents(o)
    local names = {}
    if not valid(o) then return names end
    local ok, cls = pcall(function() return o:GetClass() end)
    if not ok then return names end
    while valid(cls) do
        local n = cls:GetFName():ToString()
        names[#names + 1] = n
        if n == "Object" then break end
        cls = cls:GetSuperStruct()
    end
    return names
end

local isaCache = {}   -- "class|wanted" -> bool
-- Whether an object's class is `className` or made from it, e.g. Game.isA(actor, "WrcRoamingEnemy").
function Game.isA(o, className)
    local cls = Game.className(o)
    if not cls then return false end
    local key = cls .. "|" .. className
    local hit = isaCache[key]
    if hit == nil then
        hit = false
        for _, n in ipairs(Game.parents(o)) do
            if n == className then hit = true break end
        end
        isaCache[key] = hit
    end
    return hit
end

-- UE4SS answers a read of a property an object doesn't have with a placeholder ("TrivialObject"), not
-- nil; Game.get treats that as missing.
local function missing(v)
    if v == nil then return true end
    if type(v) ~= "userdata" then return false end
    local ok, s = pcall(tostring, v)
    if ok and type(s) == "string" and s:find("^TrivialObject") ~= nil then return true end
    return dead(v)
end
Game.missing = missing

-- Read a property path ("TurnBasedCombatComponent.AttackSelected.Damage"), or `default` when any step
-- is missing. Numbers in the path index arrays (from 1).
function Game.get(o, path, default)
    local ok, v = pcall(function()
        local cur = o
        for part in tostring(path):gmatch("[^%.]+") do
            if missing(cur) then return nil end
            local n = tonumber(part)
            if n then cur = cur[n] else cur = cur[part] end
        end
        return cur
    end)
    if not ok or missing(v) then return default end
    return v
end

-- Set a property path; returns true, or false and why.
function Game.set(o, path, value)
    local ok, err = pcall(function()
        local parts = {}
        for part in tostring(path):gmatch("[^%.]+") do parts[#parts + 1] = part end
        local cur = o
        for i = 1, #parts - 1 do
            local n = tonumber(parts[i])
            cur = n and cur[n] or cur[parts[i]]
        end
        local last = parts[#parts]
        cur[tonumber(last) or last] = value
    end)
    return ok, (not ok) and tostring(err) or nil
end

-- Call a function on an object safely: Game.call(o, "Name", args...) -> true, results... or false, error.
function Game.call(o, fname, ...)
    if not valid(o) then return false, "not a live object" end
    local args = table.pack(...)
    return pcall(function() return o[fname](o, table.unpack(args, 1, args.n)) end)
end

-- One object of a class (its short name: "WrcRoamingEnemy", "BP_WrcQuestManager_C"), found once and kept
-- while it's still that class.
local firsts = {}
function Game.find(className)
    local hit = firsts[className]
    if hit and valid(hit) and Game.isA(hit, className) then return hit end
    local ok, o = pcall(FindFirstOf, className)
    if ok and valid(o) then
        firsts[className] = o
        return o
    end
    firsts[className] = nil
    return nil
end

-- Every object of a class (valid ones only).
function Game.findAll(className)
    local out = {}
    local ok, list = pcall(FindAllOf, className)
    if ok and list then
        for _, o in ipairs(list) do
            if valid(o) then out[#out + 1] = o end
        end
    end
    return out
end

-- An object by its path ("/Script/Engine.Default__GameplayStatics"), or nil.
function Game.object(path)
    local ok, o = pcall(StaticFindObject, path)
    if ok and valid(o) then return o end
    return nil
end

-- Load an asset by path ("/Game/Mods/MyHat/SM_Hat.SM_Hat"), or nil and why.
function Game.load(path)
    local ok, o = pcall(LoadAsset, path)
    if ok and valid(o) then return o end
    return nil, ok and "not found" or tostring(o)
end

-- Values to pass to the game.
function Game.tag(name) return { TagName = FName(name) } end
function Game.tagName(tag) return str(Game.get(tag, "TagName")) end
function Game.vector(x, y, z) return { X = x or 0, Y = y or 0, Z = z or 0 } end

-- A rotator with its pitch kept (UE4SS drops the pitch of a rotator passed as a Lua table).
function Game.rotator(pitch, yaw, roll)
    local math = Game.library("KismetMathLibrary")
    if math then
        local ok, r = pcall(function() return math:MakeRotator(roll or 0, pitch or 0, yaw or 0) end)
        if ok then return r end
    end
    return { Pitch = pitch or 0, Yaw = yaw or 0, Roll = roll or 0 }
end

-- A function library's default object, for calling its static functions: Game.library("GameplayStatics").
local LIBRARIES = {
    GameplayStatics = "/Script/Engine.Default__GameplayStatics",
    KismetSystemLibrary = "/Script/Engine.Default__KismetSystemLibrary",
    KismetMathLibrary = "/Script/Engine.Default__KismetMathLibrary",
    KismetStringLibrary = "/Script/Engine.Default__KismetStringLibrary",
    KismetTextLibrary = "/Script/Engine.Default__KismetTextLibrary",
    BlueprintGameplayTagLibrary = "/Script/GameplayTags.Default__BlueprintGameplayTagLibrary",
    WidgetBlueprintLibrary = "/Script/UMG.Default__WidgetBlueprintLibrary",
    WidgetLayoutLibrary = "/Script/UMG.Default__WidgetLayoutLibrary",
    DataTableFunctionLibrary = "/Script/Engine.Default__DataTableFunctionLibrary",
    BFLSwtEngine = "/Script/SwtEngine.Default__BFLSwtEngine",
    BFLSwtQuest = "/Script/SwtQuest.Default__BFLSwtQuest",
    BFLSwtAdventure = "/Script/SwtAdventure.Default__BFLSwtAdventure",
    QuestManager = "/Script/SwtQuest.Default__QuestManager",
    SaveManager = "/Script/SwtEngine.Default__SwtSaveManager",
    GameUtil = "/Script/SwtEngine.Default__SwtGameUtil",
    QuestGameState = "/Script/SwtQuest.Default__SwtQuestGameplayGameState",
    AdventureGameState = "/Script/SwtAdventure.Default__SwtAdventureGameplayGameState",
}
Game.libraries = LIBRARIES
local libs = {}
-- The first thing a straight line from `from` to `to` ({X, Y, Z}) runs into: where it hit ({X, Y, Z}),
-- or nil if nothing is in the way.
function Game.trace(from, to)
    local hit, none = {}, { R = 0, G = 0, B = 0, A = 0 }
    local ok, found = pcall(function()
        return Game.library("KismetSystemLibrary"):LineTraceSingle(Game.player(), from, to, 0, false, {}, 0, hit, true,
                                                                   none, none, 0)
    end)
    if ok and found and hit.ImpactPoint then return { X = hit.ImpactPoint.X, Y = hit.ImpactPoint.Y, Z = hit.ImpactPoint.Z } end
    return nil
end

-- The height of the ground below a place (from 2 m above it), or nil.
function Game.ground(x, y, z)
    local hit = Game.trace({ X = x, Y = y, Z = z + 200 }, { X = x, Y = y, Z = z - 20000 })
    return hit and hit.Z or nil
end

function Game.library(name)
    local o = libs[name]
    if valid(o) then return o end
    o = Game.object(LIBRARIES[name] or name)
    libs[name] = o
    return o
end

-- ===================================================================================== the world
local pc, nextPcSearch = nil, 0
-- The player's controller, or nil (in menus, while loading).
function Game.controller()
    local ok, still = pcall(function() return valid(pc) and valid(pc.Player) end)
    if ok and still then return pc end
    pc = nil
    if os.clock() < nextPcSearch then return nil end
    nextPcSearch = os.clock() + 0.5
    for _, c in ipairs(Game.findAll("PlayerController")) do
        if valid(c.Player) then
            pc = c
            break
        end
    end
    return pc
end

-- Your cat's actor (the player's pawn) while you play, else nil.
function Game.player()
    local c = Game.controller()
    if not c then return nil end
    local ok, p = pcall(function() return c.Pawn end)
    if ok and valid(p) and Game.isA(p, "SwtAdventureCharacter") then return p end
    return nil
end

function Game.world()
    local c = Game.controller()
    if c then
        local ok, w = pcall(function() return c:GetWorld() end)
        if ok and valid(w) then return w end
    end
    local w = Game.get(Game.find("GameEngine"), "GameViewport.World")
    if valid(w) then return w end
    return nil
end

-- The level's name: "L_WorldMap_01_P" in the forest, "L_MainMenu…" and others elsewhere.
function Game.levelName()
    local w = Game.world()
    return w and Game.name(w) or nil
end

-- The game's own screens and popups showing now, by class ("WBP_GuiPopupInventory_C", the map, the
-- pause menu...); empty while you're just playing. Looked up at most four times a second.
local shownScreens, shownAt = {}, nil
function Game.screens()
    if shownAt and os.clock() - shownAt < 0.25 then return shownScreens end
    shownAt, shownScreens = os.clock(), {}
    for _, w in ipairs(Game.findAll("GuiScreenWrc")) do
        local ok, vis = pcall(function() return w:IsVisible() end)
        if ok and vis then shownScreens[#shownScreens + 1] = Game.className(w) end
    end
    return shownScreens
end

function Game.gameInstance()
    local w = Game.world()
    local ok, gi = pcall(function() return w.OwningGameInstance end)
    if ok and valid(gi) then return gi end
    return Game.find("GameInstance")
end

function Game.gameState()
    local w = Game.world()
    local ok, gs = pcall(function() return w.GameState end)
    if ok and valid(gs) then return gs end
    return nil
end

function Game.gameMode()
    local w = Game.world()
    local ok, gm = pcall(function() return w.AuthorityGameMode end)
    if ok and valid(gm) then return gm end
    return nil
end

-- The game's managers, by the property that holds each on the game instance.
Game.managers = {
    config = "GameConfig", util = "GameUtil", save = "SaveManager", gui = "GuiManager", cheats = "CheatsManager",
    flow = "FlowManager", storage = "StorageManager", services = "GameServices", analytics = "AnalyticsManager",
    online = "OnlineServicesManager", achievements = "AchievementsManager", records = "RecordsManager",
    challenges = "ChallengesManager", montages = "MontagesManager", tracer = "ActorTracerManager", vfx = "VfxManager",
    quests = "QuestManager", sequencer = "SequencerManager", tuning = "TuningManager", audio = "NativeAudioManager",
    cloud = "OnlineCloudManager", effects = "EffectManager", npcs = "NPCGenerationManager", combat = "CombatManager",
    paths = "TrackPathManager", tutorial = "TutorialManager",
}

-- One of the game's managers: Game.manager("quests"), "save", "cheats", "combat", ... (Game.managers).
function Game.manager(name)
    local prop = Game.managers[name] or name
    local gi = Game.gameInstance()
    if not gi then return nil end
    local ok, m = pcall(function() return gi[prop] end)
    if ok and valid(m) then return m end
    return nil
end

-- ===================================================================================== JSON
Game.json = {}
local NULL = setmetatable({}, { __tostring = function() return "null" end })
Game.json.null = NULL

local function encodeJson(v, depth, seen)
    local t = type(v)
    if v == nil or v == NULL then return "null" end
    if t == "boolean" then return v and "true" or "false" end
    if t == "number" then
        if v ~= v or v == math.huge or v == -math.huge then return "null" end
        if math.type(v) == "integer" then return tostring(v) end
        -- %g writes 12.0 as "12", which comes back as a whole number (and a setting then only takes whole
        -- numbers); keep it a float.
        local s = string.format("%.17g", v)
        if not s:find("[%.eE]") then s = s .. ".0" end
        return s
    end
    if t == "string" then
        return '"' .. v:gsub('[%c"\\]', function(c)
            local map = { ['"'] = '\\"', ["\\"] = "\\\\", ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }
            return map[c] or string.format("\\u%04x", c:byte())
        end) .. '"'
    end
    if t == "table" then
        depth, seen = depth or 0, seen or {}
        if seen[v] or depth > 32 then error("can't write a table that contains itself as JSON") end
        seen[v] = true
        local n, max = 0, 0
        for k in pairs(v) do
            n = n + 1
            if math.type(k) == "integer" and k > max then max = k end
        end
        local out = {}
        if (n > 0 and max == n) or getmetatable(v) == Game.json.listMeta then
            for i = 1, max do out[i] = encodeJson(v[i], depth + 1, seen) end
            seen[v] = nil
            return "[" .. table.concat(out, ",") .. "]"
        end
        local keys = {}
        for k in pairs(v) do keys[#keys + 1] = tostring(k) end
        table.sort(keys)
        for _, k in ipairs(keys) do
            local val = v[k]
            if val == nil then val = v[tonumber(k)] end
            out[#out + 1] = encodeJson(k) .. ":" .. encodeJson(val, depth + 1, seen)
        end
        seen[v] = nil
        return "{" .. table.concat(out, ",") .. "}"
    end
    return encodeJson(str(v))
end

Game.json.listMeta = {}
-- Mark a table as a JSON list, so an empty one is written [] rather than {}.
function Game.json.list(t) return setmetatable(t or {}, Game.json.listMeta) end
function Game.json.encode(v) return encodeJson(v) end

-- JSON text to Lua: objects and arrays become tables, null becomes Game.json.null.
function Game.json.decode(text)
    local pos = 1
    local function fail(what) error(string.format("bad JSON at %d: %s", pos, what)) end
    local function ws() pos = text:find("[^ \t\r\n]", pos) or #text + 1 end
    local value
    local escapes = { b = "\b", f = "\f", n = "\n", r = "\r", t = "\t", ['"'] = '"', ["\\"] = "\\", ["/"] = "/" }
    local function utf8char(cp)
        if cp < 0x80 then return string.char(cp) end
        return utf8.char(cp)
    end
    local function stringValue()
        local out, i = {}, pos + 1
        while true do
            local c = text:sub(i, i)
            if c == "" then fail("unfinished string") end
            if c == '"' then pos = i + 1 return table.concat(out) end
            if c == "\\" then
                local e = text:sub(i + 1, i + 1)
                if e == "u" then
                    local cp = tonumber(text:sub(i + 2, i + 5), 16) or fail("bad \\u escape")
                    if cp >= 0xD800 and cp <= 0xDBFF and text:sub(i + 6, i + 7) == "\\u" then
                        local lo = tonumber(text:sub(i + 8, i + 11), 16) or 0
                        cp = 0x10000 + (cp - 0xD800) * 0x400 + (lo - 0xDC00)
                        i = i + 6
                    end
                    out[#out + 1] = utf8char(cp)
                    i = i + 6
                else
                    out[#out + 1] = escapes[e] or fail("bad escape")
                    i = i + 2
                end
            else
                local j = text:find('["\\]', i) or #text + 1
                out[#out + 1] = text:sub(i, j - 1)
                i = j
            end
        end
    end
    function value()
        ws()
        local c = text:sub(pos, pos)
        if c == "{" then
            local obj = {}
            pos = pos + 1
            ws()
            if text:sub(pos, pos) == "}" then pos = pos + 1 return obj end
            while true do
                ws()
                if text:sub(pos, pos) ~= '"' then fail("expected a key") end
                local k = stringValue()
                ws()
                if text:sub(pos, pos) ~= ":" then fail("expected ':'") end
                pos = pos + 1
                obj[k] = value()
                ws()
                local d = text:sub(pos, pos)
                pos = pos + 1
                if d == "}" then return obj end
                if d ~= "," then fail("expected ',' or '}'") end
            end
        elseif c == "[" then
            local arr = Game.json.list({})
            pos = pos + 1
            ws()
            if text:sub(pos, pos) == "]" then pos = pos + 1 return arr end
            while true do
                arr[#arr + 1] = value()
                ws()
                local d = text:sub(pos, pos)
                pos = pos + 1
                if d == "]" then return arr end
                if d ~= "," then fail("expected ',' or ']'") end
            end
        elseif c == '"' then
            return stringValue()
        elseif text:sub(pos, pos + 3) == "true" then pos = pos + 4 return true
        elseif text:sub(pos, pos + 4) == "false" then pos = pos + 5 return false
        elseif text:sub(pos, pos + 3) == "null" then pos = pos + 4 return NULL
        else
            local num = text:match("^-?%d+%.?%d*[eE]?[-+]?%d*", pos)
            if not num or num == "" then fail("unexpected '" .. c .. "'") end
            pos = pos + #num
            return math.tointeger(tonumber(num)) or tonumber(num)
        end
    end
    local ok, result = pcall(value)
    if not ok then return nil, result end
    return result
end

-- ===================================================================================== scheduling
-- One game-thread loop per Lua state runs every timer, frame function and polled event.
local tasks, nextTask, started = {}, 1, false
local lastFrame = os.clock()

local function runTasks()
    local now = os.clock()
    local dt = now - lastFrame
    lastFrame = now
    for id, t in pairs(tasks) do
        if t.at == nil or now >= t.at then
            local ok, err = pcall(t.fn, dt)
            if not ok then log("%s: %s", t.what or "task", tostring(err)) end
            if t.every then
                t.at = now + t.every
            elseif t.at ~= nil then
                tasks[id] = nil
            end
        end
    end
end

local function start()
    if started then return end
    started = true
    if LoopInGameThreadAfterFrames == nil or not pcall(LoopInGameThreadAfterFrames, 1, runTasks) then
        LoopAsync(16, function()
            ExecuteInGameThread(runTasks)
            return false
        end)
    end
end

local function add(t)
    start()
    local id = nextTask
    nextTask = nextTask + 1
    tasks[id] = t
    return id
end

-- fn(dt) every frame.
function Game.onFrame(fn) return add({ fn = fn, what = "onFrame" }) end
-- fn() every `seconds`, the first time `seconds` from now.
function Game.every(seconds, fn) return add({ fn = fn, every = seconds, at = os.clock() + seconds, what = "every" }) end
-- fn() once, `seconds` from now.
function Game.after(seconds, fn) return add({ fn = fn, at = os.clock() + seconds, what = "after" }) end
-- Stop a timer, frame function or event listener.
function Game.cancel(id) tasks[id] = nil end

-- A key and what it does, for the mod menu's Overview (its list of the keys scripts use).
local function listKey(name, help)
    local line = name .. "\t" .. (tostring(help):gsub("[\t\n]", " ")) .. "\n"
    ExecuteInGameThread(function()
        local ok, list = pcall(function() return ModRef:GetSharedVariable("WCModsMenu.keys") end)
        list = ok and list or ""
        if not tostring(list):find(line, 1, true) then
            pcall(function() ModRef:SetSharedVariable("WCModsMenu.keys", tostring(list) .. line) end)
        end
    end)
end

-- fn() on the game thread when a key is pressed: Game.onKey("F6", fn) or Game.onKey("F6", fn, {"CONTROL"}).
-- With `help` ("Heal your cat"), the mod menu's Overview lists the key.
function Game.onKey(key, fn, modifiers, help)
    if help then
        local name = tostring(key)
        if modifiers and #modifiers > 0 then name = table.concat(modifiers, "+") .. "+" .. name end
        listKey(name, help)
    end
    local k = Key[key] or key
    local wrapped = function()
        ExecuteInGameThread(function()
            local ok, err = pcall(fn)
            if not ok then log("key %s: %s", tostring(key), tostring(err)) end
        end)
    end
    if modifiers and #modifiers > 0 then
        local mods = {}
        for i, m in ipairs(modifiers) do mods[i] = ModifierKey[m] or m end
        RegisterKeyBind(k, mods, wrapped)
    else
        RegisterKeyBind(k, wrapped)
    end
end

-- Whether a key or controller button went down this frame, in the game's own input: Game.pressed("T"),
-- Game.pressed("Gamepad_FaceButton_Top") (Unreal's key names). Unlike Game.onKey, it only sees keys
-- while the game has the focus, and it sees controller buttons too.
local pressKeys = {}
local function inputKey(key)
    local k = pressKeys[key]
    if not k then
        k = { KeyName = FName(key) }
        pressKeys[key] = k
    end
    return k
end
function Game.pressed(key)
    local c = Game.controller()
    if not c then return false end
    local ok, yes = pcall(function() return c:WasInputKeyJustPressed(inputKey(key)) end)
    return ok and yes == true
end
-- Whether a key or button is held down now, in the game's own input.
function Game.keyDown(key)
    local c = Game.controller()
    if not c then return false end
    local ok, yes = pcall(function() return c:IsInputKeyDown(inputKey(key)) end)
    return ok and yes == true
end

-- fn() when any of `keys` (a key name or a list: {"T", "Gamepad_DPad_Up"}) is pressed in the game, checked
-- every frame with Game.pressed. With `help`, the mod menu's Overview lists the keys. Returns an id
-- for Game.cancel.
function Game.onPress(keys, fn, help)
    if type(keys) ~= "table" then keys = { keys } end
    if help then listKey(table.concat(keys, " or "), help) end
    -- Once per press: the frame function can run twice in one game frame, while the key still reads
    -- as just pressed, so a key fires again only after it's been let go.
    local held = {}
    return Game.onFrame(function()
        for _, key in ipairs(keys) do
            if held[key] then
                if not Game.keyDown(key) then held[key] = nil end
            elseif Game.pressed(key) then
                held[key] = true
                fn(key)
                return
            end
        end
    end)
end

-- ===================================================================================== hooks
-- Run code when the game calls one of its functions: Game.hook("/Script/SwtAdventure.SwtAdventureStatusComponent:ApplyStatusType",
-- function(self, statusType) ... end). The callback gets the object and the parameters' values; it runs
-- before the function, or after it with { post = true }. Returns a handle for Game.unhook.
function Game.hook(path, fn, opts)
    opts = opts or {}
    local function call(ctx, ...)
        local params = table.pack(...)
        local values = { n = params.n }
        for i = 1, params.n do
            local p = params[i]
            local ok, v = pcall(function() return p:get() end)
            -- Not `ok and v or p`: a parameter that's false would come through as p, which is truthy.
            if ok then values[i] = v else values[i] = p end
        end
        local okSelf, self = pcall(function() return ctx:get() end)
        local ok, err = pcall(fn, okSelf and self or ctx, table.unpack(values, 1, values.n))
        if not ok then log("hook %s: %s", path, tostring(err)) end
    end
    local noop = function() end
    local ok, pre, post
    if opts.post then
        ok, pre, post = pcall(RegisterHook, path, noop, call)
    else
        ok, pre, post = pcall(RegisterHook, path, call)
    end
    if not ok then return nil, tostring(pre) end
    return { path = path, pre = pre, post = post }
end

function Game.unhook(h)
    if h then pcall(UnregisterHook, h.path, h.pre, h.post) end
end

-- The raw form, for changing a parameter before the game uses it: fn(self, params) where params[i]:get()
-- and params[i]:set(v) read and write the call's own parameters.
function Game.hookRaw(path, fn)
    local ok, pre, post = pcall(RegisterHook, path, function(ctx, ...)
        local okSelf, self = pcall(function() return ctx:get() end)
        local okCall, err = pcall(fn, okSelf and self or ctx, table.pack(...))
        if not okCall then log("hook %s: %s", path, tostring(err)) end
    end)
    if not ok then return nil, tostring(pre) end
    return { path = path, pre = pre, post = post }
end

-- ===================================================================================== events
-- Game.on(event, fn) -> id, Game.off(id). The game's own events are below; scripts can add theirs with
-- Game.emit(event, ...), which reaches listeners in the same script.
local listeners, nextListener = {}, 1
local sources = {}   -- event -> how it starts: a poller or a hook, set up on the first listener

function Game.emit(event, ...)
    for _, l in pairs(listeners[event] or {}) do
        local ok, err = pcall(l, ...)
        if not ok then log("on %s: %s", event, tostring(err)) end
    end
end

function Game.on(event, fn)
    listeners[event] = listeners[event] or {}
    local id = nextListener
    nextListener = nextListener + 1
    listeners[event][id] = fn
    local src = sources[event]
    if src and not src.started then
        src.started = true
        local ok, err = pcall(src.start)
        if not ok then log("can't watch %s: %s", event, tostring(err)) end
    end
    return { event = event, id = id }
end

function Game.off(handle)
    if handle and listeners[handle.event] then listeners[handle.event][handle.id] = nil end
end

local function poller(every, read, onChange)
    return {
        start = function()
            local last, first = nil, true
            Game.every(every, function()
                local now = read()
                if first or now ~= last then
                    local was = last
                    last, first = now, false
                    if not (was == nil and now == nil) then onChange(now, was) end
                end
            end)
        end,
    }
end

-- "level" (name, previous): the level changed.
sources.level = poller(0.5, function() return Game.levelName() end,
    function(now, was) Game.emit("level", now, was) end)

-- "player" (actor or nil): your cat appeared, changed (a new area) or went (menus).
sources.player = poller(0.25, function()
        local p = Game.player()
        return p and tostring(p:GetAddress()) or nil
    end,
    function(now) Game.emit("player", now and Game.player() or nil) end)

-- "phase" (new, old): the game state's phase (EGamePhase) changed.
sources.phase = poller(0.25, function() return Game.get(Game.gameState(), "CurrentPhase") end,
    function(now, was) Game.emit("phase", now, was) end)

-- "combatStart" (fight) / "combatEnd" (fight): a fight began or ended. fight is a Game.fight wrapper.
local function combatPoller()
    local inFight = false
    Game.every(0.25, function()
        local d = Game.combatDirector()
        local now = d ~= nil
        if now ~= inFight then
            inFight = now
            if now then Game.emit("combatStart", Game.fight(d)) else Game.emit("combatEnd") end
        end
    end)
end
sources.combatStart = { start = combatPoller }
sources.combatEnd = { start = function() if not sources.combatStart.started then sources.combatStart.started = true combatPoller() end end }

-- "genericEvent" (name): the game broadcast one of its named events (SwtGameUtil.BroadcastGenericEvent).
sources.genericEvent = { start = function()
    assert(Game.hook("/Script/SwtEngine.SwtGameUtil:BroadcastGenericEvent", function(_, name) Game.emit("genericEvent", str(name)) end))
end }

-- "questStatus" (quest, status, exact): a quest's status changed.
sources.questStatus = { start = function()
    assert(Game.hook("/Script/SwtQuest.SwtQuestGameplayGameState:OnQuestStatusChanged",
        function(_, quest, status, exact) Game.emit("questStatus", quest, status, exact) end))
end }

-- "damage" (info): a hit landed or missed in a fight. info = { target, damage, missed, stance, status }.
sources.damage = { start = function()
    assert(Game.hook("/Script/SwtAdventure.SwtAdventureCombatDirector:OnRegisterDamage", function(_, d)
        Game.emit("damage", { target = Game.get(d, "Character"), damage = Game.get(d, "Damage"),
                              missed = Game.get(d, "bMissed"), stance = Game.get(d, "StanceMultiplier"),
                              status = Game.get(d, "StatusCondition") })
    end))
end }

-- "turnEnded" (): a fighter finished its turn.
sources.turnEnded = { start = function()
    assert(Game.hook("/Script/SwtAdventure.SwtAdventureCombatDirector:OnCombatantTurnEnded", function() Game.emit("turnEnded") end))
end }

-- "status" (character, statusType): a status condition was put on a fighter.
sources.status = { start = function()
    assert(Game.hook("/Script/SwtAdventure.SwtAdventureStatusComponent:ApplyStatusType", function(comp, statusType)
        local ok, owner = Game.call(comp, "GetOwner")
        Game.emit("status", ok and owner or nil, statusType)
    end))
end }

-- ===================================================================================== the save's live data
-- The game keeps its save as JSON in memory (the save manager); these read and write it while it runs.
Game.save = {}

function Game.save.manager() return Game.manager("save") end

-- A part of the current slot's state as a Lua table (e.g. Game.save.state("Inventory")), or nil.
function Game.save.state(key)
    local sm = Game.save.manager()
    if not sm then return nil, "no save manager" end
    local ok, text = pcall(function() return sm:GetStateJsonDataAsString(key):ToString() end)
    if not ok then return nil, tostring(text) end
    if text == "" then return nil, "empty" end
    return Game.json.decode(text)
end

function Game.save.stateText(key)
    local sm = Game.save.manager()
    local ok, text = pcall(function() return sm:GetStateJsonDataAsString(key):ToString() end)
    return ok and text or nil
end

-- Replace a part of the state with a table (or JSON text).
function Game.save.setState(key, value)
    local sm = Game.save.manager()
    if not sm then return false, "no save manager" end
    local text = type(value) == "string" and value or Game.json.encode(value)
    return pcall(function() sm:SetStateJsonDataFromString(key, text) end)
end

-- Whole-number progression values (GetGameProgressionData).
function Game.save.progression(primary, sub)
    local sm = Game.save.manager()
    local ok, v = pcall(function() return sm:GetGameProgressionData(primary, sub or "") end)
    return ok and v or nil
end

function Game.save.setProgression(primary, sub, value)
    local sm = Game.save.manager()
    return pcall(function() sm:SetGameProgressionData(primary, sub or "", value) end)
end

-- Settings values (GetSettingsData).
function Game.save.setting(primary, sub)
    local sm = Game.save.manager()
    local ok, v = pcall(function() return sm:GetSettingsData(primary, sub or "") end)
    return ok and v or nil
end

function Game.save.setSetting(primary, sub, value)
    local sm = Game.save.manager()
    return pcall(function() sm:SetSettingsData(primary, sub or "", value) end)
end

-- Write the save now (the game's own Save, which it also calls at checkpoints).
function Game.save.write(context)
    local lib = Game.library("SaveManager")
    return pcall(function() lib:Save(context or "WCMods", false, false) end)
end

-- Which save slot is in use (0 for the first cat).
function Game.save.slot()
    return Game.get(Game.save.manager(), "SaveGame.CurrentSaveSlotIndex")
end

-- ===================================================================================== containers
-- A TArray or TSet the game handed back, as a Lua list (UE4SS can hand back wrappers; they're unwrapped).
local function unwrap(e)
    local ok, v = pcall(function() return e:get() end)
    if ok and v ~= nil then return v end
    return e
end
Game.unwrap = unwrap

function Game.list(container)
    local out = {}
    if container == nil then return out end
    if type(container) == "table" then
        for i, e in ipairs(container) do out[i] = unwrap(e) end
        return out
    end
    local ok = pcall(function() container:ForEach(function(_, e) out[#out + 1] = unwrap(e) end) end)
    if not ok or #out == 0 then
        pcall(function()
            for i = 1, #container do out[i] = unwrap(container[i]) end
        end)
    end
    return out
end

-- A TMap as a Lua table. Keys become strings: gameplay tags by name, names and texts by their text,
-- objects by their full name. Game.map(pickup.Reward) -> { ["Gameplay.Inventory.Materials.Moss"] = 3 }.
local function keyText(k)
    if type(k) ~= "userdata" then return k end
    local ok, tag = pcall(function() return k.TagName end)
    if ok and tag ~= nil then return str(tag) end
    ok, tag = pcall(function() return k.KeyName end)
    if ok and tag ~= nil then return str(tag) end
    local s = Game.fullName(k)
    if s then return s end
    return str(k)
end
Game.keyText = keyText

function Game.map(m)
    local out = {}
    if m == nil then return out end
    pcall(function() m:ForEach(function(k, v) out[keyText(unwrap(k))] = unwrap(v) end) end)
    return out
end

-- Replace a TMap<FGameplayTag, int32> (like a pickup's Reward) with { tagName = count }.
function Game.setTagCounts(m, counts)
    return pcall(function()
        m:Empty()
        for name, n in pairs(counts) do m:Add(Game.tag(name), n) end
    end)
end

-- ===================================================================================== reflection
-- What an object holds, for exploring the game: Game.properties(o) -> { {name, type, owner, value}, ... }
-- from its class down to Object (or Actor/ActorComponent, unless all is true). value is the live
-- value: a number, string or boolean, or a userdata (an object, struct, array or map).
local STOP = { Object = true, Actor = true, ActorComponent = true, SceneComponent = true, UserWidget = true, Widget = true }

function Game.properties(o, all)
    local out = {}
    if not valid(o) then return out end
    local ok, cls = pcall(function() return o:GetClass() end)
    if not ok then return out end
    while valid(cls) do
        local cname = cls:GetFName():ToString()
        if not all and STOP[cname] then break end
        pcall(function()
            cls:ForEachProperty(function(p)
                local name = p:GetFName():ToString()
                local okT, t = pcall(function() return p:GetClass():GetFName():ToString() end)
                local okV, v = pcall(function() return o[name] end)
                if not okV then v = nil end   -- (not `okV and v or nil`, which turns false into nil)
                out[#out + 1] = { name = name, type = okT and t or "?", owner = cname, value = v }
            end)
        end)
        -- The members mapped from the reverse-engineering notes (Game.hidden) don't show up in the class's
        -- own list, so they're added here.
        for _, d in ipairs(Game.hiddenByClass and Game.hiddenByClass[cname] or {}) do
            local okV, v = pcall(function() return o[d[1]] end)
            if not okV then v = nil end
            out[#out + 1] = { name = d[1], type = d[3], owner = cname .. " (mapped)", value = v, mapped = true }
        end
        if cname == "Object" then break end
        cls = cls:GetSuperStruct()
    end
    return out
end

-- The functions an object's class has: Game.functions(o) -> { {name, owner, params = {{name, type, out}}, returns}, ... }.
function Game.functions(o, all)
    local out = {}
    if not valid(o) then return out end
    local ok, cls = pcall(function() return o:GetClass() end)
    if not ok then return out end
    while valid(cls) do
        local cname = cls:GetFName():ToString()
        if not all and STOP[cname] then break end
        pcall(function()
            cls:ForEachFunction(function(fn)
                local entry = { name = fn:GetFName():ToString(), owner = cname, params = {} }
                pcall(function()
                    fn:ForEachProperty(function(p)
                        local pname = p:GetFName():ToString()
                        local okT, t = pcall(function() return p:GetClass():GetFName():ToString() end)
                        local okR, isReturn = pcall(function() return p:HasAnyPropertyFlags(0x400) end)
                        local okO, isOut = pcall(function() return p:HasAnyPropertyFlags(0x100) end)
                        if okR and isReturn then
                            entry.returns = okT and t or "?"
                        else
                            entry.params[#entry.params + 1] = { name = pname, type = okT and t or "?", out = okO and isOut or false }
                        end
                    end)
                end)
                out[#out + 1] = entry
            end)
        end)
        if cname == "Object" then break end
        cls = cls:GetSuperStruct()
    end
    return out
end

-- A short readable form of any value, for showing it (the inspector, the bridge).
function Game.show(v, depth)
    depth = depth or 0
    local t = type(v)
    if v == nil then return "nil" end
    if t ~= "userdata" then
        if t == "table" and depth < 2 then
            local parts, n = {}, 0
            for k, x in pairs(v) do
                n = n + 1
                if n > 8 then parts[#parts + 1] = "…" break end
                parts[#parts + 1] = tostring(k) .. "=" .. Game.show(x, depth + 1)
            end
            return "{" .. table.concat(parts, ", ") .. "}"
        end
        return tostring(v)
    end
    local full = Game.fullName(v)
    if full then return full end
    if dead(v) then return "<gone>" end
    local ok, s = pcall(function() return v:ToString() end)
    if ok and type(s) == "string" then return s end
    ok, s = pcall(function() return v.TagName end)
    if ok and s ~= nil then return str(s) end
    return tostring(v)
end

-- ===================================================================================== hidden values
-- Members the game doesn't reflect, mapped from the reverse-engineering notes (docs/mechanics/) with
-- UE4SS's RegisterCustomProperty. Each becomes a property named WCM_<name> on its class.
Game.hidden = @HIDDEN@

-- The same, by short class name ("SwtQuestResourceComponent"), for listing them.
Game.hiddenByClass = {}
for path, list in pairs(Game.hidden) do Game.hiddenByClass[path:match("%.([%w_]+)$")] = list end

local hiddenDone = false
local function registerHidden()
    if hiddenDone then return end
    hiddenDone = true
    for cls, list in pairs(Game.hidden) do
        for _, d in ipairs(list) do
            -- Registering twice (another script did) is harmless; the property is already there.
            pcall(RegisterCustomProperty, { Name = d[1], Type = PropertyTypes[d[3]], BelongsToClass = cls,
                                            OffsetInternal = d[2] })
        end
    end
end
registerHidden()

-- ===================================================================================== enums
-- The game's enums, as name -> number (Game.enums.status.Poisoned == 3) and number -> name.
local function enum(names, first)
    local e, n = {}, first or 0
    for _, name in ipairs(names) do
        e[name], e[n] = n, name
        n = n + 1
    end
    return e
end
Game.enums = {
    clan = enum({ "None", "ThunderClan", "ShadowClan", "RiverClan", "WindClan" }),
    rank = enum({ "None", "Apprentice", "Warrior", "Deputy", "Leader" }),
    trait = enum({ "None", "Brave", "Ambitious", "Wise", "Energetic", "Curious", "Patient" }),
    stance = enum({ "None", "Neutral", "Offensive", "Defensive", "Trick", "Sneaky", "Reckless" }),
    status = enum({ "None", "Blinded", "Furious", "Poisoned", "Stressed" }),
    stat = enum({ "None", "Prowess", "Strength", "Resilience", "Instinct", "Agility" }),
    resource = enum({ "Health", "Level", "Stamina", "StaminaCombat", "Currency", "FreshKill" }),
    questStatus = enum({ "None", "QuestAvailable", "OngoingQuest", "QuestComplete", "QuestTurnedIn", "DialogueProgress" }),
    questResult = enum({ "Any", "Success", "Fail" }),
    questType = enum({ "MainQuest", "SideQuest" }),
    objectiveStatus = enum({ "NotStarted", "InProgress", "Failed", "FailedTimePressure", "Succeeded" }),
    phase = enum({ "None", "PreCinematic", "CinematicIntro", "PreGame", "Game", "PostGame", "TutorialIntro" }),
    itemType = enum({ "None", "Consumable", "Equipment", "Quest", "Collectible" }),
    characterType = enum({ "None", "Cat", "BossCat", "WeakMice", "Mice", "WeakSquirrel", "Squirrel", "WeakRabbit", "Rabbit",
                          "BossRabbit", "WeakBird", "Bird", "WeakRat", "Rat", "Snake", "ThreatSnake", "BossSnake", "Badger",
                          "ThreatBadger", "BossBadger", "ThreatFox", "TitanFox", "BossFox", "ThreatDog", "TitanDog", "BossDog" }),
}
local function enumValue(e, v)
    if type(v) == "string" then return e[v] end
    return v
end

-- ===================================================================================== the save file
-- The game writes its save as plain JSON too (WrcGame.json, next to WrcGame.sav) every time it saves.
function Game.save.path()
    local base = os.getenv("LOCALAPPDATA") or ""
    return base .. "\\Wrc\\Saved\\SaveGames\\WrcGame.json"
end

local fileCache = { at = -1, data = nil }
-- The whole save as of the game's last save, as a table (cached for a second).
function Game.save.file()
    if fileCache.data and os.clock() - fileCache.at < 1 then return fileCache.data end
    local f = io.open(Game.save.path(), "rb")
    if not f then return nil, "no save file" end
    local text = f:read("a")
    f:close()
    local data, err = Game.json.decode(text)
    if not data then return nil, err end
    fileCache.at, fileCache.data = os.clock(), data
    return data
end

-- This cat's slot in the last save: GameplayProgression, NPCData, QuestProgression...
function Game.save.slotData()
    local data, err = Game.save.file()
    if not data then return nil, err end
    local account = select(2, next(data))
    if type(account) ~= "table" then return nil, "no account" end
    local slot = Game.save.slot() or 0
    return account[tostring(slot)], account
end

-- ===================================================================================== your cat and others
local Cat = {}
Cat.__index = Cat
Game.Cat = Cat

-- A cat (or any fighter): Game.cat() is yours; Game.cat(actor) wraps another.
function Game.cat(actor)
    actor = actor or Game.player()
    if not valid(actor) then return nil end
    return setmetatable({ actor = actor }, Cat)
end

function Cat:valid() return valid(self.actor) end
function Cat:isPlayer() return self.actor == Game.player() or (Game.player() and self.actor:GetAddress() == Game.player():GetAddress()) end

-- The resource component of a kind: "Health", "Stamina", "StaminaCombat" (on the cat), "Level" (on the
-- player state, for your cat).
local COMPONENT_CLASS = { Health = "SwtQuestHealthComponent", Stamina = "SwtQuestStaminaComponent",
                          StaminaCombat = "SwtCombatStaminaComponent", Level = "SwtAdventureLevelComponent" }
function Cat:component(kind)
    local cls = COMPONENT_CLASS[kind] or kind
    local owner = self.actor
    if kind == "Level" then owner = Game.get(self.actor, "Controller.PlayerState") or Game.get(Game.controller(), "PlayerState") end
    if not valid(owner) then return nil end
    local clsObj = Game.object(self._classPath(cls))
    if clsObj then
        local ok, c = pcall(function() return owner:GetComponentByClass(clsObj) end)
        if ok and valid(c) then return c end
    end
    for _, comp in ipairs(Game.findAll(cls)) do
        local okO, o = pcall(function() return comp:GetOwner() end)
        if okO and valid(o) and o:GetAddress() == owner:GetAddress() then return comp end
    end
    return nil
end

local CLASS_PATHS = {
    SwtQuestHealthComponent = "/Script/SwtQuest.SwtQuestHealthComponent",
    SwtQuestStaminaComponent = "/Script/SwtQuest.SwtQuestStaminaComponent",
    SwtCombatStaminaComponent = "/Script/SwtAdventure.SwtCombatStaminaComponent",
    SwtAdventureLevelComponent = "/Script/SwtAdventure.SwtAdventureLevelComponent",
}
function Cat._classPath(name) return CLASS_PATHS[name] or name end

local function resource(cat, kind, field)
    local c = cat:component(kind)
    return c and Game.get(c, field) or nil
end
local function setResource(cat, kind, field, v)
    local c = cat:component(kind)
    if not c then return false, "no " .. kind .. " component" end
    return Game.set(c, field, v)
end

function Cat:health() return resource(self, "Health", "WCM_Value") end
function Cat:maxHealth() return resource(self, "Health", "WCM_Max") end
function Cat:setHealth(v) return setResource(self, "Health", "WCM_Value", v) end
function Cat:setMaxHealth(v) return setResource(self, "Health", "WCM_Max", v) end
-- Full health; false when the game's maximum isn't known (a game update moved it where wcmods can't find it).
function Cat:heal()
    local max = self:maxHealth()
    if max == nil then return false end
    return self:setHealth(max)
end
function Cat:stamina() return resource(self, "Stamina", "WCM_Value") end
function Cat:maxStamina() return resource(self, "Stamina", "WCM_Max") end
function Cat:setStamina(v) return setResource(self, "Stamina", "WCM_Value", v) end
function Cat:setMaxStamina(v) return setResource(self, "Stamina", "WCM_Max", v) end
function Cat:staminaRegen() return resource(self, "Stamina", "WCM_Regen") end
function Cat:setStaminaRegen(v) return setResource(self, "Stamina", "WCM_Regen", v) end
function Cat:combatStamina() return resource(self, "StaminaCombat", "WCM_Value") end
function Cat:maxCombatStamina() return resource(self, "StaminaCombat", "WCM_Max") end
function Cat:setCombatStamina(v) return setResource(self, "StaminaCombat", "WCM_Value", v) end

-- Level and experience (your cat: the player state's level component).
function Cat:level() return resource(self, "Level", "WCM_Level") end
function Cat:setLevel(n) return setResource(self, "Level", "WCM_Level", n) end
function Cat:xp() return resource(self, "Level", "WCM_Value") end
function Cat:setXp(v) return setResource(self, "Level", "WCM_Value", v) end
function Cat:xpNeeded() return resource(self, "Level", "WCM_Max") end

local STATS = { "Prowess", "Strength", "Resilience", "Instinct", "Agility", "Stamina" }
Game.statNames = STATS
-- Your cat's stats: { Prowess, Strength, Resilience, Instinct, Agility, Stamina } (from the level
-- component; in a fight the fighter's own copy is Game.fighter(cat):stats()).
function Cat:stats()
    local c = self:component("Level")
    if not c then return nil end
    local out = {}
    for _, s in ipairs(STATS) do out[s] = Game.get(c, "WCM_" .. s) end
    return out
end
function Cat:setStat(name, v)
    local c = self:component("Level")
    if not c then return false, "no level component" end
    return Game.set(c, "WCM_" .. name, v)
end

-- The cat's looks and name IDs (its customisation data, the same fields the save keeps).
Cat.lookFields = { "ClanType", "BodyOffset", "FaceOffset", "EarOffset", "BodyValue", "FaceValue", "FurValue", "EyeValue",
                   "WhiskerValue", "TailIdx", "EarIdx", "FurIdx", "FurColorIdx", "Pattern01ColorIdx", "Pattern02ColorIdx",
                   "PatternIdx", "MarkingIdx", "EyeLeftColorIdx", "EyeRightColorIdx", "PrefixNameId", "SuffixNameId",
                   "CatSize", "Gender" }
function Cat:customization()
    local d = Game.get(self.actor, "MeshCustomizationComponent.CustomData")
    if d == nil then return nil end
    local out = {}
    for _, f in ipairs(Cat.lookFields) do
        local ok, v = pcall(function() return d[f] end)
        if ok and v ~= nil then out[f] = type(v) == "userdata" and str(v) or v end
    end
    return out
end
function Cat:clan()
    local look = self:customization()
    return look and Game.enums.clan[look.ClanType] or nil
end

local okNames, NAMES = pcall(require, "WCModsNames")
if not okNames or type(NAMES) ~= "table" or not NAMES.name then NAMES = { name = function() return nil end } end
-- The cat's name as the game shows it ("Otterpaw"), from its name IDs and your name mods, or the game's
-- own text when wcmods couldn't read its name tables at install (WCModsNames).
function Cat:name()
    local look = self:customization()
    if not look then return nil end
    return NAMES.name(look.PrefixNameId or "", look.SuffixNameId or "")
end

-- Your cat's personality traits from the last save: { "Brave", "Energetic" }.
function Cat:traits()
    local slot = Game.save.slotData()
    local list = slot and Game.get(slot, "GameplayProgression.Traits") or nil
    local out = {}
    for _, t in ipairs(type(list) == "table" and list or {}) do out[#out + 1] = Game.enums.trait[t.Type] or t.Type end
    return out
end

function Cat:location()
    if not valid(self.actor) then return nil end
    local ok, l = pcall(function() return self.actor:K2_GetActorLocation() end)
    if not ok then return nil end
    return { X = l.X, Y = l.Y, Z = l.Z }
end
-- Move the cat: cat:teleport(x, y, z), cat:teleport({X, Y, Z}) or cat:teleport(anotherActor).
function Cat:teleport(x, y, z)
    if not valid(self.actor) then return false, "the cat is gone" end
    local to
    if type(x) == "number" then to = { X = x, Y = y, Z = z }
    elseif type(x) == "table" then to = x
    else
        if not valid(x) then return false, "not a place" end
        local ok, l = pcall(function() return x:K2_GetActorLocation() end)
        if not ok then return false, "not a place" end
        to = { X = l.X, Y = l.Y, Z = l.Z + 50 }
    end
    return pcall(function() self.actor:K2_TeleportTo(to, self.actor:K2_GetActorRotation()) end)
end
function Cat:scale()
    if not valid(self.actor) then return nil end
    local ok, s = pcall(function() return self.actor:GetActorScale3D() end)
    return ok and s.X or nil
end
-- The cat's size, as the mod menu's size cheat does it (the actor's scale).
function Cat:setScale(f)
    if not valid(self.actor) then return false, "the cat is gone" end
    return pcall(function() self.actor:SetActorScale3D({ X = f, Y = f, Z = f }) end)
end
-- Time runs faster (2) or slower (0.5) for this cat alone.
function Cat:setTimeDilation(f) return Game.set(self.actor, "CustomTimeDilation", f) end

-- Status conditions (Blinded, Furious, Poisoned, Stressed), mostly for fights.
function Cat:statusComponent() return Game.get(self.actor, "StatusConditionComponent") end
function Cat:applyStatus(s) return Game.call(self:statusComponent(), "ApplyStatusType", enumValue(Game.enums.status, s)) end
function Cat:removeStatus(s) return Game.call(self:statusComponent(), "RemoveStatusType", enumValue(Game.enums.status, s)) end
function Cat:clearStatus() return Game.call(self:statusComponent(), "ClearStatusType") end

-- What the cat is: "Cat", "Mice", "BossFox", ... (ESwtQuestCharacterType).
function Cat:kind() return Game.enums.characterType[Game.get(self.actor, "CharacterType")] end
-- What it drops when beaten: { tagName = count } (writable with cat:setRewards).
function Cat:rewards() return Game.map(Game.get(self.actor, "rewards")) end
function Cat:setRewards(counts) return Game.setTagCounts(Game.get(self.actor, "rewards"), counts) end

-- ===================================================================================== items
Game.items = {}
local live = {}   -- tag -> total, from the HUD's pickup messages since the script started

-- Your items: { tagName = count } as of the game's last save, with any pickups since then.
function Game.items.list()
    local out = {}
    local slot = Game.save.slotData()
    local inv = slot and Game.get(slot, "GameplayProgression.State.Inventory")
    if type(inv) == "table" then
        for k, v in pairs(inv) do out[k] = v end
    end
    for k, v in pairs(live) do out[k] = v end
    return out
end

function Game.items.count(tag) return Game.items.list()[tag] or 0 end

local pickupWatch = false
local function watchPickups()
    if pickupWatch then return end
    pickupWatch = true
    Game.hook("/Script/Wrc.GuiHudWrc:OnItemPickedUp", function(_, tag, quantity, total)
        local name = Game.tagName(tag)
        live[name] = total
        Game.emit("itemPickedUp", name, quantity, total)
    end)
end
watchPickups()

-- What the game knows about an item (its stats row), or nil.
function Game.items.info(tag)
    local qm = Game.manager("quests")
    local row = {}
    local ok, found = pcall(function() return qm:GetItemStatsDataFromTag(Game.tag(tag), row) end)
    if ok and found then return row end
    return nil
end
function Game.items.type(tag)
    local qm = Game.manager("quests")
    local ok, t = pcall(function() return qm:GetItemType(Game.tag(tag)) end)
    return ok and Game.enums.itemType[t] or nil
end

local PICKUPS = "/Game/Gameplay/Blueprints/WorldElements/Pickups/"
-- Put a pickup holding `count` of an item on the ground (by your cat, or at `where`), for the cat to
-- pick up the usual way: Game.items.drop("Gameplay.Inventory.Materials.Moss", 5). Returns the actor.
function Game.items.drop(tag, count, where)
    count = count or 1
    local short = tag:match("%.([%w]+)$") or "SmallHealingHerb"
    local cls = Game.object(PICKUPS .. "BP_Pickup_" .. short .. ".BP_Pickup_" .. short .. "_C")
    if not cls then
        pcall(LoadAsset, PICKUPS .. "BP_Pickup_SmallHealingHerb")
        cls = Game.object(PICKUPS .. "BP_Pickup_SmallHealingHerb.BP_Pickup_SmallHealingHerb_C")
    end
    if not cls then return nil, "no pickup class loaded" end
    local at = where or (Game.cat() and Game.cat():location())
    if at ~= nil and type(at) ~= "table" then at = Game.cat(at) and Game.cat(at):location() end
    if not at then return nil, "nowhere to put it" end
    local xf = { Translation = { X = at.X + 60, Y = at.Y, Z = at.Z }, Rotation = { X = 0, Y = 0, Z = 0, W = 1 },
                 Scale3D = { X = 1, Y = 1, Z = 1 } }
    local gs = Game.library("GameplayStatics")
    local ok, a = pcall(function() return gs:BeginDeferredActorSpawnFromClass(Game.player() or Game.world(), cls, xf, 1, nil, 0) end)
    if not ok or not valid(a) then return nil, ok and "couldn't spawn" or tostring(a) end
    pcall(function()
        a.bUseSaveData = false
        a.bUseUniqueIDPersistence = false
    end)
    pcall(function() gs:FinishSpawningActor(a, xf, 0) end)
    Game.setTagCounts(a.Reward, { [tag] = count })
    return a
end

-- ===================================================================================== cats of a mod's own
-- A cat of a mod's own, standing in the world: one of the game's clan cats (its "filler" class) with the
-- colours, eyes, size and name IDs a mod gives it. wcmods keeps it where it was put: it's spawned again
-- when the game unloads it (a level change, a far-off area), and its colours go back on when the game
-- sets it up again.
--   local npc = Game.npcs.spawn({ at = { -60040, -200, 813 }, yaw = 180, size = 0.9, eyes = 15,
--       colours = { fur = "#8c919e", pattern = "#33363f", markings = "#f2f2f7" } })
--   if npc:near(300) then ... end   -- your cat is within 3 m
Game.npcs = {}
local NPC_CLASS = "/Game/Gameplay/Blueprints/Quest/Givers/BP_Quest_Filler.BP_Quest_Filler_C"
local NPC_PARAMS = { fur = "Fur Color", pattern = "Pattern Mask Color", markings = "Markings Mask Color",
                     nose = "Nose Color", paws = "Paws Color", whiskers = "Whiskers Color", ears = "Ears Color" }
local NPC_MESHES = { "SkeletalMeshComponent", "Fur", "Tail", "Ears" }
local npcs = {}
local Npc = {}
Npc.__index = Npc
local npcWatch          -- the timer that keeps them in the world, started by the first spawn
local GARBAGE = 0x00200000   -- EInternalObjectFlags::Garbage: destroyed, though still valid to UE4SS until collected

-- Whether the cat's actor is in the world (not destroyed, by a script or the level it was in going away).
local function alive(a)
    if not valid(a) then return false end
    local ok, gone = pcall(function() return a:HasAnyInternalFlags(GARBAGE) end)
    return not (ok and gone)
end

-- "#rrggbb" as the linear colour a material takes, or nil.
local function linearColour(hex)
    local r, g, b = tostring(hex):match("^#?(%x%x)(%x%x)(%x%x)$")
    if not r then return nil end
    local function lin(c)
        c = tonumber(c, 16) / 255
        return c <= 0.04045 and c / 12.92 or ((c + 0.055) / 1.055) ^ 2.4
    end
    return { R = lin(r), G = lin(g), B = lin(b), A = 1.0 }
end

local function npcClass()
    local cls = Game.object(NPC_CLASS)
    if not cls then
        pcall(LoadAsset, NPC_CLASS:match("^[^.]+"))
        cls = Game.object(NPC_CLASS)
    end
    return cls
end

-- Put the colours and eyes on the cat's materials; true if any had to change (the game had set its own).
local function paintNpc(n)
    local changed = false
    for _, field in ipairs(NPC_MESHES) do
        local ok, mesh = pcall(function() return n.actor[field] end)
        if ok and valid(mesh) then
            for i = 0, mesh:GetNumMaterials() - 1 do
                local mat = mesh:GetMaterial(i)
                if valid(mat) and mat:GetClass():GetFName():ToString() == "MaterialInstanceDynamic" then
                    local have = {}
                    pcall(function()
                        mat.VectorParameterValues:ForEach(function(_, e)
                            local v = e:get()
                            have[v.ParameterInfo.Name:ToString()] = v.ParameterValue
                        end)
                        mat.ScalarParameterValues:ForEach(function(_, e)
                            local v = e:get()
                            have[v.ParameterInfo.Name:ToString()] = v.ParameterValue
                        end)
                    end)
                    for param, want in pairs(n.paint) do
                        local cur = have[param]
                        if cur ~= nil then
                            if type(want) == "number" then
                                if math.abs(cur - want) > 0.01 then
                                    mat:SetScalarParameterValue(FName(param), want)
                                    changed = true
                                end
                            elseif math.abs(cur.R - want.R) > 0.002 or math.abs(cur.G - want.G) > 0.002
                                or math.abs(cur.B - want.B) > 0.002 then
                                mat:SetVectorParameterValue(FName(param), want)
                                changed = true
                            end
                        end
                    end
                end
            end
        end
    end
    return changed
end

-- Put a cat's feet (its body's origin) on the ground at height g: the game's cats don't fall, so one
-- placed at another cat's middle, or above a slope, would float.
local function standOn(a, g)
    if not g then return end
    local mesh = a.SkeletalMeshComponent
    if not valid(mesh) then return end
    local feet = mesh:K2_GetComponentLocation().Z
    if math.abs(g - feet) < 1 or math.abs(g - feet) > 500 then return end   -- there already, or a trace gone wrong
    local l = a:K2_GetActorLocation()
    a:K2_SetActorLocation({ X = l.X, Y = l.Y, Z = l.Z + g - feet }, false, {}, true)
end

local function spawnNpc(n)
    if n.level and Game.levelName() ~= n.level then return false end
    if not Game.player() then return false end
    n.level = n.level or Game.levelName()      -- the level it first appears in, unless it was given one
    -- The ground, found before the cat is there to be found instead.
    local g = n.ground ~= false and Game.ground(n.at.X, n.at.Y, n.at.Z) or nil
    local cls = npcClass()
    local world = Game.player() or Game.world()
    if not cls or not world then return false end
    local q = { X = 0, Y = 0, Z = 0, W = 1 }
    pcall(function()
        local r = Game.library("KismetMathLibrary"):Conv_RotatorToQuaternion(Game.rotator(0, n.yaw, 0))
        q = { X = r.X, Y = r.Y, Z = r.Z, W = r.W }
    end)
    local xf = { Translation = n.at, Rotation = q, Scale3D = { X = 1, Y = 1, Z = 1 } }
    local gs = Game.library("GameplayStatics")
    local ok, a = pcall(function() return gs:BeginDeferredActorSpawnFromClass(world, cls, xf, 1, nil, 0) end)
    if not ok or not valid(a) then return false end
    pcall(function()
        -- Not one of the save's cats: no unique ID for the save to keep it by.
        local ids = a:K2_GetComponentsByClass(Game.object("/Script/SwtAdventure.SwtAdventureIUIDComponent"))
        for i = 1, #ids do ids[i]:get().bIsEnabled = false end
    end)
    pcall(function()
        local d = a.DefaultCustomData
        if n.size then d.CatSize = n.size end
        if n.prefix then d.PrefixNameId = n.prefix end
        if n.suffix then d.SuffixNameId = n.suffix end
    end)
    pcall(function() gs:FinishSpawningActor(a, xf, 0) end)
    pcall(standOn, a, g)
    n.actor = a
    n.spawns = n.spawns + 1
    paintNpc(n)
    return true
end

-- A new cat of the mod's own at `at` ({x, y, z} or {X =, Y =, Z =}), facing `yaw` degrees. Options:
-- colours = {fur, pattern, markings, nose, paws, whiskers, ears} as "#rrggbb"; eyes = an iris colour
-- slot (0-24, as in palette.json); size (the game's cats are about 0.4-1.1); prefix and suffix = name
-- IDs ("STR_CAT_NAME1", "_PAW") for the game's own name for it; level = the level it stands in
-- ("L_WorldMap_01_P" is the forest; by default the one it first appears in). Returns the npc, which
-- appears whenever you're in its level.
function Game.npcs.spawn(opts)
    opts = opts or {}
    local at = opts.at or {}
    local n = setmetatable({
        at = { X = at.X or at[1] or 0, Y = at.Y or at[2] or 0, Z = at.Z or at[3] or 0 },
        yaw = opts.yaw or 0, size = opts.size, prefix = opts.prefix, suffix = opts.suffix,
        level = opts.level, ground = opts.ground, paint = {}, spawns = 0, removed = false,
    }, Npc)
    for part, hex in pairs(opts.colours or {}) do
        local param, c = NPC_PARAMS[part], linearColour(hex)
        if param and c then n.paint[param] = c end
    end
    if opts.eyes then
        n.paint["IndexIrisColorCurveLeft"] = opts.eyes + 1      -- row 0 of the eye atlas is the eye's white
        n.paint["IndexIrisColorCurveRight"] = opts.eyes + 1
    end
    npcs[#npcs + 1] = n
    if Game.player() then pcall(spawnNpc, n) end
    -- Keep every cat in the world, with its colours.
    npcWatch = npcWatch or Game.every(0.5, function()
        if not Game.player() then return end
        for _, c in ipairs(npcs) do
            if not c.removed then
                if alive(c.actor) then pcall(paintNpc, c) else pcall(spawnNpc, c) end
            end
        end
    end)
    return n
end

-- Every cat spawned by this script (removed ones too, with npc.removed set).
function Game.npcs.all() return npcs end

-- The cat's actor while it's in the world, else nil.
function Npc:actorOrNil() return alive(self.actor) and self.actor or nil end
function Npc:valid() return self:actorOrNil() ~= nil end
-- Where it stands ({X, Y, Z}).
function Npc:location()
    local a = self:actorOrNil()
    if a then
        local ok, l = pcall(function() return a:K2_GetActorLocation() end)
        if ok then return { X = l.X, Y = l.Y, Z = l.Z } end
    end
    return self.at
end
-- How far your cat is, in cm (nil without one).
function Npc:distance()
    local me = Game.cat()
    if not me then return nil end
    local a, b = me:location(), self:location()
    if not a then return nil end
    return math.sqrt((a.X - b.X) ^ 2 + (a.Y - b.Y) ^ 2 + (a.Z - b.Z) ^ 2)
end
-- Whether your cat is within `radius` cm (300 by default).
function Npc:near(radius)
    local d = self:distance()
    return d ~= nil and d <= (radius or 300)
end
-- Turn to face a place ({X, Y, Z}) or an actor; your cat with no argument.
function Npc:face(target)
    local a = self:actorOrNil()
    if not a then return false end
    local to = target
    if to == nil then to = Game.cat() and Game.cat():location() end
    if type(to) == "userdata" then
        local ok, l = pcall(function() return to:K2_GetActorLocation() end)
        to = ok and l or nil
    end
    if not to then return false end
    local from = self:location()
    self.yaw = math.deg(math.atan(to.Y - from.Y, to.X - from.X))
    return pcall(function() a:K2_SetActorRotation(Game.rotator(0, self.yaw, 0), false) end)
end
-- Move it, and where it comes back to.
-- Move it, and where it comes back to; it stands on the ground there. The same cat moves, so it keeps its
-- look (spawning it again lets the game choose its patterns again).
function Npc:moveTo(x, y, z)
    if type(x) == "table" then x, y, z = x.X or x[1], x.Y or x[2], x.Z or x[3] end
    self.at = { X = x, Y = y, Z = z }
    local a = self:actorOrNil()
    if not a then return end
    local g = self.ground ~= false and Game.ground(x, y, z) or nil
    pcall(function() a:K2_SetActorLocation(self.at, false, {}, true) end)
    pcall(standOn, a, g)
end

-- A place for a cat beside yours: `distance` cm away (220 by default), `side` degrees round from where
-- your cat faces (-60, to its front left; the other side and behind if that's blocked), stopped short of
-- anything in the way. Returns the place ({X, Y, Z}) and a yaw that faces your cat, or nil.
function Game.npcs.spot(distance, side)
    local me = Game.cat()
    if not me then return nil end
    local l = me:location()
    if not l then return nil end
    local facing = 0
    pcall(function() facing = me.actor:K2_GetActorRotation().Yaw end)
    distance, side = distance or 220, side or -60
    local best, bestRoom
    for _, turn in ipairs({ side, -side, 180 }) do
        local r = math.rad(facing + turn)
        local dx, dy = math.cos(r), math.sin(r)
        local from = { X = l.X + dx * 40, Y = l.Y + dy * 40, Z = l.Z + 20 }   -- from outside your cat
        local hit = Game.trace(from, { X = l.X + dx * distance, Y = l.Y + dy * distance, Z = l.Z + 20 })
        -- Room for the cat: 60 cm short of what's in the way.
        local room = hit and math.sqrt((hit.X - l.X) ^ 2 + (hit.Y - l.Y) ^ 2) - 60 or distance
        if not bestRoom or room > bestRoom then best, bestRoom = { dx, dy }, room end
        if room >= distance * 0.6 then break end
    end
    local d = math.max(80, math.min(distance, bestRoom))
    local at = { X = l.X + best[1] * d, Y = l.Y + best[2] * d, Z = l.Z }
    return at, math.deg(math.atan(l.Y - at.Y, l.X - at.X))
end
-- Take it out of the world for good.
function Npc:remove()
    self.removed = true
    local a = self:actorOrNil()
    if a then pcall(function() a:K2_DestroyActor() end) end
    self.actor = nil
end


-- ===================================================================================== the fresh-kill pile
Game.freshKill = {}
function Game.freshKill.component() return Game.get(Game.gameState(), "FreshKillPileComponent") end
function Game.freshKill.value() return Game.get(Game.freshKill.component(), "WCM_Value") end
function Game.freshKill.max() return Game.get(Game.freshKill.component(), "WCM_Max") end
function Game.freshKill.set(v) return Game.set(Game.freshKill.component(), "WCM_Value", v) end
-- Seconds since the pile last went down, and how often it does (90 s in TuningData).
function Game.freshKill.timer() return Game.get(Game.freshKill.component(), "WCM_DecayTimer") end
function Game.freshKill.decayTime() return Game.get(Game.freshKill.component(), "WCM_DecayTime") end
function Game.freshKill.setDecayTime(v) return Game.set(Game.freshKill.component(), "WCM_DecayTime", v) end
-- Full, Abundant, Good, Scarcity or Critical (the thresholds in docs/mechanics/clan-life.md).
function Game.freshKill.level()
    local v = Game.freshKill.value()
    if not v then return nil end
    if v >= 90 then return "Full" elseif v >= 70 then return "Abundant" elseif v >= 50 then return "Good"
    elseif v >= 25 then return "Scarcity" else return "Critical" end
end

-- ===================================================================================== time of day
Game.time = {}
-- The clock: hours, minutes, seconds.
function Game.time.get()
    local gs = Game.gameState()
    if not gs then return nil end
    local t = {}
    local ok = pcall(function() gs:GetDayClockTime(t, t, t) end)
    if not ok then return nil end
    return t.Hours, t.Minutes, t.Seconds
end
-- Seconds into the day (0 at midnight, 21600 at 6:00).
function Game.time.seconds() return Game.get(Game.gameState(), "WCM_DayTime") end
function Game.time.setSeconds(s) return Game.set(Game.gameState(), "WCM_DayTime", s % 86400) end
function Game.time.set(h, m, s) return Game.time.setSeconds((h or 0) * 3600 + (m or 0) * 60 + (s or 0)) end

-- ===================================================================================== quests
Game.quests = {}
function Game.quests.manager() return Game.manager("quests") end

-- A quest object's state as a table: { quest, type, status, result, tracked, xp, rewards }.
function Game.quests.describe(q)
    if not valid(q) then return nil end
    -- A quest object is named after its class; the quest graph that holds it says which quest it is.
    local okO, graph = pcall(function() return q:GetOuter() end)
    local gname = okO and Game.name(graph) or nil
    local tag = okO and Game.tagName(Game.get(graph, "questTag")) or ""
    return { quest = q, id = gname and gname:gsub("^QuestGraphProcedural_", ""):gsub("^QuestGraph_", "") or Game.name(q),
             tag = tag ~= "" and tag ~= "None" and tag or nil, graph = gname, class = Game.className(q),
             type = Game.enums.questType[Game.get(q, "questType")], status = Game.enums.questStatus[Game.get(q, "QuestStatus")],
             result = Game.enums.questResult[Game.get(q, "QuestResult")], tracked = Game.get(q, "bTracked"),
             xp = Game.get(q, "ExperienceReward"), rewards = Game.map(Game.get(q, "QuestRewards")) }
end

-- Every quest the manager holds, described (its Quests list holds {Quest, Line, Node} entries).
function Game.quests.all()
    local out = {}
    for _, entry in ipairs(Game.list(Game.get(Game.quests.manager(), "Quests"))) do
        local q = Game.get(entry, "Quest")
        if valid(q) then out[#out + 1] = Game.quests.describe(q) end
    end
    return out
end
-- A quest's objectives, in order: { objective, id, index, current, target, status, point } (point: where to
-- go, when it has one).
function Game.quests.objectives(q)
    local out = {}
    if not valid(q) then return out end
    local qm, addr = Game.quests.manager(), q:GetAddress()
    for _, o in ipairs(Game.findAll("ObjectiveBase")) do
        local owner = Game.get(o, "QuestBase")
        if valid(owner) and owner:GetAddress() == addr then
            local okId, id = Game.call(o, "GetObjectiveIDString")
            id = okId and str(id) or nil
            local okC, current = Game.call(o, "GetCurrentNumber")
            local okT, target = Game.call(o, "GetTargetNumber")
            local status
            if id and qm then
                local okS, s = pcall(function() return qm:GetObjectiveStatus(id) end)
                status = okS and Game.enums.objectiveStatus[s] or nil
            end
            local point = Game.get(o, "ObjectivePoint")
            out[#out + 1] = { objective = o, id = id, index = Game.get(o, "ObjectiveIdx", 0), current = okC and current or nil,
                              target = okT and target or nil, status = status, point = valid(point) and point or nil }
        end
    end
    table.sort(out, function(a, b) return a.index < b.index end)
    return out
end

function Game.quests.tracked()
    local qm = Game.quests.manager()
    local ok, q = pcall(function() return qm:GetCurrentTrackedQuest() end)
    return ok and valid(q) and q or nil
end
-- A quest's status and result by its tag: Game.quests.status("Quest.Main.3") -> "OngoingQuest".
function Game.quests.status(tag)
    local qm = Game.quests.manager()
    local ok, s = pcall(function() return qm:GetQuestStatus(Game.tag(tag)) end)
    return ok and Game.enums.questStatus[s] or nil
end
function Game.quests.result(tag)
    local qm = Game.quests.manager()
    local ok, s = pcall(function() return qm:GetQuestResult(Game.tag(tag)) end)
    return ok and Game.enums.questResult[s] or nil
end
function Game.quests.successes(tag)
    local qm = Game.quests.manager()
    local ok, n = pcall(function() return qm:GetCurrentSuccessCount(Game.tag(tag)) end)
    return ok and n or nil
end
-- Start or hand out a quest by tag, the way the game's own quest givers do.
function Game.quests.start(tag)
    local qm = Game.quests.manager()
    return pcall(function() qm:StartQuestOfTag(Game.tag(tag), Game.controller()) end)
end
function Game.quests.give(tag)
    local qm = Game.quests.manager()
    return pcall(function() qm:GiveQuestOfTag(Game.tag(tag)) end)
end
function Game.quests.track(q, on)
    local qm = Game.quests.manager()
    return pcall(function() qm:SetTracked(q, on ~= false) end)
end
-- The chapter the story is in ("Chapter00").
function Game.quests.chapter()
    local lib = Game.library("BFLSwtQuest")
    local out = {}
    local ok = pcall(function() lib:GetChapter(Game.player() or Game.world(), out) end)
    if not ok then return nil end
    local c = out.chapter
    return c and str(c) or nil
end

-- ===================================================================================== combat
Game.combat = {}

-- The fight going on now: the game state's combat director, or nil.
function Game.combatDirector()
    local gs = Game.gameState()
    local d = Game.get(gs, "Director")
    if valid(d) and Game.isA(d, "SwtAdventureCombatDirector") then return d end
    return nil
end
Game.combat.director = Game.combatDirector
function Game.combat.active() return Game.combatDirector() ~= nil end

local Fight = {}
Fight.__index = Fight
Game.Fight = Fight
-- The fight now (or a given director) as a Game.fight wrapper, or nil.
function Game.fight(director)
    director = director or Game.combatDirector()
    if not valid(director) then return nil end
    return setmetatable({ director = director }, Fight)
end
Game.combat.fight = Game.fight

local Fighter = {}
Fighter.__index = Fighter
Game.Fighter = Fighter
-- A fighter: a cat or animal's combat component, with its stats for this fight.
function Game.fighter(x)
    if x == nil then return nil end
    if getmetatable(x) == Cat then x = x.actor end
    local comp = x
    if Game.isA(x, "SwtAdventureCharacter") then comp = Game.get(x, "TurnBasedCombatComponent") end
    if not valid(comp) then return nil end
    return setmetatable({ component = comp }, Fighter)
end

local function fighters(list)
    local out = {}
    for _, c in ipairs(Game.list(list)) do out[#out + 1] = Game.fighter(c) end
    return out
end
function Fight:players() return fighters(Game.get(self.director, "PlayerParty")) end
function Fight:enemies() return fighters(Game.get(self.director, "EnemyParty")) end
function Fight:all()
    local out = self:players()
    for _, f in ipairs(self:enemies()) do out[#out + 1] = f end
    return out
end
-- Who acts in what order this round, as cats.
function Fight:turnOrder()
    local out = {}
    for _, a in ipairs(Game.list(Game.get(self.director, "TurnOrder"))) do out[#out + 1] = Game.cat(a) end
    return out
end
function Fight:current() return Game.cat(Game.get(self.director, "CurrentTurnAttackCharacter")) end
function Fight:mainEnemy() return Game.cat(Game.get(self.director, "MainEnemyCombatCharacter")) end
function Fight:kind() return Game.className(self.director) end
-- (There's no Fight:finish. The combat manager's EndCombat, tried in game, ends the fight but leaves
-- your cat without a body and the fight menu on screen.)

function Fighter:actor()
    local ok, a = Game.call(self.component, "GetOwnerCharacter")
    return ok and valid(a) and a or nil
end
function Fighter:cat() return Game.cat(self:actor()) end
function Fighter:stats()
    local out = {}
    for _, s in ipairs(STATS) do out[s] = Game.get(self.component, "WCM_" .. s) end
    return out
end
function Fighter:setStat(name, v) return Game.set(self.component, "WCM_" .. name, v) end
function Fighter:level() return Game.get(self.component, "WCM_Level") end
function Fighter:setLevel(n) return Game.set(self.component, "WCM_Level", n) end
function Fighter:stance() return Game.enums.stance[Game.get(self.component, "WCM_Stance")] end
-- The move it has picked: its AttackMove row ({AttackMoveTag, Damage, Accuracy, StaminaCost, Stance, ...}).
function Fighter:move() return Game.get(self.component, "AttackSelected") end
function Fighter:moveTag() return Game.tagName(Game.get(self.component, "AttackSelected.AttackMoveTag")) end
-- Change the picked move's numbers before it lands: fighter:setMove({ Damage = 80, Accuracy = 1 }).
function Fighter:setMove(fields)
    local m = Game.get(self.component, "AttackSelected")
    if m == nil then return false, "no move" end
    for k, v in pairs(fields) do
        local ok, err = Game.set(m, k, v)
        if not ok then return false, err end
    end
    return true
end
function Fighter:targets()
    local out = {}
    for _, a in ipairs(Game.list(Game.get(self.component, "CurrentTarget"))) do out[#out + 1] = Game.cat(a) end
    return out
end

-- ===================================================================================== the game's developer switches
-- The cheats manager's own settings: god mode, always-full resources, attacks that always land, fast
-- den building and more. They're the developers' switches; which ones the release build obeys varies,
-- so try each in game.
Game.dev = {}
function Game.dev.manager() return Game.manager("cheats") end
function Game.dev.get(name) return Game.get(Game.dev.manager(), name) end
function Game.dev.set(name, v) return Game.set(Game.dev.manager(), name, v) end
-- Every plain setting (numbers and on/off switches) with its value.
function Game.dev.list()
    local out = {}
    local m = Game.dev.manager()
    if not m then return out end
    for _, p in ipairs(Game.properties(m)) do
        if p.type == "BoolProperty" or p.type == "ByteProperty" or p.type == "IntProperty" or p.type == "FloatProperty"
            or p.type == "EnumProperty" then
            out[#out + 1] = { name = p.name, type = p.type, value = p.value, owner = p.owner }
        end
    end
    return out
end
-- Keep a resource full: Game.dev.fullResource("Stamina", true). Kinds: Health, Level, Stamina,
-- StaminaCombat, Currency, FreshKill.
function Game.dev.fullResource(kind, on)
    local m = Game.dev.manager()
    return pcall(function() m.AlwaysHasFullResource:Add(enumValue(Game.enums.resource, kind), on ~= false) end)
end

return Game
'''


def hidden(offsets=None):
    """HIDDEN with the offsets for the installed game: `offsets` maps "class:property" to an offset, or to
    None for one a game update moved where it couldn't be found again (left out, so reading it gives
    nil); one it doesn't name is left out too. Without `offsets`, the ones found on build 24847281."""
    out = []
    for cls, fields in HIDDEN:
        kept = []
        for name, offset, kind in fields:
            if offsets is not None:
                offset = offsets.get(f"{cls}:{name}")
            if isinstance(offset, int) and offset > 0:
                kept.append((name, offset, kind))
        if kept:
            out.append((cls, kept))
    return out


def lua(offsets=None):
    """The module's Lua; `offsets` as for hidden()."""
    rows = []
    for cls, fields in hidden(offsets):
        items = ", ".join(f'{{ "{n}", 0x{o:X}, "{k}" }}' for n, o, k in fields)
        rows.append(f'    ["{cls}"] = {{ {items} }},')
    return LUA.replace("@HIDDEN@", "{\n" + "\n".join(rows) + "\n}")
