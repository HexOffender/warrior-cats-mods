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


def item_names(ctx, text=None):
    """{item tag: its English name} from the game's item table and the rows mods add to it ("Marigold",
    not the "Medium Healing Herb" of its pickup's class). text(key): the English text to read the names from
    (the build's own Strings_EN, with its renames); the game's, ctx.text, without one."""
    text = text or ctx.text
    rows = [v for _, v in ctx.cooked_table("DT_QuestObjectsInfo")]
    rows += [v for _, v, _, _ in ctx.table_rows.get("DT_QuestObjectsInfo", [])]   # later rows win
    out = {}
    for v in rows:
        name, tag = v.get("Name") or {}, v.get("itemTag")
        said = name.get("text") if "text" in name else text(name["key"]) if "key" in name else None
        if tag and said and said != name.get("key"):
            out[tag] = said
    return out


QUEST_RANKS = ("Apprentice", "Warrior", "Deputy", "Leader")   # a quest title's rank segment, when it has one
STRINGS_EN = "Wrc/Content/Gameplay/Strings/NonAsset/Strings_EN.csv"
TABLES = "Wrc/Content/Gameplay/DataTables/NonAsset/"


def place_texts(read_text):
    """The game's areas and quest titles with the text key each is shown from (which names.json's "text"
    renames): {"areas": [{"key", "code", "text"}] ("STR_RIVERCLAN_ZONE_5", "R-05", "Willow-Weep"), "quests":
    [{"key", "tag", "quest", "rank", "text"}]}. A quest title's tag ends in its rank (Apprentice, Warrior,
    Deputy or Leader: its title can change with your cat's rank), or has none (rank "": RankUp's title is
    under Quest.Procedural.Progression.RankUp.Title whatever the rank); "quest" is the tag's last part
    ("Gather"). Only .Title rows are titles (.Title2 is a line of the quest's). A title with no text in
    Strings_EN (the Escort quests') is left out, so nothing shows its key; so is a row too short to say its
    name, and a table that can't be read leaves its names out."""
    from .formats import csvdata
    areas, quests = [], []
    try:
        strings = csvdata.Table(read_text(STRINGS_EN))
        en = {r.fields[0]: r.fields[1] for r in strings.rows if len(r.fields) > 1}
        locations = csvdata.Table(read_text(TABLES + "LocationsData.csv"))
        code, name = locations.column("Code"), locations.column("IdStrName")
        for r in locations.rows:
            if len(r.fields) > max(code, name):
                key = r.fields[name]
                areas.append({"key": key, "code": r.fields[code], "text": en.get(key, r.fields[code])})
        dialogues = csvdata.Table(read_text(TABLES + "QuestDialogues.csv"))
        column = dialogues.column("StringKey")
        for r in dialogues.rows:
            tag = r.fields[0] if r.fields else ""
            if tag.endswith(".Title") and len(r.fields) > column:
                quest, _, rank = tag[:-len(".Title")].rpartition(".")
                if rank not in QUEST_RANKS:
                    quest, rank = tag[:-len(".Title")], ""
                key = r.fields[column]
                if key in en:
                    quests.append({"key": key, "tag": quest, "quest": quest.rsplit(".", 1)[-1], "rank": rank,
                                   "text": en[key]})
    except Exception:   # no game data, or a table laid out differently: those names are left out
        pass
    return {"areas": areas, "quests": quests}


def place_names(read_text):
    """The game's area names and quest titles, from its text tables (place_texts), in the shapes WCModsNames
    uses: ({area code: name} ("R-05" -> "Willow-Weep"), {quest tag: {rank: title}}), the rank "" for a title
    with no rank segment."""
    texts = place_texts(read_text)
    quests = {}
    for q in texts["quests"]:
        quests.setdefault(q["tag"], {})[q["rank"]] = q["text"]
    return {a["code"]: a["text"] for a in texts["areas"]}, quests


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
