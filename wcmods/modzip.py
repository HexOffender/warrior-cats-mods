"""Mods as files to share: add a downloaded mod (a .zip or a folder), remove one, and pack one up.

A downloaded mod is a .zip with the mod's folder in it (its mod.json and the rest), or with mod.json
and the rest at the top; one .zip can hold several mods, and the mod folders can be deeper (a whole
download of the wcmods-examples repository works; a mod that comes with wcmods, the mod menu, is
skipped rather than replaced). Adding a mod copies files into mods/ and nothing in it runs; mods that run code
still need "allow_code_mods" (mods.Mod.has_code). A mod added switched on turns on the mods it
requires too, as switching it on does.

A .zip is checked before anything is written: no file may land outside its mod's folder (absolute
paths, "..", drive letters), no two files may be one file on Windows (names that differ only in case,
or in dots and spaces at the end), links are skipped, its mod.json must hold values mods.Mod can use,
and it may hold at most MAX_FILES files and unpack to at most MAX_BYTES. Names are compared the way
Windows sees them, so what the preview says a mod holds (code included) is what lands in mods/. A mod
that's already there is replaced, and the old copy kept in backups/mods/. Removing a mod moves it
there too, so both can be undone (restore()).
"""
import datetime
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile

from . import mods as modlib
from .mods import CONTENT, VALID_ID, Mod

MAX_FILES = 20000
MAX_BYTES = 4 * 1024 ** 3        # cooked content can be big, but not this big
MAX_META = 1024 * 1024           # a mod.json bigger than this isn't one
IGNORED = ("__MACOSX", ".git", "__pycache__", ".DS_Store", "Thumbs.db")
CODE = ("section.py", "scripts", "dlls", "cpp", "studio/section.js")
BUILTIN_SKIP = "comes with wcmods, so it's left as it is; update wcmods instead"
# A backup's folder in backups/mods: <time>[-n]-<why>-<id>. The number (for a second backup in the same
# second) goes after the time, so the id is everything after "<why>-", even one ending in "-2".
BACKUP_NAME = re.compile(r"^(\d{8}-\d{6})(?:-\d+)?-(removed|replaced)-(.+)$")


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def safe_id(text):
    """A mod folder name from a folder or file name: "My Mod v1.2" -> "my-mod-v1.2"."""
    s = re.sub(r"[^a-z0-9._-]+", "-", str(text).lower()).strip("-._")
    s = re.sub(r"-{2,}", "-", s)[:64].strip("-._")
    return s if VALID_ID.match(s or "") else "mod"


