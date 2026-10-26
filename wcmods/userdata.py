"""Your own files, kept outside wcmods' folder so that updating wcmods (git pull, or a new download unzipped
over it) never touches them. config.data_dir() says where: %LOCALAPPDATA%\\WCMods, unless WCMODS_DATA says.

  mods/          your mods, the mod menu among them
  wcmods.json    wcmods' settings and its record of what's installed
  backups/       save backups, and mods that were removed or replaced (backups/mods)

The mods that come with wcmods (the mod menu) are in wcmods/builtin. Each start puts them in mods/, or
brings the copy there up to date, keeping what's yours: whether it's on, its priority and its settings.

Older versions kept mods/, wcmods.json and backups/ in wcmods' own folder; the first start after an update
moves them here.
"""
import datetime
import errno
import json
import os
import shutil
import sys

BUILTIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "builtin")
YOURS = ("enabled", "priority")            # in a built-in mod's mod.json: as you set them
SETTINGS = ("menu.json", "settings.json")  # a built-in mod's settings: your values, with keys wcmods adds


def prepare(root, data_dir, log=None):
    """Ready the data folder before anything reads it: what an older version left in wcmods' folder (root)
    moved in, and the built-in mods up to date. `log` gets what moved (stderr unless given, so a command
    printing JSON stays readable)."""
    log = log or (lambda m: print(m, file=sys.stderr))
    moved, problems = migrate(root, data_dir)
    if moved:
        log(f"Moved your {_join(moved)} out of the wcmods folder, to {data_dir}, where updating wcmods won't "
            "touch them. Apply to game once (or `wcmods install`), so the game finds your mods there.")
    for p in problems:
        log(f"Couldn't move {p}. Close whatever has it open; the next start tries again.")
    sync_builtin(os.path.join(data_dir, "mods"))


def migrate(root, data_dir):
    """Move wcmods.json, mods/ and backups/ from wcmods' folder, where older versions kept them, into
    data_dir. Nothing is overwritten: when data_dir already has a wcmods.json or a mod of the same name (a
    second copy of wcmods moving in), the one already there stays and the old one goes to data_dir's backups,
    a mod as a replaced one (Settings and repair puts it back). An old copy of a built-in mod is dropped then:
    the one there has your settings. Returns ([what moved], [what couldn't be, and why]); what couldn't (a
    file open in another program) stays, for the next start."""
    if _same(root, data_dir):   # WCMODS_DATA is wcmods' own folder: everything stays where it is
        return [], []
    moved, problems = [], []
    backups = os.path.join(data_dir, "backups")

    old = os.path.join(root, "wcmods.json")
    if os.path.isfile(old):
        new = os.path.join(data_dir, "wcmods.json")
        if os.path.exists(new):
            new = _free(os.path.join(backups, f"{_stamp()}-wcmods.json"))
        if _move(old, new, problems):
            moved.append("settings (wcmods.json)")

    old = os.path.join(root, "mods")
    if os.path.isdir(old):
        n = 0
        for name in sorted(os.listdir(old)):
            src, dest = os.path.join(old, name), os.path.join(data_dir, "mods", name)
            builtin = os.path.isfile(os.path.join(BUILTIN, name, "mod.json"))
            if not os.path.exists(dest):
                if _move(src, dest, problems) and not builtin and os.path.isfile(os.path.join(dest, "mod.json")):
                    n += 1
            elif builtin:
                shutil.rmtree(src, ignore_errors=True)
            else:
                from .modzip import _backup
                try:
                    _backup(src, backups, "replaced")
                    n += 1
                except OSError as e:
                    problems.append(f"{src} ({e.strerror or e})")
        _rmdir(old)
        if n:
            moved.append(f"{n} mod{'s' if n != 1 else ''}")

    old = os.path.join(root, "backups")
    if os.path.isdir(old):
        any_moved = False
        for name in sorted(os.listdir(old)):
            src = os.path.join(old, name)
            if name == "mods" and os.path.isdir(src):   # removed and replaced mods: in with any already there
                for entry in sorted(os.listdir(src)):
                    any_moved |= _move(os.path.join(src, entry), _free(os.path.join(backups, "mods", entry)), problems)
                _rmdir(src)
            else:
                any_moved |= _move(src, _free(os.path.join(backups, name)), problems)
        _rmdir(old)
        if any_moved:
            moved.append("backups")
    return moved, problems


def sync_builtin(mods_root):
    """Put the mods that come with wcmods (wcmods/builtin) in mods_root, or bring the copies there up to
    date: each file as wcmods has it, except what's yours. That's mod.json's "enabled" and "priority", and
    the values in a settings file (a key only wcmods' copy has is added; the "_help" notes are wcmods'). A
    file is written only when that changes it, so an install doesn't see a change that isn't one. Returns
    the ids put in or updated."""
    changed = []
    for mod_id in sorted(os.listdir(BUILTIN)) if os.path.isdir(BUILTIN) else []:
        src = os.path.join(BUILTIN, mod_id)
        if not os.path.isfile(os.path.join(src, "mod.json")):
            continue
        wrote = False
        for folder, _, files in os.walk(src):
            for name in files:
                rel = os.path.relpath(os.path.join(folder, name), src)
                wrote = _sync(os.path.join(folder, name), os.path.join(mods_root, mod_id, rel), rel) or wrote
        if wrote:
            changed.append(mod_id)
    return changed


def _sync(src, dest, rel):
    with open(src, "rb") as f:
        new = f.read()
    if rel == "mod.json" or rel in SETTINGS:
        shipped, mine = json.loads(new.decode("utf-8-sig")), _read_json(dest)
        if mine is None:
            if os.path.exists(dest) and rel != "mod.json":
                return False   # settings that can't be read are yours to fix, not wcmods' to replace
            mine = {}
        if rel == "mod.json":
            want = {**shipped, **{k: mine[k] for k in YOURS if k in mine}}
        else:
            want = {**shipped, **{k: v for k, v in mine.items() if not k.startswith("_")}}
        if want == mine:
            return False
        new = (json.dumps(want, indent=2) + "\n").encode("utf-8")
    elif os.path.isfile(dest):
        with open(dest, "rb") as f:
            if f.read() == new:
                return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(new)
    return True


def _read_json(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _move(src, dest, problems):
    """Move a file or folder to dest (which mustn't exist). A folder going to another drive is copied beside
    its place first and renamed in when whole, so a copy that fails part way leaves nothing behind."""
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if not os.path.isdir(src):
            shutil.move(src, dest)
            return True
        try:
            os.rename(src, dest)
            return True
        except OSError as e:
            if e.errno != errno.EXDEV and getattr(e, "winerror", None) != 17:   # 17: not the same drive
                raise
        tmp = os.path.join(os.path.dirname(dest), "_moving-" + os.path.basename(dest))
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            shutil.copytree(src, tmp)
            os.rename(tmp, dest)
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
    except OSError as e:
        problems.append(f"{src} ({e.strerror or e})")
        return False
    shutil.rmtree(src, ignore_errors=True)   # what's left (a file open elsewhere) is moved aside next start
    return True


def _free(path):
    """path, or path with -2, -3... when that's taken (before a file's extension)."""
    stem, ext = (path, "") if os.path.isdir(path) else os.path.splitext(path)
    n = 2
    while os.path.exists(path):
        path = f"{stem}-{n}{ext}"
        n += 1
    return path


def _rmdir(path):
    try:
        os.rmdir(path)   # only when empty
    except OSError:
        pass


def _same(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
