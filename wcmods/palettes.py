"""Colour palettes.

palette.json sections (all optional):
  "eyes":    {"Amber": "#ffb300", "Sky": ["#001018", "#00e5ff"], "Sclera": "#f7f3e8"}
  "fur":     {"0": "#f2e6d0", "3": "#ff7a1a"}
  "pattern": {...}   "marking": {...}   "iris_ui": {...}

Eyes are baked into the eye atlas asset (works offline). Keys are the game's slot labels
(see `wcmods eyes`), "iris1".."iris25" or "row0".."row25". One colour keeps the game's
shading ramp; a list of colours is spread evenly from the pupil to the rim.

fur / pattern / marking / iris_ui are indexes (0-based) into the game's built-in colour tables
(FurColors, PatternMaskColors, MarkingMaskColors, IrisColors). Those tables live in game code,
so they are recoloured at runtime by a generated UE4SS Lua script.

Pattern and marking colours can also take new slots past the game's 25 (slot 25 and up): the
script grows those two tables, so the game's colours stay as they are and only cats set to a new
slot wear it (a cat's Pattern01ColorIdx picks its pattern colour, Pattern02ColorIdx its marking
colour). The game checks those indexes against the tables' real size. Coat colours can't grow:
the game pairs each coat slot with paw, ear, nose and whisker colours it keeps in code, and a coat
slot without them crashes it, so cats.json colours just your cat's coat instead (see catlook.py).
"""
import json
import os

from . import colors

RUNTIME_SECTIONS = {"fur": "FurColors", "pattern": "PatternMaskColors",
                    "marking": "MarkingMaskColors", "iris_ui": "IrisColors"}
SECTIONS = ("eyes",) + tuple(RUNTIME_SECTIONS)
GAME_SLOTS = 25                       # entries in each of the game's colour tables
GROWABLE = ("pattern", "marking")     # sections whose tables can take slots past GAME_SLOTS


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        raw = json.load(f)
    out = {}
    for section, entries in raw.items():
        if section.startswith("_") or section in ("name", "description"):
            continue
        if section not in SECTIONS:
            raise ValueError(f"{path}: unknown palette section '{section}' (use {', '.join(SECTIONS)})")
        parsed = {}
        for key, spec in entries.items():
            if str(key).startswith("_"):
                continue
            if section != "eyes" and not str(key).isdigit():
                raise ValueError(f"{path}: {section} keys are slot numbers starting at 0, got '{key}'")
            if section != "eyes" and int(key) >= GAME_SLOTS and section not in GROWABLE:
                raise ValueError(f"{path}: {section} has slots 0-{GAME_SLOTS - 1}; only pattern and marking colours "
                                 "take new slots (to colour just your cat's coat, use cats.json)")
            if isinstance(spec, list) and spec and not isinstance(spec[0], (int, float)):
                if section != "eyes":
                    raise ValueError(f"{path}: {section}.{key} must be a single colour (gradients are eyes-only)")
                parsed[str(key)] = [colors.parse(s) for s in spec]
            else:
                parsed[str(key)] = colors.parse(spec)
        out[section] = parsed
    return out


def new_slots(palette):
    """{section: [slot, ...]} for the slots past the game's that a loaded palette adds."""
    return {s: sorted(int(k) for k in palette.get(s, {}) if int(k) >= GAME_SLOTS) for s in GROWABLE
            if any(int(k) >= GAME_SLOTS for k in palette.get(s, {}))}


def adds_only(palette):
    """True for a palette that only adds new slots: it changes no colour the game already has."""
    return bool(new_slots(palette)) and not palette.get("eyes") and all(
        int(k) >= GAME_SLOTS for s in RUNTIME_SECTIONS for k in palette.get(s, {}))


def merge(palettes):
    merged = {s: {} for s in SECTIONS}
    for pal in palettes:
        for section, entries in pal.items():
            merged[section].update(entries)
    return {s: e for s, e in merged.items() if e}


