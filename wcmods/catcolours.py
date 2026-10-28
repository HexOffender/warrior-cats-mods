"""Cats' own looks (cats.json): your cat's, and any cat's in your save by its name or place: colours just
that cat wears, which colour slots it uses, its scars, and its shape (body, ears, tail, pattern...).

    { "player": { "colours": { "fur": "#9fb6e0", "paws": "#ffb6c1", "ears": "#ff9aa6", "nose": "#ff7b9a",
                               "whiskers": "#ffffff" },
                  "slots": { "fur": 11, "pattern": 25, "marking": 26, "eyes": 3 },
                  "scars": { "ear": "notch-left", "eye": "claws-right", "back": "none" },
                  "look": { "body": 6, "ears": 2, "tail": 7, "pattern": 12, "size": 0.9 } },
      "cats": { "Bluestar": { "slots": { "fur": 18 }, "colours": { "nose": "#202020" } },
                "Clans/RiverClan/Warrior/3": { "look": { "fur": 9 } } } }

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
- "look" sets the cat's shape in your save the same way (LOOK): body, fur, tail, ears, eyes, whiskers and
  face are each one of the game's 10 (0-9; the cat maker shows a clan's 7 of them), pattern and marking
  one of its 21 (0-20), size a scale (the game's cats go from 0.1, a kit, to 1.0, a leader). Body,
  ears and face decided your cat's traits when it was made; the traits are kept in the save apart, so
  they stay. The game sets your cat's size by rank again when it ranks up.
- "cats" gives the same to other cats in your save, each by its name ("Bluestar") or its place as the
  Names page shows it ("Clans/RiverClan/Warrior/3"), with the game's slot first for a game other than the
  one being played ("2/Bluestar"), as names.json's "cats" picks them. Their colours go on by their name
  IDs as your cat's do (a rank-up changes a cat's name IDs: install again after one).

Your cat is your character in the world, plus the copies menus and portraits show (never another
cat in the world, even one with your name). Those copies must have your character's name IDs; before
the world, the main menu's cat and the cat choice's big cat need only the same name prefix, so a
rank-up doesn't lose them. The script remembers the IDs your character last had (yourcat.txt in its
UE4SS folder); until it has seen your character, it uses your save's from when the mods were installed.
The menus take their pictures of cats with actors every cat shares, and one's picture target can be
another cat's, so out of the world a picture actor gets colours only as the cat choice's big cat (the
small pictures there show saved colours), and in the world only the HUD's picture is taken again (at most
every 2 seconds). An actor that moves on to a cat without colours gets the game's back, as the game
doesn't set colours it thinks are there. Parts with no model yet (a cat being set up) are skipped.
"debug_cat_look": true in wcmods.json makes the script log every cat it sees and whether it's yours.
"""
import re

from . import colors
from .palettes import GAME_SLOTS
from .lua import source as lua_source

UE4SS_MOD_NAME = "WCModsCatLook"
PARTS = {"fur": "Fur Color", "paws": "Paws Color", "ears": "Ears Color", "nose": "Nose Color",
         "whiskers": "Whiskers Color"}
SLOTS = {"fur": "FurColorIdx", "pattern": "Pattern01ColorIdx", "marking": "Pattern02ColorIdx",
         "eye_left": "EyeLeftColorIdx", "eye_right": "EyeRightColorIdx"}
EYE_SLOTS = ("eye_left", "eye_right")    # "eyes" in cats.json sets both
# The cat's shape: the save's fields each part sets (the cat maker's body row sets the fur's shape to match),
# and the highest each takes (the game's NPC tables: 10 of each part, 21 patterns and markings).
LOOK = {"body": ("BodyValue", "FurIdx"), "fur": ("FurValue",), "tail": ("TailIdx",), "ears": ("EarIdx",),
        "eyes": ("EyeValue",), "whiskers": ("WhiskerValue",), "face": ("FaceValue",), "pattern": ("PatternIdx",),
        "marking": ("MarkingIdx",)}
