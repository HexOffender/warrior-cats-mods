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
import struct
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
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import (addons, animations, bridge, catcolours, colors, controls, eyeatlas, guide, keymap, menupages,
               menusettings, models, mods, modzip, mouselook, names, onboarding, packs, palettes, pipeline, recolor,
               saverecord, story, ue4ss, world)
from .formats import cooked, csvdata, png, save, texture
from .exe import gamebuild
from .bridge import Bridge, BridgeError
from .colors import hex_from_linear
from .config import game_running, is_game_dir
from .gamefiles import NONASSET, Unreadable
from .formats.savejson import SaveDoc
from .sdk import BuildContext
from .sections import controls as controls_section
from .sections import savedit
from .sections.files import classify

NO_GAME = "Clan Mod Studio hasn't found the game yet: Get set up, on the Mods page, asks where it is"
# Why the Your cat page can't show what your cat wears now (cat_info's save_problem).
SAVE_MISSING = "There's no save yet: start the game once, so there's a save, then come back"
SAVE_UNREADABLE = ("Your save couldn't be read (it may be half written; try again in a moment), so the page can't "
                   "show what your cat wears now")
# What a saved file gets instead of a check while the game's files can't be read (check_file).
CHECK_LATER = "It will be checked when you apply, because the game's files aren't readable now"
# How the page says pipeline.InstallBlocked (the command line says "not installing because some mods didn't build").
BLOCKED = "Nothing went in the game, because some mods couldn't be made ready"
DEFAULT_PORT = 8765
LAST_APPLY = "last-apply.log"   # in your files' folder: what the last Apply, Play or check logged
STUDIO_LOG = "studio.log"       # there too: the details behind "Something went wrong"
STUDIO_LOG_MAX = 1024 ** 2      # studio.log's size before it starts again (the one before is kept as studio.log.1)
# How long what GitHub said of the add-ons' releases is kept (GET /addons?latest=1): GitHub answers sixty
# questions an hour to everyone behind one address, and the Mods page asks only when the player presses
# "Check for newer versions".
RELEASES_FOR = 3600

MOD_FILES = ("palette.json", "controls.json", "mouselook.json", "data.json", "items.json", "animations.json",
             "names.json", "cats.json", "save.json", "settings.json") + story.FILES
PICTURES = "pictures"        # a mod's own pictures (an item's icon, an accessory's look), added on the Items page
MODELS = "models"            # a mod's own models (an accessory's shape), added on the Items page
ANIMATIONS = "animations"    # a mod's own animations (glTF), added on the Animations page
MAX_PICTURE = 8 * 1024 ** 2
ITEM_ROOT = "Gameplay.Inventory."
ITEM_KINDS = {"Consumable": "consumable", "Materials": "material", "Cosmetic": "accessory"}   # a tag's third part, in words
STRINGS_EN = "Wrc/Content/Gameplay/Strings/NonAsset/Strings_EN.csv"   # the game's English text
HIDDEN_TABLES = ("HeightMap/", "UniqueIds/")   # map data the Game data page doesn't list (GET /game/data says which)
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
# Pages for code mods: only with "allow_code_mods" (the console runs Lua in the game).
CODE_SECTIONS = [
    {"id": "console", "title": "Console", "module": "/studio/sections/console.js", "group": "make"},
]


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


class _Notes:
    """Where a build section's checks write their warnings (ctx.warn) when Studio.file_notes runs them alone."""

    def __init__(self):
        self.warnings = []

    def warn(self, msg):
        self.warnings.append(msg[:1].upper() + msg[1:])


def _numbers(noun, numbers):
    """'colour 25', or 'colours 25-27 and 30' for several (a run of three or more as a range)."""
    runs, start = [], None
    for i, n in enumerate(numbers):
        start = n if start is None else start
        if i + 1 == len(numbers) or numbers[i + 1] != n + 1:
            runs.append(str(n) if n == start else f"{start}, {n}" if n == start + 1 else f"{start}-{n}")
            start = None
    if len(numbers) == 1:
        return f"{noun} {runs[0]}"
    head, _, last = ", ".join(runs).rpartition(", ")
    return f"{noun}s {head} and {last}" if head else f"{noun}s {last}"


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
    so nothing went in the game. app.js's plainSummary says the same for the page."""
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
    return said + story_sentence(manifest) + (f" {warnings} warning{'s' if warnings != 1 else ''}." if warnings else "")


def story_sentence(manifest):
    """The cats and questlines a build put in, and whether Sandbox mode will show them, for the summary (the
    story section's notes): " 2 cats and 1 questline from My mods; Sandbox mode 0.5 will show them.", or ""
    with none. The page's log and last-apply.log both show it (task_summary)."""
    notes = (manifest.get("notes") or {}).get("story") or {}
    made = notes.get("story") or {}
    cats = sum(len(v.get("npcs", [])) for v in made.values())
    quests = sum(len(v.get("quests", [])) for v in made.values())
    if not cats and not quests:
        return ""
    parts = [f"{n} {word}{'s' if n != 1 else ''}" for n, word in ((cats, "cat"), (quests, "questline")) if n]
    names = manifest.get("names") or {}
    sandbox = notes.get("sandbox") or {}
    if sandbox.get("state") == "on":
        then = f"Sandbox mode{' ' + sandbox['version'] if sandbox.get('version') else ''} will show them"
    elif sandbox.get("state") == "held-back":   # on, but a game update left it out of this build
        then = "they're waiting for Sandbox mode, left out since the game's update (Use it anyway, on the Mods page)"
    else:
        then = "they're waiting for Sandbox mode"
    return f" {' and '.join(parts)} from {', '.join(names.get(i, i) for i in made)}; {then}."


def manifest_of(result):
    """The build's manifest in a task's result: the result itself (Check mods, Apply), or its "manifest" (Play,
    which has one only when it applied first); else None."""
    if isinstance(result, dict) and "sections" in result:
        return result
    if isinstance(result, dict) and isinstance(result.get("manifest"), dict) and "sections" in result["manifest"]:
        return result["manifest"]
    return None


MAX_CELL_LINES = 20


def table_words(table):
    """A table's file name in words when data-titles.json hasn't one ("QuestObjectives.csv" -> "Quest
    objectives", "NPC/EarType.csv" -> "NPC ear type"), as the Game data page says it (studio/lib/data.js)."""
    stem = re.sub(r"\.csv$", "", table, flags=re.I)
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[0-9])(?=[A-Za-z])", " ", re.sub(r"[/_]+", " ", stem)).split()
    return " ".join(w if re.fullmatch(r"[A-Z0-9]{2,}", w) else (w[:1].upper() + w[1:].lower()) if i == 0 else w.lower()
                    for i, w in enumerate(spaced))


def table_lines(manifest, words=None):
    """The game's numbers a build changes, one line per cell, net of every source (the first value and the last;
    a cell that ends where it began isn't listed): "Tuning: Running speed 390 -> 450 (My mods)". The data
    tables only (the text tables names change are words, not numbers). Rows the Game data page's Quick changes
    name get its words, tables its titles (words: {"quick": [...], "titles": {...}}); at most
    MAX_CELL_LINES, then how many more."""
    words = words or {}
    titles, quick = words.get("titles") or {}, words.get("quick") or []
    names = manifest.get("names") or {}
    who = lambda by: ", ".join(names.get(part.strip(), part.strip()) for part in str(by).split(","))   # noqa: E731
    out = []
    for path, changes in (manifest.get("csv_changes") or {}).items():
        if not path.startswith(NONASSET):
            continue
        table = path[len(NONASSET):]
        cells = {}   # (row, column) -> [first value, last value, last source]
        for c in changes:
            if c.get("column") == "(row)":
                continue
            cell = cells.setdefault((c["row"], c["column"]), [c["from"], None, None])
            cell[1], cell[2] = c["to"], c["by"]
        title = (titles.get(table) or {}).get("title") or table_words(table)
        for (row, column), (was, now, by) in cells.items():
            if was == now:
                continue
            label = next((q["label"] for q in quick if q.get("table") == table and q.get("kind") == "value"
                          and row in ([q["row"]] if q.get("row") else q.get("rows", []))
                          and column.lower() in [c.lower() for c in q.get("columns") or [q.get("column", "")]]), None)
            if label is None:
                label = row if (titles.get(table) or {}).get("value") else f"{row}, {column}"
            out.append(f"{title}: {label} {was} -> {now} ({who(by)})")
    if len(out) > MAX_CELL_LINES:
        out = out[:MAX_CELL_LINES] + [f"and {len(out) - MAX_CELL_LINES} more numbers"]
    return out


