"""world.place_texts and place_names: the game's area names and quest titles with the text keys they're
shown from, which the Names page lists and WCModsNames gives the mod menu's pages (N.area, N.quest); and
the build reading them, with items' names, from its own edited Strings_EN. All from small copies of the
game's text tables."""
from wcmods import luacheck, pipeline, world

from tiny_names import EN, PLACES, STRINGS, reader


def test_place_names_reads_areas_and_ranked_quest_titles():
    areas, quests = world.place_names(reader(PLACES))
    assert areas == {"R-05": "Willow-Weep"}   # a short row (no name key) is left out
    assert quests["Quest.Procedural.Survival.Gather"] == {"Apprentice": "Feathering the Nests",
                                                          "Warrior": "Preparation is Readiness!"}   # .Title2 rows aren't titles


def test_place_names_rankup_titles():
    """A title with no rank segment is its quest's own, under its whole tag, not a quest cut short with the last
    segment as its rank (RankUp's title was filed under Progression, as rank "RankUp")."""
    _, quests = world.place_names(reader(PLACES))
    assert quests["Quest.Procedural.Progression.RankUp"] == {"": "The Proving Grounds"}
    assert quests["Quest.Procedural.Sleep.Rest1"] == {"": "A Time to Rest"}
    assert "Quest.Procedural.Progression" not in quests and "Quest.Procedural.Sleep" not in quests


def test_a_quest_title_with_no_text_is_left_out_rather_than_shown_as_its_key():
    _, quests = world.place_names(reader(PLACES))
    assert "Quest.Procedural.Progression.Escort" not in quests


def test_place_names_without_the_text_table_gives_nothing():
    assert world.place_names(reader({})) == ({}, {})


def test_place_texts_keeps_the_key_each_is_shown_from():
    texts = world.place_texts(reader(PLACES))
    assert texts["areas"] == [{"key": "STR_RIVERCLAN_ZONE_5", "code": "R-05", "text": "Willow-Weep"}]
    assert texts["quests"][0] == {"key": "QST_Gather.Apprentice.Title", "text": "Feathering the Nests", "quests": [
        {"tag": "Quest.Procedural.Survival.Gather", "quest": "Gather", "rank": "Apprentice"}]}
    assert [[q["quest"] for q in t["quests"]] for t in texts["quests"]] == [["Gather"], ["Gather"], ["RankUp"],
                                                                            ["Rest1", "Rest2", "Rest3"]]


def test_a_title_several_quests_share_is_one_row_that_names_them_all():
    """The game's Rest quests share one title text (QST_Sleep.Apprentice.Title titles Rest1, Rest2 and Rest3): one
    row, so the page has one box for it, and each quest still has its title for the mod menu."""
    texts = world.place_texts(reader(PLACES))
    rest = [t for t in texts["quests"] if t["key"] == "QST_Sleep.Apprentice.Title"]
    assert len(rest) == 1 and rest[0]["text"] == "A Time to Rest"
    assert [q["tag"] for q in rest[0]["quests"]] == [f"Quest.Procedural.Sleep.Rest{n}" for n in (1, 2, 3)]
    _, quests = world.place_names(reader(PLACES))
    assert all(quests[f"Quest.Procedural.Sleep.Rest{n}"] == {"": "A Time to Rest"} for n in (1, 2, 3))
    # Renamed, every quest it titles reads the new text.
    _, quests = world.place_names(reader({**PLACES, STRINGS: EN.replace("A Time to Rest", "Curl Up")}))
    assert {quests[f"Quest.Procedural.Sleep.Rest{n}"][""] for n in (1, 2, 3)} == {"Curl Up"}


def test_names_lua_takes_a_title_with_no_rank():
    lua = world.names_lua(places=world.place_names(reader(PLACES)))
    assert '["Quest.Procedural.Progression.RankUp"] = { [""] = "The Proving Grounds" }' in lua
    assert not luacheck.check(lua)


class Build:
    """What the build's text reader looks at: the files the build made (names.json's "text" edits a copy of
    Strings_EN), and the game's item table with the rows mods add."""

    def __init__(self, files):
        self.files = {path: (text.encode("utf-8"), "names", "csv edits") for path, text in files.items()}
        self.table_rows = {}

    def cooked_table(self, name):
        return [("Marigold", {"itemTag": "Gameplay.Inventory.Consumable.MediumHealingHerb",
                              "Name": {"table": "SwtStrings", "key": "STR_ITEM_CONSUMABLE_NAME_7"}})]

    def text(self, key):
        raise AssertionError("the game's own text: the build's edited copy should be read")


class Game:
    def read_text(self, path):
        return reader(PLACES)(path)


def test_build_names_lua_uses_the_edited_strings():
    edited = EN.replace("Willow-Weep", "Willow Hollow").replace(",Marigold", ",Sunpetal")
    build = Build({STRINGS: edited})
    read = pipeline.built_text(build, Game())
    lua = world.names_lua(None, world.item_names(build, pipeline.english(read)), world.place_names(read))
    assert '["R-05"] = "Willow Hollow"' in lua and '"Sunpetal"' in lua
    # Without an edited copy, the game's own.
    read = pipeline.built_text(Build({}), Game())
    assert world.place_names(read)[0] == {"R-05": "Willow-Weep"}
    assert pipeline.english(read)("STR_ITEM_CONSUMABLE_NAME_7") == "Marigold" and pipeline.english(read)("NOPE") == "NOPE"
