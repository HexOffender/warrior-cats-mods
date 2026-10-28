-- Written by wcmods from your mods' items.json: accessories with a model, a place or an opacity of their own.
-- Do not edit; edit items.json (or the Items page in Clan Mod Studio) and install again.
-- The game puts an accessory's own mesh on a cat and the look's picture on it; when the look is one of
-- these, this puts the look's own mesh in its place (a copy of the accessory's, made at install), and for
-- a see-through one the cats' eye glass in its colour, on every cat that wears it: yours in the forest and
-- the HUD's picture of it, the cats in menus, other cats (the cat choice's small pictures keep the game's).
-- It checks twice a second, because the game sets a cat's accessories again whenever it sets the cat up.
-- { slot = { accessory = { ["look number"] = { mesh = path, opacity = 0..1, glass = { r, g, b } } } } }
local MODELS = @MODELS@
-- The cat's accessory slots: CustomData's Accesory<slot>Id and Accesory<slot>Var, and the slot's mesh.
local SLOTS = { Neck = "AccSkelNeckComp", Paw = "AccSkelPawComp", Body = "AccSkelBodyComp", Head = "AccSkelHeadComp" }
-- The menus' pictures of cats are taken by actors every cat they show shares. The cat choice takes each save's
-- small picture with one, one cat after another, natively, as they load, and shows the cat it's on with another
-- (its CatRef), live; an actor's picture target can belong to another cat than the one it holds. So out of the
-- forest a picture actor wears ours only as the cat choice's own cat, and in the forest only the HUD's picture
-- is taken again.
local PICTURE_ACTOR = "BP_UI_CatCustomActor_C"
local CAT_CHOICE = "WBP_GuiScreenSelectYourCat_C"
local HUD_PICTURE = "RT_UI_Portrait_Exploration"
local RETAKE_TICKS = 4   -- take the HUD's picture again at most every 2 seconds
-- The only see-through material the game has made for cats: their eyes' glass. It has no picture.
local GLASS = "/Game/Art/Characters/CatMaster/Materials/MI_Cat_Cornea.MI_Cat_Cornea"

local function log(fmt, ...) print(string.format("[WCModsModels] " .. fmt .. "\n", ...)) end
local function valid(o) return o ~= nil and o:IsValid() end
local function str(v) local ok, s = pcall(function() return v:ToString() end) return ok and s or tostring(v) end
local function className(o) return o:GetClass():GetFName():ToString() end

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

-- A slot's mesh with its model in: while the game sets a cat up (the cat choice loading its cats) a slot can
-- be without one for a moment, and asking it for a material then crashes the game.
local function ready(c)
    if not valid(c) then return false end
    local ok, asset = pcall(function() return c.SkinnedAsset end)
    return ok and valid(asset)
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
    if not (look and look.opacity) and not mine then return 0 end
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
-- A cat that's off (an actor taking another cat's picture) wears none of ours: they come off.
local seen = {}   -- the slots looked at this tick, so what's kept for ones that are gone is let go
local function apply(comp, off)
    local changed = 0
    local data = comp.CustomData
    for slot, field in pairs(SLOTS) do
        local ok, c = nil, nil
        if MODELS[slot] then ok, c = pcall(function() return comp[field] end) end   -- no mod's look is for it
        if ok and valid(c) then seen[c:GetAddress()] = true end   -- kept while the cat is being set up
        if ok and ready(c) then
            local look = nil
            local byName = MODELS[slot]
            if byName and not off then
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
                -- The game sets the mesh again on every change of look; this is for when it hasn't (a menu's
                -- actor moving on to a cat with the same accessory). Taken off, the slot is hidden and the mesh
                -- left as it is.
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

-- Whether you're in the forest: the player's pawn is a cat.
local function inForest(comps)
    for _, pc in ipairs(FindAllOf("PlayerController") or {}) do
        if valid(pc) and valid(pc.Player) and valid(pc.Pawn) then
            local at = pc.Pawn:GetAddress()
            for _, comp in ipairs(comps) do
                local ok, owner = pcall(function() return comp:GetOwner() end)
                if ok and valid(owner) and owner:GetAddress() == at then return true end
            end
        end
    end
    return false
end

-- The cat choice's own cat (the big one), while that screen shows.
local function choiceCat()
    for _, s in ipairs(FindAllOf(CAT_CHOICE) or {}) do
        if valid(s) and s:IsVisible() then
            local ok, cat = pcall(function() return s.CatRef end)
            if ok and valid(cat) then return cat end
        end
    end
end

-- The HUD's picture of your cat is taken once, as you reach the forest: take it again once its actor wears
-- ours. Only that one: another picture actor's target can belong to another cat. A retake that has to wait
-- out the 2 seconds is due, and taken then.
local ticks, retaken, due = 0, {}, {}
local function retakeHud(owner)
    local cap = owner.CaptureComponent
    if not valid(cap) then return end
    local target = cap.TextureTarget
    if not (valid(target) and target:GetFName():ToString() == HUD_PICTURE) then return end
    local at = owner:GetAddress()
    if retaken[at] and ticks - retaken[at] < RETAKE_TICKS then
        due[at] = true
        return
    end
    retaken[at], due[at] = ticks, nil
    cap:CaptureScene()
end

local function forget(t)
    for key in pairs(t) do
        if not seen[key] then t[key] = nil end
    end
end

local said = false
local function tick()
    ticks = ticks + 1
    local total = 0
    seen = {}
    local comps = FindAllOf("SwtAdventureCustomizableMeshComponent") or {}
    local forest = inForest(comps)
    if not forest then retaken, due = {}, {} end
    local choice = not forest and choiceCat() or nil
    local choiceAt = choice and choice:GetAddress()
    for _, comp in ipairs(comps) do
        if valid(comp) then
            local owner = nil
            pcall(function() owner = comp:GetOwner() end)
            local picture = valid(owner) and className(owner) == PICTURE_ACTOR
            -- Out of the forest a picture actor other than the cat choice's own cat is taking another cat's
            -- picture: it wears none of ours.
            local off = picture and not forest and owner:GetAddress() ~= choiceAt
            local ok, n = pcall(apply, comp, off)
            if ok then
                total = total + n
                if picture and forest and (n > 0 or due[owner:GetAddress()]) then pcall(retakeHud, owner) end
            else
                log("error: %s", tostring(n))
            end
        end
    end
    forget(original)
    forget(originalMats)
    forget(glassOn)
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
