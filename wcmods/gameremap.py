"""Key remaps inside the game: a UE4SS script, written from controls.json, that moves the game's actions to
other keys, mouse buttons and controller buttons.

The game's bindings live in native code that nothing can reach (see docs/reverse-engineering.md, "Input"),
but each key goes to the game's listeners as OnKeyPressed(key), and each action bound to it as
OnListenCommand(command): both are reflected and can be hooked. The script sends an action's command when
its new key is pressed and drops the game's own when it comes from the old key. keymap.native_plan says
what it does; movement, the camera and the menus are left to the key remapper outside the game
(remapper.py, `wcmods play`).
"""
import os

from .lua import source as lua_source

UE4SS_MOD_NAME = "WCModsRemap"


def script(plan, debug=False):
    """plan: keymap.native_plan's first result."""
    from .sdk import lua_value
    data = {"send": plan["send"], "drop": plan["drop"], "keys": plan["keys"], "debug": debug}
    return LUA_TEMPLATE.replace("@PLAN@", lua_value(data))


def installed(cfg):
    """Whether the last install put the script in the game (then the key remapper leaves its part to it)."""
    mods_dir = cfg.ue4ss_mods_dir
    return bool(mods_dir) and os.path.isfile(os.path.join(mods_dir, UE4SS_MOD_NAME, "Scripts", "main.lua"))


LUA_TEMPLATE = lua_source("remap.lua")
