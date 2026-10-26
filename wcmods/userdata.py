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
import errno
import json
import os
import shutil
import sys

from .config import same_folder
from .modzip import BACKUP_NAME, _backup, _stamp

BUILTIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "builtin")
YOURS = ("enabled", "priority")            # in a built-in mod's mod.json: as you set them
SETTINGS = ("menu.json", "settings.json")  # a built-in mod's settings: your values, with keys wcmods adds


def prepare(root, data_dir, log=None):
    """Ready the data folder before anything reads it: what an older version left in wcmods' folder (root)
    moved in, and the built-in mods up to date. `log` gets what moved and anything that couldn't be done
    (stderr unless given, so a command printing JSON stays readable); none of that stops the command."""
    log = log or (lambda m: print(m, file=sys.stderr))
    try:
        moved, notes, problems = migrate(root, data_dir)
    except OSError as e:
        moved, notes, problems = [], [], [f"{root}'s files ({e.strerror or e})"]
    if moved:
        log(f"Moved your {_join(moved)} out of the wcmods folder, to {data_dir}, where updating wcmods won't "
            "touch them. Apply to game once (or `wcmods install`), so the game finds your mods there.")
    for note in notes:
        log(note)
    for p in problems:
        log(f"Couldn't move {p}. Close whatever has it open; the next start tries again.")
    try:
        sync_builtin(os.path.join(data_dir, "mods"))
    except OSError as e:
        log(f"Couldn't bring the mods that come with wcmods up to date in {os.path.join(data_dir, 'mods')} "
            f"({e.strerror or e}).")


def migrate(root, data_dir):
    """Move wcmods.json, mods/ and backups/ from wcmods' folder, where older versions kept them, into
    data_dir. Nothing is lost when data_dir has some already (a newer version ran from another folder first,
    or a second copy of wcmods moves in):
    - wcmods.json: the one there stays and takes the settings only yours has; yours goes to backups.
    - a mod: the one there stays; yours goes to backups as a replaced one (Settings and repair puts it back).
    - a built-in mod (the mod menu): yours replaces the one there while that still has wcmods' defaults
      (it was only put in); otherwise yours is dropped, as the one there has settings of its own.
    Returns ([what moved], [notes on what didn't], [what couldn't be moved, and why]); what couldn't (a file
    open in another program) stays, for the next start."""
    if same_folder(root, data_dir):   # WCMODS_DATA is wcmods' own folder: everything stays where it is
        return [], [], []
    moved, notes, problems = [], [], []
    backups = os.path.join(data_dir, "backups")

    old = os.path.join(root, "wcmods.json")
    if os.path.isfile(old):
        new = os.path.join(data_dir, "wcmods.json")
        if not os.path.exists(new):
            if _move(old, new, problems):
                moved.append("settings (wcmods.json)")
        else:
            yours, there = _read_json(old) or {}, _read_json(new)
            added = sorted(k for k in yours if there is not None and k not in there and not k.startswith("_"))
            if added:
                with open(new, "w", encoding="utf-8") as f:
                    json.dump({**there, **{k: yours[k] for k in added}}, f, indent=2)
                    f.write("\n")
            aside = _free(os.path.join(backups, f"{_stamp()}-wcmods.json"))
            if _move(old, aside, problems):
                notes.append(f"{new} was there already, so it stays" + (f", with {', '.join(added)} from yours"
                             if added else "") + f"; your old wcmods.json is in {aside}.")

    old = os.path.join(root, "mods")
    if os.path.isdir(old):
        n = 0
        for name in sorted(os.listdir(old)):
            src, dest = os.path.join(old, name), os.path.join(data_dir, "mods", name)
            builtin = os.path.isfile(os.path.join(BUILTIN, name, "mod.json"))
            if builtin and os.path.isdir(dest) and _untouched(dest, name):
                shutil.rmtree(dest, ignore_errors=True)
            if not os.path.exists(dest):
                if _move(src, dest, problems) and not builtin and os.path.isfile(os.path.join(dest, "mod.json")):
                    n += 1
            elif builtin:
                shutil.rmtree(src, ignore_errors=True)
            else:
                try:
                    kept = _backup(src, backups, "replaced")
                    notes.append(f"{dest} was there already, so it stays; your old copy is in {kept} "
                                 "(Settings and repair can put it back).")
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
                    dest = _free_mod_backup(os.path.join(backups, "mods"), entry)
                    any_moved |= _move(os.path.join(src, entry), dest, problems)
                _rmdir(src)
            else:
                any_moved |= _move(src, _free(os.path.join(backups, name)), problems)
        _rmdir(old)
        if any_moved:
            moved.append("backups")
    return moved, notes, problems


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


def _untouched(folder, mod_id):
    """Whether the copy of a built-in mod in folder has nothing of yours yet: wcmods' own on/off and
    priority, and its settings as they come."""
    for name in ("mod.json",) + SETTINGS:
        shipped = _read_json(os.path.join(BUILTIN, mod_id, name))
        if shipped is None:
            continue
        mine = _read_json(os.path.join(folder, name)) or {}
        keys = YOURS if name == "mod.json" else [k for k in {**shipped, **mine} if not k.startswith("_")]
        if any(mine.get(k, shipped.get(k)) != shipped.get(k) for k in keys):
            return False
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


def _free_mod_backup(folder, name):
    """folder/name for a removed or replaced mod's backup, numbered after its time when that's taken, as
    modzip numbers them, so the mod's id at the end of the name stays as it was."""
    m = BACKUP_NAME.match(name)
    path, n = os.path.join(folder, name), 2
    while m and os.path.exists(path):
        path = os.path.join(folder, f"{m.group(1)}-{n}-{m.group(2)}-{m.group(3)}")
        n += 1
    return path if m else _free(path)


def _rmdir(path):
    try:
        os.rmdir(path)   # only when empty
    except OSError:
        pass


def _join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
