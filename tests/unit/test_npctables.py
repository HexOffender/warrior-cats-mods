"""wcmods/npctables.py: the game's tables for making clan cats, as JSON for C++ mods (docs/plans/clan-life.md, S6)."""
from wcmods import npctables

FILES = {
    "PreffixName.csv": "#,Preffix,ThunderClan,RiverClan,ShadowClan,WindClan,OutOfClans,Preffix_ID\n"
                       "1,Wood,0.04,0,0,0,0.02,STR_CAT_NAME1\n2,Ember,0.05,0,0.01,0,0,STR_CAT_NAME2\n",
    "SuffixName.csv": "#,Suffix,Kit,Apprentice,Warrior,Deputy,Leader,MedicineCat,Queen,Elder,RogueCat,RogueCatLeader,"
                      "StarClanAncestor,Suffix_ID\n1,kit,1,0,0,0,0,0,0,0,0,0,0,_KIT\n"
                      "3,blaze,0,0,0.1,0.1,0,0.1,0.1,0.1,0.1,0.1,0.05,_BLAZE\n",
    "NameBanList.csv": "#,Name,PrefixID,SuffixID\n1,Tigerstar,STR_CAT_NAME32,_STAR\n",
    "RogueNames.csv": "#,Name,PrefixID\n1,Woody,STR_ROGUE_CAT_NAME_1\n",
    "BodyType.csv": 'Clan,Values\nThunderClan,"(0.00, 0.20, 0.80)"\nWindClan,"(1.00, 0.00, 0.00)"\n',
    "PatternBanList.csv": ",Name,Index\n1,gentleman,15\n2,motted,7\n",
    "ForcedAppearance.csv": ',Body,Fur,Eye,Ear,Whisker,Tail,Face\nKit,"(6,7,8,9)","(2,3)","(0,1)","(1,2)","(1)","(0,5)","(0,3)"\n',
    "CatSize.csv": "--,Role,MinScale,MaxScale\n1,Kit,0.1,0.15\n8,Leader,0.9,1\n",
    "Scars.csv": ",Role,Group,EarChance,BodyChance,EyeChance\n1,Elder,All,0.85,0.50,0.50\n",
    # the columns in another order than CLANS: read by name
    "ThunderClanNpcGenerator.csv": ",ThunderClan,ShadowClan,RiverClan,WindClan,OutOfClans\nWarrior,11,1,0,0,0\n",
}
TUNING = "Key,Value,\nGameplay.NPC.Heterochromia.Chance,0.2,\n"


def read(path):
    if path == npctables.TUNING:
        return TUNING
    name = path[len(npctables.NPC):]
    if name not in FILES:
        raise FileNotFoundError(path)
    return FILES[name]


def test_the_tables_read_as_the_game_has_them():
    d = npctables.build(read)
    assert d["prefixes"][1] == {"word": "Ember", "id": "STR_CAT_NAME2",
                                "weights": {"ThunderClan": 0.05, "RiverClan": 0, "ShadowClan": 0.01, "WindClan": 0, "OutOfClans": 0}}
    assert d["suffixes"][1]["word"] == "blaze" and d["suffixes"][1]["weights"]["Warrior"] == 0.1
    assert d["suffixes"][0]["weights"]["Kit"] == 1 and d["suffixes"][1]["id"] == "_BLAZE"
    assert d["banned"] == [{"name": "Tigerstar", "prefix": "STR_CAT_NAME32", "suffix": "_STAR"}]
    assert d["rogues"] == [{"word": "Woody", "id": "STR_ROGUE_CAT_NAME_1"}]
    assert d["looks"]["body"] == {"ThunderClan": [0.0, 0.2, 0.8], "WindClan": [1.0, 0.0, 0.0]}
    assert d["banned_patterns"] == [7, 15]
    assert d["kit_parts"] == {"body": [6, 7, 8, 9], "fur": [2, 3], "eyes": [0, 1], "ears": [1, 2], "whiskers": [1],
                              "tail": [0, 5], "face": [0, 3]}
    assert d["sizes"] == {"Kit": [0.1, 0.15], "Leader": [0.9, 1.0]}
    assert d["scars"] == [{"role": "Elder", "group": "All", "ear": 0.85, "body": 0.5, "eye": 0.5}]
    assert d["generators"]["ThunderClan"]["Warrior"]["ShadowClan"] == 1
    assert d["generators"]["ThunderClan"]["Warrior"]["RiverClan"] == 0
    assert d["odd_eyes"] == 0.2


def test_a_table_the_game_hasnt_got_is_named_not_fatal():
    d = npctables.build(read)
    assert "FaceType.csv" in d["missing"] and "face" not in d["looks"]
    assert "ShadowClanNpcGenerator.csv" in d["missing"]
    assert d["prefixes"]   # the rest still read


def test_a_short_kit_row_and_a_table_that_doesnt_read():
    files = dict(FILES)
    files["ForcedAppearance.csv"] = ',Body,Fur,Eye\nKit,"(6,7)"\n'

    def read_short(path):
        if path == npctables.TUNING:
            return TUNING
        name = path[len(npctables.NPC):]
        if name == "Scars.csv":
            raise ValueError("bad quoting")
        if name not in files:
            raise FileNotFoundError(path)
        return files[name]
    d = npctables.build(read_short)
    assert d["kit_parts"] == {"body": [6, 7], "fur": [], "eyes": []}
    assert "Scars.csv" in d["missing"] and d["problems"]["Scars.csv"] == "ValueError: bad quoting"
