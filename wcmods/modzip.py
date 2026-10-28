"""Mods as files to share: add a downloaded mod (a .zip or a folder), remove one, and pack one up.

A downloaded mod is a .zip with the mod's folder in it (its mod.json and the rest), or with mod.json
and the rest at the top; one .zip can hold several mods, and the mod folders can be deeper (a whole
download of the wcmods-examples repository works). Adding a mod copies files into mods/ and nothing in it
runs; mods that run code still need "allow_code_mods" (mods.Mod.has_code). A mod added switched on turns
on the mods it requires too, as switching it on does; one whose requirement isn't in mods/ goes in
switched off instead, with "off_because" saying what it needs. Each mod goes in on or off as its mod.json
ships it, unless the one adding it says otherwise (`enable`: one answer for all, or one per mod).

A mod is named (its folder in mods/) the same way from a .zip and from a folder (_identify): mod.json's
"id", else its folder's name, else, for a mod.json at the top of a .zip, the download's file name with a
version at its end dropped ("Cool Mod v1.3.zip" is cool-mod; "Moonlit Cats 2.zip" keeps its 2), so an
update zipped the same way replaces the mod rather than going in beside it. A mod an older wcmods named
with the version in it (cool-mod-v1.2) is found by its name and replaced; a mod that only shares the name
is left alone.

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
import unicodedata
import zipfile
import zlib

from . import mods as modlib
from .mods import CONTENT, VALID_ID, Mod

MAX_FILES = 20000
MAX_BYTES = 4 * 1024 ** 3        # cooked content can be big, but not this big
MAX_META = 1024 * 1024           # a mod.json bigger than this isn't one
IGNORED = ("__MACOSX", ".git", "__pycache__", ".DS_Store", "Thumbs.db")
CODE = ("section.py", "scripts", "dlls", "cpp", "studio/section.js")
# A backup's folder in backups/mods: <time>[-n]-<why>-<id>. The number (for a second backup in the same
# second) goes after the time, so the id is everything after "<why>-", even one ending in "-2".
BACKUP_NAME = re.compile(r"^(\d{8}-\d{6})(?:-\d+)?-(removed|replaced)-(.+)$")


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def safe_id(text):
    """A mod folder name from a folder or file name: "My Mod v1.2" -> "my-mod-v1.2". Accented letters keep
    their letter ("Étoile" -> "etoile")."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-._")
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
    if "wcmods" in meta and not modlib.is_version(meta["wcmods"]):
        bad("wcmods", 'a version like "0.4.0"')


def _without_version(base):
    """A download's file name without the version at its end: "Cool Mod v1.3" or "cool-mod-1.3" -> "Cool Mod"
    or "cool-mod". A version is a "v" and a number, or numbers with dots, after a space, "-" or "_": a plain
    number is part of the name ("Moonlit Cats 2"), and one that's nothing but a version ("2048") is kept."""
    stripped = re.sub(r"[\s_-]+(?:[vV]\d+(?:\.\d+)*|\d+(?:\.\d+)+)$", "", base)
    return stripped if stripped.strip(" -_.") else base


def _same_name(mods_root, name, mod_id):
    """The id of the one mod in mods/ called `name` (its mod.json's "name") that an older wcmods named after
    the same download, version and all (cool-mod-v1.2 for cool-mod), or None. Another mod that only has the
    same name (your own "My mods", say) is never it."""
    found = [m.id for m in modlib.discover(mods_root) if not m.problem and m.name == name]
    if len(found) == 1 and found[0] != mod_id and safe_id(_without_version(found[0])) == mod_id:
        return found[0]
    return None


