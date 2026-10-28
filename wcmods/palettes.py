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
slot without them crashes it, so cats.json colours just your cat's coat instead (see catcolours.py).

"coats" are coat presets instead, painted on rather than slots: a name, its coat colour and, if it
likes, its nose, paw, whisker and ear colours, and "like", the game's coat a cat wearing it is saved
with (so the save only ever holds the game's coats):
    "coats": {"Ash": {"fur": "#9a9590", "nose": "#3a3330", "paws": "#4a4442", "ears": "#b8a0a0", "like": 12}}
wcmods doesn't paint them itself: it lists them for scripts (WCModsPalettes, slot_groups), and the
Creator palettes mod offers them in the cat maker and paints them on the cats that chose them.
"""
import json
import os

from . import colors
from .lua import source as lua_source

RUNTIME_SECTIONS = {"fur": "FurColors", "pattern": "PatternMaskColors",
                    "marking": "MarkingMaskColors", "iris_ui": "IrisColors"}
SECTIONS = ("eyes",) + tuple(RUNTIME_SECTIONS) + ("coats",)
COAT_PARTS = ("fur", "nose", "paws", "whiskers", "ears")   # a coat preset's colours; "fur" is the one it needs
GAME_SLOTS = 25                       # entries in each of the game's colour tables
GROWABLE = ("pattern", "marking")     # sections whose tables can take slots past GAME_SLOTS


def load(path):
    """The palette in a palette.json, its colours parsed. ValueError says what's wrong with one (it's never
    anything else: the studio lists a mod with a bad palette.json, with the problem on its card)."""
    with open(path, encoding="utf-8-sig") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f'{path}: a palette is an object of sections, e.g. {{"fur": {{"3": "#ff7a1a"}}}}')
    out = {}
    for section, entries in raw.items():
        if section.startswith("_") or section in ("name", "description"):
            continue
        if section not in SECTIONS:
            raise ValueError(f"{path}: unknown palette section '{section}' (use {', '.join(SECTIONS)})")
        if section == "coats":
            out["coats"] = _coats(entries, path)
            continue
        if not isinstance(entries, dict):
            raise ValueError(f'{path}: {section} should be an object of colours by slot, e.g. {{"3": "#ff7a1a"}}'
                             if section != "eyes" else f'{path}: eyes should be an object of colours by slot name, '
                             'e.g. {"Amber": "#ffb300"}')
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


def _coats(entries, path):
    """{name: {"fur": rgb, ... "like": n}} for a palette's coat presets, checked."""
    if not isinstance(entries, dict):
        raise ValueError(f'{path}: coats should be an object of presets by name, e.g. {{"Ash": {{"fur": "#9a9590", '
                         '"like": 12}}}}')
    out = {}
    for name, spec in entries.items():
        if str(name).startswith("_"):
            continue
        where = f"{path}: coats.{name}"
        if not str(name).strip() or str(name) != str(name).strip() or len(str(name)) > 40 or "/" in str(name):
            raise ValueError(f"{where}: a preset's name is up to 40 characters, without / or spaces at its ends")
        if not isinstance(spec, dict):
            raise ValueError(f'{where} should be an object: {{"fur": "#9a9590", "like": 12}}')
        unknown = sorted(k for k in spec if k not in COAT_PARTS + ("like",) and not str(k).startswith("_"))
        if unknown:
            raise ValueError(f"{where}: unknown key(s) {', '.join(unknown)} (it takes {', '.join(COAT_PARTS)} and like)")
        if "fur" not in spec:
            raise ValueError(f'{where}: "fur" (its coat colour) is missing')
        like = spec.get("like")
        if isinstance(like, bool) or not isinstance(like, int) or not 0 <= like < GAME_SLOTS:
            raise ValueError(f'{where}: "like" should be one of the game\'s coats, 0-{GAME_SLOTS - 1}: the one a cat '
                             "wearing it is saved with")
        preset = {"like": like}
        for part in COAT_PARTS:
            if part in spec:
                try:
                    preset[part] = colors.parse(spec[part])
                except ValueError as e:
                    raise ValueError(f"{where}.{part}: {e}") from None
        out[str(name)] = preset
    return out


def new_slots(palette):
    """{section: [slot, ...]} for the slots past the game's that a loaded palette adds."""
    return {s: sorted(int(k) for k in palette.get(s, {}) if int(k) >= GAME_SLOTS) for s in GROWABLE
            if any(int(k) >= GAME_SLOTS for k in palette.get(s, {}))}


def adds_only(palette):
    """True for a palette that only adds new slots or coat presets: it changes no colour the game already has."""
    return bool(new_slots(palette) or palette.get("coats")) and not palette.get("eyes") and all(
        int(k) >= GAME_SLOTS for s in RUNTIME_SECTIONS for k in palette.get(s, {}))


GROUPS_LUA = "WCModsPalettes"   # the shared Lua module that says which palette added which new slots


def slot_groups(items):
    """[{"id", "name", "pattern": [slot, ...], "marking": [...], "coats": [...]}]: the new slots and coat presets
    each palette mod adds, for a script that shows them palette by palette (the Creator palettes mod). `items` is
    [(mod, loaded palette)] in priority order; a slot two palettes set is the one's that wins it (the later), as
    merge() keeps its colour. A coat preset is {"id": "<mod id>/<name>", "name", "like", "fur": "#rrggbb", and the
    nose, paws, whiskers and ears it sets}. Mods that add none are left out."""
    owner = {s: {} for s in GROWABLE}
    for mod, pal in items:
        for s in GROWABLE:
            for k in pal.get(s, {}):
                if int(k) >= GAME_SLOTS:
                    owner[s][int(k)] = mod.id
    out = []
    for mod, pal in items:
        group = {"id": mod.id, "name": getattr(mod, "name", mod.id),
                 **{s: sorted(k for k, m in owner[s].items() if m == mod.id) for s in GROWABLE}}
        group["coats"] = [{"id": f"{mod.id}/{name}", "name": name, "like": preset["like"],
                           **{part: colors.hex_from_srgb(preset[part]) for part in COAT_PARTS if part in preset}}
                          for name, preset in pal.get("coats", {}).items()]
        if any(group[s] for s in GROWABLE) or group["coats"]:
            out.append(group)
    return out


def groups_module(groups):
    """The Lua module listing slot_groups(): require("WCModsPalettes") gives that list."""
    from .sdk import lua_value
    return ("-- Generated by wcmods: each enabled palette's new pattern and marking colour slots (palette.json, 25 and\n"
            "-- up) and coat presets, in priority order, for scripts that show them palette by palette. Do not edit.\n"
            "return " + lua_value(groups) + "\n")


def merge(palettes):
    """The colours every palette sets, the later one's where two set the same. Coat presets aren't colours of the
    game's: slot_groups() lists them, each under its own palette."""
    merged = {s: {} for s in SECTIONS if s != "coats"}
    for pal in palettes:
        for section, entries in pal.items():
            if section != "coats":
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


LUA_TEMPLATE = lua_source("palettes.lua")


def ue4ss_script(merged):
    lines = []
    for section, prop in RUNTIME_SECTIONS.items():
        entries = merged.get(section, {})
        body = ", ".join(f"[{int(k)}] = {{{c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f}}}"
                         for k, c in sorted(entries.items(), key=lambda kv: int(kv[0])))
        lines.append(f"    {prop} = {{ {body} }},")
    return LUA_TEMPLATE % {"tables": "\n".join(lines), "game_slots": GAME_SLOTS}
