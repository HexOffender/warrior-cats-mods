"""Local web studio: `python wcmods.py studio` serves studio/ and a JSON API on 127.0.0.1.

Every /api request must carry the per-run token (X-WC-Token), and the Host header must be
this machine, so other websites can't drive the mod manager from your browser.
"""
import datetime
import json
import mimetypes
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import (animations, bridge, catcolours, colors, controls, eyeatlas, guide, menupages, menusettings, models, mods,
               modzip, names, onboarding, packs, palettes, pipeline, recolor, scriptlog, story, ue4ss)
from .formats import cooked, csvdata, png, save, texture
from .exe import gamebuild
from .bridge import Bridge, BridgeError
from .colors import hex_from_linear
from .config import game_running
from .gamefiles import NONASSET, Unreadable
from .formats.savejson import SaveDoc
from .sdk import BuildContext
from .sections import scripts
from .sections.files import classify

NO_GAME = "Clan Mod Studio hasn't found the game yet: Get set up, on the Mods page, asks where it is"
# What a saved file gets instead of a check while the game's files can't be read (check_file).
CHECK_LATER = "It will be checked when you apply, because the game's files aren't readable now"
# How the page says pipeline.InstallBlocked (the command line says "not installing because some mods didn't build").
BLOCKED = "Nothing went in the game, because some mods couldn't be made ready"
DEFAULT_PORT = 8765
LAST_APPLY = "last-apply.log"   # in your files' folder: what the last Apply, Play or check logged
STUDIO_LOG = "studio.log"       # there too: the details behind "Something went wrong"
STUDIO_LOG_MAX = 1024 ** 2      # studio.log's size before it starts again (the one before is kept as studio.log.1)

MOD_FILES = ("palette.json", "controls.json", "mouselook.json", "data.json", "items.json", "animations.json",
             "names.json", "cats.json", "save.json", "settings.json") + story.FILES
PICTURES = "pictures"        # a mod's own pictures (an item's icon, an accessory's look), added on the Items page
MODELS = "models"            # a mod's own models (an accessory's shape), added on the Items page
ANIMATIONS = "animations"    # a mod's own animations (glTF), added on the Animations page
MAX_PICTURE = 8 * 1024 ** 2
ITEM_ROOT = "Gameplay.Inventory."
MAX_UPLOAD = modzip.MAX_BYTES   # a downloaded mod's .zip
# The side bar: "play" is installing and managing mods, "make" the pages for making your own.
BUILTIN_SECTIONS = [
    {"id": "mods", "title": "Mods", "module": "/studio/sections/mods.js", "group": "play"},
    {"id": "packs", "title": "Mod packs", "module": "/studio/sections/packs.js", "group": "play"},
    {"id": "settings", "title": "Settings and repair", "module": "/studio/sections/settings.js", "group": "play"},
    {"id": "palettes", "title": "Palettes", "module": "/studio/sections/palettes.js", "group": "make"},
    {"id": "cat", "title": "Your cat", "module": "/studio/sections/cat.js", "group": "make"},
    {"id": "controls", "title": "Controls", "module": "/studio/sections/controls.js", "group": "make"},
    {"id": "names", "title": "Names", "module": "/studio/sections/names.js", "group": "make"},
    {"id": "items", "title": "Items", "module": "/studio/sections/items.js", "group": "make"},
    {"id": "animations", "title": "Animations", "module": "/studio/sections/animations.js", "group": "make"},
    {"id": "npcs", "title": "Characters", "module": "/studio/sections/npcs.js", "group": "make"},
    {"id": "quests", "title": "Questlines", "module": "/studio/sections/quests.js", "group": "make"},
    {"id": "data", "title": "Game data", "module": "/studio/sections/data.js", "group": "make"},
    {"id": "save", "title": "Save", "module": "/studio/sections/save.js", "group": "make"},
]
# Pages for code mods: only with "allow_code_mods" (the console runs Lua in the game), last in the side bar,
# under Advanced.
CODE_SECTIONS = [
    {"id": "console", "title": "Try Lua in the game", "module": "/studio/sections/console.js", "group": "advanced"},
]

# Whether the game can hear the studio (its bridge, wcmods/bridge.py), in one sentence per state: the Console's
# status strip, and what a request it can't send says.
BRIDGE_SAID = {
    "listening": "The game is running and listening ({where})",
    "not-answering": "The game is running but not answering: it may be loading, or held still behind another window",
    "no-bridge": "The game is running without the studio's connection to it: close the game, press Apply to game, "
                 "then Play",
    "closed": "The game is closed: press Play",
}
# A request that went but didn't come back (BridgeError's kinds besides "down").
BRIDGE_FAILED = {
    "busy": "Something else is talking to the game this moment (another studio page, or a command); try again in a "
            "moment",
    "withdrawn": "The game didn't answer within {timeout:g} seconds (it may be loading, or held still behind another "
                 "window), so the line was taken back: it won't run later",
    "running": "The game took the line but hasn't finished it after {timeout:g} seconds; it's still running it",
}


def bridge_state(cfg, status=None, running=None):
    """How the game and its bridge stand: (state, sentence), a state of BRIDGE_SAID's. `status` is
    Bridge.status() (read here when None); `running` whether the game's process runs (asked when None)."""
    st = Bridge(cfg).status() if status is None else status
    if st and st.get("alive"):
        return "listening", BRIDGE_SAID["listening"].format(where=bridge.where(st))
    if not (game_running() if running is None else running):
        return "closed", BRIDGE_SAID["closed"]
    state = "not-answering" if bridge_installed(cfg) else "no-bridge"
    return state, BRIDGE_SAID[state]


def bridge_installed(cfg):
    """Whether the last install put the bridge in the game (wcmods.json read afresh: an install from the command
    line counts at once)."""
    try:
        data = cfg.peek()
    except (OSError, ValueError):
        data = cfg.data
    return bridge.NAME in (data.get("installed_ue4ss") or [])


def bridge_failed(cfg, e, timeout=15):
    """A BridgeError as the sentence the page shows."""
    if e.kind in BRIDGE_FAILED:
        return BRIDGE_FAILED[e.kind].format(timeout=timeout)
    state, said = bridge_state(cfg)
    return BRIDGE_SAID["not-answering"] if state == "listening" else said


class Download:
    """An API answer that's a file to save (a mod as a .zip), not JSON."""

    def __init__(self, data, filename, ctype="application/zip"):
        self.data, self.filename, self.ctype = data, filename, ctype


def field(body, key, kind=str, what="text"):
    """body[key], which the request has to send as `kind`; a sentence (ValueError, answered 400) when it's
    missing or something else, instead of the bare key name a KeyError would give the page."""
    if key not in body:
        raise ValueError(f'the request needs "{key}"')
    value = body[key]
    if not isinstance(value, kind) or isinstance(value, bool) and kind is not bool:
        raise ValueError(f'"{key}" should be {what}')
    return value


# What PATCH /mods/<id> may change, and what each should be.
MOD_FIELDS = {"enabled": (bool, "true or false"), "priority": (int, "a whole number"), "name": (str, "text"),
              "description": (str, "text"), "version": (str, "text"), "author": (str, "text")}


def code_stamp():
    """The newest change to wcmods' own Python code. The studio runs the code it started with, so once
    this moves on (wcmods was updated while it ran), building with it would install stale scripts."""
    here = os.path.dirname(os.path.abspath(__file__))
    newest = 0.0
    for folder, _, names in os.walk(here):
        for n in names:
            if n.endswith((".py", ".lua")):
                newest = max(newest, os.path.getmtime(os.path.join(folder, n)))
    return newest


class _NoGame:
    """The game's files while there's no game folder: anything read from them is Unreadable, as a pak that
    isn't there would be, so check_file says the check waits for Apply."""

    def __getattr__(self, name):
        raise Unreadable("the game's files aren't readable now")


def owner(file):
    """The built-in build section that reads a mod file (sections/__init__.py), or None for a file no built-in
    section owns (a mod's own studio_files)."""
    from .sections import BUILTIN
    for cls in BUILTIN:
        if file in cls.files:
            return cls()
    return None


def plain_summary(manifest, checked=False):
    """What a build did, in a sentence or two, for the top of the log: which mods went in, by name, how many
    warnings; or which mod couldn't go in and why. `checked`: the build only checked the mods (Check my mods),
    so nothing went in the game. The page shows it as task_summary gives it."""
    names = manifest.get("names") or {}
    bad = [(names.get(mod, mod) if mod else rep.get("title", "a part of the build"), text)
           for rep in manifest.get("sections", {}).values() for mod, text in pipeline.section_problems(rep)]
    if bad:
        who, why = bad[0]
        more = f" ({len(bad) - 1} more problem{'s' if len(bad) > 2 else ''} in the log)" if len(bad) > 1 else ""
        return f"{who} can't go in the game yet: {why}{more}" if checked else f"Couldn't put {who} in: {why}{more}"
    ids = manifest.get("mods", [])
    warnings = len(manifest.get("warnings", []))
    listed = ", ".join(names.get(i, i) for i in ids)
    if checked:
        said = (f"Checked {len(ids)} mod{'s' if len(ids) != 1 else ''}: {listed}. Apply to game puts "
                f"{'them' if len(ids) != 1 else 'it'} in." if ids else "Checked: no mods are on.")
    else:
        said = (f"Put {len(ids)} mod{'s' if len(ids) != 1 else ''} in the game: {listed}."
                if ids else "Put the mod menu in the game, with no mods on.")
    # A script that goes in but won't load (its Lua isn't whole) is said by name: the game would only show it as
    # nothing happening.
    for mod, note in (manifest.get("notes", {}).get("scripts") or {}).items():
        if isinstance(note, dict) and note.get("problems"):
            said += f" {names.get(mod, mod)}: {note['problems'][0]}."
    return said + (f" {warnings} warning{'s' if warnings != 1 else ''}." if warnings else "")


def manifest_of(result):
    """The build's manifest in a task's result: the result itself (Check mods, Apply), or its "manifest" (Play,
    which has one only when it applied first); else None."""
    if isinstance(result, dict) and "sections" in result:
        return result
    if isinstance(result, dict) and isinstance(result.get("manifest"), dict):
        return result["manifest"]
    return None


