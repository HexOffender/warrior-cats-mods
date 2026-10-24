"""Your cat's own look (cats.json): colours just your cat wears, and which colour slots it uses.

    { "player": { "colours": { "fur": "#9fb6e0", "paws": "#ffb6c1", "ears": "#ff9aa6", "nose": "#ff7b9a",
                               "whiskers": "#ffffff" },
                  "slots": { "fur": 11, "pattern": 25, "marking": 26 } } }

- "colours" go straight onto your cat's materials while you play, by a UE4SS script, so no other cat
  changes and any colour works. Each part is a vector parameter of the cat's body materials (below).
  The game sets those from the cat's slots whenever it sets the cat up, so the script puts yours back
  each time. Coat colours can't take new slots (palettes.py explains why), so this is how your cat gets
  a coat colour of its own; paws, ears, nose and whiskers have no slots at all.
- "slots" sets which slot of the game's colour tables your cat wears, written into your save on install
  (after a backup): fur 0-24, pattern and marking any slot, new ones a palette adds (25 and up) too.
  The save keeps them in the cat's text: FurColorIdx, Pattern01ColorIdx (pattern colour) and
  Pattern02ColorIdx (marking colour).

Your cat is found by its name IDs: your character's in the world, and before that (the main menu,
where there's no character yet) the ones in your save when the mods were installed. Copies of your
cat for portraits and thumbnails get your colours too, and their pictures are taken again.
"debug_cat_look": true in wcmods.json makes the script log every cat it sees and whether it's yours.
"""
import re

from . import colors
from .palettes import GAME_SLOTS

UE4SS_MOD_NAME = "WCModsCatLook"
PARTS = {"fur": "Fur Color", "paws": "Paws Color", "ears": "Ears Color", "nose": "Nose Color",
         "whiskers": "Whiskers Color"}
SLOTS = {"fur": "FurColorIdx", "pattern": "Pattern01ColorIdx", "marking": "Pattern02ColorIdx"}
FERAL_SLOTS = range(20, 25)   # the game swaps these coat slots for others unless you own the Feral Edition
TARGETS = ("player",)


def validate(raw, where="cats.json"):
    """Check a cats.json; returns {"player": {"colours": {part: (r, g, b)}, "slots": {part: int}}}."""
    if not isinstance(raw, dict):
        raise ValueError(f"{where} should be an object")
    out = {}
    for target, look in raw.items():
        if target.startswith("_"):
            continue
        if target not in TARGETS:
            raise ValueError(f"{where}: '{target}' isn't a cat it can change yet (use \"player\")")
        if not isinstance(look, dict):
            raise ValueError(f"{where}: {target} should be an object with \"colours\" and/or \"slots\"")
        one = {"colours": {}, "slots": {}}
        for key, value in look.items():
            if key.startswith("_"):
                continue
            if key not in ("colours", "slots") or not isinstance(value, dict):
                raise ValueError(f"{where}: {target}.{key} should be \"colours\" or \"slots\", each an object")
            for part, v in value.items():
                if part.startswith("_"):
                    continue
                if key == "colours":
                    if part not in PARTS:
                        raise ValueError(f"{where}: {target}.colours.{part} should be one of {', '.join(PARTS)}")
                    one["colours"][part] = colors.parse(v)
                else:
                    if part not in SLOTS:
                        raise ValueError(f"{where}: {target}.slots.{part} should be one of {', '.join(SLOTS)}")
                    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                        raise ValueError(f"{where}: {target}.slots.{part} should be a slot number (0 or more)")
                    if part == "fur" and v >= GAME_SLOTS:
                        raise ValueError(f"{where}: {target}.slots.fur should be 0-{GAME_SLOTS - 1}; coats can't take "
                                         "new slots (set colours.fur instead)")
                    one["slots"][part] = v
        out[target] = one
    return out


def merge(items):
    """cats.json contents from several mods in priority order; later ones win part by part."""
    out = {}
    for data in items:
        for target, look in data.items():
            cur = out.setdefault(target, {"colours": {}, "slots": {}})
            cur["colours"].update(look["colours"])
            cur["slots"].update(look["slots"])
    return out


def set_fields(text, fields):
    """Set whole-number fields (FurColorIdx=11) inside a cat's save text, adding any it leaves out (the
    save leaves out fields at their default)."""
    for key, value in fields.items():
        field = re.compile(rf"(?<![A-Za-z0-9_]){key}=-?\d+")
        if field.search(text):
            text = field.sub(f"{key}={int(value)}", text, count=1)
        elif text.endswith(")"):
            text = f"{text[:-1]},{key}={int(value)})"
    return text


def script(colours, save_key="", debug=False):
    """The UE4SS script for colours: {part: (r, g, b) sRGB 0-1}. save_key is your cat's name IDs in the
    save ("STR_CAT_NAME53|_PAW"), how it finds your cat before you're in the world (the main menu)."""
    lines = []
    for part, rgb in sorted(colours.items()):
        lin = [colors.srgb_to_linear(c) for c in rgb]
        lines.append(f'    ["{PARTS[part]}"] = {{ {lin[0]:.5f}, {lin[1]:.5f}, {lin[2]:.5f} }},')
    return (LUA_TEMPLATE.replace("@COLOURS@", "\n".join(lines))
            .replace("@SAVE_KEY@", '"' + save_key.replace("\\", "").replace('"', "") + '"')
            .replace("@DEBUG@", "true" if debug else "false"))