LOOK_MAX = {"pattern": 20, "marking": 20}   # the others 9
SIZE = ("CatSize", 0.05, 1.5)
FERAL_SLOTS = range(20, 25)   # the game swaps these coat slots for others unless you own the Feral Edition
TARGETS = ("player", "cats")
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
    """Check a cats.json; returns {"player": one, "cats": {target: one}}, one being {"colours": {part: (r, g, b)},
    "slots": {part: int}, "scars": {part: number}, "look": {field: number}} (look by the save's fields)."""
    if not isinstance(raw, dict):
        raise ValueError(f"{where} should be an object")
    out = {}
    for target, look in raw.items():
        if target.startswith("_"):
            continue
        if target not in TARGETS:
            raise ValueError(f"{where}: '{target}' isn't something it knows (\"player\" for your cat, \"cats\" for others)")
        if target == "player":
            out["player"] = _one(look, f"{where}: player")
            continue
        if not isinstance(look, dict):
            raise ValueError(f'{where}: cats should be an object of cats by name or place, e.g. {{"Bluestar": {{...}}}}')
        cats = {}
        for name, one in look.items():
            if name.startswith("_"):
                continue
            if not name.strip() or name.strip().lower() in ("player", "you"):
                raise ValueError(f'{where}: cats.{name!r}: name a cat in your save (your own cat is "player", outside "cats")')
            cats[name.strip()] = _one(one, f"{where}: cats.{name}")
        out["cats"] = cats
    return out


def _one(look, where):
    """One cat's colours, slots, scars and look, checked."""
    if not isinstance(look, dict):
        raise ValueError(f'{where} should be an object with "colours", "slots", "scars" and/or "look"')
    one = {"colours": {}, "slots": {}, "scars": {}, "look": {}}
    for key, value in look.items():
        if key.startswith("_"):
            continue
        if key == "scars":
            one["scars"] = _scars(value, f"{where}.scars")
            continue
        if key not in ("colours", "slots", "look") or not isinstance(value, dict):
            raise ValueError(f'{where}.{key} should be "colours", "slots", "scars" or "look"')
        for part, v in value.items():
            if part.startswith("_"):
                continue
            if key == "colours":
                if part not in PARTS:
                    raise ValueError(f"{where}.colours.{part} should be one of {', '.join(PARTS)}")
                try:
                    one["colours"][part] = colors.parse(v)
                except ValueError as e:
                    raise ValueError(f"{where}.colours.{part}: {e}") from None
            elif key == "look":
                one["look"].update(_look(part, v, f"{where}.look.{part}"))
            else:
                if part not in SLOTS and part != "eyes":
                    raise ValueError(f"{where}.slots.{part} should be one of {', '.join(list(SLOTS) + ['eyes'])}")
                if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                    raise ValueError(f"{where}.slots.{part} should be a slot number (0 or more)")
                if part in ("fur", "eyes") + EYE_SLOTS and v >= GAME_SLOTS:
                    raise ValueError(f"{where}.slots.{part} should be 0-{GAME_SLOTS - 1}; only pattern and marking "
                                     "colours take new slots" + (" (set colours.fur instead)" if part == "fur" else ""))
                for p in (EYE_SLOTS if part == "eyes" else (part,)):
                    one["slots"][p] = v
    return one


def _look(part, v, where):
    """{save field: value} for one part of a cat's look."""
    if part == "size":
        field, lo, hi = SIZE
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise ValueError(f"{where} should be a scale from {lo:g} to {hi:g} (a kit is about 0.1, a leader 1.0)")
        return {field: float(v)}
    if part not in LOOK:
        raise ValueError(f"{where[:where.rindex('.')]} takes {', '.join(list(LOOK) + ['size'])}, not {part!r}")
    top = LOOK_MAX.get(part, 9)
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= top:
        raise ValueError(f"{where} should be one of the game's: 0 to {top}")
    return {field: v for field in LOOK[part]}


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
    """cats.json contents from several mods in priority order; later ones win part by part, cat by cat."""
    out = {}

    def add(into, look):
        for key in ("colours", "slots", "scars", "look"):
            into.setdefault(key, {}).update(look.get(key, {}))
    for data in items:
        if "player" in data:
            add(out.setdefault("player", {}), data["player"])
        for name, look in data.get("cats", {}).items():
            add(out.setdefault("cats", {}).setdefault(name, {}), look)
    return out


