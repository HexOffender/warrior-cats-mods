"""Mod discovery, and what mods need from each other.

A mod is a folder under mods/ (in your own folder, config.data_dir(); not wcmods') with a mod.json:
  {"name": "Game Tweaks", "description": "...", "enabled": true, "priority": 0,
   "version": "1.2", "author": "...",          what the studio shows about it
   "requires": ["menu-pages"],                  mods it can't work without: turned on with it, and it's left
                                                out while one is missing or off
   "uses": ["sandbox", "mod-menu"],             mods it works with when they're on: turned on with it when
                                                they're in the mods folder, never a reason to leave it out
                                                ("mod-menu", the in-game menu's window, for a page: wcmods'
                                                own, so always there)
   "pack": true}                                a mod pack: nothing of its own, its "requires" are its mods
                                                (packs.py)
and any of:
  files/<game path>   loose files that replace the game's (CSV data, configs, movies)
  paks/<name>.pak     cooked content made with Unreal Engine 5.7 (with its .utoc/.ucas), installed as is
  palette.json        colour palette (sections/palettes.py)
  controls.json       button remaps (sections/controls.py)
  mouselook.json      mouse look settings (sections/mouselook.py)
  data.json           gameplay data edits (sections/data.py)
  items.json          new herbs and materials (sections/items.py)
  npcs.json           cats of the mod's own, and quests.json, questlines with them (sections/story.py; the
  quests.json         Sandbox mode mod brings them into the game)
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

# The in-game mod menu's window, which mods name in "requires" or "uses" for a page in it. It was a mod of its
# own; it's wcmods' now (menu.py), so it's always there: a mod needing it needs nothing more.
MENU_ID = "mod-menu"
CONTENT = (("files", "files"), ("paks", "cooked content"), ("palette.json", "palette"), ("controls.json", "controls"),
           ("mouselook.json", "mouse look"), ("data.json", "data"), ("items.json", "items"),
           ("animations.json", "animations"), ("npcs.json", "characters"), ("quests.json", "questlines"),
           ("names.json", "names"), ("cats.json", "cats"),
           ("save.json", "save"), ("scripts", "in-game script"), ("dlls", "C++ mod"), ("cpp", "C++ source"),
           ("section.py", "code"),
           (os.path.join("studio", "section.js"), "studio page"))


class Mod:
    def __init__(self, folder):
        self.folder = folder
        self.id = os.path.basename(folder)
        # A mod.json that can't be read (not JSON, or not an object) is a mod that's off, with the problem
        # on its card, so it can't blank the list of every other mod. (One that can't be opened at all is
        # Mod.broken, from discover().)
        self.problem = None
        try:
            with open(os.path.join(folder, "mod.json"), encoding="utf-8-sig") as f:
                meta = json.load(f)
            if not isinstance(meta, dict):
                raise ValueError("it should hold an object, {...}")
        except ValueError as e:
            self.problem = f"{file_problem('mod.json', e)}; fix it in a text editor, or remove the mod"
            meta = {"enabled": False}
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

    @classmethod
    def broken(cls, folder, problem):
        """A mod whose mod.json can't be read: listed by its folder's name, off, with nothing in it, and
        `problem` saying what's wrong, so one damaged file can't stop the others from being listed."""
        m = cls.__new__(cls)
        m.folder, m.id, m.problem, m.meta = folder, os.path.basename(folder), problem, {}
        m.name, m.description, m.enabled, m.priority = m.id, "", False, 0
        m.version, m.author, m.requires, m.uses = "", "", [], []
        return m

    def kinds(self):
        if self.problem:
            return []
        kinds = [kind for name, kind in CONTENT if os.path.exists(os.path.join(self.folder, name))]
        return ["mod pack"] + kinds if self.meta.get("pack") else kinds

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
        if self.problem:
            raise ValueError(f"{self.id}'s mod.json can't be read, so the mod can't be changed: {self.problem}")
        path = os.path.join(self.folder, "mod.json")
        with open(path, encoding="utf-8-sig") as f:
            try:
                meta = json.load(f)
            except ValueError as e:   # broken since it was listed
                raise ValueError(f"{self.id}'s mod.json can't be read: {file_problem('mod.json', e)}; fix it in a text "
                                 "editor first") from None
        if not isinstance(meta, dict):
            raise ValueError(f"{self.id}'s mod.json should hold an object, {{...}}; fix it in a text editor first")
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
                "version": self.version, "author": self.author,
                "requires": [i for i in self.requires if i != MENU_ID], "uses": self.uses,
                "code": self.has_code(), "menu_page": self.menu_page(), "pack": bool(self.meta.get("pack")),
                "problem": self.problem}


def file_problem(name, e):
    """What's wrong with a JSON file, as a sentence: "mod.json isn't valid: Expecting ',' at line 3"."""
    if isinstance(e, json.JSONDecodeError):
        return f"{name} isn't valid: {e.msg} at line {e.lineno}"
    if isinstance(e, UnicodeDecodeError):
        return f"{name} isn't a text file wcmods can read (save it as UTF-8)"
    if isinstance(e, OSError):
        return f"{name} can't be read ({e.strerror or e})"
    return f"{name} isn't right: {e}"