def save_key(cats):
    """Your cat's name IDs as the script matches them, from cats_in_save(); "" without a player cat."""
    from .names import PLAYER_PATH
    for cat in cats:
        if PLAYER_PATH in cat["paths"]:
            return f'{cat["ids"].get("PrefixNameId", "")}|{cat["ids"].get("SuffixNameId", "")}'
    return ""


LUA_TEMPLATE = r'''-- Generated by wcmods from cats.json: colours only your cat wears. Do not edit; edit cats.json and rebuild.
-- They go onto your cat's own materials (the same vector parameters the game sets from its colour
-- slots), so other cats keep theirs. The game sets them again whenever it sets your cat up, so this
-- checks twice a second and puts yours back.
local COLOURS = {
@COLOURS@
}
-- Your cat's name IDs in the save when the mods were installed: how it's found before you're in the
-- world (the main menu). In the world, your character's own name IDs are used.
local SAVE_KEY = @SAVE_KEY@
local DEBUG = @DEBUG@
local MESHES = { "SkelMeshComp", "FurSkelMeshComp", "TailSkelMeshComp", "EarSkelMeshComp" }

local function log(fmt, ...) print(string.format("[WCModsCatLook] " .. fmt .. "\n", ...)) end
local function valid(o) return o ~= nil and o:IsValid() end
local function str(v) local ok, s = pcall(function() return v:ToString() end) return ok and s or tostring(v) end

local warned, said, seen = {}, false, {}

local function playerPawn()
    for _, c in ipairs(FindAllOf("PlayerController") or {}) do
        if valid(c) and valid(c.Player) and valid(c.Pawn) then return c.Pawn end
    end
end

-- A cat is matched by its name IDs, so your cat's portrait and menu copies get your colours too.
local function nameKey(comp)
    local d = comp.CustomData
    return str(d.PrefixNameId) .. "|" .. str(d.SuffixNameId)
end

local function paint(comp)
    local changed = 0
    for _, field in ipairs(MESHES) do
        local ok, mesh = pcall(function() return comp[field] end)
        if ok and valid(mesh) then
            for i = 0, mesh:GetNumMaterials() - 1 do
                local mat = mesh:GetMaterial(i)
                if valid(mat) then
                    local cls = mat:GetClass():GetFName():ToString()
                    if cls == "MaterialInstanceDynamic" then
                        local todo = {}
                        mat.VectorParameterValues:ForEach(function(_, e)
                            local v = e:get()
                            local pn = v.ParameterInfo.Name:ToString()
                            local want = COLOURS[pn]
                            if want then
                                local c = v.ParameterValue
                                if math.abs(c.R - want[1]) > 0.002 or math.abs(c.G - want[2]) > 0.002 or math.abs(c.B - want[3]) > 0.002 then
                                    todo[#todo + 1] = pn
                                end
                            end
                        end)
                        for _, pn in ipairs(todo) do
                            local want = COLOURS[pn]
                            mat:SetVectorParameterValue(FName(pn), { R = want[1], G = want[2], B = want[3], A = 1.0 })
                            changed = changed + 1
                        end
                    elseif not warned[cls] then
                        warned[cls] = true
                        log("a %s on your cat can't be recoloured (it's a %s)", field, cls)
                    end
                end
            end
        end
    end
    return changed
end

-- Portraits and thumbnails are pictures the game takes of a copy of your cat; once that copy has your
-- colours, take them again.
local function retake(owner)
    for _, field in ipairs({ "CaptureComponent", "CaptureComponentInventory" }) do
        pcall(function()
            local cap = owner[field]
            if valid(cap) then cap:CaptureScene() end
        end)
    end
end

local function tick()
    local comps = FindAllOf("SwtAdventureCustomizableMeshComponent") or {}
    local pawn, key = playerPawn(), SAVE_KEY
    if pawn then
        for _, comp in ipairs(comps) do
            local ok, owner = pcall(function() return comp:GetOwner() end)
            if ok and valid(owner) and owner:GetAddress() == pawn:GetAddress() then key = nameKey(comp) break end
        end
    end
    if key == "" then return end
    local total = 0
    for _, comp in ipairs(comps) do
        local ok, same = pcall(function() return nameKey(comp) == key end)
        local owner = nil
        pcall(function() owner = comp:GetOwner() end)
        if DEBUG and not seen[comp:GetAddress()] then
            seen[comp:GetAddress()] = true
            local okk, k = pcall(nameKey, comp)
            log("cat %s on %s: %s", okk and k or "?", valid(owner) and owner:GetClass():GetFName():ToString() or "?",
                (ok and same) and "yours" or "not yours")
        end
        if ok and same then
            local n = paint(comp)
            total = total + n
            if n > 0 and valid(owner) and owner:GetClass():GetFName():ToString():find("GuiCatCustom") then retake(owner) end
        end
    end
    if total > 0 and not said then
        said = true
        log("your cat's colours are on (%d set)", total)
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
'''
