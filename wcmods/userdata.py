"""Your own files, kept outside wcmods' folder so that updating wcmods (git pull, or a new download unzipped
over it) never touches them. config.data_dir() says where: %LOCALAPPDATA%\\WCMods, unless WCMODS_DATA says.

  mods/          your mods
  wcmods.json    wcmods' settings (the mod menu's key among them) and its record of what's installed
  backups/       save backups, and mods that were removed or replaced (backups/mods)

Older versions kept mods/, wcmods.json and backups/ in wcmods' own folder; the first start after an update
moves them here. They also had the mod menu as a mod of its own, mods/mod-menu, with its settings in its
menu.json: the menu is wcmods' own now, so its settings move into wcmods.json and that folder goes
(retire_menu_mod).
"""
import errno
import json
import os
import shutil
import sys

from .config import same_folder
from .modzip import BACKUP_NAME, _backup, _stamp

OLD_MENU = "mod-menu"   # the mod menu's own mod, from when it was one
# Its menu.json's settings -> where they are now, in wcmods.json ("cheats" waits there for the Menu pages
# mod, whose setting it is: menupages.add takes it).
OLD_MENU_KEYS = {"key": "menu_key", "pad": "menu_pad", "size": "menu_scale", "cheats": "cheats"}
OLD_MENU_DEFAULTS = {"key": "INS", "pad": "Gamepad_Special_Left", "size": 1.0, "cheats": False}   # as it came


def prepare(root, data_dir, log=None):
    """Ready the data folder before anything reads it: what an older version left in wcmods' folder (root)
    moved in, and an old mods/mod-menu's settings moved into wcmods.json. `log` gets what moved and anything
    that couldn't be done (stderr unless given, so a command printing JSON stays readable); none of that
    stops the command."""
    log = log or (lambda m: print(m, file=sys.stderr))
    try:
        moved, notes, problems = migrate(root, data_dir)
    except (OSError, ValueError) as e:   # ValueError: a wcmods.json that isn't JSON
        moved, notes, problems = [], [], [f"{root}'s files ({getattr(e, 'strerror', None) or e})"]
    if moved:
        log(f"Moved your {_join(moved)} out of the wcmods folder, to {data_dir}, where updating wcmods won't "
            "touch them. Apply to game once (or `wcmods install`), so the game finds your mods there.")
    for note in notes:
        log(note)
    for p in problems:
        log(f"Couldn't move {p}. Close whatever has it open; the next start tries again.")
    try:
        if retire_menu_mod(data_dir):
            log("The mod menu is part of wcmods now, so it's no longer in your mods; its key, button and size are "
                "in wcmods.json. Its pages about the game are a mod of their own, Menu pages: Get set up in Clan "
                "Mod Studio adds it. Apply to game once.")
    except (OSError, ValueError) as e:   # ValueError: a wcmods.json that isn't JSON
        log(f"Couldn't move the old mod menu's settings out of {os.path.join(data_dir, 'mods', OLD_MENU)} "
            f"({getattr(e, 'strerror', None) or e}).")


def migrate(root, data_dir):
    """Move wcmods.json, mods/ and backups/ from wcmods' folder, where older versions kept them, into
    data_dir. Nothing is lost when data_dir has some already (a newer version ran from another folder first,
    or a second copy of wcmods moves in):
    - wcmods.json: the one there stays and takes the settings only yours has; yours goes to backups.
    - a mod: the one there stays; yours goes to backups as a replaced one (Settings and repair puts it back).
    - the mod menu's own mod, from when it was one (mods/mod-menu): yours replaces the one there while that
      still has the menu's defaults (it was only put in); otherwise yours is dropped, as the one there has
      settings of its own. retire_menu_mod then moves them into wcmods.json.
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
            menu = _is_old_menu(src)
            if menu and _is_old_menu(dest) and _untouched(dest):
                shutil.rmtree(dest, ignore_errors=True)
            if not os.path.exists(dest):
                if _move(src, dest, problems) and not menu and os.path.isfile(os.path.join(dest, "mod.json")):
                    n += 1
            elif menu:   # one there already: its settings are the ones to keep, if it's the old menu too
                if not _is_old_menu(dest):   # a player's own mod-menu: take the old menu's settings from here
                    _take_menu_settings(src, data_dir)
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


def _is_old_menu(folder):
    """Whether this folder is the mod menu's own mod, from when it was one: wcmods' mod.json and menu.json,
    and nothing else of a mod's."""
    if os.path.basename(folder) != OLD_MENU or not os.path.isfile(os.path.join(folder, "menu.json")):
        return False
    meta = _read_json(os.path.join(folder, "mod.json"))
    return bool(meta) and meta.get("author") == "wcmods" and set(os.listdir(folder)) <= {"mod.json", "menu.json"}


def retire_menu_mod(data_dir):
    """The mod menu was a mod of its own (mods/mod-menu); it's wcmods' own now. Move that mod's settings into
    wcmods.json (where wcmods.json has none of its own for them) and remove the folder. Returns whether
    there was one. A mod-menu that's someone's own mod (more in it than wcmods put there) is left alone."""
    folder = os.path.join(data_dir, "mods", OLD_MENU)
    if not _is_old_menu(folder):
        return False
    _take_menu_settings(folder, data_dir)
    shutil.rmtree(folder, ignore_errors=True)
    return True


def _take_menu_settings(folder, data_dir):
    """The old mod menu's settings (its menu.json, in folder) into data_dir's wcmods.json, where that has
    none of its own for them."""
    old = _read_json(os.path.join(folder, "menu.json")) or {}
    from .config import Config
    cfg = Config(data_dir, data_dir)
    changed = False
    for key, new in OLD_MENU_KEYS.items():
        if key in old and new not in cfg.data and not (key == "cheats" and not old[key]):
            cfg.data[new] = old[key]
            changed = True
    if changed:
        cfg.save()


def _untouched(folder):
    """Whether the old mod menu in folder has nothing of yours: its settings as they came."""
    mine = _read_json(os.path.join(folder, "menu.json")) or {}
    return all(mine.get(k, v) == v for k, v in OLD_MENU_DEFAULTS.items())


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
