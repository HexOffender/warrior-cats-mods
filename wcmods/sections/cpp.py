"""C++ mods: a mod's dlls/main.dll runs in the game as a UE4SS C++ mod.

    mods/my-mod/
      mod.json
      cpp/                  the source: CMakeLists.txt and src/ (`wcmods cpp build my-mod` builds it)
      dlls/main.dll         the C++ mod, which `cpp build` makes (or a mod ships built)
      dlls/build.json       which UE4SS it was built against (`cpp build` writes it)
      settings.json         optional: its settings, which wcmods::settings() reads (WCMods.hpp)

Each mod's DLL becomes a UE4SS mod of its own, WCModsCpp_<mod id>, with a wcmods.json beside it naming the
mod, its folder and its settings file (WCMods.hpp reads it). A C++ mod is built against one build of UE4SS
and can crash the game with another, so a DLL whose build.json names another UE4SS than the game's is left
out. C++ mods are code, so they only run with "allow_code_mods": true in wcmods.json, like scripts/.
docs/SDK.md, "C++ mods", has the details.
"""
import json
import os
import re

from .. import ue4ss
from ..exe import pe
from ..cppmods import BUILD_INFO, DLLS, SOURCE
from ..mods import safe_name, same_install
from ..sdk import Section

PREFIX = "WCModsCpp_"
EXPORTS = ("start_mod", "uninstall_mod")    # what UE4SS calls in a C++ mod's main.dll
SKIP_DIRS = {"out", "build", "bin", "obj"}     # build output in cpp/ (and cmake-build-*, IDEs'), not source
VARIANT = re.compile(r"^[0-9a-fA-F]{7,40}$")   # dlls/<UE4SS commit>/: a build for that UE4SS


def ue4ss_name(mod_id):
    """The UE4SS mod a mod's C++ is installed as."""
    return PREFIX + safe_name(mod_id)


def source_time(folder):
    """When the newest file in a mod's cpp/ changed, or 0 without one."""
    newest = 0
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith((".", "cmake-build"))]
        for name in names:
            newest = max(newest, os.path.getmtime(os.path.join(root, name)))
    return newest


def same_commit(a, b):
    """Whether two git commit names (a short one and a long one, say) name the same commit: the shorter is the
    longer's start. None when either is missing."""
    a, b = str(a or "").lower(), str(b or "").lower()
    if not a or not b:
        return None
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def matches(built_for, installed):
    """Whether a DLL built against `built_for` (its build.json) suits the game's UE4SS (`installed`, from
    ue4ss.loader_identity): True, False, or None when it can't be told."""
    if not built_for or not installed:
        return None
    if built_for.get("ue4ss_dll") and built_for["ue4ss_dll"] == installed["dll"]:
        return True
    return same_commit(built_for.get("ue4ss"), installed.get("commit"))


def check_dll(path):
    """Refuse a main.dll UE4SS couldn't load as a C++ mod: not a 64-bit DLL, or without its two exports."""
    try:
        image = pe.Image(path)
    except Exception as e:   # a truncated or foreign file fails anywhere in the headers
        raise ValueError(f"dlls/main.dll isn't a 64-bit Windows DLL ({e})") from None
    if not image.is_dll or image.machine != 0x8664:
        raise ValueError("dlls/main.dll isn't a 64-bit Windows DLL")
    missing = [n for n in EXPORTS if n not in image.exports()]
    if missing:
        raise ValueError(f"dlls/main.dll doesn't export {' and '.join(missing)}, so it isn't a UE4SS C++ mod "
                         "(see docs/SDK.md, \"C++ mods\")")