def task_summary(title, result, lines, checked=False):
    """The sentence at the top of a task's log (the page's drawer, last-apply.log): what its build did
    (plain_summary), or for a Play with nothing to apply, that the game started and how many warnings its log
    has. None for a task with neither (the page words those itself)."""
    manifest = manifest_of(result)
    if manifest:
        return plain_summary(manifest, checked)
    if title == "Play":
        n = sum(1 for line in lines if line.startswith("warning: "))
        return "Started the game; nothing needed applying first." + (f" {n} warning{'s' if n != 1 else ''}." if n else "")
    return None


class Studio:
    def __init__(self, ctx):
        self.ctx = ctx
        self.code_stamp = code_stamp()
        self.root = ctx.root
        self.static = os.path.join(ctx.root, "studio")
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()
        self.log_lock = threading.Lock()   # studio.log: one handler thread writing (or starting it again) at a time
        self.progress = {"id": None, "title": None, "lines": [], "running": False}   # what the task under the lock has logged
        self.server, self.port = None, None   # set by serve(): the server this studio answers from
        self.restarting = False
        self.dry_restart = bool(os.environ.get("WCMODS_NO_RESTART"))   # the tests: answer, but don't restart
        self.cpp_building, self.cpp_log, self.cpp_result = None, [], None   # a C++ mod being built from its card
        self.cpp_tools = None   # cppmods.status() as it was when that build started, for the page's polls
        self._eyes = None
        self._names = None   # the game's name tables, read once
        self._items = None   # the game's items, read once
        self._icons = {}     # (item tag or texture, tint) -> PNG bytes
        self._skin = None    # the cat's skin, to say how far a model reaches from it
        self._views = {}     # accessory -> its shape and the cat's, for the Items page's drawing
        self._pictures = {}  # texture -> its full-size PNG, to paint over (the last few)
        self._anims = None   # the game's skeletons, read once for the Animations page
        self._sequences = {}  # kind -> the game's sequences an animation can replace, read once

    # ---------- helpers ----------
    def mods(self):
        return mods.discover(self.ctx.mods_root)

    def mod(self, mod_id):
        for m in self.mods():
            if m.id == mod_id:
                return m
        raise LookupError(f"no mod named {mod_id}")

    def save_text(self):
        path = os.path.join(self.ctx.cfg.save_dir, save.SAV_NAME)
        if not os.path.isfile(path):
            raise LookupError("no save yet; start the game once")
        return save.SaveGame.load(path).json_text, os.path.getmtime(path)

    def build(self):
        """The installed game's build, or None (no game found, or Steam doesn't say)."""
        if not self.ctx.cfg.game_dir:
            return None
        try:
            return gamebuild.current(self.ctx.cfg)["build"]
        except OSError:
            return None

    def code_changed(self):
        return code_stamp() > self.code_stamp

    def need_current_code(self):
        if self.code_changed():
            raise RuntimeError("Clan Mod Studio was updated while it was open, and this one still runs the old "
                               "version. Press Restart the studio (at the top of the page), then apply.")

    def check_file(self, mod, file):
        """What would keep a file the studio just saved out of the game: the first part of the check Apply makes
        (the build section that owns the file reads it, collect()), on this mod alone, as sentences. [] when
        it's fine. What Apply checks with every mod together (a table's rows and columns, models and pictures,
        two mods changing the same thing) is still said only then. While the
        game's files can't be read (no game folder yet, Steam updating it), one line says the check waits for
        Apply, since some files are checked against the game's tables."""
        sec = owner(file)
        if sec is None or not sec.claims(mod):
            return []
        try:
            # Most files are checked without the game's files; one that needs them (data.json's table names)
            # gets CHECK_LATER while they can't be read.
            game = self.ctx.game if self.ctx.cfg.game_dir else _NoGame()
            ctx = BuildContext(self.ctx.cfg, game, os.path.join(tempfile.gettempdir(), "wcmods-studio"), lambda m: None)
            ctx.mods = [m for m in self.mods() if m.enabled]
            sec.collect(mod, ctx)
        except KeyError as e:
            # A key a file lacks (str is the key in quotes), or a game file the reader hasn't got.
            what = e.args[0] if len(e.args) == 1 else str(e)
            return [f"{file}: {what} is missing" if isinstance(what, str) and not str(what).startswith("game file")
                    else CHECK_LATER]
        except ValueError as e:
            return [str(e)]
        except (OSError, Unreadable):   # the game's pak isn't there, or won't open
            return [CHECK_LATER]
        except (AttributeError, TypeError):   # a list where an object goes, a number where text does: not a Python name
            return [f"{file} isn't shaped the way the page writes it (docs/formats.md shows how it's laid out)"]
        except Exception as e:   # noqa: BLE001 - said, not hidden, and never as a Python name
            said = str(e).strip()
            return [f"{file} couldn't be checked{': ' + said if said else ''}"]
        return []

    def restart(self):
        """Start a fresh Clan Mod Studio (in its own window) and stop this one, for the page's Restart the
        studio button after wcmods was updated under it. The answer goes out first; then the server stops, and
        serve() starts the new one (start_again) and returns, so the launcher's window closes without a pause."""
        if not self.server:
            raise RuntimeError("This studio isn't running from a window of its own, so it can't restart itself: "
                               "close it and open Clan Mod Studio again.")
        how = restart_command(self.root, self.port)[0]
        if not self.restarting:
            self.restarting = True
            if not self.dry_restart:
                threading.Thread(target=self._stop_for_restart, daemon=True).start()
        return {"restarting": True, "how": how, "port": self.port}

    def _stop_for_restart(self):
        time.sleep(0.5)   # the answer to the page goes out first
        self.server.shutdown()

    def log_error(self, where, e):
        """The details of something that went wrong, in the console window and in studio.log (your files'
        folder), for whoever helps; the page gets a sentence."""
        text = f"{datetime.datetime.now().isoformat(timespec='seconds')} {where}\n" + \
            "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print(text, file=sys.stderr)
        try:
            os.makedirs(self.ctx.cfg.data_dir, exist_ok=True)
            path = os.path.join(self.ctx.cfg.data_dir, STUDIO_LOG)
            with self.log_lock:
                # Kept small: past STUDIO_LOG_MAX it starts again, with the one before kept as studio.log.1.
                if os.path.isfile(path) and os.path.getsize(path) > STUDIO_LOG_MAX:
                    os.replace(path, path + ".1")
                with open(path, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
        except OSError:
            pass

    # ---------- API ----------
    # ---- C++ mods: what's ready, and building one from its card (a thread; the page polls /api/cpp) ----
    def cpp_status(self):
        from . import cppmods
        with self.lock:
            building, log, result, st = self.cpp_building, list(self.cpp_log[-40:]), self.cpp_result, self.cpp_tools
        if not building or not st:
            # Finding the tools runs vswhere and git: not on every poll of a build that's under way.
            st = cppmods.status(self.ctx.root, self.ctx.cfg)
            with self.lock:
                self.cpp_tools = st
        return {"tools": {k: bool(v) for k, v in st["tools"].items()}, "problems": st["problems"], "source": st["source"],
                "game": st["game"], "matches": st["matches"], "building": building, "log": log, "result": result}

    def cpp_build(self, mod_id):
        from . import cppmods
        if not self.ctx.cfg.data.get("allow_code_mods"):
            raise PermissionError("building C++ mods runs their build files; allow mods that run code first (Options)")
        which = cppmods.cpp_mods(mods.discover(self.ctx.mods_root), [mod_id], root=self.ctx.root)
        with self.lock:
            if self.cpp_building:
                raise RuntimeError(f"already building {self.cpp_building}")
            self.cpp_building, self.cpp_log, self.cpp_result = mod_id, [], None

        def run():
            try:
                cppmods.build(self.ctx.root, self.ctx.cfg, which, log=lambda m: self.cpp_log.append(m))
                outcome = {"ok": True, "message": f"built {mod_id}; Play or Apply to game puts it in"}
            except Exception as e:   # noqa: BLE001 - the card shows whatever went wrong
                outcome = {"ok": False, "message": str(e)}
            with self.lock:
                self.cpp_building, self.cpp_result = None, outcome

        threading.Thread(target=run, daemon=True).start()
        return {"started": mod_id}

    def api(self, method, parts, body, query=None, upload=None):
        """One API call: `parts` is the path after /api/, `body` the JSON sent, `query` the URL's
        parameters, `upload` the path of a file sent as the body (mods/add)."""
        cfg = self.ctx.cfg
        if method == "POST" and parts in (["build"], ["install"], ["uninstall"], ["palettes", "apply"], ["play"]):
            if not cfg.game_dir:
                raise ValueError(NO_GAME)
            self.need_current_code()
        if parts == ["info"]:
            sections = list(BUILTIN_SECTIONS)
            if cfg.data.get("allow_code_mods"):
                sections += CODE_SECTIONS
                for m in self.mods():
                    if m.enabled and os.path.isfile(os.path.join(m.folder, "studio", "section.js")):
                        sections.append({"id": f"mod-{m.id}", "title": m.meta.get("studio_title", m.name),
                                         "module": f"/mods/{m.id}/studio/section.js", "from_mod": m.id,
                                         "group": "play"})
            return {"game_dir": cfg.game_dir, "save_found": os.path.isfile(os.path.join(cfg.save_dir, save.SAV_NAME)),
                    "ue4ss": bool(cfg.ue4ss_mods_dir), "game_running": game_running(),
                    "installed": cfg.data.get("installed"), "install_outdated": pipeline.install_outdated(cfg),
                    "code_changed": self.code_changed(), "restartable": bool(self.server),
                    "warning": cfg.warning, "data_dir": cfg.data_dir,
                    "allow_code_mods": bool(cfg.data.get("allow_code_mods")),
                    "game_build": gamebuild.current(cfg), "sections": sections}
        if parts == ["progress"] and method == "GET":
            # What the build, install or Play under the lock has logged so far (the page polls while one runs).
            p = self.progress
            return {"id": p["id"], "title": p["title"], "lines": list(p["lines"]), "running": p["running"]}
        if parts == ["last-apply"] and method == "GET":
            path = os.path.join(cfg.data_dir, LAST_APPLY)
            if not os.path.isfile(path):
                raise LookupError("Nothing has been applied from this studio yet")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            head, _, log = text.partition("\n\n")   # the task and when, its summary and warnings; then the log
            lines = head.split("\n")
            title, _, when = lines[0].partition(" · ")
            return {"title": title, "when": when, "summary": lines[1:], "log": log.strip("\n")}
        if parts == ["restart"] and method == "POST":
            return self.restart()
        if len(parts) == 2 and parts[0] == "help" and method == "GET":
            # A page of the guide (docs/guide/<page>.md) for the help panel: only the tags guide.TAGS.
            page = parts[1] if parts[1] not in ("", "index") else guide.INDEX
            text = guide.read(self.root, page)
            return {"page": page, "title": guide.title(text) or page, "html": guide.render(text),
                    "pages": guide.pages(self.root)}
        if parts == ["game", "update"] and method == "GET":
            # How wcmods stands on a build it wasn't checked on (worked out once per game update, ~a minute).
            with self.lock:   # an install may be working it out too: once, not twice at the same time
                fit = gamebuild.layout(cfg)
            return {**fit, "moved": [gamebuild.describe(k) for k in fit["moved"]],
                    "lost": [gamebuild.describe(k) for k in fit["lost"]], "offsets": None}
        if parts == ["setup"] and method == "GET":
            # "Get set up" on the Mods page (wcmods/onboarding.py), and a mod dropped on the launcher.
            waiting = onboarding.inbox()
            return {**onboarding.status(cfg, self.ctx.backups), "inbox": os.path.basename(waiting) if waiting else None}
        if parts == ["setup", "game"] and method == "POST":
            return {"dir": onboarding.set_game_dir(cfg, body.get("dir"))}
        if parts == ["setup", "backup"] and method == "POST":
            with self.lock:   # two pages asking at once make one copy
                return {"name": onboarding.first_backup(cfg, self.ctx.backups)}
        if parts == ["setup", "loader"] and method == "POST":
            # UE4SS: downloaded from GitHub, or from a .zip sent as the body.
            return self.run(lambda log: onboarding.install_loader(cfg, upload, log), "Install the script loader")
        if parts == ["setup", "pages"] and method == "POST":
            # The mod menu's pages (wcmods/menupages.py): downloaded from GitHub, from a .zip sent as the body,
            # or skipped for now.
            if body.get("skip"):
                with self.lock:
                    return {"result": onboarding.skip_pages(cfg)}
            return self.run(lambda log: onboarding.add_pages(cfg, upload, log), "Add the menu's pages")
        if parts == ["play"] and method == "POST":
            self.need_current_code()
            return self.run(lambda log: onboarding.play(self.ctx, log, force=bool(body.get("force"))), "Play", keep=True,
                            task=body.get("task"))
        if parts == ["mods", "inbox"] and method == "GET":
            waiting = onboarding.inbox()
            if not waiting:
                return {"mods": [], "name": None}
            try:
                found = modzip.inspect_folder(waiting, self.ctx.mods_root) if os.path.isdir(waiting) \
                    else modzip.inspect(waiting, self.ctx.mods_root)
            except (ValueError, OSError, zipfile.BadZipFile):
                onboarding.clear_inbox()   # said once: it isn't offered again
                raise
            return {"mods": found, "name": os.path.basename(waiting), "code_allowed": bool(cfg.data.get("allow_code_mods"))}
        if parts == ["mods", "inbox", "add"] and method == "POST":
            waiting = onboarding.inbox()
            if not waiting:
                raise LookupError("that mod isn't waiting any more; drop it on Clan Mod Studio again")
            enable = bool(body.get("enable", True))
            with self.lock:
                if os.path.isdir(waiting):
                    added = modzip.add_folder(waiting, self.ctx.mods_root, self.ctx.backups, ids=body.get("ids") or None,
                                              enable=enable)
                else:
                    added = modzip.add_zip(waiting, self.ctx.mods_root, self.ctx.backups, ids=body.get("ids") or None,
                                           enable=enable, name=os.path.basename(waiting))
            onboarding.clear_inbox()
            return {"added": added}
        if parts == ["mods", "inbox", "clear"] and method == "POST":
            onboarding.clear_inbox()
            return {"cleared": True}
        if parts == ["ingame"]:
            # The game's console, the mod menu's key, button and size, and Menu pages' cheats at start
            # (wcmods/menusettings.py).
            if method == "PATCH":
                # set_options reloads and saves wcmods.json: not in the middle of an install, which would
                # lose what the install has noted but not saved yet.
                with self.lock:
                    return menusettings.set_options(cfg, console=body.get("console"), key=body.get("key"),
                                                    size=body.get("size"), pad=body.get("pad"), cheats=body.get("cheats"))
            return menusettings.options(cfg)
        if parts == ["game", "bridge"] and method == "GET":
            # Whether the game runs with the bridge (wcmods/bridge.py), for the Console's status strip: the
            # bridge's own status, whether the game's process runs, whether the last install put the bridge in,
            # and the state that makes in a sentence (bridge_state).
            st = Bridge(cfg).status()
            running = game_running()
            state, said = bridge_state(cfg, st or {}, running)
            return {**(st or {"alive": False, "never": True}), "game_running": running,
                    "bridge_installed": bridge_installed(cfg), "state": state, "said": said}
        if parts == ["cpp"] and method == "GET":
            return self.cpp_status()
        if len(parts) == 3 and parts[:2] == ["cpp", "build"] and method == "POST":
            return self.cpp_build(parts[2])
        if parts in (["game", "lua"], ["game", "inspect"]) and method == "POST":
            if not cfg.data.get("allow_code_mods"):
                raise PermissionError("the Console runs code in the game: allow mods that run code first (Options, on "
                                      "the Settings and repair page)")
            code = body.get("code", "") if parts[1] == "lua" else bridge.inspect_code(body.get("expr", ""), bool(body.get("all")))
            if not str(code).strip():
                raise ValueError("type a line of Lua to run, e.g. Game.cat():name()")
            timeout = float(body.get("timeout", 15))
            try:
                return Bridge(cfg).run(code, timeout=timeout)
            except BridgeError as e:
                raise RuntimeError(bridge_failed(cfg, e, timeout)) from None
        if parts == ["mods"] and method == "GET":
            found = self.mods()
            old = gamebuild.outdated(cfg, found)
            held = gamebuild.held_back(cfg, found)
            unmet = mods.unmet(found, held)
            titles = {m.id: m.name for m in found}
            for i, why in held.items():   # needs a mod made for an older version: left out with it
                if i not in old:
                    unmet.setdefault(i, []).append(f"left out: it {why}")
            for m in found:   # a mod.json or palette.json that can't be read: said on the card, never a blank page
                for problem in (m.problem, mods.palette_problem(m)):
                    if problem:
                        unmet.setdefault(m.id, []).append(problem)
            # Script mods: two that would go in as one, what's wrong with a script's files now (before any Apply),
            # and how its script did when the game last started (UE4SS.log, scriptlog.py).
            for i, said in scripts.clashes(found).items():
                unmet.setdefault(i, []).append(said)
            ran = scriptlog.report(cfg, found)["mods"]
            return [{**m.to_dict(), "problems": unmet.get(m.id, []),
                     "needed_by": [titles[i] for i in mods.needing(found, m.id)],
                     "requires_names": [titles.get(i, i) for i in m.requires if i != mods.MENU_ID],
                     "game_builds": gamebuild.made_for(m), "outdated": old.get(m.id),
                     "menu_pages": m.id == menupages.ID, "script_problems": scripts.problems(m),
                     "script_run": ({"state": ran[m.id]["state"], "said": ran[m.id]["said"]}
                                    if m.id in ran and ran[m.id]["state"] else None)} for m in found]
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "log" and method == "GET":
            # What a script mod's script said when the game last started (UE4SS.log): the card's More.
            m = self.mod(parts[1])
            rep = scriptlog.report(cfg, [m], among=self.mods())   # (another mod may have its name)
            if m.id not in rep["mods"]:
                raise LookupError(f"{m.name} has no in-game script, so the game's log says nothing about it")
            return {**rep["mods"][m.id], "log": rep["log"], "session": rep["session"],
                    "run_since_apply": rep["run_since_apply"]}
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "allow-outdated" and method == "POST":
            # Use a mod made for an older version of the game anyway, on this build only (the page warns first).
            build = gamebuild.current(cfg)["build"]
            if build is None:
                raise RuntimeError("couldn't tell which build of the game is installed")
            self.mod(parts[1])
            with self.lock:
                gamebuild.allow(cfg, parts[1], build, on=bool(body.get("on", True)))
            return {"build": build, "allowed": bool(body.get("on", True))}
        if parts == ["changes"] and method == "GET":
            found = self.mods()
            p = pipeline.pending(cfg, found)
            titles = {m.id: m.name for m in found}
            return {**p, "names": {i: titles.get(i, i) for i in p["on"] + p["off"] + p["changed"]},
                    "game_running": game_running()}
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "switch" and method == "POST":
            # On: with the mods it requires. Off: refused while mods that are on need it, unless cascade.
            found = self.mods()
            titles = {m.id: m.name for m in found}
            changed, blocked = mods.switch(found, parts[1], bool(body.get("on")), cascade=bool(body.get("cascade")))
            return {"changed": [{"id": i, "name": titles.get(i, i), "on": on} for i, on in changed],
                    "blocked_by": [{"id": i, "name": titles.get(i, i)} for i in blocked]}
        if parts == ["mods", "add"] and method == "POST":
            # A downloaded .zip (the request's body): ?step=preview says what's in it, ?step=add adds it.
            if not upload:
                raise ValueError("send the .zip as the request's body")
            name = (query or {}).get("name") or "mod.zip"
            if (query or {}).get("step") != "add":
                return {"mods": modzip.inspect(upload, self.ctx.mods_root, name),
                        "code_allowed": bool(cfg.data.get("allow_code_mods"))}
            ids = [i for i in (query.get("ids") or "").split(",") if i] or None
            with self.lock:
                return {"added": modzip.add_zip(upload, self.ctx.mods_root, self.ctx.backups, ids=ids,
                                                enable=query.get("enable", "1") == "1", name=name)}
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "remove" and method == "POST":
            # As with switching it off: while mods that are on need it, nothing changes and they're
            # returned, unless cascade, which turns them off too.
            with self.lock:
                found = self.mods()
                m = self.mod(parts[1])
                titles = {x.id: x.name for x in found}
                need = mods.needing(found, m.id)
                if need and not body.get("cascade"):
                    return {"blocked_by": [{"id": i, "name": titles.get(i, i)} for i in need]}
                return {"moved_to": modzip.remove(m, self.ctx.backups, found, cascade=True),
                        "turned_off": [titles.get(i, i) for i in need], "blocked_by": []}
        if parts == ["mods", "removed"] and method == "GET":
            return modzip.removed(self.ctx.backups)
        if parts == ["mods", "restore"] and method == "POST":
            with self.lock:
                return {"restored": modzip.restore(self.ctx.backups, field(body, "name"), self.ctx.mods_root)}
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "zip" and method == "GET":
            found = self.mods()
            m = self.mod(parts[1])
            return Download(modzip.pack(m, found), modzip.zip_name(m))
        if parts == ["open"] and method == "POST":
            # The game's log (UE4SS.log) in the program that opens text files, for a script's What it said.
            if body.get("what") == "log":
                path = scriptlog.log_path(cfg)
                if not path or not os.path.isfile(path):
                    raise LookupError("There's no log yet: it's made when the game starts with the script loader")
                if not hasattr(os, "startfile"):
                    raise RuntimeError(f"open {path} yourself (this only works on Windows)")
                os.startfile(path)
                return {"opened": path}
            # Show a folder in Explorer: the mods folder, the folder with all your files, or one mod's.
            folder = ({"mods": self.ctx.mods_root, "data": cfg.data_dir}.get(body.get("what"))
                      or self.mod(body.get("id", "")).folder)
            if not hasattr(os, "startfile"):
                raise RuntimeError(f"open {folder} yourself (this only works on Windows)")
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
            return {"opened": folder}
        if parts == ["settings"]:
            # "Allow mods that run code" (wcmods.json "allow_code_mods"); the studio asks twice first.
            if method == "PATCH" and "allow_code_mods" in body:
                allow = field(body, "allow_code_mods", bool, "true or false")
                with self.lock:   # not in the middle of an install (see "menusettings")
                    cfg.reload()
                    cfg.data["allow_code_mods"] = allow
                    cfg.save()
            return {"allow_code_mods": bool(cfg.data.get("allow_code_mods")), "data_dir": cfg.data_dir}
        if parts == ["mods"] and method == "POST":
            fields = {k: field(body, k, *MOD_FIELDS[k]) for k in MOD_FIELDS if body.get(k) is not None}
            m = mods.create(self.ctx.mods_root, field(body, "id"), fields.get("name"), fields.get("description", ""),
                            enabled=fields.get("enabled", False), priority=fields.get("priority", 0),
                            game_build=self.build())
            return m.to_dict()
        if len(parts) == 2 and parts[0] == "mods" and method == "PATCH":
            m = self.mod(parts[1])
            m.update(**{k: field(body, k, *MOD_FIELDS[k]) for k in MOD_FIELDS if body.get(k) is not None})
            return m.to_dict()
        if len(parts) == 4 and parts[0] == "mods" and parts[2] == "file":
            m, name = self.mod(parts[1]), parts[3]
            # Mods can declare their own settings files for their studio page: "studio_files": ["x.json"]
            own = tuple(f for f in m.meta.get("studio_files", []) if isinstance(f, str) and f.endswith(".json")
                        and "/" not in f and "\\" not in f and not f.startswith("."))
            if name not in MOD_FILES + own:
                raise PermissionError(f"the studio only edits {', '.join(MOD_FILES + own)} in this mod")
            path = os.path.join(m.folder, name)
            if method == "GET":
                if not os.path.isfile(path):
                    return {"exists": False, "text": None}
                with open(path, encoding="utf-8-sig") as f:
                    return {"exists": True, "text": f.read()}
            if method == "PUT":
                text = field(body, "text")
                try:
                    json.loads(text)  # refuse to write broken JSON
                except ValueError as e:
                    raise ValueError(mods.file_problem(name, e)) from None
                noted = []
                with self.lock:   # two pages saving the same file at once: one after the other, never interleaved
                    with open(path, "w", encoding="utf-8", newline="\n") as f:
                        f.write(text if text.endswith("\n") else text + "\n")
                    # Cats and questlines come into the game with the Sandbox mode mod: turning this mod on turns
                    # that one on, and a shared .zip says it's needed. A mod.json that can't be read can't say so:
                    # the file is saved all the same, and the problem said with it.
                    if name in story.FILES and story.SANDBOX_ID not in m.requires:
                        try:
                            if m.problem:
                                raise ValueError(m.problem)
                            m.update(requires=m.requires + [story.SANDBOX_ID])
                        except ValueError as e:
                            noted.append("The mod can't note that it needs the Sandbox mode mod, and stays off, until "
                                         f"its mod.json is fixed: {m.problem or e}")
                # A file half made still saves; what would keep it out of the game is said now, not at Apply.
                return {"saved": name, "requires": m.requires, "problems": noted + self.check_file(m, name)}
            if method == "DELETE":
                if os.path.isfile(path):
                    os.remove(path)
                return {"deleted": name}
        if parts == ["palettes", "apply"] and method == "POST":
            ids = body.get("ids") or []
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                raise ValueError("ids should be a list of palette mod names")
            # Switching happens inside the lock too, so a second Apply can't change mods mid-build.
            if not body.get("install"):
                return self.run(lambda log: dict(zip(("on", "off"), mods.choose_palettes(self.mods(), ids))),
                                "Choose palettes", task=body.get("task"))
            return self.run(lambda log: pipeline.apply_palettes(
                cfg, self.ctx.mods_root, ids, self.ctx.build_dir, self.ctx.backups, log,
                force=bool(body.get("force")))[1], "Apply palettes", keep=True, task=body.get("task"))
        if parts == ["build"] and method == "POST":
            return self.run(lambda log: pipeline.build(cfg, self.mods(), self.ctx.build_dir, log), "Check mods",
                            task=body.get("task"), checked=True)
        if parts == ["install"] and method == "POST":
            def go(log):
                pipeline.build(cfg, self.mods(), self.ctx.build_dir, log)
                return pipeline.install(cfg, self.ctx.build_dir, self.ctx.backups, log, force=bool(body.get("force")))
            return self.run(go, "Apply to game", keep=True, task=body.get("task"))
        if parts == ["uninstall"] and method == "POST":
            return self.run(lambda log: {"removed": pipeline.uninstall(cfg, log)}, "Take mods out", keep=True,
                            task=body.get("task"))
        if parts == ["backups"]:
            return save.list_backups(self.ctx.backups)[::-1]
        if parts == ["backup"] and method == "POST":
            # Never an empty backup: it would count as the save being backed up (Get set up, and the first
            # safety copy, which only happens while there's none).
            if not os.path.isfile(os.path.join(cfg.save_dir, save.SAV_NAME)):
                raise ValueError("there's no save to back up yet; start the game once, and get into the forest")
            where, files = save.backup(cfg.save_dir, self.ctx.backups, "studio")
            return {"name": os.path.basename(where), "files": files}
        if parts == ["restore"] and method == "POST":
            if game_running():
                raise RuntimeError("close the game before restoring a save")
            name = field(body, "name")
            save.backup(cfg.save_dir, self.ctx.backups, "before-restore")
            return {"restored": save.restore(self.ctx.backups, name, cfg.save_dir)}
        if parts == ["game", "eyes"]:
            return self.eyes()
        if parts == ["game", "tables"]:
            rep = ue4ss.read_reports(cfg.win64_dir) if cfg.game_dir else None
            if rep and rep["tables"]:
                return {"tables": rep["tables"], "source": "game log"}
            path = os.path.join(self.root, "colour_tables.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8-sig") as f:
                    return {"tables": json.load(f), "source": "colour_tables.json"}
            return {"tables": None, "source": None}
        if parts == ["game", "bindings"]:
            text, mtime = self.save_text()
            return {"bindings": controls.read_bindings(text), "save_time": mtime}
        if parts == ["game", "data"]:
            tables = self.ctx.game.data_tables()
            return {"tables": tables, "kinds": {t: classify(NONASSET + t) for t in tables}}
        if len(parts) >= 3 and parts[:2] == ["game", "data"]:
            name = "/".join(parts[2:])
            table = csvdata.Table(self.ctx.game.read_text(NONASSET + name))
            return {"name": name, **table.as_dict()}
        if parts == ["save"]:
            text, mtime = self.save_text()
            doc = SaveDoc(text)
            return {"account": doc.account, "data": doc.data, "save_time": mtime}
        if parts == ["cat"] and method == "GET":
            return self.cat_info()
        if parts == ["cat", "options"] and method == "GET":
            return self.look_options()
        if parts == ["packs"] and method == "GET":
            return packs.describe(cfg, self.mods())
        if parts == ["packs"] and method == "POST":
            # Make a pack, or change one: {id, name, description, author, version, mods: [ids]}.
            pack_id = body.get("id")
            if not isinstance(body.get("mods") or [], list):
                raise ValueError('"mods" should be a list of the ids of the mods in the pack')
            with self.lock:
                if not pack_id:   # a new pack: never one that's there already
                    taken = {m.id for m in self.mods()}
                    base = pack_id = modzip.safe_id(body.get("name") or "pack")
                    n = 2
                    while pack_id in taken:
                        pack_id, n = f"{base}-{n}", n + 1
                p = packs.save(self.ctx.mods_root, self.mods(), pack_id, (body.get("name") or "").strip(), body.get("mods") or [],
                               description=(body.get("description") or "").strip(), author=(body.get("author") or "").strip(),
                               version=(body.get("version") or "").strip(), game_build=self.build())
            return p.to_dict()
        if len(parts) == 3 and parts[0] == "packs" and parts[2] == "play" and method == "POST":
            with self.lock:   # not while an install reads which mods are on
                return packs.play(cfg, self.mods(), parts[1])
        if parts == ["packs", "stop"] and method == "POST":
            with self.lock:
                return packs.stop(cfg, self.mods())
        if parts == ["game", "items"] and method == "GET":
            return self.game_items()
        if parts == ["game", "icon"] and method == "GET":
            # An item's icon (or a texture's) as a small PNG, recoloured with ?tint=#rrggbb, for the Items page.
            return Download(self.icon((query or {}).get("of", ""), (query or {}).get("tint")), "icon.png", "image/png")
        if parts == ["game", "where"] and method == "POST":
            # Where your cat stands in the game, for a cat or a quest's place (through the game bridge).
            if not cfg.data.get("allow_code_mods"):
                raise PermissionError("reading where your cat is goes through the game bridge, which runs code: allow "
                                      "mods that run code first (Options, on the Settings and repair page)")
            try:
                reply = Bridge(cfg).run(WHERE_LUA, timeout=10)
            except BridgeError as e:
                raise RuntimeError(bridge_failed(cfg, e, 10)) from None
            spot = (reply.get("result") or [None])[0]
            if not reply.get("ok") or not isinstance(spot, dict):
                raise RuntimeError(reply.get("error") or "your cat isn't in the world: go into the forest first")
            return spot
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "picture" and method == "POST":
            # A picture for the mod (an item's icon), sent as the body: kept in the mod's pictures/ folder.
            return self.add_picture(self.mod(parts[1]), (query or {}).get("name", ""), upload)
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "model" and method == "POST":
            # A model for an accessory or for a herb on the ground (?ground=1), OBJ or glTF, sent as the body:
            # kept in the mod's models/ folder.
            return self.add_model(self.mod(parts[1]), (query or {}).get("name", ""), (query or {}).get("file", ""), upload,
                                  on_cat=(query or {}).get("ground") != "1")
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "model-view" and method == "GET":
            # A model in the mod's folder, in the game's space, for the Items page's drawing of it on the cat
            # (or on the ground, ?ground=1).
            return self.model_view(self.mod(parts[1]), (query or {}).get("path", ""), on_cat=(query or {}).get("ground") != "1")
        if parts == ["game", "accessory"] and method == "GET":
            # An accessory's own shape and the cat it sits on, for the same drawing.
            return self.accessory_view((query or {}).get("of", ""))
        if parts == ["game", "cat-shape"] and method == "GET":
            # The cat alone, to stand beside a herb's model on the ground for its size.
            return {"cat": self.cat_view()}
        if parts == ["game", "model-kit"] and method == "GET":
            # An accessory and the cat as OBJ files, with its look, to make a model of your own on (models.py).
            name, look = _accessory_look((query or {}).get("of", ""))
            data, filename = models.start_kit(self.ctx.game, name, look)
            return Download(data, filename)
        if parts == ["game", "anim-kinds"] and method == "GET":
            # The cats and animals an animation can be for, for the Animations page.
            return {"kinds": [{"id": k, "label": v["label"], "examples": len(v["examples"])}
                              for k, v in animations.KINDS.items()]}
        if parts == ["game", "anim-sequences"] and method == "GET":
            # The game's sequences for a kind, for an animation to replace one: their names and paths, and
            # which are additive (those can't be replaced).
            return {"sequences": self.anim_sequences((query or {}).get("for", "cat"))}
        if parts == ["game", "anim-sequence"] and method == "GET":
            # One of them: where it is, how long it plays and how many keys it has (a replacement is fitted to them).
            q = query or {}
            return self.anim_sequence(q.get("for", "cat"), q.get("name", ""))
        if parts == ["game", "anim-kit"] and method == "GET":
            # A cat or an animal rigged to its skeleton as a .glb, to animate in Blender (animations.py).
            data, filename = animations.start_kit(self.ctx.game, (query or {}).get("for", "cat"))
            return Download(data, filename)
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "animation" and method == "POST":
            # A glTF animation, sent as the body: kept in the mod's animations/ folder once it reads.
            q = query or {}
            return self.add_animation(self.mod(parts[1]), q.get("name", ""), q.get("file", ""), q.get("for", "cat"), upload)
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "animation-info" and method == "GET":
            # What an animation file in the mod holds: its animations, and the game's bones it moves.
            q = query or {}
            return self.animation_info(self.mod(parts[1]), q.get("path", ""), q.get("for", "cat"))
        if parts == ["game", "texture"] and method == "GET":
            # One of the game's pictures at full size to paint over: an accessory's look, an item's icon.
            asset = self.texture_asset((query or {}).get("of", ""), (query or {}).get("what", "icon"))
            if asset not in self._pictures:          # a look takes seconds to decode: the last few kept
                if len(self._pictures) >= 4:
                    self._pictures.pop(next(iter(self._pictures)))
                w, h, rgba = texture.load(self.ctx.game, asset).image(0)
                self._pictures[asset] = png.write(w, h, rgba)
            return Download(self._pictures[asset], asset.split(".", 1)[0].rsplit("/", 1)[-1] + ".png", "image/png")
        if len(parts) == 4 and parts[0] == "mods" and parts[2] == "picture" and method == "GET":
            m = self.mod(parts[1])
            path = os.path.join(m.folder, PICTURES, os.path.basename(parts[3]))
            if not os.path.isfile(path):
                raise LookupError(f"{m.id} has no picture {parts[3]}")
            with open(path, "rb") as f:
                return Download(f.read(), os.path.basename(path), "image/png")
        if parts == ["names"] and method == "GET":
            return self.names_preview({})
        if parts == ["names", "preview"] and method == "POST":
            return self.names_preview(names.validate(body.get("spec") or {}))
        raise LookupError("unknown API route")

    def cat_info(self):
        """Your cat's colour slots, scars and look in the save, the other cats of the game being played with
        theirs (for cats.json's "cats"), the colours each slot has with the enabled palettes (the game's
        tables, recoloured slots, and new slots palettes add), what each scar place can be, and the look's
        parts with the highest each takes."""
        current, scars, looks, others = {}, {}, {}, []

        def read(raw):
            """(slots, scars, look) a cat's save text has; a field it leaves out is at its default, 0."""
            def num(field, cast=int):
                m = re.search(rf"(?<![A-Za-z0-9_]){field}=(-?\d+(?:\.\d+)?)", raw)
                return cast(m.group(1)) if m else cast(0)
            look = {part: num(fields[0]) for part, fields in catcolours.LOOK.items()}
            # A size the save leaves out is the game's default, not 0: unknown here.
            look["size"] = round(num(catcolours.SIZE[0], float), 3) if re.search(
                rf"(?<![A-Za-z0-9_]){catcolours.SIZE[0]}=", raw) else None
            return ({part: num(field) for part, field in catcolours.SLOTS.items()},
                    {part: num(field) for part, field in catcolours.SCARS.items()}, look)
        try:
            text, _ = self.save_text()
            doc = SaveDoc(text)
            cats = [c for c in names.cats_in_save(doc.data) if c["current"]]
            mine = [c for c in cats if c["player"]]
            if mine:
                current, scars, looks = read(doc.get(mine[0]["paths"][0]))
            # The cats' names as they show with the enabled names mods; without the game's name tables (no game
            # folder, a pak that won't read) the cats are named by their places.
            shown = lambda c: ""     # noqa: E731
            try:
                if self._names is None:
                    if not self.ctx.cfg.game_dir:   # not ctx.game, which ends the command line (SystemExit)
                        raise LookupError(NO_GAME)
                    self._names = names.GameNames(lambda path: self.ctx.game.read_text(BuildContext.data_path(path)))
                try:
                    spec = names.merge(names.mod_specs([m for m in self.mods() if m.enabled]))
                except ValueError:
                    spec = names.merge([])
                plan = names.Plan(self._names, spec)
                shown = lambda c: plan.display(c["ids"]) or plan.display(c["ids"], final=False)   # noqa: E731
            except Exception:       # noqa: BLE001 - the page still opens, with places for names
                pass
            called = {}
            for c in cats:
                if not c["player"] and shown(c):
                    called[shown(c).lower()] = called.get(shown(c).lower(), 0) + 1
            for c in cats:
                if c["player"]:
                    continue
                name, where = shown(c), names.place(c["paths"][0])
                slots_now, scars_now, look_now = read(doc.get(c["paths"][0]))
                # A name picks the cat while it's the only one called that; else its place does.
                others.append({"target": name if name and called[name.lower()] == 1 else where, "name": name or where,
                               "where": where, "role": c["ids"].get("Role", ""),
                               "current": {"slots": slots_now, "scars": scars_now, "look": look_now}})
        except LookupError:
            pass
        options = self.look_options()
        return {"current": current, "palette": options["palette"], "game_slots": options["game_slots"],
                "feral_slots": options["feral_slots"], "parts": catcolours.PARTS,
                "scars": {"current": scars, "types": catcolours.SCAR_TYPES},
                "look": {"current": looks, "parts": options["parts"], "size": list(catcolours.SIZE[1:])},
                "cats": others}

    def look_options(self):
        """What a cat's look can be, with no save needed: the colours each slot has with the enabled palettes
        (recoloured slots and new slots palettes add; the rest are the game's tables) and the look's parts
        with the highest each takes."""
        enabled = []
        for m in self.mods():
            path = os.path.join(m.folder, "palette.json")
            if m.enabled and os.path.isfile(path):
                try:
                    enabled.append(palettes.load(path))
                except ValueError:
                    continue
        merged = palettes.merge(enabled)
        slots = {part: {k: colors.hex_from_srgb(v) for k, v in merged.get(part, {}).items()}
                 for part in ("fur", "pattern", "marking")}
        return {"palette": slots, "game_slots": palettes.GAME_SLOTS, "feral_slots": list(catcolours.FERAL_SLOTS),
                "parts": {p: catcolours.LOOK_MAX.get(p, 9) for p in catcolours.LOOK}}

    def names_preview(self, spec):
        """The game's names, what a names.json (not yet saved) does to them, and the cats in the save."""
        if self._names is None:
            self._names = names.GameNames(lambda path: self.ctx.game.read_text(BuildContext.data_path(path)))
        plan = names.Plan(self._names, names.merge([spec]))
        cats, slot = [], None
        try:
            text, _ = self.save_text()
            doc = SaveDoc(text)
            cats, slot = names.cats_in_save(doc.data), names.current_slot(doc.data)
        except LookupError:
            pass
        ops = plan.plan_cats(cats)
        return {**self._names.summary(), "final": {"prefixes": [p["final"] for p in plan.prefixes],
                                                   "suffixes": [s["final"] for s in plan.suffixes],
                                                   "rogues": [r["final"] for r in plan.rogues]},
                "cats": names.cat_list(plan, cats, ops), "current_slot": slot,
                "renames": [{"from": a, "to": b} for a, b in plan.cat_renames],
                "warnings": plan.warnings, "changed_texts": _changed_texts(plan.edits.get(names.strings_path("EN"), {}))}

    def _reader(self):
        """A build context only for reading the game's tables (it never builds)."""
        return BuildContext(self.ctx.cfg, self.ctx.game, os.path.join(tempfile.gettempdir(), "wcmods-studio"))

    def game_items(self):
        """The game's items for the Items and Questlines pages: tag, kind, name, description, and for herbs
        what using them does; and the choices an item has (effects, badges, rarities, colours)."""
        if self._items is None:
            b = self._reader()
            use = {r["key"]: r for r in b.table("Consumables.csv")}
            recipes = {r["key"] for r in b.table("BarteringCost.csv")}

            def text(v):
                if isinstance(v, dict) and v.get("key"):
                    return b.text(v["key"])
                return v.get("text", "") if isinstance(v, dict) else ""

            from . import accessories
            from .sections.items import PICKUPS
            looks = accessories.read_variations(self.ctx.game.read(accessories.GUI_MANAGER))
            pickups = {p[len(PICKUPS):-len(".uasset")] for p in self.ctx.game.find(PICKUPS + "*.uasset")}
            items = []
            for _, v in b.cooked_table("DT_QuestObjectsInfo"):
                tag = v.get("itemTag") or ""
                name = text(v.get("Name"))
                if not tag.startswith(ITEM_ROOT) or tag.count(".") < 3 or not name:   # "None" accessories
                    continue
                kind = tag.split(".")[2]
                u = use.get(tag, {})
                item = {"tag": tag, "kind": {"Consumable": "consumable", "Materials": "material",
                                             "Cosmetic": "accessory"}.get(kind, kind.lower()),
                        "short": tag[len(ITEM_ROOT):] if kind == "Cosmetic" else tag.split(".", 3)[3],
                        "name": name, "description": text(v.get("Description")),
                        "effect": u.get("EffectOnUse"), "type": u.get("Type"), "recipe": tag in recipes,
                        "pickup": tag.rsplit(".", 1)[-1] in pickups}    # the game has a pickup of its own for it
                parts = tag.split(".")
                if kind == "Cosmetic" and len(parts) == 6 and parts[5].isdigit():
                    # An accessory's look: its slot, the accessory, which look, and the look's picture.
                    own = looks.get(parts[4], [])
                    n = int(parts[5])
                    item.update({"slot": parts[3], "accessory": parts[4], "look_number": n, "looks": len(own),
                                 "look": own[n - 1] if 0 < n <= len(own) else None})
                items.append(item)
            items.sort(key=lambda i: (i["kind"], i["name"].lower()))
            self._items = {"items": items,
                           "effects": sorted({r["EffectOnUse"] for r in use.values() if r.get("EffectOnUse")}),
                           "groups": list(cooked.ITEM_GROUP_ICON), "rarities": list(cooked.ITEM_RARITY),
                           "colors": list(cooked.ITEM_CATEGORY_COLOR)}
        return self._items

    def icon(self, of, tint=None):
        """An item's icon (by its tag) or a game texture (/Game/...) as a PNG of 128 pixels or so, maybe
        recoloured."""
        key = (of, tint)
        if key not in self._icons:
            asset = of
            if not of.startswith("/Game/"):
                row = next((v for _, v in self._reader().cooked_table("DT_QuestObjectsInfo") if v.get("itemTag") == of), None)
                if not row or not isinstance(row.get("Icon"), dict):
                    raise LookupError(f"the game has no item {of}")
                asset = f"{row['Icon']['package']}.{row['Icon']['asset']}"
            tex = texture.load(self.ctx.game, asset)
            mip = next((i for i, m in enumerate(tex.mips) if m[0] <= 128), len(tex.mips) - 1)
            w, h, rgba = tex.image(mip)
            if tint:
                spec = {"tint": tint}
                recolor.check(spec, "tint")
                rgba = recolor.apply(rgba, spec)
            if len(self._icons) > 300:
                self._icons.clear()
            self._icons[key] = png.write(w, h, rgba)
        return self._icons[key]

    def add_picture(self, mod, name, upload):
        """Keep a PNG sent from the Items page in the mod's pictures/ folder; returns its path in the mod."""
        if not upload:
            raise ValueError("send the picture as the request's body")
        if os.path.getsize(upload) > MAX_PICTURE:
            raise ValueError(f"that picture is over {MAX_PICTURE // 1024 ** 2} MB")
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", os.path.splitext(os.path.basename(name))[0]).strip("-")[:40] or "picture"
        with open(upload, "rb") as f:
            data = f.read()
        try:
            w, h, _ = png.read(data)
        except Exception:   # noqa: BLE001 - whatever is wrong with it, it isn't a PNG wcmods can use
            raise ValueError("that isn't a PNG picture (save it as .png first)") from None
        if not (16 <= w <= 4096 and 16 <= h <= 4096):
            raise ValueError(f"the picture is {w} x {h}; it should be 16 to 4096 pixels each way")
        folder = os.path.join(mod.folder, PICTURES)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, stem + ".png"), "wb") as f:
            f.write(data)
        return {"path": f"{PICTURES}/{stem}.png", "width": w, "height": h}

    def add_model(self, mod, name, filename, upload, on_cat=True):
        """Keep a model sent from the Items page in the mod's models/ folder, once it reads; returns its path
        in the mod, what it is (vertices, triangles, size) and, for one worn on the cat, how far it reaches
        from the cat."""
        if not upload:
            raise ValueError("send the model as the request's body")
        ext = os.path.splitext(filename)[1].lower()
        if ext not in models.FORMATS:
            raise ValueError(f"models are {', '.join(models.FORMATS)} files (Blender: File > Export > Wavefront "
                             "or glTF 2.0)")
        with open(upload, "rb") as f:
            data = f.read()
        model = models.read(filename, data)          # a .gltf whose data is in another file is refused here
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", os.path.splitext(os.path.basename(name or filename))[0]).strip("-")[:40] \
            or "model"
        folder = os.path.join(mod.folder, MODELS)
        os.makedirs(folder, exist_ok=True)
        # The last one stays: the saved items.json names it until the page is saved again.
        with open(os.path.join(folder, stem + ext), "wb") as f:
            f.write(data)
        out = {"path": f"{MODELS}/{stem}{ext}", **model.summary()}
        if on_cat:
            out["farthest_cm"] = round(self._skin_distance(model), 1)
        return out

    def _skeleton(self, kind):
        if kind not in animations.KINDS:
            raise ValueError(f"there's no animal {kind!r} (there are {', '.join(animations.KINDS)})")
        if self._anims is None:
            self._anims = animations.Game(self.ctx.game.read)
        return self._anims.skeleton(kind)

    def add_animation(self, mod, name, filename, kind, upload):
        """Keep a glTF animation sent from the Animations page in the mod's animations/ folder, once it reads
        and has an animation; returns its path in the mod and what it holds (animations.describe)."""
        if not upload:
            raise ValueError("send the animation as the request's body")
        ext = os.path.splitext(filename)[1].lower()
        if ext not in animations.FORMATS:
            raise ValueError("animations are glTF files: in Blender, File > Export > glTF 2.0, as glTF Binary (.glb)")
        with open(upload, "rb") as f:
            data = f.read()
        info = animations.describe(filename, data, kind, self._skeleton(kind))   # a .gltf with its data elsewhere is refused
        if not info["clips"]:
            raise ValueError("the file has no animation: in Blender, export with Animation on")
        if not info["matched"]:
            raise ValueError("none of the file's bones has the name of one of the game's: animate the start kit's armature")
        stem = (re.sub(r"[^A-Za-z0-9_-]+", "-", os.path.splitext(os.path.basename(name or filename))[0]).strip("-")[:40]
                or "animation")
        folder = os.path.join(mod.folder, ANIMATIONS)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, stem + ext), "wb") as f:
            f.write(data)
        return {"path": f"{ANIMATIONS}/{stem}{ext}", **info}

    def animation_info(self, mod, rel, kind):
        folder = os.path.realpath(mod.folder)
        path = os.path.realpath(os.path.join(folder, rel))
        if os.path.commonpath([folder, path]) != folder or not os.path.isfile(path):
            raise LookupError(f"{mod.id} has no animation {rel}")
        with open(path, "rb") as f:
            data = f.read()

        def sibling(name):
            p = os.path.realpath(os.path.join(os.path.dirname(path), name))
            if os.path.commonpath([folder, p]) == folder and os.path.isfile(p):
                with open(p, "rb") as f:
                    return f.read()
            return None
        return animations.describe(rel, data, kind, self._skeleton(kind), sibling)

    def anim_sequences(self, kind):
        """[{"name", "paths", "additive"}] for a kind's sequences, by name."""
        from .formats import anim, texture
        if kind not in animations.KINDS:
            raise ValueError(f"there's no animal {kind!r}")
        if kind not in self._sequences:
            out = []
            for name, paths in animations.game_sequences(self.ctx.game.io.files, kind).items():
                additive = False
                for path in paths:
                    try:
                        additive = additive or anim.AnimSequence(self.ctx.game.read(texture.content_path(path))).additive()
                    except (anim.FormatError, ValueError, KeyError):
                        pass        # not one wcmods reads: the install says so if it's chosen
                out.append({"name": name, "paths": paths, "additive": additive})
            self._sequences[kind] = sorted(out, key=lambda s: s["name"].lower())
        return self._sequences[kind]

    def anim_sequence(self, kind, name):
        """One of the game's sequences an animation can replace: {"path", "seconds", "keys", "root_motion"}."""
        from .formats import anim, texture
        if kind not in animations.KINDS:
            raise ValueError(f"there's no animal {kind!r}")
        try:
            path = animations.find_sequence(self.ctx.game.io.files, kind, name)
        except ValueError as e:
            raise LookupError(str(e)) from None
        try:
            seq = anim.AnimSequence(self.ctx.game.read(texture.content_path(path)))
            if seq.additive():
                raise ValueError(f"{path.rsplit('/', 1)[-1]} is an additive animation (its keys are added to another "
                                 "pose, not a pose of their own); replacing those isn't supported")
            return {"path": path, "seconds": round((seq.nkeys - 1) / seq.frame_rate(), 4), "keys": seq.nkeys,
                    "root_motion": seq.root_motion()}
        except anim.FormatError as e:
            raise ValueError(f"{name} isn't a sequence wcmods can read ({e})") from None

    def _skin_distance(self, model):
        """How far the model's farthest vertex is from the cat's skin (cm)."""
        if self._skin is None:
            self._skin = models.Body(self.ctx.game).skin(())
        step = max(1, len(model.positions) // 2000)    # a sample is enough to see a model in the wrong place
        return max(self._skin.nearest(p, 1)[0][0] for p in model.positions[::step])

    def model_view(self, mod, rel, on_cat=True):
        folder = os.path.realpath(mod.folder)
        path = os.path.realpath(os.path.join(folder, rel))
        if os.path.commonpath([folder, path]) != folder or not os.path.isfile(path):
            raise LookupError(f"{mod.id} has no model {rel}")
        with open(path, "rb") as f:
            data = f.read()

        def sibling(name):
            p = os.path.realpath(os.path.join(os.path.dirname(path), name))
            if os.path.commonpath([folder, p]) == folder and os.path.isfile(p):
                with open(p, "rb") as f:
                    return f.read()
            return None
        model = models.read(rel, data, sibling)
        out = {**_view(model.positions, model.triangles), **model.summary()}
        if on_cat:
            out["farthest_cm"] = round(self._skin_distance(model), 1)
        return out

    def accessory_view(self, of):
        """{"accessory": its shape, "cat": the cat's skin (a light LOD), "slot"} for one of the game's
        accessories (DogCollar, or a look's tag Neck.DogCollar.1)."""
        name, _ = _accessory_look(of)
        if name not in self._views:
            from . import accessories
            from .formats import skelmesh
            meshes = accessories.read_meshes(self.ctx.game.read(accessories.GUI_MANAGER))
            if name not in meshes:
                raise LookupError(f"the game has no accessory {name}")
            mesh = skelmesh.SkeletalMesh(self.ctx.game.read(texture.content_path(meshes[name].split(".", 1)[0])))
            geo = mesh.geometry(0)
            self._views[name] = {"accessory": _view(geo["positions"], geo["triangles"]), "cat": self.cat_view()}
        return self._views[name]

    def cat_view(self):
        """The cat's skin (a light LOD), for the Items page's drawings."""
        if "cat" not in self._views:
            from .formats import skelmesh
            body = skelmesh.SkeletalMesh(self.ctx.game.read(texture.content_path(models.BODY)))
            lod = min(2, len(body.lods) - 1)
            cat = body.geometry(lod)
            sec = body.lods[lod].sections[0]
            first = sec.base_index // 3
            self._views["cat"] = _view(cat["positions"], cat["triangles"][first:first + sec.triangles])
        return self._views["cat"]

    def texture_asset(self, of, what="icon"):
        """A texture's asset path: an item's icon (by its tag), an accessory's look (what="look", by the look's
        tag, Neck.DogCollar.1), or a texture by its own path (/Game/...)."""
        from . import accessories
        if of.startswith("/Game/"):
            return of
        short = of.split("Cosmetic.", 1)[-1]
        if what == "look":
            name, look = _accessory_look(short)
            lists = accessories.read_variations(self.ctx.game.read(accessories.GUI_MANAGER))
            if name not in lists or not 0 < look <= len(lists[name]):
                raise LookupError(f"the game has no look {of}")
            return lists[name][look - 1]
        row = next((v for _, v in self._reader().cooked_table("DT_QuestObjectsInfo") if v.get("itemTag") == of), None)
        if not row or not isinstance(row.get("Icon"), dict):
            raise LookupError(f"the game has no item {of}")
        return f"{row['Icon']['package']}.{row['Icon']['asset']}"

    def eyes(self):
        if self._eyes is None:
            atlas = eyeatlas.EyeAtlas(self.ctx.game.read(eyeatlas.PATH))
            self._eyes = {"labels": atlas.labels,
                          "rows": [[hex_from_linear(p)[1:] for p in atlas.row(r)] for r in range(atlas.height)]}
        return self._eyes

    def run(self, fn, title="Working", keep=False, task=None, checked=False):
        """A task under the studio's lock (a build, an install, Play), with what it logs kept for GET /progress
        while it runs, under the task's id (`task`, which the page sends): a page whose task is waiting for the
        lock sees whose log that is, never another task's as its own. While nothing else runs, /progress shows
        this task (with no lines yet) from the moment it's asked for, not the last one's log. With `keep`, the
        log goes to last-apply.log in your files' folder afterwards, headed by the task, when it ran and what it
        did in plain words, for the page's Last apply button. `checked`: the task only checks the mods (Check my
        mods), which the summary says. The answer has the log, the result and that summary."""
        mine = {"id": str(task or secrets.token_hex(6)), "title": title, "lines": [], "running": True}
        if not self.progress["running"]:
            self.progress = mine
        with self.lock:
            self.progress = mine
            lines = mine["lines"]
            try:
                result = fn(lines.append)
            except Exception as e:
                if keep:
                    self.keep_log(title, lines, None, e)
                raise
            finally:
                mine["running"] = False
        summary = task_summary(title, result, lines, checked)
        if keep:
            self.keep_log(title, lines, result, None, summary)
        return {"log": list(lines), "result": result, "summary": summary}

    def keep_log(self, title, lines, result, error, summary=None):
        """last-apply.log: "<title> · <when>", a plain summary, the warnings, then the log."""
        manifest = manifest_of(result)
        head = [f"{title} · {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"]
        if error is not None:
            head.append(error.describe("press Apply the rest anyway", "what they put in the game before is removed", BLOCKED)
                        if isinstance(error, pipeline.InstallBlocked) else f"Couldn't finish: {sentence(error) or error}")
        elif summary:
            head.append(summary)
            head += [f"warning: {w}" for w in (manifest or {}).get("warnings", [])]
        try:
            os.makedirs(self.ctx.cfg.data_dir, exist_ok=True)
            with open(os.path.join(self.ctx.cfg.data_dir, LAST_APPLY), "w", encoding="utf-8") as f:
                f.write("\n".join(head + [""] + list(lines)) + "\n")
        except OSError:
            pass


def _accessory_look(of):
    """("DogCollar", 1) from "DogCollar", "Neck.DogCollar.1" or "Gameplay.Inventory.Cosmetic.Neck.DogCollar.1"."""
    parts = of.split("Cosmetic.", 1)[-1].split(".")
    if len(parts) == 3 and parts[2].isdigit():
        return parts[1], int(parts[2])
    if len(parts) == 1 and parts[0]:
        return parts[0], 1
    raise ValueError(f"{of!r}: give an accessory's look, e.g. Neck.DogCollar.1")


VIEW_TRIANGLES = 30000   # a model drawn on the Items page: enough triangles to see its shape


def _view(positions, triangles):
    """A mesh for the Items page's drawing: flat lists, positions in cm to 0.01."""
    step = max(1, -(-len(triangles) // VIEW_TRIANGLES))
    return {"p": [round(c, 2) for p in positions for c in p], "t": [i for t in triangles[::step] for i in t]}


def _json_file(e):
    """The name of the file a JSONDecodeError came from, when json.load read it (its `fp` is in the traceback),
    else None."""
    tb, name = e.__traceback__, None
    while tb is not None:
        fp = tb.tb_frame.f_locals.get("fp") if tb.tb_frame.f_code.co_name == "load" else None
        if isinstance(getattr(fp, "name", None), str):
            name = os.path.basename(fp.name)
        tb = tb.tb_next
    return name


def sentence(e):
    """An exception the page gets as a sentence a non-technical person can act on; None for the ones the
    handler words itself (LookupError, ValueError, RuntimeError say their own)."""
    if isinstance(e, json.JSONDecodeError):
        return mods.file_problem(_json_file(e) or "A file the studio reads", e)
    if isinstance(e, FileNotFoundError):
        if not e.filename:   # raised with words of its own ("no backup named ..."): those say it
            return str(e) or "A file the studio needs is missing"
        return f"A file the studio needs is missing: {os.path.basename(str(e.filename))} (is Steam updating the game?)"
    if isinstance(e, PermissionError) and getattr(e, "filename", None):
        return f"{os.path.basename(str(e.filename))} is in use (is the game running?)"
    return None


# Where your cat is, through the game bridge: a place and level for a cat or a quest's step.
WHERE_LUA = """
local me = Game and Game.cat()
local l = me and me:location()
if not l then return nil end
local yaw = 0
pcall(function() yaw = Game.player():K2_GetActorRotation().Yaw end)
return { at = { math.floor(l.X), math.floor(l.Y), math.floor(l.Z) }, yaw = math.floor(yaw), level = Game.levelName() }
"""


def _changed_texts(edits):
    """How many English texts a set of csvdata edits changes or adds (row operations aren't keys)."""
    return sum(1 for k in edits if k not in ("+", "-")) + len(edits.get("+", []))


def make_handler(studio, port):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # keep the console quiet
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8", filename=None):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _handle(self, method):
            if self.headers.get("Host") not in allowed_hosts:
                return self._send(403, {"error": "wrong host"})
            url = urlparse(self.path)
            path = unquote(url.path)
            if path.startswith("/api/"):
                if self.headers.get("X-WC-Token") != studio.token:
                    return self._send(403, {"error": "missing or wrong studio token; reload the page"})
                body, upload = {}, None
                length = int(self.headers.get("Content-Length") or 0)
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if length and ctype in ("application/zip", "application/x-zip-compressed", "application/octet-stream"):
                    # A file (a downloaded mod): saved to a temp file as it arrives, never held whole.
                    if length > MAX_UPLOAD:
                        return self._send(413, {"error": f"that file is over {MAX_UPLOAD // 1024 ** 3} GB"})
                    fd, upload = tempfile.mkstemp(suffix=".zip", prefix="wcmods-upload-")
                    try:
                        with os.fdopen(fd, "wb") as f:
                            left = length
                            while left > 0:
                                chunk = self.rfile.read(min(left, 1024 * 1024))
                                if not chunk:
                                    break
                                f.write(chunk)
                                left -= len(chunk)
                    except BaseException:   # the page went away mid-upload: don't leave the part in %TEMP%
                        os.remove(upload)
                        raise
                elif length:
                    try:
                        body = json.loads(self.rfile.read(length) or b"{}")
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        return self._send(400, {"error": f"request body isn't valid JSON: {e}"})
                    if not isinstance(body, dict):
                        return self._send(400, {"error": "request body must be a JSON object"})
                parts = [p for p in path[5:].split("/") if p]
                query = {k: v[-1] for k, v in parse_qs(url.query).items()}
                where = f"{method} {path}"
                try:
                    result = studio.api(method, parts, body, query, upload)
                    if isinstance(result, Download):
                        return self._send(200, result.data, result.ctype, filename=result.filename)
                    return self._send(200, result)
                except zipfile.BadZipFile:
                    return self._send(400, {"error": "that isn't a .zip file (or it's damaged)"})
                except pipeline.InstallBlocked as e:
                    # The facts, worded for the page: its way past them is Apply the rest anyway.
                    return self._send(409, {"error": e.describe("press Apply the rest anyway",
                                                                "what they put in the game before is removed", BLOCKED),
                                            "blocked": [{"title": t, "mod": m, "text": x} for t, m, x in e.problems],
                                            "mods": e.mods()})
                except SystemExit as e:   # Ctx.need_game and the like, which end the command line
                    return self._send(400, {"error": NO_GAME if not studio.ctx.cfg.game_dir else str(e)})
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    studio.log_error(where, e)
                    return self._send(400, {"error": sentence(e)})
                except PermissionError as e:
                    if getattr(e, "filename", None):   # a file that won't open, not a refusal of ours
                        studio.log_error(where, e)
                        return self._send(400, {"error": sentence(e)})
                    return self._send(403, {"error": str(e)})
                except KeyError as e:
                    # Something the request left out (a LookupError too, but not a 404: the route is there), or a
                    # game file that isn't (gamefiles.read): the key alone, without the quotes str() adds.
                    return self._send(400, {"error": str(e.args[0]) if len(e.args) == 1 else str(e)})
                except LookupError as e:
                    return self._send(404, {"error": str(e)})
                except (ValueError, RuntimeError) as e:
                    if str(e).strip():
                        return self._send(400, {"error": str(e)})
                    studio.log_error(where, e)   # nothing to say: the details are all there is
                    return self._send(400, {"error": f"Something went wrong, with the details in {STUDIO_LOG}"})
                except Exception as e:   # noqa: BLE001 - whatever it is, the page gets a sentence and the log the rest
                    studio.log_error(where, e)
                    said = str(e).strip()
                    return self._send(500, {"error": f"Something went wrong{': ' + said if said else ''}, with the "
                                                     f"details in {STUDIO_LOG}"})
                finally:
                    if upload:
                        os.remove(upload)
            if method != "GET":
                return self._send(405, {"error": "method not allowed"})
            if path in ("/", "/index.html", "/studio/index.html"):
                with open(os.path.join(studio.static, "index.html"), encoding="utf-8") as f:
                    html = f.read().replace("{{WC_TOKEN}}", studio.token)
                return self._send(200, html.encode(), "text/html; charset=utf-8")
            if path.startswith("/studio/"):
                return self._file(studio.static, path[len("/studio/"):])
            if path.startswith("/help/images/"):
                return self._file(os.path.join(guide.folder(studio.root), "images"), path[len("/help/images/"):])
            if path == "/help" or path.startswith("/help/"):
                # A page of the guide on its own (the panel's "Open in a tab"), in the studio's look.
                page = path[len("/help/"):].strip("/") or guide.INDEX
                try:
                    text = guide.read(studio.root, guide.INDEX if page == "index" else page)
                except LookupError:
                    return self._send(404, {"error": "there's no such help page"})
                html = guide.page_html(guide.title(text), guide.render(text))
                return self._send(200, html.encode(), "text/html; charset=utf-8")
            if path.startswith("/mods/") and studio.ctx.cfg.data.get("allow_code_mods"):
                parts = path.split("/")
                if len(parts) >= 5 and parts[3] == "studio":
                    return self._file(os.path.join(studio.ctx.mods_root, parts[2], "studio"), "/".join(parts[4:]))
            return self._send(404, {"error": "not found"})

        def _file(self, base, rel):
            full = os.path.realpath(os.path.join(base, rel))
            if not full.startswith(os.path.realpath(base) + os.sep) or not os.path.isfile(full):
                return self._send(404, {"error": "not found"})
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if full.endswith(".js"):
                ctype = "text/javascript; charset=utf-8"
            with open(full, "rb") as f:
                return self._send(200, f.read(), ctype)

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_PUT(self):
            self._handle("PUT")

        def do_PATCH(self):
            self._handle("PATCH")

        def do_DELETE(self):
            self._handle("DELETE")

    return Handler


class _Server(ThreadingHTTPServer):
    """One studio per port. HTTPServer turns on SO_REUSEADDR, which on Windows lets a second server
    bind a port that's already in use, so two studios would silently share it."""
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


LAUNCHER = "Clan Mod Studio.bat"   # beside wcmods.py: what a player double-clicks
PORT_TRIES = 10                     # ports tried from the one asked for, when it's taken by another program
PROBE_TIMEOUT = 3                   # seconds to wait for whatever holds a port to answer


def other_studio(port):
    """Whether what holds a port is a Clan Mod Studio: asked for /api/info with no token, ours answers 403
    with its JSON saying so."""
    # Straight to this machine: a proxy set for the system (HTTP_PROXY) never sees the question.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/info", timeout=PROBE_TIMEOUT):
            return False   # answered without a token: something else
    except urllib.error.HTTPError as e:
        try:
            data = json.load(e)
        except ValueError:
            return False
        return e.code == 403 and isinstance(data, dict) and "studio token" in str(data.get("error", ""))
    except (OSError, ValueError):
        return False


# What a restarted studio runs under when it isn't the launcher: the studio, and when that ends with a problem
# (its port taken, say), the window stays open with the message, as the launcher's does, instead of closing
# before it can be read. Ctrl+C reaches the studio too, which stops by itself.
RESTART_WRAPPER = """import subprocess, sys
p = subprocess.Popen([sys.executable, "-I"] + sys.argv[1:])
while True:
    try:
        code = p.wait()
        break
    except KeyboardInterrupt:
        pass
if code:
    print()
    print("Something went wrong; the message above says what.")
    try:
        input("Press Enter to close this window.")
    except (EOFError, KeyboardInterrupt):
        pass
sys.exit(code)
"""


def restart_command(root, port):
    """How start_again starts the fresh studio: (how, the command). The launcher (which finds Python as a
    double-click does) when it's there and the port is the usual one: run by cmd /C, which closes its window
    when the launcher ends (a later restart leaves no window behind at a prompt), with the launcher's path
    quoted inside a second pair of quotes, which cmd takes off, so a folder with & or spaces in its name is
    still one path. Else Python itself, under RESTART_WRAPPER."""
    bat = os.path.join(root, LAUNCHER)
    if os.name == "nt" and port == DEFAULT_PORT and os.path.isfile(bat):
        return "launcher", f'cmd.exe /C ""{bat}""'
    return "python", [sys.executable, "-I", "-c", RESTART_WRAPPER, os.path.join(root, "wcmods.py"), "studio",
                      "--port", str(port)]


def start_again(root, port):
    """A fresh studio in a window of its own (restart_command). It won't open another browser tab: the page
    that asked finds the new studio by itself once it answers."""
    env = {**os.environ, "WCMODS_NO_BROWSER": "1"}
    how, command = restart_command(root, port)
    subprocess.Popen(command, cwd=root, env=env, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                     close_fds=True)
    return how


def find_port(port):
    """A server bound to `port`, or to the next free one when another program holds it: (server, tried,
    other), `tried` the ports found in use and `other` the port of a Clan Mod Studio already open, which ends
    the search with no server (that studio is opened instead). Port 0 takes any free port (the tests)."""
    tried = []
    for attempt in range(PORT_TRIES if port else 1):
        want = port + attempt if port else 0
        try:
            return _Server(("127.0.0.1", want), None), tried, None
        except OSError:
            tried.append(want)
            if other_studio(want):
                return None, tried, want
    return None, tried, None


def serve(ctx, port=DEFAULT_PORT, open_browser=True, add=None):
    """Run the studio; `add` is a mod's .zip or folder (dropped on the launcher) for it to offer to add,
    which a studio already running picks up too. When the port is held by another studio, that one is opened
    instead; when by anything else, the next ports are tried. Port 0 takes any free port (the tests), named on
    the first line printed."""
    if add:
        onboarding.put_inbox(add)
    studio = Studio(ctx)
    open_browser = open_browser and not os.environ.get("WCMODS_NO_BROWSER")
    server, tried, other = find_port(port)
    if other:
        # Most likely a studio started earlier (a second double-click): open that one instead.
        url = f"http://127.0.0.1:{other}/"
        print(f"Clan Mod Studio is already open, at {url}")
        print("(after an update, press Restart the studio at the top of its page, or close its window and open it again)")
        if open_browser:
            webbrowser.open(url)
        return
    if server is None:
        sys.exit(f"Couldn't open Clan Mod Studio: ports {tried[0]} to {tried[-1]} are all in use by other programs. "
                 "Close some, or start it with --port and a free one.")
    port = server.server_address[1]   # the one chosen for port 0, or the next free one
    server.RequestHandlerClass = make_handler(studio, port)
    studio.server, studio.port = server, port
    url = f"http://127.0.0.1:{port}/"
    print(f"Clan Mod Studio running at {url}  (Ctrl+C to stop)", flush=True)
    if tried:
        print(f"(port {tried[0]} is in use by another program, so it's on port {port} instead)", flush=True)
    if ctx.cfg.warning:
        print(ctx.cfg.warning, flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    finally:
        server.server_close()
    if studio.restarting:
        start_again(ctx.root, port)
        print("Restarting Clan Mod Studio in a new window; this one can close.")
