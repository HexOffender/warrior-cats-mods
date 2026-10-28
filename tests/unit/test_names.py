"""The names planner (wcmods/names.py) on a tiny game made of CSV text: no game needed. Every rename keeps its
text (a cat never ends up with IDs the game has no text for), names.json's mistakes are refused in a sentence,
and what `python wcmods.py selftest` checks against the installed game (renames, additions, the ban list,
cats picked by name, place or "player" in one or two games) runs here too."""
import json
import os
import re

import pytest

from wcmods import names

from conftest import REPO
from tiny_names import cat, save, tiny_game

GAME = tiny_game()


def plan(spec, game=GAME):
    return names.Plan(game, names.merge([names.validate(spec)]))


def cats_of(data):
    return names.cats_in_save(data)


def rename(spec, data):
    """The plan for a names.json, its save ops and the cats as the Names page lists them."""
    p = plan(spec)
    cats = cats_of(data)
    ops = p.plan_cats(cats)
    return p, ops, {c["target"]: c for c in names.cat_list(p, cats, ops)}


WARRIOR = cat("Warrior", "STR_CAT_NAME1", "_HEART")          # Woodheart
ROGUE = cat("RogueCat", "STR_ROGUE_CAT_NAME_5")              # Fury, with no suffix


# ---------- every rename keeps its text ----------
def test_rogue_name_on_a_clan_cat_gets_fixed_texts():
    p, ops, listed = rename({"cats": {"player": "Storm"}}, save(player=WARRIOR))
    assert p.added_keys["STR_CAT_NAME_WCM_FIXED_STORM"] == "Storm"
    assert p.added_keys["STR_CAT_NAME_WCM_FIXED_STORM_HEART"] == "Storm"
    assert [o["set"] for o in ops] == [{"PrefixNameId": "STR_CAT_NAME_WCM_FIXED_STORM"}]
    assert listed["player"]["with_mods"] == "Storm" and listed["player"]["how"] == "fixed"
    assert p.warnings == []


def test_rogue_name_on_a_rogue_takes_the_rogue_id():
    p, ops, listed = rename({"cats": {"Fury": "Storm"}}, save(outsiders=[ROGUE]))
    assert [o["set"] for o in ops] == [{"PrefixNameId": "STR_ROGUE_CAT_NAME_16"}]
    assert ops[0]["from"] == "Fury" and ops[0]["to"] == "Storm"
    assert listed["Outsiders/0"]["how"] == "rogue"


def test_game_prefix_on_a_rogue_has_a_bare_text():
    p, ops, listed = rename({"cats": {"Fury": {"prefix": "Otter"}}}, save(outsiders=[ROGUE]))
    assert p.added_keys["STR_CAT_NAME53"] == "Otter"
    assert [o["set"] for o in ops] == [{"PrefixNameId": "STR_CAT_NAME53"}]
    assert listed["Outsiders/0"]["with_mods"] == "Otter" and listed["Outsiders/0"]["how"] == "prefix"
    # Every language has it, so no language shows a blank.
    for lang in names.LANGUAGES:
        assert {"Key": "STR_CAT_NAME53", "SourceString": "Otter"} in p.edits[names.strings_path(lang)]["+"]


def test_a_rogue_given_a_whole_name_gets_a_suffix_field():
    p, ops, _ = rename({"cats": {"Fury": "Otterheart"}}, save(outsiders=[ROGUE]))
    assert ops[0]["set"] == {"PrefixNameId": "STR_CAT_NAME53", "SuffixNameId": "_HEART"}
    renamed = names.rename_struct(ROGUE, ops[0]["set"], ops[0]["expect"])
    assert renamed == '(ClanType=RiverClan,Role=RogueCat,PrefixNameId="STR_CAT_NAME53",SuffixNameId="_HEART")'


def test_no_text_rename_is_skipped_with_a_warning():
    gone = cat("Warrior", "STR_CAT_NAME1", "_WCM_GONE")   # a suffix from a mod that's off
    p, ops, listed = rename({"cats": {"RiverClan/Warrior/0": {"prefix": "Otter"}}}, save(warriors=[gone]))
    assert ops == [] and p.cat_renames == []
    assert listed["RiverClan/Warrior/0"]["how"] == "none"
    assert p.notes == [("cats.RiverClan/Warrior/0", "The cat at RiverClan · Warrior · 0 would have no text in the game "
                        "as 'Otter', so it keeps its name; pick a name the game has, or a name of your own")]