def fields_of(one):
    """{save field: value} that a cat's slots, scars and look set."""
    fields = {SLOTS[part]: slot for part, slot in one.get("slots", {}).items()}
    fields.update({SCARS[part]: n for part, n in one.get("scars", {}).items()})
    fields.update(one.get("look", {}))
    return fields


def set_fields(text, fields):
    """Set number fields (FurColorIdx=11, CatSize=0.900000) inside a cat's save text, adding any it leaves out
    (the save leaves out fields at their default). A float is written as the game writes one."""
    for key, value in fields.items():
        field = re.compile(rf"(?<![A-Za-z0-9_]){key}=-?\d+(\.\d+)?")
        written = f"{key}={value:.6f}" if isinstance(value, float) else f"{key}={int(value)}"
        if field.search(text):
            text = field.sub(written, text, count=1)
        elif text.endswith(")"):
            text = f"{text[:-1]},{written})"
    return text


LABELS = {"fur": "Coat", "paws": "Paw pads", "ears": "Inner ears", "nose": "Nose", "whiskers": "Whiskers"}


def name_key(cat):
    """A cat's name IDs as the script matches them ("STR_CAT_NAME53|_PAW"), from cats_in_save()."""
    return f'{cat["ids"].get("PrefixNameId", "")}|{cat["ids"].get("SuffixNameId", "")}'


def _colour_lines(colours, indent):
    out = []
    for part, rgb in sorted(colours.items()):
        lin = [colors.srgb_to_linear(c) for c in rgb]
        out.append(f'{indent}["{PARTS[part]}"] = {{ {lin[0]:.5f}, {lin[1]:.5f}, {lin[2]:.5f} }},')
    return out


def script(colours, save_key="", key_file="", debug=False, save=None, others=None):
    """The UE4SS script for colours: {part: (r, g, b) sRGB 0-1}. save_key is your cat's name IDs in the
    save ("STR_CAT_NAME53|_PAW"), how it finds your cat before you're in the world (the main menu);
    key_file is where it remembers the IDs your character last had, which win once known. save is where
    the in-game menu's Save writes: {"path": the mod's cats.json, "file": its name for the player,
    "doc": that file's contents, whose player colours Save replaces}. others: {name key: colours} for
    other cats, found by their name IDs wherever they are (the world, the clan's menus, portraits)."""
    from .sdk import lua_value
    lines = _colour_lines(colours, "    ")
    other_lines = []
    for key, cols in sorted((others or {}).items()):
        other_lines += [f"    [{lua_value(key)}] = {{"] + _colour_lines(cols, "        ") + ["    },"]
    parts = [{"id": p, "param": PARTS[p], "label": LABELS[p],
              "hex": "#%02x%02x%02x" % tuple(round(c * 255) for c in colours[p]) if p in colours else None}
             for p in PARTS]

    def lua_str(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return (LUA_TEMPLATE.replace("@COLOURS@", "\n".join(lines)).replace("@OTHERS@", "\n".join(other_lines))
            .replace("@SAVE_KEY@", lua_str(save_key)).replace("@KEY_FILE@", lua_str(key_file))
            .replace("@DEBUG@", "true" if debug else "false")
            .replace("@PARTS@", lua_value(parts)).replace("@SAVE@", lua_value(save)))


def save_key(cats):
    """Your cat's name IDs as the script matches them, from cats_in_save(): the player cat of the game being
    played (a save holds one per cat slot started); "" without one."""
    for cat in cats:
        if cat["player"] and cat["current"]:
            return name_key(cat)
    return ""


LUA_TEMPLATE = lua_source("catcolours.lua")
