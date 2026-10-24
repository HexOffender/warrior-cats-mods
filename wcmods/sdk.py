"""wcmods shared library: the API every section uses, built-in or from another mod.

A *section* handles one kind of mod content. It names the files it reads from a mod folder,
turns each enabled mod's copy into data (`collect`), then contributes outputs (`build`)
through the BuildContext. Sections run independently: if one fails, its outputs are
discarded and the others still build.

A mod can ship its own section as `section.py` next to its `mod.json`:

    from wcmods.sdk import Section

    class FasterRun(Section):
        id = "faster-run"
        title = "Faster running"
        files = ("faster-run.json",)

        def collect(self, mod, ctx):
            return self.read_json(mod, "faster-run.json")

        def build(self, ctx, items):
            for mod, data in items:
                ctx.edit_csv("TuningData.csv",
                             {"Gameplay.Exploration.Player.MoveAndRun.Run.Speed": data["speed"]},
                             source=mod.id)

Mod-provided sections only run when "allow_code_mods": true is set in wcmods.json, because
they are Python code. See docs/SDK.md for the full API.
"""
import json
import os

from . import csvdata, luacheck
from .gamefiles import NONASSET


def lua_value(value):
    """JSON-style data (dicts, lists, strings, numbers, booleans, None) as a Lua literal, for putting
    a mod's settings into a UE4SS script: f"local QUEST = {lua_value(data)}"."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        out = []
        for ch in value:
            if ch in '"\\':
                out.append("\\" + ch)
            elif ch == "\n":
                out.append("\\n")
            elif ord(ch) < 32 or ord(ch) == 127:
                out.append(f"\\{ord(ch):03d}")
            else:
                out.append(ch)   # the rest, UTF-8 included, is fine as it is in a Lua string
        return '"' + "".join(out) + '"'
    if isinstance(value, (list, tuple)):
        return "{ " + ", ".join(lua_value(v) for v in value) + " }"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"[{lua_value(str(k))}] = {lua_value(v)}" for k, v in value.items()) + " }"
    raise TypeError(f"can't write {type(value).__name__} as Lua")


class Section:
    id = ""
    title = ""
    files = ()            # file or folder names (relative to a mod folder) this section reads
    appearance_only = False

    def claims(self, mod):
        return any(os.path.exists(os.path.join(mod.folder, f)) for f in self.files)

    def collect(self, mod, ctx):
        """Return this mod's data for the section, or None to skip. Raise ValueError for mistakes."""
        return None

    def build(self, ctx, items):
        """items: [(mod, data)] in priority order (later wins)."""

    # helpers
    @staticmethod
    def read_json(mod, name):
        path = os.path.join(mod.folder, name)
        try:
            with open(path, encoding="utf-8-sig") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"{name}: {e.msg} at line {e.lineno} column {e.colno}") from None


