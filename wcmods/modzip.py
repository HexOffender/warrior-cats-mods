"""Mods as files to share: add a downloaded mod (a .zip or a folder), remove one, and pack one up.

A downloaded mod is a .zip with the mod's folder in it (its mod.json and the rest), or with mod.json
and the rest at the top; one .zip can hold several mods, and the mod folders can be deeper (a whole
download of wcmods' repository works). Adding a mod copies files into mods/ and nothing in it runs;
mods that run code still need "allow_code_mods" (mods.Mod.has_code).

A .zip is checked before anything is written: no file may land outside its mod's folder (absolute
paths, "..", drive letters), links are skipped, and it may hold at most MAX_FILES files and unpack to
at most MAX_BYTES. A mod that's already there is replaced, and the old copy kept in backups/mods/.
Removing a mod moves it there too, so both can be undone (restore()).
"""
import datetime
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile

from .mods import CONTENT, VALID_ID, Mod

MAX_FILES = 20000
MAX_BYTES = 4 * 1024 ** 3        # cooked content can be big, but not this big
MAX_META = 1024 * 1024           # a mod.json bigger than this isn't one
IGNORED = ("__MACOSX", ".git", "__pycache__", ".DS_Store", "Thumbs.db")
CODE = ("section.py", "scripts", "studio/section.js")


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def safe_id(text):
    """A mod folder name from a folder or file name: "My Mod v1.2" -> "my-mod-v1.2"."""
    s = re.sub(r"[^a-z0-9._-]+", "-", str(text).lower()).strip("-._")
    s = re.sub(r"-{2,}", "-", s)[:64].strip("-._")
    return s if VALID_ID.match(s or "") else "mod"


def _parts(name):
    """A member's path as parts, refusing any that would leave the folder it's unpacked into."""
    name = name.replace("\\", "/")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ValueError(f"{name}: an absolute path; this .zip isn't safe to add")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise ValueError(f"{name}: a path that climbs out of the mod's folder; this .zip isn't safe to add")
    return parts


def _is_link(info):
    return stat.S_ISLNK(info.external_attr >> 16)


def _members(z):
    """[(parts, info)] for the files in a .zip that a mod could use."""
    out = []
    for info in z.infolist():
        parts = _parts(info.filename)
        if info.is_dir() or not parts or _is_link(info) or any(p in IGNORED for p in parts):
            continue
        out.append((parts, info))
    if len(out) > MAX_FILES:
        raise ValueError(f"this .zip holds {len(out)} files; a mod has at most {MAX_FILES}")
    return out


def _kinds(names):
    """What a mod holds, from its file names (relative, with /), as mods.Mod.kinds() says it."""
    kinds = []
    for path, kind in CONTENT:
        path = path.replace(os.sep, "/")
        if any(n == path or n.startswith(path + "/") for n in names):
            kinds.append(kind)
    return kinds


def _found(mods_root, mod_id, meta, names, size, root):
    kinds = _kinds(names)
    existing = None
    folder = os.path.join(mods_root, mod_id)
    if os.path.isfile(os.path.join(folder, "mod.json")):
        try:
            old = Mod(folder)
            existing = {"name": old.name, "version": old.version, "builtin": old.builtin}
        except (OSError, ValueError):
            existing = {"name": mod_id, "version": "", "builtin": False}
    req = meta.get("requires")
    uses = meta.get("uses")
    ids = lambda v: [x for x in ([v] if isinstance(v, str) else v if isinstance(v, list) else []) if isinstance(x, str)]
    return {"id": mod_id, "name": str(meta.get("name") or mod_id), "description": str(meta.get("description") or ""),
            "version": str(meta.get("version") or ""), "author": str(meta.get("author") or ""),
            "requires": ids(req), "uses": ids(uses), "kinds": kinds,
            "code": any(n == c or n.startswith(c + "/") for n in names for c in CODE),
            "files": len(names), "bytes": size, "existing": existing, "root": root}


def inspect(path, mods_root, name=None):
    """The mods in a .zip, without adding anything: [{id, name, description, version, author, requires,
    uses, kinds, code, files, bytes, existing (the copy you have, or None), root}]. `name` is the
    download's file name, which names a mod whose mod.json is at the top."""
    with zipfile.ZipFile(path) as z:
        return _inspect(z, mods_root, name or os.path.basename(path))


