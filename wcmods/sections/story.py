"""Cats and questlines of a mod's own (npcs.json and quests.json), made on Clan Mod Studio's Characters and
Questlines pages; story.py has the format. They're data, not code: every enabled mod's go into one small
UE4SS mod, WCModsStory, which hands them to the game's other scripts as the shared variable WCMods.story
(JSON text). The Sandbox mode mod reads it and puts the cats in the forest with a sandbox cat.
"""
import os

from .. import story
from ..sdk import Section, lua_value

UE4SS_NAME = "WCModsStory"


def script(text):
    """The WCModsStory mod's main.lua: the cats and questlines, shared with the game's other scripts."""
    return ("-- Written by wcmods: the cats and questlines of your mods (npcs.json, quests.json), for the Sandbox\n"
            "-- mode mod to bring into the game. Change them on Clan Mod Studio's Characters and Questlines pages.\n"
            f"local STORY = {lua_value(text)}\n"
            f"local ok, err = pcall(function() ModRef:SetSharedVariable({lua_value(story.SHARED_VARIABLE)}, STORY) end)\n"
            'if not ok then print("[WCModsStory] couldn\'t share the cats and questlines: " .. tostring(err) .. "\\n") end\n')


def _icon(row):
    """An item row's icon as the texture's asset path ("/Game/.../T_X.T_X"), or None."""
    icon = row.get("Icon")
    if isinstance(icon, dict) and icon.get("package") and icon.get("asset"):
        return f"{icon['package']}.{icon['asset']}"
    return None


class StorySection(Section):
    id = "story"
    title = "Characters and questlines"
    files = story.FILES

    def collect(self, mod, ctx):
        raw = {name: self.read_json(mod, name) if os.path.isfile(os.path.join(mod.folder, name)) else None
               for name in story.FILES}
        data = story.read(raw["npcs.json"], raw["quests.json"])
        return data if data["npcs"] or data["quests"] else None

    def build(self, ctx, items):
        if not items:
            return
        if not any(m.id == story.SANDBOX_ID for m in ctx.mods):
            ctx.warn("cats and questlines come into the game with the Sandbox mode mod (github.com/HexOffender/"
                     "wcmods-sandbox), and it isn't on; they go in, but nothing shows them until it is")
        # Items the quests name: the game's, or one a mod adds (the items section comes first and adds a row for
        # each item it makes, so its rows here are every mod item), with their icons.
        icons = {v.get("itemTag"): _icon(v) for _, v in ctx.cooked_table("DT_QuestObjectsInfo")}
        for _, v, _, _ in ctx.table_rows.get("DT_QuestObjectsInfo", []):
            icons[v.get("itemTag")] = _icon(v)
        known = set(icons)
        used = set()
        for mod, data in items:
            used |= story.items_used(data)
            for tag in sorted(story.items_used(data) - known):
                ctx.warn(f"{mod.id}: quests.json names the item {tag}, which the game hasn't got (and no mod adds)")
        icons = {tag: icons[tag] for tag in sorted(used) if icons.get(tag)}
        ctx.add_ue4ss_mod(UE4SS_NAME, {"Scripts/main.lua": script(story.bundle(items, icons)), "enabled.txt": ""})
        ctx.note("story", {mod.id: {"npcs": [c["id"] for c in data["npcs"]], "quests": [q["id"] for q in data["quests"]]}
                           for mod, data in items})
