"""Mod discovery, and what mods need from each other.

A mod is a folder under mods/ with a mod.json:
  {"name": "Game Tweaks", "description": "...", "enabled": true, "priority": 0,
   "version": "1.2", "author": "...",          what the studio shows about it
   "requires": ["mod-menu"],                    mods it can't work without: turned on with it
   "uses": ["mod-menu"]}                        mods it works with when they're on (the mod menu, for a page)
and any of:
  files/<game path>   loose files that replace the game's (CSV data, configs, movies)
  paks/<name>.pak     cooked content made with Unreal Engine 5.7 (with its .utoc/.ucas), installed as is
  menu.json           the in-game mod menu itself and its settings (mods/mod-menu; pipeline.py)
  palette.json        colour palette (sections/palettes.py)
  controls.json       button remaps (sections/controls.py)
  mouselook.json      mouse look settings (sections/mouselook.py)
  data.json           gameplay data edits (sections/data.py)
  items.json          new herbs and materials (sections/items.py)
  names.json          cat names: prefixes, suffixes, rogues, the ban list, cats in your save (sections/names.py)
  cats.json           your cat's own colours and colour slots (sections/cats.py)
  save.json           save edits (sections/savedit.py)
  scripts/main.lua    an in-game Lua script, with settings.json for its settings (sections/scripts.py, opt-in)
  dlls/main.dll       a UE4SS C++ mod, built from cpp/ by `wcmods cpp build` (sections/cpp.py, opt-in)
  section.py          the mod's own section, written with wcmods.sdk (opt-in)
  studio/section.js   the mod's own studio page, written with studio/lib/wc.js (opt-in)
Folders starting with '_' are ignored (half-added mods; `wcmods new` copies wcmods/templates).
"""
import json
import os
import re

MENU_ID = "mod-menu"   # the mod menu's own mod: other mods name it in "requires" or "uses"
CONTENT = (("files", "files"), ("paks", "cooked content"), ("menu.json", "mod menu"), ("palette.json", "palette"), ("controls.json", "controls"),
           ("mouselook.json", "mouse look"), ("data.json", "data"), ("items.json", "items"), ("names.json", "names"), ("cats.json", "cats"),
           ("save.json", "save"), ("scripts", "in-game script"), ("dlls", "C++ mod"), ("cpp", "C++ source"),
           ("section.py", "code"),
           (os.path.join("studio", "section.js"), "studio page"))


class Mod:
    def __init__(self, folder):
        self.folder = folder
        self.id = os.path.basename(folder)
        with open(os.path.join(folder, "mod.json"), encoding="utf-8-sig") as f:
            meta = json.load(f)
        self.meta = meta
        # A mistake in one mod's mod.json (a name that isn't text, a priority that isn't a number) falls
        # back to the default here, so it can't stop every other mod from being listed and built.
        name, description = meta.get("name", self.id), meta.get("description", "")
        self.name = name if isinstance(name, str) else self.id
        self.description = description if isinstance(description, str) else ""
        self.enabled = bool(meta.get("enabled", True))
        try:
            self.priority = int(meta.get("priority", 0))
        except (TypeError, ValueError, OverflowError):
            self.priority = 0
        self.version = str(meta.get("version") or "")
        self.author = str(meta.get("author") or "")
        self.requires = _ids(meta.get("requires"))
        self.uses = [i for i in _ids(meta.get("uses")) if i not in self.requires]
        self.builtin = bool(meta.get("builtin", False))   # comes with wcmods: it can be turned off, not removed

    def kinds(self):
        return [kind for name, kind in CONTENT if os.path.exists(os.path.join(self.folder, name))]

    def has_code(self):
        """Whether it runs code (Python at build time, Lua or C++ in game, a studio page): only with code mods allowed."""
        return any(k in ("code", "in-game script", "C++ mod", "C++ source", "studio page") for k in self.kinds())

    def menu_page(self):
        """Whether it adds a page to the mod menu: it says it uses the menu, or it's something wcmods gives
        one (mouse look, a script with settings)."""
        if MENU_ID in self.requires or MENU_ID in self.uses:
            return True
        kinds = self.kinds()
        return "mouse look" in kinds or ("in-game script" in kinds and os.path.isfile(os.path.join(self.folder, "settings.json")))

    def update(self, **fields):
        path = os.path.join(self.folder, "mod.json")
        with open(path, encoding="utf-8-sig") as f:
            meta = json.load(f)
        for k, v in fields.items():
            if v is not None:
                meta[k] = v
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            f.write("\n")
        self.__init__(self.folder)

    def set_enabled(self, value):
        self.update(enabled=bool(value))

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description, "enabled": self.enabled,
                "priority": self.priority, "kinds": self.kinds(), "preset": palette_only(self),
                "version": self.version, "author": self.author, "requires": self.requires, "uses": self.uses,
                "builtin": self.builtin, "code": self.has_code(), "menu_page": self.menu_page()}