def task_summary(title, result, lines, checked=False):
    """The sentence at the top of a task's log (the page's drawer, last-apply.log): what its build did
    (plain_summary); for a Play with nothing to apply, that the game started and how many warnings its log
    has; for Take mods out, that the mods are out and how many cats' names now show as <MISSING STRING TABLE
    ENTRY> (its result's "losing"). None for any other task (the page words those itself)."""
    manifest = manifest_of(result)
    if manifest:
        return plain_summary(manifest, checked)
    if title == "Play":
        n = sum(1 for line in lines if line.startswith("warning: "))
        return "Started the game; nothing needed applying first." + (f" {n} warning{'s' if n != 1 else ''}." if n else "")
    if title == "Take mods out":
        said = "Took every mod out of the game. Your mods are still here."
        n = len(result.get("losing") or []) if isinstance(result, dict) else 0
        if n:
            who = "A cat's name shows" if n == 1 else f"{n} cats' names show"
            said += f" {who} as <MISSING STRING TABLE ENTRY> until they're back (the log says which)."
        return said
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
        self._name_texts = None   # the game's areas, quest titles and items' names with their text keys, read once
        self._items = None   # the game's items, read once
        self._icons = {}     # (item tag or texture, tint) -> PNG bytes
        self._skin = None    # the cat's skin, to say how far a model reaches from it
        self._views = {}     # accessory -> its shape and the cat's, for the Items page's drawing
        self._pictures = {}  # texture -> its full-size PNG, to paint over (the last few)
        self._anims = None   # the game's skeletons, read once for the Animations page
        self._sequences = {}  # kind -> the game's sequences an animation can replace, read once
        self._english = None  # the game's English text by key, read once
        self._data_index = None   # every data table's row names and descriptions, read once (data_index)
        self._model_views = {}  # (mod, path, mtime, on_cat) -> a model's drawing, the last few
        self.releases, self.releases_at = {}, 0.0   # add-on id -> addons.latest(), and when GitHub was asked

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
        """What would keep a file the studio just saved out of the game, or part of it: the first part of the
        check Apply makes (the build section that owns the file reads it, collect()), on this mod alone. Returns
        (problems, notes, left_out). problems: sentences that keep the file out, [] when it's fine. notes: what
        the check warned about, as sentences: a part it leaves out (data.json's table the game hasn't got); the
        file goes in. left_out: the parts of the file collect leaves out because they aren't finished yet
        (ctx.leave_out: an item with no description, an animation with nothing chosen to play), as {"id",
        "name", "why"}; the rest of the file goes in without them, and the page says them as a note. What Apply
        checks with every mod together (a table's rows and columns, models and pictures, two mods changing the
        same thing) is still said only then. While the game's files can't be read (no game folder yet, Steam
        updating it), one line says the check waits for Apply, since some files are checked against the game's
        tables."""
        sec = owner(file)
        if sec is None or not sec.claims(mod):
            return [], [], []
        try:
            # Most files are checked without the game's files; one that needs them (data.json's table names)
            # gets CHECK_LATER while they can't be read.
            game = self.ctx.game if self.ctx.cfg.game_dir else _NoGame()
            ctx = BuildContext(self.ctx.cfg, game, os.path.join(tempfile.gettempdir(), "wcmods-studio"), lambda m: None)
            ctx.found = self.mods()
            ctx.mods = [m for m in ctx.found if m.enabled]
            sec.collect(mod, ctx)
        except KeyError as e:
            # A key a file lacks (str is the key in quotes), or a game file the reader hasn't got.
            what = e.args[0] if len(e.args) == 1 else str(e)
            return [f"{file}: {what} is missing" if isinstance(what, str) and not str(what).startswith("game file")
                    else CHECK_LATER], [], []
        except ValueError as e:
            return [str(e)], [], []
        except (OSError, Unreadable):   # the game's pak isn't there, or won't open
            return [CHECK_LATER], [], []
        except (AttributeError, TypeError):   # a list where an object goes, a number where text does: not a Python name
            return [f"{file} isn't shaped the way the page writes it (docs/formats.md shows how it's laid out)"], [], []
        except Exception as e:   # noqa: BLE001 - said, not hidden, and never as a Python name
            said = str(e).strip()
            return [f"{file} couldn't be checked{': ' + said if said else ''}"], [], []
        # What collect left out because it isn't finished yet (an item with no description): the rest goes in.
        left = [{k: x[k] for k in ("id", "name", "why")} for x in ctx.left_out if x["mod"] == mod.id]
        said = tuple(f"{mod.id}: {x['id']}: " for x in left)
        # Any other warning collect gives is a note. The warnings name the mod for the build's log; under the
        # page's bar the mod is the one in view.
        lead = f"{mod.id}: "
        notes = [w[len(lead):] if w.startswith(lead) else w for w in ctx.warnings if not (said and w.startswith(said))]
        return [], notes, left

    def story_saved(self, mod):
        """After a save of npcs.json or quests.json: a mod with cats or quests says it uses Sandbox mode (soft:
        it's never left out for want of it), and Sandbox mode, when it's in the mods folder but off, is turned
        on. A "requires" an older studio wrote moves to "uses", unless the mod has code of its own (a script
        calling Sandbox mode's API really needs it). Returns the names of the mods it turned on."""
        # What mod.json itself says (Mod reads an older studio's "sandbox" in "requires" as a use already).
        meta_requires, meta_uses = mod.written("requires"), mod.written("uses")
        requires, uses = list(meta_requires), list(meta_uses)
        sid = story.SANDBOX_ID
        if sid in requires and not mod.has_code():
            requires.remove(sid)
            if sid not in uses:
                uses.append(sid)
        has_any = story.has_any(mod.folder)   # a file emptied of them leaves "uses" as it is: it blocks nothing
        if has_any and sid not in uses and sid not in requires:
            uses.append(sid)
        changes = {k: v for k, v, was in (("requires", requires, meta_requires), ("uses", uses, meta_uses)) if v != was}
        if changes:
            mod.update(**changes)
        if not has_any:
            return []
        found = self.mods()
        sandbox = next((x for x in found if x.id == sid), None)
        if sandbox is None or sandbox.enabled or sandbox.problem:
            return []
        try:
            changed, _ = mods.switch(found, sid, True)
        except ValueError:   # it needs a mod that isn't there: the Mods page and the story pages say so
            return []
        names = {x.id: x.name for x in found}
        return [names.get(i, i) for i, on in changed if on]

    def file_notes(self, mod, file):
        """What Apply would warn about a file the studio just saved that check_file found fine, as sentences: an
        entry it would leave out, or one another mod's file wins. The file still goes in. [] when there's
        nothing to say, or when what the note needs can't be read now (the game's files, the save)."""
        notes = _Notes()
        try:
            if file == "palette.json":
                self._palette_notes(mod, notes)
            elif file == "cats.json":
                self._cats_notes(mod, notes)
        except Exception as e:   # noqa: BLE001 - a note is a nicety: whatever stops one, the save still stands
            self.log_error(f"notes on {mod.id}'s {file}", e)
        return notes.warnings

    def _palette_notes(self, mod, notes):
        path = os.path.join(mod.folder, "palette.json")
        data = palettes.load(path)
        # An eye key that isn't one of the game's eye colours: the build skips it. Checked against the names the
        # Palettes page already read (eyes()), only while the game's files can be read.
        labels = None
        if data.get("eyes") and self.ctx.cfg.game_dir:
            try:
                labels = self.eyes()["labels"]
            except Exception:   # noqa: BLE001 - the game's files aren't readable now: Apply checks them
                labels = None
            for key in data["eyes"] if labels else ():
                try:
                    eyeatlas.resolve(labels, key)
                except KeyError as e:
                    notes.warn(f"eyes: {e.args[0]}, so Apply leaves it out")
        # One colour named twice ("03" and "3", "Amber" and "iris2"): the build takes the later in the file, which the
        # Palettes page can't always tell (it lists both as a conflict), so it's said here, from the file's own order.
        with open(path, encoding="utf-8-sig") as f:
            raw = json.load(f)
        for part, at, keys in palettes.named_twice(raw, (lambda k: eyeatlas.resolve(labels, k)) if labels else None):
            what = palettes.eye_word(labels, at) if part == "eyes" else f"{palettes.PLAIN[part]} colour {at}"
            said = ", ".join(f'"{k}"' for k in keys[:-1]) + f' and "{keys[-1]}"'
            both, later, rest = ("both", "the later", "the other") if len(keys) == 2 else ("all", "the last", "the others")
            notes.warn(f'{part}: {said} {both} name {what}, and Apply uses "{keys[-1]}", {later} in the file: remove {rest}')
        # A new colour another palette that's on adds too: the one later in the Mods list shows.
        mine = palettes.new_slots(data)
        found = self.mods() if mine else []
        order = [m.id for m in found]
        for other in found:
            path = os.path.join(other.folder, "palette.json")
            if other.id == mod.id or not other.enabled or not os.path.isfile(path):
                continue
            try:
                theirs = palettes.new_slots(palettes.load(path))
            except ValueError:
                continue   # its own card says what's wrong with it
            later = order.index(other.id) > order.index(mod.id)
            for part, slots in mine.items():
                both = sorted(set(slots) & set(theirs.get(part, [])))
                if both:
                    notes.warn(f"{part.title()} {_numbers('colour', both)} {'is' if len(both) == 1 else 'are'} also "
                               f"added by {other.name}, which is {'later' if later else 'earlier'} in the Mods list, so "
                               f"{'its colour shows' if later else 'this one shows'}")

    def _cats_notes(self, mod, notes):
        from .sections.cats import EMPTY, CatsSection
        data = catcolours.validate(CatsSection.read_json(mod, "cats.json"))
        enabled = [m for m in self.mods() if m.enabled or m.id == mod.id]
        added = palettes.added_slots(enabled)
        # The build's own checks, with its own words: a new colour no palette adds, a Feral coat, a scar that
        # shows nothing.
        CatsSection._check(notes, "your cat", {**EMPTY, **data.get("player", {})}, added)
        for target, one in data.get("cats", {}).items():
            CatsSection._check(notes, target, {**EMPTY, **one}, added)
        # Cats no key finds, or a name two cats share, found the way the build finds them (with the game's names,
        # for the cats' names as they show).
        if not data.get("cats"):
            return
        try:
            text, _ = self.save_text()
            cats = names.cats_in_save(SaveDoc(text).data)
        except LookupError:
            CatsSection._others(notes, None, [data["cats"]], [], False)
            return
        except (ValueError, OSError, struct.error, zlib.error, EOFError):
            return   # a save being written: Apply finds the cats
        if not self.ctx.cfg.game_dir:
            return
        try:
            if self._names is None:
                self._names = names.GameNames(lambda path: self.ctx.game.read_text(BuildContext.data_path(path)))
            try:
                spec = names.merge(names.mod_specs(enabled))
            except ValueError:
                spec = names.merge([])
            plan = names.Plan(self._names, spec)
            found = _Notes()
            CatsSection._others(found, plan, [data["cats"]], cats, True)
        except (Unreadable, OSError, LookupError):
            return   # the game's names can't be read now: Apply finds the cats
        notes.warnings += found.warnings

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
    def new_id(self, name):
        """A mod folder name for a mod called `name`, not taken yet: "Moonlit Path" -> moonlit-path (-2, -3...)."""
        base = modzip.safe_id(name or "my-mod")
        taken = {m.id for m in self.mods()} | set(os.listdir(self.ctx.mods_root) if os.path.isdir(self.ctx.mods_root) else [])
        mod_id, n = base, 2
        while mod_id in taken:   # a folder name is at most 64 characters: the number fits inside them
            suffix = f"-{n}"
            mod_id, n = base[:64 - len(suffix)].rstrip("-._") + suffix, n + 1
        return mod_id

    def last_crash(self):
        """GET /crash: the game's newest crash report from after the last Apply or Take all mods out
        (wcmods.json "crash_after", else the install's "built"), as crashes.summary says it; None without
        either (a fresh folder: no crash of wcmods' to show), or when the crash folder can't be read right now
        (a report being written or removed as it's read)."""
        from . import cppmods, crashes
        data = self.ctx.cfg.data
        since = data.get("crash_after") or (data.get("installed") or {}).get("built")
        try:
            after = datetime.datetime.fromisoformat(str(since)).timestamp()
        except (TypeError, ValueError):
            return {"crash": None}
        try:
            path = crashes.latest(after=after)
            return {"crash": crashes.summary(path, self.mods(), cppmods.SDK_DIR) if path else None}
        except OSError:
            return {"crash": None}

    # ---- the mods that go with Clan Mod Studio (wcmods/addons.py) ----
    def ask_releases(self):
        """What GitHub has of each add-on (self.releases), asked at most once an hour. Only answers are kept
        for the hour (addons.answered): when GitHub couldn't be reached, or turned the question away, the card
        shows why, and the next press asks again."""
        fresh = time.time() - self.releases_at < RELEASES_FOR
        if fresh and all(addons.answered(self.releases.get(a.id)) for a in addons.ADDONS):
            return
        found = {a.id: addons.latest(a) for a in addons.ADDONS}
        with self.lock:
            self.releases = found
            self.releases_at = time.time() if all(addons.answered(r) for r in found.values()) else 0.0

    def noting_release(self, addon, fn):
        """fn(), noting what it found out about the add-on's release: none yet (ue4ss.NoRelease), so the
        Add-ons card can say so without asking GitHub again."""
        try:
            return fn()
        except ue4ss.NoRelease as e:
            self.releases[addon.id] = {"no_release": True, "error": str(e)}
            raise

    def add_addon(self, addon_id, upload, body):
        """POST /addons/<id>: add or update it, with the progress shown (self.run)."""
        addon = addons.get(addon_id)
        on = body.get("on")
        if on is not None and not isinstance(on, bool):
            raise ValueError('"on" should be true or false')
        cfg = self.ctx.cfg

        def go(log):
            if addon.id == menupages.ID:   # with its cheats from when the mod menu was wcmods' own
                done = menupages.add(cfg, upload, log)
                if on is not None and not done["unchanged"]:
                    mods.Mod(os.path.join(cfg.mods_root, addon.id)).set_enabled(on)
                    done["on"] = on
                return done
            return addons.add(cfg, addon.id, upload, on=on, log=log)
        result = self.run(lambda log: self.noting_release(addon, lambda: go(log)), f"Add {addon.name}")
        if not upload and not result["result"]["unchanged"]:
            self.releases[addon.id] = {"version": result["result"]["version"]}
        return result

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
            if not is_game_dir(cfg.game_dir):   # none found, or the folder named isn't the game's (it moved)
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
            # A folder that isn't the game's (the game moved) is no game: Play and Apply wait while Get set up
            # asks where it is.
            return {"game_dir": cfg.game_dir if is_game_dir(cfg.game_dir) else None,
                    "save_found": os.path.isfile(os.path.join(cfg.save_dir, save.SAV_NAME)),
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
            with self.lock:   # it reloads and saves wcmods.json: not in the middle of an install
                return {"dir": onboarding.set_game_dir(cfg, body.get("dir"))}
        if parts == ["setup", "code"] and method == "POST":
            # Not now on "Let mods run their own scripts"; Allow is PATCH /settings, as on Settings and repair.
            if not body.get("skip"):
                raise ValueError("allowing mods that run code is PATCH /settings {allow_code_mods: true}")
            with self.lock:
                return {"result": onboarding.skip_code(cfg)}
        if parts == ["setup", "addons"] and method == "POST":
            # The add-ons step done: {"choice": "added"} once Add all four has run, or "not now".
            with self.lock:
                return {"result": onboarding.addons_step(cfg, body.get("choice"))}
        if parts == ["setup", "backup"] and method == "POST":
            with self.lock:   # two pages asking at once make one copy
                return {"name": onboarding.first_backup(cfg, self.ctx.backups)}
        if parts == ["setup", "loader"] and method == "POST":
            # UE4SS: downloaded from GitHub, or from a .zip sent as the body.
            return self.run(lambda log: onboarding.install_loader(cfg, upload, log), "Install the script loader")
        if parts == ["setup", "pages"] and method == "POST":
            # The older route for the mod menu's pages, kept: POST /addons/menu-pages, or skipped for now.
            if body.get("skip"):
                with self.lock:
                    return {"result": onboarding.skip_pages(cfg)}
            return self.add_addon(menupages.ID, upload, body)
        if parts == ["addons"] and method == "GET":
            # The mods that go with Clan Mod Studio (wcmods/addons.py), as the Add-ons card shows them;
            # ?latest=1 also asks GitHub for each one's latest release (kept for an hour).
            if (query or {}).get("latest") == "1":
                self.ask_releases()
            return {"addons": addons.status(cfg, self.releases), "code_allowed": bool(cfg.data.get("allow_code_mods")),
                    "checked": self.releases_at or None}
        if len(parts) == 3 and parts[0] == "addons" and parts[2] == "preview" and method == "POST":
            # What adding one would add, as a dropped .zip's preview: downloaded (with the progress shown).
            addon = addons.get(parts[1])
            return self.run(lambda log: self.noting_release(addon, lambda: addons.preview(cfg, addon.id, log)),
                            f"Look at {addon.name}")["result"]
        if len(parts) == 2 and parts[0] == "addons" and method == "POST":
            # Add or update one: its latest release from GitHub, or a .zip of it sent as the body; {on} says
            # whether it goes in on (else as it ships, or as you had it).
            return self.add_addon(parts[1], upload, body)
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
            onboarding.shown_inbox()   # on the page now: it waits there as long as the player likes
            return {"mods": found, "name": os.path.basename(waiting), "code_allowed": bool(cfg.data.get("allow_code_mods"))}
        if parts == ["mods", "inbox", "add"] and method == "POST":
            waiting = onboarding.inbox()
            if not waiting:
                raise LookupError("that mod isn't waiting any more; drop it on Clan Mod Studio again")
            # {ids, on: [the ids that go in switched on]}, or {ids, enable: one answer for all}.
            if isinstance(body.get("on"), list):
                enable = {i: i in body["on"] for i in (body.get("ids") or [])} if body.get("ids") else \
                    {i: True for i in body["on"]}
            else:
                enable = bool(body.get("enable", True))
            with self.lock:
                # An add-on updated from its own .zip keeps your values in its settings, as its Add does.
                mine = addons.remember(self.ctx.mods_root)
                if os.path.isdir(waiting):
                    added = modzip.add_folder(waiting, self.ctx.mods_root, self.ctx.backups, ids=body.get("ids") or None,
                                              enable=enable)
                else:
                    added = modzip.add_zip(waiting, self.ctx.mods_root, self.ctx.backups, ids=body.get("ids") or None,
                                           enable=enable, name=os.path.basename(waiting))
                addons.put_back(self.ctx.mods_root, mine, added)
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
            # Whether the game runs with the bridge (wcmods/bridge.py), for the console's status line.
            return Bridge(cfg).status() or {"alive": False, "never": True}
        if parts == ["cpp"] and method == "GET":
            return self.cpp_status()
        if len(parts) == 3 and parts[:2] == ["cpp", "build"] and method == "POST":
            return self.cpp_build(parts[2])
        if parts in (["game", "lua"], ["game", "inspect"]) and method == "POST":
            if not cfg.data.get("allow_code_mods"):
                raise PermissionError("the Console runs code in the game: allow mods that run code first (Options, on "
                                      "the Settings and repair page)")
            code = body.get("code", "") if parts[1] == "lua" else bridge.inspect_code(body.get("expr", ""), bool(body.get("all")))
            try:
                return Bridge(cfg).run(code, timeout=float(body.get("timeout", 15)))
            except BridgeError as e:
                raise RuntimeError(str(e)) from None
        if parts == ["mods"] and method == "GET":
            found = self.mods()
            old = gamebuild.outdated(cfg, found)
            held = pipeline.leave_out(cfg, found)
            unmet = mods.unmet(found, held)
            titles = {m.id: m.name for m in found}
            # Needs a newer Clan Mod Studio, or needs a mod that's left out (made for an older version of the
            # game, or needing a newer studio): left out, and why. A mod made for an older version says so itself.
            for i, why in held.items():
                if i not in old:
                    unmet.setdefault(i, []).append(f"left out: it {why}")
            for m in found:   # a mod.json or palette.json that can't be read: said on the card, never a blank page
                for problem in (m.problem, mods.palette_problem(m)):
                    if problem:
                        unmet.setdefault(m.id, []).append(problem)
            by_id = {m.id: m for m in found}
            known = {story.SANDBOX_ID: story.SANDBOX_NAME}   # a mod's name for a studio that hasn't got it
            # What the re-check after a game update found (gamebuild.recheck): "ok" or why, for this build; a
            # mod it passed says so on its card until the next Apply.
            build = gamebuild.steam_build(cfg)
            results = gamebuild.checked(cfg, build) if build is not None else {}
            check_warnings = gamebuild.check_warnings(cfg, build) if build is not None else {}
            rec = cfg.data.get("rechecked") if isinstance(cfg.data.get("rechecked"), dict) else {}
            since = str(rec.get("when", "")) > str((cfg.data.get("installed") or {}).get("built", ""))
            return [{**m.to_dict(), "problems": unmet.get(m.id, []),
                     "needed_by": [titles[i] for i in mods.needing(found, m.id)],
                     "requires_names": [titles.get(i) or mods.missing_name(i) for i in m.requires if i != mods.MENU_ID],
                     # The mods it works with that aren't on: said on its card, never a reason to leave it out.
                     "works_with": [{"id": i, "name": titles.get(i) or known.get(i, i),
                                     "state": "off" if i in by_id else "missing"}
                                    for i in m.uses if i != mods.MENU_ID and not (i in by_id and by_id[i].enabled)],
                     # A game_builds without a build number, and what the check after a game update warned of it
                     # (while it's still held back, or until the next Apply puts it in).
                     "warnings": [w for w in [gamebuild.builds_problem(m)] if w] +
                                 (list(check_warnings.get(m.id) or []) if old.get(m.id) or (since and m.id in results) else []),
                     "checkable": gamebuild.checkable(m),
                     "rechecked": results.get(m.id), "rechecked_since_apply": since and m.id in results,
                     "game_builds": gamebuild.made_for(m), "outdated": old.get(m.id),
                     "menu_pages": m.id == menupages.ID, "addon": bool(addons.find(m.id)),
                     "tool": packs.is_tool(m)} for m in found]
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "allow-outdated" and method == "POST":
            # Use a mod made for an older version of the game anyway, on this build only (the page warns first).
            build = gamebuild.current(cfg)["build"]
            if build is None:
                raise RuntimeError("couldn't tell which build of the game is installed")
            self.mod(parts[1])
            with self.lock:
                gamebuild.allow(cfg, parts[1], build, on=bool(body.get("on", True)))
            return {"build": build, "allowed": bool(body.get("on", True))}
        if parts == ["mods", "recheck"] and method == "POST":
            # After a game update: build the held-back data mods on the new game; those that build go in.
            return self.run(lambda log: gamebuild.recheck(cfg, self.mods(), self.ctx.build_dir, log),
                            "Check mods on the new version")
        if parts == ["changes"] and method == "GET":
            found = self.mods()
            p = pipeline.pending(cfg, found)
            titles = {m.id: m.name for m in found}
            # left_out ({id: why}): the mods that are on but that Apply leaves out (made for an older version of
            # the game, needing a newer Clan Mod Studio, or needing one of those); held_back is their ids, which
            # the Controls page's line says aren't in the game. Neither counts as a change to apply, but one
            # still in the game (still_in) does: the next Apply takes it out.
            return {**p, "names": {i: titles.get(i, i) for i in p["on"] + p["off"] + p["changed"] + list(p["left_out"])},
                    "held_back": sorted(p["left_out"]),
                    # The re-check after a game update has mods to build (the page starts it: POST /mods/recheck);
                    # nothing is built here, which four pages ask on every focus.
                    "recheck_due": gamebuild.recheck_due(cfg, found),
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
            # ?on=a,b: the ticked mods that go in switched on (the others off); without it, ?enable=1 or 0 for all.
            if "on" in query:
                on = {i for i in query["on"].split(",") if i}
                enable = {i: i in on for i in ids} if ids else {i: True for i in on}
            else:
                enable = query.get("enable", "1") == "1"
            with self.lock:
                # An add-on updated from its own .zip keeps your values in its settings (the Emote wheel's key,
                # Menu pages' cheats), as its Add on the add-ons card does.
                mine = addons.remember(self.ctx.mods_root)
                added = modzip.add_zip(upload, self.ctx.mods_root, self.ctx.backups, ids=ids, enable=enable, name=name)
                addons.put_back(self.ctx.mods_root, mine, added)
                return {"added": added}
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
                # The pack being played on its own: your own mods come back first, as Back to my mods does.
                before = cfg.data.get("pack_before") if isinstance(cfg.data.get("pack_before"), dict) else {}
                back = packs.stop(cfg, found) if before.get("pack") == m.id else None
                return {"moved_to": modzip.remove(m, self.ctx.backups, self.mods() if back else found, cascade=True),
                        "turned_off": [titles.get(i, i) for i in need], "blocked_by": [],
                        "back_to_my_mods": back is not None}
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
                    if not allow:   # a choice made: Get set up doesn't ask again
                        cfg.data["skip_code"] = True
                    cfg.save()
            return {"allow_code_mods": bool(cfg.data.get("allow_code_mods")), "data_dir": cfg.data_dir}
        if parts == ["mods", "new-id"] and method == "GET":
            # The folder a new mod with this name would get (Make your own mod shows it under the Name box).
            return {"id": self.new_id((query or {}).get("name", ""))}
        if parts == ["mods"] and method == "POST":
            fields = {k: field(body, k, *MOD_FIELDS[k]) for k in MOD_FIELDS if body.get(k) is not None}
            # A name alone is enough: the folder's made from it (new_id), as Make your own mod shows.
            mod_id = field(body, "id") if "id" in body or not fields.get("name") else self.new_id(fields["name"])
            m = mods.create(self.ctx.mods_root, mod_id, fields.get("name"), fields.get("description", ""),
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
                    # Cats and questlines come into the game with the Sandbox mode mod: the mod says it works with
                    # it (story_saved). A mod.json that can't be read can't say so: the file is saved all the same,
                    # and the problem said with it.
                    turned_on = None
                    if name in story.FILES:
                        try:
                            if m.problem:
                                raise ValueError(m.problem)
                            turned_on = self.story_saved(m)
                        except ValueError as e:
                            turned_on = []
                            noted.append("The mod can't note that it works with the Sandbox mode mod, and stays off, "
                                         f"until its mod.json is fixed: {m.problem or e}")
                # A file half made still saves; what would keep it, or part of it, out of the game is said now,
                # not at Apply, and so is what Apply would leave out of a file that's fine (notes: the check's own
                # warnings, then file_notes'), and what's left out until it's finished (left_out).
                problems, notes, left = self.check_file(m, name)
                problems = noted + problems
                if not problems:
                    notes = notes + [n for n in self.file_notes(m, name) if n not in notes]
                said = {"saved": name, "requires": m.requires, "problems": problems, "notes": notes, "left_out": left}
                if turned_on is not None:   # cats and quests: the mods they work with, and what came on for them
                    said.update(uses=m.uses, turned_on=turned_on)
                return said
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
            def take_out(log):
                losing = self.names_losing()   # read before: the names come from the mods going out
                return {"removed": pipeline.uninstall(cfg, log, losing=losing), "losing": losing}
            return self.run(take_out, "Take mods out", keep=True, task=body.get("task"))
        if parts == ["backups"]:
            # Newest first, each with its name in words ("Today 15:30, backed up by you").
            return [{"name": n, "label": save.backup_label(n)} for n in save.list_backups(self.ctx.backups)[::-1]]
        if parts == ["backup"] and method == "POST":
            # Never an empty backup (save.backup refuses without a save): it would count as the save being
            # backed up (Get set up, and the first safety copy, which only happens while there's none). The
            # record of save edits goes in it, to come back with the save.
            with self.lock:   # not while an install writes the save
                where, files = saverecord.backup(cfg, self.ctx.backups, "studio")
            return {"name": os.path.basename(where), "label": save.backup_label(os.path.basename(where)), "files": files}
        if parts == ["restore"] and method == "POST":
            if game_running():
                raise RuntimeError("close the game before restoring a save")
            name = field(body, "name")
            with self.lock:
                if name not in save.list_backups(self.ctx.backups):   # only a backup: nothing else is put back
                    raise LookupError(f"there's no backup called {name}")
                before = None
                if save.has_save(cfg.save_dir):   # the save you have, kept first, with the record as it is now
                    before = os.path.basename(saverecord.backup(cfg, self.ctx.backups, "before-restore")[0])
                restored = save.restore(self.ctx.backups, name, cfg.save_dir)
                # The record of save edits comes back with the save: the next Apply makes again only the mods'
                # changes that save hasn't got.
                saverecord.put_back(cfg, os.path.join(self.ctx.backups, name))
            return {"restored": restored, "before": before, "before_label": save.backup_label(before) if before else None}
        if parts == ["game", "eyes"]:
            return self.eyes()
        if parts == ["game", "tables"]:
            # The game's colour tables, once the game has run with the script loader (its log), else the file
            # `wcmods tables` writes; game_slots either way, so a page can show the game's colours by number.
            rep = ue4ss.read_reports(cfg.win64_dir) if cfg.game_dir else None
            if rep and rep["tables"]:
                return {"tables": rep["tables"], "source": "game log", "game_slots": palettes.GAME_SLOTS}
            path = os.path.join(self.root, "colour_tables.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8-sig") as f:
                    return {"tables": json.load(f), "source": "colour_tables.json", "game_slots": palettes.GAME_SLOTS}
            return {"tables": None, "source": None, "game_slots": palettes.GAME_SLOTS}
        if parts == ["game", "bindings"]:
            # The save's copy of the bindings (the game ignores edits to it, and it puts Pause on Enter while the
            # game pauses on Escape): for mods' own pages. The Controls page uses /game/keys.
            text, mtime = self.save_text()
            return {"bindings": controls.read_bindings(text), "save_time": mtime}
        if parts == ["game", "keys"] and method == "GET":
            # The game's own keys as the build knows them (keymap.game_keys), with no save needed, and mouse look's
            # settings as the build reads them (its defaults, and the keys that can switch it off and on).
            return {**keymap.game_keys(), "ue4ss": bool(cfg.ue4ss_mods_dir),
                    "mouselook": {"defaults": mouselook.DEFAULTS, "toggle_keys": list(mouselook.TOGGLE_KEYS)}}
        if parts == ["controls", "check"] and method == "POST":
            # What Apply would do with the Controls page's controls.json for a mod, merged with the other mods'
            # (sections/controls.check): a sentence per entry, the keys in use, who else changes the same.
            mod_id = field(body, "mod")
            if "controls" not in body:
                raise ValueError("the page didn't send its controls.json; reload the page and try again")
            return controls_section.check(body["controls"], mod_id, self.mods(), cfg)
        if parts == ["game", "data"]:
            tables = self.ctx.game.data_tables()
            return {"tables": tables, "kinds": {t: classify(NONASSET + t) for t in tables},
                    "hidden": [t for t in tables if t.startswith(HIDDEN_TABLES)]}
        if parts == ["game", "data", "index"] and method == "GET":
            # Every table's row names and descriptions, for the Game data page's search (before the table route).
            return {"tables": self.data_index()}
        if len(parts) >= 3 and parts[:2] == ["game", "data"]:
            name = "/".join(parts[2:])
            if not self.ctx.game.exists(NONASSET + name):
                raise ValueError(f"the game has no table '{name}'; the Game data page lists the ones it has")
            table = csvdata.Table(self.ctx.game.read_text(NONASSET + name))
            # The English for the game's text keys in it (STR_...), so the page never shows a key alone.
            try:
                english = self.english()
            except KeyError:   # no English text in this game's files: the keys show as they are
                english = {}
            texts = {v: english[v] for r in table.rows for v in r.fields if v.startswith("STR_") and v in english}
            return {"name": name, **table.as_dict(), "texts": texts}
        if parts == ["save"]:
            return self.save_info()
        if parts == ["save", "apply"] and method == "POST":
            return self.save_apply(body.get("changes"))
        if parts == ["save", "undo"] and method == "POST":
            # Put it back, on the Save page: the value a recorded change replaced, after a backup.
            if game_running():
                raise RuntimeError("close the game before changing your save: it would write over the change")
            source, path = field(body, "source"), field(body, "path")
            done = self.run(lambda log: pipeline.undo_save_change(cfg, source, path, self.ctx.backups, log),
                            "Put a change back")
            return {"log": done["log"], **done["result"]}
        if parts == ["save", "applied"] and method == "GET":
            return self.save_applied()
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
            # Where your cat stands in the game, for a cat or a quest's place (through the game bridge), with a
            # sentence that says what to press when it can't be read.
            if not cfg.data.get("allow_code_mods"):
                raise PermissionError(WHERE_NO_CODE)
            try:
                reply = Bridge(cfg).run(WHERE_LUA, timeout=10)
            except BridgeError as e:
                raise RuntimeError(where_problem(e)) from None
            spot = (reply.get("result") or [None])[0]
            if not reply.get("ok") or not isinstance(spot, dict):
                raise RuntimeError("Your cat isn't in the forest yet: go into the forest, stand where you want the cat "
                                   "and press this again")
            return spot
        if parts == ["story", "sandbox"] and method == "GET":
            # What Sandbox mode can show of the cats and questlines, for the Characters and Questlines pages: a
            # Sandbox mode held back after a game update (until "Use it anyway") shows nothing either.
            found = self.mods()
            return story.sandbox(found, bool(cfg.data.get("allow_code_mods")), gamebuild.held_back(cfg, found))
        if parts == ["story", "progress"] and method == "DELETE":
            # Every sandbox cat's questlines back to the start (Sandbox mode keeps them beside the game's saves).
            if game_running():
                raise RuntimeError("Close the game first, then press this again: the game keeps its own copy of "
                                   "how far each cat has got while it runs")
            return story.start_over(pipeline.saved_folder(cfg))
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "picture" and method == "POST":
            # A picture for the mod (an item's icon), sent as the body: kept in the mod's pictures/ folder, never
            # over another item's (?current= is the one this item names now, which it may replace).
            q = query or {}
            return self.add_picture(self.mod(parts[1]), q.get("name", ""), upload, current=q.get("current", ""))
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "model" and method == "POST":
            # A model for an accessory or for a herb on the ground (?ground=1), OBJ or glTF, sent as the body:
            # kept in the mod's models/ folder, as a picture is.
            q = query or {}
            return self.add_model(self.mod(parts[1]), q.get("name", ""), q.get("file", ""), upload,
                                  on_cat=q.get("ground") != "1", current=q.get("current", ""))
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
        if parts == ["build", "last"] and method == "GET":
            # The last build's notes and warnings, and whether it's the one in the game: the Items and
            # Animations pages' "in the game" chips after the studio was started again.
            return self.last_build()
        if parts == ["game", "try-anim"] and method == "POST":
            # One of the game's animations played on your cat in the running game (through the game bridge), to
            # see it before choosing it on the Animations page.
            return self.try_anim(cfg, field(body, "path"))
        if parts == ["game", "anim-kit"] and method == "GET":
            # A cat or an animal rigged to its skeleton as a .glb, to animate in Blender (animations.py).
            data, filename = animations.start_kit(self.ctx.game, (query or {}).get("for", "cat"))
            return Download(data, filename)
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "animation" and method == "POST":
            # A glTF animation, sent as the body: kept in the mod's animations/ folder once it reads, never over
            # another animation's file (?current= as for a picture).
            q = query or {}
            return self.add_animation(self.mod(parts[1]), q.get("name", ""), q.get("file", ""), q.get("for", "cat"), upload,
                                      current=q.get("current", ""))
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
        if len(parts) == 3 and parts[0] == "mods" and parts[2] == "picture" and method == "GET":
            # A PNG anywhere in the mod's folder, by its path in the mod (?path=icons/moon.png: one items.json
            # names that the page didn't put in pictures/), for the Items page's preview.
            m = self.mod(parts[1])
            rel = (query or {}).get("path", "")
            folder = os.path.realpath(m.folder)
            path = os.path.realpath(os.path.join(folder, rel))
            if (not rel.lower().endswith(".png") or os.path.commonpath([folder, path]) != folder
                    or not os.path.isfile(path)):
                raise LookupError(f"{m.id} has no picture {rel}")
            with open(path, "rb") as f:
                return Download(f.read(), os.path.basename(path), "image/png")
        if parts == ["names"] and method == "GET":
            return self.names_preview({})
        if parts == ["names", "preview"] and method == "POST":
            mod_id = body.get("mod")
            return self.names_preview(names.validate(body.get("spec") or {}), mod_id if isinstance(mod_id, str) else None)
        if parts == ["names", "texts"] and method == "GET":
            return self.names_texts()
        if parts == ["names", "losing"] and method == "GET":
            return {"losing": self.names_losing()}
        raise LookupError("unknown API route")

    def cat_info(self):
        """Your cat's colour slots, scars and look in the save, the other cats of the game being played with
        theirs (for cats.json's "cats"), the colours each slot has with the enabled palettes (the game's
        tables, recoloured slots, and new slots palettes add), what each scar place can be, and the look's
        parts with the highest each takes, and the slot of the game being played (current_slot: a key with it first
        means that game's cat). A save that isn't there or can't be read leaves the cats out and says why in
        save_problem (None when it reads), so the page still opens."""
        current, scars, looks, others, save_problem, your_clan, slot = {}, {}, {}, [], None, None, None

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
        doc = None
        try:
            text, _ = self.save_text()
            doc = SaveDoc(text)
        except LookupError:
            save_problem = SAVE_MISSING
        except (ValueError, OSError, struct.error, zlib.error, EOFError):
            # Half written (read while the game saves), cut short, or held open: said, and the page still opens.
            save_problem = SAVE_UNREADABLE
        try:
            if doc is None:
                raise LookupError(save_problem)
            cats = [c for c in names.cats_in_save(doc.data) if c["current"]]
            slot = names.current_slot(doc.data)   # a key with it first ("0/Warrior/1") means this game's cat
            mine = [c for c in cats if c["player"]]
            if mine:
                raw = doc.get(mine[0]["paths"][0])
                current, scars, looks = read(raw)
                clan = re.search(r"(?<![A-Za-z0-9_])ClanType=(\w+)", raw)
                your_clan = clan.group(1) if clan else None
            # The cats' names as they show with the enabled names mods, and every name the build finds each by;
            # without the game's name tables the cats are named by their places (cat_namers).
            shown, called_as = self.cat_namers()
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
                # Every key the build would find it by (names.Plan._targets): its names, matched ignoring case, and
                # its places, matched as written, so the page puts a file's key on the cat it changes.
                others.append({"target": name if name and called[name.lower()] == 1 else where, "name": name or where,
                               "where": where, "role": c["ids"].get("Role", ""), "clan": _clan_of(where),
                               "aliases": {"names": called_as(c), "places": names.place_keys(c["paths"])},
                               "current": {"slots": slots_now, "scars": scars_now, "look": look_now}})
        except LookupError:
            pass
        options = self.look_options()
        return {"current": current, "save_problem": save_problem, "palette": options["palette"], "eyes": options["eyes"],
                "game_slots": options["game_slots"], "slot_parts": list(catcolours.SLOTS),
                "feral_slots": options["feral_slots"], "parts": catcolours.PARTS,
                "scars": {"current": scars, "types": catcolours.SCAR_TYPES},
                "look": {"current": looks, "parts": options["parts"], "size": list(catcolours.SIZE[1:])},
                "cats": others, "your_clan": your_clan, "current_slot": slot}

    def cat_namers(self):
        """(shown, called_as) for cats of names.cats_in_save: shown(cat) is its name as it shows with the enabled
        names mods, called_as(cat) every name the build finds it by, lowercased (names.Plan._targets). Without
        the game's name tables (no game folder, a pak that won't read) "" and [], where pages name cats by their
        places."""
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
            names_of = lambda c: (plan.display(c["ids"]), plan.display(c["ids"], final=False))   # noqa: E731
            return (lambda c: names_of(c)[0] or names_of(c)[1]), (lambda c: sorted({n.lower() for n in names_of(c) if n}))
        except Exception:       # noqa: BLE001 - the page still opens, with places for names
            return (lambda c: ""), (lambda c: [])

    def cat_namer(self):
        """shown(cat) of cat_namers: a cat's name as it shows, or "" without the game's name tables."""
        return self.cat_namers()[0]

    def save_info(self):
        """Your save for the Save page: its account and data, the cat being played and the cats of the other
        slots by name (your cat in each; None where the game's names can't be read), whether the game runs,
        and what the page words and checks values with (savedit.WORDS and RANGES, one home for both)."""
        text, mtime = self.save_text()
        doc = SaveDoc(text)
        slot = names.current_slot(doc.data)
        shown = self.cat_namer()
        cats = {c["slot"]: shown(c) or None for c in names.cats_in_save(doc.data) if c["player"]}
        return {"account": doc.account, "data": doc.data, "save_time": mtime,
                "current_cat": {"slot": slot, "name": cats.get(slot)}, "cats": cats,
                "game_running": game_running(), "words": savedit.WORDS, "ranges": savedit.RANGES}

    def _save_words(self, doc, cats):
        """savedit.label for this save, with the cats' names and the game's item names where they can be read."""
        try:
            items = {i["tag"]: i["name"] for i in self.game_items()["items"]} if self.ctx.cfg.game_dir else {}
        except Exception:   # noqa: BLE001 - no item table: the tags in words
            items = {}
        current = names.current_slot(doc.data)
        return lambda path: savedit.label(path, cats.get, items.get, current)

    def save_apply(self, changes):
        """The Save page's Change my save now: each change made in your save after a backup, and recorded (a
        change to make is {"path", "value"}, {"add": object path, "key", "value"} or {"remove": path})."""
        if game_running():
            raise RuntimeError("close the game before changing your save: it would write over the change")
        if not isinstance(changes, list) or not changes:
            raise ValueError("there are no changes to make")
        info = self.save_info()
        doc = SaveDoc(self.save_text()[0])
        say = self._save_words(doc, info["cats"])
        ops = []
        for c in changes:
            if not isinstance(c, dict):
                raise ValueError("a change should be an object")
            if "add" in c:
                full = f"{c['add']}/{c.get('key')}"
                if not isinstance(c.get("key"), str) or not isinstance(doc.get(c["add"]) if doc.exists(c["add"]) else None, dict):
                    raise ValueError(f"{say(full)}: your save has nowhere to add it")
                op = {"op": "insert", "path": c["add"], "key": c["key"], "value": c.get("value")}
            elif "remove" in c:
                full = c["remove"]
                if not isinstance(full, str):
                    raise ValueError("a remove should be a path")
                problem = savedit.remove_problem(full, doc)
                if problem:
                    raise ValueError(problem[:1].upper() + problem[1:])
                if not doc.exists(full):
                    raise ValueError(f"{say(full)}: your save hasn't got it any more")
                op = {"op": "remove", "path": full}
            elif "path" in c and "value" in c:
                full = c["path"]
                if not doc.exists(full):
                    raise ValueError(f"{say(full)}: your save has no value there")
                op = {"op": "set", "path": full, "value": c["value"]}
            else:
                raise ValueError("a change needs a path and a value, an add or a remove")
            if op["op"] != "remove":
                problem = savedit.range_problem(full, op["value"])
                if problem:
                    raise ValueError(f"{say(full)}: {problem}")
            ops.append({**op, "source": saverecord.STUDIO, "section": "save", "record": True, "label": say(full)})
        done = self.run(lambda log: pipeline.apply_save_ops(self.ctx.cfg, ops, self.ctx.backups, log), "Change my save")
        return {"log": done["log"], "applied": done["result"]["applied"], "backup": done["result"]["backup"]}

    def save_applied(self):
        """The changes made to this save (by mods and by the Save page), newest first, each with what the save
        holds there now and whether it can be put back."""
        record = saverecord.load(self.ctx.cfg) or {}
        try:
            doc = SaveDoc(self.save_text()[0])
        except LookupError:
            return {"changes": []}
        out = []
        for e in saverecord.listing(record, doc.account):
            if e.get("lost_to"):   # another mod's change there went in: nothing of this one was done
                continue
            out.append({**e, "path": e["key"], "current": doc.get(e["key"]) if doc.exists(e["key"]) else None,
                        "can_undo": not e.get("before") and not e.get("undone")})
        return {"changes": out}

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
        return {"palette": slots, "eyes": self._palette_eyes(enabled), "game_slots": palettes.GAME_SLOTS,
                "feral_slots": list(catcolours.FERAL_SLOTS), "parts": {p: catcolours.LOOK_MAX.get(p, 9) for p in catcolours.LOOK}}

    def _palette_eyes(self, loaded):
        """The eye colours the enabled palettes give, by atlas row (str), the later palette's where two give one, as
        the build resolves them: {"2": {"mode": "single" | "grad", "colors": ["#rrggbb", ...]}}. {} while the
        game's eye names can't be read (there's nothing to resolve the keys against)."""
        if not any(p.get("eyes") for p in loaded) or not self.ctx.cfg.game_dir:
            return {}
        try:
            labels = self.eyes()["labels"]
        except Exception:   # noqa: BLE001 - the game's files aren't readable now: the page shows the game's eyes
            return {}
        out = {}
        for pal in loaded:
            for key, spec in pal.get("eyes", {}).items():
                try:
                    row = eyeatlas.resolve(labels, key)
                except KeyError:
                    continue   # the build skips it too, and Save said so
                listed = isinstance(spec, list)
                hexes = [colors.hex_from_srgb(c) for c in (spec if listed else [spec])]
                # A list of one is that colour flat, pupil to rim (palettes.apply_eyes): a gradient of two the same, as
                # the Palettes page reads it, since one colour alone keeps the game's shading.
                out[str(row)] = {"mode": "grad" if listed else "single", "colors": hexes * 2 if listed and len(hexes) == 1 else hexes}
        return out

    def name_tables(self):
        """The game's name tables (names.GameNames), read once. Without a game folder this ends as the command
        line would (SystemExit), which the handler says as NO_GAME; with one it can't read, Unreadable."""
        if self._names is None:
            self._names = names.GameNames(lambda path: self.ctx.game.read_text(BuildContext.data_path(path)))
        return self._names

    def names_specs(self, spec=None, mod_id=None):
        """The names.json of every enabled mod, in priority order, as the next Apply merges them, with `spec` (the
        Names page's file, not saved yet) standing in for mod_id's own: that mod counts even while it's off, since
        saving turns it on, and one not made yet (My mods before its first save) goes last. A file that can't be
        used is left out, with a sentence for each in the second list."""
        specs, left_out, placed = [], [], False
        for m in self.mods():
            if mod_id is not None and m.id == mod_id:
                specs.append(spec or {})
                placed = True
                continue
            if not m.enabled:
                continue
            try:
                theirs = names.read_spec(m)
            except (OSError, ValueError) as e:
                left_out.append(f"{m.name}'s names.json is left out here, because it can't be used: {e}")
                continue
            if theirs is not None:
                specs.append(theirs)
        if mod_id is not None and not placed:
            specs.append(spec or {})
        return specs, left_out

    def names_preview(self, spec, mod_id=None):
        """The game's names, what a names.json not yet saved (`spec`, the Names page's, for mod `mod_id`) does to
        them, and the cats in the save.

        Two plans. The page's own, from `spec` alone, says what this file does: the cards' renamed parts ("final"),
        "What this does" (changed_names, changed_texts, warnings) and what each "names" entry renames
        (names_hits). The cats come from every enabled mod's names.json with `spec` in its mod's place
        (names_specs), named as the next Apply would name them: the list, the renames this file makes, the
        warnings about its own cats entries, and losing_text, the cats that would show as <MISSING STRING TABLE
        ENTRY> if Apply ran now (their names are text a mod gives, and no mod in it gives that text). Each
        warning is also in "notes" with the part of names.json it's about, for the page to put by its row. A cat a
        mod named has "before", the name it had as any mod's file says (for Give it a game name). A save that can't
        be read leaves the list empty, with save_problem saying why.

        With mod_id's mod off ("mod_off"), "off_named" lists the cats whose names only its file gives: they show as
        <MISSING STRING TABLE ENTRY> until it's on and applied (each such cat has "named_by_off_mod")."""
        game = self.name_tables()
        own = names.Plan(game, names.merge([spec]))
        specs, left_out = self.names_specs(spec, mod_id)
        every = names.Plan(game, names.merge(specs))
        cats, slot, problem = [], None, None
        try:
            text, _ = self.save_text()
            doc = SaveDoc(text)
            cats, slot = names.cats_in_save(doc.data), names.current_slot(doc.data)
        except LookupError:
            pass   # no save yet: the page says so
        except ValueError:   # cut short: the game may be writing it
            problem = ("Couldn't read your save: it's cut short, or not laid out the way wcmods expects (the game may "
                       "be writing it just now). The cats list is empty until it can be read")
        except OSError as e:   # locked, or gone between looking and reading
            problem = f"Couldn't open your save ({e.strerror or e}). The cats list is empty until it can be read"
        ops = every.plan_cats(cats)
        listed = names.cat_list(every, cats, ops)
        # For "Give it a game name": the name a mod-named cat had, as any mod's file says (one that's off too).
        every_file = []
        if any(c["mod_named"] for c in listed):
            for m in self.mods():
                try:
                    every_file.append(names.read_spec(m) or {})
                except (OSError, ValueError):
                    continue
            every_file.append(spec)
        for c, cat in zip(listed, cats):
            c["before"] = names.name_before(cat["ids"], every_file) if c["mod_named"] else ""
        mine, merged = spec.get("cats", {}), every.spec.get("cats", {})
        renames = [{"target": t, "from": a, "to": b} for (a, b), t in zip(every.cat_renames, every.rename_targets)
                   if t in mine and merged.get(t) == mine[t]]
        notes = ([n for n in own.notes if not n[0].startswith("cats.")]
                 + [n for n in every.notes if n[0].startswith("cats.") and n[0][len("cats."):] in mine])
        shown = {c["target"]: c["name"] for c in listed}
        losing = [{"target": names.target_of(c), "name": shown.get(names.target_of(c), ""), "key": key}
                  for c, _, key in names.losing_text(cats, ops, every.final.__contains__, game.text)]
        # This page's mod is off: the cats whose names only it gives show as <MISSING STRING TABLE ENTRY> now,
        # though the list names them (its file counts here, as saving turns it on).
        mod = next((m for m in self.mods() if m.id == mod_id), None) if mod_id is not None else None
        mod_off, off_named = bool(mod and not mod.enabled), []
        if mod_off and cats:
            on = names.Plan(game, names.merge(self.names_specs()[0]))   # the mods that are on, without this one
            gone = {x["target"] for x in losing}
            for c, _, key in names.losing_text(cats, (), on.final.__contains__, game.text):
                if names.target_of(c) not in gone:
                    off_named.append({"target": names.target_of(c), "name": shown.get(names.target_of(c), ""), "key": key})
        off = {x["target"] for x in off_named}
        for c in listed:
            c["named_by_off_mod"] = c["target"] in off
        return {**game.summary(), "final": {"prefixes": [p["final"] for p in own.prefixes],
                                            "suffixes": [s["final"] for s in own.suffixes],
                                            "rogues": [r["final"] for r in own.rogues]},
                "cats": listed, "current_slot": slot, "save_problem": problem,
                "renames": renames, "losing_text": losing, "mod_off": mod_off, "off_named": off_named,
                # The game's own text under each key this file's "text" renames ("" for one the game hasn't),
                # for the rows the page's lists don't have.
                "text_now": {k: game.text.get(k, "") for k in spec.get("text", {})},
                "names_hits": own.names_hits,
                "warnings": left_out + [text for _, text in notes],
                "notes": [{"where": where, "text": text} for where, text in notes],
                "changed_names": own.changed + len(renames),
                "changed_texts": _changed_texts(own.edits.get(names.strings_path("EN"), {}))}

    def names_texts(self):
        """What the Names page's Places, quests and items card lists, each with the text key names.json's "text"
        renames it by: the areas and quest titles (world.place_texts), and the items' names from the game's item
        table, by kind. One row per text key, with every item it names ("tags": Rock and Rock2 share one name, so
        renaming it renames both), as place_texts has one per quest title. An item whose name is written in the
        table itself rather than under a key has no key (the game's own items all have one; a row a mod adds may
        not): the page says it can't be renamed here."""
        if self._name_texts is None:
            b = self._reader()
            places = world.place_texts(lambda path: self.ctx.game.read_text(path))
            items, by_key = [], {}
            for _, v in b.cooked_table("DT_QuestObjectsInfo"):
                tag, name = v.get("itemTag") or "", v.get("Name") or {}
                if not tag.startswith(ITEM_ROOT) or tag.count(".") < 3:
                    continue
                kind = ITEM_KINDS.get(tag.split(".")[2], tag.split(".")[2].lower())
                if name.get("key"):
                    if name["key"] in by_key:   # one name, two items
                        by_key[name["key"]]["tags"].append(tag)
                        continue
                    text = b.text(name["key"])
                    if text == name["key"]:   # no text: nothing to show
                        continue
                    by_key[name["key"]] = {"key": name["key"], "tags": [tag], "kind": kind, "text": text}
                    items.append(by_key[name["key"]])
                elif name.get("text"):
                    items.append({"key": None, "tags": [tag], "kind": kind, "text": name["text"]})
            items.sort(key=lambda i: (i["kind"], i["text"].lower()))
            self._name_texts = {**places, "items": items}
        return self._name_texts

    def names_losing(self):
        """The cats in the save whose names are text only a mod gives (pipeline.cats_losing_text): what taking every
        mod out of the game would leave as <MISSING STRING TABLE ENTRY>. Named with the enabled mods' names when
        the game's tables can be read, else from their IDs."""
        plan = None
        try:
            if self.ctx.cfg.game_dir:   # not ctx.game, which ends the command line (SystemExit)
                plan = names.Plan(self.name_tables(), names.merge(self.names_specs()[0]))
        except Exception:   # noqa: BLE001 - the names then come from the cats' IDs
            plan = None
        return pipeline.cats_losing_text(self.ctx.cfg, plan)

    def _reader(self):
        """A build context only for reading the game's tables (it never builds)."""
        return BuildContext(self.ctx.cfg, self.ctx.game, os.path.join(tempfile.gettempdir(), "wcmods-studio"))

    def english(self):
        """The game's English text by its key (STR_...), read once."""
        if self._english is None:
            table = csvdata.Table(self.ctx.game.read_text(STRINGS_EN))
            self._english = {r.fields[0]: r.fields[1] for r in table.rows if len(r.fields) > 1}
        return self._english

    def data_index(self):
        """Every data table the Game data page lists, as {table: {"rows": [row names], "descriptions":
        {row: text}}}, for its search across tables; read once. The map tables (HeightMap/, UniqueIds/) aren't
        listed there, so they're left out here too."""
        if self._data_index is None:
            index = {}
            for name in self.ctx.game.data_tables():
                if name.startswith(HIDDEN_TABLES):
                    continue
                table = csvdata.Table(self.ctx.game.read_text(NONASSET + name))
                low = [h.lower() for h in table.header]
                desc = low.index("description") if "description" in low else None
                rows = [r.fields[0] for r in table.rows if r.fields and r.fields[0]]
                index[name] = {"rows": rows, "descriptions": {
                    r.fields[0]: r.fields[desc] for r in table.rows
                    if desc is not None and len(r.fields) > desc and r.fields[desc].strip()}}
            self._data_index = index
        return self._data_index

    def game_items(self):
        """The game's items for the Items and Questlines pages: tag, kind, name, description, badge (group), and
        for herbs what using them does (the effect, and in words: sections/items.EFFECT_WORDS), who for (target)
        and when (combat, exploring, fight_only); and the choices an item has (effects, badges, rarities,
        colours)."""
        if self._items is None:
            from .sections.items import EFFECT_WORDS
            b = self._reader()
            use = {r["key"]: r for r in b.table("Consumables.csv")}
            recipes = {r["key"] for r in b.table("BarteringCost.csv")}
            badges = {v: k for k, v in cooked.ITEM_GROUP_ICON.items()}

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
                item = {"tag": tag, "kind": ITEM_KINDS.get(kind, kind.lower()),
                        "short": tag[len(ITEM_ROOT):] if kind == "Cosmetic" else tag.split(".", 3)[3],
                        "name": name, "description": text(v.get("Description")),
                        "effect": u.get("EffectOnUse"), "type": u.get("Type"), "recipe": tag in recipes,
                        "pickup": tag.rsplit(".", 1)[-1] in pickups,    # the game has a pickup of its own for it
                        "group": badges.get(v.get("ItemGroupIcon"), "None")}
                if u:
                    item.update({"target": u.get("Target"), "combat": u.get("bCombat") == "TRUE",
                                 "exploring": u.get("bExploration") == "TRUE",
                                 "fight_only": u.get("bRemoveAfterCombat") == "TRUE"})
                    if item["short"] in EFFECT_WORDS:
                        item["words"] = EFFECT_WORDS[item["short"]]
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

    def add_picture(self, mod, name, upload, current=""):
        """Keep a PNG sent from the Items page in the mod's pictures/ folder; returns its path in the mod.
        `current` is the picture the item names now, which this one may replace (_free_stem)."""
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
        name = _free_stem(folder, stem, ".png", current)
        with open(os.path.join(folder, name), "wb") as f:
            f.write(data)
        return {"path": f"{PICTURES}/{name}", "width": w, "height": h}

    def add_model(self, mod, name, filename, upload, on_cat=True, current=""):
        """Keep a model sent from the Items page in the mod's models/ folder, once it reads; returns its path
        in the mod, what it is (vertices, triangles, size) and, for one worn on the cat, how far it reaches
        from the cat. `current` is the model the item names now, which this one may replace (_free_stem)."""
        if not upload:
            raise ValueError("send the model as the request's body")
        ext = os.path.splitext(filename)[1].lower()
        if ext not in models.FORMATS:
            raise ValueError(f"models are {', '.join(models.FORMATS)} files (Blender: File > Export > Wavefront "
                             "or glTF 2.0)")
        with open(upload, "rb") as f:
            data = f.read()
        _one_file(filename, data, "model")
        model = models.read(filename, data)
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", os.path.splitext(os.path.basename(name or filename))[0]).strip("-")[:40] \
            or "model"
        folder = os.path.join(mod.folder, MODELS)
        os.makedirs(folder, exist_ok=True)
        name = _free_stem(folder, stem, ext, current)
        with open(os.path.join(folder, name), "wb") as f:
            f.write(data)
        out = {"path": f"{MODELS}/{name}", **model.summary()}
        if on_cat:
            out["farthest_cm"] = round(self._skin_distance(model), 1)
        return out

    def _skeleton(self, kind):
        if kind not in animations.KINDS:
            raise ValueError(f"there's no animal {kind!r} (there are {', '.join(animations.KINDS)})")
        if self._anims is None:
            self._anims = animations.Game(self.ctx.game.read)
        return self._anims.skeleton(kind)

    def add_animation(self, mod, name, filename, kind, upload, current=""):
        """Keep a glTF animation sent from the Animations page in the mod's animations/ folder, once it reads
        and has an animation the game can take; returns its path in the mod and what it holds
        (animations.describe). `current` is the file the animation names now, which this one may replace
        (_free_stem)."""
        if not upload:
            raise ValueError("send the animation as the request's body")
        ext = os.path.splitext(filename)[1].lower()
        if ext not in animations.FORMATS:
            raise ValueError("animations are glTF files: in Blender, File > Export > glTF 2.0, as glTF Binary (.glb)")
        with open(upload, "rb") as f:
            data = f.read()
        _one_file(filename, data, "animation")
        info = animations.describe(filename, data, kind, self._skeleton(kind))
        if not info["clips"]:
            raise ValueError("the file has no animation: in Blender, export with Animation on")
        if not info["matched"]:
            raise ValueError("none of the file's bones has the name of one of the game's: animate the start kit's armature")
        if all(c["too_long"] for c in info["clips"]):
            c = info["clips"][0]
            raise ValueError(f"{c['name']} is {c['seconds']:.1f} s long; an animation can be up to "
                             f"{info['max_seconds']} s: shorten it in Blender")
        stem = (re.sub(r"[^A-Za-z0-9_-]+", "-", os.path.splitext(os.path.basename(name or filename))[0]).strip("-")[:40]
                or "animation")
        folder = os.path.join(mod.folder, ANIMATIONS)
        os.makedirs(folder, exist_ok=True)
        name = _free_stem(folder, stem, ext, current)
        with open(os.path.join(folder, name), "wb") as f:
            f.write(data)
        return {"path": f"{ANIMATIONS}/{name}", **info}

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
        """[{"name", "paths", "additive", "label", "group"}] for a kind's sequences, by name: label is its plain
        name where one is known (animations.label: "Yawn"; a photo pose by the game's own name for it), group
        "everyday", "poses" or None."""
        from .formats import anim, texture
        if kind not in animations.KINDS:
            raise ValueError(f"there's no animal {kind!r}")
        if kind not in self._sequences:
            out = []
            reader = None

            def text(key):                # the photo poses' names, from the game's text
                nonlocal reader
                try:
                    reader = reader or self._reader()
                    return reader.text(key)
                except Exception:   # noqa: BLE001 - no name then: the pose is listed by its own
                    return key
            for name, paths in animations.game_sequences(self.ctx.game.io.files, kind).items():
                additive = False
                for path in paths:
                    try:
                        additive = additive or anim.AnimSequence(self.ctx.game.read(texture.content_path(path))).additive()
                    except Exception:   # noqa: BLE001 - one asset wcmods can't read leaves the rest listed
                        pass        # the install says so if it's chosen
                label, group = animations.label(name, text)
                out.append({"name": name, "paths": paths, "additive": additive, "label": label, "group": group})
            self._sequences[kind] = sorted(out, key=lambda s: s["name"].lower())
        return self._sequences[kind]

    def last_build(self):
        """{"manifest": the build folder's manifest.json as the pages read it (built, mods, names, notes, warnings,
        sections), or None without one; "installed": whether that build is the one in the game (wcmods.json's
        "installed" names the same build), not only a check of the mods}."""
        try:
            with open(os.path.join(self.ctx.build_dir, "manifest.json"), encoding="utf-8-sig") as f:
                m = json.load(f)
        except (OSError, ValueError):
            return {"manifest": None, "installed": False}
        if not isinstance(m, dict):
            return {"manifest": None, "installed": False}
        installed = (self.ctx.cfg.data.get("installed") or {}).get("built")
        return {"manifest": {k: m.get(k) for k in ("built", "mods", "names", "notes", "warnings", "sections")},
                "installed": bool(installed) and installed == m.get("built")}

    def try_anim(self, cfg, path):
        """Play one of the game's sequences (`path`, /Game/...) on your cat in the running game, through the
        game bridge, for the Animations page's Try it on my cat. Returns {"played": its asset path}."""
        if not cfg.data.get("allow_code_mods"):
            raise PermissionError("trying an animation in the game goes through the game bridge, which runs code: "
                                  "allow mods that run code first (Options, on the Settings and repair page)")
        if not isinstance(path, str) or not GAME_SEQUENCE.match(path):
            raise ValueError("only one of the game's own animations can be tried here")
        full = path if "." in path else f"{path}.{path.rsplit('/', 1)[-1]}"
        bridge = Bridge(cfg)
        status = bridge.status()
        if not status or not status.get("alive"):
            raise RuntimeError("the game isn't running with mods that run code: press Play, go into the forest, "
                               "then try it again")
        try:
            reply = bridge.run(TRY_ANIM_LUA.replace("@PATH@", json.dumps(full)), timeout=10)
        except BridgeError as e:
            raise RuntimeError(str(e)) from None
        said = (reply.get("result") or [None])[0]
        if not reply.get("ok") or said is not True:
            raise RuntimeError(f"it didn't play: {reply.get('error') or said or 'your cat may not be in the world yet'}")
        return {"played": full}

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
        """A model in the mod's folder for the Items page's drawing: its triangles and facts, and how far it
        reaches from the cat. Kept by (mod, path, when it changed, on the cat or not), so the place sliders'
        redraws don't read and measure a big model again."""
        folder = os.path.realpath(mod.folder)
        path = os.path.realpath(os.path.join(folder, rel))
        if os.path.commonpath([folder, path]) != folder or not os.path.isfile(path):
            raise LookupError(f"{mod.id} has no model {rel}")
        key = (mod.id, path, os.path.getmtime(path), on_cat)
        if key not in self._model_views:
            if len(self._model_views) >= 8:
                self._model_views.pop(next(iter(self._model_views)))
            self._model_views[key] = self._model_view(mod, folder, path, rel, on_cat)
        return self._model_views[key]

    def _model_view(self, mod, folder, path, rel, on_cat):
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
        mods), which the summary says. A build's manifest gets `cells_in_words`, the game's numbers it changes
        (table_lines), for the log's drawer. The answer has the log, the result and that summary."""
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
        manifest = manifest_of(result)
        if manifest is not None:
            manifest["cells_in_words"] = table_lines(manifest, self._data_words())
        summary = task_summary(title, result, lines, checked)
        if keep:
            self.keep_log(title, lines, result, None, summary)
        return {"log": list(lines), "result": result, "summary": summary}

    def _data_words(self):
        """The Game data page's own names for rows and tables (data-quick.json, data-titles.json), for
        table_lines; {} where one can't be read."""
        words = {}
        for name in ("data-quick.json", "data-titles.json"):
            try:
                with open(os.path.join(self.static, "sections", name), encoding="utf-8-sig") as f:
                    words[name] = json.load(f)
            except (OSError, ValueError):
                words[name] = {}
        return {"quick": words["data-quick.json"].get("rows", []), "titles": words["data-titles.json"]}

    def keep_log(self, title, lines, result, error, summary=None):
        """last-apply.log: "<title> · <when>", a plain summary, the game's numbers it changed, the warnings,
        then the log."""
        manifest = manifest_of(result)
        head = [f"{title} · {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"]
        if error is not None:
            head.append(error.describe("press Apply the rest anyway", "what they put in the game before is removed", BLOCKED)
                        if isinstance(error, pipeline.InstallBlocked) else f"Couldn't finish: {sentence(error) or error}")
        elif summary:
            head.append(summary)
            head += (manifest or {}).get("cells_in_words", [])
            head += [f"warning: {w}" for w in (manifest or {}).get("warnings", [])]
        try:
            os.makedirs(self.ctx.cfg.data_dir, exist_ok=True)
            with open(os.path.join(self.ctx.cfg.data_dir, LAST_APPLY), "w", encoding="utf-8") as f:
                f.write("\n".join(head + [""] + list(lines)) + "\n")
        except OSError:
            pass


def _clan_of(where):
    """The clan a cat's place is in ("WindClan" for "Clans/WindClan/Warrior/1", the clan the save keeps it
    under), else the place's first part ("Outsiders", "NarrativeRoles"), for the Your cat page's groups."""
    parts = where.split("/")
    return parts[1] if parts[0] == "Clans" and len(parts) > 1 else parts[0]


def _accessory_look(of):
    """("DogCollar", 1) from "DogCollar", "Neck.DogCollar.1" or "Gameplay.Inventory.Cosmetic.Neck.DogCollar.1"."""
    parts = of.split("Cosmetic.", 1)[-1].split(".")
    if len(parts) == 3 and parts[2].isdigit():
        return parts[1], int(parts[2])
    if len(parts) == 1 and parts[0]:
        return parts[0], 1
    raise ValueError(f"{of!r}: give an accessory's look, e.g. Neck.DogCollar.1")


def _free_stem(folder, stem, ext, current=""):
    """The name an upload is kept under in `folder` (a mod's pictures/, models/ or animations/): stem + ext when
    no file has that name, or when the file there is `current` (the mod-relative path of the file the item or
    animation names now, which this one replaces); else the first free one of stem-2, stem-3... So an upload
    never writes over a file another item or animation names. Names are told apart without case, as Windows
    and the game's package names tell them."""
    taken = {n.lower() for n in os.listdir(folder)} if os.path.isdir(folder) else set()
    mine = os.path.normcase(os.path.normpath(os.path.join(os.path.dirname(folder), current))) if current else None
    n = 1
    while True:
        name = stem + ext if n == 1 else f"{stem}-{n}{ext}"
        if name.lower() not in taken or os.path.normcase(os.path.join(folder, name)) == mine:
            return name
        n += 1


def _one_file(filename, data, what):
    """ValueError for a .gltf that keeps its data in another file (glTF Separate): the studio's upload takes one
    file, so the Blender step that makes one is said."""
    if not filename.lower().endswith(".gltf"):
        return
    try:
        buffers = json.loads(data.decode("utf-8-sig")).get("buffers", [])
        apart = next((b.get("uri") for b in buffers if b.get("uri") and not str(b["uri"]).startswith("data:")), None)
    except (ValueError, AttributeError, TypeError):
        return                                   # the reader says what's wrong with it
    if apart:
        raise ValueError(f"that .gltf keeps its {what} in {apart}: in Blender, export it again as glTF Binary (.glb); "
                         "the page takes one file")


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


# What the studio says when it can't talk to the running game (the game bridge), in the order to press things:
# the same words wherever the studio asks the game something.
BRIDGE_CLOSED = "The game is closed: press Play"
BRIDGE_MISSING = ("The game is running without the studio's connection to it: close the game, press Apply to game, "
                  "then Play")
BRIDGE_QUIET = "The game is running but not answering: it may be loading, or held still behind another window"
# "Use where my cat is standing": the same, with what to do once the game is up.
WHERE_THEN = ", stand where you want the cat and press this again"
WHERE_NO_CODE = ("This needs mods that run code: allow them on Settings and repair, then Apply to game and Play"
                 + WHERE_THEN)


def where_problem(e):
    """A BridgeError from reading where your cat is, as the sentence the page shows: what to press next."""
    text = str(e)
    if "no reply within" in text or "another wcmods command" in text:
        return BRIDGE_QUIET + ": press this again in a moment"
    return (BRIDGE_MISSING if game_running() else BRIDGE_CLOSED) + WHERE_THEN


# Where your cat is, through the game bridge: a place and level for a cat or a quest's step.
WHERE_LUA = """
local me = Game and Game.cat()
local l = me and me:location()
if not l then return nil end
local yaw = 0
pcall(function() yaw = Game.player():K2_GetActorRotation().Yaw end)
return { at = { math.floor(l.X), math.floor(l.Y), math.floor(l.Z) }, yaw = math.floor(yaw), level = Game.levelName() }
"""


# One of the game's sequences played once on your cat (the Animations page's Try it on my cat): its asset path,
# "/Game/.../A_CatMaster_Yawn_1.A_CatMaster_Yawn_1", goes in for @PATH@. True, or why it didn't play.
TRY_ANIM_LUA = """
if not Game then return "wcmods' game module isn't loaded" end
local played, why = Game.anims.play(nil, @PATH@)
if not played then return why or "the game didn't play it" end
return true
"""
GAME_SEQUENCE = re.compile(r"/Game/[A-Za-z0-9_/]+/A_[A-Za-z0-9_]+(\.A_[A-Za-z0-9_]+)?$")   # a path TRY_ANIM_LUA takes


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
                        # GitHub out of reach, or a mod with no release yet: said for the page to tell apart.
                        flags = {"offline": True} if isinstance(e, ue4ss.Offline) else \
                            {"no_release": True} if isinstance(e, ue4ss.NoRelease) else {}
                        return self._send(400, {"error": str(e), **flags})
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
    bind a port that's already in use, so two studios would silently share it. A page asks for its scripts,
    styles and data all at once: room for that many to wait their turn (socketserver's 5 overflows on a busy
    machine, which the browser says as ERR_NO_BUFFER_SPACE or a refused connection)."""
    allow_reuse_address = False
    request_queue_size = 128

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
