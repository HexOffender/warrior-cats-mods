"""Build, install and uninstall: runs every section independently, then writes the outputs."""
import datetime
import json
import os
import re
import shutil
import struct

from . import bridge, catcolours, controls, draw, luacheck, menu, menupages, menusettings, names
from .formats import texture
from .exe import gamebuild
from . import ue4ss, view, world
from . import game as game_lua   # WCModsGame (the name `game` is the game's files in build())
from . import mods as modlib
from .formats.blake3 import blake3
from .config import (MOD_BASENAME, UE4SS_MOD_NAME, game_running, same_folder, steam_elsewhere,
                     steam_elsewhere_text)
from .formats.csvdata import Table
from .gamefiles import GameFiles
from .formats.iostore import ModContainerWriter
from .formats.pak import PakReader, PakWriter
from .formats.save import SAV_NAME, SaveGame, list_backups, write_save
from .formats.savejson import SaveDoc
from .sdk import BuildContext
from .sections import load_sections, savedit
from . import saverecord

MARKER = "Wrc/WCMods/BuildInfo.json"
PAK_PREFIX = "zzz_WCMods_"                  # every pak file wcmods installs starts with this
PAK_EXTS = (".pak", ".utoc", ".ucas", ".sig")


class InstallBlocked(RuntimeError):
    """Not installing, because some mods didn't build: installing replaces what's installed now, so a mod
    that failed would silently lose what it put in the game before. `problems` is [(section title, mod id or
    None, what went wrong)], for each surface to word with its own way past it: the command line says
    --force (str(e)), the studio says Apply the rest anyway (describe)."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__(self.describe("install anyway with --force", "anything they installed before is removed"))

    def describe(self, how, then, lead="not installing because some mods didn't build"):
        said = "; ".join(f"{title}: {mod + ': ' if mod else ''}{text}" for title, mod, text in self.problems)
        return f"{lead}: {said}. Fix or turn off those mods, or {how} ({then})."

    def mods(self):
        """The mods that didn't build, in order, once each."""
        return list(dict.fromkeys(mod for _, mod, _ in self.problems if mod))


def section_problems(rep):
    """What went wrong in one section of a build's report, [(mod id or None, text)]; [] when its status is
    "ok". Its "failed" lines up with its "errors", one for one; a report where it doesn't (an older wcmods
    wrote only the errors' text, or added one without the other) is read from the errors, so nothing that
    went wrong is ever missed. A section that isn't "ok" always has at least one."""
    if rep.get("status") == "ok":
        return []
    errors = list(rep.get("errors") or [])
    failed = rep.get("failed")
    if isinstance(failed, list) and failed and len(failed) >= len(errors):
        found = [(mod, text) for mod, text in failed]
    else:
        found = [(None, e) for e in errors]
    return found or [(None, "it didn't build fully")]


def user_paks(mod):
    """Cooked content a mod ships itself: {stem: {ext: path}} for mods/<id>/paks/<stem>.pak and the
    .utoc/.ucas/.sig beside it (made with Unreal Engine 5.7, see docs/SDK.md, "New content")."""
    folder = os.path.join(mod.folder, "paks")
    out = {}
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            stem, ext = os.path.splitext(name)
            if ext.lower() in PAK_EXTS:
                out.setdefault(stem, {})[ext.lower()] = os.path.join(folder, name)
    return out


def user_pak_name(mod_id, stem):
    """What a mod's own pak is installed as: wcmods' prefix (so it's found and removed with the rest),
    the mod and the file's name, and the _P (patch) suffix that lets it override the game's files."""
    safe = lambda t: re.sub(r"[^A-Za-z0-9-]+", "-", t).strip("-") or "pak"
    return f"{PAK_PREFIX}{safe(mod_id)}_{safe(re.sub(r'_P$', '', stem))}_P"


def saved_folder(cfg):
    """WCMods in the game's Saved folder, beside its saves: the folder scripts keep their own files in
    (Game.save.folder() in WCModsGame), made by every install."""
    return os.path.join(os.path.dirname(os.path.normpath(cfg.save_dir)), "WCMods")


def remove_paks(folder):
    """Remove every pak file wcmods installed (its own and the ones mods ship); returns their paths."""
    gone = []
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if name.startswith(PAK_PREFIX) and os.path.splitext(name)[1].lower() in PAK_EXTS:
                os.remove(os.path.join(folder, name))
                gone.append(os.path.join(folder, name))
    return gone


def names_without_text(cfg, ctx, game):
    """Build warnings for cats in your save named with a mod's own text (an ID with _WCM_ in it) that this
    build doesn't give the game, once the sections' CSV edits are in: the mod that named them is off or left
    out, so the game would show <MISSING STRING TABLE ENTRY>. The game's text is only read when a cat has
    such a name."""
    sav = os.path.join(cfg.save_dir, SAV_NAME)
    try:
        text = SaveGame.load(sav).json_text if os.path.isfile(sav) else ""
        if "_WCM_" not in text:
            return []
        path = BuildContext.data_path(names.strings_path("EN"))
        strings = ctx.files[path][0].decode("utf-8") if path in ctx.files else game.read_text(path)
        keys = {r.fields[0] for r in Table(strings).rows if r.fields}
        missing = names.without_text(names.cats_in_save(SaveDoc(text).data), ctx.save_ops, keys.__contains__)
    except Exception as e:   # said, so the check isn't skipped unseen
        return [f"couldn't check your cats' names against the game's text ({type(e).__name__}: {e})"]
    if not missing:
        return []
    shown = [f"{'your cat' if where == 'you' else where} ({key})" for where, key in missing[:5]]
    if len(missing) > 5:
        shown.append(f"{len(missing) - 5} more")
    them = "it" if len(missing) == 1 else "them"
    cats = "a cat in your save has" if len(missing) == 1 else f"{len(missing)} cats in your save have"
    yours = ", and the HUD calls your cat Cat 1" if any(where == "you" for where, _ in missing) else ""
    return [f"{cats} a name a mod made, and no mod in this build gives the game its text, so the game will show "
            f"{them} as <MISSING STRING TABLE ENTRY>{yours}: {', '.join(shown)}. Turn the mod that named {them} "
            "back on (or, if it's left out as made for an older version of the game, use it anyway), or rename "
            f"{them} on the Names page; Backups and repair puts your save back as it was before"]
