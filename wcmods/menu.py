"""The in-game mod menu: a shared UE4SS Lua module (WCModsMenu) and the script that hosts the window.

Insert (menu.json "key", the Mod menu's Settings in Clan Mod Studio) opens a window with a tab per page. Any UE4SS script adds a page with
WCModsMenu.page(title, fn); wcmods' own scripts add pages for their live settings, and the host's
first page lists the installed mods and what they set, from the build. See docs/SDK.md, "WCModsMenu".

How the pieces fit: each UE4SS mod runs in a Lua state of its own, so the host and the pages talk
through UE4SS's shared variables (strings, numbers, booleans and UObjects). The host makes the
window and shares its content panel; while a page is showing, the script that owns it builds its
controls straight into that panel. The controls are the game's own UI widgets (buttons, check boxes,
sliders, drop-downs, text boxes), so they take clicks and typing properly, and the page reads back
what the player changed each frame.
"""
from .sdk import lua_value
from .lua import source as lua_source

SHARED_NAME = "WCModsMenu"
HOST_NAME = "WCModsMenuHost"
DEFAULT_KEY = "INS"
# UE4SS Key names a player might want for the menu (F11 is the game's fullscreen key).
KEYS = ("INS", "HOME", "END", "DEL", "PAGE_UP", "PAGE_DOWN") + tuple(f"F{n}" for n in range(1, 13) if n != 11)

LUA = lua_source("menu.lua")

HOST_LUA = lua_source("menu_host.lua")

# The menu's size, as a factor on the usual: what menu.json "size", the studio and A-/A+ in game stay within.
SCALES = (0.6, 2.2)
KEY_NAMES = {"INS": "Insert", "HOME": "Home", "END": "End", "DEL": "Delete", "PAGE_UP": "Page Up",
             "PAGE_DOWN": "Page Down"}
# Controller buttons the game leaves free while you play (its own: the face buttons, bumpers, the left
# trigger, moving the sticks and Start; the right trigger is fly and ghost's up, on the Cheats page), as
# Unreal key names; "" for none. View is Back on older Xbox pads, Create or Share on PlayStation and -
# on Switch.
DEFAULT_PAD = "Gamepad_Special_Left"
PAD_NAMES = {"Gamepad_Special_Left": "View", "Gamepad_LeftThumbstick": "Left stick click",
             "Gamepad_RightThumbstick": "Right stick click", "Gamepad_DPad_Up": "D-pad up",
             "Gamepad_DPad_Down": "D-pad down", "Gamepad_DPad_Left": "D-pad left", "Gamepad_DPad_Right": "D-pad right",
             "": "None"}
PADS = tuple(PAD_NAMES)


# The side bar's groups, in order: id, label, and what the Overview page says is there (Home holds the
# Overview itself; Tools gains the Inspector and the Lua console with code mods allowed, said in the Lua).
# Written into the Lua as Menu.groups; the agent's menu driver (agent/menu.py) and the C++ SDK's
# PageOptions (cpp_sdk/include/WCMods/Menu.hpp) follow it.
GROUPS = (
    {"id": "home", "label": "Home"},
    {"id": "cat", "label": "Your cat",
     "where": "Stats: health, stamina, level and stats. Colours and Mouse look, when those mods are on."},
    {"id": "world", "label": "World", "where": "The time of day and the fresh-kill pile; Travel; what's Nearby; your Items."},
    {"id": "story", "label": "Story", "where": "Quests: the one you follow, its objectives, and every quest's state."},
    {"id": "fight", "label": "Fight", "where": "Both sides of a fight while you're in one."},
    {"id": "cheats", "label": "Cheats", "where": "The engine's cheats, and the game's own developer switches."},
    {"id": "mods", "label": "Mods", "where": "Pages from the mods you have on."},
    {"id": "tools", "label": "Tools", "where": "The log, this menu's settings"},
)


def lua():
    """The shared WCModsMenu module, with the side bar's groups in."""
    return LUA.replace("@GROUPS@", lua_value([dict(g) for g in GROUPS]))


def host_script(manifest, mods, key=DEFAULT_KEY, cheats=False, scale=1.0, dev=False, pages=None, pad=DEFAULT_PAD):
    """The host's script, with the overview of this build: the enabled mods and what each section set.
    cheats: whether the Cheats page starts with cheats on (menu.json "cheats"); scale: the menu's size,
    1 for the usual (menu.json "size"); dev: whether the Inspector and Lua console pages are in
    (they're for code mods, so wcmods.json "allow_code_mods"); pages: menupages.data(), the area names and
    quest titles the pages show; pad: the controller button that opens it too (an Unreal key name, "" for
    none)."""
    if key not in KEYS:
        raise ValueError(f"the menu's key should be one of {', '.join(KEYS)}")
    enabled = [m for m in mods if m.enabled]
    sections = []
    for sid, rep in manifest["sections"].items():
        if not rep.get("mods"):
            continue
        sections.append({"id": sid, "title": rep["title"], "status": rep["status"], "errors": rep.get("errors", []),
                         "mods": rep["mods"], "notes": manifest["notes"].get(sid)})
    key_name, pad_name = KEY_NAMES.get(key, key), PAD_NAMES.get(pad, pad) if pad else ""
    settings = {
        "key": key, "key_name": key_name, "built": manifest["built"].replace("T", " "),
        "pad": pad or "", "pad_name": pad_name, "opens": key_name + (f" (or {pad_name} on a controller)" if pad else ""),
        "cheats": bool(cheats), "scale": float(scale), "size_min": SCALES[0], "size_max": SCALES[1], "dev": bool(dev),
        "mods": [{"id": m.id, "name": m.name, "description": m.description, "kinds": m.kinds(),
                  "priority": m.priority} for m in enabled],
        "sections": sections, "warnings": manifest["warnings"],
    }
    from . import menupages
    return (HOST_LUA.replace("@SETTINGS@", lua_value(settings)).replace("@KEY@", KEY_NAMES.get(key, key))
            .replace("@PAGES@", menupages.lua(pages)))