def apply_eyes(atlas, eyes):
    """Recolour atlas rows. Returns [(row, label, old_hex, new_hex)]. Unknown slot names raise KeyError."""
    changes = []
    for key, spec in eyes.items():
        r = atlas.slot(key)
        old = atlas.row(r)
        w = atlas.width
        if isinstance(spec, list):
            stops = [colors.to_linear(c) for c in spec]
            new = []
            for x in range(w):
                t = x / (w - 1) * (len(stops) - 1)
                i = min(int(t), len(stops) - 2) if len(stops) > 1 else 0
                f = t - i if len(stops) > 1 else 0.0
                a, b = stops[i], stops[min(i + 1, len(stops) - 1)]
                new.append(tuple(a[k] + (b[k] - a[k]) * f for k in range(3)) + (old[x][3],))
        else:
            target = colors.to_linear(spec)
            peak = max(colors.luminance(p) for p in old)
            ramp = colors.luminance(old[0]) < 0.02 * max(peak, 1e-6)
            new = []
            for x in range(w):
                # Iris rows ramp up from black: keep that shape. Other rows (sclera) become flat.
                scale = colors.luminance(old[x]) / peak if (ramp and peak > 0) else 1.0
                new.append(tuple(c * scale for c in target) + (old[x][3],))
        atlas.set_row(r, new)
        changes.append((r, atlas.labels[r], colors.hex_from_linear(old[-1]), colors.hex_from_linear(new[-1])))
    return changes


