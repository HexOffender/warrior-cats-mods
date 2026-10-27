"""Key remaps inside the game: a UE4SS script, written from controls.json, that moves the game's actions and
menu keys to other keys, mouse buttons and controller buttons.

The game's bindings live in native code that nothing can reach (see docs/reverse-engineering.md, "Input"),
but each key goes to the game's listeners as OnKeyPressed(key), and each command bound to it as
OnListenCommand(command): both are reflected and can be hooked. The script sends a command when its new key
is pressed and drops the game's own when it comes from the old key. keymap.native_plan says what it does;
what the game reads as axes (movement, the camera, the map's zoom and move) is left to the key remapper
outside the game (remapper.py, `wcmods play`).
"""
import os

from .lua import source as lua_source

UE4SS_MOD_NAME = "WCModsRemap"


def script(plan, debug=False):
    """plan: keymap.native_plan's first result."""
    from .sdk import lua_value
    data = {"play": plan["play"], "menu": plan["menu"], "keys": plan["keys"], "icons": plan["icons"],
            "debug": debug}
    return LUA_TEMPLATE.replace("@PLAN@", lua_value(data))


def has_work(plan):
    """Whether keymap.native_plan left the script anything to do."""
    return any(plan[where]["send"] or plan[where]["drop"] for where in ("play", "menu"))


def installed(cfg):
    """Whether the last install put the script in the game (then the key remapper leaves its part to it)."""
    mods_dir = cfg.ue4ss_mods_dir
    return bool(mods_dir) and os.path.isfile(os.path.join(mods_dir, UE4SS_MOD_NAME, "Scripts", "main.lua"))


LUA_TEMPLATE = lua_source("remap.lua")
