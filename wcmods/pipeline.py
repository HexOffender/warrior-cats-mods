"""Build, install and uninstall: runs every section independently, then writes the outputs."""
import datetime
import json
import os
import re
import shutil
import struct

from . import bridge, catcolours, controls, draw, gamebuild, luacheck, menu, menupages, menusettings, names, texture
from . import ue4ss, view, world
from . import game as game_lua   # WCModsGame (the name `game` is the game's files in build())
from . import mods as modlib
from .blake3 import blake3
from .config import MOD_BASENAME, UE4SS_MOD_NAME, Config, game_running
from .gamefiles import GameFiles
from .iostore import ModContainerWriter
from .pak import PakReader, PakWriter
from .save import SAV_NAME, SaveGame, backup, write_save
from .savejson import SaveDoc
from .sdk import BuildContext
from .sections import load_sections

MARKER = "Wrc/WCMods/BuildInfo.json"
PAK_PREFIX = "zzz_WCMods_"                  # every pak file wcmods installs starts with this
PAK_EXTS = (".pak", ".utoc", ".ucas", ".sig")


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


def remove_paks(folder):
    """Remove every pak file wcmods installed (its own and the ones mods ship); returns their paths."""
    gone = []
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if name.startswith(PAK_PREFIX) and os.path.splitext(name)[1].lower() in PAK_EXTS:
                os.remove(os.path.join(folder, name))
                gone.append(os.path.join(folder, name))
    return gone
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
    game = GameFiles(cfg)
    sections, skipped = load_sections(cfg, [m for m in mods if m.id not in unmet and m.id not in left_out], log)
    ctx = BuildContext(cfg, game, out_dir, log)
    ctx.mods = enabled   # the enabled mods, for sections that check another kind of file (cats.json and palettes)
    report = {}
    if unmet:
        report["requirements"] = {"title": "Mods that need other mods", "status": "failed", "mods": [],
                                  "errors": [f"{i}: {why}" for i, whys in unmet.items() for why in whys],
                                  "from_mod": None}

    for sec in sections:
        ctx.begin(sec.id)
        items, used, errors = [], [], []
        for mod in enabled:
            try:
                if not sec.claims(mod):
                    continue
                data = sec.collect(mod, ctx)
            except (ValueError, KeyError) as e:   # mistakes in the mod's files
                errors.append(f"{mod.id}: {e}")
                continue
            except Exception as e:                # anything else still only skips this mod
                errors.append(f"{mod.id}: {type(e).__name__}: {e} (is the file laid out as documented?)")
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
            status = "failed"
        report[sec.id] = {"title": sec.title, "status": status, "mods": used, "errors": errors,
                          "from_mod": getattr(sec, "owner", None)}
        ctx.end()

    for mod_id in skipped:
        ctx.warnings.append(f"{mod_id}: ships its own section.py (Python code); set \"allow_code_mods\": true "
                            "in wcmods.json to let it run")

    csv_changes, csv_failures = ctx.resolve_csv_edits()
    for path, section_ids, error in csv_failures:
        for sid in section_ids:
            rep = report.get(sid)
            if rep is not None:
                rep["errors"].append(f"{path.rsplit('/', 1)[-1]}: edits not applied ({error})")
                if rep["status"] == "ok":
                    rep["status"] = "partial"

    table_changes, table_failures = ctx.resolve_table_rows()
    for name, section_ids, error in table_failures:
        for sid in section_ids:
            rep = report.get(sid)
            if rep is not None:
                rep["errors"].append(f"{name}: rows not added ({error})")
                if rep["status"] == "ok":
                    rep["status"] = "partial"
    # A section's save edits go with its table edits: a cat's new name is an ID whose text the pak adds, and
    # a new item's inventory entry needs its rows. With a table of theirs left out, the save would point at
    # text or items the game hasn't got (the cat shows as "<MISSING STRING TABLE ENTRY>"), so they stay out too.
    broken = {sid for _, ids, _ in csv_failures + table_failures for sid in ids}
    kept = [op for op in ctx.save_ops if op.get("section") not in broken]
    if len(kept) != len(ctx.save_ops):
        ctx.save_ops = kept
        for sid in broken:
            if sid in report:
                report[sid]["errors"].append("its save edits were left out too: they'd point at text or items "
                                             "the game wouldn't have")

    manifest = {"mods": [m.id for m in enabled], "sections": report, "outputs": [], "ue4ss_mods": [],
                "ue4ss_shared": [], "save_ops": ctx.save_ops, "warnings": ctx.warnings, "notes": ctx.notes,
                "csv_changes": csv_changes, "table_rows": table_changes, "files": sorted(ctx.files),
                "built": datetime.datetime.now().isoformat(timespec="seconds")}
    titles = {m.id: m.name for m in mods}
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
    if ctx.packages:
        io = game.io
        header = io.container_header()
        container = ModContainerWriter(blake3(MOD_BASENAME.lower().encode(), 8))
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
            container.add_package(path, cid, data, imports, shaders)
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
            manifest["paks"].append({"mod": m.id, "file": f"paks/{stem}", "installed_as": name})
            log(f"  {m.id}: paks/{stem} goes in as {name}")
    # The in-game mod menu is a mod of its own (mods/mod-menu, with its menu.json): its window and the
    # WCModsMenu module go in only while it's on. Mods that add pages look for the module first, so
    # without the menu they simply have none.
    menus = [m for m in enabled if os.path.isfile(os.path.join(m.folder, menusettings.MENU_FILE))]
    menu_mod = menus[0] if menus else None
    if len(menus) > 1:
        manifest["warnings"].append(f"only one mod menu can be on; using {menu_mod.id} (also on: "
                                    + ", ".join(m.id for m in menus[1:]) + ")")
    manifest["menu"] = menu_mod.id if menu_mod else None
    if menu_mod:
        opts = menusettings.menu_settings(cfg, menu_mod)
        if not opts["key_ok"]:
            manifest["warnings"].append(f"{menu_mod.id}: key {opts['key_given']!r} isn't one of {', '.join(menu.KEYS)}; "
                                        f"using {menu.DEFAULT_KEY}")
        if not opts["pad_ok"]:
            manifest["warnings"].append(f"{menu_mod.id}: controller button {opts['pad_given']!r} isn't an Unreal key "
                                        f"name; using {menu.DEFAULT_PAD}")
        # The pages show the game's own area names and quest titles, read here from its tables.
        pages = menupages.data(lambda path: game.read_text(path), cfg)
        # The menu's list of installed mods: the ones this build has (not those left out).
        host = menu.host_script(manifest, enabled, opts["key"], cheats=opts["cheats"], scale=opts["size"], pad=opts["pad"],
                                dev=bool(cfg.data.get("allow_code_mods")), pages=pages)
        manifest["warnings"] += [f"{menu.HOST_NAME}: {p}" for p in luacheck.check(host)[:3]]
        ctx.ue4ss_mods[menu.HOST_NAME] = ({"Scripts/main.lua": host.encode(), "enabled.txt": b""}, None)
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
    # Shared Lua modules go in whatever mods are on, for any UE4SS script to require (the menu's with
    # the mod menu).
    shared_files = {m.SHARED_NAME: m.lua(fit["offsets"]) if m is game_lua else m.lua()
                    for m in SHARED_LUA if m is not menu or menu_mod}
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
    shared_files[world.NAMES_NAME] = world.names_lua(plan, item_labels)
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
        json.dump(world.names_data(plan, item_labels), f, ensure_ascii=False)

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


