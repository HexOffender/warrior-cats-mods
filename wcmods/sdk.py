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

from . import luacheck
from .formats import cooked, csvdata
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
    def read_tree(folder, skip=()):
        """Every file under a folder as {"sub/path": bytes} ("/" separated), leaving out the paths in `skip`."""
        files = {}
        for root, _, names in os.walk(folder):
            for name in sorted(names):
                path = os.path.join(root, name)
                rel = os.path.relpath(path, folder).replace(os.sep, "/")
                if rel not in skip:
                    with open(path, "rb") as f:
                        files[rel] = f.read()
        return files

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
        self.new_packages = {}  # asset path of a package the game hasn't got -> (chunk id, imports, shaders, bulk)
        self.patch_imports = {} # asset path of a patched game package -> the package IDs it imports now
        self.csv_edits = {}     # csv path -> [(edits, section, source)]
        self.table_rows = {}    # cooked table name -> [(row name, values, section, source)]
        self.ue4ss_mods = {}    # name -> ({relpath: bytes}, section)
        self.ue4ss_shared = {}  # Lua module name -> (text, section)
        self.save_ops = []      # [{"op": ..., "section": ..., ...}]
        self.warnings = []
        self.notes = {}
        self.current = None
        self.mods = []          # the enabled mods in priority order (set by the build)
        self.found = []         # every mod in the mods folder, on or off (set by the build)
        self.held_back = {}     # {mod id: why} for the mods on that a game update leaves out (set by the build)
        self._tuning = None     # TuningData.csv as numbers, read once (ctx.tuning)
        self._texts = {}        # language -> {key: text} (ctx.text)
        self._cooked = {}       # cooked table name -> (the game's asset, its rows) (ctx.cooked_table)
        self._body = None       # the cat's body, read once for the models that need it (ctx.add_mesh)
        self._skeletons = None  # the game's skeletons, read once for the animations that need them (ctx.add_animation)

    @property
    def cache_dir(self):
        """Where a build keeps work it can reuse (encoded textures): cache/ beside the build's output
        folder, so a normal build's is wcmods' cache/ and the selftest's stays in its temp folder."""
        return os.path.join(os.path.dirname(os.path.abspath(self.out_dir)), "cache")

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

    def table(self, name):
        """A game table's rows (as the game ships them, before any mod's edits), each a dict of column ->
        text, with the row's key (its first column) also under "key": ctx.table("AttackMove.csv").
        docs/mechanics/ says what the tables hold."""
        t = csvdata.Table(self.read_data_table(name))
        rows = []
        for r in t.rows:
            row = {h: (r.fields[i] if i < len(r.fields) else "") for i, h in enumerate(t.header)}
            row["key"] = r.fields[0] if r.fields else ""
            rows.append(row)
        return rows

    def cooked_table(self, name):
        """The rows of one of the game's cooked tables (cooked.TABLES) as the game ships them, as
        [(row name, {field: value})]: ctx.cooked_table("DT_QuestObjectsInfo")."""
        if name not in cooked.TABLES:
            raise ValueError(f"wcmods can't read the cooked table {name} (it knows {', '.join(sorted(cooked.TABLES))})")
        return self._cooked_table(name)[1]

    def _cooked_table(self, name):
        if name not in self._cooked:
            path, schema = cooked.TABLES[name]
            data = self.game.read(path)
            self._cooked[name] = (data, cooked.DataTable(data, schema).rows)
        return self._cooked[name]

    def tuning(self, key=None):
        """TuningData.csv as {key: number} (text where a value isn't a number), or one value with a key:
        ctx.tuning("Gameplay.Exploration.Player.MoveAndRun.Run.Speed") -> 390.0."""
        if self._tuning is None:
            t = csvdata.Table(self.read_data_table("TuningData.csv"))
            values = {}
            for r in t.rows:
                if not r.fields:
                    continue
                raw = r.fields[1] if len(r.fields) > 1 else ""
                try:
                    values[r.fields[0]] = float(raw)
                except ValueError:
                    values[r.fields[0]] = raw
            self._tuning = values
        if key is None:
            return dict(self._tuning)
        if key not in self._tuning:
            raise KeyError(f"no tuning value {key} (docs/mechanics/ lists them by system)")
        return self._tuning[key]

    def tune(self, values, source=""):
        """Change TuningData values: ctx.tune({"Gameplay.Combat.Rest.Stamina": 0.6}, source=mod.id). Numbers
        and "x1.5" (times the game's value) both work, merged with every other mod's edits."""
        unknown = [k for k in values if k not in self.tuning()]
        if unknown:
            self.warn(f"TuningData has no {', '.join(sorted(unknown))}; the game won't read new keys it doesn't ask for")
        self.edit_csv("TuningData.csv", dict(values), source=source)

    def text(self, key, language="EN"):
        """A line of the game's own text by its key: ctx.text("STR_ATTACK_QUICK_CLAW") -> "Quick Claw".
        Unknown keys come back as they are."""
        if language not in self._texts:
            table = csvdata.Table(self.game.read_text(f"Wrc/Content/Gameplay/Strings/NonAsset/Strings_{language}.csv"))
            self._texts[language] = {r.fields[0]: r.fields[1] for r in table.rows if len(r.fields) > 1}
        return self._texts[language].get(key, key)

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

    def add_table_row(self, table, row, values, source=""):
        """Add a row to one of the game's cooked tables (cooked.TABLES), merged with every other
        section's rows at the end of the build and written into a copy of the game's asset:
        ctx.add_table_row("DT_QuestObjectsInfo", "MyMod_MoonHerb", {"itemTag": ..., "Name": ...}).
        `values` uses cooked.SCHEMAS' fields; ones left out get the row struct's default."""
        if table not in cooked.TABLES:
            raise ValueError(f"wcmods can't add rows to {table} (it knows {', '.join(sorted(cooked.TABLES))})")
        fields = {f for f, _ in cooked.SCHEMAS[cooked.TABLES[table][1]]}
        unknown = sorted(set(values) - fields)
        if unknown:
            raise ValueError(f"{table} has no field {', '.join(unknown)} (it has {', '.join(sorted(fields))})")
        self.table_rows.setdefault(table, []).append((row, dict(values), self.current, source))

    def patch_package(self, path, data, source="", imports=None):
        """Replace a cooked asset (.uasset) with patched bytes (they may be longer or shorter). `imports`: the
        package IDs it imports (the container header's), when the patch changed them; the game's otherwise."""
        self.packages[path] = (bytes(data), self.current, source)
        if imports is not None:
            self.patch_imports[path] = list(imports)
        else:
            self.patch_imports.pop(path, None)

    def add_package(self, path, data, chunk_id, imports, shaders=(), bulk=None, source=""):
        """Add a cooked asset the game hasn't got ("Wrc/Content/WCMods/.../T_X.uasset"), with its
        12-byte chunk ID, the package IDs it imports and its shader maps (as in the container header),
        and its .ubulk bytes if it has one. texture.py makes these; add_texture is the easy way."""
        if self.game.exists(path):
            raise ValueError(f"{path} is one of the game's own files; patch_package replaces those")
        self.packages[path] = (bytes(data), self.current, source)
        self.new_packages[path] = (bytes(chunk_id), list(imports), list(shaders),
                                   bytes(bulk) if bulk is not None else None)

    def add_texture(self, name, image, like, source="", key=None):
        """A new texture, /Game/WCMods/<name> ("my_mod/T_MoonHerb"), made from an image (width, height,
        RGBA bytes, as png.read gives) as a copy of `like`, one of the game's textures (its asset path,
        "/Game/Art/UXD/Textures/.../T_UI_Icon_Inventory_Horsetail_D"): the same size, format and mips.
        `image` may be a function that makes the image, and `key` text that changes whenever the image
        would (a hash of the PNG file, say): with both, a texture made before comes from the cache
        without making the image again. Returns the new texture's asset path, for an icon or an
        accessory's look."""
        from .formats import texture
        package = texture.new_package_name(name)
        path = texture.content_path(package)
        built = texture.build(self, package, image, like, key)
        self.add_package(path, built["data"], built["chunk_id"], built["imports"], built["shaders"],
                         bulk=built["bulk"], source=source)
        return package + "." + package.rsplit("/", 1)[-1]

    def add_mesh(self, name, model, like, source="", key=None, on_cat=True):
        """A new skeletal mesh, /Game/WCMods/<name> ("my_mod/SK_MoonCollar"), made from a model (a
        models.Model, or a function that reads one) as a copy of `like`, one of the game's accessory meshes
        (its asset path): the same skeleton, material, LODs and body-shape morphs, with the model's shape
        tied to the cat's body (models.py). With on_cat False, the model stays as it is, on the skeleton's
        root bone, for a mesh shown on its own (a pickup's on the ground). `key` is text that changes
        whenever the model would (a hash of its file); with it, a mesh made before comes from the cache.
        Returns the new mesh's asset path."""
        from . import models
        from .formats import texture
        package = texture.new_package_name(name)
        if on_cat and self._body is None:
            self._body = models.Body(self.game)
        built = models.build(self, package, like, model, key if key is not None else repr(model),
                             self._body if on_cat else None)
        if on_cat and built["farthest"] > models.FAR:
            self.warn(f"{source or name}: part of the model is {built['farthest']:.0f} cm from the cat; models are in "
                      "metres, with Y up, around the cat of the start kit (docs/SDK.md, New items)")
        elif not on_cat and built["farthest"] > models.GROUND_FAR:
            self.warn(f"{source or name}: part of the model is {built['farthest']:.0f} cm from its spot on the ground; "
                      "models are in metres, with Y up, standing at their origin (docs/SDK.md, New items)")
        self.add_package(texture.content_path(package), built["data"], built["chunk_id"], built["imports"],
                         built["shaders"], source=source)
        return package + "." + package.rsplit("/", 1)[-1]

    def add_animation(self, name, read, kind="cat", clip=None, claws=False, source="", key=None):
        """A new animation, /Game/WCMods/<name> ("my_mod/A_Wave"), from a glTF file: read() gives its
        (file name, bytes, sibling) (sibling(name) the bytes of a file a .gltf refers to, or None), and
        `clip` names the animation in it (the first by default). It's for `kind`'s skeleton (animations.KINDS:
        "cat", "mouse"...), as a copy of one of the game's sequences on it (animations.py); for a cat,
        `claws` out. `key` is text that changes whenever the file would (a hash of it); with it, an
        animation made before comes from the cache, and without it, it's made each install. Returns (the
        new sequence's asset path, its seconds)."""
        from . import animations
        from .formats import texture
        if kind not in animations.KINDS:
            raise ValueError(f"there's no animal {kind!r} to animate (there are {', '.join(animations.KINDS)})")
        package = texture.new_package_name(name)
        path = texture.content_path(package)
        if any(p.lower() == path.lower() for p in self.packages):
            # The game names packages in any case, and new_package_name makes - and the like _.
            raise ValueError(f"{package} is another animation's already (their mods' names or ids differ only "
                             "in case, or in - and _)")
        if self._skeletons is None:
            self._skeletons = animations.Game(self.read_game_file)
        built = animations.build(self, package, kind, read, clip, key, claws=claws, game=self._skeletons)
        self.add_package(path, built["data"], built["chunk_id"], built["imports"], built["shaders"], source=source)
        return package + "." + package.rsplit("/", 1)[-1], built["seconds"]

    def replace_animation(self, sequence, read, kind="cat", clip=None, source="", key=None):
        """One of the game's sequences played with a glTF file's keys instead, wherever the game plays it (for
        every animal on that skeleton): `sequence` is its name ("A_CatMaster_Trot_1") or path, in `kind`'s
        folder; read, clip and key as add_animation's. The clip is fitted to the sequence's length, and the
        sequence keeps its notifies (footsteps) and curves. Returns (its asset path, its seconds)."""
        from . import animations
        from .formats import texture
        if kind not in animations.KINDS:
            raise ValueError(f"there's no animal {kind!r} to animate (there are {', '.join(animations.KINDS)})")
        package = animations.find_sequence(self.game.io.files, kind, sequence)
        path = texture.content_path(package)
        if path in self.packages and self.packages[path][1] != self.current:
            # Another section's change to the same package (a higher-priority mod's replacement in this one
            # takes the place of an earlier one, as files do).
            raise ValueError(f"{package.rsplit('/', 1)[-1]} is changed by {self.packages[path][1]} already")
        if self._skeletons is None:
            self._skeletons = animations.Game(self.read_game_file)
        built = animations.build(self, package, kind, read, clip, key, game=self._skeletons, replace=True)
        self.patch_package(path, built["data"], source=source, imports=built["imports"])
        return package + "." + package.rsplit("/", 1)[-1], built["seconds"]

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

    def add_ue4ss_shared(self, name, text):
        """A Lua module any UE4SS script can require(name), installed beside WCModsGame (ue4ss/Mods/shared/
        <name>/<name>.lua) when UE4SS is present: data a section gives the shared scripts, say."""
        for problem in luacheck.check(text)[:3]:
            self.warn(f"{name}.lua: {problem}")
        self.ue4ss_shared[name] = (text, self.current)

    def edit_save(self, path, value, source=""):
        """Set an existing save value at install time (path like 'Shared/SettingsData/Minimap')."""
        self.save_ops.append({"op": "set", "path": path, "value": value, "section": self.current, "source": source})

    def add_save_key(self, object_path, key, value, source="", only_new=False):
        """Add (or set) a key inside a save object, e.g. a new inventory item. With only_new, a key the
        save already has is left as it is (a mod's starting items, given once)."""
        op = {"op": "insert", "path": object_path, "key": key, "value": value, "section": self.current,
              "source": source}
        if only_new:
            op["only_new"] = True
        self.save_ops.append(op)

    def save_op(self, op):
        op = dict(op, section=self.current)
        self.save_ops.append(op)

    # ---- section isolation ----
    def begin(self, section_id):
        self.current = section_id
        self._snapshot = (dict(self.files), dict(self.packages), dict(self.new_packages), dict(self.patch_imports),
                          {k: list(v) for k, v in self.csv_edits.items()},
                          {k: list(v) for k, v in self.table_rows.items()}, dict(self.ue4ss_mods),
                          dict(self.ue4ss_shared), list(self.save_ops), list(self.warnings))

    def rollback(self):
        (self.files, self.packages, self.new_packages, self.patch_imports, self.csv_edits, self.table_rows, self.ue4ss_mods,
         self.ue4ss_shared, self.save_ops, self.warnings) = self._snapshot
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
                table = path.rsplit('/', 1)[-1]
                touched = {}   # (row, column) -> the source that changed it last
                over = {}      # (column, earlier source, later source) -> the rows the later one set over it
                for edits, section, source in queue:
                    who = source or section
                    how = {}
                    text, applied, problems = csvdata.apply_edits(text, edits, how)
                    warnings += [f"{who}: {table}: {p}" for p in problems]
                    changes += [{"row": r, "column": c, "from": a, "to": b, "by": who} for r, c, a, b in applied]
                    for r, c, _, _ in applied:
                        if c == "(row)":
                            continue
                        # Two mods (or a page and a mod) on one cell: multipliers stack, as documented; a plain
                        # value from the later one replaces what the earlier one made, which is said.
                        if touched.get((r, c), who) != who and not how.get((r, c)):
                            over.setdefault((c, touched[(r, c)], who), []).append(r)
                        touched[(r, c)] = who
                for (c, before, who), rows in over.items():   # one line per column and pair of mods
                    named = ", ".join(rows[:3]) + (f" and {len(rows) - 3} more" if len(rows) > 3 else "")
                    warnings.append(f"{who} sets {c} in {table} where {before} changed it too ({named}): the "
                                    f"game gets {who}'s value{'s' if len(rows) > 1 else ''} there")
            except Exception as e:
                failures.append((path, sorted({s for _, s, _ in queue}), f"{type(e).__name__}: {e}"))
                continue
            self.warnings += warnings
            if changes:
                results[path] = changes
            self.files[path] = (text.encode("utf-8"), queue[-1][1], "csv edits")
        return results, failures

    # ---- cooked table rows ----
    def resolve_table_rows(self):
        """Write each cooked table that sections added rows to into the mod container.

        Each table is resolved on its own, like resolve_csv_edits. Returns (changes, failures):
        changes is {table: [{"row", "by"}]}, failures [(table, section ids, error)].
        """
        results, failures = {}, []
        for name, queue in self.table_rows.items():
            path, schema = cooked.TABLES[name]
            sections = sorted({section for _, _, section, _ in queue})
            try:
                if path in self.packages:
                    raise ValueError(f"{self.packages[path][1]} also replaces {path.rsplit('/', 1)[-1]}")
                dt = cooked.DataTable(self._cooked_table(name)[0], schema)
                added = []
                for row, values, section, source in queue:
                    try:
                        dt.add(row, values)
                        added.append({"row": row, "by": source or section})
                    except ValueError as e:
                        self.warnings.append(f"{section}: {name}: {e}")
                if added:
                    self.packages[path] = (dt.bytes(), queue[-1][2], "table rows")
                    results[name] = added
            except Exception as e:
                failures.append((name, sections, f"{type(e).__name__}: {e}"))
        return results, failures