def test_fixed_name_keeps_a_suffix_the_tables_lack():
    gone = cat("Warrior", "STR_CAT_NAME1", "_WCM_GONE")
    p, ops, listed = rename({"cats": {"RiverClan/Warrior/0": {"fixed": "Glow"}}}, save(warriors=[gone]))
    assert p.added_keys["STR_CAT_NAME_WCM_FIXED_GLOW_WCM_GONE"] == "Glow"
    # The added text goes into the pak with the others: plan_cats adds it to the build's edits too.
    added = {r["Key"] for r in p.edits[names.strings_path("EN")]["+"]}
    assert "STR_CAT_NAME_WCM_FIXED_GLOW_WCM_GONE" in added
    assert [o["to"] for o in ops] == ["Glow"] and listed["RiverClan/Warrior/0"]["how"] == "fixed"


def test_own_prefix_keeps_a_suffix_the_tables_lack():
    gone = cat("Warrior", "STR_CAT_NAME1", "_WCM_GONE")
    p, ops, _ = rename({"cats": {"RiverClan/Warrior/0": {"prefix": "Glimmer"}}}, save(warriors=[gone]))
    assert p.added_keys["STR_CAT_NAME_WCM_GLIMMER_WCM_GONE"] == "Glimmergone"
    assert [o["to"] for o in ops] == ["Glimmergone"]


def test_prefix_rename_clash_warns():
    p = plan({"prefixes": {"rename": {"Otter": "Wren"}}})
    assert ("prefixes.rename.Otter", "'Otter' renamed to 'Wren' would give two prefixes called Wren") in p.notes
    assert plan({"prefixes": {"rename": {"Otter": "Moth"}}}).warnings == []


def test_typo_whole_name_reports_fixed():
    _, ops, listed = rename({"cats": {"player": "Woodhart"}}, save(player=WARRIOR))
    assert listed["player"]["how"] == "fixed" and ops[0]["set"] == {"PrefixNameId": "STR_CAT_NAME_WCM_FIXED_WOODHART"}


def test_whole_name_of_parts_reports_parts_and_a_prefix_its_own():
    _, _, listed = rename({"cats": {"player": "Otterpelt"}}, save(player=WARRIOR))
    assert listed["player"]["how"] == "parts" and listed["player"]["with_mods"] == "Otterpelt"
    _, _, listed = rename({"cats": {"player": {"prefix": "Glimmer"}}}, save(player=WARRIOR))
    assert listed["player"]["how"] == "own-prefix" and listed["player"]["with_mods"] == "Glimmerheart"


def test_a_cat_already_renamed_needs_nothing_and_says_nothing():
    fixed = cat("Warrior", "STR_CAT_NAME_WCM_FIXED_SPARKLE", "_HEART")
    p, ops, _ = rename({"cats": {"Woodheart": {"fixed": "Sparkle"}}}, save(warriors=[fixed]))
    assert ops == [] and p.warnings == []


# ---------- cats a mod named ----------
def test_a_cat_named_by_a_mod_thats_off_is_listed_by_a_name_made_from_its_ids():
    sparkle = cat("Warrior", "STR_CAT_NAME_WCM_FIXED_SPARKLE", "_HEART")
    glimmer = cat("Apprentice", "STR_CAT_NAME_WCM_GLIMMER")   # an apprentice: its rank's suffix
    _, _, listed = rename({}, save(warriors=[sparkle, glimmer]))
    one, two = listed["RiverClan/Warrior/0"], listed["RiverClan/Warrior/1"]
    assert (one["name"], one["mod_named"], one["name_known"], one["was"]) == (
        "Sparkle", True, False, "STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART")
    assert two["name"] == "Glimmerpaw" and two["with_mods"] == ""
    assert not any(c["mod_named"] for c in rename({}, save(warriors=[WARRIOR]))[2].values())


def test_a_mod_named_cat_with_its_mod_on_is_listed_by_its_name():
    sparkle = cat("Warrior", "STR_CAT_NAME_WCM_FIXED_SPARKLE", "_HEART")
    _, _, listed = rename({"cats": {"Someone": {"fixed": "Sparkle"}}}, save(warriors=[sparkle]))
    one = listed["RiverClan/Warrior/0"]
    assert (one["name"], one["mod_named"], one["name_known"], one["was"]) == ("Sparkle", True, True, "Sparkle")


