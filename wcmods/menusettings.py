"""In-game options: the mod menu's own settings and the game's console.

The mod menu's window is wcmods' own (menu.py), and its settings are in wcmods.json:
- "menu_key": the key that opens it (menu.KEYS). Applies on the next install.
- "menu_pad": the controller button that opens it too, an Unreal key name ("" for none; the studio offers
  menu.PADS). Applies on the next install.
- "menu_scale": its size, 1 for the usual (MENU_SCALES). Applies on the next install; A- and A+ in the
  menu change it for the session.
When the menu was a mod of its own, they were in mods/mod-menu/menu.json; userdata.prepare moves them in.
Whether cheats start on is the Menu pages mod's setting now (menupages.cheats).

The game's console is UE4SS's console unlocker (ConsoleEnablerMod): ~ or F10 opens it. wcmods.json's
"console" remembers the choice; it applies the next time the game starts.
"""
import os
import re

from . import menu, ue4ss

CONSOLE_MOD = "ConsoleEnablerMod"
MENU_SCALES = menu.SCALES   # the mod menu's size, 1 for the usual; A-/A+ in game stay within these too
SIZE_CHOICES = ((0.8, "Small"), (1, "Normal"), (1.25, "Large"), (1.5, "Larger"), (1.8, "Largest"))   # the studio's choices
KEYS = {"key": "menu_key", "pad": "menu_pad", "size": "menu_scale"}   # a setting -> its key in wcmods.json


def console_on(cfg):
    """Whether UE4SS starts its console unlocker, as its mods.txt says; wcmods.json's choice without UE4SS."""
    mods_dir = cfg.ue4ss_mods_dir
    txt = os.path.join(mods_dir, "mods.txt") if mods_dir else None
    if txt and os.path.isfile(txt):
        with open(txt, encoding="utf-8-sig") as f:
            for line in f:
                name, _, value = line.partition(":")
                if name.strip() == CONSOLE_MOD:
                    return value.strip() == "1"
        return False
    return bool(cfg.data.get("console", False))


def _scale(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return 1.0
    return float(min(max(v, MENU_SCALES[0]), MENU_SCALES[1]))


def menu_settings(cfg, data=None):
    """The mod menu's key, controller button and size, from wcmods.json (cfg's, or `data` read from it):
    what isn't there or can't be used is the default; "key_ok" and "pad_ok" say whether what's there could
    be, "key_given" and "pad_given" what it was."""
    data = cfg.data if data is None else data
    key = data.get(KEYS["key"], menu.DEFAULT_KEY)
    # Any Unreal key name works in wcmods.json; the studio offers the controller buttons the game leaves free.
    pad = data.get(KEYS["pad"], menu.DEFAULT_PAD)
    pad_ok = isinstance(pad, str) and (pad == "" or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", pad) is not None)
    return {"key": key if key in menu.KEYS else menu.DEFAULT_KEY, "key_ok": key in menu.KEYS, "key_given": key,
            "pad": pad if pad_ok else menu.DEFAULT_PAD, "pad_ok": pad_ok, "pad_given": pad,
            "size": _scale(data.get(KEYS["size"], 1.0))}


def options(cfg):
    """The in-game options as the studio shows them: the menu's key, pad and size (with the choices for
    each, as [value, label] pairs) and the game's console."""
    s = menu_settings(cfg)
    return {"console": console_on(cfg),
            "console_available": bool(cfg.ue4ss_mods_dir and os.path.isdir(os.path.join(cfg.ue4ss_mods_dir, CONSOLE_MOD))),
            "key": s["key"], "keys": [[k, menu.KEY_NAMES.get(k, k)] for k in menu.KEYS],
            "size": s["size"], "sizes": [[v, label] for v, label in SIZE_CHOICES],
            "pad": s["pad"], "pads": [[p, n] for p, n in menu.PAD_NAMES.items()]}


def apply_console(cfg):
    """Make UE4SS's mods list match wcmods.json's "console" (when it says anything)."""
    mods_dir = cfg.ue4ss_mods_dir
    if "console" in cfg.data and mods_dir and os.path.isdir(os.path.join(mods_dir, CONSOLE_MOD)):
        ue4ss.set_registered(mods_dir, CONSOLE_MOD, bool(cfg.data["console"]))


def set_options(cfg, console=None, key=None, size=None, pad=None):
    """Change some options (None leaves one as it is) and return them all, all kept in wcmods.json."""
    cfg.reload()   # the studio keeps one Config for its whole run
    if size is not None and (isinstance(size, bool) or not isinstance(size, (int, float))
                             or not MENU_SCALES[0] <= size <= MENU_SCALES[1]):
        raise ValueError(f"size should be a number from {MENU_SCALES[0]} to {MENU_SCALES[1]} (1 is the usual size)")
    if key is not None and key not in menu.KEYS:
        raise ValueError(f"key should be one of {', '.join(menu.KEYS)}")
    if pad is not None and pad not in menu.PADS:
        raise ValueError(f"pad should be one of {', '.join(repr(p) for p in menu.PADS)}")
    if key is not None:
        cfg.data[KEYS["key"]] = key
    if size is not None:
        cfg.data[KEYS["size"]] = float(size)
    if pad is not None:
        cfg.data[KEYS["pad"]] = pad
    if console is not None:
        cfg.data["console"] = bool(console)
        apply_console(cfg)
    cfg.save()
    return options(cfg)
