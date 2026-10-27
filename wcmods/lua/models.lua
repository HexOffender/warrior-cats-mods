-- Written by wcmods from your mods' items.json: accessories with a model of their own. Do not edit; edit
-- items.json (or the Items page in Clan Mod Studio) and install again.
-- The game puts an accessory's own mesh on a cat and the look's picture on it; when the look is one of
-- these, this puts the model's mesh in its place (a copy of the accessory's, made at install), on every
-- cat that wears it: yours in the forest, the copies in menus and portraits, other cats. It checks twice a
-- second, because the game sets a cat's accessories again whenever it sets the cat up.
-- { slot = { accessory = { ["look number"] = mesh path } } }
local MODELS = @MODELS@
-- The cat's accessory slots: CustomData's Accesory<slot>Id and Accesory<slot>Var, and the slot's mesh.
local SLOTS = { Neck = "AccSkelNeckComp", Paw = "AccSkelPawComp", Body = "AccSkelBodyComp", Head = "AccSkelHeadComp" }
-- Actors that show a copy of a cat in menus and portraits, whose pictures are taken again after a change.
local MENU_ACTORS = { "CatCustomActor", "MainMenu", "Customization_Player" }

local function log(fmt, ...) print(string.format("[WCModsModels] " .. fmt .. "\n", ...)) end
local function valid(o) return o ~= nil and o:IsValid() end
local function str(v) local ok, s = pcall(function() return v:ToString() end) return ok and s or tostring(v) end

local OURS = {}
for _, byName in pairs(MODELS) do
    for _, byVar in pairs(byName) do
        for _, path in pairs(byVar) do OURS[path] = true end
    end
end

local loaded, failed, original = {}, {}, {}
local ksl = nil

-- A mod's mesh isn't in the game's asset registry, so it's loaded by its path the way the game loads a
-- soft reference.
local function load(path)
    local m = loaded[path]
    if valid(m) then return m end
    if failed[path] then return nil end
    if not valid(ksl) then ksl = StaticFindObject("/Script/Engine.Default__KismetSystemLibrary") end
    local ok, obj = pcall(function()
        return ksl:LoadAsset_Blocking(ksl:Conv_SoftObjPathToSoftObjRef(ksl:MakeSoftObjectPath(path)))
    end)
    if ok and valid(obj) then
        loaded[path] = obj
        return obj
    end
    failed[path] = true
    log("couldn't load %s (%s)", path, ok and "not found" or tostring(obj))
end

local function meshOf(c)
    local ok, m = pcall(function() return c:GetSkeletalMeshAsset() end)
    if ok and valid(m) then return m, str(m:GetFullName()):match("^%S+ (.+)$") end
end

local function setMesh(c, m)
    if not pcall(function() c:SetSkeletalMeshAsset(m) end) then
        c:SetSkeletalMesh(m, false)
    end
end

-- One cat: each slot whose look has a model gets it; a slot that has one of ours on a look without a
-- model gets the game's mesh back (when the game changed the look but not the mesh).
local function apply(comp)
    local changed = 0
    local data = comp.CustomData
    for slot, field in pairs(SLOTS) do
        local ok, c = pcall(function() return comp[field] end)
        if ok and valid(c) then
            local want = nil
            local byName = MODELS[slot]
            if byName then
                local id = str(data["Accesory" .. slot .. "Id"])
                local byVar = byName[id]
                if byVar then
                    local var = data["Accesory" .. slot .. "Var"]
                    want = byVar[tostring(math.tointeger(var) or var)]   -- look numbers are keys as text
                end
            end
            local current, path = meshOf(c)
            local key = c:GetAddress()
            if want and path ~= want then
                local m = load(want)
                if m then
                    if path and not OURS[path] then original[key] = current end
                    setMesh(c, m)
                    changed = changed + 1
                end
            elseif not want and path and OURS[path] then
                if valid(original[key]) then setMesh(c, original[key]) end
                original[key] = nil
                changed = changed + 1
            end
        end
    end
    return changed
end

local function isMenuActor(owner)
    local cls = owner:GetClass():GetFName():ToString()
    for _, part in ipairs(MENU_ACTORS) do
        if cls:find(part, 1, true) then return true end
    end
    return false
end

-- Portraits and thumbnails are pictures the game takes of a copy of the cat: take them again.
local function retake(owner)
    for _, field in ipairs({ "CaptureComponent", "CaptureComponentInventory" }) do
        pcall(function()
            local cap = owner[field]
            if valid(cap) then cap:CaptureScene() end
        end)
    end
end

local said = false
local function tick()
    local total = 0
    for _, comp in ipairs(FindAllOf("SwtAdventureCustomizableMeshComponent") or {}) do
        if valid(comp) then
            local ok, n = pcall(apply, comp)
            if ok and n > 0 then
                total = total + n
                local okOwner, owner = pcall(function() return comp:GetOwner() end)
                if okOwner and valid(owner) and isMenuActor(owner) then retake(owner) end
            elseif not ok then
                log("error: %s", tostring(n))
            end
        end
    end
    if total > 0 and not said then
        said = true
        log("a cat wears an accessory with a model of a mod's own")
    end
end

LoopAsync(500, function()
    ExecuteInGameThread(function()
        local ok, err = pcall(tick)
        if not ok then log("error: %s", tostring(err)) end
    end)
    return false
end)
log("loaded")
