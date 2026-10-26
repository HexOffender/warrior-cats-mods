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
import datetime
import errno
import json
import os
import shutil
import sys

OLD_MENU = "mod-menu"   # the mod menu's own mod, from when it was one
# Its menu.json's settings -> where they are now, in wcmods.json ("cheats" waits there for the Menu pages
# mod, whose setting it is: menupages.add takes it).
OLD_MENU_KEYS = {"key": "menu_key", "pad": "menu_pad", "size": "menu_scale", "cheats": "cheats"}


def prepare(root, data_dir, log=None):
    """Ready the data folder before anything reads it: what an older version left in wcmods' folder (root)
    moved in, and an old mods/mod-menu's settings moved into wcmods.json. `log` gets what moved (stderr
    unless given, so a command printing JSON stays readable)."""
    log = log or (lambda m: print(m, file=sys.stderr))
    moved, problems = migrate(root, data_dir)
    if moved:
        log(f"Moved your {_join(moved)} out of the wcmods folder, to {data_dir}, where updating wcmods won't "
            "touch them. Apply to game once (or `wcmods install`), so the game finds your mods there.")
    for p in problems:
        log(f"Couldn't move {p}. Close whatever has it open; the next start tries again.")
    if retire_menu_mod(data_dir):
        log("The mod menu is part of wcmods now, so it's no longer in your mods; its key, button and size are "
            "in wcmods.json. Its pages about the game are a mod of their own, Menu pages: Get set up in Clan Mod "
            "Studio adds it. Apply to game once.")


def migrate(root, data_dir):
    """Move wcmods.json, mods/ and backups/ from wcmods' folder, where older versions kept them, into
    data_dir. Nothing is overwritten: when data_dir already has a wcmods.json or a mod of the same name (a
    second copy of wcmods moving in), the one already there stays and the old one goes to data_dir's backups,
    a mod as a replaced one (Settings and repair puts it back). Returns ([what moved], [what couldn't be, and why]); what couldn't (a
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
            menu = _is_old_menu(src)
            if not os.path.exists(dest):
                if _move(src, dest, problems) and not menu and os.path.isfile(os.path.join(dest, "mod.json")):
                    n += 1
            elif menu:   # one there already: its settings are the ones to keep
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
    shutil.rmtree(folder, ignore_errors=True)
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