class CppSection(Section):
    id = "cpp"
    title = "C++ mods"
    files = (DLLS, SOURCE)

    def collect(self, mod, ctx):
        # Two mods whose ids differ only in punctuation or case would go in as one UE4SS mod, the second
        # replacing the first: both are kept out, by name (here, not in build, so the other C++ mods still go in).
        others = sorted(m.id for m in ctx.mods if m.enabled and same_install(m.id, mod.id) and self.claims(m))
        if others:
            ids = sorted([mod.id] + others)
            raise ValueError(f"{', '.join(ids[:-1])} and {ids[-1]} would both go in as {ue4ss_name(ids[0])}: rename "
                             "one of them (their names differ only in punctuation or capitals)")
        folder = os.path.join(mod.folder, DLLS)
        # A mod can carry builds for several UE4SS versions as dlls/<commit>/ (`cpp build --keep`): when
        # dlls/main.dll isn't for the game's UE4SS (its build.json says), the main.dll and build.json kept for
        # it are used instead. A fresh dlls/main.dll for the game's UE4SS wins over a kept one, so a build
        # without --keep is what's installed. The rest of dlls/ (a helper DLL, say) goes in either way; the
        # versions' folders don't.
        variant = None
        try:
            installed = ue4ss.loader_identity(ctx.cfg.win64_dir)
        except Exception:   # no game found
            installed = None
        own = None
        if os.path.isfile(os.path.join(folder, BUILD_INFO)):
            own = self.read_json(mod, os.path.join(DLLS, BUILD_INFO))
        if installed and installed.get("commit") and matches(own if isinstance(own, dict) else None, installed) is not True:
            for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                if VARIANT.match(name) and same_commit(name, installed["commit"]) \
                        and os.path.isfile(os.path.join(folder, name, "main.dll")):
                    variant = name
        main_dir = os.path.join(folder, variant) if variant else folder
        main = os.path.join(main_dir, "main.dll")
        has_source = os.path.isfile(os.path.join(mod.folder, SOURCE, "CMakeLists.txt"))
        if not os.path.isfile(main):
            if has_source:
                raise ValueError(f"its C++ (cpp/) isn't built yet: run `python wcmods.py cpp build {mod.id}`")
            raise ValueError("dlls/ needs a main.dll (a UE4SS C++ mod)")
        check_dll(main)
        files = {rel: data for rel, data in self.read_tree(folder, skip=(BUILD_INFO,)).items()
                 if "/" not in rel or not VARIANT.match(rel.split("/")[0])}
        if variant:
            with open(main, "rb") as f:
                files["main.dll"] = f.read()
        built_for = None
        if os.path.isfile(os.path.join(main_dir, BUILD_INFO)):
            built_for = self.read_json(mod, os.path.relpath(os.path.join(main_dir, BUILD_INFO), mod.folder))
            if not isinstance(built_for, dict):
                raise ValueError(f"dlls/{BUILD_INFO} should hold an object: {{\"ue4ss\": commit, ...}}")
        settings, settings_file = {}, None
        if os.path.isfile(os.path.join(mod.folder, "settings.json")):
            settings = self.read_json(mod, "settings.json")
            if not isinstance(settings, dict):
                raise ValueError("settings.json should hold an object: {\"name\": value, ...}")
            settings_file = os.path.abspath(os.path.join(mod.folder, "settings.json"))
        stale = has_source and source_time(os.path.join(mod.folder, SOURCE)) > os.path.getmtime(main)
        return {"files": files, "built_for": built_for, "settings": settings, "settings_file": settings_file,
                "stale": stale, "variant": variant}

    def build(self, ctx, items):
        if not ctx.cfg.data.get("allow_code_mods"):
            for mod, _ in items:
                ctx.warn(f"{mod.id}: has a C++ mod (dlls/, code); set \"allow_code_mods\": true in wcmods.json "
                         "to let it run")
            return
        try:
            installed = ue4ss.loader_identity(ctx.cfg.win64_dir)
        except Exception:   # no game found
            installed = None
        for mod, data in items:
            built_for = data["built_for"]
            fits = matches(built_for, installed)
            if fits is False:
                ctx.warn(f"{mod.id}: its C++ mod was built for UE4SS {str(built_for.get('ue4ss') or '?')[:8]} and the "
                         f"game has UE4SS {installed['commit'][:8] if installed.get('commit') else '(another build)'}; "
                         "left out, since a C++ mod built for another UE4SS can crash the game. Build it again "
                         f"(`python wcmods.py cpp build {mod.id}`) or get one built for this UE4SS")
                continue
            if fits is None and installed:
                ctx.warn(f"{mod.id}: can't tell which UE4SS its C++ mod was built for"
                         + ("" if built_for else f" (it has no dlls/{BUILD_INFO})")
                         + "; if the game closes as it starts, turn this mod off")
            if data["stale"]:
                ctx.warn(f"{mod.id}: cpp/ changed after dlls/main.dll was built; `python wcmods.py cpp build "
                         f"{mod.id}` builds it again")
            name = ue4ss_name(mod.id)
            info = {"id": mod.id, "name": mod.name, "version": mod.version, "author": mod.author,
                    "description": mod.description, "folder": os.path.abspath(mod.folder),
                    "settings_file": data["settings_file"], "settings": data["settings"]}
            files = {"dlls/" + rel: blob for rel, blob in data["files"].items()}
            files["wcmods.json"] = json.dumps(info, indent=2, ensure_ascii=False)
            files["enabled.txt"] = ""
            ctx.add_ue4ss_mod(name, files)
            ctx.note(mod.id, {"installed as": name, "dlls": sorted(data["files"]),
                              "built for UE4SS": (built_for or {}).get("ue4ss"), "variant": data["variant"]})
            ctx.log(f"  {mod.id}: dlls/{data['variant'] + '/' if data['variant'] else ''}main.dll goes in as {name}")
