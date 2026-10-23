"""Build, install and uninstall: runs every section independently, then writes the outputs."""
import datetime
import json
import os
import shutil
import struct

from . import controls, ue4ss
from .blake3 import blake3
from .config import MOD_BASENAME, UE4SS_MOD_NAME, game_running
from .gamefiles import GameFiles
from .iostore import ModContainerWriter
from .pak import PakWriter
from .save import SAV_NAME, SaveGame, backup, write_save
from .savejson import SaveDoc
from .sdk import BuildContext
from .sections import load_sections

MARKER = "Wrc/WCMods/BuildInfo.json"


def build(cfg, mods, out_dir, log=print):
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    enabled = [m for m in mods if m.enabled]
    game = GameFiles(cfg)
    sections, skipped = load_sections(cfg, mods, log)
    ctx = BuildContext(cfg, game, out_dir, log)
    report = {}

    for sec in sections:
        ctx.begin(sec.id)
        items, used, errors = [], [], []
        for mod in enabled:
            if not sec.claims(mod):
                continue
            try:
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

    manifest = {"mods": [m.id for m in enabled], "sections": report, "outputs": [], "ue4ss_mods": [],
                "save_ops": ctx.save_ops, "warnings": ctx.warnings, "notes": ctx.notes,
                "csv_changes": csv_changes, "files": sorted(ctx.files),
                "built": datetime.datetime.now().isoformat(timespec="seconds")}

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
            ci = io.chunk_index(path)
            cid = io.chunk_ids[ci]
            imports, shaders = header.entry_for(struct.unpack("<Q", cid[:8])[0])
            container.add_package(path, cid, data, imports, shaders)
        container.write(os.path.join(out_dir, MOD_BASENAME + ".utoc"), os.path.join(out_dir, MOD_BASENAME + ".ucas"))
        manifest["outputs"] += [MOD_BASENAME + ".utoc", MOD_BASENAME + ".ucas"]
    for name, (files, _) in ctx.ue4ss_mods.items():
        for rel, data in files.items():
            dst = os.path.join(out_dir, "ue4ss", name, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
        manifest["ue4ss_mods"].append(name)

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def install(cfg, build_dir, backups_root, log=print, force=False):
    with open(os.path.join(build_dir, "manifest.json"), encoding="utf-8-sig") as f:
        manifest = json.load(f)
    if game_running():
        raise RuntimeError("the game is running; close it before installing mods")
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
    for ext in (".pak", ".utoc", ".ucas"):
        stale = os.path.join(dest, MOD_BASENAME + ext)
        if os.path.exists(stale):
            os.remove(stale)
    for name in manifest["outputs"]:
        shutil.copy2(os.path.join(build_dir, name), os.path.join(dest, name))
        log(f"  installed {name}")

    mods_dir = cfg.ue4ss_mods_dir
    previous = set(cfg.data.get("installed_ue4ss", [])) | {UE4SS_MOD_NAME}
    if mods_dir:
        for name in manifest["ue4ss_mods"]:
            ue4ss.install_mod(mods_dir, name, os.path.join(build_dir, "ue4ss", name))
            log(f"  installed UE4SS mod {name}")
        for name in previous - set(manifest["ue4ss_mods"]):
            ue4ss.remove_mod(mods_dir, name)
        cfg.data["installed_ue4ss"] = manifest["ue4ss_mods"]
    elif any(manifest["notes"].get("palettes", {}).get("runtime_palette", {}).values()):
        log("  NOTE: coat/pattern/marking/eye-button colours need UE4SS, which isn't installed; skipped those.")

    if manifest["save_ops"]:
        apply_save_ops(cfg, manifest["save_ops"], backups_root, log)
    cfg.data["installed"] = {"mods": manifest["mods"], "built": manifest["built"]}
    cfg.save()
    return manifest


def apply_save_ops(cfg, ops, backups_root, log=print):
    sav = os.path.join(cfg.save_dir, SAV_NAME)
    if not os.path.isfile(sav):
        log("  NOTE: no save yet; launch the game once, then install again to apply save edits and controls.")
        return []
    save = SaveGame.load(sav)
    doc = SaveDoc(save.json_text)
    changed = []
    pending = []   # consecutive "set" ops, applied together with one parse of the save

    def flush():
        if not pending:
            return
        try:
            doc.set_many([(p, v) for p, v, _ in pending])
            changed.extend(desc for _, _, desc in pending)
        except (KeyError, ValueError):
            for p, v, desc in pending:   # fall back to one at a time so one bad edit doesn't drop the rest
                try:
                    doc.set(p, v)
                    changed.append(desc)
                except (KeyError, ValueError) as e:
                    log(f"  save edit skipped: {e}")
        pending.clear()

    for op in ops:
        try:
            if op["op"] == "set":
                old = doc.get(op["path"])
                if old != op["value"]:
                    pending.append((op["path"], op["value"],
                                    f"{op['path']}: {json.dumps(old)} -> {json.dumps(op['value'])}"))
                continue
            flush()
            if op["op"] == "controls":
                text, applied, warnings = controls.apply(doc.text, op["changes"])
                for w in warnings:
                    log(f"  controls warning: {w}")
                doc = SaveDoc(text)
                changed += [f"{d}: {a}: {o} -> {n}" for d, a, o, n in applied if o != n]
            elif op["op"] == "insert":
                full = f"{op['path']}/{op['key']}"
                old = doc.get(full) if doc.exists(full) else None
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


def uninstall(cfg, log=print):
    if game_running():
        raise RuntimeError("the game is running; close it before uninstalling mods")
    removed = []
    for ext in (".pak", ".utoc", ".ucas"):
        p = os.path.join(cfg.mods_install_dir, MOD_BASENAME + ext)
        if os.path.exists(p):
            os.remove(p)
            removed.append(p)
    mods_dir = cfg.ue4ss_mods_dir
    if mods_dir:
        for name in set(cfg.data.get("installed_ue4ss", [])) | {UE4SS_MOD_NAME}:
            if os.path.isdir(os.path.join(mods_dir, name)):
                ue4ss.remove_mod(mods_dir, name)
                removed.append(os.path.join(mods_dir, name))
        cfg.data["installed_ue4ss"] = []
    cfg.data.pop("installed", None)
    cfg.save()
    for p in removed:
        log(f"  removed {p}")
    return removed
