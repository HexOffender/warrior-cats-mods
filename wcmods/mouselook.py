"""Mouse look (mouselook.json): a UE4SS script that lets the mouse turn the exploration camera.

The game switches Unreal's mouse capture off (DefaultViewportMouseCaptureMode=NoCapture in its
DefaultInput.ini), so mouse movement never reaches it, and the bindings kept in the save don't
change its controls. The script works at runtime instead: while you explore with the cursor hidden
it captures the mouse like most PC games and moves the camera actor (BP_AdventureCamera) directly.
It releases the mouse whenever the game shows its cursor.
"""
import json
from .lua import source as lua_source

UE4SS_MOD_NAME = "WCModsMouseLook"
DEFAULTS = {
    "sensitivity": 1.0,
    "invert": False,
    "toggle_key": "F6",     # turns mouse look off and on in game; "" for none
    # Tilt limits, from Gameplay.Exploration.Camera.Pitch.Min/Max in TuningData.csv.
    "pitch_min": -20.0,
    "pitch_max": 23.0,
    # How long the camera takes to catch up with the mouse, in milliseconds; 0 for not at all. The game
    # eases the camera after the arrow keys and stick over about 200 ms (Lag.Rotation 5 in TuningData.csv).
    "smoothing": 0.0,
    "debug": False,         # log what the script sees to ue4ss/UE4SS.log as [MouseLook]
}
TOGGLE_KEYS = tuple(f"F{n}" for n in range(1, 13) if n != 11)   # F11 is the game's fullscreen key


def validate(raw):
    """Check a mouselook.json and return just the settings it sets."""
    if not isinstance(raw, dict):
        raise ValueError("mouselook.json should be an object like {\"sensitivity\": 1.0}")
    out = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if key not in DEFAULTS:
            raise ValueError(f"mouselook.json: unknown setting '{key}' (known: {', '.join(DEFAULTS)})")
        default = DEFAULTS[key]
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError(f"mouselook.json: '{key}' should be true or false")
        elif isinstance(default, float):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"mouselook.json: '{key}' should be a number")
            value = float(value)
            if key == "sensitivity" and not 0.05 <= value <= 10:
                raise ValueError("mouselook.json: 'sensitivity' should be between 0.05 and 10")
            if key.startswith("pitch_") and not -89 <= value <= 89:
                raise ValueError(f"mouselook.json: '{key}' should be between -89 and 89 degrees")
            if key == "smoothing" and not 0 <= value <= 1000:
                raise ValueError("mouselook.json: 'smoothing' should be between 0 and 1000 milliseconds")
        elif key == "toggle_key":
            if value not in TOGGLE_KEYS + ("",):
                raise ValueError(f"mouselook.json: 'toggle_key' should be one of {', '.join(TOGGLE_KEYS)} or \"\"")
        out[key] = value
    return out


def merge(items, sources=None):
    """Settings from several mods, later ones winning. sources names each item for error messages."""
    settings, setter = dict(DEFAULTS), {}
    for i, data in enumerate(items):
        settings.update(data)
        for key in data:
            setter[key] = sources[i] if sources else None
    if settings["pitch_min"] >= settings["pitch_max"]:
        def said(key):
            who = setter.get(key)
            return f"{settings[key]:g} ({'from ' + who if who else 'default'})"
        raise ValueError(f"mouse look: pitch_min {said('pitch_min')} must be below pitch_max {said('pitch_max')}")
    return settings


def _lua(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(float(value))
    return json.dumps(value)   # ASCII-only strings here; JSON escapes are valid Lua


def script(settings, save=None):
    """save: where the in-game menu's Save writes the settings: {"path": the mod's mouselook.json,
    "file": how to name it to the player, "keep": the file's own notes such as "_help"}."""
    from .sdk import lua_value
    table = "{ " + ", ".join(f"{k} = {_lua(settings[k])}" for k in DEFAULTS) + " }"
    return LUA_TEMPLATE.replace("@SETTINGS@", table).replace("@SAVE@", lua_value(save))


LUA_TEMPLATE = lua_source("mouselook.lua")