"""Mouse look (mouselook.json), shipped as a UE4SS script that turns the game's camera."""
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
        ctx.add_ue4ss_mod(mouselook.UE4SS_MOD_NAME, {"Scripts/main.lua": mouselook.script(settings), "enabled.txt": ""})
        ctx.note("mouselook", settings)
