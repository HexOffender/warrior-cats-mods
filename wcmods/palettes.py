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
"""
import json
import os

from . import colors
from .lua import source as lua_source

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


LUA_TEMPLATE = lua_source("palettes.lua")


def ue4ss_script(merged):
    lines = []
    for section, prop in RUNTIME_SECTIONS.items():
        entries = merged.get(section, {})
        body = ", ".join(f"[{int(k)}] = {{{c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f}}}"
                         for k, c in sorted(entries.items(), key=lambda kv: int(kv[0])))
        lines.append(f"    {prop} = {{ {body} }},")
    return LUA_TEMPLATE % {"tables": "\n".join(lines), "game_slots": GAME_SLOTS}
