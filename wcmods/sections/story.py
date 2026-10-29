"""Cats and questlines of a mod's own (npcs.json and quests.json), made on Clan Mod Studio's Characters and
Questlines pages; story.py has the format. They're data, not code: every enabled mod's go into one small
UE4SS mod, WCModsStory, which hands them to the game's other scripts as the shared variable WCMods.story
(JSON text). The Sandbox mode mod reads it and puts the cats in the forest with a sandbox cat.

At Apply the build fills in each step's objective that its maker left empty, with the names the cats and
items have then, and says what Sandbox mode can show of them (story.sandbox): missing, off, left out after
a game update (until "Use it anyway"), kept out by "Allow mods that run code", or too old for a fixed look.
"""
import os

from .. import palettes, story
from ..mods import version_key
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


def _name(ctx, value):
    """An item row's Name (an FText) as words: a mod's own text as it is, the game's through its strings."""
    if not isinstance(value, dict):
        return None
    if value.get("ns") == "WCMods" or not value.get("key"):
        return value.get("text") or None
    try:
        said = ctx.text(value["key"])
    except Exception:   # noqa: BLE001 - the game's strings can't be read: the tag's own words instead
        said = value["key"]
    return said if said != value["key"] else value.get("text") or None


def _sandbox_words(state):
    """What the cats and questlines wait for, when Sandbox mode can't show them, or None."""
    if state["state"] == "missing":
        return ("cats and questlines go in, but nothing shows them until Sandbox mode is added and on (download "
                f"it from {story.SANDBOX_RELEASES} and drop it on the Mods page)")
    if state["state"] == "off":
        return "cats and questlines go in, but nothing shows them until Sandbox mode is on (the Mods page switches it on)"
    if state["state"] == "held-back":
        return f"cats and questlines go in, but nothing shows them: {story.held_words(state['held'])}"
    if state["state"] == "no-code":
        return ("cats and questlines go in, but nothing shows them: Sandbox mode is a script, and mods that run code "
                "aren't allowed (allow them on Settings and repair)")
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
        state = story.sandbox(ctx.found or ctx.mods, bool(ctx.cfg.data.get("allow_code_mods")), ctx.held_back)
        said = _sandbox_words(state)
        if said:
            ctx.warn(said)
        # Items the quests name: the game's, or one a mod adds (the items section comes first), with their icons
        # and names.
        icons, names = {}, {}
        rows = [v for _, v in ctx.cooked_table("DT_QuestObjectsInfo")]
        rows += [v for _, v, _, _ in ctx.table_rows.get("DT_QuestObjectsInfo", [])]
        for v in rows:
            tag = v.get("itemTag")
            icons[tag] = _icon(v)
            names[tag] = _name(ctx, v.get("Name")) or names.get(tag)
        known = set(icons) | set(ctx.notes.get("items", {}).get("items", []))
        added = palettes.added_slots(ctx.mods)
        used = set()
        for mod, data in items:
            used |= story.items_used(data)
            for tag in sorted(story.items_used(data) - known):
                ctx.warn(f"{mod.id}: quests.json names the item {tag}, which the game hasn't got (and no mod adds)")
            for cat in data["npcs"]:
                self._check_cat(ctx, mod, cat, added, state)
            cat_names = {c["id"]: c["name"] for c in data["npcs"]}
            for q in data["quests"]:
                for step in q["steps"]:
                    if not step.get("objective"):
                        step["objective"] = story.objective(step, lambda i: cat_names.get(i, i),
                                                            lambda t: names.get(t) or story.item_words(t))
        icons = {tag: icons[tag] for tag in sorted(used) if icons.get(tag)}
        ctx.add_ue4ss_mod(UE4SS_NAME, {"Scripts/main.lua": script(story.bundle(items, icons)), "enabled.txt": ""})
        ctx.note("story", {mod.id: {"npcs": [c["id"] for c in data["npcs"]], "quests": [q["id"] for q in data["quests"]]}
                           for mod, data in items})
        ctx.note("sandbox", {"state": state["state"], "version": state["version"], "older": state["older"]})

    @staticmethod
    def _check_cat(ctx, mod, cat, added, state):
        """What would make a cat look or act other than chosen: a palette's colour slot no palette that's on adds,
        or a fixed look or a patrol the installed Sandbox mode is too old for."""
        words = {"pattern": "pattern", "marking": "markings"}
        for part in ("pattern", "marking"):
            slot = cat.get("slots", {}).get(part)
            if slot is not None and slot >= palettes.GAME_SLOTS and slot not in added.get(part, set()):
                ctx.warn(f"{mod.id}: {cat['name']} wears {words[part]} colour {slot}, which no palette that's on adds, "
                         "so it shows no colour there")
        older = [f for f in state["older"] if cat.get(f)]
        if state["state"] == "missing":
            return
        for fields, what, without in ((("look", "slots"), "a fixed look", "the game makes the look up each time"),
                                      (("patrol",), "a patrol", "it stands still")):
            wanted = [story.SANDBOX_NEEDS[f] for f in older if f in fields
                      and version_key(story.SANDBOX_NEEDS[f]) is not None]
            if wanted:
                need = max(wanted, key=version_key)
                ctx.warn(f"{mod.id}: {cat['name']} has {what}, which needs Sandbox mode {need} or newer; you have "
                         f"{state['version'] or 'an older one'}, so {without}")
