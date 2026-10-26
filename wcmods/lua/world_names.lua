
-- The game's own text for a name: its string table holds whole names under the prefix's id and the
-- suffix's ("STR_CAT_NAME1" .. "_PAW" is "Woodpaw"). Used for a name the tables above haven't got, as
-- when wcmods had no Oodle DLL to read the game's tables at install, so they're empty.
local strings, tableIds, found = nil, nil, {}
local function gameText(key)
    if key == "" then return nil end
    if found[key] then return found[key] end   -- asked again and again (the status line, labels); it doesn't change
    if strings == nil then
        strings = StaticFindObject("/Script/Engine.Default__KismetStringTableLibrary") or false
        tableIds = {}
        if strings and strings:IsValid() then
            local ok, ids = pcall(function() return strings:GetRegisteredStringTables() end)
            for _, id in ipairs(ok and type(ids) == "table" and ids or {}) do tableIds[#tableIds + 1] = id:get() end
        end
    end
    for _, id in ipairs(tableIds) do
        local ok, s = pcall(function()
            if strings:IsRegisteredTableEntry(id, key) then return strings:GetTableEntrySourceString(id, key):ToString() end
        end)
        if ok and type(s) == "string" and s ~= "" then
            found[key] = s
            return s
        end
    end
    return nil
end

-- A cat's name from its name ids (its customization's PrefixNameId and SuffixNameId), or nil.
function N.name(prefix, suffix)
    prefix, suffix = prefix or "", suffix or ""
    -- A whole name first: a fixed name or a cat's own prefix has one under prefix + suffix, a cameo cat or a
    -- rogue (and a loner with only a prefix) under the prefix alone. Then the tables' parts.
    local whole = N.whole[prefix .. suffix] or N.whole[prefix]
    if whole then return whole end
    local p = N.prefixes[prefix]
    if p then return p .. (N.suffixes[suffix] or "") end
    return gameText(prefix .. suffix) or gameText(prefix)
end

-- Whether the game has the names your mods add. They're text in wcmods' pak: a game that isn't reading
-- that pak shows "<MISSING STRING TABLE ENTRY>" for a cat renamed to one (and calls it "Cat 1" in
-- dialogue), while the save already carries the new ID. nil when no mod adds a name; asked once.
local loaded = nil
function N.loaded()
    if #N.added == 0 then return nil end
    if loaded == nil then
        loaded = false
        for _, key in ipairs(N.added) do
            if gameText(key) then loaded = true break end
        end
        if not loaded then
            print("[WCModsNames] the game hasn't got the names your mods add (no text under " .. N.added[1] ..
                  "): it isn't reading wcmods' pak (~mods/zzz_WCMods_P.pak)\n")
        end
    end
    return loaded
end

-- An item's name from its tag ("Gameplay.Inventory.Consumable.MediumHealingHerb" is "Marigold"), or nil.
function N.item(tag) return N.items[tag] end

return N