@pytest.mark.parametrize("key", ["STR_CAT_NAME_WCM_FIXED_SPARKLE_HEART", "STR_CAT_NAME_WCM_FIXED_SPARKLE", "Sparkle"])
def test_id_key_still_finds_the_cat(key):
    """A cats key or "was" an older page wrote as the cat's IDs (its name had no text then), or the name its IDs
    were made from, finds the cat, so a second rename of it reaches the save."""
    sparkle = cat("Warrior", "STR_CAT_NAME_WCM_FIXED_SPARKLE", "_HEART")
    _, ops, _ = rename({"cats": {key: "Otterheart"}}, save(warriors=[sparkle]))
    assert [o["set"] for o in ops] == [{"PrefixNameId": "STR_CAT_NAME53", "SuffixNameId": "_HEART"}]
    _, ops, _ = rename({"cats": {"RiverClan/Warrior/0": {"name": "Otterheart", "was": key}}}, save(warriors=[sparkle]))
    assert len(ops) == 1


def test_losing_text_finds_the_key_the_game_looks_up():
    data = save(player=cat("Leader", "STR_CAT_NAME_WCM_FAWN", "_STAR"),
                warriors=[cat("Warrior", "STR_CAT_NAME_WCM_GLIMMER", "_WCM_GONE"), WARRIOR],
                outsiders=[cat("RogueCat", "STR_ROGUE_CAT_NAME_WCM_MOSS")])
    # The bare prefix's text doesn't save a cat whose suffix has none: the game looks up prefix + suffix.
    have = {"STR_CAT_NAME_WCM_GLIMMER", "STR_CAT_NAME1_HEART"}
    lost = names.without_text(cats_of(data), [], have.__contains__)
    assert lost == [("you", "STR_CAT_NAME_WCM_FAWN_STAR"), ("Outsiders/0", "STR_ROGUE_CAT_NAME_WCM_MOSS"),
                    ("RiverClan/Warrior/0", "STR_CAT_NAME_WCM_GLIMMER_WCM_GONE")]
    assert names.without_text(cats_of(data), [], lambda key: True) == []


@pytest.mark.parametrize("ids, name", [
    ({"PrefixNameId": "STR_CAT_NAME_WCM_FIXED_SPARKLE", "SuffixNameId": "_HEART"}, "Sparkle"),
    ({"PrefixNameId": "STR_CAT_NAME_WCM_FIXED_MIST_STAR"}, "Mist Star"),
    ({"PrefixNameId": "STR_CAT_NAME_WCM_FAWN", "SuffixNameId": "_STAR"}, "Fawnstar"),
    ({"PrefixNameId": "STR_CAT_NAME_WCM_FAWN", "Role": "Kit"}, "Fawnkit"),
    ({"PrefixNameId": "STR_ROGUE_CAT_NAME_WCM_MOSS"}, "Moss"),
    ({"PrefixNameId": "STR_CAT_NAME53", "SuffixNameId": "_WCM_WHISPER"}, ""),   # the game's prefix: needs its tables
    ({"PrefixNameId": "SOMETHING"}, ""),
])
def test_guess_name_reads_wcmods_ids(ids, name):
    assert names.guess_name(ids) == name


def test_guess_name_takes_the_games_parts_from_a_plan():
    p = plan({"prefixes": {"rename": {"Otter": "Moth"}}})
    assert names.guess_name({"PrefixNameId": "STR_CAT_NAME53", "SuffixNameId": "_WCM_WHISPER"}, p) == "Mothwhisper"