class BuildContext:
    """Collects outputs from all sections, then writes them in finish()."""

    def __init__(self, cfg, game, out_dir, log=print):
        self.cfg, self.game, self.out_dir, self._log = cfg, game, out_dir, log
        self.files = {}         # pak path -> (bytes, section, source)
        self.packages = {}      # asset path -> (bytes, section, source)
        self.csv_edits = {}     # csv path -> [(edits, section, source)]
        self.ue4ss_mods = {}    # name -> ({relpath: bytes}, section)
        self.save_ops = []      # [{"op": ..., "section": ..., ...}]
        self.warnings = []
        self.notes = {}
        self.current = None
        self.mods = []          # the enabled mods in priority order (set by the build)

    # ---- logging ----
    def log(self, msg):
        self._log(msg)

    def warn(self, msg):
        self.warnings.append(f"{self.current}: {msg}" if self.current else msg)

    def note(self, key, value):
        """Attach information to this build's manifest under the current section."""
        self.notes.setdefault(self.current, {})[key] = value

    # ---- reading the game ----
    def read_game_file(self, path):
        return self.game.read(path)

    def read_data_table(self, name):
        """Text of a NonAsset CSV, e.g. 'TuningData.csv' or 'NPC/CatSize.csv'."""
        return self.game.read_text(self.data_path(name))

    @staticmethod
    def data_path(name):
        return name if name.startswith("Wrc/") else NONASSET + name

    # ---- outputs ----
    def add_file(self, path, data, source=""):
        """Add or replace a loose game file (CSV, ini, movie...) in the mod pak."""
        path = path.replace("\\", "/").lstrip("/")
        if path in self.files and self.files[path][1] != self.current:
            self.log(f"  {path}: {self.current} overrides {self.files[path][1]}")
        self.files[path] = (bytes(data), self.current, source)

    def edit_csv(self, name, edits, source=""):
        """Queue cell edits on a game CSV (see csvdata.apply_edits). Edits from all sections merge."""
        self.csv_edits.setdefault(self.data_path(name), []).append((edits, self.current, source))

    def patch_package(self, path, data, source=""):
        """Replace a cooked asset (.uasset) with patched bytes of the same layout."""
        self.packages[path] = (bytes(data), self.current, source)

    def add_ue4ss_mod(self, name, files):
        """files: {"Scripts/main.lua": text, ...}. Installed only when UE4SS is present.

        Lua files get a structure check (balanced blocks and brackets); problems become build warnings.
        """
        for rel, data in files.items():
            if rel.endswith(".lua"):
                text = data if isinstance(data, str) else data.decode("utf-8", "replace")
                for problem in luacheck.check(text)[:3]:
                    self.warn(f"{name}/{rel}: {problem}")
        self.ue4ss_mods[name] = ({k: v.encode() if isinstance(v, str) else v for k, v in files.items()}, self.current)

    def edit_save(self, path, value, source=""):
        """Set an existing save value at install time (path like 'Shared/SettingsData/Minimap')."""
        self.save_ops.append({"op": "set", "path": path, "value": value, "section": self.current, "source": source})

    def add_save_key(self, object_path, key, value, source=""):
        """Add (or set) a key inside a save object, e.g. a new inventory item."""
        self.save_ops.append({"op": "insert", "path": object_path, "key": key, "value": value,
                              "section": self.current, "source": source})

    def save_op(self, op):
        op = dict(op, section=self.current)
        self.save_ops.append(op)

    # ---- section isolation ----
    def begin(self, section_id):
        self.current = section_id
        self._snapshot = (dict(self.files), dict(self.packages), {k: list(v) for k, v in self.csv_edits.items()},
                          dict(self.ue4ss_mods), list(self.save_ops), list(self.warnings))

    def rollback(self):
        (self.files, self.packages, self.csv_edits, self.ue4ss_mods, self.save_ops, self.warnings) = self._snapshot
        self.notes.pop(self.current, None)

    def end(self):
        self.current = None

    # ---- CSV merge ----
    def resolve_csv_edits(self):
        """Apply queued CSV edits on top of the game's (or a section-supplied) file.

        Each table is resolved on its own: a table that can't be read or parsed keeps no edits,
        and the others are unaffected. Returns (changes, failures) where failures is
        [(path, section ids, error)].
        """
        results, failures = {}, []
        for path, queue in self.csv_edits.items():
            try:
                text = self.files[path][0].decode("utf-8") if path in self.files else self.game.read_text(path)
                changes, warnings = [], []
                for edits, section, source in queue:
                    text, applied, problems = csvdata.apply_edits(text, edits)
                    warnings += [f"{section}: {path.rsplit('/', 1)[-1]}: {p}" for p in problems]
                    changes += [{"row": r, "column": c, "from": a, "to": b, "by": source or section}
                                for r, c, a, b in applied]
            except Exception as e:
                failures.append((path, sorted({s for _, s, _ in queue}), f"{type(e).__name__}: {e}"))
                continue
            self.warnings += warnings
            if changes:
                results[path] = changes
            self.files[path] = (text.encode("utf-8"), queue[-1][1], "csv edits")
        return results, failures
