"""Colour palettes (palette.json): eyes via the eye atlas, coat/pattern/marking/eye buttons via UE4SS."""
import os

from .. import colors, eyeatlas, palettes
from ..config import UE4SS_MOD_NAME
from ..sdk import Section


class PaletteSection(Section):
    id = "palettes"
    title = "Colour palettes"
    files = ("palette.json",)
    appearance_only = True

    def collect(self, mod, ctx):
        return palettes.load(os.path.join(mod.folder, "palette.json"))

    def build(self, ctx, items):
        palettes_in = [data for _, data in items]
        atlas = None
        if any(data.get("eyes") for data in palettes_in):
            atlas = eyeatlas.EyeAtlas(ctx.read_game_file(eyeatlas.PATH))
            # Each mod's eye keys as the rows they mean, so the later palette wins a row whatever each calls it
            # ("Amber", "iris2"); a key that isn't one of the rows skips just that entry, not every mod's palette.
            palettes_in = []
            for mod, data in items:
                rows = {}
                for key, spec in data.get("eyes", {}).items():
                    try:
                        rows[str(atlas.slot(key))] = spec
                    except KeyError as e:
                        ctx.warn(f"{mod.id}: {e.args[0]}; skipped it")
                palettes_in.append({**data, "eyes": rows} if "eyes" in data else data)
        merged = palettes.merge(palettes_in)
        if "eyes" in merged:
            changes = palettes.apply_eyes(atlas, merged["eyes"])
            for _, label, old, new in changes:
                ctx.log(f"  eyes: {label:14s} {old} -> {new}")
            # IrisColors (the cat creator's eye buttons) follows atlas rows 1-25 in order.
            swatches = merged.setdefault("iris_ui", {})
            for row, _, _, new in changes:
                if row >= 1:
                    swatches.setdefault(str(row - 1), colors.parse(new))
            ctx.patch_package(eyeatlas.PATH, atlas.bytes(), source="palettes")
            ctx.note("eyes", [{"row": r, "slot": l, "from": o, "to": n} for r, l, o, n in changes])
        runtime = {s: e for s, e in merged.items() if s in palettes.RUNTIME_SECTIONS}
        # Always shipped: with no changes it still logs the game's colour tables.
        ctx.add_ue4ss_mod(UE4SS_MOD_NAME, {"Scripts/main.lua": palettes.ue4ss_script(runtime), "enabled.txt": ""})
        ctx.note("runtime_palette", {s: sorted(e, key=int) for s, e in runtime.items()})
        groups = palettes.slot_groups(items)
        ctx.add_ue4ss_shared(palettes.GROUPS_LUA, palettes.groups_module(groups))
        if groups:
            ctx.note("new_colours", {g["id"]: {s: len(g[s]) for s in palettes.GROWABLE + ("coats",) if g[s]}
                                     for g in groups})
