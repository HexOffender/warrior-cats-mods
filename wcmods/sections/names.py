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

A rename that would leave a cat with no text in the game is left out with a warning (names.Plan.plan_cats),
so a cat never shows as <MISSING STRING TABLE ENTRY> because of this section.
"""
import os

from .. import names
from ..formats.save import SAV_NAME, SaveGame
from ..formats.savejson import SaveDoc
from ..sdk import Section


class NamesSection(Section):
    id = "names"
    title = "Names"
    files = ("names.json",)

    def collect(self, mod, ctx):
        return names.validate(self.read_json(mod, "names.json")) or None

    def build(self, ctx, items):
        if not items:
            return
        spec = names.merge(data for _, data in items)
        source = ", ".join(mod.id for mod, _ in items)
        game = names.GameNames(lambda path: ctx.game.read_text(ctx.data_path(path)))
        plan = names.Plan(game, spec)
        ops = []
        if plan.renames:
            sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
            if os.path.isfile(sav):
                try:
                    doc = SaveDoc(SaveGame.load(sav).json_text)
                    ops = plan.plan_cats(names.cats_in_save(doc.data))
                except (ValueError, OSError):   # a save wcmods can't read: the names still change, in the tables
                    ctx.warn("cats: your save couldn't be read, so the cats in it weren't renamed this time")
            else:
                ctx.warn("No save yet, so no cats are renamed: start the game once, then apply again")
        for w in plan.warnings:
            ctx.warn(w)
        for table, edits in plan.edits.items():
            ctx.edit_csv(table, edits, source=source)
        for op in ops:
            ctx.save_op(dict(op, source=source))
        ctx.note("names", {"tables": sorted(plan.edits), "added_texts": len(plan.added_keys),
                           "cats": [f"{a} -> {b}" for a, b in plan.cat_renames]})
