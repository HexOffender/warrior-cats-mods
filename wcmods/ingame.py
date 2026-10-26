"""In-game options: the mod menu's own settings and the game's console.

The mod menu is a mod of its own (mods/mod-menu, mods.MENU_ID), and its settings are in its menu.json:
- "key": the key that opens it (menu.KEYS). Applies on the next install.
- "pad": the controller button that opens it too, an Unreal key name ("" for none; the studio offers
  menu.PADS). Applies on the next install.
- "size": its size, 1 for the usual (MENU_SCALES). Applies on the next install; A- and A+ in the menu
  change it for the session.
- "cheats": the menu's Cheats page starts with cheats on (it can switch them on and off live).
  Applies on the next install, which writes it into the menu's script.
Older setups kept these in wcmods.json ("menu_key", "menu_scale", "cheats"). Those still count while
they're there; changing a setting moves them all into menu.json.

The game's console is UE4SS's console unlocker (ConsoleEnablerMod): ~ or F10 opens it. wcmods.json's
"console" remembers the choice; it applies the next time the game starts.
"""
import json
import os
import re

from . import menu, mods as modlib, ue4ss

CONSOLE_MOD = "ConsoleEnablerMod"
MENU_FILE = "menu.json"
MENU_SCALES = menu.SCALES   # the mod menu's size, 1 for the usual; A-/A+ in game stay within these too
SIZE_CHOICES = ((0.8, "Small"), (1, "Normal"), (1.25, "Large"), (1.5, "Larger"), (1.8, "Largest"))   # the studio's choices
LEGACY = {"key": "menu_key", "size": "menu_scale", "cheats": "cheats"}   # menu.json key -> old wcmods.json key
MENU_HELP = ("The in-game mod menu. key: INS, HOME, END, DEL, PAGE_UP, PAGE_DOWN or F1-F12 (not F11). pad: the "
             "controller button that opens it too (an Unreal key name such as Gamepad_Special_Left, the View button; "
             "\"\" for none). size: 0.6 to 2.2, 1 is the usual. cheats: whether its Cheats page starts with cheats on. "
             "Install again after a change.")


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


def menu_mod(cfg, found=None):
    """The mod that is the mod menu (it has a menu.json): the one that's on, mods/mod-menu first; None
    when there's none."""
    found = found if found is not None else modlib.discover(os.path.join(cfg.root, "mods"))
    menus = [m for m in found if os.path.isfile(os.path.join(m.folder, MENU_FILE))]
    menus.sort(key=lambda m: (not m.enabled, m.id != modlib.MENU_ID, m.id))
    return menus[0] if menus else None


def _read(mod):
    if not mod:
        return {}
    try:
        with open(os.path.join(mod.folder, MENU_FILE), encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _scale(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return 1.0
    return float(min(max(v, MENU_SCALES[0]), MENU_SCALES[1]))


def menu_settings(cfg, mod=None, found=None):
    """The mod menu's key, controller button, size and cheats (from its menu.json, or wcmods.json while it
    still has them)."""
    mod = mod or menu_mod(cfg, found)
    own = _read(mod)
    pick = lambda k, default: cfg.data[LEGACY[k]] if LEGACY[k] in cfg.data else own.get(k, default)
    key = pick("key", menu.DEFAULT_KEY)
    # Any Unreal key name works in menu.json; the studio offers the controller buttons the game leaves free.
    pad = own.get("pad", menu.DEFAULT_PAD)
    pad_ok = isinstance(pad, str) and (pad == "" or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", pad) is not None)
    return {"key": key if key in menu.KEYS else menu.DEFAULT_KEY, "key_ok": key in menu.KEYS, "key_given": key,
            "pad": pad if pad_ok else menu.DEFAULT_PAD, "pad_ok": pad_ok, "pad_given": pad,
            "size": _scale(pick("size", 1.0)), "cheats": bool(pick("cheats", False))}


def options(cfg):
    """The in-game options as the studio shows them: the menu's key, pad and size (with the choices for
    each, as [value, label] pairs), whether cheats start on, and the game's console."""
    m = menu_mod(cfg)
    s = menu_settings(cfg, m)
    return {"cheats": s["cheats"], "console": console_on(cfg),
            "console_available": bool(cfg.ue4ss_mods_dir and os.path.isdir(os.path.join(cfg.ue4ss_mods_dir, CONSOLE_MOD))),
            "key": s["key"], "keys": [[k, menu.KEY_NAMES.get(k, k)] for k in menu.KEYS],
            "size": s["size"], "sizes": [[v, label] for v, label in SIZE_CHOICES],
            "pad": s["pad"], "pads": [[p, n] for p, n in menu.PAD_NAMES.items()],
            "menu_mod": m.id if m else None, "menu_on": bool(m and m.enabled)}


def apply_console(cfg):
    """Make UE4SS's mods list match wcmods.json's "console" (when it says anything)."""
    mods_dir = cfg.ue4ss_mods_dir
    if "console" in cfg.data and mods_dir and os.path.isdir(os.path.join(mods_dir, CONSOLE_MOD)):
        ue4ss.set_registered(mods_dir, CONSOLE_MOD, bool(cfg.data["console"]))


def set_options(cfg, cheats=None, console=None, key=None, size=None, pad=None):
    """Change some options (None leaves one as it is) and return them all. The menu's go in its menu.json
    (taking any still in wcmods.json along), the console's in wcmods.json."""
    cfg.reload()   # the studio keeps one Config for its whole run
    if size is not None and (isinstance(size, bool) or not isinstance(size, (int, float))
                             or not MENU_SCALES[0] <= size <= MENU_SCALES[1]):
        raise ValueError(f"size should be a number from {MENU_SCALES[0]} to {MENU_SCALES[1]} (1 is the usual size)")
    if key is not None and key not in menu.KEYS:
        raise ValueError(f"key should be one of {', '.join(menu.KEYS)}")
    if pad is not None and pad not in menu.PADS:
        raise ValueError(f"pad should be one of {', '.join(repr(p) for p in menu.PADS)}")
    if any(v is not None for v in (cheats, key, size, pad)):
        m = menu_mod(cfg)
        if not m:
            raise LookupError("there's no mod menu in your mods (mods/mod-menu with its menu.json)")
        s = menu_settings(cfg, m)
        data = {**_read(m), "key": s["key"], "size": s["size"], "cheats": s["cheats"]}
        data.setdefault("_help", MENU_HELP)
        if key is not None:
            data["key"] = key
        if size is not None:
            data["size"] = float(size)
        if pad is not None:
            data["pad"] = pad
        if cheats is not None:
            data["cheats"] = bool(cheats)
        with open(os.path.join(m.folder, MENU_FILE), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        for old in LEGACY.values():
            cfg.data.pop(old, None)
    if console is not None:
        cfg.data["console"] = bool(console)
        apply_console(cfg)
    cfg.save()
    return options(cfg)
