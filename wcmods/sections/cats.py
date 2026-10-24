"""Your cat (cats.json): colours only your cat wears, by a UE4SS script, and which colour slots it uses,
in your save. See catlook.py."""
import os

from .. import catlook, names
from ..save import SAV_NAME, SaveGame
from ..savejson import SaveDoc
from ..sdk import Section


class CatsSection(Section):
    id = "cats"
    title = "Your cat"
    files = ("cats.json",)
    appearance_only = True

    def collect(self, mod, ctx):
        return catlook.validate(self.read_json(mod, "cats.json")) or None

    def build(self, ctx, items):
        merged = catlook.merge(data for _, data in items)
        source = ", ".join(mod.id for mod, _ in items)
        player = merged.get("player", {"colours": {}, "slots": {}})
        sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
        cats = names.cats_in_save(SaveDoc(SaveGame.load(sav).json_text).data) if os.path.isfile(sav) else []
        if player["colours"]:
            if ctx.cfg.ue4ss_mods_dir:
                script = catlook.script(player["colours"], catlook.save_key(cats), debug=bool(ctx.cfg.data.get("debug_cat_look")))
                ctx.add_ue4ss_mod(catlook.UE4SS_MOD_NAME, {"Scripts/main.lua": script, "enabled.txt": ""})
            else:
                ctx.warn("your cat's colours need UE4SS, which isn't installed")
            if not cats:
                ctx.warn("your cat's colours: no save yet, so they show only once you're in the world")
        slots = player["slots"]
        if slots.get("fur") in catlook.FERAL_SLOTS:
            ctx.warn(f"coat slot {slots['fur']} is one of the Feral Edition's; without it the game gives your cat another")
        if slots:
            if not os.path.isfile(sav):
                ctx.warn("your cat's colour slots: no save yet; start the game once, then install again")
            else:
                mine = [c for c in cats if names.PLAYER_PATH in c["paths"]]
                fields = {catlook.SLOTS[part]: slot for part, slot in slots.items()}
                for cat in mine:
                    for path in cat["paths"]:   # every copy of your cat in the save
                        ctx.save_op({"op": "fields", "path": path, "set": fields, "source": source,
                                     "label": ", ".join(f"{p} slot {s}" for p, s in sorted(slots.items()))})
                if not mine:
                    ctx.warn("your cat's colour slots: your save has no player cat yet")
        ctx.note("cat", {"colours": sorted(player["colours"]), "slots": slots})
