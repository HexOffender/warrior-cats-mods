"""Cat names (names.json): rename, add and remove prefixes, suffixes and rogue names, edit the ban list
and any name the game shows, and rename cats in your save. See names.py for how the game names cats.

    {
      "prefixes": { "rename": { "Otter": "Moth" }, "add": { "Sparrow": { "like": "Wren" } }, "remove": ["Pigeon"] },
      "suffixes": { "rename": { "pelt": "coat" }, "add": { "whisper": {} }, "remove": ["face"] },
      "rogues":   { "rename": { "Chesnut": "Chestnut" }, "add": ["Moss"], "remove": ["Fury"] },
      "banned":   { "add": ["Lionheart"], "remove": ["Tigerstar"] },
      "names":    { "Brightheart": "Brightfur" },
      "cats":     { "player": "Mothheart", "Ripplestorm": { "fixed": "Sparkle" } }
    }
"""
import os

from .. import names
from ..save import SAV_NAME, SaveGame
from ..savejson import SaveDoc
from ..sdk import Section


class NamesSection(Section):
    id = "names"
    title = "Names"
    files = ("names.json",)

    def collect(self, mod, ctx):
        return names.validate(self.read_json(mod, "names.json")) or None

    def build(self, ctx, items):
        spec = names.merge(data for _, data in items)
        source = ", ".join(mod.id for mod, _ in items)
        game = names.GameNames(lambda path: ctx.game.read_text(ctx.data_path(path)))
        plan = names.Plan(game, spec)
        ops = []
        if plan.renames:
            sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
            if os.path.isfile(sav):
                doc = SaveDoc(SaveGame.load(sav).json_text)
                ops = plan.plan_cats(names.cats_in_save(doc.data))
            else:
                ctx.warn("cats: no save yet; start the game once, then install again to rename cats")
        for w in plan.warnings:
            ctx.warn(w)
        for table, edits in plan.edits.items():
            ctx.edit_csv(table, edits, source=source)
        for op in ops:
            ctx.save_op(dict(op, source=source))
        ctx.note("names", {"tables": sorted(plan.edits), "added_texts": len(plan.added_keys),
                           "cats": [f"{a} -> {b}" for a, b in plan.cat_renames]})
