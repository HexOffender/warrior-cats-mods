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

What's wrong with a script's files (problems) is said in the creator's words, on the mod's card in the
studio before any Apply, and as the build's warnings: a script whose Lua won't load is left as it is (only
it fails in the game; the rest of the install is fine), while a settings.json that isn't an object, or two
mods that would install into one folder, keep the mod out (collect raises).
"""
import json
import os

from .. import luacheck
from ..mods import file_problem, safe_name, same_install
from ..sdk import Section, lua_value
from ..lua import source as lua_source

FOLDER = "scripts"
SETTINGS = "settings.json"
PREFIX = "WCModsScript_"
WONT_RUN = "so the script won't run"

BOOTSTRAP = lua_source("script_bootstrap.lua")


def ue4ss_name(mod_id):
    """The UE4SS mod a mod's scripts are installed as."""
    return PREFIX + safe_name(mod_id)


def has_scripts(mod):
    return os.path.isdir(os.path.join(mod.folder, FOLDER))


def read_settings(mod):
    """A script mod's settings.json as a dict ({} without one), and its path (or None). A file that isn't JSON,
    or isn't an object, is a ValueError saying so in the creator's words."""
    path = os.path.join(mod.folder, SETTINGS)
    if not os.path.isfile(path):
        return {}, None
    try:
        with open(path, encoding="utf-8-sig") as f:
            settings = json.load(f)
    except (ValueError, OSError) as e:
        raise ValueError(file_problem(SETTINGS, e)) from None
    if not isinstance(settings, dict):
        raise ValueError(f'{SETTINGS} should hold an object: {{"name": value, ...}}')
    return settings, os.path.abspath(path)


def lua_problems(files, most=1):
    """What would stop the Lua in a script's files ({"main.lua": bytes, ...}, as read_tree gives) from loading,
    as sentences naming the file and line: "scripts/main.lua, line 1: a "function" is never closed with "end",
    so the script won't run". The first `most` of each file's: one missing end leaves the brackets around it
    open too, so the first is the one to fix."""
    out = []
    for rel, blob in sorted(files.items()):
        if not rel.endswith(".lua"):
            continue
        text = blob if isinstance(blob, str) else blob.decode("utf-8", "replace")
        # As the script bootstrap loads it (loadOwn): a byte order mark (Notepad's) and a first line for a shell
        # ("#!...") are passed over.
        text = text.lstrip("﻿")
        if text.startswith("#"):
            text = "--" + text
        out += [f"{FOLDER}/{rel}, {luacheck.explain(p)}, {WONT_RUN}" for p in luacheck.check(text)[:most]]
    return out


_problems = {}   # mod folder -> (the files' sizes and times, the problems found then)


def problems(mod):
    """Everything wrong with a mod's scripts/ and settings.json now, as sentences for its card: a missing
    main.lua, a settings.json that isn't an object (or isn't JSON), and Lua that won't load. Kept until one of
    the files changes (by size or time), since the Mods page asks every time it draws. [] without scripts/."""
    folder = os.path.join(mod.folder, FOLDER)
    if not os.path.isdir(folder):
        return []
    stamp = []
    for root, _, names in os.walk(folder):
        for name in sorted(names):
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
                stamp.append((os.path.relpath(path, folder), st.st_size, st.st_mtime_ns))
            except OSError:
                pass
    try:
        st = os.stat(os.path.join(mod.folder, SETTINGS))
        stamp.append((SETTINGS, st.st_size, st.st_mtime_ns))
    except OSError:
        pass
    stamp = tuple(sorted(stamp))
    hit = _problems.get(mod.folder)
    if hit and hit[0] == stamp:
        return list(hit[1])
    found = []
    if not os.path.isfile(os.path.join(folder, "main.lua")):
        found.append(f"{FOLDER}/ needs a main.lua (it runs when the game starts), {WONT_RUN}")
    try:
        read_settings(mod)
    except ValueError as e:
        found.append(str(e))
    try:
        found += lua_problems(Section.read_tree(folder))
    except OSError as e:
        found.append(f"{FOLDER}/ can't be read ({e.strerror or e})")
    _problems[mod.folder] = (stamp, found)
    return list(found)


def clash(mod, mods):
    """The sentence saying another enabled script mod in `mods` would go in as the same UE4SS mod as `mod` (their
    ids differ only in punctuation or case, and Windows' folders don't tell those apart), or None."""
    others = [m.id for m in mods if m.enabled and same_install(m.id, mod.id) and has_scripts(m)]
    if not others:
        return None
    ids = sorted([mod.id] + others)
    return (f"{', '.join(ids[:-1])} and {ids[-1]} would both go in as {ue4ss_name(ids[0])}: rename one of them "
            "(their names differ only in punctuation or capitals)")


def clashes(mods):
    """{mod id: clash sentence} for every enabled script mod that shares its UE4SS name with another."""
    out = {}
    for m in mods:
        if m.enabled and has_scripts(m):
            said = clash(m, mods)
            if said:
                out[m.id] = said
    return out


class ScriptsSection(Section):
    id = "scripts"
    title = "In-game scripts"
    files = (FOLDER, SETTINGS)   # settings.json only with scripts/ (claims), for the studio's check at save

    def claims(self, mod):
        return has_scripts(mod)

    def collect(self, mod, ctx):
        folder = os.path.join(mod.folder, FOLDER)
        if not os.path.isfile(os.path.join(folder, "main.lua")):
            raise ValueError("scripts/ needs a main.lua (it runs when the game starts)")
        # Checked here, not in build: a mistake here keeps out only these mods, while one in build would take
        # every script mod out of the install (the section is rolled back as a whole).
        said = clash(mod, ctx.mods)
        if said:
            raise ValueError(said)
        files = self.read_tree(folder)
        settings, settings_file = read_settings(mod)
        return {"files": files, "settings": settings, "settings_file": settings_file, "problems": lua_problems(files)}

    def build(self, ctx, items):
        if not ctx.cfg.data.get("allow_code_mods"):
            for mod, _ in items:
                ctx.warn(f"{mod.name} has an in-game script (scripts/), which only runs with mods that run code allowed "
                         "(Options, on the Settings and repair page; \"allow_code_mods\" in wcmods.json); left out")
                ctx.note(mod.id, {"left out": "mods that run code are off"})
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
            # The mod's own Lua was checked in collect, and is said in its own words: only wcmods' part here.
            for problem in luacheck.check(main)[:3]:
                ctx.warn(f"{name}/Scripts/main.lua: {problem}")
            for problem in data["problems"]:
                ctx.warn(f"{mod.name}: {problem}")
            ctx.add_ue4ss_mod(name, files, check=False)
            note = {"installed as": name, "files": sorted(data["files"]),
                    "settings": sorted(k for k in data["settings"] if not str(k).startswith("_"))}
            if data["problems"]:
                note["problems"] = data["problems"]
            ctx.note(mod.id, note)
            ctx.log(f"  {mod.id}: scripts/ goes in as {name}")