# ---------- the check says what's wrong ----------
LEAF_MISTAKES = [
    ({"prefixes": {"rename": {"Otter": ""}}}, "names.json: prefixes.rename.Otter should be the new text, not empty"),
    ({"prefixes": {"rename": {"Otter": None}}}, "names.json: prefixes.rename.Otter should be the new text, not empty"),
    ({"rogues": {"rename": {"Fury": 3}}}, "names.json: rogues.rename.Fury should be the new text, in quotes"),
    ({"prefixes": {"weights": {"Otter": "lots"}}},
     'names.json: prefixes.weights.Otter should be an object like {"ThunderClan": 0.07}'),
    ({"prefixes": {"weights": {"Otter": {"ThunderClan": "lots"}}}},
     "names.json: prefixes.weights.Otter.ThunderClan should be a number"),
    ({"suffixes": {"weights": {"heart": [1]}}}, 'names.json: suffixes.weights.heart should be an object like {"Warrior": 0.07}'),
    ({"prefixes": {"add": {"Sparrow": {"clans": [1, 2]}}}},
     'names.json: prefixes.add.Sparrow.clans should be an object like {"ThunderClan": 0.07}'),
    ({"suffixes": {"add": {"whisper": {"ranks": {"Warrior": "often"}}}}},
     'names.json: suffixes.add.whisper.ranks should be an object like {"Warrior": 0.07}'),
    ({"prefixes": {"add": {"Sparrow": {"like": 5}}}}, "names.json: prefixes.add.Sparrow.like should be the name of a prefix, in quotes"),
    ({"prefixes": {"add": {"Sparrow": {"looks": [1]}}}}, "names.json: prefixes.add.Sparrow.looks should be an object"),
    ({"prefixes": {"remove": [1]}}, "names.json: prefixes.remove should be a list of names in quotes"),
    ({"rogues": {"add": [{"name": "Moss"}]}}, "names.json: rogues.add should be a list of names in quotes"),
    ({"banned": {"add": [None]}}, "names.json: banned.add should be a list of names in quotes"),
    ({"banned": {"remove": [7]}}, "names.json: banned.remove should be a list of names in quotes"),
    ({"cats": {"RiverClan/Warrior/0": {"name": "Moth", "was": 3}}},
     "names.json: cats.RiverClan/Warrior/0.was should be the name the cat had, in quotes"),
    ({"names": {"Rock": ["Pebble"]}}, "names.json: names.Rock should be the new text"),
    ({"text": {"STR_BOT_NAME_1": {"to": "X"}}}, "names.json: text.STR_BOT_NAME_1 should be the new text"),
]


@pytest.mark.parametrize("spec, said", LEAF_MISTAKES)
def test_validate_reports_leaf_mistakes(spec, said):
    with pytest.raises(ValueError) as e:
        names.validate(spec)
    assert str(e.value) == said


def test_what_validate_refuses_would_have_broken_the_plan():
    """Each refused shape, past the check, ends in a Python error or a name made of nothing: why it's refused."""
    for spec in ({"prefixes": {"weights": {"Otter": "lots"}}}, {"prefixes": {"weights": {"Otter": {"ThunderClan": "x"}}}},
                 {"prefixes": {"add": {"Sparrow": {"clans": [1, 2]}}}}, {"prefixes": {"remove": [1]}}):
        with pytest.raises((AttributeError, ValueError, TypeError)):
            names.Plan(GAME, names.merge([spec]))
    assert names.Plan(GAME, names.merge([{"prefixes": {"rename": {"Otter": ""}}}])).edits[names.strings_path("EN")][
        "STR_CAT_NAME53_PAW"] == {"SourceString": "paw"}


def documented_examples():
    with open(os.path.join(REPO, "wcmods", "templates", "names", "names.json"), encoding="utf-8") as f:
        template = json.load(f)
    with open(os.path.join(REPO, "docs", "formats.md"), encoding="utf-8") as f:
        docs = f.read()
    block = re.search(r"### `names\.json`\n```json\n(.*?)\n```", docs, re.S).group(1)
    return [template["_example"], {k: v for k, v in template.items() if k != "_example"}, json.loads(block)]


def test_validate_accepts_every_documented_shape():
    for spec in documented_examples():
        plan(spec)   # validated, and planned without an error


def test_validate_keeps_todays_tolerant_shapes():
    """Shapes that apply today still do: an add that isn't an object (the average part), a weight in quotes,
    a cats entry with two kinds of name (the first that counts wins), a number as a name's new text."""
    p = plan({"prefixes": {"add": {"Sparrow": True}, "weights": {"Otter": {"ThunderClan": "0.07"}}},
              "cats": {"player": {"name": "Otterheart", "fixed": "Sparkle"}}, "names": {"Rock": 5}})
    assert any(a["Preffix"] == "Sparrow" for a in p.edits[names.PREFIXES]["+"])
    assert p.edits[names.PREFIXES]["3"]["ThunderClan"] == 0.07
    assert p.final["STR_CRAFT_MATERIAL_NAME_20"] == "5"