def _identify(meta, base, label, taken, mods_root=None, top=False):
    """The id a mod goes in under: mod.json's "id", else `base` (its folder's name; for a mod.json at the
    top of a .zip, the download's name without its version), with "-2" added while another mod in the same
    .zip or folder has it. A mod.json at the top with no "id", whose id isn't in mods/ yet, takes the id of
    the mod there with its name whose id is this one with a version after it (_same_name): an older wcmods
    named it after its file name, version and all, so the update replaces it. mod.json is checked first
    (_check_meta)."""
    _check_meta(meta, label)
    if meta.get("id"):
        mod_id = safe_id(meta["id"])
    else:
        mod_id = safe_id(_without_version(base) if top else base)
        if top and mods_root and isinstance(meta.get("name"), str) \
                and not os.path.isfile(os.path.join(mods_root, mod_id, "mod.json")):
            mod_id = _same_name(mods_root, meta["name"], mod_id) or mod_id
    while mod_id in taken:
        mod_id = safe_id(mod_id + "-2")
    taken.add(mod_id)
    return mod_id


def _kinds(names):
    """What a mod holds, from its file names (relative, with /, as _fold gives them), as mods.Mod.kinds()
    says it."""
    kinds = []
    for path, kind in CONTENT:
        path = path.replace(os.sep, "/")
        if any(n == path or n.startswith(path + "/") for n in names):
            kinds.append(kind)
    return kinds


def _signature(files):
    """What a mod holds, as its files' names (folded as Windows sees them) and sizes, mod.json left out (it
    differs by whether the mod is on)."""
    return sorted((n, size) for n, size in files.items() if n != "mod.json")


def _folder_files(folder, paths=None):
    """{name, folded as _fold does, with /: size} for the files in a mod's folder, as a .zip of it would hold
    them; `paths` (a dict), when given, gets each name's file on disk."""
    out = {}
    for d, dirs, names in os.walk(folder):
        dirs[:] = [x for x in dirs if x not in IGNORED]
        for fn in names:
            if fn in IGNORED or fn.endswith(".pyc"):
                continue
            full = os.path.join(d, fn)
            key = "/".join(_fold(os.path.relpath(full, folder).split(os.sep)))
            out[key] = os.path.getsize(full)
            if paths is not None:
                paths[key] = full
    return out


def _crc(path):
    """A file's CRC-32, as a .zip records it for each file it holds."""
    crc = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF


def _same_files(folder, files, crc_of):
    """Whether the mod in `folder` holds what `files` ({name: size}) does, mod.json aside: the same names and
    sizes, then (only when those agree, so a different mod costs no reading) the same contents, its files'
    CRC-32 against crc_of(name) (a .zip's own, or a folder's files read). A friend's palette with other colours
    in a file of the same size is different."""
    paths = {}
    have = _folder_files(folder, paths)
    if _signature(have) != _signature(files):
        return False
    try:
        return all(_crc(paths[n]) == crc_of(n) for n in have if n != "mod.json")
    except (OSError, KeyError):
        return False


def _existing(mods_root, mod_id, meta, files, crc_of):
    """The copy of a mod you have, beside the one being added: {"name", "version", "different" (it holds other
    files, or other contents, than the new one: _same_files), "take" (tick the new copy in a pack's preview:
    it's different and newer, or neither says a version), "keep" (a sentence when the new copy is an older one
    of the mods that go with Clan Mod Studio: never ticked)}, or None. Versions compare with mods.version_key:
    "0.4" is "0.4.0", and one that isn't a version compares with nothing."""
    folder = os.path.join(mods_root, mod_id)
    if not os.path.isfile(os.path.join(folder, "mod.json")):
        return None
    try:
        old = Mod(folder)
        name, have = old.name, old.version
    except (OSError, ValueError):
        name, have = mod_id, ""
    different = not _same_files(folder, files, crc_of)
    new = str(meta.get("version") or "")
    kn, kh = modlib.version_key(new), modlib.version_key(have)   # None for one that isn't a version
    both = kn is not None and kh is not None
    newer = (kn > kh) if both else (bool(new) and not have)
    from . import addons
    keep = None
    if addons.find(mod_id) and different and both and kh >= kn:
        keep = f"You have {name} {have}; this carries {new}: keeping yours"
    return {"name": name, "version": have, "different": different, "keep": keep,
            "take": different and not keep and (newer or (not new and not have))}