def _ids(value):
    """A list of mod ids from mod.json ("requires", "uses"); anything else in it is ignored."""
    if isinstance(value, str):
        value = [value]
    return [v.strip() for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def needed(mods, mod_id):
    """The mods `mod_id` requires, and what they require in turn (ids, nearest first); missing ones too."""
    by_id = {m.id: m for m in mods}
    out, todo = [], list(by_id[mod_id].requires) if mod_id in by_id else []
    while todo:
        i = todo.pop(0)
        if i in out or i == mod_id:
            continue
        out.append(i)
        if i in by_id:
            todo += by_id[i].requires
    return out


def needing(mods, mod_id):
    """The mods that are on and require `mod_id`, directly or through another mod."""
    return [m.id for m in mods if m.enabled and m.id != mod_id and mod_id in needed(mods, m.id)]


def unmet(mods, left_out=None):
    """{mod id: [why]} for the mods that are on but need a mod that's missing, off, or in `left_out`
    ({id: why}, e.g. made for an older version of the game)."""
    by_id = {m.id: m for m in mods}
    left_out = left_out or {}
    out = {}
    for m in mods:
        if not m.enabled or m.id in left_out:
            continue
        why = []
        for i in needed(mods, m.id):
            if i not in by_id:
                why.append(f"needs {i}, which isn't in your mods")
            elif not by_id[i].enabled:
                why.append(f"needs {by_id[i].name} ({i}), which is off")
            elif i in left_out:
                why.append(f"needs {by_id[i].name} ({i}), which is left out: {left_out[i]}")
        if why:
            out[m.id] = why
    return out


def switch(mods, mod_id, on, cascade=False):
    """Turn a mod on (and the mods it requires) or off. Turning off a mod that others on need only
    happens with cascade=True, which turns them off too; otherwise nothing changes and they're returned.

    Returns (changed, blocked): [(id, now on)] and the ids of mods that need it."""
    by_id = {m.id: m for m in mods}
    if mod_id not in by_id:
        raise LookupError(f"no mod named {mod_id}")
    changed = []
    if on:
        missing = [i for i in needed(mods, mod_id) if i not in by_id]
        if missing:
            raise ValueError(f"{by_id[mod_id].name} needs {', '.join(missing)}, which isn't in your mods; add it first")
        for i in [mod_id] + needed(mods, mod_id):
            if not by_id[i].enabled:
                by_id[i].set_enabled(True)
                changed.append((i, True))
        return changed, []
    blocked = needing(mods, mod_id)
    if blocked and not cascade:
        return [], blocked
    for i in [mod_id] + blocked:
        if by_id[i].enabled:
            by_id[i].set_enabled(False)
            changed.append((i, False))
    return changed, []


def palette_only(mod):
    """A mod that holds nothing but a palette.json recolouring the game's slots: safe to switch on and off
    as a colour preset. One that only adds new colour slots isn't a preset (cats may be wearing those
    slots), so quick palette switching leaves it alone."""
    if mod.kinds() != ["palette"]:
        return False
    from . import palettes
    try:
        return not palettes.adds_only(palettes.load(os.path.join(mod.folder, "palette.json")))
    except (OSError, ValueError):
        return True


def choose_palettes(mods, ids):
    """Turn on the palette-only mods in ids and turn the other palette-only mods off.

    Mods with anything besides a palette are left alone. Returns (on, off): the ids now on and off.
    """
    found = {m.id: m for m in mods if palette_only(m)}
    adders = sorted(i for i in ids if i not in found and any(m.id == i and m.kinds() == ["palette"] for m in mods))
    if adders:
        raise ValueError(f"{', '.join(adders)} only add new colours, so they aren't switched with the presets; "
                         "turn them on or off with `wcmods enable/disable`")
    unknown = [i for i in ids if i not in found]
    if unknown:
        raise ValueError(f"not a palette mod: {', '.join(unknown)} (palette mods: {', '.join(sorted(found))})")
    on, off = [], []
    for mod_id, m in sorted(found.items()):
        want = mod_id in ids
        if m.enabled != want:
            m.set_enabled(want)
        (on if want else off).append(mod_id)
    return on, off


def discover(mods_root):
    mods = []
    if os.path.isdir(mods_root):
        for name in sorted(os.listdir(mods_root)):
            folder = os.path.join(mods_root, name)
            if name.startswith("_") or not os.path.isfile(os.path.join(folder, "mod.json")):
                continue
            mods.append(Mod(folder))
    return sorted(mods, key=lambda m: (m.priority, m.id))


VALID_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def create(mods_root, mod_id, name=None, description="", enabled=False, priority=0):
    if not VALID_ID.match(mod_id):
        raise ValueError("mod folder names use lowercase letters, digits, '-', '_' or '.'")
    folder = os.path.join(mods_root, mod_id)
    if os.path.exists(folder):
        raise ValueError(f"a mod named {mod_id} already exists")
    os.makedirs(folder)
    with open(os.path.join(folder, "mod.json"), "w", encoding="utf-8") as f:
        json.dump({"name": name or mod_id.replace("-", " ").title(), "description": description,
                   "enabled": enabled, "priority": priority}, f, indent=2)
        f.write("\n")
    return Mod(folder)
