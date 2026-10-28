"""world.place_names: the game's area names and quest titles, which WCModsNames gives the mod menu's pages
(N.area, N.quest), read from small copies of the game's text tables."""
from wcmods import luacheck, world

STRINGS = "Wrc/Content/Gameplay/Strings/NonAsset/Strings_EN.csv"
BASE = "Wrc/Content/Gameplay/DataTables/NonAsset/"
EN = """Key,SourceString
STR_RIVERCLAN_ZONE_5,Willow-Weep
QST_Gather.Apprentice.Title,Feathering the Nests
QST_Gather.Apprentice.Title2,Feathering the Nests (again)
QST_Gather.Warrior.Title,Preparation is Readiness!
QST_RankUp.Apprentice.Title,The Proving Grounds
QST_Rest1.Title,A Time to Rest
"""
LOCATIONS = """---,Code,LocationType,IdStrName
1,R-05,Riverclan,STR_RIVERCLAN_ZONE_5
2,R-06
"""
HEAD = "---,Score,ClanBonding,Talker,Trait,VoiceOver,StringKey,DebugText"
QUESTS = "\n".join([
    HEAD,
    "Quest.Procedural.Survival.Gather.Apprentice.Title,0,0,NPC,None,vo,QST_Gather.Apprentice.Title,x",
    "Quest.Procedural.Survival.Gather.Apprentice.Title2,0,0,NPC,None,vo,QST_Gather.Apprentice.Title2,x",
    "Quest.Procedural.Survival.Gather.Warrior.Title,0,0,NPC,None,vo,QST_Gather.Warrior.Title,x",
    "Quest.Procedural.Progression.RankUp.Title,0,0,NPC,None,vo,QST_RankUp.Apprentice.Title,x",
    "Quest.Procedural.Sleep.Rest1.Title,0,0,NPC,None,vo,QST_Rest1.Title,x",
]) + "\n"


def reader(files):
    def read(path):
        if path not in files:
            raise KeyError(f"game file {path}")
        return files[path]
    return read


GAME = {STRINGS: EN, BASE + "LocationsData.csv": LOCATIONS, BASE + "QuestDialogues.csv": QUESTS}


def test_place_names_reads_areas_and_ranked_quest_titles():
    areas, quests = world.place_names(reader(GAME))
    assert areas == {"R-05": "Willow-Weep"}   # a short row (no name key) is left out
    assert quests["Quest.Procedural.Survival.Gather"] == {"Apprentice": "Feathering the Nests",
                                                          "Warrior": "Preparation is Readiness!"}   # .Title2 rows aren't titles


def test_place_names_rankup_titles():
    """A title with no rank segment is its quest's own, under its whole tag, not a quest cut short with the last
    segment as its rank (RankUp's title was filed under Progression, as rank "RankUp")."""
    _, quests = world.place_names(reader(GAME))
    assert quests["Quest.Procedural.Progression.RankUp"] == {"": "The Proving Grounds"}
    assert quests["Quest.Procedural.Sleep.Rest1"] == {"": "A Time to Rest"}
    assert "Quest.Procedural.Progression" not in quests and "Quest.Procedural.Sleep" not in quests


def test_place_names_without_the_text_table_gives_nothing():
    assert world.place_names(reader({})) == ({}, {})


def test_names_lua_takes_a_title_with_no_rank():
    lua = world.names_lua(places=world.place_names(reader(GAME)))
    assert '["Quest.Procedural.Progression.RankUp"] = { [""] = "The Proving Grounds" }' in lua
    assert not luacheck.check(lua)