# Shared Lua modules installed with any build, for UE4SS scripts to require (docs/SDK.md, "Overlays").
SHARED_LUA = (view, draw, world, menu, game_lua)


def build(cfg, mods, out_dir, log=print):
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    # The installed game's build (gamebuild.py). A mod made for an older version stays out unless the
    # player chose to use it anyway on this build; the in-game module follows what the update moved.
    build = gamebuild.current(cfg)["build"]
    old = gamebuild.outdated(cfg, mods, build)
    # Those mods, and the ones that need them: a game update alone doesn't stop installing.
    left_out = gamebuild.held_back(cfg, mods, build)
    # A mod that needs another mod ("requires" in mod.json) which is missing or off is left out, and
    # the report says why, so installing stops until that's sorted (or --force leaves it out).
    unmet = modlib.unmet(mods, left_out)
    enabled = [m for m in mods if m.enabled and m.id not in unmet and m.id not in left_out]
    titles = {m.id: m.name for m in mods}
    game = GameFiles(cfg)
    sections, skipped = load_sections(cfg, [m for m in mods if m.id not in unmet and m.id not in left_out], log)
    ctx = BuildContext(cfg, game, out_dir, log)
    ctx.mods = enabled   # the enabled mods, for sections that check another kind of file (cats.json and palettes)
    report = {}
    if unmet:
        report["requirements"] = {"title": "Mods that need other mods", "status": "failed", "mods": [],
                                  "errors": [f"{i}: {why}" for i, whys in unmet.items() for why in whys],
                                  "failed": [(i, why) for i, whys in unmet.items() for why in whys],
                                  "from_mod": None}

    for sec in sections:
        ctx.begin(sec.id)
        items, used, errors, failed = [], [], [], []   # failed: [(mod id or None, what went wrong)], as errors
        for mod in enabled:
            try:
                if not sec.claims(mod):
                    continue
                data = sec.collect(mod, ctx)
            except (ValueError, KeyError) as e:   # mistakes in the mod's files
                errors.append(f"{mod.id}: {e}")
                failed.append((mod.id, str(e)))
                continue
            except Exception as e:                # anything else still only skips this mod
                errors.append(f"{mod.id}: {type(e).__name__}: {e} (is the file laid out as documented?)")
                failed.append((mod.id, f"{e} (is the file laid out as documented?)"))
                continue
            if data is not None:
                items.append((mod, data))
                used.append(mod.id)
        status = "ok" if not errors else "partial"
        try:
            sec.build(ctx, items)
        except Exception as e:  # isolate sections: drop this one's outputs, keep going
            ctx.rollback()
            errors.append(f"{type(e).__name__}: {e}")
            failed.append((None, str(e)))
            status = "failed"
        report[sec.id] = {"title": sec.title, "status": status, "mods": used, "errors": errors, "failed": failed,
                          "from_mod": getattr(sec, "owner", None)}
        ctx.end()

    for mod_id in skipped:
        ctx.warnings.append(f"{titles.get(mod_id, mod_id)} brings code of its own (section.py), which only runs with mods "
                            "that run code allowed (Options, on the Settings and repair page; \"allow_code_mods\" in "
                            "wcmods.json); left out")
    # A mod whose mod.json can't be read counts as off (mods.Mod, Mod.broken), so nothing above mentions it: said
    # here, for `wcmods build` and install and for the studio's Apply log, rather than left out without a word.
    for m in mods:
        if getattr(m, "problem", None):
            ctx.warnings.append(f"{m.id} is left out: {m.problem}")

    # What goes wrong after the sections ran goes in "failed" as well as "errors": install reads "failed", and a
    # problem missing from it would let an install go ahead and remove what the section put in before.
    def fail(sid, text):
        rep = report[sid]
        rep["errors"].append(text)
        rep["failed"].append((None, text))
        if rep["status"] == "ok":
            rep["status"] = "partial"

    csv_changes, csv_failures = ctx.resolve_csv_edits()
    for path, section_ids, error in csv_failures:
        for sid in section_ids:
            if sid in report:
                fail(sid, f"{path.rsplit('/', 1)[-1]}: edits not applied ({error})")

    table_changes, table_failures = ctx.resolve_table_rows()
    for name, section_ids, error in table_failures:
        for sid in section_ids:
            if sid in report:
                fail(sid, f"{name}: rows not added ({error})")
    # A section's save edits go with its table edits: a cat's new name is an ID whose text the pak adds, and
    # a new item's inventory entry needs its rows. With a table of theirs left out, the save would point at
    # text or items the game hasn't got (the cat shows as "<MISSING STRING TABLE ENTRY>"), so they stay out too.
    broken = {sid for _, ids, _ in csv_failures + table_failures for sid in ids}
    kept = [op for op in ctx.save_ops if op.get("section") not in broken]
    if len(kept) != len(ctx.save_ops):
        ctx.save_ops = kept
        for sid in broken:
            if sid in report:
                fail(sid, "its save edits were left out too: they'd point at text or items the game wouldn't have")
    # What else leaves a renamed cat without its text: a mod that named one is off now, or the mods go into a
    # copy of the game Steam doesn't start.
    ctx.warnings += names_without_text(cfg, ctx, game)
    steam = steam_elsewhere(cfg)
    if steam:
        ctx.warnings.append(steam_elsewhere_text(steam, cfg.game_dir))

    manifest = {"mods": [m.id for m in enabled], "names": titles, "sections": report, "outputs": [], "ue4ss_mods": [],
                "ue4ss_shared": [], "save_ops": ctx.save_ops, "warnings": ctx.warnings, "notes": ctx.notes,
                "csv_changes": csv_changes, "table_rows": table_changes, "files": sorted(ctx.files),
                "built": datetime.datetime.now().isoformat(timespec="seconds")}
    manifest["outdated"] = [{"id": i, "name": titles[i], "made_for": o["made_for"], "used": o["allowed"]}
                            for i, o in old.items()]
    for o in manifest["outdated"]:
        manifest["warnings"].append(
            f"{o['name']} was made for an older version of the game, so it may not work or may behave "
            "unpredictably; you chose to use it anyway" if o["used"] else
            f"{o['name']} was made for an older version of the game, so it's left out until it's updated "
            "(or you choose to use it anyway)")
    for i, why in left_out.items():
        if i not in old:
            manifest["warnings"].append(f"{titles.get(i, i)} is left out: it {why}")
    # wcmods' own in-game members on this build: as found on a verified one, or where the update moved them.
    fit = gamebuild.layout(cfg, log)
    manifest["game"] = {"build": build, "status": fit["status"], "moved": fit["moved"], "lost": fit["lost"],
                        "layout": gamebuild.layout_key(cfg)}
    if fit["lost"]:
        manifest["warnings"].append(
            "the game updated, and these values couldn't be found again, so what uses them is off until wcmods "
            "is updated: " + ", ".join(gamebuild.describe(k) for k in fit["lost"]))

    if ctx.files or ctx.packages:
        pak = PakWriter()
        for path, (data, _, _) in ctx.files.items():
            pak.add(path, data)
        pak.add(MARKER, json.dumps({"mods": manifest["mods"]}, indent=2).encode())
        pak.write(os.path.join(out_dir, MOD_BASENAME + ".pak"), MOD_BASENAME + ".pak")
        manifest["outputs"].append(MOD_BASENAME + ".pak")
        # The game reads a pak in ~mods only with a container of the same name beside it (seen on build
        # 26184573: a pak of text edits alone was ignored), so one goes with every pak, empty when no
        # package changed.
        container = ModContainerWriter(blake3(MOD_BASENAME.lower().encode(), 8))
        if ctx.packages:
            io = game.io
            header = io.container_header()
        for path, (data, _, _) in ctx.packages.items():
            if path in ctx.new_packages:
                cid, imports, shaders, bulk = ctx.new_packages[path]
                container.add_package(path, cid, data, imports, shaders)
                if bulk is not None:
                    container.add_chunk(path[:-len(".uasset")] + ".ubulk", cid[:11] + bytes([texture.CHUNK_BULK]), bulk)
                continue
            ci = io.chunk_index(path)
            cid = io.chunk_ids[ci]
            imports, shaders = header.entry_for(struct.unpack("<Q", cid[:8])[0])
            container.add_package(path, cid, data, ctx.patch_imports.get(path, imports), shaders)
        container.write(os.path.join(out_dir, MOD_BASENAME + ".utoc"), os.path.join(out_dir, MOD_BASENAME + ".ucas"))
        manifest["outputs"] += [MOD_BASENAME + ".utoc", MOD_BASENAME + ".ucas"]
    # Cooked content mods ship themselves (paks/): copied as they are, under names that load after the
    # game's and come off again on uninstall.
    manifest["paks"] = []
    for m in enabled:
        for stem, files in user_paks(m).items():
            if ".pak" not in files:
                ctx.warnings.append(f"{m.id}: paks/{stem} has no .pak; the game only mounts a .utoc/.ucas next to "
                                    "a .pak of the same name, so it's left out")
                continue
            if (".utoc" in files) != (".ucas" in files):
                ctx.warnings.append(f"{m.id}: paks/{stem} needs both a .utoc and a .ucas (or neither); left out")
                continue
            name = user_pak_name(m.id, stem)
            for ext, src in files.items():
                shutil.copy2(src, os.path.join(out_dir, name + ext))
                manifest["outputs"].append(name + ext)
            if ".utoc" not in files:   # a pak alone isn't read, as wcmods' own isn't: an empty container goes with it
                ModContainerWriter(blake3(name.lower().encode(), 8)).write(
                    os.path.join(out_dir, name + ".utoc"), os.path.join(out_dir, name + ".ucas"))
                manifest["outputs"] += [name + ".utoc", name + ".ucas"]
            manifest["paks"].append({"mod": m.id, "file": f"paks/{stem}", "installed_as": name})
            log(f"  {m.id}: paks/{stem} goes in as {name}")
    # The in-game mod menu's window is wcmods' own: it goes in with every build (the install leaves it out
    # without UE4SS, as it does every UE4SS mod), with the WCModsMenu module that mods add pages with. Its
    # pages about the game are a mod of their own, Menu pages (menupages.py); the window's Overview says how
    # to get it while this build hasn't got it.
    opts = menusettings.menu_settings(cfg)
    if not opts["key_ok"]:
        manifest["warnings"].append(f"the mod menu's key {opts['key_given']!r} (wcmods.json menu_key) isn't one of "
                                    f"{', '.join(menu.KEYS)}; using {menu.DEFAULT_KEY}")
    if not opts["pad_ok"]:
        manifest["warnings"].append(f"the mod menu's controller button {opts['pad_given']!r} (wcmods.json menu_pad) "
                                    f"isn't an Unreal key name; using {menu.DEFAULT_PAD}")
    try:   # where UE4SS's log is, or will be once the game has run with it
        log_path = ue4ss.log_path(cfg.win64_dir) or os.path.join(cfg.win64_dir, "ue4ss", "UE4SS.log")
    except Exception:   # no game found
        log_path = ""
    # The menu's list of installed mods: the ones this build has (not those left out).
    host = menu.host_script(manifest, enabled, opts["key"], scale=opts["size"], pad=opts["pad"],
                            dev=bool(cfg.data.get("allow_code_mods")), log=log_path,
                            pages_note=menupages.note(cfg, mods, {m.id for m in enabled}))
    manifest["warnings"] += [f"{menu.HOST_NAME}: {p}" for p in luacheck.check(host)[:3]]
    ctx.ue4ss_mods[menu.HOST_NAME] = ({"Scripts/main.lua": host.encode(), "enabled.txt": b""}, None)
    manifest["menu"] = {k: opts[k] for k in ("key", "pad", "size")}
    # The game bridge runs Lua that wcmods sends it, so it's code: only with code mods allowed.
    if cfg.data.get("allow_code_mods"):
        ctx.ue4ss_mods[bridge.NAME] = ({"Scripts/main.lua": bridge.script(cfg).encode(), "enabled.txt": b""}, None)
    for name, (files, _) in ctx.ue4ss_mods.items():
        for rel, data in files.items():
            dst = os.path.join(out_dir, "ue4ss", name, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
        manifest["ue4ss_mods"].append(name)
    # Shared Lua modules go in whatever mods are on, for any UE4SS script to require.
    shared_files = {m.SHARED_NAME: m.lua(fit["offsets"], saved_folder(cfg)) if m is game_lua else m.lua()
                    for m in SHARED_LUA}
    plan = None
    try:   # the cats' names, after the enabled name mods, for WCModsWorld's labels
        plan = names.Plan(names.GameNames(lambda path: game.read_text(BuildContext.data_path(path))),
                          names.merge(names.mod_specs(enabled)))
    except Exception as e:   # no game data (no Oodle DLL) or a broken names.json, which the names section reports
        log(f"  (cat names for the mod menu left out: {e})")
    item_labels = {}
    try:   # items' own names, for the Nearby page's labels
        item_labels = world.item_names(ctx)
    except Exception as e:   # no game data (no Oodle DLL)
        log(f"  (item names for the mod menu left out: {e})")
    # Areas' names and quests' titles, for the menu's pages (WCModsNames' N.area and N.quest).
    places = world.place_names(lambda path: game.read_text(path))
    shared_files[world.NAMES_NAME] = world.names_lua(plan, item_labels, places)
    for name, (text, section) in ctx.ue4ss_shared.items():   # the sections' own (items: WCModsItems)
        if name.lower() in {n.lower() for n in shared_files}:   # folders on Windows don't mind the case
            raise ValueError(f"{section}: a shared Lua module {name} is wcmods' own")
        shared_files[name] = text
    for name, text in shared_files.items():
        shared = os.path.join(out_dir, "ue4ss_shared", name)
        os.makedirs(shared)
        with open(os.path.join(shared, name + ".lua"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        manifest["ue4ss_shared"].append(name)
    # The same members for C++ mods (wcmods::member in WCMods.hpp), as found on this build, and the same
    # names (wcmods::cat_name, item_name).
    with open(os.path.join(out_dir, "ue4ss_shared", game_lua.SHARED_NAME, "offsets.json"), "w", encoding="utf-8") as f:
        json.dump(game_lua.offsets_json(fit["offsets"], build), f, indent=2)
    with open(os.path.join(out_dir, "ue4ss_shared", world.NAMES_NAME, "names.json"), "w", encoding="utf-8") as f:
        json.dump(world.names_data(plan, item_labels, places), f, ensure_ascii=False)

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def _newest(folder):
    newest = 0.0
    for d, dirs, files in os.walk(folder):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            newest = max(newest, os.path.getmtime(os.path.join(d, f)))
    return newest


def code_installed(data):
    """The UE4SS mods in the game that run mods' code (the bridge, scripts, C++ mods), from wcmods.json's
    record of the last install (`data`)."""
    from .sections import cpp, scripts
    return sorted(n for n in data.get("installed_ue4ss", [])
                  if n == bridge.NAME or n.startswith((scripts.PREFIX, cpp.PREFIX)))


def pending(cfg, mods):
    """How your mods differ from what's installed: {"installed" (ever), "on" and "off" (ids turned on or off
    since), "changed" (on both times, with files changed since), "redo" (why the last install has to be
    made again: it was made before UE4SS or the Oodle DLL was there, so it left parts out), "any"}. The
    studio's Apply button shows it."""
    # wcmods.json read afresh, without touching the studio's Config: reloading that would throw away what an
    # install running at the same time has noted but not saved yet.
    try:
        data = cfg.peek()
    except (OSError, ValueError):   # not there yet, or being written this moment
        data = cfg.data
    # What an install would put in: mods made for an older version of the game stay out (unless used anyway).
    left_out = set(gamebuild.held_back(cfg, mods))
    now = {m.id for m in mods if m.enabled} - left_out
    inst = data.get("installed")
    if not inst:
        # The mod menu's window goes in with every install, so with the script loader there one is worth
        # making even with no mods on.
        redo = ["the mod menu isn't in the game yet"] if not now and cfg.ue4ss_mods_dir else []
        return {"installed": False, "on": sorted(now), "off": [], "changed": [], "redo": redo, "any": bool(now or redo)}
    was = set(inst.get("mods", []))
    try:
        built = datetime.datetime.fromisoformat(inst.get("built", "")).timestamp()
    except ValueError:
        built = 0.0
    changed = sorted(m.id for m in mods if m.enabled and m.id in was and _newest(m.folder) > built + 1)
    redo = []
    if inst.get("ue4ss") is False and cfg.ue4ss_mods_dir:   # the mod menu at least goes in now
        redo.append("the script loader (UE4SS) is in now")
    # The game updated since (or its exe changed): wcmods' in-game module has to follow it. An install
    # from before the build was recorded was made on the build every one was then.
    build = gamebuild.steam_build(cfg)
    if now and build is not None and build != inst.get("game_build", gamebuild.ASSUMED_BUILDS[0]):
        redo.append(f"the game updated (build {build})")
    elif now and inst.get("layout") and gamebuild.layout_key(cfg) not in (None, inst["layout"]):
        redo.append("the game, or what wcmods knows of it, changed")
    # Scripts and C++ mods in the game find their settings in your mods' folders; an install made while those
    # were somewhere else (wcmods' own folder, before they moved out of it) still points there.
    was_root = inst.get("mods_root") or os.path.join(cfg.root, "mods")
    if now and not same_folder(was_root, cfg.mods_root):
        redo.append(f"your mods moved (to {cfg.mods_root})")
    # An install into another copy of the game (before Use Steam's copy, say) isn't in this one.
    if inst.get("game_dir") and cfg.game_dir and not same_folder(inst["game_dir"], cfg.game_dir):
        redo.append(f"the game folder changed (to {cfg.game_dir})")
    # The mod menu's key, button and size are written into its script at install.
    menu_now = {k: v for k, v in menusettings.menu_settings(cfg, data).items() if k in ("key", "pad", "size")}
    if isinstance(inst.get("menu"), dict) and inst["menu"] != menu_now:
        redo.append("the mod menu's settings changed")
    # A test install (`agent install`) puts code in with "allow_code_mods" off; the next Apply or Play
    # takes it out again.
    if not data.get("allow_code_mods") and code_installed(data):
        redo.append("the game has code from a test install, and mods that run code are off")
    # Save edits made before there was a save were left out; now there is one, they're waiting.
    if inst.get("save_pending") and os.path.isfile(os.path.join(cfg.save_dir, SAV_NAME)):
        redo.append("save edits are waiting for a save")
    out = {"installed": True, "on": sorted(now - was), "off": sorted(was - now), "changed": changed, "redo": redo}
    out["any"] = bool(out["on"] or out["off"] or out["changed"] or redo)
    return out


def apply_palettes(cfg, mods_root, ids, build_dir, backups_root, log=print, force=False):
    """Switch the palette-only mods to ids, then build and install. All or nothing: if the build or
    install fails, the previous choice is put back, so nothing is left switched but not installed.

    Returns (on, manifest).
    """
    if game_running():
        raise RuntimeError("the game is running; close it before applying palettes")
    found = modlib.discover(mods_root)
    before = {m.id: m.enabled for m in found if modlib.palette_only(m)}
    on, _ = modlib.choose_palettes(found, ids)
    log(f"palettes on: {', '.join(on) or 'none (the game colours)'}")
    try:
        build(cfg, modlib.discover(mods_root), build_dir, log)
        return on, install(cfg, build_dir, backups_root, log, force=force)
    except Exception:
        for m in modlib.discover(mods_root):
            if m.id in before and m.enabled != before[m.id]:
                m.set_enabled(before[m.id])
        log("palette choice put back as it was")
        raise


def install(cfg, build_dir, backups_root, log=print, force=False):
    with open(os.path.join(build_dir, "manifest.json"), encoding="utf-8-sig") as f:
        manifest = json.load(f)
    if game_running():
        raise RuntimeError("the game is running; close it before installing mods")
    cfg.reload()
    # Installing replaces what's installed now, so a section that failed or skipped a mod would
    # silently remove that mod's previously installed changes.
    problems = [(rep.get("title", sid), mod, text) for sid, rep in manifest["sections"].items()
                for mod, text in section_problems(rep)]
    if problems and not force:
        raise InstallBlocked(problems)
    dest = cfg.mods_install_dir
    os.makedirs(dest, exist_ok=True)
    remove_paks(dest)   # wcmods' own and any a mod shipped, including ones no longer on
    for name in manifest["outputs"]:
        shutil.copy2(os.path.join(build_dir, name), os.path.join(dest, name))
        log(f"  installed {name}")

    mods_dir = cfg.ue4ss_mods_dir
    previous = set(cfg.data.get("installed_ue4ss", [])) | {UE4SS_MOD_NAME}
    if mods_dir:
        previous |= ue4ss.ours(mods_dir)   # also any the list lost track of
        for name in manifest["ue4ss_mods"]:
            ue4ss.install_mod(mods_dir, name, os.path.join(build_dir, "ue4ss", name))
            log(f"  installed UE4SS mod {name}")
        for name in previous - set(manifest["ue4ss_mods"]):
            ue4ss.remove_mod(mods_dir, name)
        cfg.data["installed_ue4ss"] = manifest["ue4ss_mods"]
        shared = manifest.get("ue4ss_shared", [])
        for name in shared:
            ue4ss.install_shared(mods_dir, name, os.path.join(build_dir, "ue4ss_shared", name))
        for name in set(cfg.data.get("installed_ue4ss_shared", [])) - set(shared):
            ue4ss.remove_shared(mods_dir, name)
        cfg.data["installed_ue4ss_shared"] = shared
        # Lua can't make folders, so the ones the scripts write to are made here: WCMods in the game's Saved
        # folder (WCModsGame's Game.save.folder(): the Menu pages mod's saved travel spots, say) and the
        # bridge's inside it.
        os.makedirs(saved_folder(cfg), exist_ok=True)
        if bridge.NAME in manifest["ue4ss_mods"]:
            os.makedirs(bridge.folder(cfg), exist_ok=True)
        menusettings.apply_console(cfg)
    else:
        skipped = []
        if any(manifest["notes"].get("palettes", {}).get("runtime_palette", {}).values()):
            skipped.append("coat/pattern/marking/eye-button colours")
        if "mouselook" in manifest["notes"]:
            skipped.append("mouse look")
        if manifest.get("menu"):
            skipped.append("the mod menu")
        if skipped:
            log(f"  NOTE: {' and '.join(skipped)} need the script loader (UE4SS), which isn't installed; skipped.")

    save_pending = False
    if manifest["save_ops"]:
        # The paks are in by now: a save edit that fails is said, and the install is still recorded.
        try:
            save_pending = apply_save_ops(cfg, manifest["save_ops"], backups_root, log)["no_save"]
        except Exception as e:   # noqa: BLE001 - said in the log and the warnings, never lost
            log(f"  save edits couldn't be made: {e}")
            manifest["warnings"].append(f"your save edits couldn't be made ({e}); your save is as it was")
    # What the game had then: an install made without UE4SS left parts out, so pending() asks for
    # another once it's there; one made before there was a save left its save edits out.
    game_info = manifest.get("game") or {}
    cfg.data["installed"] = {"mods": manifest["mods"], "built": manifest["built"], "ue4ss": bool(mods_dir),
                             "game_build": game_info.get("build"), "layout": game_info.get("layout"),
                             "mods_root": cfg.mods_root, "menu": manifest.get("menu"), "game_dir": cfg.game_dir}
    if save_pending:
        cfg.data["installed"]["save_pending"] = True
    cfg.save()
    return manifest


def _said(value):
    """A save value in a log line: none for a value that isn't there, else as JSON."""
    return "none" if value is None else json.dumps(value, ensure_ascii=False)


def _made_at(path):
    """When a file was made (its creation time), or None where the system doesn't keep one (Linux)."""
    st = os.stat(path)
    born = getattr(st, "st_birthtime", None)
    if born is None and os.name == "nt":
        born = st.st_ctime   # creation time on Windows before Python 3.12's st_birthtime
    return born


def _had_save(cfg, backups_root, when):
    """Whether there was a save at `when` (a timestamp: the last install's): a backup of one made by then, or
    the save file itself made by then. Unknown (no creation time, and no backup that old) counts as yes, as
    before this was asked."""
    stamp = datetime.datetime.fromtimestamp(when).strftime("%Y%m%d-%H%M%S")
    if any(name[:15] <= stamp and os.path.isfile(os.path.join(backups_root, name, SAV_NAME))
           for name in list_backups(backups_root)):
        return True
    made = _made_at(os.path.join(cfg.save_dir, SAV_NAME))
    return made is None or made <= when + 1


def apply_save_ops(cfg, ops, backups_root, log=print):
    """Make the build's save edits in WrcGame.sav, after a backup when anything changes. An op with "once"
    (a save.json's, unless it says "always") is made once per save: saverecord keeps what was made, and an op
    recorded with the same value is skipped, so playing on past it isn't undone. One with "record" (the Save
    page's) is always made and recorded. The others (renames, looks, controls, starting items) have guards of
    their own. Returns {"changed": [lines for the log], "applied": [{"source", "path", "label", "was", "now"}],
    "backup": the backup's name or None, "no_save": True when there's no save to change yet}."""
    result = {"changed": [], "applied": [], "backup": None, "no_save": False}
    sav = os.path.join(cfg.save_dir, SAV_NAME)
    if not os.path.isfile(sav):
        log("  NOTE: no save yet; launch the game once, then install again to apply save edits.")
        result["no_save"] = True
        return result
    save = SaveGame.load(sav)
    doc = SaveDoc(save.json_text)
    changed = result["changed"]
    # The record of what's been made. With none yet (the first install since edits were made once), the mods
    # of the last install have had theirs made at every install: they're recorded as made, without writing,
    # so a save that has played on past them keeps what it has. Not when that install had no save to make them
    # in (wcmods 0.3 didn't say so; the save made since does): they're still to be made.
    record = saverecord.load(cfg)
    first = record is None
    record = record or {}
    last = cfg.data.get("installed") or {}
    made_before = set()
    if first and not last.get("save_pending"):
        try:
            built = datetime.datetime.fromisoformat(last.get("built", "")).timestamp()
        except ValueError:
            built = 0.0
        # A mod changed since that install may have a new value, which that install never made: not counted.
        if built and _had_save(cfg, backups_root, built):
            made_before = {i for i in last.get("mods", [])
                           if not _newest(os.path.join(cfg.mods_root, i)) > built + 1}
    records = []   # (op, key, value, was, lost_to): what to record once the save is written
    write_record = first

    def source(op):
        return op.get("source") or op.get("section") or "?"

    def wanted(op, key, value):
        """Whether a once-per-save op is to be made now (False: it was, or it was made before this version)."""
        nonlocal write_record
        if not op.get("once"):
            return True
        had = saverecord.entry(record, doc.account, source(op), key)
        if had is not None and had.get("op") == op["op"] and had.get("value") == value:
            return False
        if source(op) in made_before:
            saverecord.note(record, doc.account, source(op), key, op=op["op"], value=value, was=None,
                            label=op.get("label") or key, when=saverecord.now(), backup=None, before=True)
            write_record = True
            return False
        return True

    # Consecutive "set" ops are applied together with one parse of the save. Keyed by path, so a
    # later (higher-priority) op replaces an earlier one, and whether anything changes is decided
    # against the save itself at flush time.
    pending = {}
    labels = {}   # path -> how a name change reads in the log ("Otterpaw -> Mothpaw")
    said = {}     # path -> a set op's path in words ("Fawnstar's level")
    owners = {}   # path -> the recorded ops that set it
    winner = {}   # path -> the op whose value it gets (the last to set it, recorded or not)
    inserted = {}  # an added key's path -> its record's place in records (a later add of it wins)
    removes = []  # remove ops, made after the sets and inserts

    def flush():
        if not pending:
            return
        olds = {p: doc.get(p) for p in pending}
        items = [(p, v) for p, v in pending.items() if olds[p] != v]
        settled = {p for p, v in pending.items() if olds[p] == v}   # already so: recorded, not written
        pending.clear()
        done = []
        if items:
            try:
                doc.set_many(items)
                done = items
            except Exception:
                for p, v in items:   # fall back to one at a time so one bad edit doesn't drop the rest
                    try:
                        doc.set(p, v)
                        done.append((p, v))
                    except Exception as e:
                        log(f"  save edit skipped ({p}): {e}")
        for p, v in done:
            changed.append(labels.get(p) or f"{said.get(p) or p}: {_said(olds[p])} -> {_said(v)}")
        for p in settled | {p for p, _ in done}:
            # Every op that set it, so a lower mod's isn't made next time instead; the ones another op won over
            # are recorded as not made.
            for op in owners.pop(p, []):
                won = winner.get(p)
                records.append((op, p, op["value"], olds[p], None if won is op else source(won) if won else "?"))
        owners.clear()
        winner.clear()

    for op in ops:
        if op["op"] == "set":
            try:
                doc.get(op["path"])   # the path must exist; nothing else touches the doc until flush
            except (KeyError, IndexError, ValueError, TypeError):
                log(f"  save edit skipped ({op.get('section')}): your save has no value at {op['path']}")
                continue
            if not wanted(op, op["path"], op["value"]):
                continue
            pending[op["path"]] = op["value"]
            labels.pop(op["path"], None)
            said[op["path"]] = op.get("label")
            winner[op["path"]] = op
            if op.get("once") or op.get("record"):
                owners.setdefault(op["path"], []).append(op)
            continue
        if op["op"] == "remove":
            if wanted(op, op["path"], None):
                removes.append(op)
            continue
        if op["op"] == "name":
            # A cat's name lives inside its save text: change just the name IDs, and only if the cat
            # still has the name it had when the mods were built.
            try:
                current = pending[op["path"]] if op["path"] in pending else doc.get(op["path"])
            except (KeyError, IndexError, ValueError, TypeError):
                log(f"  name skipped ({op.get('from')}): your save has no cat at {op['path']}")
                continue
            new = names.rename_struct(current, op["set"], op["expect"]) if isinstance(current, str) else None
            if new is None:
                log(f"  name skipped ({op.get('from')}): that cat's name changed since the build; install again")
            elif new != current:
                pending[op["path"]] = new
                winner[op["path"]] = op
                labels[op["path"]] = f"name: {op.get('from')} -> {op.get('to')} ({op.get('where', op['path'])})"
            continue
        if op["op"] == "fields":
            # Number fields inside a cat's save text (a cat's colour slots, scars and look).
            try:
                current = pending[op["path"]] if op["path"] in pending else doc.get(op["path"])
            except (KeyError, IndexError, ValueError, TypeError):
                log(f"  {op.get('who', 'your cat')}: skipped, your save has no cat at {op['path']}")
                continue
            if isinstance(current, str):
                new = catcolours.set_fields(current, op["set"])
                if new != current:
                    pending[op["path"]] = new
                    winner[op["path"]] = op
                    labels[op["path"]] = f"{op.get('who', 'your cat')}: {op.get('label', op['set'])}"
            continue
        flush()
        try:
            if op["op"] == "controls":
                text, applied, warnings = controls.apply(doc.text, op["changes"])
                for w in warnings:
                    log(f"  controls warning: {w}")
                doc = SaveDoc(text)
                changed += [f"{d}: {a}: {o} -> {n}" for d, a, o, n in applied if o != n]
            elif op["op"] == "insert":
                full = f"{op['path']}/{op['key']}"
                old = doc.get(full) if doc.exists(full) else None
                if old is not None and op.get("only_new"):
                    continue
                if not wanted(op, full, op["value"]):
                    continue
                if old != op["value"]:
                    doc.insert(op["path"], op["key"], op["value"])
                    changed.append(f"{op.get('label') or full}: {_said(old)} -> {_said(op['value'])}")
                if op.get("once") or op.get("record"):
                    if full in inserted:   # added by another op before, this install: this one's value went in
                        i = inserted[full]
                        o, k, v, old, _ = records[i]   # what was there before either
                        records[i] = (o, k, v, old, source(op))
                    inserted[full] = len(records)
                    records.append((op, full, op["value"], old, None))
        except (KeyError, IndexError, ValueError, TypeError) as e:
            log(f"  save edit skipped ({op.get('section')}): {e}")
    flush()
    # Removals last, list elements from the highest index down so the others keep theirs.
    def order(op):
        last_part = op["path"].rstrip("/").rsplit("/", 1)[-1]
        return (op["path"].rstrip("/").rsplit("/", 1)[0], -int(last_part) if last_part.isdigit() else 0)
    for op in sorted(removes, key=order):
        problem = savedit.remove_problem(op["path"], doc)
        if problem:   # a whole cat, the game's settings, a cat's progress: never taken out
            log(f"  save edit skipped ({source(op)}): {problem}")
            continue
        if not doc.exists(op["path"]):
            records.append((op, op["path"], None, None, None))   # already gone: nothing to do, ever
            continue
        try:
            old = doc.get(op["path"])
            doc.delete(op["path"])
            changed.append(f"{op.get('label') or op['path']}: {_said(old)} -> removed")
            records.append((op, op["path"], None, old, None))
        except (KeyError, IndexError, ValueError, TypeError) as e:
            log(f"  save edit skipped ({op.get('section')}): {e}")
    if changed:
        # The backup keeps the record as it is before these changes, for a restore to put back with it.
        where, _ = saverecord.backup(cfg, backups_root, "before-save-edits")
        log(f"  backed up saves -> {where}")
        save.json_text = doc.text
        write_save(cfg.save_dir, save)
        result["backup"] = os.path.basename(where)
        for c in changed:
            log(f"  save: {c}")
    else:
        log("  save already matches; nothing to change")
    when = saverecord.now()
    for op, key, value, was, lost_to in records:
        made = was != value and not lost_to
        if made:
            result["applied"].append({"source": source(op), "path": key, "label": op.get("label") or key,
                                      "was": was, "now": value, "op": op["op"]})
        fields = {"op": op["op"], "value": value, "was": was, "label": op.get("label") or key, "when": when,
                  "backup": result["backup"] if made else None}
        if lost_to:   # another op's value went in: not made, and not made later instead of that one
            fields["lost_to"] = lost_to
        saverecord.note(record, doc.account, source(op), key, **fields)
        write_record = True
    if write_record:
        saverecord.store(cfg, record)
    return result


def undo_save_change(cfg, source, key, backups_root, log=print):
    """Put back what a recorded save change replaced (its "was"), after a backup, and mark the record undone,
    so a mod that is still on doesn't make it again. Returns {"label", "before": what the save held just
    before, "now": what it holds now, "backup"}."""
    sav = os.path.join(cfg.save_dir, SAV_NAME)
    if not os.path.isfile(sav):
        raise LookupError("no save yet; start the game once")
    save = SaveGame.load(sav)
    doc = SaveDoc(save.json_text)
    record = saverecord.load(cfg) or {}
    entry = saverecord.entry(record, doc.account, source, key)
    if entry is None:
        raise LookupError("that change isn't in the record of changes to this save")
    if entry.get("before"):
        raise ValueError("that change was made before wcmods kept a record of them, so what it replaced isn't known; "
                         "Settings and repair puts a whole backup back")
    if entry.get("undone"):
        raise ValueError("that change was put back already")
    if entry.get("lost_to"):
        raise ValueError(f"that change wasn't made: {entry['lost_to']}'s change there went in instead")
    before = doc.get(key) if doc.exists(key) else None
    was = entry.get("was")
    parent, _, last = key.rstrip("/").rpartition("/")
    if entry.get("op") == "insert" and was is None:   # an item that wasn't there: it goes again
        if doc.exists(key):
            doc.delete(key)
    elif doc.exists(key):
        doc.set(key, was)
    elif was is not None:   # removed since (or by the change): it comes back
        doc.insert(parent, last, was)
    if doc.text != save.json_text:
        where, _ = saverecord.backup(cfg, backups_root, "before-put-back")   # the record before it's undone
        log(f"  backed up saves -> {where}")
        save.json_text = doc.text
        write_save(cfg.save_dir, save)
        entry["undone_backup"] = os.path.basename(where)
    log(f"  save: {entry.get('label') or key}: {_said(before)} -> {_said(was)} (put back)")
    entry["undone"] = saverecord.now()
    saverecord.store(cfg, record)
    return {"label": entry.get("label") or key, "before": before, "now": was, "backup": entry.get("undone_backup")}


def install_outdated(cfg):
    """True when the installed mod pak was built by an older wcmods in a way the game never reads: with no
    container beside it (the game reads a pak in ~mods only with one), or with file names the engine never
    matches (see pak._read_file_name). Installing fixes it."""
    path = os.path.join(cfg.mods_install_dir, MOD_BASENAME + ".pak") if cfg.game_dir else None
    if not path or not os.path.isfile(path):
        return False
    if not os.path.isfile(os.path.join(cfg.mods_install_dir, MOD_BASENAME + ".utoc")):
        return True
    try:
        return PakReader(path).legacy_file_names > 0
    except (OSError, ValueError, struct.error):
        return False


def uninstall(cfg, log=print):
    if game_running():
        raise RuntimeError("the game is running; close it before uninstalling mods")
    cfg.reload()
    removed = remove_paks(cfg.mods_install_dir)
    mods_dir = cfg.ue4ss_mods_dir
    if mods_dir:
        for name in set(cfg.data.get("installed_ue4ss", [])) | {UE4SS_MOD_NAME} | ue4ss.ours(mods_dir):
            if os.path.isdir(os.path.join(mods_dir, name)):
                ue4ss.remove_mod(mods_dir, name)
                removed.append(os.path.join(mods_dir, name))
        cfg.data["installed_ue4ss"] = []
        for name in set(cfg.data.get("installed_ue4ss_shared", [])) | {m.SHARED_NAME for m in SHARED_LUA} | {world.NAMES_NAME}:
            gone = ue4ss.remove_shared(mods_dir, name)
            if gone:
                removed.append(gone)
        cfg.data["installed_ue4ss_shared"] = []
    cfg.data.pop("installed", None)
    cfg.save()
    for p in removed:
        log(f"  removed {p}")
    return removed
