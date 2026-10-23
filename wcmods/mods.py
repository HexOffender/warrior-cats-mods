"""Mod discovery.

A mod is a folder under mods/ with a mod.json and any of:
  files/<game path>   loose files that replace the game's (CSV data, configs, movies)
  palette.json        colour palette (sections/palettes.py)
  controls.json       button remaps (sections/controls.py)
  data.json           gameplay data edits (sections/data.py)
  save.json           save edits (sections/savedit.py)
  section.py          the mod's own section, written with wcmods.sdk (opt-in)
  studio/section.js   the mod's own studio page, written with studio/lib/wc.js (opt-in)
Folders starting with '_' are templates and are ignored.
"""
import json
import os
import re

CONTENT = (("files", "files"), ("palette.json", "palette"), ("controls.json", "controls"),
           ("data.json", "data"), ("save.json", "save"), ("section.py", "code"),
           (os.path.join("studio", "section.js"), "studio page"))


class Mod:
    def __init__(self, folder):
        self.folder = folder
        self.id = os.path.basename(folder)
        with open(os.path.join(folder, "mod.json"), encoding="utf-8-sig") as f:
            meta = json.load(f)
        self.meta = meta
        self.name = meta.get("name", self.id)
        self.description = meta.get("description", "")
        self.enabled = bool(meta.get("enabled", True))
        self.priority = int(meta.get("priority", 0))

    def kinds(self):
        return [kind for name, kind in CONTENT if os.path.exists(os.path.join(self.folder, name))]

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
                "priority": self.priority, "kinds": self.kinds()}


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
