"""Local web studio: `python wcmods.py studio` serves studio/ and a JSON API on 127.0.0.1.

Every /api request must carry the per-run token (X-WC-Token), and the Host header must be
this machine, so other websites can't drive the mod manager from your browser.
"""
import json
import mimetypes
import os
import re
import secrets
import socket
import tempfile
import threading
import traceback
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import (bridge, catlook, colors, controls, csvdata, eyeatlas, gamebuild, ingame, mods, modzip, names,
               onboarding, palettes, pipeline, save, ue4ss)
from .bridge import Bridge, BridgeError
from .colors import hex_from_linear
from .config import game_running
from .gamefiles import NONASSET
from .savejson import SaveDoc
from .sdk import BuildContext
from .sections.files import classify

NO_GAME = "Clan Mod Studio hasn't found the game yet: Get set up, on the Mods page, asks where it is"

MOD_FILES = ("palette.json", "controls.json", "mouselook.json", "data.json", "items.json", "names.json", "cats.json",
             "save.json", "settings.json", "menu.json")
MAX_UPLOAD = modzip.MAX_BYTES   # a downloaded mod's .zip
# The side bar: "play" is installing and managing mods, "make" the pages for making your own.
BUILTIN_SECTIONS = [
    {"id": "mods", "title": "Mods", "module": "/studio/sections/mods.js", "group": "play"},
    {"id": "palettes", "title": "Palettes", "module": "/studio/sections/palettes.js", "group": "make"},
    {"id": "cat", "title": "Your cat", "module": "/studio/sections/cat.js", "group": "make"},
    {"id": "controls", "title": "Controls", "module": "/studio/sections/controls.js", "group": "make"},
    {"id": "names", "title": "Names", "module": "/studio/sections/names.js", "group": "make"},
    {"id": "data", "title": "Game data", "module": "/studio/sections/data.js", "group": "make"},
    {"id": "save", "title": "Save", "module": "/studio/sections/save.js", "group": "make"},
]
# Pages for code mods: only with "allow_code_mods" (the console runs Lua in the game).
CODE_SECTIONS = [
    {"id": "console", "title": "Console", "module": "/studio/sections/console.js", "group": "make"},
]


class Download:
    """An API answer that's a file to save (a mod as a .zip), not JSON."""

    def __init__(self, data, filename, ctype="application/zip"):
        self.data, self.filename, self.ctype = data, filename, ctype


def code_stamp():
    """The newest change to wcmods' own Python code. The studio runs the code it started with, so once
    this moves on (wcmods was updated while it ran), building with it would install stale scripts."""
    here = os.path.dirname(os.path.abspath(__file__))
    newest = 0.0
    for folder, _, names in os.walk(here):
        for n in names:
            if n.endswith(".py"):
                newest = max(newest, os.path.getmtime(os.path.join(folder, n)))
    return newest


