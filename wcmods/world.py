"""WCModsWorld: a shared UE4SS Lua module that finds things in the game world.

Nearby pickups, interactables, quest objectives, cats and the game's managers, for overlays (with
WCModsDraw and WCModsView) and custom quests. Installed next to them as
ue4ss/Mods/shared/WCModsWorld/WCModsWorld.lua; see docs/SDK.md, "Overlays".

The kinds start from the game's base Blueprints (BP_PickupActor_Base, BP_Interactable_Base, ...): an
actor is of a kind when its class or any class it's made from is listed.
"""
from .lua import source as lua_source

SHARED_NAME = "WCModsWorld"

LUA = lua_source("world.lua")


def lua():
    return LUA


NAMES_NAME = "WCModsNames"
NAME_FN = lua_source("world_names.lua")


def item_names(ctx):
    """{item tag: its English name} from the game's item table and the rows mods add to it ("Marigold",
    not the "Medium Healing Herb" of its pickup's class)."""
    rows = [v for _, v in ctx.cooked_table("DT_QuestObjectsInfo")]
    rows += [v for _, v, _, _ in ctx.table_rows.get("DT_QuestObjectsInfo", [])]   # later rows win
    out = {}
    for v in rows:
        name, tag = v.get("Name") or {}, v.get("itemTag")
        text = name.get("text") if "text" in name else ctx.text(name["key"]) if "key" in name else None
        if tag and text and text != name.get("key"):
            out[tag] = text
    return out


def place_names(read_text):
    """The game's area names and quest titles, from its text tables: ({area code: name} ("R-05" ->
    "Willow-Weep"), {quest tag: {rank: title}}), the rank being Apprentice, Warrior, Deputy or Leader (a
    quest's title can change with your cat's rank). A table that can't be read leaves its names out."""
    from .formats import csvdata
    areas, quests = {}, {}
    try:
        strings = csvdata.Table(read_text("Wrc/Content/Gameplay/Strings/NonAsset/Strings_EN.csv"))
        en = {r.fields[0]: r.fields[1] for r in strings.rows if len(r.fields) > 1}
        base = "Wrc/Content/Gameplay/DataTables/NonAsset/"
        locations = csvdata.Table(read_text(base + "LocationsData.csv"))
        code, name = locations.column("Code"), locations.column("IdStrName")
        for r in locations.rows:
            if len(r.fields) > max(code, name):
                areas[r.fields[code]] = en.get(r.fields[name], r.fields[code])
        dialogues = csvdata.Table(read_text(base + "QuestDialogues.csv"))
        key = dialogues.column("StringKey")
        for r in dialogues.rows:
            tag = r.fields[0] if r.fields else ""
            if tag.endswith(".Title") and len(r.fields) > key:
                quest, _, rank = tag[:-len(".Title")].rpartition(".")
                quests.setdefault(quest, {})[rank] = en.get(r.fields[key], r.fields[key])
    except Exception:   # no game data, or a table laid out differently: those names are left out
        pass
    return areas, quests


def names_data(plan=None, items=None, places=None):
    """The name tables WCModsNames and the C++ SDK's cat_name share: {"prefixes", "suffixes", "whole",
    "items"}, each {id or tag: English text}, after the enabled name mods (names.Plan), and "added", a few
    text keys the mods add (N.loaded() checks the game has them); "areas" and "quests" from place_names
    (`places`). Without a plan (no game data) the tables are empty, and names come from the game's own
    text."""
    areas, quests = places or ({}, {})
    data = {"prefixes": {}, "suffixes": {}, "whole": {}, "items": dict(items or {}), "added": [],
            "areas": dict(areas), "quests": {q: dict(t) for q, t in quests.items()}}
    if plan is not None:
        data["prefixes"] = {p["id"]: p["final"] for p in plan.prefixes}
        data["suffixes"] = {s["id"]: s["final"] for s in plan.suffixes}
        whole = {r["id"]: r["final"] for r in plan.rogues}
        for key, text in plan.final.items():   # cameo cats, and cats given a name of their own by a mod
            if key.startswith("STR_CAT_NAME_ICONIC_") or key.startswith("STR_CAT_NAME_WCM"):
                whole[key] = text
        data["whole"] = whole
        # A few texts the mods add, for N.loaded(): the game has them only if it reads wcmods' pak.
        data["added"] = sorted(plan.added_keys)[:3]
    return data


def names_lua(plan=None, items=None, places=None):
    """WCModsNames: the English text of every name part and whole name, after the enabled name mods
    (names.Plan), and N.name, which WCModsGame and WCModsWorld name cats with; items' names (item_names),
    for N.item; and areas' names and quests' titles (place_names), for N.area and N.quest. Without a plan
    (no game data) the tables are empty and N.name reads the game's own text."""
    from .sdk import lua_value
    data = names_data(plan, items, places)
    return ("-- WCModsNames: the English names of cats' name parts and whole names (rogues, cameo cats, names\n"
            "-- given by mods), after your name mods, of items, areas and quests. Written by wcmods on every\n"
            "-- install; WCModsGame and WCModsWorld use it: NAMES.name(prefix id, suffix id), NAMES.item(tag),\n"
            "-- NAMES.area(code), NAMES.quest(tag, rank).\n"
            "local N = " + lua_value(data) + "\n" + NAME_FN)
