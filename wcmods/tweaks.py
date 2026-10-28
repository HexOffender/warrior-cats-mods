"""Tweaks (tweaks.json): small changes while you play, ticked on the studio's Tweaks page, with no code of the
mod's own. Like mouse look, the mod holds data and the script that acts on it is wcmods' own (lua/tweaks.lua,
with WCModsGame), so it needs no "Allow mods that run code":

    { "keep_stamina_full": true, "heal_key": "F5", "hold_time": false, "time_of_day": 12.0,
      "min_fresh_kill": 20, "skip_scenes": false }

Every key is optional, and a missing one is off. The tweaks and what they do are Game Tweaks' (the example script
in wcmods-examples), and its way of skipping the story's scenes is Sandbox mode's. Skipping the story's scenes is
refused for now (UNCHECKED). With no tweak on, nothing goes in the game (sections/tweaks.py).
"""
import os

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
# Keys a heal can go on: F1 to F9. F10 opens the game's own command window (when that's on), F11 is full screen,
# and F12 is Steam's screenshot key. A key something else in the build has you press (the mod menu's, mouse look's
# on and off key, a remap) isn't offered either, and the build warns about one a file has (sections/tweaks.py).
HEAL_KEYS = tuple(f"F{n}" for n in range(1, 10))
# Tweaks refused until someone has checked them in the game, and why. Skipping the story's scenes was only seen
# working for Sandbox mode's cats: whether the skip still does what a story scene does at its end (a quest step,
# a ceremony's new rank) hasn't been checked. WCMODS_UNCHECKED_TWEAKS=1, set where an install runs, lets them
# through for that check (tests/game/test_tweaks.py says how).
UNCHECKED = {"skip_scenes": "it hasn't been checked that skipping keeps the story's steps"}


def unchecked():
    """The tweaks refused for now, {key: why}: none with WCMODS_UNCHECKED_TWEAKS=1 (for checking them in the game)."""
    return {} if os.environ.get("WCMODS_UNCHECKED_TWEAKS") == "1" else dict(UNCHECKED)


def validate(raw):
    """Check a tweaks.json and return the tweaks it sets ("_" keys are notes, left out); a ValueError says what's
    wrong in a sentence. A heal key that another part of the build uses is the build's to warn about."""
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
            why = unchecked().get(key)
            if value and why:
                raise ValueError(f"{FILE}: '{key}' is not available yet: {why}")
        elif key == "heal_key":
            if value != "" and value not in HEAL_KEYS:
                raise ValueError(f"{FILE}: 'heal_key' should be one of {', '.join(HEAL_KEYS)}, or \"\" for none (F10 and "
                                 "F11 are the game's own keys, F12 Steam's for a screenshot)")
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


def active(settings):
    """The tweaks merged settings turn on, {key: value} ({} when none is, and then nothing goes in the game)."""
    on = {}
    if settings["keep_stamina_full"]:
        on["keep_stamina_full"] = True
    if settings["heal_key"]:
        on["heal_key"] = settings["heal_key"]
    if settings["hold_time"]:
        on["hold_time"], on["time_of_day"] = True, settings["time_of_day"]
    if settings["min_fresh_kill"] > 0:
        on["min_fresh_kill"] = settings["min_fresh_kill"]
    if settings["skip_scenes"]:
        on["skip_scenes"] = True
    return on


def heal_keys(taken=()):
    """The keys a heal can go on, without those something else has you press (`taken`, keys)."""
    return [k for k in HEAL_KEYS if k not in taken]


def script(settings, save=None, taken=()):
    """The in-game script with the settings in. save: where its page in the mod menu saves them, {"path": the
    top mod's tweaks.json, "file": how to name it to the player, "keep": that file's own notes}, or None.
    taken: keys something else has you press, which its page doesn't offer for the heal (but the one it has)."""
    from .sdk import lua_value
    keys = [k for k in HEAL_KEYS if k not in taken or k == settings["heal_key"]]
    return (LUA.replace("@SETTINGS@", lua_value({k: settings[k] for k in DEFAULTS})).replace("@SAVE@", lua_value(save))
            .replace("@HEAL_KEYS@", lua_value(keys)))


LUA = lua_source("tweaks.lua")
