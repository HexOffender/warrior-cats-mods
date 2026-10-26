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
from .lua import source as lua_source

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


LUA_TEMPLATE = lua_source("catcolours.lua")
