"""Mouse look (mouselook.json), shipped as a UE4SS script that turns the game's camera."""
import os

from .. import mouselook
from ..sdk import Section


class MouseLookSection(Section):
    id = "mouselook"
    title = "Mouse look"
    files = ("mouselook.json",)

    def collect(self, mod, ctx):
        return mouselook.validate(self.read_json(mod, "mouselook.json"))

    def build(self, ctx, items):
        if not items:
            return
        settings = mouselook.merge([data for _, data in items], [mod.id for mod, _ in items])
        # The in-game menu saves into the mod whose settings win: the one with the highest priority.
        top = items[-1][0]
        save = {"path": os.path.abspath(os.path.join(top.folder, "mouselook.json")),
                "file": f"mods/{top.id}/mouselook.json",
                "keep": {k: v for k, v in self.read_json(top, "mouselook.json").items() if k.startswith("_")}}
        ctx.add_ue4ss_mod(mouselook.UE4SS_MOD_NAME, {"Scripts/main.lua": mouselook.script(settings, save),
                                                     "enabled.txt": ""})
        ctx.note("mouselook", settings)
