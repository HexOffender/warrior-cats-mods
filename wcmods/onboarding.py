"""Getting a player from a fresh download to playing with mods: what Clan Mod Studio's "Get set up" steps
check and do, its Play button, and handing it a mod's .zip dropped on the launcher.

The steps, in the order the studio shows them:
1. the game: found on the Steam libraries, or a folder the player picks;
2. a safety copy of the save, made the first time the studio sees one;
3. UE4SS, the script loader most mods need: downloaded from its GitHub releases (or a .zip the player
   gives) and set up for players (ue4ss.install_loader);
4. optional: the Oodle DLL from another game, which only names, game data and eye-colour mods need.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

from . import mods as modlib, pipeline, save, ue4ss
from .config import EXE_NAME, STEAM_APP_ID, game_running

INBOX = os.path.join(tempfile.gettempdir(), "wcmods-studio-inbox.json")


def _game_ok(folder):
    return bool(folder) and os.path.isfile(os.path.join(folder, "Wrc", "Binaries", "Win64", EXE_NAME))


def status(cfg, backups_root):
    """{"game", "save", "backup", "loader", "oodle", "running", "done"}: each step's state for the studio."""
    cfg.reload()
    game = cfg.game_dir if _game_ok(cfg.game_dir) else None
    win64 = cfg.win64_dir if game else None
    save_found = os.path.isfile(os.path.join(cfg.save_dir, save.SAV_NAME))
    backups = save.list_backups(backups_root)
    out = {"game": {"ok": bool(game), "dir": game},
           "save": {"ok": save_found},
           "backup": {"ok": bool(backups), "latest": backups[-1] if backups else None},
           "loader": {"ok": ue4ss.loader_installed(win64), "page": ue4ss.RELEASE_PAGE},
           "oodle": {"ok": bool(cfg.oodle_dll), "path": cfg.oodle_dll},
           "running": game_running()}
    # The Oodle DLL is optional: most mods don't need it.
    out["done"] = all(out[k]["ok"] for k in ("game", "save", "backup", "loader"))
    return out


def set_game_dir(cfg, folder):
    """Use the game in `folder` (the one holding Wrc\\, or Wrc itself, or the exe's folder)."""
    folder = os.path.normpath(str(folder or "").strip().strip('"'))
    tries = [folder, os.path.dirname(folder)]
    for _ in range(3):   # the exe's folder: <game>\Wrc\Binaries\Win64
        tries.append(os.path.dirname(tries[-1]))
    for f in tries:
        if _game_ok(f):
            cfg.reload()
            cfg.data["game_dir"] = f
            cfg.save()
            return f
    raise ValueError(f"the game isn't in {folder}: it's the folder with Wrc in it, usually "
                     r"...\steamapps\common\Warrior Cats Clans of the Forest")


def set_oodle(cfg, path):
    """Use an Oodle DLL (oo2core_*_win64.dll) from another game."""
    path = os.path.normpath(str(path or "").strip().strip('"'))
    if os.path.isdir(path):
        found = sorted(f for f in os.listdir(path) if f.lower().startswith("oo2core_") and f.lower().endswith("_win64.dll"))
        if not found:
            raise ValueError(f"there's no oo2core_*_win64.dll in {path}")
        path = os.path.join(path, found[-1])
    name = os.path.basename(path).lower()
    if not (os.path.isfile(path) and name.startswith("oo2core_") and name.endswith("_win64.dll")):
        raise ValueError("pick a file called oo2core_<number>_win64.dll")
    from .oodle import Oodle
    try:
        Oodle(path)
    except OSError as e:
        raise ValueError(f"Windows couldn't load {path}: {e}") from None
    cfg.reload()
    cfg.data["oodle_dll"] = path
    cfg.save()
    return path


def first_backup(cfg, backups_root):
    """A safety copy of the save, the first time there is one and no backup yet; its name, or None."""
    if save.list_backups(backups_root) or not os.path.isfile(os.path.join(cfg.save_dir, save.SAV_NAME)):
        return None
    where, _ = save.backup(cfg.save_dir, backups_root, "first-run")
    return os.path.basename(where)


def install_loader(cfg, zip_path=None, log=print):
    """Put UE4SS in the game: from `zip_path`, or downloaded from GitHub. The game must be closed."""
    if not _game_ok(cfg.game_dir):
        raise RuntimeError("find the game first")
    if game_running():
        raise RuntimeError("close the game first: it has the script loader's files open")
    console = bool(cfg.data.get("console", True))
    if zip_path:
        ue4ss.install_loader(zip_path, cfg.win64_dir, console=console, log=log)
        return {"from": os.path.basename(zip_path)}
    asset = ue4ss.download_and_install(cfg.win64_dir, console=console, log=log)
    return {"from": asset["name"]}


def remaps(ctx):
    """Whether the enabled mods remap keys, so the game has to start with the key remapper."""
    from .cli import _remap_plan
    send, block, menu_send, _ = _remap_plan(ctx)
    return bool(send or block or menu_send)


def play(ctx, log=print, force=False):
    """Clan Mod Studio's Play: apply waiting changes (with the game closed), then start the game through
    Steam, with the key remapper in a window of its own when mods remap keys."""
    cfg = ctx.cfg
    if game_running():
        raise RuntimeError("the game is already running")
    found = modlib.discover(ctx.mods_root)
    applied = False
    if pipeline.pending(cfg, found)["any"] or pipeline.install_outdated(cfg):
        log("applying your mods first:")
        pipeline.build(cfg, found, ctx.build_dir, log)
        pipeline.install(cfg, ctx.build_dir, ctx.backups, log, force=force)
        applied = True
    with_remaps = remaps(ctx)
    if with_remaps:
        # `wcmods play` starts the game and runs the remapper until it closes, in its own console window.
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen([sys.executable, os.path.join(ctx.root, "wcmods.py"), "play"], cwd=ctx.root, creationflags=flags)
        log("starting the game with your key remaps (their window closes when the game does)")
    else:
        os.startfile(f"steam://rungameid/{STEAM_APP_ID}")
        log("starting the game through Steam")
    return {"applied": applied, "remaps": with_remaps}


# ---------- a mod's .zip dropped on the launcher ----------
def put_inbox(path):
    """Leave a mod's .zip (or folder) for the studio to offer to add: one already running picks it up."""
    with open(INBOX, "w", encoding="utf-8") as f:
        json.dump({"path": os.path.abspath(path), "time": time.time()}, f)


def inbox():
    """The .zip or folder waiting to be added (left within the last ten minutes), or None."""
    try:
        with open(INBOX, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    path = data.get("path")
    if not path or time.time() - data.get("time", 0) > 600 or not os.path.exists(path):
        clear_inbox()
        return None
    return path


def clear_inbox():
    try:
        os.remove(INBOX)
    except OSError:
        pass