def _ids(value):
    """A list of mod ids from mod.json ("requires", "uses"); anything else in it is ignored."""
    if isinstance(value, str):
        value = [value]
    return [v.strip() for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def needed(mods, mod_id):
    """The mods `mod_id` requires, and what they require in turn (ids, nearest first); missing ones too. The
    mod menu (MENU_ID) isn't one: it's wcmods' own."""
    by_id = {m.id: m for m in mods}
    out, todo = [], list(by_id[mod_id].requires) if mod_id in by_id else []
    while todo:
        i = todo.pop(0)
        if i in out or i == mod_id or i == MENU_ID:
            continue
        out.append(i)
        if i in by_id:
            todo += by_id[i].requires
    return out


def used(mods, mod_id):
    """The mods that `mod_id`, and the mods it requires, say they work with ("uses") and that are in the mods
    folder (ids): turned on with it, but never needed. The mod menu isn't one, and nor is a mod it requires."""
    by_id = {m.id: m for m in mods}
    inside = [mod_id] + needed(mods, mod_id)
    out = []
    for i in inside:
        for u in by_id[i].uses if i in by_id else []:
            if u in by_id and u != MENU_ID and u not in inside and u not in out:
                out.append(u)
    return out


def carried(mods, mod_id):
    """What goes along with a mod pack (packs.py): the mods it requires and what they require (ids, missing
    ones too), then the mods those use that are in the mods folder (a story's Sandbox mode), so the pack's
    .zip has them and playing it keeps them on."""
    inside = needed(mods, mod_id)
    return inside + [u for u in used(mods, mod_id) if u not in inside]


def needing(mods, mod_id):
    """The mods that are on and require `mod_id`, directly or through another mod. A mod that only uses it
    isn't one: it works without it."""
    return [m.id for m in mods if m.enabled and m.id != mod_id and mod_id in needed(mods, m.id)]


def version_key(version):
    """A version as something to compare: "0.5" is "0.5.0", "0.4" < "0.5" < "0.10", and anything that isn't a
    version ("", "beta", None) comes before every version."""
    parts = str(version or "").strip().lstrip("vV").split(".")
    try:
        numbers = [int(p) for p in parts]
    except ValueError:
        return (0, ())
    return (1, tuple(numbers + [0] * (3 - len(numbers))))


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
    """Turn a mod on (with the mods it requires, and the mods it uses that are in the mods folder) or off.
    Turning off a mod that others on need only happens with cascade=True, which turns them off too;
    otherwise nothing changes and they're returned. A mod that's only used is never in the way.

    Returns (changed, blocked): [(id, now on)] and the ids of mods that need it."""
    by_id = {m.id: m for m in mods}
    if mod_id not in by_id:
        raise LookupError(f"no mod named {mod_id}")
    changed = []
    if on:
        missing = [i for i in needed(mods, mod_id) if i not in by_id]
        if missing:
            raise ValueError(f"{by_id[mod_id].name} needs {', '.join(missing)}, which isn't in your mods; add it first")
        turn = [mod_id] + needed(mods, mod_id)
        for u in used(mods, mod_id):
            # A used mod comes on only when it can: never one whose mod.json can't be read, or that needs a
            # mod that isn't there (turning this one on doesn't fail for it).
            if not by_id[u].problem and all(i in by_id and not by_id[i].problem for i in needed(mods, u)):
                turn += [u] + needed(mods, u)
        for i in dict.fromkeys(turn):
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
    slots), so quick palette switching leaves it alone. One whose palette.json can't be read counts as a
    preset (palette_problem says what's wrong with it)."""
    if mod.kinds() != ["palette"]:
        return False
    from . import palettes
    try:
        return not palettes.adds_only(palettes.load(os.path.join(mod.folder, "palette.json")))
    except (OSError, ValueError):
        return True


def palette_problem(mod):
    """What's wrong with a mod's palette.json (not JSON, a list, a section that isn't an object of colours),
    or None: for the mod's card, so one mistake never stops the list of mods from showing."""
    path = os.path.join(mod.folder, "palette.json")
    if not os.path.isfile(path):
        return None
    from . import palettes
    try:
        palettes.load(path)
    except ValueError as e:   # a sentence naming the file (palettes.load never raises anything else)
        return str(e)
    return None


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
    """Every mod under mods_root, in priority order. One whose mod.json can't be read is listed all the
    same (Mod.broken, with `problem` saying why), off and empty, rather than stopping the whole list."""
    mods = []
    if os.path.isdir(mods_root):
        for name in sorted(os.listdir(mods_root)):
            folder = os.path.join(mods_root, name)
            if name.startswith("_") or not os.path.isfile(os.path.join(folder, "mod.json")):
                continue
            try:
                mods.append(Mod(folder))
            except (OSError, ValueError) as e:   # ValueError: not JSON, not UTF-8, or not an object
                mods.append(Mod.broken(folder, file_problem("mod.json", e)))
    return sorted(mods, key=lambda m: (m.priority, m.id))


VALID_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def create(mods_root, mod_id, name=None, description="", enabled=False, priority=0, game_build=None):
    """A new, empty mod. game_build: the build of the game it's made on (mod.json "game_builds"); without
    one it counts as made for the build mods were made on before builds were noted, and a newer game
    leaves it out (exe/gamebuild.py)."""
    if not VALID_ID.match(mod_id):
        raise ValueError("mod folder names use lowercase letters, digits, '-', '_' or '.'")
    folder = os.path.join(mods_root, mod_id)
    if os.path.exists(folder):
        raise ValueError(f"a mod named {mod_id} already exists")
    os.makedirs(folder)
    with open(os.path.join(folder, "mod.json"), "w", encoding="utf-8") as f:
        meta = {"name": name or mod_id.replace("-", " ").title(), "description": description,
                "enabled": enabled, "priority": priority}
        if game_build:
            meta["game_builds"] = [game_build]
        json.dump(meta, f, indent=2)
        f.write("\n")
    return Mod(folder)
