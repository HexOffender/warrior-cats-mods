-- WCModsWorld: finds things in the game world. Installed by wcmods; any UE4SS script can use it:
--
--   local World = require("WCModsWorld")
--   for _, it in ipairs(World.nearby("pickups", 3000)) do      -- within 30 m of your cat, nearest first
--       print(string.format("%s %.0f m\n", it.label, it.distance / 100))
--   end
--   local quests = World.manager("quests")                     -- the game's quest manager
--
-- It reads the engine's actor list (one FindAllOf("Actor") at most every World.refresh seconds, 2 by
-- default) and sorts each actor into kinds by its class and the classes that's made from. Queries in
-- between use that list, so they're cheap; call them on the game thread. Every call is in docs/SDK.md.
local World = { refresh = 2 }

-- Kind -> the classes it covers (an actor of a class made from one of them counts too). Checked in
-- game: the classes and what they're made from, as the game's own objects report them.
World.kinds = {
    pickups = { "SwtAdventurePickupActor" },                     -- herbs, catnip, healing herbs, pouches
    interactables = { "BP_Interactable_Base_C", "SwtAdventureInteractableSequence", "SwtAdventureInteractByContact" },
                                                                 -- dig, claw, sharpen, sleep, play spots; flowers
    objectives = { "SwtQuestObjectivePoint", "QuestBoxTrigger", "BP_Objective_Base_C", "BP_ScentObjective_C",
                   "BP_InterativeObjective_C" },                 -- quest places and trigger areas
    cats = { "SwtAdventureWalkingNPC", "SwtAdventureQuestActor" }, -- clan cats walking about, quest givers, fillers
    questGivers = { "BP_Quest_Giver_Base_C", "SwtAdventureQuestHintActor", "SwtAdventureFreshKillActor" },
    creatures = { "WrcRoamingEnemy" },                           -- prey and other animals roaming the territory
    climbing = { "SwtAdventureSplineClimbTarget", "SwtAdventureJumpHotspotBase" },  -- trees and walls; jump spots
    dens = { "SwtAdventureHousingDoorActor" },
    freshKill = { "SwtAdventureFreshKillPileActor" },
    zones = { "WrcZoneNameTrigger" },                            -- the areas whose names the game shows
    checkpoints = { "BP_Checkpoint_Base_C" },
}

-- How the kinds are shown: in this order, named so, in these colours (scripts can change them).
World.kindInfo = {
    pickups = { label = "Pickups", color = "#7ee081" },
    interactables = { label = "Interactables", color = "#8fd3ff" },
    objectives = { label = "Quest objectives", color = "#ffd166" },
    questGivers = { label = "Quest givers", color = "#ff9f5a" },
    cats = { label = "Cats", color = "#f4a7ff" },
    creatures = { label = "Creatures", color = "#ff6b6b" },
    climbing = { label = "Climbing and jumping", color = "#b9a8ff" },
    dens = { label = "Dens", color = "#d8b48a" },
    freshKill = { label = "Fresh-kill pile", color = "#f0e68c" },
    zones = { label = "Areas", color = "#9ad8cf" },
    checkpoints = { label = "Checkpoints", color = "#ffffff" },
}
World.order = { "pickups", "interactables", "objectives", "questGivers", "cats", "creatures", "climbing", "dens",
                "freshKill", "zones", "checkpoints" }

