"""Example: a custom quest on screen, with markers on nearby pickups and a debug panel.

It ships a UE4SS script (overlay.lua) built on the shared modules wcmods installs with every build:
WCModsDraw draws, WCModsView turns places in the world into places on screen, and WCModsWorld finds
the pickups (docs/SDK.md, "Overlays"). quest.json holds the quest and the settings.
"""
import os

from wcmods.sdk import Section, lua_value

DEFAULTS = {"title": "Custom quest", "steps": [], "pickups": True, "pickup_range": 4000, "debug_panel": True,
            "toggle_key": "F7", "waypoint_key": "F9"}


class QuestMarkers(Section):
    id = "quest-markers"
    title = "Quest markers"
    files = ("quest.json",)

    def collect(self, mod, ctx):
        data = {k: v for k, v in self.read_json(mod, "quest.json").items() if not k.startswith("_")}
        unknown = sorted(set(data) - set(DEFAULTS))
        if unknown:
            raise ValueError(f"quest.json: unknown setting(s) {', '.join(unknown)} (known: {', '.join(DEFAULTS)})")
        for i, step in enumerate(data.get("steps", []), 1):
            at = step.get("at") if isinstance(step, dict) else None
            if not (isinstance(step, dict) and isinstance(step.get("text"), str) and isinstance(at, list)
                    and len(at) == 3 and all(isinstance(v, (int, float)) for v in at)):
                raise ValueError(f'quest.json: step {i} needs "text" and "at": [x, y, z]')
        return {**DEFAULTS, **data}

    def build(self, ctx, items):
        mod, settings = items[-1]   # one quest on screen: the highest-priority mod's
        if len(items) > 1:
            ctx.warn(f"quest markers: showing {mod.id}'s quest; {', '.join(m.id for m, _ in items[:-1])} also have one")
        with open(os.path.join(mod.folder, "overlay.lua"), encoding="utf-8") as f:
            script = f.read()
        # Where the mod menu's Save writes: this mod's quest.json, notes like "_help" kept.
        save = {"path": os.path.abspath(os.path.join(mod.folder, "quest.json")), "file": f"mods/{mod.id}/quest.json",
                "doc": self.read_json(mod, "quest.json")}
        script = script.replace("@SETTINGS@", lua_value(settings)).replace("@SAVE@", lua_value(save))
        ctx.add_ue4ss_mod("WCModsQuestMarkers", {"Scripts/main.lua": script, "enabled.txt": ""})
        ctx.note("quest", {"title": settings["title"], "steps": len(settings["steps"])})
