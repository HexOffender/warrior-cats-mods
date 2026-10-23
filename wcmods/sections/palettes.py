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
        merged = palettes.merge([data for _, data in items])
        if "eyes" in merged:
            if ctx.game.oodle is None:
                raise RuntimeError("eye palettes need the Oodle DLL to read the game's eye atlas")
            atlas = eyeatlas.EyeAtlas(ctx.read_game_file(eyeatlas.PATH))
            # A misspelled slot in one mod skips just that entry, not every mod's palette.
            for mod, data in items:
                for key in data.get("eyes", {}):
                    try:
                        atlas.slot(key)
                    except KeyError:
                        ctx.warn(f"{mod.id}: '{key}' isn't an eye slot (see `wcmods eyes`); skipped it")
                        merged["eyes"].pop(key, None)
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
