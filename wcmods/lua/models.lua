-- Written by wcmods from your mods' items.json: accessories with a model, a place or an opacity of their own.
-- Do not edit; edit items.json (or the Items page in Clan Mod Studio) and install again.
-- The game puts an accessory's own mesh on a cat and the look's picture on it; when the look is one of
-- these, this puts the look's own mesh in its place (a copy of the accessory's, made at install), and for
-- a see-through one the cats' eye glass in its colour, on every cat that wears it: yours in the forest,
-- the copies in menus and portraits, other cats. It checks twice a second, because the game sets a cat's
-- accessories again whenever it sets the cat up.
-- { slot = { accessory = { ["look number"] = { mesh = path, opacity = 0..1, glass = { r, g, b } } } } }
local MODELS = @MODELS@
-- The cat's accessory slots: CustomData's Accesory<slot>Id and Accesory<slot>Var, and the slot's mesh.
local SLOTS = { Neck = "AccSkelNeckComp", Paw = "AccSkelPawComp", Body = "AccSkelBodyComp", Head = "AccSkelHeadComp" }
-- Actors that show a copy of a cat in menus and portraits, whose pictures are taken again after a change.
local MENU_ACTORS = { "CatCustomActor", "MainMenu", "Customization_Player" }
-- The only see-through material the game has made for cats: their eyes' glass. It has no picture.
local GLASS = "/Game/Art/Characters/CatMaster/Materials/MI_Cat_Cornea.MI_Cat_Cornea"

local function log(fmt, ...) print(string.format("[WCModsModels] " .. fmt .. "\n", ...)) end
local function valid(o) return o ~= nil and o:IsValid() end
local function str(v) local ok, s = pcall(function() return v:ToString() end) return ok and s or tostring(v) end

local OURS = {}
for _, byName in pairs(MODELS) do
    for _, byVar in pairs(byName) do
        for _, look in pairs(byVar) do
            if look.mesh then OURS[look.mesh] = true end
        end
    end
end

local loaded, failed = {}, {}
local original, originalMats, glassOn = {}, {}, {}   -- per component: the game's mesh and materials, our glass
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

-- The look's opacity: every material slot in glass of its colour, or the game's materials back.
local function setGlass(c, key, look)
    local mine = glassOn[key]
    local first = c:GetMaterial(0)
    local wearing = mine and valid(mine.mid) and valid(first) and first:GetAddress() == mine.mid:GetAddress()
    if look and look.opacity then
        if wearing and mine.opacity == look.opacity and mine.glass == look.glass then return 0 end
        local glass = load(GLASS)
        if not glass then return 0 end
        if not wearing then
            local mats = {}
            for i = 0, c:GetNumMaterials() - 1 do mats[i] = c:GetMaterial(i) end
            originalMats[key] = mats
        end
        for i = 0, c:GetNumMaterials() - 1 do
            local mid = c:CreateDynamicMaterialInstance(i, glass, FName("WCModsGlass"))
            if valid(mid) then
                mid:SetScalarParameterValue(FName("Glass Opacity"), look.opacity)
                mid:SetVectorParameterValue(FName("Glass Color"), { R = look.glass[1], G = look.glass[2], B = look.glass[3], A = 1.0 })
                if i == 0 then glassOn[key] = { mid = mid, opacity = look.opacity, glass = look.glass } end
            end
        end
        return 1
    elseif wearing then
        for i, m in pairs(originalMats[key] or {}) do
            if valid(m) then c:SetMaterial(i, m) end
        end
        glassOn[key], originalMats[key] = nil, nil
        return 1
    end
    return 0
end

-- One cat: each slot whose look has a mesh of its own gets it; a slot that has one of ours on a look
-- without one gets the game's mesh back (when the game changed the look but not the mesh). Then its glass.
local function apply(comp)
    local changed = 0
    local data = comp.CustomData
    for slot, field in pairs(SLOTS) do
        local ok, c = pcall(function() return comp[field] end)
        if ok and valid(c) then
            local look = nil
            local byName = MODELS[slot]
            if byName then
                local byVar = byName[str(data["Accesory" .. slot .. "Id"])]
                if byVar then
                    local var = data["Accesory" .. slot .. "Var"]
                    look = byVar[tostring(math.tointeger(var) or var)]   -- look numbers are keys as text
                end
            end
            local want = look and look.mesh
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
                -- The game sets the mesh again on every change of look; this is for when it hasn't. Taken
                -- off, the slot is hidden and the mesh left as it is.
                if valid(original[key]) then
                    setMesh(c, original[key])
                    changed = changed + 1
                end
                original[key] = nil
            end
            changed = changed + setGlass(c, key, look)
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
        log("a cat wears an accessory of a mod's own (a model, a place or glass)")
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
