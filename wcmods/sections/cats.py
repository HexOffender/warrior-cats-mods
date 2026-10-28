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
        if not items:   # nothing to do, so the save isn't read (one wcmods can't read mustn't stop other mods)
            return
        merged = catcolours.merge(data for _, data in items)
        source = ", ".join(mod.id for mod, _ in items)
        player = {**EMPTY, **merged.get("player", {})}
        sav = os.path.join(ctx.cfg.save_dir, SAV_NAME)
        unreadable = False
        try:
            cats = names.cats_in_save(SaveDoc(SaveGame.load(sav).json_text).data) if os.path.isfile(sav) else []
        except (ValueError, OSError):
            ctx.warn("your save couldn't be read, so the changes to cats in it were skipped (your cat's colours "
                     "still go in)")
            cats, unreadable = [], True
        # Lowest priority first; none while the save can't be read (other cats are found in it).
        per_mod = [data.get("cats", {}) for _, data in items if data.get("cats")] if not unreadable else []
        plan = self._plan(ctx) if per_mod and cats else None
        others = self._others(ctx, plan, per_mod, cats, os.path.isfile(sav))
        coloured = self._coloured(ctx, plan, others, cats)
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
            if player["colours"] and not cats and not unreadable:
                ctx.warn("your cat's colours: no save yet, so they show only once you're in the world")
        added = palettes.added_slots(ctx.mods)
        self._check(ctx, "your cat", player, added)
        if any(player[k] for k in ("slots", "scars", "look")) and not unreadable:
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
    def _plan(ctx):
        """The cats' names after the enabled names mods (a cat one renames is found by its new name too)."""
        game = names.GameNames(lambda path: ctx.game.read_text(ctx.data_path(path)))
        try:
            return names.Plan(game, names.merge(names.mod_specs(ctx.mods)))
        except ValueError:          # a broken names.json, which the names section reports
            return names.Plan(game, names.merge([]))

    @staticmethod
    def _others(ctx, plan, per_mod, cats, have_save):
        """[(targets, cat, look)] for cats.json's "cats" (each mod's, lowest priority first): each name or place
        found in the save (every cat called that, as names.json's "cats" finds them). Without a slot first, a
        name or place means the game being played."""
        if not per_mod:
            return []
        if not have_save:
            wanted = sorted({t for m in per_mod for t in m})
            ctx.warn(f"cats: no save yet, so {', '.join(wanted)} can't be found; start the game once, then install again")
            return []
        found, said = {}, set()   # a cat's first path -> (the targets that found it, the cat, its look): one edit a cat
        for wanted in per_mod:
            for target, one in wanted.items():
                hits = [c for c in plan.cats_called(target, cats) if not c["player"]]
                if names.slot_of(target) is None:
                    elsewhere = sorted({c["slot"] for c in hits if not c["current"]})
                    hits = [c for c in hits if c["current"]]
                    if not hits and elsewhere and target not in said:
                        said.add(target)
                        ctx.warn(f"cats: '{target}' isn't in the game you're playing; for game {elsewhere[0]}'s, put "
                                 f"its slot first ('{elsewhere[0]}/{target}')")
                        continue
                if not hits:
                    if target not in said:
                        said.add(target)
                        ctx.warn(f"cats: no cat in your save is called '{target}' (the Your cat page lists them, with "
                                 "their places)")
                    continue
                if len(hits) > 1 and not names.by_place(target) and target not in said:
                    said.add(target)
                    ctx.warn(f"cats: {len(hits)} cats are called '{target}', and all of them change; name one by its "
                             f"place to change just it ({', '.join(names.place(c['paths'][0]) for c in hits[:4])})")
                for cat in hits:
                    # A cat a name and a place both find takes both; a later mod wins part by part.
                    targets, _, look = found.setdefault(cat["paths"][0], ([], cat, {k: {} for k in EMPTY}))
                    if target not in targets:
                        targets.append(target)
                    for key in EMPTY:
                        look[key].update(one.get(key, {}))
        return [(" and ".join(targets), cat, look) for targets, cat, look in found.values()]

    @staticmethod
    def _coloured(ctx, plan, others, cats):
        """{name key: colours} for the script: the cats found in the game being played (the script tells cats
        apart by their name IDs only, whatever the game), by the IDs they'll have after this install's renames."""
        renamed = {}
        if plan is not None and plan.renames:
            for op in plan.plan_cats(cats):
                if op.get("op") == "name":
                    renamed[op["path"]] = op["set"]
        key = lambda cat: catcolours.name_key({"ids": {**cat["ids"], **renamed.get(cat["paths"][0], {})}})   # noqa: E731
        sharing = {}
        for cat in cats:
            if cat["current"] and not cat["player"]:
                sharing.setdefault(key(cat), []).append(cat)
        out = {}
        for targets, cat, one in others:
            if not one["colours"]:
                continue
            if not cat["current"]:
                ctx.warn(f"cats: {targets}: colours go on only in the game being played, so game {cat['slot']}'s "
                         "cat gets its slots, scars and shape but not its colours")
                continue
            k = key(cat)
            if len(sharing.get(k, [])) > 1:
                ctx.warn(f"cats: {targets}: its colours go on every cat with its name ({len(sharing[k])} in this game): "
                         "the game tells them apart only by their names")
            out[k] = one["colours"]
        return out

    @staticmethod
    def _check(ctx, who, one, added):
        slots, scars = one["slots"], one["scars"]
        if slots.get("fur") in catcolours.FERAL_SLOTS:
            ctx.warn(f"{who}: coat colour {slots['fur']} is one of the Feral Edition's; without it the game gives "
                     "another")
        for part in ("pattern", "marking"):
            slot = slots.get(part)
            if slot is not None and slot >= palettes.GAME_SLOTS and slot not in added.get(part, set()):
                ctx.warn(f"{who}: {part} colour {slot} is a new colour no palette that's on adds, so it shows none")
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