class Studio:
    def __init__(self, ctx):
        self.ctx = ctx
        self.code_stamp = code_stamp()
        self.root = ctx.root
        self.static = os.path.join(ctx.root, "studio")
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()
        self.cpp_building, self.cpp_log, self.cpp_result = None, [], None   # a C++ mod being built from its card
        self._eyes = None
        self._names = None   # the game's name tables, read once

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

    def code_changed(self):
        return code_stamp() > self.code_stamp

    def need_current_code(self):
        if self.code_changed():
            raise RuntimeError("wcmods was updated while Clan Mod Studio was open, and the studio still runs the old "
                               "code. Close the studio's window and open it again, then install.")

    # ---------- API ----------
    # ---- C++ mods: what's ready, and building one from its card (a thread; the page polls /api/cpp) ----
    def cpp_status(self):
        from . import cppmods
        st = cppmods.status(self.ctx.root, self.ctx.cfg)
        with self.lock:
            building, log, result = self.cpp_building, list(self.cpp_log[-40:]), self.cpp_result
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
                    "oodle": bool(cfg.oodle_dll), "ue4ss": bool(cfg.ue4ss_mods_dir), "game_running": game_running(),
                    "installed": cfg.data.get("installed"), "install_outdated": pipeline.install_outdated(cfg),
                    "code_changed": self.code_changed(),
                    "allow_code_mods": bool(cfg.data.get("allow_code_mods")),
                    "game_build": gamebuild.current(cfg), "sections": sections}
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
        if parts == ["setup", "oodle"] and method == "POST":
            path = onboarding.set_oodle(cfg, body.get("path"))
            self.ctx._game = None   # its readers were made without the DLL: the pages read the game afresh
            return {"path": path}
        if parts == ["setup", "backup"] and method == "POST":
            with self.lock:   # two pages asking at once make one copy
                return {"name": onboarding.first_backup(cfg, self.ctx.backups)}
        if parts == ["setup", "loader"] and method == "POST":
            # UE4SS: downloaded from GitHub, or from a .zip sent as the body.
            return self.run(lambda log: onboarding.install_loader(cfg, upload, log))
        if parts == ["play"] and method == "POST":
            self.need_current_code()
            return self.run(lambda log: onboarding.play(self.ctx, log, force=bool(body.get("force"))))
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
            # The game's console, cheats at start and the mod menu's key (wcmods/ingame.py).
            if method == "PATCH":
                # set_options reloads and saves wcmods.json: not in the middle of an install, which would
                # lose what the install has noted but not saved yet.
                with self.lock:
                    return ingame.set_options(cfg, cheats=body.get("cheats"), console=body.get("console"),
                                              menu_key=body.get("menu_key"), menu_scale=body.get("menu_scale"),
                                              menu_pad=body.get("menu_pad"))
            return ingame.options(cfg)
        if parts == ["game", "bridge"] and method == "GET":
            # Whether the game runs with the bridge (wcmods/bridge.py), for the console's status line.
            return Bridge(cfg).status() or {"alive": False, "never": True}
        if parts == ["cpp"] and method == "GET":
            return self.cpp_status()
        if len(parts) == 3 and parts[:2] == ["cpp", "build"] and method == "POST":
            return self.cpp_build(parts[2])
        if parts in (["game", "lua"], ["game", "inspect"]) and method == "POST":
            if not cfg.data.get("allow_code_mods"):
                raise PermissionError("the console runs code in the game; set \"allow_code_mods\": true in wcmods.json")
            code = body.get("code", "") if parts[1] == "lua" else bridge.inspect_code(body.get("expr", ""), bool(body.get("all")))
            try:
                return Bridge(cfg).run(code, timeout=float(body.get("timeout", 15)))
            except BridgeError as e:
                raise RuntimeError(str(e)) from None
        if parts == ["mods"] and method == "GET":
            found = self.mods()
            old = gamebuild.outdated(cfg, found)
            held = gamebuild.held_back(cfg, found)
            unmet = mods.unmet(found, held)
            titles = {m.id: m.name for m in found}
            for i, why in held.items():   # needs a mod made for an older version: left out with it
                if i not in old:
                    unmet.setdefault(i, []).append(f"left out: it {why}")
            return [{**m.to_dict(), "problems": unmet.get(m.id, []),
                     "needed_by": [titles[i] for i in mods.needing(found, m.id)],
                     "requires_names": [titles.get(i, i) for i in m.requires],
                     "game_builds": gamebuild.made_for(m), "outdated": old.get(m.id)} for m in found]
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
                return {"restored": modzip.restore(self.ctx.backups, body["name"], self.ctx.mods_root)}
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "zip" and method == "GET":
            m = self.mod(parts[1])
            return Download(modzip.pack(m), modzip.zip_name(m))
        if parts == ["open"] and method == "POST":
            # Show a folder in Explorer: the mods folder, or one mod's.
            folder = self.ctx.mods_root if body.get("what") == "mods" else self.mod(body.get("id", "")).folder
            if not hasattr(os, "startfile"):
                raise RuntimeError(f"open {folder} yourself (this only works on Windows)")
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
            return {"opened": folder}
        if parts == ["settings"]:
            # "Allow mods that run code" (wcmods.json "allow_code_mods"); the studio asks twice first.
            if method == "PATCH" and "allow_code_mods" in body:
                with self.lock:   # not in the middle of an install (see "ingame")
                    cfg.reload()
                    cfg.data["allow_code_mods"] = bool(body["allow_code_mods"])
                    cfg.save()
            return {"allow_code_mods": bool(cfg.data.get("allow_code_mods"))}
        if parts == ["mods"] and method == "POST":
            m = mods.create(self.ctx.mods_root, body["id"], body.get("name"), body.get("description", ""),
                            enabled=bool(body.get("enabled", False)), priority=int(body.get("priority", 0)))
            return m.to_dict()
        if len(parts) == 2 and parts[0] == "mods" and method == "PATCH":
            m = self.mod(parts[1])
            m.update(**{k: body.get(k) for k in ("enabled", "priority", "name", "description")})
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
                text = body["text"]
                json.loads(text)  # refuse to write broken JSON
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text if text.endswith("\n") else text + "\n")
                return {"saved": name}
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
                return self.run(lambda log: dict(zip(("on", "off"), mods.choose_palettes(self.mods(), ids))))
            return self.run(lambda log: pipeline.apply_palettes(
                cfg, self.ctx.mods_root, ids, self.ctx.build_dir, self.ctx.backups, log,
                force=bool(body.get("force")))[1])
        if parts == ["build"] and method == "POST":
            return self.run(lambda log: pipeline.build(cfg, self.mods(), self.ctx.build_dir, log))
        if parts == ["install"] and method == "POST":
            def go(log):
                pipeline.build(cfg, self.mods(), self.ctx.build_dir, log)
                return pipeline.install(cfg, self.ctx.build_dir, self.ctx.backups, log, force=bool(body.get("force")))
            return self.run(go)
        if parts == ["uninstall"] and method == "POST":
            return self.run(lambda log: {"removed": pipeline.uninstall(cfg, log)})
        if parts == ["backups"]:
            return save.list_backups(self.ctx.backups)[::-1]
        if parts == ["backup"] and method == "POST":
            where, files = save.backup(cfg.save_dir, self.ctx.backups, "studio")
            return {"name": os.path.basename(where), "files": files}
        if parts == ["restore"] and method == "POST":
            if game_running():
                raise RuntimeError("close the game before restoring a save")
            save.backup(cfg.save_dir, self.ctx.backups, "before-restore")
            return {"restored": save.restore(self.ctx.backups, body["name"], cfg.save_dir)}
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
        if parts == ["names"] and method == "GET":
            return self.names_preview({})
        if parts == ["names", "preview"] and method == "POST":
            return self.names_preview(names.validate(body.get("spec") or {}))
        raise LookupError("unknown API route")

    def cat_info(self):
        """Your cat's colour slots in the save, and the colours each slot has with the enabled palettes
        (the game's tables, recoloured slots, and new slots palettes add)."""
        current = {}
        try:
            text, _ = self.save_text()
            doc = SaveDoc(text)
            mine = [c for c in names.cats_in_save(doc.data) if names.PLAYER_PATH in c["paths"]]
            if mine:
                raw = doc.get(mine[0]["paths"][0])
                for part, field in catlook.SLOTS.items():
                    m = re.search(rf"(?<![A-Za-z0-9_]){field}=(\d+)", raw)
                    current[part] = int(m.group(1)) if m else 0
        except LookupError:
            pass
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
        return {"current": current, "palette": slots, "game_slots": palettes.GAME_SLOTS,
                "feral_slots": list(catlook.FERAL_SLOTS), "parts": catlook.PARTS}

    def names_preview(self, spec):
        """The game's names, what a names.json (not yet saved) does to them, and the cats in the save."""
        if self._names is None:
            self._names = names.GameNames(lambda path: self.ctx.game.read_text(BuildContext.data_path(path)))
        plan = names.Plan(self._names, names.merge([spec]))
        try:
            text, _ = self.save_text()
            cats = names.cats_in_save(SaveDoc(text).data)
        except LookupError:
            cats = []
        ops = plan.plan_cats(cats)
        return {**self._names.summary(), "final": {"prefixes": [p["final"] for p in plan.prefixes],
                                                   "suffixes": [s["final"] for s in plan.suffixes],
                                                   "rogues": [r["final"] for r in plan.rogues]},
                "cats": names.cat_list(plan, cats, ops), "renames": [{"from": a, "to": b} for a, b in plan.cat_renames],
                "warnings": plan.warnings, "changed_texts": _changed_texts(plan.edits.get(names.strings_path("EN"), {}))}

    def eyes(self):
        if self._eyes is None:
            atlas = eyeatlas.EyeAtlas(self.ctx.game.read(eyeatlas.PATH))
            self._eyes = {"labels": atlas.labels,
                          "rows": [[hex_from_linear(p)[1:] for p in atlas.row(r)] for r in range(atlas.height)]}
        return self._eyes

    def run(self, fn):
        lines = []
        with self.lock:
            result = fn(lines.append)
        return {"log": lines, "result": result}


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
                try:
                    result = studio.api(method, parts, body, query, upload)
                    if isinstance(result, Download):
                        return self._send(200, result.data, result.ctype, filename=result.filename)
                    return self._send(200, result)
                except zipfile.BadZipFile:
                    return self._send(400, {"error": "that isn't a .zip file (or it's damaged)"})
                except SystemExit as e:   # Ctx.need_game and the like, which end the command line
                    return self._send(400, {"error": NO_GAME if not studio.ctx.cfg.game_dir else str(e)})
                except LookupError as e:
                    return self._send(404, {"error": str(e)})
                except PermissionError as e:
                    return self._send(403, {"error": str(e)})
                except (ValueError, KeyError, RuntimeError, FileNotFoundError) as e:
                    return self._send(400, {"error": str(e)})
                except Exception as e:
                    traceback.print_exc()
                    return self._send(500, {"error": f"{type(e).__name__}: {e}"})
                finally:
                    if upload:
                        os.remove(upload)
            if method != "GET":
                return self._send(405, {"error": "method not allowed"})
            if path in ("/", "/index.html"):
                with open(os.path.join(studio.static, "index.html"), encoding="utf-8") as f:
                    html = f.read().replace("{{WC_TOKEN}}", studio.token)
                return self._send(200, html.encode(), "text/html; charset=utf-8")
            if path.startswith("/studio/"):
                return self._file(studio.static, path[len("/studio/"):])
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


def serve(ctx, port=8765, open_browser=True, add=None):
    """Run the studio; `add` is a mod's .zip or folder (dropped on the launcher) for it to offer to add,
    which a studio already running picks up too."""
    if add:
        onboarding.put_inbox(add)
    studio = Studio(ctx)
    url = f"http://127.0.0.1:{port}/"
    try:
        server = _Server(("127.0.0.1", port), make_handler(studio, port))
    except OSError:
        # Most likely a studio started earlier (a second double-click): open that one instead.
        print(f"Port {port} is already in use. If Clan Mod Studio is already running, it's at {url}")
        print("(to get a fresh one after an update, close the other studio window first)")
        if open_browser:
            webbrowser.open(url)
        return
    print(f"Clan Mod Studio running at {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    finally:
        server.server_close()