def test_warnings_have_rows():
    p = plan({"prefixes": {"rename": {"Ottr": "Moth"}, "weights": {"Otter": {"ThunderClam": 1}}},
              "suffixes": {"remove": ["kit"]}, "rogues": {"add": ["Fox"]}, "banned": {"remove": ["Nobody"]},
              "names": {"Rokc": "Pebble"}, "cats": {"player": {"was": "x"}}})
    assert [where for where, _ in p.notes] == [
        "prefixes.rename.Ottr", "prefixes.weights.Otter", "suffixes.remove.kit", "rogues.add.Fox",
        "banned.remove.Nobody", "cats.player", "names.Rokc"]
    assert p.warnings == [text for _, text in p.notes]


def test_warnings_use_no_command_line_or_json_words():
    data = save(warriors=[WARRIOR, WARRIOR.replace("ClanType=RiverClan", "ClanType=RiverClan,X=1")])
    p = plan({"prefixes": {"rename": {"Ottr": "Moth"}, "add": {"Wood": {}}}, "cats": {"Woodheart": "Otterheart",
              "Nobody": "Mothheart", "player": {}}})
    p.plan_cats(cats_of(data))
    assert p.warnings
    for w in p.warnings:
        assert not re.search(r"--|`|\{|\}|\bnames\.json\b|STR_", w), w


# ---------- what the selftest checks, on the tiny game ----------
def test_renames_reach_every_name_with_that_part_and_additions_every_language():
    p = plan({"prefixes": {"rename": {"Otter": "Moth"}, "add": {"Sparrow": {"like": "Wren"}}, "remove": ["Pigeon"]},
              "suffixes": {"add": {"whisper": {}}, "remove": ["kit"]},
              "rogues": {"add": ["Moss"]}, "banned": {"remove": ["Woodstar"], "add": ["Mothheart"]}})
    en = p.edits[names.strings_path("EN")]
    added = {r["Key"]: r["SourceString"] for r in en["+"]}
    assert en["STR_CAT_NAME53_PAW"] == {"SourceString": "Mothpaw"}
    assert added["STR_CAT_NAME_WCM_SPARROW_PAW"] == "Sparrowpaw" and added["STR_CAT_NAME53_WCM_WHISPER"] == "Mothwhisper"
    assert added["STR_ROGUE_CAT_NAME_WCM_MOSS"] == "Moss"
    assert set(added) <= {r["Key"] for r in p.edits[names.strings_path("DE")]["+"]}
    assert "STR_CAT_NAME2_PELT" not in added   # the combination the game leaves out stays out
    assert p.edits[names.PREFIXES]["-"] == ["5"]
    assert "-" not in p.edits[names.SUFFIXES]   # kit is kept
    assert ("suffixes.remove.kit", "'kit' is the only suffix for kits, so it's kept") in p.notes
    assert p.edits[names.BANNED]["-"] == ["1"] and p.edits[names.BANNED]["+"][0]["PrefixID"] == "STR_CAT_NAME53"
    # Sparrow is used like Wren: its clans' weights, and its looks on the name screen.
    sparrow = next(a for a in p.edits[names.PREFIXES]["+"] if a["Preffix"] == "Sparrow")
    assert sparrow["ThunderClan"] == 0.02 and sparrow["Preffix_ID"] == "STR_CAT_NAME_WCM_SPARROW"
    assert next(a for a in p.edits[names.PREFIX_LOOKS]["+"] if a["Prefix"] == "Sparrow")["Body_1"] == "2"


def test_merge_later_mods_win_name_by_name():
    a = names.validate({"prefixes": {"remove": ["Pigeon"], "add": {"Sparrow": {}}}, "cats": {"player": "Otterheart"}})
    b = names.validate({"prefixes": {"add": {"Pigeon": {}}, "remove": ["Sparrow"]}, "cats": {"player": "Wrenheart"}})
    merged = names.merge([a, b])
    assert merged["prefixes"]["remove"] == ["Sparrow"] and merged["prefixes"]["add"] == {"Pigeon": {}}
    assert merged["cats"] == {"player": "Wrenheart"}
    p = names.Plan(GAME, merged)
    assert "-" not in p.edits.get(names.PREFIXES, {}) or "5" not in p.edits[names.PREFIXES]["-"]
    assert not any(a["Preffix"] == "Sparrow" for a in p.edits.get(names.PREFIXES, {}).get("+", []))


