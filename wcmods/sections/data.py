"""Gameplay data edits (data.json): change cells in the game's CSV tables without copying them.

    {
      "TuningData.csv": { "Gameplay.Exploration.Player.MoveAndRun.Run.Speed": 450 },
      "CombatBaseExperience.csv": { "*": { "BaseExperience": "x2" } }
    }

Keys are table names under Gameplay/DataTables/NonAsset (subfolders allowed, e.g. "NPC/Scars.csv").
Several mods can edit the same table; their edits are applied in priority order.
"""
from ..sdk import Section
from .files import classify


class DataSection(Section):
    id = "data"
    title = "Game data"
    files = ("data.json",)

    def collect(self, mod, ctx):
        raw = self.read_json(mod, "data.json")
        out = {}
        for table, edits in raw.items():
            if table.startswith("_"):
                continue
            if not table.endswith(".csv") or not isinstance(edits, dict):
                raise ValueError(f"data.json: '{table}' should be a table name ending in .csv mapped to edits")
            if not ctx.game.exists(ctx.data_path(table)):
                raise ValueError(f"data.json: the game has no table '{table}' (the Game data page lists the ones it has)")
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
                ctx.edit_csv(table, edits, source=mod.id)
                tables.add(table)
        if tables:
            ctx.note("tables", sorted(tables))
