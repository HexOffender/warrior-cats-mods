"""Gameplay data edits (data.json): change cells in the game's CSV tables without copying them.

    {
      "TuningData.csv": { "Gameplay.Exploration.Player.MoveAndRun.Run.Speed": 450 },
      "CombatBaseExperience.csv": { "*": { "BaseExperience": "x2" } }
    }

Keys are table names under Gameplay/DataTables/NonAsset (subfolders allowed, e.g. "NPC/Scars.csv"), or a
full Wrc/... path. Several mods can edit the same table; their edits are applied in priority order. Inside
one file the order is fixed (csvdata.apply_edits). A table the game hasn't got is a warning, and the
file's other tables still go in.
"""
from ..sdk import Section
from .files import classify


class DataSection(Section):
    id = "data"
    title = "Game data"
    files = ("data.json",)

    def collect(self, mod, ctx):
        raw = self.read_json(mod, "data.json")
        if not isinstance(raw, dict):
            raise ValueError("data.json should be an object of table names, each with its edits")
        out = {}
        for table, edits in raw.items():
            if table.startswith("_"):
                continue
            if not table.endswith(".csv") or not isinstance(edits, dict):
                raise ValueError(f"data.json: '{table}' should be a table name ending in .csv mapped to edits")
            if not ctx.game.exists(ctx.data_path(table)):
                # A typo, or a table a game update renamed: left out, and the rest still go in.
                ctx.warn(f"{mod.id}: the game has no table '{table}', so its edits are left out (the Game data "
                         "page lists the tables the game has)")
                continue
            out[table] = edits
        return out or None

    def build(self, ctx, items):
        tables = set()
        for mod, data in items:
            for table, edits in data.items():
                path = ctx.data_path(table)
                kind = classify(path)
                if kind == "online":
                    ctx.warn(f"{mod.id}: {table} feeds the online den-visit features; changes there may be "
                             "visible to or rejected by the server")
                elif kind == "traits":
                    ctx.warn(f"{mod.id}: {table} changes which traits cats get")
                elif kind == "story":
                    ctx.warn(f"{mod.id}: {table} is quests and talk; a wrong value can stop a quest")
                ctx.edit_csv(table, edits, source=mod.id)
                tables.add(table)
        if tables:
            ctx.note("tables", sorted(tables))
