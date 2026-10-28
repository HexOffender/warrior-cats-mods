"""Tweaks (tweaks.json): small changes while you play, ticked on the studio's Tweaks page, with no code of the
mod's own. Like mouse look, the mod holds data and the script that acts on it is wcmods' own (lua/tweaks.lua,
with WCModsGame), so it needs no "Allow mods that run code":

    { "keep_stamina_full": true, "heal_key": "F5", "hold_time": false, "time_of_day": 12.0,
      "min_fresh_kill": 20, "skip_scenes": false }

Every key is optional, and a missing one is off. The tweaks and what they do are Game Tweaks' (the example script
in wcmods-examples), and its way of skipping the story's scenes is Sandbox mode's.
"""
from .lua import source as lua_source

UE4SS_MOD_NAME = "WCModsTweaks"
FILE = "tweaks.json"
DEFAULTS = {
    "keep_stamina_full": False,   # stamina topped up twice a second
    "heal_key": "",               # a key that fills health and stamina; "" for none
    "hold_time": False,           # the clock held at time_of_day
    "time_of_day": 12.0,          # hours, 0 to 24
    "min_fresh_kill": 0,          # the camp's fresh-kill pile kept at least this full (0 to 100); 0 is off
    "skip_scenes": False,         # each of the story's scenes skipped as it starts, with the game's own skip
}
# Keys a heal can go on: F1 to F12, but F10 (the game's own command window opens on it when that's on) and F11
# (full screen); the mod menu's own key is refused too (validate).
HEAL_KEYS = tuple(f"F{n}" for n in range(1, 13) if n not in (10, 11))


def validate(raw, menu_key=None):
    """Check a tweaks.json and return the tweaks it sets ("_" keys are notes, left out); a ValueError says what's
    wrong in a sentence. menu_key: the mod menu's key (wcmods.json), which a heal key can't share."""
    if not isinstance(raw, dict):
        raise ValueError(f'{FILE} should be an object, like {{"keep_stamina_full": true}}')
    out = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if key not in DEFAULTS:
            raise ValueError(f"{FILE}: there's no tweak called '{key}' (there are {', '.join(DEFAULTS)})")
        default = DEFAULTS[key]
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError(f"{FILE}: '{key}' should be true or false")
        elif key == "heal_key":
            if value != "" and value not in HEAL_KEYS:
                raise ValueError(f"{FILE}: 'heal_key' should be one of {', '.join(HEAL_KEYS)}, or \"\" for none")
            if value and value == menu_key:
                raise ValueError(f"{FILE}: 'heal_key' is {value}, the mod menu's own key: pick another")
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{FILE}: '{key}' should be a number")
            if key == "time_of_day":
                if not 0 <= value <= 24:
                    raise ValueError(f"{FILE}: 'time_of_day' should be from 0 to 24 (hours)")
                value = float(value)
            elif key == "min_fresh_kill":
                if not 0 <= value <= 100:
                    raise ValueError(f"{FILE}: 'min_fresh_kill' should be from 0 to 100 (the pile's own range)")
                value = int(round(value))
        out[key] = value
    return out


def merge(items):
    """The tweaks of several mods, in priority order: each key from the last mod that sets it."""
    settings = dict(DEFAULTS)
    for data in items:
        settings.update(data)
    return settings


def script(settings, save=None):
    """The in-game script with the settings in. save: where its page in the mod menu saves them, {"path": the
    top mod's tweaks.json, "file": how to name it to the player, "keep": that file's own notes}, or None."""
    from .sdk import lua_value
    return LUA.replace("@SETTINGS@", lua_value({k: settings[k] for k in DEFAULTS})).replace("@SAVE@", lua_value(save)) \
        .replace("@HEAL_KEYS@", lua_value(list(HEAL_KEYS)))


LUA = lua_source("tweaks.lua")
