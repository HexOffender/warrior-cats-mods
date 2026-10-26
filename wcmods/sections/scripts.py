"""In-game scripts without any Python: a mod's scripts/ folder runs in the game through UE4SS.

    mods/my-mod/
      mod.json
      scripts/main.lua      runs when the game starts (more .lua files beside it can be require'd)
      settings.json         optional: the script's settings, as MOD.settings; the mod menu gets a page
                            to change them live and save them back

Each mod's scripts become a UE4SS mod of their own, WCModsScript_<mod id>. Its main.lua is written by
wcmods: it sets up MOD (the mod's id, name, settings and a few helpers) and Game (WCModsGame), then runs
the mod's own scripts/main.lua. Scripts are code, so they only run with "allow_code_mods": true in
wcmods.json, like section.py. docs/scripting.md has the details.
"""
import json
import os
import re

from ..sdk import Section, lua_value
from ..lua import source as lua_source

FOLDER = "scripts"
PREFIX = "WCModsScript_"

BOOTSTRAP = lua_source("script_bootstrap.lua")


def ue4ss_name(mod_id):
    """The UE4SS mod a mod's scripts are installed as."""
    return PREFIX + re.sub(r"[^A-Za-z0-9]+", "_", mod_id).strip("_")


class ScriptsSection(Section):
    id = "scripts"
    title = "In-game scripts"
    files = (FOLDER,)

    def collect(self, mod, ctx):
        folder = os.path.join(mod.folder, FOLDER)
        if not os.path.isfile(os.path.join(folder, "main.lua")):
            raise ValueError("scripts/ needs a main.lua (it runs when the game starts)")
        files = self.read_tree(folder)
        settings, settings_file = {}, None
        if os.path.isfile(os.path.join(mod.folder, "settings.json")):
            settings = self.read_json(mod, "settings.json")
            if not isinstance(settings, dict):
                raise ValueError("settings.json should hold an object: {\"name\": value, ...}")
            settings_file = os.path.abspath(os.path.join(mod.folder, "settings.json"))
        return {"files": files, "settings": settings, "settings_file": settings_file}

    def build(self, ctx, items):
        if not ctx.cfg.data.get("allow_code_mods"):
            for mod, _ in items:
                ctx.warn(f"{mod.id}: has in-game scripts (scripts/, code); set \"allow_code_mods\": true in wcmods.json "
                         "to let them run")
            return
        try:
            fallback = ctx.cfg.ue4ss_mods_dir
        except Exception:   # no game found; the script works out its own folder anyway
            fallback = None
        for mod, data in items:
            name = ue4ss_name(mod.id)
            here = (os.path.join(fallback, name, "Scripts") + os.sep).replace("\\", "/") if fallback else ""
            main = (BOOTSTRAP.replace("@NAME@", mod.name.replace("\n", " ")).replace("@ID@", mod.id)
                    .replace("@FALLBACK@", lua_value(here)).replace("@ID_LUA@", lua_value(mod.id))
                    .replace("@NAME_LUA@", lua_value(mod.name)).replace("@FOLDER_LUA@", lua_value(os.path.abspath(mod.folder)))
                    .replace("@SETTINGS@", lua_value(data["settings"])).replace("@SETTINGS_FILE@", lua_value(data["settings_file"]))
                    .replace("@AUTO_PAGE@", "true" if mod.meta.get("settings_page", True) else "false"))
            files = {"Scripts/main.lua": main, "enabled.txt": ""}
            for rel, blob in data["files"].items():
                files["Scripts/mod/" + rel] = blob
            ctx.add_ue4ss_mod(name, files)
            ctx.note(mod.id, {"installed as": name, "files": sorted(data["files"]),
                              "settings": sorted(k for k in data["settings"] if not str(k).startswith("_"))})
            ctx.log(f"  {mod.id}: scripts/ goes in as {name}")
