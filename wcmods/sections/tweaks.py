"""Tweaks (tweaks.json), shipped as wcmods' own UE4SS script (lua/tweaks.lua): no code of the mod's own runs."""
import os

from .. import menusettings, tweaks
from ..sdk import Section


class TweaksSection(Section):
    id = "tweaks"
    title = "Tweaks"
    files = (tweaks.FILE,)

    def collect(self, mod, ctx):
        return tweaks.validate(self.read_json(mod, tweaks.FILE), menusettings.menu_settings(ctx.cfg)["key"])

    def build(self, ctx, items):
        if not items:
            return
        settings = tweaks.merge([data for _, data in items])
        # The page in the mod menu saves into the mod whose tweaks win: the one with the highest priority.
        top = items[-1][0]
        save = {"path": os.path.abspath(os.path.join(top.folder, tweaks.FILE)), "file": f"mods/{top.id}/{tweaks.FILE}",
                "keep": {k: v for k, v in self.read_json(top, tweaks.FILE).items() if k.startswith("_")}}
        menu_key = menusettings.menu_settings(ctx.cfg)["key"]
        ctx.add_ue4ss_mod(tweaks.UE4SS_MOD_NAME, {"Scripts/main.lua": tweaks.script(settings, save, menu_key),
                                                  "enabled.txt": ""})
        ctx.note("on", {k: v for k, v in settings.items() if v != tweaks.DEFAULTS[k]})   # the Installed mods page's
