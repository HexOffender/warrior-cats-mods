"""Your cat (cats.json): colours only your cat wears, by a UE4SS script, and which colour slots it uses,
in your save. See catlook.py."""
import os

from .. import catlook, names, palettes
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
        player = merged.get("player", {"colours": {}, "slots": {}, "scars": {}})
        sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
        cats = names.cats_in_save(SaveDoc(SaveGame.load(sav).json_text).data) if os.path.isfile(sav) else []
        if player["colours"]:
            if ctx.cfg.ue4ss_mods_dir:
                key_file = os.path.join(ctx.cfg.ue4ss_mods_dir, catlook.UE4SS_MOD_NAME, "yourcat.txt")
                # The in-game menu saves into the mod whose colours win: the one with the highest priority.
                top = items[-1][0]
                save = {"path": os.path.abspath(os.path.join(top.folder, "cats.json")),
                        "file": f"mods/{top.id}/cats.json", "doc": self.read_json(top, "cats.json")}
                script = catlook.script(player["colours"], catlook.save_key(cats), key_file,
                                        debug=bool(ctx.cfg.data.get("debug_cat_look")), save=save)
                ctx.add_ue4ss_mod(catlook.UE4SS_MOD_NAME, {"Scripts/main.lua": script, "enabled.txt": ""})
            else:
                ctx.warn("your cat's colours need UE4SS, which isn't installed")
            if not cats:
                ctx.warn("your cat's colours: no save yet, so they show only once you're in the world")
        slots = player["slots"]
        if slots.get("fur") in catlook.FERAL_SLOTS:
            ctx.warn(f"coat slot {slots['fur']} is one of the Feral Edition's; without it the game gives your cat another")
        added = _new_slots(ctx.mods)
        for part in ("pattern", "marking"):
            slot = slots.get(part)
            if slot is not None and slot >= palettes.GAME_SLOTS and slot not in added.get(part, set()):
                ctx.warn(f"your cat's {part} slot {slot} isn't added by any enabled palette, so it shows no colour")
        scars = player.get("scars", {})
        if slots or scars:
            what = "your cat's colour slots" if not scars else "your cat's scars" if not slots else \
                "your cat's colour slots and scars"
            if not os.path.isfile(sav):
                ctx.warn(f"{what}: no save yet; start the game once, then install again")
            else:
                mine = [c for c in cats if names.PLAYER_PATH in c["paths"]]
                fields = {catlook.SLOTS[part]: slot for part, slot in slots.items()}
                fields.update({catlook.SCARS[part]: n for part, n in scars.items()})
                label = [f"{p} slot {s}" for p, s in sorted(slots.items())]
                if scars and not any(scars.values()) and len(scars) == len(catlook.SCARS):
                    label.append("no scars")
                else:
                    label += [f"{p} scar {n or 'none'}" for p, n in sorted(scars.items())]
                for cat in mine:
                    for path in cat["paths"]:   # every copy of your cat in the save
                        ctx.save_op({"op": "fields", "path": path, "set": fields, "source": source,
                                     "label": ", ".join(label)})
                if not mine:
                    ctx.warn(f"{what}: your save has no player cat yet")
        ctx.note("cat", {"colours": sorted(player["colours"]), "slots": slots, "scars": sorted(scars)})


def _new_slots(mods):
    """{part: {slot, ...}} for the new colour slots the enabled palettes add."""
    out = {}
    for mod in mods:
        path = os.path.join(mod.folder, "palette.json")
        if os.path.isfile(path):
            try:
                for part, found in palettes.new_slots(palettes.load(path)).items():
                    out.setdefault(part, set()).update(found)
            except ValueError:
                continue   # the palette section reports a broken palette.json
    return out