-- The kinds in order: World.order first, then any others (added by a script) by name.
function World.kindOrder()
    local out, seen = {}, {}
    for _, k in ipairs(World.order) do
        if World.kinds[k] then out[#out + 1], seen[k] = k, true end
    end
    local rest = {}
    for k in pairs(World.kinds) do
        if not seen[k] then rest[#rest + 1] = k end
    end
    table.sort(rest)
    for _, k in ipairs(rest) do out[#out + 1] = k end
    return out
end

function World.kindLabel(kind) return (World.kindInfo[kind] or {}).label or kind end

local SPARE = { "#ff8fab", "#a0e7e5", "#caffbf", "#ffc6ff", "#fdffb6", "#bdb2ff" }
function World.kindColor(kind)
    local info = World.kindInfo[kind]
    if info and info.color then return info.color end
    local h = 0
    for i = 1, #kind do h = (h * 31 + kind:byte(i)) % 997 end
    return SPARE[h % #SPARE + 1]
end

-- The game's managers: one object each, found by class.
World.managers = {
    quests = "BP_WrcQuestManager_C", npcs = "BP_WrcNPCGenerationManager_C", tracer = "BP_WrcActorTracerManager_C",
    gui = "BP_WrcGuiManager_C", storage = "BP_WrcStorageManager_C", paths = "BP_WrcTrackPathManager_C",
    tutorial = "BP_WrcTutorialManager_C", combat = "BP_WrcCombatManager_C", tuning = "BP_WrcTuningManager_C",
}

local function valid(o) return o ~= nil and o:IsValid() end

local pc, nextSearch = nil, 0
local function controller()
    -- A destroyed controller's slot can be taken by another object, so even reading it is guarded.
    local ok, still = pcall(function() return valid(pc) and valid(pc.Player) end)
    if ok and still then return pc end
    pc = nil
    if os.clock() < nextSearch then return nil end
    nextSearch = os.clock() + 0.5
    for _, c in ipairs(FindAllOf("PlayerController") or {}) do
        if valid(c) and valid(c.Player) then
            pc = c
            break
        end
    end
    return pc
end

-- Your cat: the player's pawn, or nil (in menus, loading).
function World.player()
    local c = controller()
    if c and valid(c.Pawn) then return c.Pawn end
    return nil
end

-- An actor's location as {X, Y, Z}; a table that's already a location comes back as it is.
function World.location(it)
    if type(it) == "table" then return it end
    local l = it:K2_GetActorLocation()
    return { X = l.X, Y = l.Y, Z = l.Z }
end

-- Centimetres between two actors or locations.
function World.distance(a, b)
    local p, q = World.location(a), World.location(b)
    local dx, dy, dz = p.X - q.X, p.Y - q.Y, p.Z - q.Z
    return math.sqrt(dx * dx + dy * dy + dz * dz)
end

-- The class an actor is made of, then the ones that's made from, up to Actor.
function World.parents(cls)
    local names = {}
    while valid(cls) do
        local n = cls:GetFName():ToString()
        names[#names + 1] = n
        if n == "Actor" or n == "Object" then break end
        cls = cls:GetSuperStruct()
    end
    return names
end

-- ---------- readable names ----------
-- From the class (BP_Pickup_SmallHealingHerb_C is "Small Healing Herb", BP_Interactable_Claw_Bush_C
-- "Bush (claw)"); cats by their own names (WCModsNames, written by wcmods from the game's name tables and
-- your name mods); creatures by their model ("Mouse").
local okNames, NAMES = pcall(require, "WCModsNames")
if not okNames or type(NAMES) ~= "table" or not NAMES.name then NAMES = { name = function() return nil end } end
if not NAMES.item then NAMES.item = function() return nil end end   -- a WCModsNames from before items had names

local NAMED = {
    BP_Quest_Filler_C = "Clan cat", BP_Quest_Giver_Gossip_C = "Gossip", BP_Quest_Giver_FreshKill_C = "Fresh-kill task",
    BP_WalkingNPC_Character_Base_C = "Cat", BP_Exploration_Character_Base_C = "Creature",
    BP_Housing_DoorActor_C = "Den", BP_SplineClimb_Target_TreeClimb_C = "Climbable tree",
    BP_SplineClimb_Target_Wall_C = "Climbable wall", BP_ZoneNameTrigger_C = "Area", BP_QuestBoxTrigger_C = "Quest area",
    BP_RaceTrigger_C = "Race", WrcObjectivePoint = "Quest place", BP_ScentObjective_C = "Scent trail",
    BP_ScentObjectiveFish_C = "Scent trail (fish)", BP_InterativeObjective_C = "Quest spot",
}
-- The things a cat does at an interactable (BP_Interactable_<Action>_<Thing>).
local ACTIONS = { Claw = true, Dig = true, Sharpen = true, Sleep = true, Play = true }
local function words(str)
    return (str:gsub("_", " "):gsub("(%l)(%u)", "%1 %2"):gsub("(%u)(%u%l)", "%1 %2"):gsub("%s+", " "))
end

local classLabels = {}
local function classLabel(n)
    local hit = classLabels[n]
    if hit then return hit end
    hit = NAMED[n]
    if not hit then
        local b = n:gsub("^BP_", ""):gsub("_C$", "")
        local action, thing = b:match("^Interactable_(%a+)_(.+)$")
        local only = b:match("^Interactable_(%a+)$")
        if not ACTIONS[action or ""] then action, thing = nil, nil end
        if not ACTIONS[only or ""] then only = nil end
        if b:find("^FreshKill_Pile") then
            hit = "Fresh-kill pile"
        elseif b:find("Jump") and b:find("HotSpot") then
            hit = "Jump spot"
        elseif b:find("^SplineClimb") then
            hit = "Climbing spot"
        elseif action then
            hit = words(thing) .. " (" .. action:lower() .. ")"
        elseif only then
            hit = only .. " spot"
        else
            for _, prefix in ipairs({ "InteractableReward_Container_", "InteractableByContact_", "Interactable_", "PickupActor_",
                                      "Pickup_", "Quest_Giver_", "Quest_", "WalkingNPC_", "Exploration_" }) do
                if b:sub(1, #prefix) == prefix and #b > #prefix then
                    b = b:sub(#prefix + 1)
                    break
                end
            end
            hit = words(b)
        end
    end
    classLabels[n] = hit
    return hit
end

local function str(v)
    local ok, s = pcall(function() return v:ToString() end)
    if ok and type(s) == "string" then return s end
    return type(v) == "string" and v or ""
end

-- A cat's name from its customisation data (the same name IDs the game saves), or nil.
local meshClass, meshSearch = nil, 0
local function catName(actor)
    if not valid(meshClass) then
        if os.clock() < meshSearch then return nil end
        meshSearch = os.clock() + 5
        local any = FindFirstOf("SwtAdventureCustomizableMeshComponent")
        if not valid(any) then return nil end
        meshClass = any:GetClass()
    end
    local ok, name = pcall(function()
        local comp = actor:GetComponentByClass(meshClass)
        if not valid(comp) then return nil end
        local d = comp.CustomData
        return NAMES.name(str(d.PrefixNameId), str(d.SuffixNameId))
    end)
    if ok then return name end
    return nil
end

-- A creature's model name: SK_Mouse is "Mouse".
local function meshLabel(actor)
    -- Calling a function on an object that isn't there crashes the game inside UE4SS (pcall can't catch
    -- that), and animals far away can have no mesh loaded, so every step is checked first.
    local ok, name = pcall(function()
        local m = actor.Mesh
        if not valid(m) then return nil end
        local asset
        if not pcall(function() asset = m:GetSkeletalMeshAsset() end) or not valid(asset) then asset = m.SkeletalMesh end
        if not valid(asset) then return nil end
        return asset:GetFName():ToString()
    end)
    if not ok or type(name) ~= "string" or name == "" then return nil end
    name = name:gsub("^SKM?_", ""):gsub("^SK_", ""):gsub("_%d+$", ""):gsub("_[Ss]keletal[Mm]esh$", "")
    return words(name)
end

-- What a pickup holds, by the items' own names ("Marigold"; its class may say "Medium Healing Herb", as
-- the game uses a few pickup classes for many items), or nil.
local function pickupLabel(actor)
    local names = {}
    pcall(function()
        actor.Reward:ForEach(function(k, _)
            local name = NAMES.item(str(k:get().TagName))
            if name then names[#names + 1] = name end
        end)
    end)
    if #names == 0 then return nil end
    table.sort(names)
    return table.concat(names, ", ")
end

local actorLabels = {}   -- "address|class" -> label, for labels that belong to one actor; scan() clears it
-- A readable name for an actor (kind, when known, helps: cats get their names, creatures their model).
function World.label(actor, kind)
    local n = actor:GetClass():GetFName():ToString()
    local base = classLabel(n)
    local pickup = kind == "pickups" or (kind == nil and n:find("Pickup") ~= nil)
    local personal = pickup or kind == "cats" or kind == "questGivers" or kind == "creatures"
    if not personal then return base end
    local key = tostring(actor:GetAddress()) .. "|" .. n
    local hit = actorLabels[key]
    if hit then return hit end
    if pickup then
        hit = pickupLabel(actor) or base
    elseif kind == "creatures" then
        hit = meshLabel(actor) or base
    else
        local name = catName(actor)
        if name and (base == "Cat" or base == "Clan cat") then
            hit = name
        elseif name then
            hit = name .. " (" .. base .. ")"
        else
            hit = base
        end
    end
    actorLabels[key] = hit
    return hit
end

-- ---------- the index ----------
local index = { at = nil, byKind = {} }
local classKinds = {}   -- class address -> { kind = true }

local function kindsOf(cls)
    local key = cls:GetAddress()
    local hit = classKinds[key]
    if hit then return hit end
    local names = {}
    for _, n in ipairs(World.parents(cls)) do names[n] = true end
    hit = {}
    for kind, list in pairs(World.kinds) do
        for _, n in ipairs(list) do
            if names[n] then
                hit[kind] = true
                break
            end
        end
    end
    classKinds[key] = hit
    return hit
end

local function scan()
    -- An actor that went since the last scan can have left its address to another of the same class (a
    -- pickup picked up, another item dropped there), which mustn't keep the old one's label.
    actorLabels = {}
    local byKind = {}
    for kind in pairs(World.kinds) do byKind[kind] = {} end
    for _, a in ipairs(FindAllOf("Actor") or {}) do
        if a:IsValid() then
            for kind in pairs(kindsOf(a:GetClass())) do
                local list = byKind[kind]
                list[#list + 1] = a
            end
        end
    end
    index = { at = os.clock(), byKind = byKind }
end

local function fresh()
    if index.at == nil or os.clock() - index.at >= World.refresh then scan() end
    return index.byKind
end

-- Look again at the next query, e.g. after something was spawned.
function World.rescan() index.at = nil end

-- Add a kind, or change one: World.addKind("birds", { "BP_Bird_C" }).
function World.addKind(kind, classes)
    World.kinds[kind] = classes
    classKinds, index.at = {}, nil
end

local byClass = {}   -- class name -> { at, list }, for queries by a class that isn't a kind
-- Every actor of a kind (a name from World.kinds) or of a class (its name, e.g. "BP_Pickup_Herb_1_C").
function World.find(kind)
    if World.kinds[kind] then return fresh()[kind] or {} end
    local c = byClass[kind]
    if not c or os.clock() - c.at >= World.refresh then
        c = { at = os.clock(), list = FindAllOf(kind) or {} }
        byClass[kind] = c
    end
    return c.list
end

-- What's within `radius` centimetres (all of them without one) of `from` (an actor or {X, Y, Z};
-- your cat by default), nearest first: { actor, location, distance, name, label, class }. Your cat
-- itself is left out.
function World.nearby(kind, radius, from)
    local me = World.player()
    from = from or me
    if not from then return {} end
    local origin = World.location(from)
    local mine = me and me:GetAddress()
    local out = {}
    local isKind = World.kinds[kind] ~= nil
    for _, a in ipairs(World.find(kind)) do
        -- Between scans an actor can go (a pickup picked up) and another object take its slot, so the
        -- class is checked again.
        local ok0, fits = pcall(function()
            return a:IsValid() and a:GetAddress() ~= mine and (not isKind or kindsOf(a:GetClass())[kind] == true)
        end)
        if ok0 and fits then
            local ok, l = pcall(World.location, a)
            if ok then
                local dx, dy, dz = l.X - origin.X, l.Y - origin.Y, l.Z - origin.Z
                local d = math.sqrt(dx * dx + dy * dy + dz * dz)
                if not radius or d <= radius then
                    out[#out + 1] = { actor = a, location = l, distance = d, name = a:GetFName():ToString(),
                                      label = World.label(a, isKind and kind or nil),
                                      class = a:GetClass():GetFName():ToString() }
                end
            end
        end
    end
    table.sort(out, function(p, q) return p.distance < q.distance end)
    return out
end

-- Everything handy about one actor: { name, label, class, parents, location }.
function World.describe(actor)
    return { name = actor:GetFName():ToString(), label = World.label(actor),
             class = actor:GetClass():GetFName():ToString(), parents = World.parents(actor:GetClass()),
             location = World.location(actor) }
end

local managers = {}
-- One of the game's managers by its name in World.managers ("quests", "npcs", ...) or its class.
function World.manager(name)
    local cls = World.managers[name] or name
    local m = managers[cls]
    if valid(m) then return m end
    m = FindFirstOf(cls)
    if valid(m) then
        managers[cls] = m
        return m
    end
    return nil
end

return World