def pending(cfg, mods):
    """How your mods differ from what's installed: {"installed" (ever), "on" and "off" (ids turned on or off
    since), "changed" (on both times, with files changed since), "redo" (why the last install has to be
    made again: it was made before UE4SS or the Oodle DLL was there, so it left parts out), "any"}. The
    studio's Apply button shows it."""
    # wcmods.json read afresh into a Config of its own: reloading the studio's would throw away what an
    # install running at the same time has noted but not saved yet.
    try:
        data = Config(cfg.root).data
    except (OSError, ValueError):   # being written this moment
        data = cfg.data
    # What an install would put in: mods made for an older version of the game stay out (unless used anyway).
    left_out = set(gamebuild.held_back(cfg, mods))
    now = {m.id for m in mods if m.enabled} - left_out
    inst = data.get("installed")
    if not inst:
        return {"installed": False, "on": sorted(now), "off": [], "changed": [], "redo": [], "any": bool(now)}
    was = set(inst.get("mods", []))
    try:
        built = datetime.datetime.fromisoformat(inst.get("built", "")).timestamp()
    except ValueError:
        built = 0.0
    changed = sorted(m.id for m in mods if m.enabled and m.id in was and _newest(m.folder) > built + 1)
    redo = []
    if now and inst.get("ue4ss") is False and cfg.ue4ss_mods_dir:
        redo.append("the script loader (UE4SS) is in now")
    # The game updated since (or its exe changed): wcmods' in-game module has to follow it. An install
    # from before the build was recorded was made on the build every one was then.
    build = gamebuild.steam_build(cfg)
    if now and build is not None and build != inst.get("game_build", gamebuild.ASSUMED_BUILDS[0]):
        redo.append(f"the game updated (build {build})")
    elif now and inst.get("layout") and gamebuild.layout_key(cfg) not in (None, inst["layout"]):
        redo.append("the game, or what wcmods knows of it, changed")
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
    problems = [f"{rep['title']}: {err}" for rep in manifest["sections"].values()
                if rep["status"] != "ok" for err in rep["errors"]]
    if problems and not force:
        raise RuntimeError("not installing because some mods didn't build: " + "; ".join(problems) +
                           ". Fix or turn off those mods, or install anyway with --force "
                           "(anything they installed before is removed).")
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
        # folder (the menu's saved travel spots) and the bridge's inside it.
        os.makedirs(os.path.dirname(menupages.data(cfg=cfg)["places"]), exist_ok=True)
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
            log(f"  NOTE: {' and '.join(skipped)} need UE4SS, which isn't installed; skipped.")

    if manifest["save_ops"]:
        apply_save_ops(cfg, manifest["save_ops"], backups_root, log)
    # What the game had then: an install made without UE4SS left parts out, so pending() asks for
    # another once it's there.
    game_info = manifest.get("game") or {}
    cfg.data["installed"] = {"mods": manifest["mods"], "built": manifest["built"], "ue4ss": bool(mods_dir),
                             "game_build": game_info.get("build"), "layout": game_info.get("layout")}
    cfg.save()
    return manifest


