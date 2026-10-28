"""What a game update switched off, in a player's words (wcmods/exe/gamebuild.py): the Apply warning, `wcmods
game build` and the Mods page's banner name values by what they are, not by the game's C++ classes."""
from wcmods import game
from wcmods.exe import gamebuild

LEVEL = "/Script/SwtAdventure.SwtAdventureLevelComponent"
STATE = "/Script/SwtAdventure.SwtAdventureGameplayGameState"


def test_describe_says_it_in_plain_words():
    lost = [f"{LEVEL}:WCM_Level", f"{LEVEL}:WCM_LevelShown", f"{LEVEL}:WCM_Prowess", f"{LEVEL}:WCM_Stamina"]
    assert gamebuild.describe(lost) == "your cat's level and stats"
    assert gamebuild.describe(lost + [f"{STATE}:WCM_DayTime"]) == "your cat's level and stats; the time of day"
    assert gamebuild.describe(f"{STATE}:WCM_DayTime") == "the time of day"
    assert gamebuild.phrases(lost + [f"{STATE}:WCM_DayTime"] + lost) == ["your cat's level and stats",
                                                                          "the time of day"]
    assert gamebuild.describe([]) == ""


def test_every_value_wcmods_reads_has_plain_words():
    words = gamebuild.phrases(f"{cls}:{name}" for cls, fields in game.HIDDEN for name, _, _ in fields)
    assert len(words) == len(game.HIDDEN)
    assert not [w for w in words if "Component" in w or "GameState" in w or "WCM_" in w]


def test_a_class_without_words_is_named_as_it_is():
    assert gamebuild.describe("/Script/Wrc.WrcSomethingNew:WCM_Value") == "WrcSomethingNew.Value"
    assert gamebuild.name(f"{LEVEL}:WCM_Level") == "SwtAdventureLevelComponent.Level"
