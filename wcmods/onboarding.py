"""Getting a player from a fresh download to playing with mods: what Clan Mod Studio's "Get set up" steps
check and do, its Play button, and handing it a mod's .zip dropped on the launcher.

The steps, in the order the studio shows them:
1. the game: found on the Steam libraries, or a folder the player picks;
2. a safety copy of the save, made the first time the studio sees one;
3. UE4SS, the script loader most mods need: downloaded from its GitHub releases (or a .zip the player
   gives) and set up for players (ue4ss.install_loader);
4. the mod menu's pages about the game, a mod of their own (Menu pages): downloaded from its GitHub
   releases (or a .zip the player gives) into their mods (menupages.add), or skipped for now (wcmods.json
   "skip_menu_pages").
"""
import json
import os
import tempfile
import time

from . import menupages, mods as modlib, pipeline, ue4ss
from .formats import save
from .config import STEAM_APP_ID, game_running, is_game_dir as _game_ok, steam_elsewhere, steam_elsewhere_text

INBOX = os.path.join(tempfile.gettempdir(), "wcmods-studio-inbox.json")


def status(cfg, backups_root):
    """{"game", "save", "backup", "loader", "pages", "running", "done"}: each step's state for the studio. The
    game's "steam" is Steam's copy of the game when it isn't the one found (with "steam_text" saying what that
    means): the Mods page offers to switch, whether or not every step is done."""
    cfg.reload()
    game = cfg.game_dir if _game_ok(cfg.game_dir) else None
    win64 = cfg.win64_dir if game else None
    save_found = os.path.isfile(os.path.join(cfg.save_dir, save.SAV_NAME))
    backups = save.list_backups(backups_root)
    steam = steam_elsewhere(cfg) if game else None
    out = {"game": {"ok": bool(game), "dir": game, "steam": steam,
                    "steam_text": steam_elsewhere_text(steam, game, fix=False) if steam else None},
           "save": {"ok": save_found},
           "backup": {"ok": bool(backups), "latest": backups[-1] if backups else None},
           "loader": {"ok": ue4ss.loader_installed(win64), "page": ue4ss.RELEASE_PAGE},
           "pages": menupages.status(cfg),
           "running": game_running()}
    # The pages step is done once they're in your mods (on or off, code allowed or not: the mod's card says
    # what's missing), or skipped.
    out["pages"]["ok"] = out["pages"]["installed"] or bool(cfg.data.get("skip_menu_pages"))
    out["done"] = all(out[k]["ok"] for k in ("game", "save", "backup", "loader", "pages"))
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



def first_backup(cfg, backups_root):
    """A safety copy of the save, the first time there is one and no backup yet; its name, or None."""
    if save.list_backups(backups_root) or not os.path.isfile(os.path.join(cfg.save_dir, save.SAV_NAME)):
        return None
    where, _ = save.backup(cfg.save_dir, backups_root, "first-run")
    return os.path.basename(where)


def add_pages(cfg, zip_path=None, log=print):
    """Put the Menu pages mod in your mods, or update it: from `zip_path`, or downloaded from GitHub."""
    return menupages.add(cfg, zip_path, log=log)


def skip_pages(cfg):
    """Get set up without the Menu pages mod for now (it can still be added, then or as any mod)."""
    cfg.reload()
    cfg.data["skip_menu_pages"] = True
    cfg.save()
    return {"skipped": True}


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
    """Whether the enabled mods remap keys that the in-game script can't, which only the old (deprecated) key
    remapper does."""
    from .sections.controls import remap_plan
    send, block, menu_send, _ = remap_plan(ctx.mods_root, ctx.cfg)
    return bool(send or block or menu_send)


def play(ctx, log=print, force=False):
    """Clan Mod Studio's Play: apply waiting changes (with the game closed), then start the game through
    Steam. Remaps work inside the game; the old key remapper (deprecated) isn't started, and Play says when
    some remaps need it."""
    cfg = ctx.cfg
    if game_running():
        raise RuntimeError("the game is already running")
    found = modlib.discover(ctx.mods_root)
    applied, manifest = False, None
    if pipeline.pending(cfg, found)["any"] or pipeline.install_outdated(cfg):
        log("applying your mods first:")
        manifest = pipeline.build(cfg, found, ctx.build_dir, log)
        pipeline.install(cfg, ctx.build_dir, ctx.backups, log, force=force)
        applied = True
        for w in manifest["warnings"]:   # the studio's drawer sums them up from the manifest; the log has them too
            log(f"warning: {w}")
    with_remaps = remaps(ctx)
    os.startfile(f"steam://rungameid/{STEAM_APP_ID}")
    log("starting the game through Steam")
    steam = None if applied else steam_elsewhere(cfg)   # an apply's build said so already
    if steam:
        log(f"warning: {steam_elsewhere_text(steam, cfg.game_dir)}")
    if with_remaps:
        log("some of your remaps only work with the old key remapper, which is deprecated (what the game reads "
            "itself, such as movement and the camera, or every remap without the script loader): start the game "
            "with Play with key remaps.bat for them")
    # The manifest goes back too, so the studio's drawer can say what went in (and keep its warnings in view).
    return {"applied": applied, "remaps": with_remaps, "manifest": manifest}


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