def apply_save_ops(cfg, ops, backups_root, log=print):
    sav = os.path.join(cfg.save_dir, SAV_NAME)
    if not os.path.isfile(sav):
        log("  NOTE: no save yet; launch the game once, then install again to apply save edits.")
        return []
    save = SaveGame.load(sav)
    doc = SaveDoc(save.json_text)
    changed = []
    # Consecutive "set" ops are applied together with one parse of the save. Keyed by path, so a
    # later (higher-priority) op replaces an earlier one, and whether anything changes is decided
    # against the save itself at flush time.
    pending = {}
    labels = {}   # path -> how a name change reads in the log ("Otterpaw -> Mothpaw")

    def flush():
        if not pending:
            return
        items = [(p, v) for p, v in pending.items() if doc.get(p) != v]
        olds = {p: doc.get(p) for p, _ in items}
        pending.clear()
        if not items:
            return
        try:
            doc.set_many(items)
            done = items
        except Exception:
            done = []
            for p, v in items:   # fall back to one at a time so one bad edit doesn't drop the rest
                try:
                    doc.set(p, v)
                    done.append((p, v))
                except Exception as e:
                    log(f"  save edit skipped ({p}): {e}")
        changed.extend(labels.get(p) or f"{p}: {json.dumps(olds[p])} -> {json.dumps(v)}" for p, v in done)

    for op in ops:
        if op["op"] == "set":
            try:
                doc.get(op["path"])   # the path must exist; nothing else touches the doc until flush
            except (KeyError, IndexError, ValueError, TypeError):
                log(f"  save edit skipped ({op.get('section')}): your save has no value at {op['path']}")
                continue
            pending[op["path"]] = op["value"]
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
                labels[op["path"]] = f"name: {op.get('from')} -> {op.get('to')} ({op.get('where', op['path'])})"
            continue
        if op["op"] == "fields":
            # Whole-number fields inside a cat's save text (your cat's colour slots).
            try:
                current = pending[op["path"]] if op["path"] in pending else doc.get(op["path"])
            except (KeyError, IndexError, ValueError, TypeError):
                log(f"  colour slots skipped: your save has no cat at {op['path']}")
                continue
            if isinstance(current, str):
                new = catcolours.set_fields(current, op["set"])
                if new != current:
                    pending[op["path"]] = new
                    labels[op["path"]] = f"your cat: {op.get('label', op['set'])}"
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
                if old != op["value"]:
                    doc.insert(op["path"], op["key"], op["value"])
                    changed.append(f"{full}: {json.dumps(old)} -> {json.dumps(op['value'])}")
        except (KeyError, IndexError, ValueError, TypeError) as e:
            log(f"  save edit skipped ({op.get('section')}): {e}")
    flush()
    if not changed:
        log("  save already matches; nothing to change")
        return []
    where, _ = backup(cfg.save_dir, backups_root, "before-save-edits")
    log(f"  backed up saves -> {where}")
    save.json_text = doc.text
    write_save(cfg.save_dir, save)
    for c in changed:
        log(f"  save: {c}")
    return changed


def install_outdated(cfg):
    """True when the installed mod pak was built by an older wcmods, whose file names the engine never
    matches (see pak._read_file_name): the pak loads but none of its files are used. Installing fixes it."""
    path = os.path.join(cfg.mods_install_dir, MOD_BASENAME + ".pak") if cfg.game_dir else None
    if not path or not os.path.isfile(path):
        return False
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
