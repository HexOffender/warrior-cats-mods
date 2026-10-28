"""The mod menu's pages about the game: a mod of their own, Menu pages (mods/menu-pages), from its own
repository, github.com/HexOffender/wcmods-menu-pages. The menu itself (the window, WCModsMenu, the
window's own pages) is wcmods' (menu.py); Menu pages adds your cat, the world, travel, items, quests,
fights and cheats to it through WCModsMenu like any mod does. It's an in-game script, so it runs only with
"allow_code_mods" on, as any script does.

It's one of the mods that go with Clan Mod Studio (addons.py), which adds it from its latest release on
GitHub, or from a .zip of it you downloaded, and updates it, keeping whether it's on and its settings
(settings.json: "cheats", whether its Cheats page starts with cheats on). What's here is what is its own:
what the menu's Overview says while a build hasn't got it, and its cheats setting. `add`, `status` and
`find_release` are the registry's, kept here for `wcmods menu-pages` and the Mods page's older route.
"""
import json
import os

from . import addons

ID = "menu-pages"
NAME = "Menu pages"
REPO = addons.get(ID).repo
RELEASE_PAGE = addons.get(ID).page
SETTINGS = "settings.json"
ABOUT = "The pages about your cat, the world, quests, fights and cheats"


def installed(mods_root):
    """The Menu pages mod in your mods, or None."""
    return addons.installed(mods_root, addons.get(ID))


def note(cfg, mods, built):
    """What the menu's Overview says about the Menu pages mod: how to get its pages while this build hasn't
    got them (`mods`: all your mods; `built`: the ids the build has), "" when it has."""
    m = next((m for m in mods if m.id == ID), None)
    if m is None:
        return (f"{ABOUT} are a mod of their own, Menu pages. In Clan Mod Studio, the Mods page's add-ons card "
                "(Mods that go with Clan Mod Studio) adds it.")
    if not m.enabled:
        return f"{ABOUT} come with the Menu pages mod, which is off: turn it on in Clan Mod Studio, then Apply to game."
    if m.id not in built:
        return f"{ABOUT} come with the Menu pages mod, which this install left out (Installed mods says why)."
    if not cfg.data.get("allow_code_mods"):
        return (f"{ABOUT} come with the Menu pages mod, which runs code: allow mods that run code (Options, on the "
                "Settings and repair page in Clan Mod Studio), then Apply to game.")
    return ""


def status(cfg):
    """{"installed", "enabled", "version", "code" (mods that run code are allowed, which it needs), "page"
    (its releases on GitHub)}."""
    m = installed(cfg.mods_root)
    return {"installed": bool(m), "enabled": bool(m and m.enabled), "version": m.version if m else None,
            "code": bool(cfg.data.get("allow_code_mods")), "page": RELEASE_PAGE}


def find_release(timeout=20):
    """The latest release's .zip: {"name", "url", "size", "version", "page"} from GitHub. No release at all
    is ue4ss.NoRelease saying "no release yet" as every add-on's does (addons.no_release)."""
    from .ue4ss import NoRelease
    addon = addons.get(ID)
    try:
        return addons.find_release(addon, timeout)
    except NoRelease:
        raise NoRelease(addons.no_release(addon)) from None


def add(cfg, zip_path=None, log=print):
    """Add Menu pages to your mods, or update it: from `zip_path`, or its latest release downloaded from
    GitHub (addons.add). Cheats at start from when the mod menu was wcmods' own (wcmods.json "cheats", or the
    old mods/mod-menu's menu.json, which userdata moved there) go into its settings.json. Returns as
    addons.add."""
    cfg.reload()
    seed = {SETTINGS: {"cheats": bool(cfg.data["cheats"])}} if "cheats" in cfg.data else None
    # find_release is looked up here, as this module has it, so a stand-in for GitHub reaches it.
    done = addons.add(cfg, ID, zip_path, log=log, release=None if zip_path else find_release(), seed=seed)
    if not done["unchanged"] and "cheats" in cfg.data:
        cfg.data.pop("cheats")
        cfg.save()
    return done


def _read_settings(mod):
    if not mod:
        return None
    try:
        with open(os.path.join(mod.folder, SETTINGS), encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_settings(mod, data):
    with open(os.path.join(mod.folder, SETTINGS), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def cheats_or_none(cfg):
    """cheats(), or None without the mod: for showing the setting only where there is one."""
    try:
        return cheats(cfg)
    except LookupError:
        return None


def cheats(cfg, on=None):
    """Whether Menu pages' Cheats page starts with cheats on (its settings.json "cheats"); with `on`, set
    that first. Raises LookupError when the mod isn't in your mods."""
    m = installed(cfg.mods_root)
    if not m:
        raise LookupError(f"{NAME} isn't in your mods: the Mods page's add-ons card in Clan Mod Studio adds it")
    data = _read_settings(m) or {}
    if on is not None and data.get("cheats") != bool(on):
        data["cheats"] = bool(on)
        _write_settings(m, data)
    return bool(data.get("cheats", False))