def test_two_adds_number_their_rows_in_the_part_and_filters_tables():
    p = plan({"prefixes": {"add": {"Sparrow": {}, "Finch": {}}}})
    assert [a["#"] for a in p.edits[names.PREFIXES]["+"]] == ["6", "7"]
    assert [a["---"] for a in p.edits[names.PREFIX_LOOKS]["+"]] == ["6", "7"]


def test_a_slug_clash_is_warned_about_and_skipped():
    p = plan({"prefixes": {"add": {"Sun light": {}, "Sun-light": {}}}})
    assert [a["Preffix"] for a in p.edits[names.PREFIXES]["+"]] == ["Sun light"]
    assert ("prefixes.add.Sun-light", "'Sun-light' isn't added: inside the game it would have the same name as "
            "'Sun light'") in p.notes


def test_banned_clear_with_an_add():
    p = plan({"banned": {"clear": True, "add": ["Otterheart"]}})
    assert p.edits[names.BANNED]["-"] == ["1"]
    assert [(a["PrefixID"], a["SuffixID"]) for a in p.edits[names.BANNED]["+"]] == [("STR_CAT_NAME53", "_HEART")]


def test_ban_list_names_follow_renamed_parts():
    p = plan({"prefixes": {"rename": {"Wood": "Lion"}}})
    assert p.edits[names.BANNED]["1"] == {"Name": "Lionstar"}


def test_cats_story_roles_places_and_was():
    """A story role is a copy of a clan cat (renamed in both places); a place with "was" counts only while that
    cat still has that name; a cat that isn't there still gets its texts; a rename already in the save needs
    nothing and says nothing."""
    w = '(ClanType=RiverClan,Role=Warrior,PrefixNameId="{}",SuffixNameId="_HEART")'
    data = save(player=w.format("STR_CAT_NAME53"),
                warriors=[w.format("STR_CAT_NAME1"), w.format("STR_CAT_NAME2"), w.format("STR_CAT_NAME_WCM_FIXED_GLOW")],
                roles={"TheAgingLeader": w.format("STR_CAT_NAME1")})
    cats = cats_of(data)
    p = plan({"cats": {"Woodheart": {"fixed": "Sparkle"}, "RiverClan/Warrior/1": {"name": "Wrenheart", "was": "Someone"},
                       "Nobody": {"prefix": "Glimmer"}, "Was-glow": {"fixed": "Glow"}}})
    ops = p.plan_cats(cats)
    assert len(cats) == 4 and [len(c["paths"]) for c in cats if c["ids"]["PrefixNameId"] == "STR_CAT_NAME1"] == [2]
    assert sorted(o["where"] for o in ops) == ["NarrativeRoles/TheAgingLeader", "RiverClan/Warrior/0"]
    assert p.added_keys["STR_CAT_NAME_WCM_FIXED_SPARKLE_PAW"] == "Sparkle"
    assert p.added_keys["STR_CAT_NAME_WCM_GLIMMER_PAW"] == "Glimmerpaw"
    assert [n for n in p.notes if n[0].startswith("cats.")] == [
        ("cats.RiverClan/Warrior/1", "The cat at RiverClan · Warrior · 1 isn't called 'Someone' any more, so it isn't "
                                     "renamed; rename it again from the list"),
        ("cats.Nobody", "No cat in your save is called 'Nobody'")]
    listed = {c["target"]: c for c in names.cat_list(p, cats, ops)}
    assert listed["RiverClan/Warrior/2"]["name"] == "Glow" and listed["player"]["name"] == "Otterheart"
    assert listed["RiverClan/Warrior/0"]["with_mods"] == "Sparkle" and listed["RiverClan/Warrior/0"]["roles"] == ["TheAgingLeader"]
    assert p.cat_renames == [("Woodheart", "Sparkle")] and p.rename_targets == ["Woodheart"]