def _found(mods_root, mod_id, meta, files, root, crc_of):
    names = list(files)
    size = sum(files.values())
    kinds = _kinds(names)
    existing = _existing(mods_root, mod_id, meta, files, crc_of)
    req = meta.get("requires")
    uses = meta.get("uses")
    ids = lambda v: [x for x in ([v] if isinstance(v, str) else v if isinstance(v, list) else []) if isinstance(x, str)]
    if meta.get("pack"):
        kinds = ["mod pack"] + kinds
    name = str(meta.get("name") or mod_id)
    wanted = meta.get("wcmods").strip() if modlib.is_version(meta.get("wcmods")) else None
    too_new = modlib.needs_newer(wanted) if wanted else None
    return {"id": mod_id, "name": name, "description": str(meta.get("description") or ""),
            "version": str(meta.get("version") or ""), "author": str(meta.get("author") or ""),
            "requires": [i for i in ids(req) if i != modlib.MENU_ID], "uses": ids(uses), "kinds": kinds,
            "menu_page": modlib.MENU_ID in ids(req) + ids(uses),
            "code": any(n == c or n.startswith(c + "/") for n in names for c in CODE),
            "enabled": meta.get("enabled", True) is not False, "wcmods": wanted, "too_new": too_new,
            "files": len(names), "bytes": size, "existing": existing, "root": root}


def inspect(path, mods_root, name=None):
    """The mods in a .zip, without adding anything: [{id, name, description, version, author, requires,
    uses, kinds, code, enabled (on or off as it ships), wcmods (the oldest wcmods it says it needs, or None),
    too_new (why this wcmods leaves it out, or None), files, bytes, existing (the copy you have, or None),
    root}]. `name` is the download's file name, which names a mod whose mod.json is at the top."""
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
        mod_id = _identify(meta, r[-1] if r else os.path.splitext(name)[0], label, ids, mods_root, top=not r)
        crcs = {"/".join(_fold(p)): i.CRC for p, i in files}   # the .zip's own, read without unpacking
        out.append(_found(mods_root, mod_id, meta, {"/".join(_fold(p)): i.file_size for p, i in files}, "/".join(r),
                          crcs.get))
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


def _on(enable, mod_id, shipped):
    """Whether a mod goes in switched on: `enable` is one answer for every mod (True or False), or a dict
    {mod id: on} in which a mod it doesn't name goes in as it ships (`shipped`, its mod.json's "enabled")."""
    if isinstance(enable, dict):
        return bool(enable.get(mod_id, shipped))
    return bool(enable)


def _needs_on(mods_root, done):
    """Turn on what the mods just added switched on require, as switching them on does. Each entry's
    "also_on" gets the names of the mods that went on with it. One that needs a mod that isn't in mods/
    goes off instead (switching it on would be refused the same way), with "off_because" saying what it
    needs and "missing" the ids, so nothing waits at the next Apply on a requirement that can't be met."""
    for d in done:
        if not d["on"]:
            continue
        found = modlib.discover(mods_root)
        names = {m.id: m.name for m in found}
        missing = [i for i in modlib.needed(found, d["id"]) if i not in names]
        if missing:
            by_id = {m.id: m for m in found}
            if d["id"] in by_id:
                by_id[d["id"]].set_enabled(False)
            d["on"] = False
            d["missing"] = missing
            d["off_because"] = f"needs {', '.join(modlib.missing_name(i) for i in missing)}, which you don't have"
            continue
        changed, _ = modlib.switch(found, d["id"], True)
        d["also_on"] = [names.get(i, i) for i, _ in changed if i != d["id"]]