def _inspect(z, mods_root, name):
    members = _members(z)
    roots = sorted({tuple(p[:-1]) for p, _ in members if p[-1] == "mod.json"}, key=len)
    # A mod folder inside another mod's (a template, say) belongs to that mod; folders starting with
    # "_" are templates, as in mods/.
    keep = []
    for r in roots:
        if any(r[:len(k)] == k for k in keep) or any(p.startswith("_") for p in r):
            continue
        keep.append(r)
    if not keep:
        raise ValueError("this .zip has no mod in it (a mod is a folder with a mod.json)")
    out, ids = [], set()
    for r in keep:
        files = [(p[len(r):], info) for p, info in members if tuple(p[:len(r)]) == r]
        meta_info = next(info for p, info in files if p == ["mod.json"])
        if meta_info.file_size > MAX_META:
            raise ValueError(f"{'/'.join(r) or name}: mod.json is too big to be one")
        try:
            meta = json.loads(z.read(meta_info).decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"{'/'.join(r) or name}: mod.json isn't valid JSON ({e})") from None
        if not isinstance(meta, dict):
            raise ValueError(f"{'/'.join(r) or name}: mod.json should hold an object")
        base = r[-1] if r else os.path.splitext(name)[0]
        mod_id = safe_id(meta.get("id") or base)
        while mod_id in ids:
            mod_id = safe_id(mod_id + "-2")
        ids.add(mod_id)
        out.append(_found(mods_root, mod_id, meta, ["/".join(p) for p, _ in files],
                          sum(i.file_size for _, i in files), "/".join(r)))
    return out


def _backup(folder, backups_root, why):
    dest_root = os.path.join(backups_root, "mods")
    os.makedirs(dest_root, exist_ok=True)
    base = dest = os.path.join(dest_root, f"{_stamp()}-{why}-{os.path.basename(folder)}")
    n = 2
    while os.path.exists(dest):
        dest = f"{base}-{n}"
        n += 1
    shutil.move(folder, dest)
    return dest


def _set_enabled(folder, on):
    path = os.path.join(folder, "mod.json")
    with open(path, encoding="utf-8-sig") as f:
        meta = json.load(f)
    meta["enabled"] = bool(on)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")


def _place(tmp, mods_root, mod_id, backups_root, enable):
    """Move a mod unpacked in tmp to mods/<id>, keeping any copy that's there in backups/mods/."""
    _set_enabled(tmp, enable)
    final = os.path.join(mods_root, mod_id)
    replaced = None
    if os.path.exists(final):
        replaced = os.path.basename(_backup(final, backups_root, "replaced"))
    os.rename(tmp, final)
    return replaced


def add_zip(path, mods_root, backups_root, ids=None, enable=True, name=None):
    """Add the mods in a .zip (all of them, or those in `ids`), on unless enable=False.
    Returns [{id, name, replaced (the old copy's backup folder, or None)}]."""
    with zipfile.ZipFile(path) as z:
        found = _inspect(z, mods_root, name or os.path.basename(path))
        chosen = [f for f in found if ids is None or f["id"] in ids]
        if not chosen:
            raise ValueError("none of the mods asked for is in this .zip")
        if any(f["existing"] and f["existing"]["builtin"] for f in chosen):
            raise ValueError("this .zip would replace a mod that comes with wcmods (" +
                             ", ".join(f["id"] for f in chosen if f["existing"] and f["existing"]["builtin"]) +
                             "); update wcmods instead")
        if sum(f["bytes"] for f in chosen) > MAX_BYTES:
            raise ValueError(f"this .zip unpacks to more than {MAX_BYTES // 1024 ** 3} GB")
        members = _members(z)
        os.makedirs(mods_root, exist_ok=True)
        done = []
        for f in chosen:
            root = tuple(p for p in f["root"].split("/") if p)
            # Unpacked beside mods/ first ("_" keeps it out of the mod list), then moved in whole.
            tmp = tempfile.mkdtemp(prefix=f"_adding-{f['id']}-", dir=mods_root)
            try:
                budget = f["bytes"]
                for parts, info in members:
                    if tuple(parts[:len(root)]) != root:
                        continue
                    rel = parts[len(root):]
                    dest = os.path.join(tmp, *rel)
                    if not os.path.realpath(dest).startswith(os.path.realpath(tmp) + os.sep):
                        raise ValueError(f"{info.filename}: lands outside the mod's folder")
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with z.open(info) as src, open(dest, "wb") as out:
                        while True:
                            chunk = src.read(1024 * 1024)
                            if not chunk:
                                break
                            budget -= len(chunk)
                            if budget < 0:   # it unpacks to more than it says
                                raise ValueError(f"{info.filename} is bigger than the .zip says; not adding it")
                            out.write(chunk)
                replaced = _place(tmp, mods_root, f["id"], backups_root, enable)
            except BaseException:
                shutil.rmtree(tmp, ignore_errors=True)
                raise
            done.append({"id": f["id"], "name": f["name"], "replaced": replaced})
    return done


