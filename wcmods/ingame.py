"""In-game options kept in wcmods.json: cheats when the game starts, the game's console, the mod menu's key.

- "cheats": the mod menu's Cheats page starts with cheats on (it can switch them on and off live).
  Applies on the next install, which writes it into the menu's script.
- "console": UE4SS's own console unlocker (ConsoleEnablerMod): ~ or F10 opens the game's console.
  Applies the next time the game starts.
- "menu_key": the key that opens the mod menu (menu.KEYS). Applies on the next install.
- "menu_scale": the mod menu's size, 1 for the usual (MENU_SCALES). Applies on the next install;
  A- and A+ in the menu change it for the session.
"""
import os

from . import menu, ue4ss

CONSOLE_MOD = "ConsoleEnablerMod"


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


MENU_SCALES = (0.6, 2.2)   # the mod menu's size, 1 for the usual; A-/A+ in game stay within these too


def menu_scale(cfg):
    v = cfg.data.get("menu_scale", 1.0)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return 1.0
    return float(min(max(v, MENU_SCALES[0]), MENU_SCALES[1]))


def options(cfg):
    return {"cheats": bool(cfg.data.get("cheats", False)), "console": console_on(cfg),
            "console_available": bool(cfg.ue4ss_mods_dir and os.path.isdir(os.path.join(cfg.ue4ss_mods_dir, CONSOLE_MOD))),
            "menu_key": cfg.data.get("menu_key", menu.DEFAULT_KEY), "menu_keys": list(menu.KEYS),
            "menu_scale": menu_scale(cfg)}


def apply_console(cfg):
    """Make UE4SS's mods list match wcmods.json's "console" (when it says anything)."""
    mods_dir = cfg.ue4ss_mods_dir
    if "console" in cfg.data and mods_dir and os.path.isdir(os.path.join(mods_dir, CONSOLE_MOD)):
        ue4ss.set_registered(mods_dir, CONSOLE_MOD, bool(cfg.data["console"]))


def set_options(cfg, cheats=None, console=None, menu_key=None, menu_scale=None):
    """Change some options (None leaves one as it is), save wcmods.json, and return them all."""
    cfg.reload()   # the studio keeps one Config for its whole run
    if menu_scale is not None:
        if isinstance(menu_scale, bool) or not isinstance(menu_scale, (int, float)) \
                or not MENU_SCALES[0] <= menu_scale <= MENU_SCALES[1]:
            raise ValueError(f"menu_scale should be a number from {MENU_SCALES[0]} to {MENU_SCALES[1]} (1 is the usual size)")
        cfg.data["menu_scale"] = float(menu_scale)
    if menu_key is not None:
        if menu_key not in menu.KEYS:
            raise ValueError(f"menu_key should be one of {', '.join(menu.KEYS)}")
        cfg.data["menu_key"] = menu_key
    if cheats is not None:
        cfg.data["cheats"] = bool(cheats)
    if console is not None:
        cfg.data["console"] = bool(console)
        apply_console(cfg)
    cfg.save()
    return options(cfg)