def add_zip(path, mods_root, backups_root, ids=None, enable=True, name=None):
    """Add the mods in a .zip (all of them, or those in `ids`). `enable` is True (all on), False (all off)
    or {mod id: on}, where a mod it doesn't name goes in as it ships. Returns [{id, name, code, on, replaced
    (the old copy's backup folder, or None), also_on (mods turned on because it needs them), and for one
    left off because a mod it needs is missing, off_because and missing}]."""
    with zipfile.ZipFile(path) as z:
        found = _inspect(z, mods_root, name or os.path.basename(path))
        chosen = [f for f in found if ids is None or f["id"] in ids]
        if not chosen:
            raise ValueError("none of the mods asked for is in this .zip")
        if sum(f["bytes"] for f in chosen) > MAX_BYTES:
            raise ValueError(f"this .zip unpacks to more than {MAX_BYTES // 1024 ** 3} GB")
        members = _members(z)
        os.makedirs(mods_root, exist_ok=True)
        done = []
        for f in chosen:
            root = tuple(p for p in f["root"].split("/") if p)
            on = _on(enable, f["id"], f["enabled"])
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
                replaced = _place(tmp, mods_root, f["id"], backups_root, on)
            except BaseException:
                shutil.rmtree(tmp, ignore_errors=True)
                raise
            done.append({"id": f["id"], "name": f["name"], "code": f["code"], "on": on, "replaced": replaced,
                         "also_on": []})
    _needs_on(mods_root, done)
    return done


def _mod_folders(path):
    path = os.path.abspath(path)
    if os.path.isfile(os.path.join(path, "mod.json")):
        return [path]
    return sorted(os.path.join(path, d) for d in os.listdir(path)
                  if not d.startswith("_") and os.path.isfile(os.path.join(path, d, "mod.json")))


def _folder_plan(path, mods_root):
    """[(folder, id, mod.json)] for the mods in a folder (one with a mod.json, or holding mod folders), each
    checked and named as a .zip's would be (_identify), before anything is copied."""
    plan, taken = [], set()
    for folder in _mod_folders(path):
        label = os.path.basename(folder)
        try:
            with open(os.path.join(folder, "mod.json"), encoding="utf-8-sig") as f:
                meta = json.load(f)
        except ValueError as e:
            raise ValueError(f"{label}: mod.json isn't valid JSON ({e})") from None
        if not isinstance(meta, dict):
            raise ValueError(f"{label}: mod.json should hold an object")
        plan.append((folder, _identify(meta, label, label, taken, mods_root), meta))
    if not plan:
        raise ValueError(f"{path} has no mod in it (a mod is a folder with a mod.json)")
    return plan


def inspect_folder(path, mods_root):
    """As inspect(), for a folder that is a mod or holds mod folders."""
    out = []
    for folder, mod_id, meta in _folder_plan(path, mods_root):
        paths = {}
        files = _folder_files(folder, paths)
        out.append(_found(mods_root, mod_id, meta, files, "", lambda n, paths=paths: _crc(paths[n])))
    return out


def add_folder(path, mods_root, backups_root, ids=None, enable=True):
    """Add the mods in a folder (one with a mod.json, or holding mod folders): all of them, or those in
    `ids`, on or off as add_zip's `enable` says. Returns as add_zip."""
    path = os.path.abspath(path)
    if not _mod_folders(path):
        raise ValueError(f"{path} has no mod in it (a mod is a folder with a mod.json)")
    try:
        inside = os.path.commonpath([path, os.path.abspath(mods_root)]) == os.path.abspath(mods_root)
    except ValueError:   # on another drive
        inside = False
    if inside:
        raise ValueError("that's already in your mods folder")
    plan = [(folder, mod_id, meta) for folder, mod_id, meta in _folder_plan(path, mods_root)
            if ids is None or mod_id in ids]
    if not plan:
        raise ValueError("none of the mods picked are in it")
    os.makedirs(mods_root, exist_ok=True)
    done = []
    for folder, mod_id, meta in plan:
        on = _on(enable, mod_id, meta.get("enabled", True) is not False)
        tmp = tempfile.mkdtemp(prefix=f"_adding-{mod_id}-", dir=mods_root)
        try:
            os.rmdir(tmp)
            shutil.copytree(folder, tmp, symlinks=False, ignore=shutil.ignore_patterns(*IGNORED, "*.pyc"))
            replaced = _place(tmp, mods_root, mod_id, backups_root, on)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        m = Mod(os.path.join(mods_root, mod_id))
        done.append({"id": mod_id, "name": m.name, "code": m.has_code(), "on": on, "replaced": replaced,
                     "also_on": []})
    _needs_on(mods_root, done)
    return done


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
            try:
                when = datetime.datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").isoformat(timespec="minutes")
            except ValueError:   # a date that can't be: not one of ours, and no reason to fail the list
                continue
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


