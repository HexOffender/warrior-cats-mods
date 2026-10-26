"""Play state for the key remapper: a UE4SS script that writes "play" or "menu" to a file.

The remapper runs outside the game, so it can't tell exploring from a menu or the name screen.
Windows doesn't help: the game draws its own cursor, which Windows reports as shown in menus and
in play alike. The game knows, though, so this script writes "play" while you explore with the
cursor hidden (the same test mouse look uses) and "menu" otherwise. The controls section ships
it whenever there are keyboard remaps.
"""
import json
import os
from .lua import source as lua_source

UE4SS_MOD_NAME = "WCModsPlayState"
STATE_FILE = "state.txt"


def state_path(cfg):
    """Where the script writes, or None without UE4SS."""
    mods_dir = cfg.ue4ss_mods_dir
    return os.path.join(mods_dir, UE4SS_MOD_NAME, STATE_FILE) if mods_dir else None


def script(path):
    return LUA_TEMPLATE.replace("@PATH@", json.dumps(path, ensure_ascii=False))


LUA_TEMPLATE = lua_source("playstate.lua")