def test_cats_in_two_games():
    """Two games in one save (slot 1 being played): its cats come first, your cat first in each; "player", a
    name or a place means the game being played, and a slot first picks another game's cat."""
    w = '(ClanType=RiverClan,Role=Warrior,PrefixNameId="{}",SuffixNameId="_HEART")'
    data = {"Shared": {"General": {"CurrentCatSlot": 1}},
            **save(player=w.format("STR_CAT_NAME53"), warriors=[w.format("STR_CAT_NAME1"), w.format("STR_CAT_NAME60")]),
            **save(player=w.format("STR_CAT_NAME53"), warriors=[w.format("STR_CAT_NAME1")], slot="1")}
    cats = cats_of(data)
    assert names.current_slot(data) == "1"
    assert [(c["slot"], c["player"], c["current"]) for c in cats] == [
        ("1", True, True), ("1", False, True), ("0", True, False), ("0", False, False), ("0", False, False)]
    p = plan({"cats": {"player": {"fixed": "Me"}, "Woodheart": {"fixed": "Sparkle"}, "0/RiverClan/Warrior/0": {"fixed": "Other"},
                       "Wrenheart": {"fixed": "Far"}, "1/": {"fixed": "Nothing"}}})
    ops = sorted((o["path"], o["to"], o["where"]) for o in p.plan_cats(cats))
    assert ops == [("0/NPCData/RiverClan/Warrior/0", "Other", "0/RiverClan/Warrior/0"),
                   ("0/NPCData/RiverClan/Warrior/1", "Far", "0/RiverClan/Warrior/1"),
                   ("1/GameplayProgression/Gameplay.Combat.Character.Cat.Player/Customization", "Me", "you"),
                   ("1/NPCData/RiverClan/Warrior/0", "Sparkle", "RiverClan/Warrior/0")]
    assert [n for n in p.notes if n[0].startswith("cats.")] == [("cats.1/", "'1/' doesn't say which cat")]
    shown = names.cat_list(p, cats, ())
    assert [c["target"] for c in shown] == ["player", "RiverClan/Warrior/0", "0/player", "0/RiverClan/Warrior/0",
                                            "0/RiverClan/Warrior/1"]


def test_identical_clan_cats_stay_two_cats():
    data = save(warriors=[WARRIOR, WARRIOR], roles={"TheAgingLeader": WARRIOR})
    cats = cats_of(data)
    assert [c["paths"] for c in cats] == [["0/NPCData/RiverClan/Warrior/0", "0/NPCData/NarrativeRoles/TheAgingLeader"],
                                          ["0/NPCData/RiverClan/Warrior/1"]]
    p = plan({"cats": {"RiverClan/Warrior/1": "Otterheart"}})
    assert [o["path"] for o in p.plan_cats(cats)] == ["0/NPCData/RiverClan/Warrior/1"]


def test_without_text_after_a_build_with_empty_ops():
    data = save(warriors=[cat("Warrior", "STR_CAT_NAME_WCM_FIXED_GLOW", "_HEART")])
    p = plan({})
    assert names.without_text(cats_of(data), p.plan_cats(cats_of(data)), p.final.__contains__) == [
        ("RiverClan/Warrior/0", "STR_CAT_NAME_WCM_FIXED_GLOW_HEART")]
    p = plan({"cats": {"Nobody": {"fixed": "Glow"}}})   # the mod that named it is on again
    assert names.without_text(cats_of(data), p.plan_cats(cats_of(data)), p.final.__contains__) == []


def test_names_entries_say_what_else_they_rename():
    p = plan({"names": {"Rock": "Pebble", "Fox": "Russet", "Brightheart": "Brightfur"}})
    assert p.names_hits["Rock"] == {"cats": ["the cameo cat Rock"], "elsewhere": ["the material Rock", "a line in a quest"]}
    assert p.names_hits["Fox"] == {"cats": ["the rogue name Fox"], "elsewhere": ["the animal Fox"]}
    assert p.names_hits["Brightheart"] == {"cats": ["the cameo cat Brightheart"], "elsewhere": []}
    assert p.final["STR_CRAFT_MATERIAL_NAME_20"] == "Pebble"   # as it always has: every text that's exactly the name
    assert p.changed == 3


def test_describe_target_says_a_cats_key_in_words():
    assert [names.describe_target(t) for t in ("player", "2/player", "Blaze", "1/Blaze", "RiverClan/Warrior/3")] == [
        "your cat", "your cat in cat slot 2", "Blaze", "Blaze in cat slot 1", "the cat at RiverClan · Warrior · 3"]
