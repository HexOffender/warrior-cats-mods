"""Local web studio: `python wcmods.py studio` serves studio/ and a JSON API on 127.0.0.1.

Every /api request must carry the per-run token (X-WC-Token), and the Host header must be
this machine, so other websites can't drive the mod manager from your browser.
"""
import json
import mimetypes
import os
import secrets
import socket
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from . import controls, csvdata, eyeatlas, mods, names, pipeline, save, ue4ss
from .colors import hex_from_linear
from .config import game_running
from .gamefiles import NONASSET
from .savejson import SaveDoc
from .sdk import BuildContext
from .sections.files import classify

MOD_FILES = ("palette.json", "controls.json", "mouselook.json", "data.json", "names.json", "save.json")
BUILTIN_SECTIONS = [
    {"id": "mods", "title": "Mods", "module": "/studio/sections/mods.js"},
    {"id": "palettes", "title": "Palettes", "module": "/studio/sections/palettes.js"},
    {"id": "controls", "title": "Controls", "module": "/studio/sections/controls.js"},
    {"id": "names", "title": "Names", "module": "/studio/sections/names.js"},
    {"id": "data", "title": "Game data", "module": "/studio/sections/data.js"},
    {"id": "save", "title": "Save", "module": "/studio/sections/save.js"},
]


class Studio:
    def __init__(self, ctx):
        self.ctx = ctx
        self.root = ctx.root
        self.static = os.path.join(ctx.root, "studio")
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()
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

    # ---------- API ----------
    def api(self, method, parts, body):
        cfg = self.ctx.cfg
        if parts == ["info"]:
            sections = list(BUILTIN_SECTIONS)
            if cfg.data.get("allow_code_mods"):
                for m in self.mods():
                    if m.enabled and os.path.isfile(os.path.join(m.folder, "studio", "section.js")):
                        sections.append({"id": f"mod-{m.id}", "title": m.meta.get("studio_title", m.name),
                                         "module": f"/mods/{m.id}/studio/section.js", "from_mod": m.id})
            return {"game_dir": cfg.game_dir, "save_found": os.path.isfile(os.path.join(cfg.save_dir, save.SAV_NAME)),
                    "oodle": bool(cfg.oodle_dll), "ue4ss": bool(cfg.ue4ss_mods_dir), "game_running": game_running(),
                    "installed": cfg.data.get("installed"), "install_outdated": pipeline.install_outdated(cfg),
                    "allow_code_mods": bool(cfg.data.get("allow_code_mods")),
                    "sections": sections}
        if parts == ["mods"] and method == "GET":
            return [m.to_dict() for m in self.mods()]
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
        if parts == ["names"] and method == "GET":
            return self.names_preview({})
        if parts == ["names", "preview"] and method == "POST":
            return self.names_preview(names.validate(body.get("spec") or {}))
        raise LookupError("unknown API route")

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
                "warnings": plan.warnings, "changed_texts": sum(len([k for k in e if k not in "+-"]) + len(e.get("+", []))
                                                              for t, e in plan.edits.items() if "Strings_EN" in t)}

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


def make_handler(studio, port):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # keep the console quiet
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
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
                body = {}
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    try:
                        body = json.loads(self.rfile.read(length) or b"{}")
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        return self._send(400, {"error": f"request body isn't valid JSON: {e}"})
                    if not isinstance(body, dict):
                        return self._send(400, {"error": "request body must be a JSON object"})
                parts = [p for p in path[5:].split("/") if p]
                try:
                    return self._send(200, studio.api(method, parts, body))
                except LookupError as e:
                    return self._send(404, {"error": str(e)})
                except PermissionError as e:
                    return self._send(403, {"error": str(e)})
                except (ValueError, KeyError, RuntimeError, FileNotFoundError) as e:
                    return self._send(400, {"error": str(e)})
                except Exception as e:
                    traceback.print_exc()
                    return self._send(500, {"error": f"{type(e).__name__}: {e}"})
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


def serve(ctx, port=8765, open_browser=True):
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