LUA_TEMPLATE = r'''-- Generated by wcmods from your enabled palette mods. Do not edit; edit palette.json and rebuild.
-- Recolours the customization colour tables that Warrior Cats keeps in game code.
local PALETTE = {
%(tables)s
}
local GAME_SLOTS = %(game_slots)d
local ORDER = { "FurColors", "PatternMaskColors", "MarkingMaskColors", "IrisColors" }
-- Tables that take new slots past the game's. The game checks pattern and marking indexes against the
-- table's size; coat slots are paired with colours kept in game code, so FurColors must never grow.
local GROW = { PatternMaskColors = true, MarkingMaskColors = true }
local gameSize = {}
-- "GuiManager" is the class name found in the game code; the rest are fallbacks.
local CLASSES = { "GuiManager", "BP_WrcGuiManager_C", "SwtAdventureGuiManager", "WrcGuiManager" }
local patched = {}
local attempts = 0
local searched = false

local function log(fmt, ...) print(string.format("[WCModsPalettes] " .. fmt .. "\n", ...)) end

local function srgbToLinear(c)
    if c <= 0.04045 then return c / 12.92 end
    return ((c + 0.055) / 1.055) ^ 2.4
end

local function toHex(el, isByte)
    local function b(v)
        if isByte then return math.floor(v + 0.5) end
        v = math.max(0, math.min(1, v))
        v = (v <= 0.0031308) and (v * 12.92) or (1.055 * v ^ (1 / 2.4) - 0.055)
        return math.floor(v * 255 + 0.5)
    end
    return string.format("#%%02X%%02X%%02X", b(el.R), b(el.G), b(el.B))
end

local function patchArray(obj, prop, entries)
    local ok, arr = pcall(function() return obj[prop] end)
    if not ok or arr == nil or not arr.GetArrayNum then
        log("%%s: property %%s not found", obj:GetFullName(), prop)
        return
    end
    local n = arr:GetArrayNum()
    gameSize[prop] = gameSize[prop] or n
    local top = -1
    for idx, _ in pairs(entries) do if idx > top then top = idx end end
    if top >= n and GROW[prop] then
        -- New slots start as copies of the game's colours (only slots a palette sets are recoloured).
        for k = n + 1, top + 1 do
            local base = arr[((k - 1) %% n) + 1]
            arr[k] = { R = base.R, G = base.G, B = base.B, A = base.A }
        end
        log("%%s grew from %%d to %%d slots", prop, n, arr:GetArrayNum())
        n = arr:GetArrayNum()
    end
    for i = 1, n do
        local el = arr[i]
        local isByte = math.type(el.R) == "integer" or el.R > 1.0 or el.G > 1.0 or el.B > 1.0
        local idx = i - 1
        local rgb = entries[idx]
        local before = toHex(el, isByte)
        if rgb then
            if isByte then
                el.R = math.floor(rgb[1] * 255 + 0.5)
                el.G = math.floor(rgb[2] * 255 + 0.5)
                el.B = math.floor(rgb[3] * 255 + 0.5)
            else
                el.R = srgbToLinear(rgb[1])
                el.G = srgbToLinear(rgb[2])
                el.B = srgbToLinear(rgb[3])
            end
            log("%%s[%%d] %%s -> %%s", prop, idx, before, toHex(el, isByte))
        end
    end
    for idx, _ in pairs(entries) do
        if idx >= n then log("%%s has only %%d slots and can't take new ones; slot %%d ignored", prop, n, idx) end
    end
end

-- One line per table with the game's original colours, read by `wcmods` for the palette designer.
local function dumpTable(obj, prop)
    local ok, arr = pcall(function() return obj[prop] end)
    if not ok or arr == nil or not arr.GetArrayNum then return end
    local parts = {}
    for i = 1, arr:GetArrayNum() do
        local el = arr[i]
        local isByte = math.type(el.R) == "integer" or el.R > 1.0 or el.G > 1.0 or el.B > 1.0
        parts[#parts + 1] = toHex(el, isByte)
    end
    log("TABLE %%s %%d %%s", prop, #parts, table.concat(parts, " "))
end

-- Cats already set up before the tables grew picked no colour for a new slot: set them up again. Only
-- cats whose coat slot is one the game has (a coat slot past it crashes the game's set-up).
local function refreshCats(obj)
    local fur = obj.FurColors:GetArrayNum()
    local pat, mark = gameSize.PatternMaskColors or GAME_SLOTS, gameSize.MarkingMaskColors or GAME_SLOTS
    local count = 0
    for _, comp in ipairs(FindAllOf("SwtAdventureCustomizableMeshComponent") or {}) do
        pcall(function()
            local d = comp.CustomData
            if (d.Pattern01ColorIdx >= pat or d.Pattern02ColorIdx >= mark) and d.FurColorIdx >= 0 and d.FurColorIdx < fur then
                comp:RefreshShape()
                count = count + 1
            end
        end)
    end
    if count > 0 then log("refreshed %%d cat(s) wearing new colour slots", count) end
end

local function patchObject(obj)
    log("patching %%s (class %%s)", obj:GetFullName(), obj:GetClass():GetFullName())
    for _, prop in ipairs(ORDER) do
        dumpTable(obj, prop)
        patchArray(obj, prop, PALETTE[prop] or {})
    end
    pcall(refreshCats, obj)
end

-- Fallback: find every class that declares FurColors and add it to CLASSES.
local function searchOwners()
    local found = {}
    ForEachUObject(function(obj)
        local okc, isClass = pcall(function() return obj:IsClass() end)
        if okc and isClass then
            pcall(function()
                obj:ForEachProperty(function(p)
                    if p:GetFName():ToString() == "FurColors" then
                        found[#found + 1] = obj:GetFName():ToString()
                        log("FurColors is declared on %%s", obj:GetFullName())
                    end
                end)
            end)
        end
    end)
    for _, name in ipairs(found) do table.insert(CLASSES, 1, name) end
    if #found == 0 then log("no loaded class declares FurColors yet") end
end

local function tryPatch()
    attempts = attempts + 1
    local any = false
    for _, cls in ipairs(CLASSES) do
        local objs = FindAllOf(cls)
        if objs then
            for _, obj in ipairs(objs) do
                if obj:IsValid() then
                    any = true
                    local addr = obj:GetAddress()
                    if not patched[addr] then
                        patched[addr] = true
                        patchObject(obj)
                    end
                end
            end
        end
    end
    if not any and not searched and attempts >= 10 then
        searched = true
        log("none of %%s found after %%d tries; searching classes", table.concat(CLASSES, ", "), attempts)
        searchOwners()
    end
end

LoopAsync(2000, function()
    ExecuteInGameThread(function()
        local ok, err = pcall(tryPatch)
        if not ok then log("error: %%s", tostring(err)) end
    end)
    return false
end)
log("loaded")
'''


def ue4ss_script(merged):
    lines = []
    for section, prop in RUNTIME_SECTIONS.items():
        entries = merged.get(section, {})
        body = ", ".join(f"[{int(k)}] = {{{c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f}}}"
                         for k, c in sorted(entries.items(), key=lambda kv: int(kv[0])))
        lines.append(f"    {prop} = {{ {body} }},")
    return LUA_TEMPLATE % {"tables": "\n".join(lines), "game_slots": GAME_SLOTS}