def add_folder(path, mods_root, backups_root, enable=True):
    """Add a mod from a folder (one with a mod.json, or holding mod folders). Returns as add_zip."""
    path = os.path.abspath(path)
    if os.path.isfile(os.path.join(path, "mod.json")):
        folders = [path]
    else:
        folders = sorted(os.path.join(path, d) for d in os.listdir(path)
                         if not d.startswith("_") and os.path.isfile(os.path.join(path, d, "mod.json")))
    if not folders:
        raise ValueError(f"{path} has no mod in it (a mod is a folder with a mod.json)")
    try:
        inside = os.path.commonpath([path, os.path.abspath(mods_root)]) == os.path.abspath(mods_root)
    except ValueError:   # on another drive
        inside = False
    if inside:
        raise ValueError("that's already in your mods folder")
    done = []
    for folder in folders:
        mod_id = safe_id(os.path.basename(folder))
        tmp = tempfile.mkdtemp(prefix=f"_adding-{mod_id}-", dir=mods_root)
        try:
            os.rmdir(tmp)
            shutil.copytree(folder, tmp, symlinks=False, ignore=shutil.ignore_patterns(*IGNORED, "*.pyc"))
            replaced = _place(tmp, mods_root, mod_id, backups_root, enable)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        done.append({"id": mod_id, "name": Mod(os.path.join(mods_root, mod_id)).name, "replaced": replaced})
    return done


def remove(mod, backups_root):
    """Take a mod out of mods/: it's moved to backups/mods/ (restore() puts it back). Returns that folder's name."""
    if mod.builtin:
        raise ValueError(f"{mod.name} comes with wcmods; turn it off instead")
    return os.path.basename(_backup(mod.folder, backups_root, "removed"))


def removed(backups_root):
    """Mods taken out or replaced, newest first: [{name (the backup folder), id, why, when, title}]."""
    folder = os.path.join(backups_root, "mods")
    out = []
    if os.path.isdir(folder):
        for d in sorted(os.listdir(folder), reverse=True):
            m = re.match(r"^(\d{8}-\d{6})-(removed|replaced)-(.+?)(-\d+)?$", d)
            if not m or not os.path.isfile(os.path.join(folder, d, "mod.json")):
                continue
            try:
                title = Mod(os.path.join(folder, d)).name
            except (OSError, ValueError):
                title = m.group(3)
            when = datetime.datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").isoformat(timespec="minutes")
            out.append({"name": d, "id": m.group(3), "why": m.group(2), "when": when, "title": title})
    return out


def restore(backups_root, name, mods_root):
    """Put a mod from backups/mods/ back into mods/ (off: turn it on when you want it). Returns its id."""
    entry = next((r for r in removed(backups_root) if r["name"] == name), None)
    if not entry:
        raise LookupError(f"no removed mod {name}")
    dest = os.path.join(mods_root, entry["id"])
    if os.path.exists(dest):
        raise ValueError(f"there's a mod called {entry['id']} already; remove it first to put this copy back")
    shutil.move(os.path.join(backups_root, "mods", name), dest)
    _set_enabled(dest, False)
    return entry["id"]


def pack(mod):
    """The mod as a .zip (its folder inside, named as it is), to share. Returns the bytes."""
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, dirs, files in os.walk(mod.folder):
            dirs[:] = sorted(d for d in dirs if d not in IGNORED)
            for f in sorted(files):
                if f in IGNORED or f.endswith(".pyc"):
                    continue
                full = os.path.join(folder, f)
                z.write(full, os.path.join(mod.id, os.path.relpath(full, mod.folder)).replace(os.sep, "/"))
    return buf.getvalue()
