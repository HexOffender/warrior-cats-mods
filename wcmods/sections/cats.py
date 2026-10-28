"""Cats' looks (cats.json): colours only your cat (or a cat you name) wears, by a UE4SS script, and which
colour slots, scars and shape it has, in your save. See catcolours.py."""
import os

from .. import catcolours, names, palettes
from ..formats.save import SAV_NAME, SaveGame
from ..formats.savejson import SaveDoc
from ..sdk import Section

EMPTY = {"colours": {}, "slots": {}, "scars": {}, "look": {}}


class CatsSection(Section):
    id = "cats"
    title = "Your cat"
    files = ("cats.json",)
    appearance_only = True

    def collect(self, mod, ctx):
        return catcolours.validate(self.read_json(mod, "cats.json")) or None

    def build(self, ctx, items):
        merged = catcolours.merge(data for _, data in items)
        source = ", ".join(mod.id for mod, _ in items)
        player = {**EMPTY, **merged.get("player", {})}
        sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
        cats = names.cats_in_save(SaveDoc(SaveGame.load(sav).json_text).data) if os.path.isfile(sav) else []
        others = self._others(ctx, merged.get("cats", {}), cats, os.path.isfile(sav))
        coloured = {catcolours.name_key(cat): one["colours"] for _, cat, one in others if one["colours"]}
        if player["colours"] or coloured:
            if ctx.cfg.ue4ss_mods_dir:
                key_file = os.path.join(ctx.cfg.ue4ss_mods_dir, catcolours.UE4SS_MOD_NAME, "yourcat.txt")
                # The in-game menu saves into the mod whose colours win: the one with the highest priority.
                top = items[-1][0]
                save = {"path": os.path.abspath(os.path.join(top.folder, "cats.json")),
                        "file": f"mods/{top.id}/cats.json", "doc": self.read_json(top, "cats.json")}
                script = catcolours.script(player["colours"], catcolours.save_key(cats), key_file,
                                           debug=bool(ctx.cfg.data.get("debug_cat_look")), save=save, others=coloured)
                ctx.add_ue4ss_mod(catcolours.UE4SS_MOD_NAME, {"Scripts/main.lua": script, "enabled.txt": ""})
            else:
                ctx.warn("cats' own colours need UE4SS, which isn't installed")
            if player["colours"] and not cats:
                ctx.warn("your cat's colours: no save yet, so they show only once you're in the world")
        added = _new_slots(ctx.mods)
        self._check(ctx, "your cat", player, added)
        if any(player[k] for k in ("slots", "scars", "look")):
            if not os.path.isfile(sav):
                ctx.warn("your cat's slots, scars or look: no save yet; start the game once, then install again")
            else:
                mine = [c for c in cats if c["player"] and c["current"]]   # the game being played, not every slot's cat
                for cat in mine:
                    self._write(ctx, cat, player, source, "your cat")
                if not mine:
                    ctx.warn("your cat's slots, scars or look: your save has no player cat yet")
        for target, cat, one in others:
            who = f"{target} ({names.place(cat['paths'][0])})" if "/" not in target else target
            self._check(ctx, who, one, added)
            if any(one[k] for k in ("slots", "scars", "look")):
                self._write(ctx, cat, one, source, who)
        ctx.note("cat", {"colours": sorted(player["colours"]), "slots": player["slots"], "scars": sorted(player["scars"]),
                         "look": player["look"]})
        if others:
            ctx.note("cats", sorted({f"{t} -> {names.place(c['paths'][0])}" for t, c, _ in others}))

    @staticmethod
    def _others(ctx, wanted, cats, have_save):
        """[(target, cat, look)] for cats.json's "cats": each name or place found in the save (every cat called
        that, as names.json's "cats" finds them)."""
        if not wanted:
            return []
        if not have_save:
            ctx.warn(f"cats: no save yet, so {', '.join(sorted(wanted))} can't be found; start the game once, then "
                     "install again")
            return []
        plan = names.Plan(names.GameNames(lambda path: ctx.game.read_text(ctx.data_path(path))), names.merge([]))
        found = {}    # a cat's first path -> (the targets that found it, the cat, its look): one edit a cat
        for target, one in wanted.items():
            hits = [c for c in plan.cats_called(target, cats) if not c["player"]]
            if not hits:
                ctx.warn(f"cats: no cat in your save is called '{target}' (the Names page lists them, with their places)")
                continue
            if len(hits) > 1 and not names.by_place(target):
                ctx.warn(f"cats: {len(hits)} cats are called '{target}', and all of them change; name one by its "
                         f"place to change just it ({', '.join(names.place(c['paths'][0]) for c in hits[:4])})")
            for cat in hits:
                # A cat a name and a place both find takes both, the later entry winning part by part.
                targets, _, look = found.setdefault(cat["paths"][0], ([], cat, {k: {} for k in EMPTY}))
                targets.append(target)
                for key in EMPTY:
                    look[key].update(one.get(key, {}))
        return [(" and ".join(targets), cat, look) for targets, cat, look in found.values()]

    @staticmethod
    def _check(ctx, who, one, added):
        slots, scars = one["slots"], one["scars"]
        if slots.get("fur") in catcolours.FERAL_SLOTS:
            ctx.warn(f"{who}: coat slot {slots['fur']} is one of the Feral Edition's; without it the game gives "
                     "another")
        for part in ("pattern", "marking"):
            slot = slots.get(part)
            if slot is not None and slot >= palettes.GAME_SLOTS and slot not in added.get(part, set()):
                ctx.warn(f"{who}: {part} slot {slot} isn't added by any enabled palette, so it shows no colour")
        for part, n in sorted(scars.items()):
            if n > len(catcolours.SCAR_TYPES[part]):
                ctx.warn(f"{who}: {part} scar {n} seems to show nothing (the game has no scar for it); its scars "
                         f"are {', '.join(catcolours.SCAR_NAMES[part])}")

    @staticmethod
    def _write(ctx, cat, one, source, who):
        """The fields a cat's slots, scars and look set, into every copy of it in the save."""
        slots, scars, look = one["slots"], one["scars"], one["look"]
        label = [f"{p} slot {s}" for p, s in sorted(slots.items())]
        if scars and not any(scars.values()) and len(scars) == len(catcolours.SCARS):
            label.append("no scars")
        else:
            label += [f"{p} scar " + ("none" if not n else catcolours.SCAR_TYPES[p][n - 1][0]
                                      if n <= len(catcolours.SCAR_TYPES[p]) else str(n))
                      for p, n in sorted(scars.items())]
        label += [f"{f} {v:g}" for f, v in sorted(look.items()) if f != "FurIdx"]
        for path in cat["paths"]:
            ctx.save_op({"op": "fields", "path": path, "set": catcolours.fields_of(one), "source": source,
                         "label": ", ".join(label), "who": who})


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
