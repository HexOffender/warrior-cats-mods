"""Your cat's own look (cats.json): colours just your cat wears, which colour slots it uses, and its scars.

    { "player": { "colours": { "fur": "#9fb6e0", "paws": "#ffb6c1", "ears": "#ff9aa6", "nose": "#ff7b9a",
                               "whiskers": "#ffffff" },
                  "slots": { "fur": 11, "pattern": 25, "marking": 26 },
                  "scars": { "ear": "notch-left", "eye": "claws-right", "back": "none" } } }

- "colours" go straight onto your cat's materials while you play, by a UE4SS script, so no other cat
  changes and any colour works. Each part is a vector parameter of the cat's body materials (below).
  The game sets those from the cat's slots whenever it sets the cat up, so the script puts yours back
  each time. Coat colours can't take new slots (palettes.py explains why), so this is how your cat gets
  a coat colour of its own; paws, ears, nose and whiskers have no slots at all.
- "slots" sets which slot of the game's colour tables your cat wears, written into your save on install
  (after a backup): fur 0-24, pattern and marking any slot, new ones a palette adds (25 and up) too.
  The save keeps them in the cat's text: FurColorIdx, Pattern01ColorIdx (pattern colour) and
  Pattern02ColorIdx (marking colour).
- "scars" chooses your cat's scars, written into your save on install the same way: "none" for no
  scars at all, or each place on its own (one left out keeps your save's). The save keeps them as
  ScarEyeId, ScarEarId, ScarBodyId (the back) and ScarChestId, 0 for none; SCAR_TYPES has what
  each place can be, by name or number (docs/reverse-engineering.md, "Scars").

Your cat is your character in the world, plus the copies menus and portraits show (never another
cat in the world, even one with your name). In the world those copies must have your character's name
IDs; before that (the main menu, with no character yet) the same name prefix, so a rank-up doesn't
lose them. The script remembers the IDs your character last had (yourcat.txt in its UE4SS folder);
until it has seen your character, it uses your save's from when the mods were installed. Copies'
pictures (portraits, thumbnails) are taken again, at most every 2 seconds.
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
SCARS = {"eye": "ScarEyeId", "ear": "ScarEarId", "back": "ScarBodyId", "chest": "ScarChestId"}
# Every scar each place can have: (name, what it looks like), scar n being the n-th. Ears are the game's torn
# and notched ear models (seen in game); an eye scar shuts the eye, odd numbers the cat's right eye and even its
# left (seen in game); the back has a bite and claw marks in two spots (which spot is where isn't known yet);
# the chest a bite or claw marks. The shapes are read off the scar texture's cells in order, and only the
# first eye scar and the claw marks were seen in game. The back's 5 and 6 seem to show nothing (the texture has
# no third back scar), so they aren't offered; the game's numbers are still taken (SCAR_GAME_MAX).
SCAR_TYPES = {
    "ear": [("torn-right", "Torn, right"), ("torn-left", "Torn, left"), ("torn-both", "Torn, both"),
            ("notch-right", "Notched, right"), ("notch-left", "Notched, left"), ("notch-both", "Notched, both")],
    "eye": [("ring-right", "Scar ring, right eye"), ("ring-left", "Scar ring, left eye"),
            ("slash-right", "Slash, right eye"), ("slash-left", "Slash, left eye"),
            ("claws-right", "Claw marks, right eye"), ("claws-left", "Claw marks, left eye")],
    "back": [("bite-1", "Bite, spot 1"), ("bite-2", "Bite, spot 2"), ("claws-1", "Claw marks, spot 1"),
             ("claws-2", "Claw marks, spot 2")],
    "chest": [("bite", "Bite"), ("claws", "Claw marks")],
}
SCAR_NAMES = {part: {name: i + 1 for i, (name, _) in enumerate(types)} for part, types in SCAR_TYPES.items()}
SCAR_GAME_MAX = {"ear": 6, "eye": 6, "back": 6, "chest": 2}   # the numbers the game takes; past SCAR_TYPES, a warning


def validate(raw, where="cats.json"):
    """Check a cats.json; returns {"player": {"colours": {part: (r, g, b)}, "slots": {part: int},
    "scars": {part: number}}}."""
    if not isinstance(raw, dict):
        raise ValueError(f"{where} should be an object")
    out = {}
    for target, look in raw.items():
        if target.startswith("_"):
            continue
        if target not in TARGETS:
            raise ValueError(f"{where}: '{target}' isn't a cat it can change yet (use \"player\")")
        if not isinstance(look, dict):
            raise ValueError(f"{where}: {target} should be an object with \"colours\", \"slots\" and/or \"scars\"")
        one = {"colours": {}, "slots": {}, "scars": {}}
        for key, value in look.items():
            if key.startswith("_"):
                continue
            if key == "scars":
                one["scars"] = _scars(value, f"{where}: {target}.scars")
                continue
            if key not in ("colours", "slots") or not isinstance(value, dict):
                raise ValueError(f"{where}: {target}.{key} should be \"colours\", \"slots\" or \"scars\"")
            for part, v in value.items():
                if part.startswith("_"):
                    continue
                if key == "colours":
                    if part not in PARTS:
                        raise ValueError(f"{where}: {target}.colours.{part} should be one of {', '.join(PARTS)}")
                    try:
                        one["colours"][part] = colors.parse(v)
                    except ValueError as e:
                        raise ValueError(f"{where}: {target}.colours.{part}: {e}") from None
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


def _scars(value, where):
    """{part: number} for "none" (no scars) or {"ear": "notch-left", "eye": 3, "back": "none", ...}: a
    scar by its name or number (SCAR_TYPES)."""
    if value == "none":
        return {part: 0 for part in SCARS}
    if not isinstance(value, dict):
        raise ValueError(f'{where} should be "none", or e.g. {{"ear": "notch-left", "eye": 3, "back": "none"}}')
    if "body" in value and "back" in value:
        raise ValueError(f'{where}: "body" and "back" are the same place (the save calls the back "body"); give one')
    out = {}
    for part, v in value.items():
        if part.startswith("_"):
            continue
        if part == "body":   # the save's name for the back
            part = "back"
        if part not in SCARS:
            raise ValueError(f"{where}.{part} should be one of {', '.join(SCARS)}")
        top = SCAR_GAME_MAX[part]
        if v == "none":
            v = 0
        elif isinstance(v, str) and v in SCAR_NAMES[part]:
            v = SCAR_NAMES[part][v]
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= top:
            raise ValueError(f'{where}.{part} should be "none", {", ".join(SCAR_NAMES[part])}, or 1 to '
                             f'{len(SCAR_TYPES[part])}')
        out[part] = v
    return out


def merge(items):
    """cats.json contents from several mods in priority order; later ones win part by part."""
    out = {}
    for data in items:
        for target, look in data.items():
            cur = out.setdefault(target, {"colours": {}, "slots": {}, "scars": {}})
            cur["colours"].update(look["colours"])
            cur["slots"].update(look["slots"])
            cur["scars"].update(look["scars"])
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


LABELS = {"fur": "Coat", "paws": "Paw pads", "ears": "Inner ears", "nose": "Nose", "whiskers": "Whiskers"}


def script(colours, save_key="", key_file="", debug=False, save=None):
    """The UE4SS script for colours: {part: (r, g, b) sRGB 0-1}. save_key is your cat's name IDs in the
    save ("STR_CAT_NAME53|_PAW"), how it finds your cat before you're in the world (the main menu);
    key_file is where it remembers the IDs your character last had, which win once known. save is where
    the in-game menu's Save writes: {"path": the mod's cats.json, "file": its name for the player,
    "doc": that file's contents, whose player colours Save replaces}."""
    from .sdk import lua_value
    lines = []
    for part, rgb in sorted(colours.items()):
        lin = [colors.srgb_to_linear(c) for c in rgb]
        lines.append(f'    ["{PARTS[part]}"] = {{ {lin[0]:.5f}, {lin[1]:.5f}, {lin[2]:.5f} }},')
    parts = [{"id": p, "param": PARTS[p], "label": LABELS[p],
              "hex": "#%02x%02x%02x" % tuple(round(c * 255) for c in colours[p]) if p in colours else None}
             for p in PARTS]

    def lua_str(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return (LUA_TEMPLATE.replace("@COLOURS@", "\n".join(lines))
            .replace("@SAVE_KEY@", lua_str(save_key)).replace("@KEY_FILE@", lua_str(key_file))
            .replace("@DEBUG@", "true" if debug else "false")
            .replace("@PARTS@", lua_value(parts)).replace("@SAVE@", lua_value(save)))


def save_key(cats):
    """Your cat's name IDs as the script matches them, from cats_in_save(): the player cat of the game being
    played (a save holds one per cat slot started); "" without one."""
    for cat in cats:
        if cat["player"] and cat["current"]:
            return f'{cat["ids"].get("PrefixNameId", "")}|{cat["ids"].get("SuffixNameId", "")}'
    return ""


LUA_TEMPLATE = r'''-- Generated by wcmods from cats.json: colours only your cat wears. Do not edit; edit cats.json and rebuild.
-- They go onto your cat's own materials (the same vector parameters the game sets from its colour
-- slots), so other cats keep theirs. The game sets them again whenever it sets your cat up, so this
-- checks twice a second and puts yours back.
local COLOURS = {
@COLOURS@
}
-- How your cat is found. In the world: your character, plus menu and portrait copies with its name IDs.
-- Before that (the main menu) there's no character, so menu copies are matched on the name's prefix
-- (a rank-up changes only the suffix), taken from the IDs your character last had (remembered in
-- KEY_FILE), or else from your save when the mods were installed.
local SAVE_KEY = @SAVE_KEY@
local KEY_FILE = @KEY_FILE@
local DEBUG = @DEBUG@
local MESHES = { "SkelMeshComp", "FurSkelMeshComp", "TailSkelMeshComp", "EarSkelMeshComp" }
-- Actors that show a copy of your cat in menus, portraits and thumbnails (never cats in the world).
local MENU_ACTORS = { "CatCustomActor", "MainMenu", "Customization_Player" }
local RETAKE_TICKS = 4   -- take a copy's pictures again at most every 2 seconds

local function log(fmt, ...) print(string.format("[WCModsCatLook] " .. fmt .. "\n", ...)) end
local function valid(o) return o ~= nil and o:IsValid() end
local function str(v) local ok, s = pcall(function() return v:ToString() end) return ok and s or tostring(v) end

local warned, said, seen, retaken, ticks = {}, false, {}, {}, 0
local known = SAVE_KEY
if io and KEY_FILE ~= "" then
    local f = io.open(KEY_FILE, "r")
    if f then
        local s = f:read("*l")
        f:close()
        if s and s ~= "" then known = s end
    end
end

local function remember(key)
    if key == known then return end
    known = key
    if io and KEY_FILE ~= "" then
        local f = io.open(KEY_FILE, "w")
        if f then f:write(key) f:close() end
    end
end

local function prefixOf(key) return key:match("^([^|]*)") or "" end

local function isMenuActor(owner)
    local cls = owner:GetClass():GetFName():ToString()
    for _, part in ipairs(MENU_ACTORS) do
        if cls:find(part, 1, true) then return true end
    end
    return false
end

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
    ticks = ticks + 1
    local comps = FindAllOf("SwtAdventureCustomizableMeshComponent") or {}
    local pawn, mine = playerPawn(), nil
    if pawn then
        for _, comp in ipairs(comps) do
            local ok, owner = pcall(function() return comp:GetOwner() end)
            if ok and valid(owner) and owner:GetAddress() == pawn:GetAddress() then mine = comp break end
        end
    end
    if mine then remember(nameKey(mine)) end
    if known == "" then return end
    local total = 0
    for _, comp in ipairs(comps) do
        local owner = nil
        pcall(function() owner = comp:GetOwner() end)
        local yours = false
        if mine and comp:GetAddress() == mine:GetAddress() then
            yours = true
        elseif valid(owner) and isMenuActor(owner) then
            local ok, key = pcall(nameKey, comp)
            -- In the world, a menu copy must have your full name IDs; before it, the same prefix.
            yours = ok and (mine and key == known or (not mine and prefixOf(key) ~= "" and prefixOf(key) == prefixOf(known)))
        end
        if DEBUG and not seen[comp:GetAddress()] then
            seen[comp:GetAddress()] = true
            local okk, k = pcall(nameKey, comp)
            log("cat %s on %s: %s", okk and k or "?", valid(owner) and owner:GetClass():GetFName():ToString() or "?",
                yours and "yours" or "not yours")
        end
        if yours then
            local n = paint(comp)
            total = total + n
            if n > 0 and valid(owner) and isMenuActor(owner) then
                local at = owner:GetAddress()
                if not retaken[at] or ticks - retaken[at] >= RETAKE_TICKS then
                    retaken[at] = ticks
                    retake(owner)
                end
            end
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

-- A page in the mod menu (Insert): change your cat's colours while you play. A part you switch off
-- keeps the colour it has until the game sets your cat up again (a new area, the main menu).
local PARTS = @PARTS@
local SAVE = @SAVE@
-- The page is extra: if the menu can't load or add it, the script works as before.
local okMenu, Menu = pcall(require, "WCModsMenu")
if okMenu then pcall(function()
    local installed, status = {}, nil
    for _, p in ipairs(PARTS) do installed[p.id] = p.hex end
    local function apply(p)
        if p.hex then
            local c = Menu.color(p.hex)
            COLOURS[p.param] = { c.R, c.G, c.B }
        else
            COLOURS[p.param] = nil
        end
    end
    Menu.page("Colours", function(ui)
        ui.heading("Your cat's colours")
        ui.note("Only your cat wears these. Changes show within half a second." ..
                (SAVE and (" Save writes them to " .. SAVE.file .. ", so installing again keeps them.") or ""))
        for _, p in ipairs(PARTS) do
            local on = ui.switch(p.label, p.hex ~= nil)
            if on and not p.hex then
                p.hex = p.last or "#a0a0a0"
                apply(p)
            elseif not on and p.hex then
                p.last, p.hex = p.hex, nil
                apply(p)
            end
            if p.hex then
                local hex = ui.color("   colour", p.hex)
                if hex ~= p.hex then
                    p.hex = hex
                    apply(p)
                end
            end
        end
        ui.space(6)
        local hit = ui.buttons(SAVE and { "Save", "Back to installed" } or { "Back to installed" }, { kinds = { "primary" } })
        if hit and SAVE and hit == 1 then
            local doc = SAVE.doc or {}
            doc.player = doc.player or {}
            local out = {}
            for _, p in ipairs(PARTS) do
                if p.hex then out[p.id] = p.hex end
            end
            doc.player.colours = out
            local ok, err = Menu.saveJson(SAVE.path, doc)
            status = ok and ("Saved to " .. SAVE.file .. ".") or ("Couldn't save: " .. tostring(err))
        elseif hit then
            for _, p in ipairs(PARTS) do
                p.hex = installed[p.id]
                apply(p)
            end
            status = "Back to the installed colours."
        end
        if status then ui.note(status) end
    end, { order = 11, group = "cat" })
end) end
'''