DEFAULT_ID = "my-mods"   # the mod the studio's Make pages save into first (wc.modTarget's My mods)


def pack(mod, found=()):
    """The mod as a .zip (its folder inside, named as it is), to share. Returns the bytes. A mod pack
    (packs.py) carries the mods in it too, each in its own folder, from `found` (the mods folder's mods).
    In a pack's .zip, My mods (DEFAULT_ID, which every player has one of) goes in as "<pack id>-mods", named
    "<pack name>: its own content" ("-2" and so on after it while the pack holds a mod by that name already),
    with every requires and uses naming it rewritten, so whoever adds the pack keeps their own My mods and
    plays the pack's; the folders here are left as they are. Only mod.json's requires and uses are
    rewritten: content that names my-mods itself (a script reading mods/my-mods, a coat preset's id made
    from it) still says my-mods in the pack."""
    import io
    folders = [mod]
    rename = {}
    if mod.meta.get("pack"):
        by_id = {m.id: m for m in found}
        missing = [i for i in modlib.needed(list(found), mod.id) if i not in by_id]
        if missing:
            raise ValueError(f"{mod.name} needs {', '.join(missing)}, which isn't in your mods, so the pack can't carry it")
        folders += [by_id[i] for i in modlib.needed(list(found), mod.id)]
        if any(m.id == DEFAULT_ID for m in folders):
            taken = {m.id for m in folders}
            base = new_id = safe_id(f"{mod.id}-mods")
            n = 2
            while new_id in taken:   # never two folders under one name in the .zip
                new_id, n = safe_id(f"{base[:58]}-{n}"), n + 1
            rename[DEFAULT_ID] = new_id
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for m in folders:
            top = rename.get(m.id, m.id)
            for folder, dirs, files in os.walk(m.folder):
                dirs[:] = sorted(d for d in dirs if d not in IGNORED)
                for f in sorted(files):
                    if f in IGNORED or f.endswith(".pyc"):
                        continue
                    full = os.path.join(folder, f)
                    arc = os.path.join(top, os.path.relpath(full, m.folder)).replace(os.sep, "/")
                    if rename and os.path.normcase(full) == os.path.normcase(os.path.join(m.folder, "mod.json")):
                        z.writestr(arc, _renamed_meta(m, rename, mod))
                    else:
                        z.write(full, arc)
    return buf.getvalue()


def _renamed_meta(m, rename, pack_mod):
    """A mod's mod.json as a pack's .zip carries it, with the mods in `rename` under their new ids."""
    with open(os.path.join(m.folder, "mod.json"), encoding="utf-8-sig") as f:
        meta = json.load(f)
    for key in ("requires", "uses"):
        v = meta.get(key)
        if isinstance(v, str):
            meta[key] = rename.get(v, v)
        elif isinstance(v, list):
            meta[key] = [rename.get(x, x) if isinstance(x, str) else x for x in v]
    if m.id in rename:
        meta["name"] = f"{pack_mod.name}: its own content"
    return json.dumps(meta, indent=2) + "\n"