def zip_name(mod):
    """The file name for a mod packed as a .zip, from its id and version, with anything that isn't a
    letter, digit, '.', '-' or '_' made a dash (it goes in a file name and a download's header)."""
    stem = f"{mod.id}-{mod.version}" if mod.version else mod.id
    return (re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.") or "mod") + ".zip"


def _parts(name):
    """A member's path as parts, refusing any that would leave the folder it's unpacked into."""
    name = name.replace("\\", "/")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ValueError(f"{name}: an absolute path; this .zip isn't safe to add")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise ValueError(f"{name}: a path that climbs out of the mod's folder; this .zip isn't safe to add")
    return parts


def _key(part):
    """A name as Windows sees it: case doesn't count, and dots and spaces at the end are dropped."""
    return part.rstrip(" .").casefold()


def _fold(parts):
    return tuple(_key(p) for p in parts)


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


def _no_clashes(files, label):
    """Refuse two members that would be one file on Windows ("Section.py" and "section.py", or a second
    "MOD.JSON"), or a file where another member needs a folder: the later one would replace the first,
    so the mod would hold something other than what was checked."""
    seen, folders = {}, set()
    for parts, info in files:
        key = _fold(parts)
        if key in seen:
            raise ValueError(f"{label}: {seen[key]} and {info.filename} would be the same file on Windows; "
                             "this .zip isn't safe to add")
        seen[key] = info.filename
        folders.update(key[:i] for i in range(1, len(key)))
    clash = next((seen[k] for k in seen if k in folders), None)
    if clash:
        raise ValueError(f"{label}: {clash} is both a file and a folder; this .zip isn't safe to add")


def _check_meta(meta, label):
    """Refuse a mod.json with values mods.Mod can't use, saying which one to fix."""
    def bad(key, what):
        raise ValueError(f"{label}: mod.json's \"{key}\" should be {what}")
    for key in ("id", "name", "description", "author"):
        if key in meta and not isinstance(meta[key], str):
            bad(key, "text")
    version = meta.get("version", "")
    if isinstance(version, bool) or not isinstance(version, (str, int, float)):
        bad("version", "text, like \"1.2\"")
    priority = meta.get("priority", 0)
    if isinstance(priority, bool) or not isinstance(priority, int):
        bad("priority", "a whole number")
    if not isinstance(meta.get("enabled", True), bool):
        bad("enabled", "true or false")
    for key in ("requires", "uses"):
        v = meta.get(key, [])
        if not (isinstance(v, str) or (isinstance(v, list) and all(isinstance(x, str) for x in v))):
            bad(key, "a list of mod folder names")


def _kinds(names):
    """What a mod holds, from its file names (relative, with /, as _fold gives them), as mods.Mod.kinds()
    says it."""
    kinds = []
    for path, kind in CONTENT:
        path = path.replace(os.sep, "/")
        if any(n == path or n.startswith(path + "/") for n in names):
            kinds.append(kind)
    return kinds


def _builtin(folder):
    """Whether the mod in this folder is one that comes with wcmods."""
    try:
        return Mod(folder).builtin
    except (OSError, ValueError):
        return False


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
    # Folders and files are matched as Windows sees their names (_fold), so "MOD.JSON" or "Section.py"
    # counts for what it is on disk.
    roots = sorted({_fold(p[:-1]) for p, _ in members if _key(p[-1]) == "mod.json"}, key=lambda r: (len(r), r))
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
        label = "/".join(r) or name
        files = [(p[len(r):], info) for p, info in members if _fold(p[:len(r)]) == r]
        _no_clashes(files, label)
        meta_info = next(info for p, info in files if _fold(p) == ("mod.json",))
        if meta_info.file_size > MAX_META:
            raise ValueError(f"{label}: mod.json is too big to be one")
        try:
            meta = json.loads(z.read(meta_info).decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"{label}: mod.json isn't valid JSON ({e})") from None
        if not isinstance(meta, dict):
            raise ValueError(f"{label}: mod.json should hold an object")
        _check_meta(meta, label)
        base = r[-1] if r else os.path.splitext(name)[0]
        mod_id = safe_id(meta.get("id") or base)
        while mod_id in ids:
            mod_id = safe_id(mod_id + "-2")
        ids.add(mod_id)
        out.append(_found(mods_root, mod_id, meta, ["/".join(_fold(p)) for p, _ in files],
                          sum(i.file_size for _, i in files), "/".join(r)))
    return out


def _backup(folder, backups_root, why):
    dest_root = os.path.join(backups_root, "mods")
    os.makedirs(dest_root, exist_ok=True)
    stamp, mod_id = _stamp(), os.path.basename(folder)
    dest, n = os.path.join(dest_root, f"{stamp}-{why}-{mod_id}"), 2
    while os.path.exists(dest):   # see BACKUP_NAME
        dest = os.path.join(dest_root, f"{stamp}-{n}-{why}-{mod_id}")
        n += 1
    shutil.move(folder, dest)
    return dest


def _set_enabled(folder, on, downloaded=False):
    path = os.path.join(folder, "mod.json")
    with open(path, encoding="utf-8-sig") as f:
        meta = json.load(f)
    meta["enabled"] = bool(on)
    if downloaded:
        # Only the mods in wcmods' own folder are built in; a download saying it is one couldn't be
        # removed or updated afterwards.
        meta.pop("builtin", None)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")


def _place(tmp, mods_root, mod_id, backups_root, enable):
    """Move a mod unpacked in tmp to mods/<id>, keeping any copy that's there in backups/mods/."""
    _set_enabled(tmp, enable, downloaded=True)
    final = os.path.join(mods_root, mod_id)
    replaced = None
    if os.path.exists(final):
        replaced = os.path.basename(_backup(final, backups_root, "replaced"))
    os.rename(tmp, final)
    return replaced


def _needs_on(mods_root, done):
    """Turn on what the mods just added (switched on) require, as switching them on does. Each entry's
    "also_on" gets the names of the mods that went on with it."""
    for d in done:
        if d.get("skipped"):
            continue
        found = modlib.discover(mods_root)
        names = {m.id: m.name for m in found}
        try:
            changed, _ = modlib.switch(found, d["id"], True)
        except ValueError:   # it needs a mod that isn't in mods/; the mod list says so
            changed = []
        d["also_on"] = [names.get(i, i) for i, _ in changed if i != d["id"]]


def add_zip(path, mods_root, backups_root, ids=None, enable=True, name=None):
    """Add the mods in a .zip (all of them, or those in `ids`), on unless enable=False. Mods that come with
    wcmods (the mod menu) aren't replaced: they're skipped, unless that leaves nothing to add.
    Returns [{id, name, code, replaced (the old copy's backup folder, or None), also_on (mods turned on
    because it needs them)}], then [{id, name, skipped (why)}] for the ones left out."""
    with zipfile.ZipFile(path) as z:
        found = _inspect(z, mods_root, name or os.path.basename(path))
        chosen = [f for f in found if ids is None or f["id"] in ids]
        if not chosen:
            raise ValueError("none of the mods asked for is in this .zip")
        skipped = [f for f in chosen if f["existing"] and f["existing"]["builtin"]]
        chosen = [f for f in chosen if f not in skipped]
        if not chosen:
            raise ValueError("this .zip would replace a mod that comes with wcmods (" +
                             ", ".join(f["id"] for f in skipped) + "); update wcmods instead")
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
                    if _fold(parts[:len(root)]) != root:
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
            done.append({"id": f["id"], "name": f["name"], "code": f["code"], "replaced": replaced, "also_on": []})
    if enable:
        _needs_on(mods_root, done)
    return done + [{"id": f["id"], "name": f["name"], "skipped": BUILTIN_SKIP} for f in skipped]


def _mod_folders(path):
    path = os.path.abspath(path)
    if os.path.isfile(os.path.join(path, "mod.json")):
        return [path]
    return sorted(os.path.join(path, d) for d in os.listdir(path)
                  if not d.startswith("_") and os.path.isfile(os.path.join(path, d, "mod.json")))


def inspect_folder(path, mods_root):
    """As inspect(), for a folder that is a mod or holds mod folders."""
    out = []
    for folder in _mod_folders(path):
        try:
            with open(os.path.join(folder, "mod.json"), encoding="utf-8-sig") as f:
                meta = json.load(f)
        except ValueError as e:
            raise ValueError(f"{os.path.basename(folder)}: mod.json isn't valid JSON ({e})") from None
        names, size = [], 0
        for d, dirs, files in os.walk(folder):
            dirs[:] = [x for x in dirs if x not in IGNORED]
            for fn in files:
                full = os.path.join(d, fn)
                names.append(os.path.relpath(full, folder).replace(os.sep, "/"))
                size += os.path.getsize(full)
        out.append(_found(mods_root, safe_id(os.path.basename(folder)), meta if isinstance(meta, dict) else {},
                          names, size, ""))
    if not out:
        raise ValueError(f"{path} has no mod in it (a mod is a folder with a mod.json)")
    return out


def add_folder(path, mods_root, backups_root, ids=None, enable=True):
    """Add the mods in a folder (one with a mod.json, or holding mod folders): all of them, or those in
    `ids`. Returns as add_zip."""
    path = os.path.abspath(path)
    folders = _mod_folders(path)
    if not folders:
        raise ValueError(f"{path} has no mod in it (a mod is a folder with a mod.json)")
    try:
        inside = os.path.commonpath([path, os.path.abspath(mods_root)]) == os.path.abspath(mods_root)
    except ValueError:   # on another drive
        inside = False
    if inside:
        raise ValueError("that's already in your mods folder")
    # Every mod.json is checked, and each mod named as add_zip names it (its "id", else its folder),
    # before anything is copied.
    plan, taken, skipped = [], set(), []
    for folder in folders:
        try:
            with open(os.path.join(folder, "mod.json"), encoding="utf-8-sig") as f:
                meta = json.load(f)
        except ValueError as e:
            raise ValueError(f"{folder}: mod.json isn't valid JSON ({e})") from None
        if not isinstance(meta, dict):
            raise ValueError(f"{folder}: mod.json should hold an object")
        _check_meta(meta, folder)
        mod_id = safe_id(meta.get("id") or os.path.basename(folder))
        while mod_id in taken:
            mod_id = safe_id(mod_id + "-2")
        taken.add(mod_id)
        if ids is not None and mod_id not in ids:
            continue
        if _builtin(os.path.join(mods_root, mod_id)):
            skipped.append({"id": mod_id, "name": str(meta.get("name") or mod_id), "skipped": BUILTIN_SKIP})
        else:
            plan.append((folder, mod_id))
    if not plan and not skipped:
        raise ValueError("none of the mods picked are in it")
    if not plan:
        raise ValueError("that would replace a mod that comes with wcmods (" + ", ".join(s["id"] for s in skipped) +
                         "); update wcmods instead")
    done = []
    for folder, mod_id in plan:
        tmp = tempfile.mkdtemp(prefix=f"_adding-{mod_id}-", dir=mods_root)
        try:
            os.rmdir(tmp)
            shutil.copytree(folder, tmp, symlinks=False, ignore=shutil.ignore_patterns(*IGNORED, "*.pyc"))
            replaced = _place(tmp, mods_root, mod_id, backups_root, enable)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        m = Mod(os.path.join(mods_root, mod_id))
        done.append({"id": mod_id, "name": m.name, "code": m.has_code(), "replaced": replaced, "also_on": []})
    if enable:
        _needs_on(mods_root, done)
    return done + skipped


class Needed(ValueError):
    """Removing a mod that mods which are on need: `by` holds their ids."""

    def __init__(self, mod, by):
        super().__init__(f"{', '.join(by)} need{'s' if len(by) == 1 else ''} {mod.id}; turn "
                         f"{'it' if len(by) == 1 else 'them'} off first")
        self.by = by


def remove(mod, backups_root, found=(), cascade=False):
    """Take a mod out of mods/: it's moved to backups/mods/ (restore() puts it back). Returns that folder's
    name. `found` is every mod: while mods that are on need this one, removing it is refused (Needed),
    unless cascade, which turns them off first, as turning it off does."""
    if mod.builtin:
        raise ValueError(f"{mod.name} comes with wcmods; turn it off instead")
    found = list(found)
    need = modlib.needing(found, mod.id) if found else []
    if need:
        if not cascade:
            raise Needed(mod, need)
        modlib.switch(found, mod.id, False, cascade=True)
    return os.path.basename(_backup(mod.folder, backups_root, "removed"))


def removed(backups_root):
    """Mods taken out or replaced, newest first: [{name (the backup folder), id, why, when, title}]."""
    folder = os.path.join(backups_root, "mods")
    out = []
    if os.path.isdir(folder):
        for d in sorted(os.listdir(folder), reverse=True):
            m = BACKUP_NAME.match(d)
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
