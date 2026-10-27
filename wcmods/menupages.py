"""The mod menu's pages about the game: a mod of their own, Menu pages (mods/menu-pages), from its own
repository, github.com/HexOffender/wcmods-menu-pages. The menu itself (the window, WCModsMenu, the
window's own pages) is wcmods' (menu.py); Menu pages adds your cat, the world, travel, items, quests,
fights and cheats to it through WCModsMenu like any mod does. It's an in-game script, so it runs only with
"allow_code_mods" on, as any script does.

Get set up in Clan Mod Studio (or `wcmods menu-pages`) adds it from its latest release on GitHub, or from
a .zip of it you downloaded; doing that again updates it, keeping whether it's on and its settings
(settings.json: "cheats", whether its Cheats page starts with cheats on). It can be added like any mod too.
"""
import json
import os
import re
import tempfile

from . import modzip
from .mods import Mod

ID = "menu-pages"
NAME = "Menu pages"
REPO = "HexOffender/wcmods-menu-pages"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSET = re.compile(r"^menu-pages[^/\\]*\.zip$")
MAX_ZIP = 20 * 1024 * 1024
SETTINGS = "settings.json"
ABOUT = "The pages about your cat, the world, quests, fights and cheats"


def installed(mods_root):
    """The Menu pages mod in your mods, or None."""
    folder = os.path.join(mods_root, ID)
    if not os.path.isfile(os.path.join(folder, "mod.json")):
        return None
    try:
        return Mod(folder)
    except (OSError, ValueError):   # a broken mod.json: as good as not there
        return None


def note(cfg, mods, built):
    """What the menu's Overview says about the Menu pages mod: how to get its pages while this build hasn't
    got them (`mods`: all your mods; `built`: the ids the build has), "" when it has."""
    m = next((m for m in mods if m.id == ID), None)
    if m is None:
        return f"{ABOUT} are a mod of their own, Menu pages. In Clan Mod Studio, Get set up on the Mods page adds it."
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
    (its releases on GitHub)}, for Get set up."""
    m = installed(cfg.mods_root)
    return {"installed": bool(m), "enabled": bool(m and m.enabled), "version": m.version if m else None,
            "code": bool(cfg.data.get("allow_code_mods")), "page": RELEASE_PAGE}


def find_release(timeout=20):
    """The latest release's .zip: {"name", "url", "size", "version", "page"} from GitHub."""
    from .ue4ss import github_release
    data = github_release(RELEASE_API, NAME, RELEASE_PAGE, timeout)
    for a in data.get("assets", []):
        if ASSET.match(a.get("name", "")):
            return {"name": a["name"], "url": a["browser_download_url"], "size": a.get("size"),
                    "version": str(data.get("tag_name") or "").lstrip("v"), "page": RELEASE_PAGE}
    raise RuntimeError(f"the latest Menu pages release has no menu-pages .zip; download it from {RELEASE_PAGE} "
                       "and add it on the Mods page")


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


def add(cfg, zip_path=None, log=print):
    """Add Menu pages to your mods, or update it: from `zip_path`, or its latest release downloaded from
    GitHub. An update keeps whether it's on and your values in its settings.json (a key only the new copy
    has is added); the older copy goes to backups, as with any mod replaced. From GitHub, a release of the
    version you have changes nothing ("unchanged"). Returns {"id", "name", "version", "from", "replaced" (the
    older copy's backup, or None), "unchanged"}."""
    from . import ue4ss
    cfg.reload()
    old = installed(cfg.mods_root)
    mine = _read_settings(old)
    if mine is None and "cheats" in cfg.data:
        # Cheats at start, from when the mod menu was wcmods' own (wcmods.json "cheats", or the old
        # mods/mod-menu's menu.json, which userdata moved there).
        mine = {"cheats": bool(cfg.data["cheats"])}
    enable = old.enabled if old else True

    def put(path, label):
        added = modzip.add_zip(path, cfg.mods_root, cfg.backups_dir, ids=[ID], enable=enable, name=label)
        return next(a for a in added if a.get("id") == ID)

    if zip_path:
        done, source = put(zip_path, os.path.basename(zip_path)), os.path.basename(zip_path)
    else:
        asset = find_release()
        if old and asset["version"] and asset["version"] == old.version:
            return {"id": ID, "name": NAME, "version": old.version, "from": asset["name"], "replaced": None,
                    "unchanged": True}
        log(f"downloading {asset['name']} ({(asset['size'] or 0) / 1024:.0f} KB) from GitHub...")
        with tempfile.TemporaryDirectory() as tmp:
            path = ue4ss.download(asset, tmp, limit=MAX_ZIP, what="Menu pages")
            done = put(path, asset["name"])
        source = asset["name"]
    new = installed(cfg.mods_root)
    if new and mine:
        shipped = _read_settings(new) or {}
        want = {**shipped, **{k: v for k, v in mine.items() if not str(k).startswith("_")}}
        if want != shipped:
            _write_settings(new, want)
    if "cheats" in cfg.data:
        cfg.data.pop("cheats")
        cfg.save()
    return {"id": ID, "name": NAME, "version": new.version if new else None, "from": source,
            "replaced": done.get("replaced"), "unchanged": False}


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
        raise LookupError(f"{NAME} isn't in your mods: Get set up in Clan Mod Studio adds it "
                          "(or python wcmods.py menu-pages)")
    data = _read_settings(m) or {}
    if on is not None and data.get("cheats") != bool(on):
        data["cheats"] = bool(on)
        _write_settings(m, data)
    return bool(data.get("cheats", False))
